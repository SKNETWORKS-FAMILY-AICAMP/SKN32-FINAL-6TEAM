"""예시 일정 정답 파일(골든)과 지금 계산 결과를 칸 단위로 비교한다 — 읽기 전용. 사용: python golden_diff.py <out_dir> (작업 사본 루트에서, DATA_DIR 지정)"""
import json, sys
from pathlib import Path
sys.path.insert(0, 'final_project_cs')
from tests.unit.travel.mobility import test_plan_v1 as T
from app.domains.travel_ops.instances.mobility.engine.plan import plan

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)


def walk(a, b, path, diffs):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                diffs.append((path + [k], '<없음>', b[k]))
            elif k not in b:
                diffs.append((path + [k], a[k], '<없음>'))
            else:
                walk(a[k], b[k], path + [k], diffs)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((path + ['len'], len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, path + [i], diffs)
    elif a != b:
        diffs.append((path, a, b))


doc = json.loads(T.IN.read_text(encoding='utf-8'))
for name, modes, gold in (('subway_walk', T.MODES, T.GOLD), ('all', T.MODES_ALL, T.GOLD_ALL)):
    got = plan(doc['places'], doc['items'], doc.get('party_size'), doc.get('constraints'), runtime=T._runtime(), modes=modes)
    got.pop('basis')
    got = T._customer_values(got)
    want = json.loads(gold.read_text(encoding='utf-8'))
    (out / f'current-{name}.json').write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding='utf-8')
    diffs = []
    walk(want, got, [], diffs)
    print(f'=== {name}: {len(diffs)} 칸 다름 (골든 → 지금)')
    for p, a, b in diffs:
        sa, sb = json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False)
        print('  ', '/'.join(map(str, p)), '|', sa[:160], '→', sb[:160])
