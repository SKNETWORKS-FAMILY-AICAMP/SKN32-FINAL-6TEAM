---
license: apache-2.0
base_model: Qwen/Qwen3.5-4B
pipeline_tag: text-classification
tags:
- decision-model
- system-one
- jev
- agent-guardrails
- tool-call-safety
- classification
---

# spark-s1-4b-v6

Part of [Open Spark Jev](https://github.com/abhishek085/open-spark-jev), an independent, open-source implementation inspired by TypeSafe's Jev
and System One, built for local inference on NVIDIA DGX Spark. It is not Jev and not affiliated with TypeSafe AI.

`spark-s1` is a System-1 decision model: given a state (text or JSON) and a typed question with options defined at request time, it returns a
probability for every option and a confidence from one forward pass, without generating text. The answer is the softmax of the first-token
logits restricted to the option letters, divided by a fitted temperature — no extra head.

This is a very early release; expect it to change quickly.

## What's new in v6

v6 keeps v5's data, scope and LoRA recipe unchanged and swaps the backbone: **Qwen3-4B -> Qwen3.5-4B**, a hybrid architecture (24
Gated-DeltaNet-style linear-attention layers + 8 full-attention layers, of 32 total) rather than a uniform transformer. It's the largest jump of
any release so far — own-split accuracy +6.2 points over v5-4b, JevBench public-tier Intelligence 74.2 -> 83.1 — but not a clean win everywhere:
two of five external Jev-style sets regressed slightly. See Limitations.

## How it reads an answer

1. The state is rendered once and passed through the model; its cache is retained.
2. A question is turned into a lettered menu (`A. billing`, `B. technical`, ...).
3. The next-token logits are restricted to the option letters and converted to a probability distribution.
4. A temperature fitted on a held-out calibration split scales the result.

```python
from open_spark_jev.model import MenuScorer
from open_spark_jev.schema import Choice, State

model = MenuScorer("abhishek085/spark-s1-4b-v6")
state = State(content={"tool": "bash", "command": "kubectl get pods -n production"})
answer = model.decide(state, [Choice(prompt="Approve this tool call?", options=["allow", "ask", "deny"])])
```

## Results

| Measure | v6-4b | v5-4b (prior release) |
|---|---:|---:|
| Own locked test / challenge accuracy | **0.929 / 0.911** | 0.867 / 0.861 |
| 60-case tool-call diagnostic set | 0.900 | 0.917 |
| Prompt injection, with / without deployment context | **0.924** / 0.867 | 0.894 / 0.903 |
| Jev-directory (70 questions) | **0.871** | 0.800 |
| Kev decision-v1 (external classification) | **0.800** | 0.755 |
| Kev transfer-v4 (dev / locked test, 764 each) | 0.756 / 0.787 | not evaluated |
| JevBench public tiers (easy / standard / hard) | **1.000 / 1.000 / 0.595** | 1.000 / 0.847 / 0.523 |
| JevBench public-proxy Intelligence score | **83.1** | 74.2 |

[JevBench](https://github.com/fstandhartinger/jevbench) v1.2, public items only (231 of 534, judge tier entirely private). Public-proxy
Intelligence is our own metric from JevBench's own `composite_v12.intelligence()`, not the official JevBench Score.

## Latency

Batch size 1, one NVIDIA DGX Spark (GB10), **served via vLLM** (the recommended path for this backbone — see Limitations for why HF Transformers
in-process serving is currently much slower).

| Backend | p50 | decisions/s |
|---|---:|---:|
| vLLM, bf16 | 74.9 ms | 13.3 |
| vLLM, NVFP4 (MLP-only) — [abhishek085/spark-s1-4b-v6-nvfp4](https://huggingface.co/abhishek085/spark-s1-4b-v6-nvfp4) | 53.3 ms | 18.6 |

NVFP4 is 1.40x faster with **no measurable accuracy cost** (JevBench Intelligence 83.1 -> 83.2). Smaller speedup than v5-4b's 1.66x since only
the MLP is quantized and this hybrid backbone carries relatively more compute in its unquantized attention paths — but v6-4b-nvfp4 (53.3ms) is
still faster than v5-4b bf16 (61.6ms) while being far more accurate.

## Limitations

* **Jev-style decisions only.** Not trained or evaluated on general text classification or vulnerable-code detection; treat those as
  unsupported.
* **HF Transformers in-process serving/training is slow on this backbone.** `causal_conv1d` and `flash-linear-attention` aren't installed in the
  environment this was trained in, so the linear-attention layers fall back to reference PyTorch kernels. **vLLM is unaffected** — it has its own
  fast native kernels for this architecture (`model_type=qwen3_5_text`) and is the recommended serving path.
* **The state-cache optimization (encode once, answer several questions cheaply) doesn't apply to this backbone yet** — falls back to a full
  forward pass per question; results are correct, just without the multi-question speedup.
* **Backbone swap is not a clean win**: `ext-injection-noctx` -3.6 points and `ext-toolcall-risk` -1.7 points versus v5-4b, even as own-splits
  and JevBench improved substantially.
* RLCD (outcome-based calibration) made results worse in two prior attempts (on earlier releases) and was not retried here.
* Sensitive to how options are defined and to option order; recalibrate on your own labelled outcomes before relying on thresholds.
* English only.

## Reproducibility

Training: `scripts/run_v6_4b.sh` (`configs/train/sft_v6.yaml`) in the [repository](https://github.com/abhishek085/open-spark-jev). Evaluation:
`python -m open_spark_jev.eval.osdg`, `python -m open_spark_jev.eval.external`, JevBench `scripts/run_jevbench.sh`. Data: assembled by
`scripts/build_v5_data.py` from `os-datagen` runs (unchanged from v5) — not yet packaged as its own versioned dataset.

## Safety

Do not use a model decision as the only authorization control. Deploy with deterministic policy guardrails, a conservative auto-allow threshold,
logging, least-privilege credentials and human approval for sensitive actions. See
[SECURITY.md](https://github.com/abhishek085/open-spark-jev/blob/main/SECURITY.md).

## License

Apache-2.0. Backbone `Qwen/Qwen3.5-4B` (Apache-2.0). This is a LoRA-merged derivative.
