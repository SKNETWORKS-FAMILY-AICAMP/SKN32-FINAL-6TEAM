---
language:
- en
- zh
license: apache-2.0
library_name: transformers
tags:
- valen
- qwen3_5
- decision-making
- image-text-to-text
- video
- shared-state
- full-finetuning
base_model: Qwen/Qwen3.5-0.8B
---
# Valen-0.8B

Qwen3.5 with a two-layer MLP-Mixer decision head. Supports text, images and videos, and returns Choice, Noul and Score decisions. Multiple questions can share one state encoding with `execution="shared_state"`. Trained on millions of samples.
## Inference

Install Python 3.10+, PyTorch, Transformers 5.4.0, torchvision, Pillow and av. Flash Attention 2 is optional with a compatible CUDA build. The model contains its tokenizer, processor and custom inference code; a separate base-model download is unnecessary.

```python
import torch
from transformers import AutoModel

model = AutoModel.from_pretrained(
    "Valen-Team/Valen-0.8B", trust_remote_code=True,
    dtype="auto", attn_implementation="sdpa",
).to("cuda").eval()
torch.set_float32_matmul_precision("highest")
torch.backends.cudnn.allow_tf32 = False
print(model.predict({
    "state": "A cat is on the sofa.",
    "questions": {
        "animal": {"type": "choice", "instructions": "Which animal is present?",
                   "criteria": {"cat": "A cat", "dog": "A dog"}},
        "on_sofa": {"type": "noul", "instructions": "The cat is on the sofa."},
    },
}, execution="shared_state"))
```

Use `attn_implementation="flash_attention_2"` for Flash Attention, or `execution="question"` for independent questions. Video defaults to 16 frames. Image/video request examples and training instructions are in the [Valen repository](https://github.com/Liuziyu77/Valen).

`dtype="auto"` preserves the trained FP32 parameters. The backbone runs under BF16 autocast and the Mixer stays FP32, matching native checkpoint evaluation. Loading all weights as BF16 rounds the trained parameters and can change outputs.

## Evaluation

Final native checkpoint, shared-state inference, the same fixed evaluation sets used for the earlier release:

| Benchmark | Accuracy (%) |
| --- | ---: |
| VisualDecisionBench Image | 75.94 |
| VisualDecisionBench Video | 79.03 |
| JevBench | 77.92 |

