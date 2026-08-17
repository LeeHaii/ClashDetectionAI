# Production model serving

Run the model service on a Linux NVIDIA host. The API only requires an OpenAI-compatible `/v1/chat/completions` endpoint and does not import GPU frameworks.

The exact adapter metadata declares:

```text
base_model_name_or_path: Qwen/Qwen2.5-VL-7B-Instruct
adapter: E:\Downloads\clashAI\train_2026-07-29-14-13-40
```

Before deployment, run `services/model/compatibility.py preflight`, prepare a reviewed 10–20 case golden set, and compare Transformers/PEFT, direct vLLM LoRA, and a merged model. Promote only the configuration whose output matches the PEFT reference within the team's reviewed tolerance.

Once selected, expose the chosen service name as `clash-detection-qwen2.5-vl-7b`, set `INFERENCE_PROVIDER=openai`, and point `INFERENCE_BASE_URL` at the server. Keep model and adapter artifacts outside the application image and mount them read-only.

Operational checks should record:

- base and adapter content hashes;
- GPU model and memory;
- first-token latency;
- tokens per second;
- maximum concurrent requests before queuing;
- vLLM and CUDA versions;
- comparison artifact from the golden set.

The normal automated suite deliberately excludes GPU checks.
