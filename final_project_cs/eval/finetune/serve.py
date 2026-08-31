"""Minimal resident inference server for the fine-tuned model on x600.

Loads the model ONCE at process start (unlike predict.py, which reloads
per-invocation) and serves POST /complete -- the wire contract
app/infrastructure/llm/local_ft.py::LocalFTTeamLLM expects: send
{"prompt": "<the exact JSON string OpenAITeamLLM would send>"}, get back
{"text": "<raw model completion, expected to be a JSON object as text>",
 "input_tokens": int, "output_tokens": int}.

Same load pattern as diag_3b.py: plain bf16, no device_map, no
quantization, CPU load then .to("cuda") -- the only path that avoids the
Windows pagefile OSError documented in
docs/reports/2026-08-30_S-DOD28-FINETUNE-PIPELINE_리포트.md.

Usage:
    uvicorn serve:app --host 127.0.0.1 --port 8100
"""
from __future__ import annotations

import argparse
import os
import sys

import torch
from fastapi import FastAPI
from peft import PeftModel
from pydantic import BaseModel
from transformers import Qwen2ForCausalLM
from huggingface_hub import snapshot_download
from pathlib import Path

from load_tok import load_tokenizer

BASE_MODEL_ID = os.environ.get("FT_BASE_MODEL", "Qwen/Qwen2.5-3B-Instruct")
ADAPTER_DIR = os.environ.get("FT_ADAPTER_DIR", "ckpt_stage3")

app = FastAPI()
_state: dict = {}


def _resolve_local(model_id: str) -> str:
    if Path(model_id).is_dir():
        return model_id
    return snapshot_download(model_id)


def _load() -> None:
    print(f"loading tokenizer for {BASE_MODEL_ID}...", flush=True)
    tokenizer = load_tokenizer(BASE_MODEL_ID)
    local_base = _resolve_local(BASE_MODEL_ID)
    print("loading base model (bf16, cpu-first)...", flush=True)
    model = Qwen2ForCausalLM.from_pretrained(local_base, dtype=torch.bfloat16, local_files_only=True)
    model = model.to("cuda")
    print(f"attaching adapter from {ADAPTER_DIR}...", flush=True)
    model = PeftModel.from_pretrained(model, ADAPTER_DIR)
    model.eval()
    _state["tokenizer"] = tokenizer
    _state["model"] = model
    print("model ready.", flush=True)


class CompleteRequest(BaseModel):
    prompt: str


@app.on_event("startup")
def startup() -> None:
    _load()


@app.get("/health")
def health() -> dict:
    return {"status": "ok" if "model" in _state else "loading"}


@app.post("/complete")
def complete(req: CompleteRequest) -> dict:
    tokenizer = _state["tokenizer"]
    model = _state["model"]
    torch.cuda.empty_cache()
    messages = [{"role": "user", "content": req.prompt}]
    prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    # ★2026-08-31 bug: 3000 silently truncated real ContextPack prompts from
    #   the RIGHT, cutting off "instructions" (which sits at the end of the
    #   JSON blob) -- the model then had no task instruction to follow and
    #   just continued the truncated evidence text. Raised well above any
    #   observed real prompt length (16.6k chars ~= a few thousand tokens);
    #   single-request inference has no OOM pressure the way batched
    #   training does, so this is safe.
    inputs = tokenizer(prompt_text, return_tensors="pt", truncation=True, max_length=8192).to(model.device)
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=400, do_sample=False)
    text = tokenizer.decode(generated[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return {
        "text": text,
        "input_tokens": int(inputs["input_ids"].shape[1]),
        "output_tokens": int(generated.shape[1] - inputs["input_ids"].shape[1]),
    }


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
