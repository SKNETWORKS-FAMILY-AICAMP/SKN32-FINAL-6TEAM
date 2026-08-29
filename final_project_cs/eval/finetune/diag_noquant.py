import torch
from transformers import Qwen2ForCausalLM

local_dir = r"E:\hf_cache\hub\models--Qwen--Qwen2.5-7B-Instruct\snapshots\a09a35458c702b33eeacc393d103063234e8bc28"
print("loading model WITHOUT quantization, CPU, no device_map...")
model = Qwen2ForCausalLM.from_pretrained(
    local_dir, dtype=torch.bfloat16, local_files_only=True,
)
print("model loaded ok (CPU, no quant)")
print(model.get_memory_footprint() / 1e9, "GB")
