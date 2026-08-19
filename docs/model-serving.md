# Production model serving

Run the model service on a Linux NVIDIA host. The API only requires an OpenAI-compatible `/v1/chat/completions` endpoint and does not import GPU frameworks.

The exact adapter metadata declares:

```text
base_model_name_or_path: Qwen/Qwen3-VL-2B-Instruct
adapter: E:\CodingFolder\LlamaFactory\LlamaFactory\saves\Qwen3-VL-2B-Instruct\lora\train_2026-06-27-00-01-40
```

Before deployment, run `services/model/compatibility.py preflight`, prepare a reviewed 10–20 case golden set, and compare Transformers/PEFT, direct vLLM LoRA, and a merged model. Promote only the configuration whose output matches the PEFT reference within the team's reviewed tolerance.

Once selected, expose the chosen service name as `clash-detection-qwen3-vl-2b`, set `INFERENCE_PROVIDER=openai`, and point `INFERENCE_BASE_URL` at the server. Keep model and adapter artifacts outside the application image and mount them read-only.

Operational checks should record:

- base and adapter content hashes;
- GPU model and memory;
- first-token latency;
- tokens per second;
- maximum concurrent requests before queuing;
- vLLM and CUDA versions;
- comparison artifact from the golden set.

The normal automated suite deliberately excludes GPU checks.
