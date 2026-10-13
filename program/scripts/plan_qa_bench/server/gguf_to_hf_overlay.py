# 서버에서: 공개 가중치가 GGUF(BF16)뿐인 Winnow-E4B 를 학습용 HF 체크포인트로 되돌린다.
#  방법: 원본 Gemma-4-E4B-it 의 HF 체크포인트(같은 구조·같은 텐서 이름)를 뼈대로 두고, 언어 모델 텐서마다 GGUF 의 같은 텐서를 읽어 덮어쓴다(llama.cpp 의 tensor_mapping 으로 이름을 대응).
#   Gemma-4 변환은 norm 에 이동값을 더하지 않고(norm_shift=0) 가중치를 그대로 옮기므로 BF16 GGUF 에서는 값이 그대로 돌아온다.
#   검증: ① 대응된 텐서 수 · 대응 못 한 텐서 목록 ② 원본과 같은 텐서/달라진 텐서 수 — Winnow 가 LoRA 를 합친 것이라면 달라진 것은 어텐션·MLP 투영 행렬뿐이어야 한다.
#   비전·오디오 탑 텐서는 GGUF 본체에 없어 원본 값을 그대로 둔다(글 전용 학습에는 쓰이지 않는다).
# 사용: python gguf_to_hf_overlay.py <원본 HF 폴더> <winnow-bf16.gguf> <출력 폴더> [--dry]
import json, os, shutil, sys
sys.path.insert(0, os.environ.get('GGUF_PY', '/root/llama.cpp/gguf-py'))
import gguf
import numpy as np
import torch
from safetensors import safe_open
from safetensors.torch import save_file

BASE, GG, OUT = sys.argv[1:4]
DRY = '--dry' in sys.argv
cfg = json.load(open(os.path.join(BASE, 'config.json')))
n_blocks = (cfg.get('text_config') or cfg)['num_hidden_layers']
tmap = gguf.get_tensor_name_map(gguf.MODEL_ARCH.GEMMA4, n_blocks)
reader = gguf.GGUFReader(GG)
gt = {t.name: t for t in reader.tensors}
print('GGUF 텐서', len(gt), '· 블록', n_blocks, flush=True)


def to_torch(t):
    ty = t.tensor_type
    if ty == gguf.GGMLQuantizationType.BF16:
        return torch.from_numpy(np.ascontiguousarray(t.data).view(np.int16).copy()).view(torch.bfloat16)
    if ty == gguf.GGMLQuantizationType.F16:
        return torch.from_numpy(np.ascontiguousarray(t.data).copy()).to(torch.bfloat16)
    if ty == gguf.GGMLQuantizationType.F32:
        return torch.from_numpy(np.ascontiguousarray(t.data).copy()).to(torch.bfloat16)
    return torch.from_numpy(gguf.quants.dequantize(t.data, ty)).to(torch.bfloat16)


shards = sorted(f for f in os.listdir(BASE) if f.endswith('.safetensors'))
used, unmapped, missing_in_gguf, same, changed, shape_fix = set(), [], [], 0, 0, 0
changed_kinds = {}
out = {}
for sh in shards:
    with safe_open(os.path.join(BASE, sh), 'pt') as f:
        meta = f.metadata()
        for name in f.keys():
            w = f.get_tensor(name)
            is_text = '.language_model.' in name or name.startswith('lm_head')
            key = name.replace('.language_model.', '.')      # llama.cpp 변환기도 이 접두를 떼고 이름을 대응한다
            gname = tmap.get_name(key, try_suffixes=('.weight', '.bias'))
            if gname is None and name.endswith(('.layer_scalar', '.per_dim_scale')):
                gname = tmap.get_name(key + '.weight', try_suffixes=('.weight', '.bias'))
            if gname is None:
                if is_text:
                    unmapped.append(name)
                out[name] = w
                continue
            if gname is not None and gname not in gt and gname + '.weight' in gt:
                gname += '.weight'
            if gname not in gt:
                if is_text:
                    missing_in_gguf.append((name, gname))
                out[name] = w
                continue
            g = to_torch(gt[gname])
            if g.shape != w.shape:
                if g.numel() == w.numel():
                    g = g.reshape(w.shape)
                    shape_fix += 1
                else:
                    unmapped.append(f'{name} 모양 불일치 gguf {tuple(g.shape)} 원본 {tuple(w.shape)}')
                    out[name] = w
                    continue
            used.add(gname)
            if torch.equal(g, w):
                same += 1
            else:
                changed += 1
                kind = name.split('.')[-2] if name.endswith('.weight') else name.split('.')[-1]
                st = changed_kinds.setdefault(kind, [0, 0.0])
                st[0] += 1
                st[1] += float((g.float() - w.float()).norm() / (w.float().norm() + 1e-9))
            out[name] = g.contiguous()
print(f'대응·덮어씀 {len(used)} (원본과 같음 {same} · 달라짐 {changed} · 모양 맞춤 {shape_fix}) · 글 모델인데 대응 못 함 {len(unmapped)} · GGUF 에 없음 {len(missing_in_gguf)}')
for k, (n, r) in sorted(changed_kinds.items(), key=lambda x: -x[1][0]):
    print(f'   달라진 종류 {k}: {n}개 · 평균 상대 차이 {r / n:.4f}')
for n in unmapped[:10]:
    print('   대응 못 함:', n)
for n, g in missing_in_gguf[:10]:
    print('   GGUF 에 없음:', n, '→', g)
leftover = [n for n in gt if n not in used and not n.startswith('rope_freqs')]
print(f'GGUF 쪽에서 쓰이지 않은 텐서 {len(leftover)}: {leftover[:8]}')
if DRY:
    sys.exit(0)
assert not unmapped, '글 모델 텐서를 대응 못 했다 — 덮어쓰지 않고 멈춘다'
os.makedirs(OUT, exist_ok=True)
save_file(out, os.path.join(OUT, shards[0] if len(shards) == 1 else 'model.safetensors'), metadata=meta or {'format': 'pt'})
for f in os.listdir(BASE):
    if not f.endswith('.safetensors') and os.path.isfile(os.path.join(BASE, f)):
        shutil.copy(os.path.join(BASE, f), os.path.join(OUT, f))
print('저장', OUT, flush=True)
