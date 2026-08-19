# Model compatibility and serving

## Authoritative model pair

- Base: `Qwen/Qwen3-VL-2B-Instruct`
- Adapter: `E:\CodingFolder\LlamaFactory\LlamaFactory\saves\Qwen3-VL-2B-Instruct\lora\train_2026-06-27-00-01-40`

The adapter metadata is authoritative. Run the preflight before any comparison:

```bash
python services/model/compatibility.py preflight \
  --adapter 'E:\CodingFolder\LlamaFactory\LlamaFactory\saves\Qwen3-VL-2B-Instruct\lora\train_2026-06-27-00-01-40' \
  --expected-base Qwen/Qwen3-VL-2B-Instruct
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
vllm serve Qwen/Qwen3-VL-2B-Instruct \
  --enable-lora \
  --enable-tower-connector-lora \
  --enable-log-requests \
  --enable-log-outputs \
  --max-lora-rank 8 \
  --lora-modules clash-detection-qwen3-vl-2b=/models/train_2026-06-27-00-01-40
```

`--enable-log-outputs` writes the generated response to the vLLM server logs. It requires
`--enable-log-requests`; remove both flags after debugging because requests and model output
may contain sensitive project data.

This is a compatibility candidate, not a production recommendation, until its golden-set output matches Transformers/PEFT. Keep vLLM media inputs as API-supplied data URLs; do not enable unrestricted remote media fetching.
