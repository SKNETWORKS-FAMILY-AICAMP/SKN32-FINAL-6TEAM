from pathlib import Path
from datetime import datetime
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2];sys.stdout.reconfigure(encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
priorpath=ROOT/'final_project_cs/wiki/records/evidence/2026-10-09_1426_김포공항_공표승차_대조/final-integrity-v1.json'
prior=json.loads(priorpath.read_text(encoding='utf8'));hashes=prior['source_test_data_hashes']|prior['artifact_hashes']
current={p:sha(ROOT/p) for p in hashes};changed=[p for p,h in hashes.items() if current[p]!=h]
now=datetime.now().astimezone();tag=now.strftime('%Y-%m-%d_%H%M')+'_차량회전자료_내용갱신'
ev=ROOT/'final_project_cs/wiki/records/evidence'/tag;ev.mkdir()
state={'tag':tag,'evidence':ev.relative_to(ROOT).as_posix(),'previous_integrity':priorpath.relative_to(ROOT).as_posix(),'prepared_at':now.isoformat()}
with (ev/'baseline-v1.json').open('x',encoding='utf8') as f:json.dump({'hashes':current,'previous_matched':len(hashes)-len(changed),'previous_total':len(hashes),'previous_changed':changed,'limited_api_calls':0,'public_web_failures':['CUA初期化: kernel assets path missing','public HTML sandbox DNS failure','public HTML elevated SSL wrong signature type'],'source_scope':'공식 웹 정적 본문은 열림. 실시간 목록 추가 식별은 미확인. 제한 API 공유 사용량/갱신 시각 미확인으로 호출 안 함.'},f,ensure_ascii=False,indent=2)
with (Path(__file__).parent/'turn-reload-state-20261010-v1.json').open('x',encoding='utf8') as f:json.dump(state,f,ensure_ascii=False,indent=2)
print(json.dumps(state,ensure_ascii=False))
