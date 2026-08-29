from pathlib import Path
from safetensors import safe_open

def flush(msg):
    print(msg, flush=True)

local_dir = Path(r"E:\hf_cache\hub\models--Qwen--Qwen2.5-7B-Instruct\snapshots\a09a35458c702b33eeacc393d103063234e8bc28")
path = local_dir / "model-00002-of-00004.safetensors"
flush(f"opening {path} fresh, isolated process")
with safe_open(str(path), framework="pt", device="cpu") as f:
    keys = list(f.keys())
    flush(f"{len(keys)} keys retrieved")
    flush(f"first key: {keys[0]}")
    t = f.get_tensor(keys[0])
    flush(f"first tensor loaded: shape={tuple(t.shape)} dtype={t.dtype}")
    for i, k in enumerate(keys):
        t = f.get_tensor(k)
        flush(f"  [{i}] {k} shape={tuple(t.shape)}")
flush("ALL OK")
