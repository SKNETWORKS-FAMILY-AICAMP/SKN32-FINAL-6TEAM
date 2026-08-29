import torch
from transformers import BitsAndBytesConfig
from load_tok import load_tokenizer
from huggingface_hub import snapshot_download

print("torch", torch.__version__, "cuda", torch.cuda.is_available())
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
)
print("loading tokenizer...")
tok = load_tokenizer("Qwen/Qwen2.5-7B-Instruct")
print("tokenizer ok")

print("snapshot_download full model to local dir...")
local_dir = snapshot_download("Qwen/Qwen2.5-7B-Instruct")
print("snapshot_download done:", local_dir)

import os
print("files:", os.listdir(local_dir))

from transformers import Qwen2ForCausalLM
model = Qwen2ForCausalLM.from_pretrained(
    local_dir, quantization_config=bnb_config, device_map="auto",
    dtype=torch.bfloat16, local_files_only=True,
)
print("model loaded ok")
print(model.get_memory_footprint() / 1e9, "GB")

msgs = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "안녕하세요"}]
prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
inputs = tok(prompt, return_tensors="pt").to(model.device)
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=30)
print("generation ok:", tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
