---
base_model: mistralai/Ministral-3-3B-Instruct-2512-BF16
library_name: transformers
license: apache-2.0
pipeline_tag: text-generation
language:
  - en
  - ja
  - zh
  - es
  - fr
  - de
  - pt
  - ru
  - ko
tags:
  - mistral3
  - decision-model
  - typed-decisions
  - jev
  - jevbench
  - calibration
  - decode-free
  - multilingual
  - vision-language
---

# Standard One 3B

> **Updated weights (v2.2, 2026-10-04).** If you downloaded this model before, download it again.
> Earlier releases remain available under the `v1`, `v1.1`, `v2` and `v2.1` tags.

**Version:** v2.2

Standard One scores a bounded set of answers for a supplied scenario and returns probabilities through `POST /v1/systemone`. It does not generate free-form response text. This repository contains the merged BF16 3B checkpoint. The server code is in [StandardOne-8B](https://huggingface.co/StandardThinking/StandardOne-8B).

Image input is supported; the results below measure text decisions.

## At a glance

- `choice` selects among labeled options, `noul` is yes/no and `score` uses an ordinal scale.
- The training mixture covers English, Japanese, Chinese, Spanish, French, German, Portuguese, Russian and a smaller Korean share. Performance varies by language.
- Probabilities are fitted by answer type; the measured endpoint configuration and calibration results are below.
- The base, adapter, merged weights and shared server code are Apache-2.0.

## Repositories

- [Merged BF16 checkpoint](https://huggingface.co/StandardThinking/StandardOne-3B)
- [LoRA adapter and merge recipe](https://huggingface.co/StandardThinking/StandardOne-3B-LoRA)
- [GGUF quantizations](https://huggingface.co/StandardThinking/StandardOne-3B-GGUF)
- [Shared server code](https://huggingface.co/StandardThinking/StandardOne-8B/tree/main/server)

## Quick start

Use this merged checkpoint. Follow the [server setup](https://huggingface.co/StandardThinking/StandardOne-8B/blob/main/QUICKSTART.md) on a CUDA-capable Linux host to install SGLang 0.5.20 and the adapter in separate virtual environments. Start the engine and the adapter in separate terminals. Use the 3B commands below; the linked guide also covers another model size.

Engine:

```bash
CUDA_VISIBLE_DEVICES=0 SGLANG_VLM_CACHE_SIZE_MB=0 .venv-sglang/bin/python -m sglang.launch_server \
  --model-path ./StandardOne-3B --served-model-name standard-one-3b \
  --host 127.0.0.1 --port 30000 --tp-size 1 --model-impl sglang --dtype bfloat16 \
  --context-length 32768 --max-running-requests 32 --mem-fraction-static 0.8 \
  --chunked-prefill-size -1 --disable-radix-cache --mm-preprocess-cache-size-mb 0 \
  --model-config-parser hf --load-format safetensors
```

Adapter:

```bash
.venv-native/bin/jev-adapter --engine-url http://127.0.0.1:30000 --model standard-one-3b --alias jev-latest \
  --host 0.0.0.0 --port 30120 --max-concurrency 1 \
  --tokenizer-model mistralai/Ministral-3-3B-Instruct-2512-BF16 \
  --tokenizer-revision b6d637bef2393152b3da2b2fde72eecdee30557e \
  --prompt-wording served --label-scheme upper --default-temperature 1.65
```

The endpoint accepts `choice` (labeled options), `noul` (yes/no) and `score` (ordinal) questions. It returns probabilities for the caller's labels in one forward pass without decoding answer text. For example:

```bash
curl -s http://127.0.0.1:30120/v1/systemone -X POST -H 'content-type: application/json' -d '{
  "model": "jev-latest",
  "state": "Refunds require a receipt. The customer has no receipt.",
  "questions": {"decision": {"type": "noul",
    "instructions": "Is a refund allowed under the rule?",
    "criteria": {"true": "The requirement is met.",
                 "false": "A requirement is missing."}}}
}'
```

`usage.output_tokens` is 0. The server applies the default temperature shown above unless a request supplies `options.temperature`. Each probability vector is normalized over exactly the caller's labels.

## Prompt wording and temperatures

`served` is the adapter's default wording and the one used for the v2.2 measurements (`--label-scheme upper`, `--default-temperature 1.65`); `native` accepts at most 26 options per question. The table below is a v2.1 measurement of both wordings through the same served endpoint. Temperatures were fitted separately for each wording and answer type on three calibration suites only and have not been refit for v2.2. No JevBench item was used for these decisions.

| Wording | Default temperature | Choice | Yes/no | Ordinal | Mean accuracy, 10 suites |
|---|---:|---:|---:|---:|---:|
| `native` | 0.90 | 0.90 | 1.15 | 1.20 | 69.91 % |
| `served` (adapter default) | 1.00 | 1.00 | 0.90 | 0.80 | 70.21 % |

To use `native` with its v2.1-fitted temperatures, pass `--prompt-wording native --native-system-prompt none --default-temperature 0.90 --temperature-by-type choice=0.90,noul=1.15,score=1.20`.

## Changes in v2.2

v2.2 continues training from v2.1 with additional decision data. Questions with more than 26 options now use the labels `A`–`Z`, then `AA`, `AB`, …; the adapter in `server/` uses this order by default (`--label-scheme upper`). Both versions were measured the same way: merged BF16 weights through SGLang 0.5.20 and `jev-adapter`, `served` wording, one option order, accuracy of the most probable answer; measured 3 October 2026.

| Suite | v2.1 | **v2.2** | Change (points) |
|---|---:|---:|---:|
| many-option questions, 53–151 options (18,000) | 48.00 % | **79.97 %** | +31.97 |
| the same question set, at most 26 options (750) | 79.07 % | **85.47 %** | +6.40 |
| long-document questions (150) | 32.67 % | **38.00 %** | +5.33 |
| held-out decision set (600) | 73.50 % | **82.00 %** | +8.50 |
| hard proxy (600) | 44.83 % | **44.67 %** | −0.16 |
| realistic transfer set (600) | 89.50 % | **88.17 %** | −1.33 |
| JevBench public easy (48) | 97.92 % | **100.00 %** | +2.08 |
| JevBench public standard (72) | 93.06 % | **93.06 %** | 0.00 |
| JevBench public hard (111) | 46.85 % | **45.95 %** | −0.90 |

Decision Index 0.2.1 (balanced skill): **34.85**, measured through the adapter in `server/` (`served` wording, default temperature 1.65). The tables below are the v2.1 measurements with `native` wording and are not directly comparable with the table above.

## Benchmarks

### Served endpoint, v2.1

Merged BF16 weights through SGLang 0.5.20 and `jev-adapter`, one option order, `native` wording, no system prompt. Accuracy is independent of the fitted temperature.

| Suite | Questions | Accuracy |
|---|---:|---:|
| Judge proxy | 600 | 87.50 % |
| Hard proxy | 600 | 44.17 % |
| Stated-distribution probability | 1,036 | 78.38 % |
| Realistic transfer | 600 | 90.17 % |
| MuSiQue multiple choice | 500 | 69.80 % |
| SQuAD 2.0 unanswerable | 500 | 79.80 % |
| ContractNLI | 500 | 62.20 % |
| PAWS-X English | 500 | 74.40 % |
| Hard decisions | 800 | 51.50 % |
| Consistency | 1,200 | 61.17 % |

The following public tiers are reported separately and were excluded from wording, temperature, checkpoint and quantization decisions. These are our measurements, not official sealed-set scores.

| Suite | Questions | Accuracy |
|---|---:|---:|
| JevBench public easy | 48 | 100.00 % |
| JevBench public standard | 72 | 86.11 % |
| JevBench public hard | 111 | 47.75 % |

At the fitted temperatures, public-hard 10-bin ECE is 0.212 and mean total-variation distance on the stated-distribution validation set is 0.124.

### Offline six-suite result, v2.1

This separate `transformers` run used native wording, no system prompt and T=1. It is not the served endpoint result. The three public JevBench tiers below are report-only and were excluded from wording, temperature, checkpoint and quantization decisions.

| Suite | Questions | Accuracy |
|---|---:|---:|
| JevBench public easy | 48 | 100.00 % |
| JevBench public standard | 72 | 93.06 % |
| JevBench public hard | 111 | 47.75 % |
| Judge proxy | 600 | 88.00 % |
| Realistic transfer | 600 | 89.33 % |
| Stated-distribution probability | 1,036 | 77.99 % |

### Public classification and decision suites, v2.1

Served endpoint, 400 cases per suite, seed 13: AG News 84.5 %, typed decisions 67.3 %, nine-language MASSIVE intent mean 83.4 %, email spam 92.0 %, phishing 88.8 %. Results vary by language and task.

The full report in [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md) and the classification tables in [`docs/public-classification-suites.md`](docs/public-classification-suites.md) are historical; for this checkpoint, see [Changes in v2.2](#changes-in-v22). The [historical v2 benchmark chart](docs/assets/00-benchmark-card.png) shows earlier-version measurements.

## Model details

- **Base model:** `mistralai/Ministral-3-3B-Instruct-2512-BF16`, revision `b6d637bef2393152b3da2b2fde72eecdee30557e` (Apache-2.0).
- **Adapter architecture:** LoRA r=16, α=32, dropout 0 on `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj` and `down_proj` of the language model.
- **Adapter file:** `adapter_model.safetensors`, `135,113,048` bytes, SHA-256 `cfe06432d85efbe99df53dbfd3fa3881e5d6ef177c6e26d5800d8bf83afe79e4`.
- **Merge:** 182 language-model tensors changed, none outside the language-model projections; maximum absolute weight change 0.0022.
- **Serving:** `served` wording (the adapter default), no system prompt, labels `A`–`Z`, then `AA`, `AB`, … (`--label-scheme upper`), `--default-temperature 1.65` for every answer type (the setting of the v2.2 measurements; no temperature was refit for v2.2), SGLang 0.5.20 and `jev-adapter`; 32,768-token context, one caller-supplied option order and no rotation ensemble.

## Training data

The public source inventory shared with Standard One 8B is listed below. Training data is synthetic and format-augmented decision data plus decision items converted from public
datasets (listed below); the JevBench public tiers used only for evaluation carry MIT. The linked full report is historical.

Public datasets used (train splits where the dataset has one; licence as stated by each dataset; labels come from the
datasets, distractor options are generated by code):

| Dataset | Licence |
|---|---|
| SQuAD 2.0 | CC BY-SA 4.0 |
| ARC | CC BY-SA 4.0 |
| BoolQ | CC BY-SA 3.0 |
| CommonsenseQA | MIT |
| HellaSwag | MIT |
| Banking77 | CC BY 4.0 |
| Bias in Bios | MIT |
| Bitext customer support | CDLA-Sharing-1.0 |
| CLINC150 | CC BY 3.0 |
| Amazon Counterfactual | CC BY 4.0 |
| DBpedia-14 | CC BY-SA 3.0 |
| Dolly 15k | CC BY-SA 3.0 |
| GoEmotions | Apache-2.0 |
| MASSIVE | CC BY 4.0 |
| Twitter Financial News Sentiment | MIT |
| HelpSteer3 | CC BY 4.0 |
| HelpSteer2 | CC BY 4.0 |
| 2WikiMultihopQA | Apache-2.0 |
| HotpotQA | CC BY-SA 4.0 |
| MuSiQue | CC BY 4.0 |
| QASC | CC BY 4.0 |
| DROP | CC BY-SA 4.0 |
| GSM8K | MIT |
| TempReason | CC BY-SA 3.0 |
| MultiNLI | OANC / CC BY-SA 3.0 / CC BY 3.0 |
| PAWS | Google terms, free for any purpose |
| PAWS-X | Google terms, free for any purpose |
| SNLI | CC BY-SA 4.0 |
| WANLI | CC BY 4.0 |
| ContractNLI | CC BY 4.0 |
| CUAD | CC BY 4.0 |
| ShARC | CC BY-SA 3.0 |
| Jailbreak classification | Apache-2.0 |
| Prompt injections | Apache-2.0 |
| Aegis AI Content Safety 2.0 | CC BY 4.0 |
| Jigsaw Toxic Comment Classification (mirror of the Kaggle data) | CC0 (data); comment text CC BY-SA 3.0 (Wikipedia) |
| Measuring Hate Speech | CC BY 4.0 |
| Image safety classes | MIT |
| WinoGrande | CC BY |
| Lichess puzzles and games | CC0 |
| ClinicalTrials.gov records | Public domain (U.S. Government work) |

Historical upstream-id mapping: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md#training-data-provenance).

## Limitations

- Results depend on the task distribution and the serving path. Refit temperatures when using a materially different distribution.
- With `native` wording, at most 26 options per question (one uppercase letter per option, `A`–`Z`). With `served` wording the adapter continues with `AA`, `AB`, … up to 255 single-token labels (`--label-scheme upper`); v2.2 was evaluated with up to 151 options.
- Served and offline probabilities can differ on identical prompts. Use the served results to estimate endpoint behavior.
- Korean is a small share of the multilingual training mixture.
- The card reports text benchmarks; it does not establish accuracy on image inputs.
- The sealed JevBench set has not been measured for this version.

## Licence

Adapter weights, merged weights and this card: Apache-2.0. Base model `mistralai/Ministral-3-3B-Instruct-2512` (and `-BF16`): Apache-2.0 per its Hugging Face model card, which adds that the model must not be used in a way that infringes, misappropriates, or otherwise violates any third party's rights. `jev-adapter` and SGLang: Apache-2.0. The JevBench harness and public tiers used for evaluation: MIT; other benchmark items keep their own upstream terms.

## Citation

`StandardThinking/StandardOne-3B` (merged weights) · `StandardThinking/StandardOne-3B-LoRA` (adapter + merge recipe).
