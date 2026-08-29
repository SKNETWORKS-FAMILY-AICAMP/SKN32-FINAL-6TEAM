from safetensors import safe_open

path = r"E:\hf_cache\hub\models--Qwen--Qwen2.5-7B-Instruct\snapshots\a09a35458c702b33eeacc393d103063234e8bc28\model-00001-of-00004.safetensors"
print("opening with safe_open, framework=pt, device=cpu...")
with safe_open(path, framework="pt", device="cpu") as f:
    keys = list(f.keys())
    print("keys:", len(keys))
    first = keys[0]
    print("loading first tensor:", first)
    t = f.get_tensor(first)
    print("loaded ok, shape", t.shape, "dtype", t.dtype)
