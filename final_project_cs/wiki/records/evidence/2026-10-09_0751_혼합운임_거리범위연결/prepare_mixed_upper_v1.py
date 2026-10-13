from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
now = datetime.now().astimezone()
tag = now.strftime('%Y-%m-%d_%H%M') + '_혼합운임_거리범위연결'
ev = cs / 'wiki/records/evidence' / tag
ev.mkdir(exist_ok=False)
backups = []
for rel in ('app/domains/travel_ops/instances/mobility/engine/options.py',
            'app/domains/travel_ops/instances/mobility/engine/plan.py', 'wiki/teams/mobility.md'):
    p = cs / rel
    b = p.parent / '_backup' / tag / p.name
    b.parent.mkdir(parents=True, exist_ok=True)
    assert not b.exists()
    shutil.copy2(p, b)
    backups.append({'source': p.relative_to(root).as_posix(), 'backup': b.relative_to(root).as_posix(),
                    'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
debug_rel = f'wiki/records/reports/debugs/{tag}_상단계산을_혼합후보에서_누락.md'
with (cs / debug_rel).open('x', encoding='utf8') as f:
    f.write('# 혼합 후보의 지하철 거리 범위 상단 누락\n\n## 미해결\n\noptions.py:566은 연속 지하철 묶음의 확정 요금만 사용합니다. 같은 묶음의 거리 범위 상단은 subway_fare_upper로 계산할 수 있어도 혼합 후보에서는 요금 칸을 잃습니다. plan.py:1695의 혼합 상한 문구도 실제 결제 보장과 구분해야 합니다. 통제 조건으로 수정 전 실패를 확인하고 기존 승인 거리 범위만 재사용합니다. 공식 거리 누락을 기본운임으로 메우지 않으며 할인 후 정확 요금은 별도 남습니다.\n')
with (cs / 'wiki/teams/mobility.md').open('a', encoding='utf8') as f:
    f.write(f'\n\n## {tag} 혼합 경로의 개별 요금 범위 전달 계약\n\nfare_upper_of는 버스가 포함된 혼합 경로의 연속 지하철 묶음을 한 번으로 계산합니다. 지하철 확정 요금이 없지만 승인된 거리 범위로 subway_fare_upper를 계산할 수 있으면 그 상단을 사용합니다. 버스 요금 또는 지하철 범위 근거가 하나라도 없으면 값을 만들지 않습니다. 공개 label은 환승 할인 전 예상액 상단으로 표시하며 실제 결제 보장·통합 할인 후 확정액으로 취급하지 않습니다. 버스 거리·하차 태그·동일 노선·조조 규칙을 반영하는 할인 후 제품 연결은 여전히 미완료입니다.\n')
state = {'tag': tag, 'created_at': now.isoformat(), 'backups': backups, 'debug': debug_rel,
         'prior_source_hashes': 209, 'prior_artifacts': 6}
with (ev / 'start-v1.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
with (Path(__file__).parent / 'mixed-upper-work-v1.json').open('x', encoding='utf8') as f:
    json.dump(state, f, ensure_ascii=False)
print(tag)
