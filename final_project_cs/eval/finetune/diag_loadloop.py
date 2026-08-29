import sys
import json
from pathlib import Path
from safetensors import safe_open

local_dir = Path(r"E:\hf_cache\hub\models--Qwen--Qwen2.5-7B-Instruct\snapshots\a09a35458c702b33eeacc393d103063234e8bc28")

def flush(msg):
    print(msg, flush=True)

flush("STEP 1: read index.json")
with open(local_dir / "model.safetensors.index.json", encoding="utf-8") as f:
    index = json.load(f)
weight_map = index["weight_map"]
flush(f"STEP 1 ok: {len(weight_map)} params across shards")

shard_files = sorted(set(weight_map.values()))
flush(f"STEP 2: shard files = {shard_files}")

flush("STEP 3: iterate ALL tensors across ALL shards via safe_open (pure safetensors, no torch model)")
total = 0
for shard in shard_files:
    flush(f"  opening shard {shard}")
    path = local_dir / shard
    with safe_open(str(path), framework="pt", device="cpu") as f:
        keys = list(f.keys())
        flush(f"    {len(keys)} tensors in this shard")
        for i, k in enumerate(keys):
            t = f.get_tensor(k)
            total += 1
            if i % 20 == 0:
                flush(f"    ...loaded tensor {i}/{len(keys)}: {k} shape={tuple(t.shape)}")
    flush(f"  shard {shard} fully read ok")
flush(f"STEP 3 ok: {total} tensors read total via pure safetensors")

flush("STEP 4: construct empty Qwen2ForCausalLM from config only (random init, no weight loading)")
from transformers import AutoConfig  # noqa: E402
config_dict = json.loads((local_dir / "config.json").read_text(encoding="utf-8"))
from transformers.models.qwen2.configuration_qwen2 import Qwen2Config  # noqa: E402
cfg = Qwen2Config(**{k: v for k, v in config_dict.items() if k not in ("architectures", "transformers_version")})
flush("  config built ok")
from transformers import Qwen2ForCausalLM  # noqa: E402
import torch  # noqa: E402
with torch.device("meta"):
    model = Qwen2ForCausalLM(cfg)
flush("STEP 4 ok: empty meta model constructed")

flush("STEP 5: assign real weights into the meta model one shard at a time using load_state_dict(assign=True)")
model = model.to_empty(device="cpu")
for shard in shard_files:
    flush(f"  loading shard {shard} into model...")
    path = local_dir / shard
    sd = {}
    with safe_open(str(path), framework="pt", device="cpu") as f:
        for k in f.keys():
            sd[k] = f.get_tensor(k)
    flush(f"    read {len(sd)} tensors from shard into a plain dict, now assigning...")
    missing, unexpected = model.load_state_dict(sd, strict=False, assign=True)
    flush(f"    assigned ok. missing={len(missing)} unexpected={len(unexpected)}")
flush("STEP 5 ok: full state dict assigned on CPU")

flush("STEP 6: move model to cuda")
model = model.to("cuda", dtype=torch.bfloat16)
flush("STEP 6 ok: model on cuda")

flush("ALL STEPS PASSED")
