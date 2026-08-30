import torch
from transformers import Qwen2ForCausalLM

def flush(msg):
    print(msg, flush=True)

local_dir = r"E:\hf_cache\hub\models--Qwen--Qwen2.5-7B-Instruct\snapshots\a09a35458c702b33eeacc393d103063234e8bc28"
flush("loading in fp16 with device_map=auto, low_cpu_mem_usage=True, no quantization...")
model = Qwen2ForCausalLM.from_pretrained(
    local_dir, dtype=torch.float16, device_map="auto",
    low_cpu_mem_usage=True, local_files_only=True,
    max_memory={0: "9GiB", "cpu": "10GiB"},
)
flush("model loaded ok")
flush(f"hf_device_map: {model.hf_device_map}")
flush(f"{model.get_memory_footprint() / 1e9} GB footprint")
