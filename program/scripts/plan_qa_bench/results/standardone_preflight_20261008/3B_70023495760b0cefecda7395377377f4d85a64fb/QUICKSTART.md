# Quickstart

## Standard One 8B

1. Clone the repository.

```bash
git clone https://huggingface.co/StandardThinking/StandardOne-8B
```

2. Create a venv and install SGLang.

```bash
uv venv --python 3.12 .venv-sglang
uv pip install --python .venv-sglang/bin/python 'sglang==0.5.20'
```

3. Start the engine.

```bash
CUDA_VISIBLE_DEVICES=0 SGLANG_VLM_CACHE_SIZE_MB=0 .venv-sglang/bin/python -m sglang.launch_server \
  --model-path ./StandardOne-8B --served-model-name standard-one-8b \
  --host 127.0.0.1 --port 30000 --tp-size 1 --model-impl sglang --dtype bfloat16 \
  --context-length 32768 --max-running-requests 32 --mem-fraction-static 0.8 \
  --chunked-prefill-size -1 --disable-radix-cache --mm-preprocess-cache-size-mb 0 \
  --model-config-parser hf --load-format safetensors
```

4. Create a venv and install the adapter.

```bash
uv venv --python 3.12 .venv-native
pip install -e ./StandardOne-8B/server[native-tokenizer]
```

5. Start the adapter.

```bash
jev-adapter --engine-url http://127.0.0.1:30000 --model standard-one-8b --alias jev-latest \
  --host 0.0.0.0 --port 30120 --max-concurrency 1 \
  --tokenizer-model mistralai/Ministral-3-8B-Instruct-2512-BF16 \
  --tokenizer-revision f6fae9795746f63c9be8344932f01275f3c63734 \
  --prompt-wording served --label-scheme upper --default-temperature 1.65
```

6. Check health and models.

```bash
curl -s http://127.0.0.1:30120/health
curl -s http://127.0.0.1:30120/v1/models
```

7. Send a request.

```bash
curl -s http://127.0.0.1:30120/v1/systemone -X POST -H 'content-type: application/json' -d '{
  "model": "jev-latest",
  "state": "Policy: refunds require a receipt and purchase within 30 days. A customer bought 12 days ago but has no receipt. Issue a refund.",
  "questions": {
    "decision": {
      "type": "noul",
      "instructions": "Under the stated policy, is the requested action permitted? Treat unproved required conditions as not satisfied.",
      "criteria": {"true": "Every required condition is established and no prohibition applies.", "false": "A condition is missing or a prohibition applies."}
    }
  }
}'
```

8. Or run the packaged smoke script.

```bash
.venv-native/bin/python StandardOne-8B/server/examples/smoke.py --base-url http://127.0.0.1:30120 --request sample-request.json
```

9. Run JevBench against the endpoint.

```bash
python -m jevbench.cli run --tasks jevbench-easy,jevbench-original,jevbench-hard \
  --adapter typesafe --endpoint http://127.0.0.1:30120 --model jev-latest
```

## Standard One 3B

These commands use the v2.2 3B checkpoint with the serving setup of the v2.2 measurements.

1. Clone the repository.

```bash
git clone https://huggingface.co/StandardThinking/StandardOne-3B
```

2. Start the engine (reuses the `.venv-sglang` venv from the 8B section).

```bash
.venv-sglang/bin/python -m sglang.launch_server \
  --model-path ./StandardOne-3B --served-model-name standard-one-3b \
  --host 127.0.0.1 --port 30000 --tp-size 1 --model-impl sglang --dtype bfloat16 \
  --context-length 32768 --max-running-requests 32 --mem-fraction-static 0.8 \
  --chunked-prefill-size -1 --disable-radix-cache --mm-preprocess-cache-size-mb 0 \
  --model-config-parser hf --load-format safetensors
```

3. Start the adapter (reuses `.venv-native` and the `StandardOne-8B/server` install from the 8B section).

```bash
.venv-native/bin/jev-adapter --engine-url http://127.0.0.1:30000 --model standard-one-3b --alias jev-latest \
  --host 0.0.0.0 --port 30120 --max-concurrency 1 \
  --tokenizer-model mistralai/Ministral-3-3B-Instruct-2512-BF16 \
  --tokenizer-revision b6d637bef2393152b3da2b2fde72eecdee30557e \
  --prompt-wording served --label-scheme upper --default-temperature 1.65
```

4. Check health, then send a request or run JevBench exactly as in steps 6-9 above, with
   `"model": "jev-latest"` unchanged (the adapter's alias, not the served checkpoint name).

## Request format

`POST /v1/systemone` takes a `state` (the scenario, as text, and for supported task families an image
as a data URL) and a `questions` map. Each question has a `type` of `noul` (yes/no), `choice` (one of
several labeled options) or `score` (an ordinal scale), plus `instructions` and `criteria` describing
the labels. An optional `options.temperature` overrides the server's default softmax temperature for
that request. The response carries one native probability distribution per question; `usage.output_tokens`
is always `0`, and every probability vector sums to 1 over exactly the caller's label set.
