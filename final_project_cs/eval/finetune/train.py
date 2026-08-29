"""QLoRA SFT for DoD-28 (1차 공개데이터 -> 2차 알파데이터, sequential).

Usage (on the GPU box):
    python train.py --stage 1 --data sft_stage1.jsonl --base Qwen/Qwen2.5-7B-Instruct --out ckpt_stage1
    python train.py --stage 2 --data sft_stage2.jsonl --base ckpt_stage1 --out ckpt_stage2

12GB VRAM budget -> 4-bit QLoRA, small batch, gradient accumulation.
"""
from __future__ import annotations

import argparse
import json

import torch
from datasets import load_dataset
from peft import LoraConfig, PeftModel
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

from load_tok import load_tokenizer


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=int, required=True, choices=[1, 2])
    p.add_argument("--data", required=True)
    p.add_argument("--base", required=True, help="HF model id, or a stage-1 checkpoint dir for stage 2")
    p.add_argument("--out", required=True)
    p.add_argument("--epochs", type=float, default=None)
    args = p.parse_args()

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )

    base_model_id = "Qwen/Qwen2.5-7B-Instruct"
    tokenizer = load_tokenizer(base_model_id)

    model = AutoModelForCausalLM.from_pretrained(
        base_model_id, quantization_config=bnb_config, device_map="auto",
        torch_dtype=torch.bfloat16,
    )

    if args.stage == 2:
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
        logging_steps=10, save_strategy="epoch", bf16=True, max_length=768,
        report_to=[], packing=False,
    )

    trainer = SFTTrainer(
        model=model, args=sft_config, train_dataset=dataset,
        peft_config=peft_config, formatting_func=formatting,
    )
    trainer.train()
    trainer.save_model(args.out)
    tokenizer.save_pretrained(args.out)
    print(json.dumps({"stage": args.stage, "output_dir": args.out, "rows": len(dataset)}))


if __name__ == "__main__":
    main()
