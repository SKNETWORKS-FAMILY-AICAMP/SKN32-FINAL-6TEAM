import torch
from transformers import Qwen2ForCausalLM, BitsAndBytesConfig
from load_tok import load_tokenizer

def flush(msg):
    print(msg, flush=True)

flush("torch " + torch.__version__ + " cuda " + str(torch.cuda.is_available()))
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
)
flush("loading tokenizer...")
tok = load_tokenizer("Qwen/Qwen2.5-3B-Instruct")
flush("tokenizer ok")
from huggingface_hub import snapshot_download
flush("snapshot_download...")
local_dir = snapshot_download("Qwen/Qwen2.5-3B-Instruct")
flush("downloaded to " + local_dir)
flush("loading 3B model in bf16 on CPU first (no device_map, no quant)...")
model = Qwen2ForCausalLM.from_pretrained(
    local_dir, dtype=torch.bfloat16, local_files_only=True,
)
flush("loaded on CPU ok, quantizing+moving to cuda via .to()...")
model = model.to("cuda")
flush("moved to cuda ok (no 4-bit this time, just to confirm CPU-first path avoids the pagefile error)")
flush("model loaded ok")
flush(str(model.get_memory_footprint() / 1e9) + " GB")

msgs = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "안녕하세요"}]
prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
inputs = tok(prompt, return_tensors="pt").to(model.device)
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=30)
flush("generation ok: " + tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True))
