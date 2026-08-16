from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from collections.abc import AsyncIterator
from typing import Protocol

import httpx

from app.services.analysis import ModelInput


class InferenceProvider(Protocol):
    def stream(self, model_input: ModelInput) -> AsyncIterator[str]: ...


class MockInferenceProvider:
    response = """| Field | Value |
|---|---|
| Clash | True |
| Clash type | Intersected |
| Orientation | Horizontal |
| Cross-sectional shape | Circular |
| Cross-sectional size | Small |
| Explanation | The selected elements visibly overlap. |"""

    async def stream(self, model_input: ModelInput) -> AsyncIterator[str]:
        del model_input
        for token in self.response.split(" "):
            await asyncio.sleep(0.002)
            yield token + " "


class OpenAIInferenceProvider:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def stream(self, model_input: ModelInput) -> AsyncIterator[str]:
        content: list[dict[str, object]] = []
        if model_input.image_path is not None:
            media_type = mimetypes.guess_type(model_input.image_path.name)[0] or "image/jpeg"
            encoded = base64.b64encode(model_input.image_path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{encoded}"},
                }
            )
        content.append({"type": "text", "text": model_input.prompt})
        messages: list[dict[str, object]] = []
        for message in model_input.history:
            messages.append({"role": message["role"], "content": message["content"]})
        messages.append({"role": "user", "content": content})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "stream": True,
        }
        timeout = httpx.Timeout(self.timeout_seconds, connect=10)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ")
                    if data == "[DONE]":
                        break
                    item = json.loads(data)
                    delta = item.get("choices", [{}])[0].get("delta", {}).get("content")
                    if isinstance(delta, str) and delta:
                        yield delta
