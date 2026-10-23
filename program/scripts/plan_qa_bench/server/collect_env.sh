#!/bin/bash
# 서버에서: 시험 환경(GPU·드라이버·CUDA·라이브러리 버전)과 모델 저장소(받은 날·수정판 해시·형식)를 한 파일로 모은다. 읽기 전용 — 큰 파일은 해시하지 않고 크기·수정 시각만 본다.
# 접속 주소·호스트 이름·계정은 적지 않는다. 사용: bash collect_env.sh <서버표시이름> > env_<표시이름>_<날짜>.txt
# 새 실험을 시작할 때마다 돌려 결과 폴더에 같이 남긴다(문서 §91).
SRV=${1:-server}
echo "# 환경 수집 — $SRV — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "## GPU"; nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>&1; nvidia-smi 2>/dev/null | grep -o "CUDA Version: [0-9.]*"
echo "## CPU·메모리"; nproc; grep -m1 "model name" /proc/cpuinfo | cut -d: -f2; free -g | sed -n 2p
echo "## OS"; grep PRETTY_NAME /etc/os-release
echo "## 파이썬 환경별 라이브러리"
for PY in /workspace/rtenv/bin/python /root/venv_imajev/bin/python /usr/bin/python3 /root/venv/bin/python /opt/venv/bin/python /tmp/jevenv/bin/python; do
  [ -x "$PY" ] || continue
  echo "- $PY: $($PY -c 'import sys;print(sys.version.split()[0])' 2>&1)"
  $PY - <<'EOF' 2>&1
import importlib
for m in ('torch', 'transformers', 'peft', 'bitsandbytes', 'accelerate', 'sentence_transformers', 'huggingface_hub', 'laya', 'opendecider', 'gguf', 'safetensors', 'numpy', 'scikit-learn'):
    try:
        mod = importlib.import_module('sklearn' if m == 'scikit-learn' else m)
        print('   ', m, getattr(mod, '__version__', '?'))
    except Exception:
        pass
EOF
done
echo "## 추론 엔진"
command -v ollama >/dev/null && echo "ollama $(ollama --version 2>&1 | head -1)"
for LS in /workspace/deciders/bin/llama-server /root/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server /opt/llama/bin/llama-server; do [ -x "$LS" ] && { echo "$LS: $($LS --version 2>&1 | head -1)"; }; done
if command -v ollama >/dev/null && ollama list >/dev/null 2>&1; then
  echo "## ollama 모델 (이름 · 아이디=내용 해시 앞 12자 · 크기 · 수정 시각)"
  ollama list 2>&1
  for M in $(ollama list 2>/dev/null | awk 'NR>1{print $1}'); do echo "- $M: $(ollama show $M 2>/dev/null | tr -s ' \n' ' ' | cut -c1-260)"; done
fi
echo "## 허깅페이스 캐시(수정판 해시 · 받은 시각)"
for H in /workspace/hf/hub /root/.cache/huggingface/hub /root/hf/hub; do
  [ -d "$H" ] || continue
  for d in "$H"/models--*; do
    [ -d "$d" ] || continue
    repo=$(basename "$d" | sed 's/^models--//; s/--/\//g')
    for s in "$d"/snapshots/*; do [ -d "$s" ] && echo "$repo $(basename "$s") $(stat -c %y "$s" | cut -c1-16)"; done
  done
done
echo "## 폴더로 받은 모델(수정판 해시 · 받은 시각 · 크기)"
for D in /root/hf_models/* /workspace/hf_models/* /workspace/winnow_models /workspace/deciders/winnow_e4b; do
  [ -d "$D" ] || continue
  meta=$(find "$D/.cache/huggingface/download" -name '*.metadata' 2>/dev/null | head -1)
  if [ -n "$meta" ]; then rev=$(sed -n 1p "$meta"); ts=$(sed -n 3p "$meta"); else rev="기록 없음"; ts=$(stat -c %y "$D" | cut -c1-16); fi
  echo "$D 수정판=$rev 시각=$ts 크기=$(du -sm "$D" 2>/dev/null | cut -f1)MB"
done
echo "## GGUF 파일(경로 · 크기 · 수정 시각)"
find /workspace/deciders /workspace/hf_models /root -maxdepth 4 -name '*.gguf' 2>/dev/null | while read f; do echo "$f $(stat -c '%s %y' "$f" | cut -c1-40)"; done
echo "## LoRA 어댑터(기반 모델 · r · alpha · 수정 시각)"
for A in /root/adapters/* /workspace/experts/*; do
  [ -f "$A/adapter_config.json" ] || continue
  python3 - "$A" <<'EOF' 2>&1
import json, os, sys, time
a = sys.argv[1]; c = json.load(open(os.path.join(a, 'adapter_config.json')))
print(a, c.get('base_model_name_or_path'), 'r=%s' % c.get('r'), 'alpha=%s' % c.get('lora_alpha'), time.strftime('%Y-%m-%d %H:%M', time.gmtime(os.path.getmtime(os.path.join(a, 'adapter_config.json')))))
EOF
done
echo "## 끝"
