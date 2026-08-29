import torch
from transformers import Qwen2ForCausalLM

local_dir = r"E:\hf_cache\hub\models--Qwen--Qwen2.5-7B-Instruct\snapshots\a09a35458c702b33eeacc393d103063234e8bc28"
print("loading on CPU without device_map...")
model = Qwen2ForCausalLM.from_pretrained(local_dir, dtype=torch.bfloat16, local_files_only=True, low_cpu_mem_usage=False)
print("loaded on CPU ok, moving to cuda...")
model = model.to("cuda")
print("moved to cuda ok")
print(torch.cuda.memory_allocated() / 1e9, "GB allocated")
