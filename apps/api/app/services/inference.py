from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AnalysisResult, ClashItem, InferenceRun, Message
from app.domain.enums import RunStatus
from app.repositories.conversations import MessageRepository
from app.services.analysis import AnalysisNormalizer, ModelInput, PromptBuilder
from app.services.events import RunEventBroker
from app.services.inference_client import InferenceProvider
from app.services.storage import StorageService


class RunCancelled(Exception):
    pass


class InferenceService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        storage: StorageService,
        provider: InferenceProvider,
        broker: RunEventBroker,
        prompt_builder: PromptBuilder,
        normalizer: AnalysisNormalizer,
        max_concurrent_runs: int,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.provider = provider
        self.broker = broker
        self.prompt_builder = prompt_builder
        self.normalizer = normalizer
        self._capacity = asyncio.Semaphore(max_concurrent_runs)
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(self, run_id: str) -> None:
        task = asyncio.create_task(self._execute(run_id), name=f"inference-{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(lambda _task: self._tasks.pop(run_id, None))

    def interrupt(self, run_id: str) -> None:
        task = self._tasks.get(run_id)
        if task is not None and not task.done():
            task.cancel()

    async def _execute(self, run_id: str) -> None:
        started = time.perf_counter()
        session = self.session_factory()
        try:
            run = session.get(InferenceRun, run_id)
            if run is None:
                return
            if run.cancellation_requested:
                raise RunCancelled
            run.status = RunStatus.RUNNING
            run.started_at = datetime.now(UTC)
            session.commit()
            await self.broker.publish(run_id, "run.started", {"run_id": run_id})

            user_message = session.get(Message, run.user_message_id)
            if user_message is None:
                raise ValueError("User message no longer exists")
            clash = session.get(ClashItem, run.clash_item_id) if run.clash_item_id else None
            history = self._history(session, run.conversation_id, user_message.sequence)
            image_path = None
            if clash and clash.image_path:
                image_path = self.storage.absolute(clash.image_path)
            else:
                image_attachment = next(
                    (
                        attachment
                        for attachment in user_message.attachments
                        if attachment.media_type in {"image/jpeg", "image/png"}
                    ),
                    None,
                )
                if image_attachment is not None:
                    image_path = self.storage.absolute(image_attachment.storage_path)
            model_input = ModelInput(
                prompt=self.prompt_builder.build(question=user_message.content, clash=clash),
                image_path=image_path,
                history=history,
            )

            output: list[str] = []
            first_token_at: float | None = None
            await self.broker.publish(run_id, "progress", {"stage": "queued"})
            async with self._capacity:
                await self.broker.publish(run_id, "progress", {"stage": "inference"})
                async for delta in self.provider.stream(model_input):
                    session.refresh(run, attribute_names=["cancellation_requested"])
                    if run.cancellation_requested:
                        raise RunCancelled
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                        run.first_token_ms = (first_token_at - started) * 1_000
                        session.commit()
                    output.append(delta)
                    await self.broker.publish(run_id, "content.delta", {"delta": delta})

            raw_output = "".join(output).strip()
            normalized = self.normalizer.normalize(raw_output, run, clash)
            markdown = self.normalizer.to_markdown(normalized)
            result = AnalysisResult(
                inference_run_id=run.id,
                raw_model_output=raw_output,
                normalized=normalized.model_dump(mode="json"),
                markdown=markdown,
                parser_version=normalized.parser_version,
                severity_rule_version=normalized.severity_rule_version,
            )
            assistant = MessageRepository(session).create(
                conversation_id=run.conversation_id,
                role="assistant",
                content=markdown,
            )
            run.result = result
            run.assistant_message_id = assistant.id
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.now(UTC)
            run.duration_ms = (time.perf_counter() - started) * 1_000
            session.commit()
            await self.broker.publish(
                run_id,
                "result.completed",
                {
                    "result": normalized.model_dump(mode="json"),
                    "markdown": markdown,
                    "assistant_message_id": assistant.id,
                },
            )
            await self.broker.finish(run_id)
        except (RunCancelled, asyncio.CancelledError):
            session.rollback()
            run = session.get(InferenceRun, run_id)
            if run is not None:
                run.status = RunStatus.CANCELLED
                run.cancellation_requested = True
                run.completed_at = datetime.now(UTC)
                run.duration_ms = (time.perf_counter() - started) * 1_000
                session.commit()
            await self.broker.publish(run_id, "run.cancelled", {"run_id": run_id})
            await self.broker.finish(run_id)
        except Exception as error:
            session.rollback()
            run = session.get(InferenceRun, run_id)
            if run is not None:
                run.status = RunStatus.FAILED
                run.error = str(error)[:4_000]
                run.completed_at = datetime.now(UTC)
                run.duration_ms = (time.perf_counter() - started) * 1_000
                session.commit()
            await self.broker.publish(run_id, "error", {"message": str(error)})
            await self.broker.finish(run_id)
        finally:
            session.close()

    @staticmethod
    def _history(
        session: Session, conversation_id: str, before_sequence: int
    ) -> list[dict[str, str]]:
        messages = list(
            session.scalars(
                select(Message)
                .where(
                    Message.conversation_id == conversation_id,
                    Message.sequence < before_sequence,
                )
                .order_by(Message.sequence.desc())
                .limit(8)
            )
        )
        return [
            {"role": message.role, "content": message.content}
            for message in reversed(messages)
            if message.role in {"user", "assistant"}
        ]
