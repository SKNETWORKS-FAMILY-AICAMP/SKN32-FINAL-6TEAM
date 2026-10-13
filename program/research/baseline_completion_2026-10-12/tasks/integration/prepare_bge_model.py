"""공개 BGE-M3 원본을 별도 로컬 폴더에 받는다. 유료 추론·사용자 자료 전송 없음."""
from pathlib import Path
import json, os, hashlib
os.environ['HF_HUB_DISABLE_XET'] = '1'
from huggingface_hub import HfApi, snapshot_download
root = Path(__file__).resolve().parents[5]
target = root / 'datasets/travel/baseline_completion_20261012/model/bge-m3'
target.mkdir(parents=True, exist_ok=True)
api = HfApi(token=False)
info = api.model_info('BAAI/bge-m3')
print('revision', info.sha, flush=True)
snapshot_download('BAAI/bge-m3', revision=info.sha, token=False, local_dir=target,
    allow_patterns=['config.json','modules.json','sentence_bert_config.json','config_sentence_transformers.json',
                    '1_Pooling/config.json','pytorch_model.bin','tokenizer.json','tokenizer_config.json',
                    'special_tokens_map.json','sentencepiece.bpe.model','README.md'], max_workers=2)
assert (target/'pytorch_model.bin').is_file(), '실제 모델 가중치가 필요합니다'
files={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
       for p in target.rglob('*') if p.is_file() and '.cache' not in p.parts}
(target.parent/'model-manifest.json').write_text(json.dumps(dict(model='BAAI/bge-m3',revision=info.sha,
    additional_training=False,dimension=1024,files=files),indent=2)+'\n',encoding='utf-8')
print('model_ready', len(files), flush=True)
