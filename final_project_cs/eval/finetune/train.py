"""QLoRA SFT for DoD-28 (1차 공개데이터 -> 2차 알파데이터, sequential).

Usage (on the GPU box):
    python train.py --stage 1 --data sft_stage1.jsonl --base Qwen/Qwen2.5-3B-Instruct --out ckpt_stage1
    python train.py --stage 2 --data sft_stage2.jsonl --base ckpt_stage1 --out ckpt_stage2

12GB VRAM budget. 3B model in plain bf16 fits without 4-bit quantization,
which matters here: on this box, transformers' CUDA-targeted safe_open()
(triggered by device_map="auto" and/or quantization_config) hits a Windows
pagefile OSError regardless of free RAM. The workaround confirmed by
diag_3b.py is to load in bf16 on CPU with no device_map and no
quantization_config, then move the whole model to cuda via .to() -- that
codepath never calls the CUDA-targeted safe_open().
"""
from __future__ import annotations

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import argparse
import json
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, PeftModel
from transformers import Qwen2ForCausalLM
from trl import SFTConfig, SFTTrainer
from huggingface_hub import snapshot_download

from load_tok import load_tokenizer


def resolve_local(model_id: str) -> str:
    """Pre-download so from_pretrained never has to resolve remote shard
    lists itself (works around a checkpoint-resolution bug in this
    transformers build)."""
    if Path(model_id).is_dir():
        return model_id
    return snapshot_download(model_id)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=int, required=True, choices=[1, 2, 3])
    p.add_argument("--data", required=True)
    p.add_argument("--base", required=True, help="HF model id, or a stage-1 checkpoint dir for stage 2")
    p.add_argument("--out", required=True)
    p.add_argument("--epochs", type=float, default=None)
    p.add_argument("--resume", default=None, help="checkpoint dir to resume trainer state from")
    p.add_argument("--max_length", type=int, default=512,
                    help="stage1/2's short classification examples fit 512; stage3's full "
                         "ContextPack review-task examples ran 6k-11k tokens (2026-08-31 finding "
                         "-- default 512 silently truncated away the instructions and/or target, "
                         "producing an unusably-trained adapter). Pass a value covering your data's "
                         "actual token length (see eval/finetune/check_lens.py).")
    args = p.parse_args()

    base_model_id = "Qwen/Qwen2.5-3B-Instruct"
    tokenizer = load_tokenizer(base_model_id)
    local_base = resolve_local(base_model_id)

    model = Qwen2ForCausalLM.from_pretrained(
        local_base, dtype=torch.bfloat16, local_files_only=True,
    )
    model = model.to("cuda")

    if args.stage >= 2:
        # continue from the stage-1 LoRA adapter
        model = PeftModel.from_pretrained(model, args.base, is_trainable=True)
        peft_config = None
    else:
        peft_config = LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        )

    dataset = load_dataset("json", data_files=args.data, split="train")

    def formatting(example):
        return tokenizer.apply_chat_template(example["messages"], tokenize=False, add_generation_prompt=False)

    epochs = args.epochs or (2.0 if args.stage == 1 else 4.0)
    sft_config = SFTConfig(
        output_dir=args.out, num_train_epochs=epochs, per_device_train_batch_size=1,
        gradient_accumulation_steps=8, learning_rate=2e-4 if args.stage == 1 else 1e-4,
        logging_steps=10, save_strategy="steps", save_steps=40, save_total_limit=5,
        bf16=True, max_length=args.max_length,
        report_to=[], packing=False,
        gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False},
    )

    trainer = SFTTrainer(
        model=model, args=sft_config, train_dataset=dataset,
        peft_config=peft_config, formatting_func=formatting,
    )
    trainer.train(resume_from_checkpoint=args.resume)
    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    print(json.dumps({"stage": args.stage, "output_dir": args.out, "rows": len(dataset)}))


if __name__ == "__main__":
    main()
