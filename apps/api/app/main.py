from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings
from app.db.base import Base
from app.db.session import create_engine_and_session
from app.services.analysis import AnalysisNormalizer, PromptBuilder
from app.services.events import RunEventBroker
from app.services.html_parser import HtmlParser
from app.services.inference import InferenceService
from app.services.inference_client import (
    InferenceProvider,
    MockInferenceProvider,
    OpenAIInferenceProvider,
)
from app.services.report_ingestion import ReportIngestionService
from app.services.report_renderer import ReportRenderer
from app.services.storage import StorageService


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or Settings()
    configured.prepare_directories()
    engine, session_factory = create_engine_and_session(configured.database_url)
    storage = StorageService(
        configured.storage_root,
        max_upload_bytes=configured.max_upload_bytes,
        max_archive_entries=configured.max_archive_entries,
        max_archive_uncompressed_bytes=configured.max_archive_uncompressed_bytes,
    )
    parser = HtmlParser(configured.parser_version)
    broker = RunEventBroker()
    provider: InferenceProvider
    if configured.inference_provider == "mock":
        provider = MockInferenceProvider()
    elif configured.inference_provider == "openai":
        provider = OpenAIInferenceProvider(
            base_url=configured.inference_base_url,
            api_key=configured.inference_api_key,
            model=configured.served_model_name,
            timeout_seconds=configured.inference_timeout_seconds,
        )
    else:
        raise ValueError("INFERENCE_PROVIDER must be 'mock' or 'openai'")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = FastAPI(title="ClashDetectionAI API", version="0.1.0", lifespan=lifespan)
    app.state.settings = configured
    app.state.session_factory = session_factory
    app.state.storage = storage
    app.state.ingestion = ReportIngestionService(storage, parser)
    app.state.broker = broker
    app.state.renderer = ReportRenderer(storage)
    app.state.inference = InferenceService(
        session_factory=session_factory,
        storage=storage,
        provider=provider,
        broker=broker,
        prompt_builder=PromptBuilder(configured.prompt_version),
        normalizer=AnalysisNormalizer(
            parser_version=configured.parser_version,
            severity_rule_version=configured.severity_rule_version,
        ),
        max_concurrent_runs=configured.max_concurrent_inference,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
