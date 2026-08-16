"""Preflight model metadata and compare OpenAI-compatible vision endpoints."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ComparisonResult:
    endpoint: str
    case_id: str
    elapsed_seconds: float
    response_sha256: str
    response: str


def adapter_base(adapter_dir: Path) -> str:
    config_path = adapter_dir / "adapter_config.json"
    if not config_path.is_file():
        raise ValueError(f"Missing adapter metadata: {config_path}")
    data = json.loads(config_path.read_text(encoding="utf-8"))
    base = data.get("base_model_name_or_path")
    if not isinstance(base, str) or not base.strip():
        raise ValueError("adapter_config.json has no base_model_name_or_path")
    return base


def preflight(adapter_dir: Path, expected_base: str) -> None:
    actual_base = adapter_base(adapter_dir)
    if actual_base != expected_base:
        raise ValueError(
            f"Adapter/base mismatch: adapter declares {actual_base!r}, "
            f"but configuration requested {expected_base!r}"
        )
    weights = adapter_dir / "adapter_model.safetensors"
    if not weights.is_file() or weights.stat().st_size == 0:
        raise ValueError(f"Missing adapter weights: {weights}")
    print(json.dumps({"status": "compatible", "base_model": actual_base}))


def _data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    media_type = "image/png" if suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _request(endpoint: str, model: str, prompt: str, image_path: Path) -> str:
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _data_url(image_path)}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        body: dict[str, Any] = json.load(response)
    return str(body["choices"][0]["message"]["content"])


def compare(manifest_path: Path, endpoints: list[str], output_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    results: list[ComparisonResult] = []
    for endpoint_spec in endpoints:
        name, endpoint = endpoint_spec.split("=", 1)
        for case in manifest["cases"]:
            started = time.perf_counter()
            response = _request(
                endpoint,
                case.get("model", manifest["model"]),
                case["prompt"],
                (root / case["image"]).resolve(),
            )
            results.append(
                ComparisonResult(
                    endpoint=name,
                    case_id=case["id"],
                    elapsed_seconds=round(time.perf_counter() - started, 4),
                    response_sha256=hashlib.sha256(response.encode("utf-8")).hexdigest(),
                    response=response,
                )
            )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--adapter", type=Path, required=True)
    preflight_parser.add_argument("--expected-base", required=True)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--manifest", type=Path, required=True)
    compare_parser.add_argument("--endpoint", action="append", required=True)
    compare_parser.add_argument("--output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "preflight":
        preflight(args.adapter, args.expected_base)
    else:
        compare(args.manifest, args.endpoint, args.output)


if __name__ == "__main__":
    main()

