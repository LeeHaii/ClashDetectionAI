# Model compatibility and serving

## Authoritative model pair

- Base: `Qwen/Qwen2.5-VL-7B-Instruct`
- Adapter: `E:\Downloads\clashAI\train_2026-07-29-14-13-40`

The adapter metadata is authoritative. Run the preflight before any comparison:

```bash
python services/model/compatibility.py preflight \
  --adapter 'E:\Downloads\clashAI\train_2026-07-29-14-13-40' \
  --expected-base Qwen/Qwen2.5-VL-7B-Instruct
```

## Compatibility spike

Use a Linux NVIDIA host and the manifest in `tests/fixtures/model-responses/golden-set.example.json`. Compare deterministic output from:

1. Transformers + PEFT.
2. vLLM with a static LoRA module.
3. vLLM serving a merged, versioned model if direct LoRA output is incompatible.

The HTTP comparison command consumes OpenAI-compatible endpoints and records latency and response hashes:

```bash
python services/model/compatibility.py compare \
  --manifest tests/fixtures/model-responses/golden-set.json \
  --endpoint peft=http://peft:8000/v1 \
  --endpoint direct-lora=http://vllm-lora:8000/v1 \
  --endpoint merged=http://vllm-merged:8000/v1 \
  --output artifacts/model-comparison.json
```

Do not promote a serving mode until the golden set has been reviewed and the selected provider has reproducible output. vLLM belongs on Linux; the Windows development path uses the API's deterministic mock provider or a separately hosted OpenAI-compatible endpoint.

Current vLLM releases expose experimental tower/connector LoRA support for Qwen-VL models. The direct-LoRA candidate should therefore be launched with the adapter's actual rank and the tower/connector flag:

```bash
vllm serve Qwen/Qwen2.5-VL-7B-Instruct \
  --enable-lora \
  --enable-tower-connector-lora \
  --max-lora-rank 32 \
  --lora-modules clash-detection-qwen2.5-vl-7b=/models/train_2026-07-29-14-13-40
```

This is a compatibility candidate, not a production recommendation, until its golden-set output matches Transformers/PEFT. Keep vLLM media inputs as API-supplied data URLs; do not enable unrestricted remote media fetching.
