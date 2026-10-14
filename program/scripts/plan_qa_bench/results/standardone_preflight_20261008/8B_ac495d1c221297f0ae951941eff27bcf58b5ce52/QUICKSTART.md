# Quickstart

Run these commands from one working directory on a CUDA-capable Linux host with Git, Git LFS, `uv`,
and an NVIDIA GPU. Keep the engine and adapter running in separate terminals. The 8B and 3B
examples use the same ports, so stop one pair before starting the other. The model card's
latency figures were measured on one H200; other GPUs may need different memory settings.

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
uv pip install --python .venv-native/bin/python -e './StandardOne-8B/server[native-tokenizer]'
```

5. Start the adapter.

```bash
.venv-native/bin/jev-adapter --engine-url http://127.0.0.1:30000 --model standard-one-8b --alias jev-latest \
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

8. Or run the packaged smoke script with its bundled request.

```bash
.venv-native/bin/python StandardOne-8B/server/examples/smoke.py --base-url http://127.0.0.1:30120
```

## Standard One 3B

1. Clone the 3B checkpoint and the 8B repository, which contains the shared `server/` code.
   Skip the second clone if you already completed the 8B steps above.

```bash
git clone https://huggingface.co/StandardThinking/StandardOne-3B
git clone https://huggingface.co/StandardThinking/StandardOne-8B
```

2. Create the engine and adapter venvs. Skip this step if you already completed the 8B setup.

```bash
uv venv --python 3.12 .venv-sglang
uv pip install --python .venv-sglang/bin/python 'sglang==0.5.20'
uv venv --python 3.12 .venv-native
uv pip install --python .venv-native/bin/python -e './StandardOne-8B/server[native-tokenizer]'
```

3. Start the engine.

```bash
CUDA_VISIBLE_DEVICES=0 SGLANG_VLM_CACHE_SIZE_MB=0 .venv-sglang/bin/python -m sglang.launch_server \
  --model-path ./StandardOne-3B --served-model-name standard-one-3b \
  --host 127.0.0.1 --port 30000 --tp-size 1 --model-impl sglang --dtype bfloat16 \
  --context-length 32768 --max-running-requests 32 --mem-fraction-static 0.8 \
  --chunked-prefill-size -1 --disable-radix-cache --mm-preprocess-cache-size-mb 0 \
  --model-config-parser hf --load-format safetensors
```

4. Start the adapter.

```bash
.venv-native/bin/jev-adapter --engine-url http://127.0.0.1:30000 --model standard-one-3b --alias jev-latest \
  --host 0.0.0.0 --port 30120 --max-concurrency 1 \
  --tokenizer-model mistralai/Ministral-3-3B-Instruct-2512-BF16 \
  --tokenizer-revision b6d637bef2393152b3da2b2fde72eecdee30557e \
  --prompt-wording served --label-scheme upper --default-temperature 1.65
```

5. Check health, then send a request or run the smoke script as in 8B steps 6-8, with
   `"model": "jev-latest"` unchanged (the adapter's alias, not the served checkpoint name).

## Run JevBench against either endpoint

From the same working directory, clone the [official JevBench harness](https://github.com/fstandhartinger/jevbench)
and run its public JSONL files. This uses the local adapter at port 30120 and saves run artifacts
outside the JevBench repository. Choose a new `jevbench-run` directory for each run.

```bash
git clone https://github.com/fstandhartinger/jevbench.git
uv pip install --python .venv-native/bin/python -e ./jevbench
.venv-native/bin/python -m jevbench.cli run \
  --tasks jevbench/datasets/public/easy.jsonl,jevbench/datasets/public/original.jsonl,jevbench/datasets/public/hard.jsonl \
  --adapter typesafe --endpoint http://127.0.0.1:30120 --model jev-latest --key-env '' \
  --cost-basis self_hosted_compute_excluded --reserve-usd 0 \
  --results jevbench-run/results.jsonl --raw-dir jevbench-run/raw \
  --ledger jevbench-run/ledger.jsonl --manifest jevbench-run/manifest.json
```

## Request format

`POST /v1/systemone` takes a `state` (the scenario, as text, and for supported task families an image
as a data URL) and a `questions` map. Each question has a `type` of `noul` (yes/no), `choice` (one of
several labeled options) or `score` (an ordinal scale), plus `instructions` and `criteria` describing
the labels. An optional `options.temperature` overrides the server's default softmax temperature for
that request. The response carries one native probability distribution per question; `usage.output_tokens`
is always `0`, and every probability vector sums to 1 over exactly the caller's label set.
