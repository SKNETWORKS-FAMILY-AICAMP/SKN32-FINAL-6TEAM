from pathlib import Path
from datetime import datetime
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2]
state=json.loads((Path(__file__).parent/'published-boarding-state-v1.json').read_text(encoding='utf8'))
EV=ROOT/state['evidence'];TAG=datetime.now().astimezone().strftime('%Y-%m-%d_%H%M')+'_공표승차_명세누락검사'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[ROOT/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/datacheck.py',ROOT/'datasets/mobility/processed/mobility/MANIFEST_git_v1.json',ROOT/'final_project_cs/wiki/teams/mobility.md',ROOT/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/runtime.py',ROOT/'final_project_cs/tests/unit/travel/mobility/test_published_boarding_v1.py']
records=[]
for p in paths:
 d=p.parent/'_backup'/TAG/p.name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);assert sha(p)==sha(d)
 records.append({'source':p.relative_to(ROOT).as_posix(),'backup':d.relative_to(ROOT).as_posix(),'sha256':sha(p)})
with (EV/'backup-additions-v1.json').open('x',encoding='utf8') as f:json.dump(records,f,ensure_ascii=False,indent=2)
with paths[2].open('a',encoding='utf8') as f:f.write('\n명세 누락 보완: 공표 승차 자료가 한 번 적재된 뒤 사라지면 같은 프로세스는 이전 무대조 계산으로 복귀하지 않고 오류를 냅니다. 기동 명세에 공표 자료가 등록된 환경에서도 누락은 필수 입력 실패입니다. 원래 등록되지 않은 환경만 기존 동작을 유지합니다.\n')
