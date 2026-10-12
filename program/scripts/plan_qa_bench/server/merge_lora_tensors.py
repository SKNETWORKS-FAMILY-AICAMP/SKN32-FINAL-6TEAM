# 서버에서: LoRA 어댑터를 원본 HF 체크포인트에 「텐서 단위로」 합친다 — 원본과 같은 파일 이름·텐서 이름·설정을 그대로 두어 llama.cpp 변환기가 원본처럼 읽게 한다.
#  (transformers 로 불러 merge_and_unload 해서 저장하면 클래스·텐서 이름이 바뀌어 변환기가 못 읽을 수 있다.)
#  W' = W + (B @ A) × (alpha / r)  — float32 로 계산해 원래 자료형(bf16)으로 되돌린다. 어댑터가 건드리지 않은 텐서는 그대로 복사한다.
#  주의(QLoRA 의 통상적 한계): 학습은 4비트(NF4)로 줄인 기반 위에서 했고 여기서는 bf16 원본에 합친다 — 점수가 학습 때와 조금 다를 수 있어 GGUF 로 바꾼 뒤 같은 문제로 다시 잰다.
# 사용: python merge_lora_tensors.py <원본 HF 폴더> <어댑터 폴더> <출력 폴더>
import json, os, re, shutil, sys
import torch
from safetensors import safe_open
from safetensors.torch import save_file

BASE, ADAPTER, OUT = sys.argv[1:4]
cfg = json.load(open(os.path.join(ADAPTER, 'adapter_config.json')))
scale = cfg['lora_alpha'] / cfg['r']
ad = {}
with safe_open(os.path.join(ADAPTER, 'adapter_model.safetensors'), 'pt') as f:
    for k in f.keys():
        ad[k] = f.get_tensor(k)
mods = {}
for k in ad:
    m = re.match(r'base_model\.model\.(.+)\.lora_([AB])\.weight$', k)
    mods.setdefault(m.group(1), {})[m.group(2)] = ad[k]
print('어댑터 모듈', len(mods), '· 배율', scale, flush=True)
os.makedirs(OUT, exist_ok=True)
shards = sorted(f for f in os.listdir(BASE) if f.endswith('.safetensors'))
used, total = set(), 0
for sh in shards:
    tensors = {}
    with safe_open(os.path.join(BASE, sh), 'pt') as f:
        meta = f.metadata()
        for name in f.keys():
            w = f.get_tensor(name)
            total += 1
            if name.endswith('.weight') and name[:-7] in mods:
                m = mods[name[:-7]]
                delta = (m['B'].float() @ m['A'].float()) * scale
                assert delta.shape == w.shape, (name, delta.shape, w.shape)
                w = (w.float() + delta).to(w.dtype)
                used.add(name[:-7])
            tensors[name] = w.contiguous()
    save_file(tensors, os.path.join(OUT, sh), metadata=meta or {'format': 'pt'})
    print('쓴 파일', sh, len(tensors), '텐서', flush=True)
missing = set(mods) - used
assert not missing, f'합치지 못한 어댑터 모듈 {len(missing)}개: {sorted(missing)[:5]}'
for f in os.listdir(BASE):
    if not f.endswith('.safetensors') and os.path.isfile(os.path.join(BASE, f)):
        shutil.copy(os.path.join(BASE, f), os.path.join(OUT, f))
print(f'합친 모듈 {len(used)}/{len(mods)} · 전체 텐서 {total} · 출력 {OUT}', flush=True)
