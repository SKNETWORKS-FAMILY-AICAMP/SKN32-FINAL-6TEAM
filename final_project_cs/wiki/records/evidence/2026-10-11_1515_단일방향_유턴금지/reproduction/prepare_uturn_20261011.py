from pathlib import Path
import hashlib, json, shutil

root=Path(__file__).resolve().parents[2]
repo=root/'final_project_cs'
out=repo/'wiki/records/evidence/2026-10-11_1515_단일방향_유턴금지'
out.mkdir(exist_ok=False)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
prior=json.loads((repo/'wiki/records/evidence/2026-10-11_0918_버스접근방향_진단/integrity-final-v2.json').read_text(encoding='utf8'))
check={}
for group in ('source_test_data_hashes','artifact_hashes'):
    rows={p: {'before':h,'now':digest(root/p)} for p,h in prior[group].items()}
    check[group]={'total':len(rows),'matched':sum(v['before']==v['now'] for v in rows.values()),'changed':{p:v for p,v in rows.items() if v['before']!=v['now']}}
with (out/'integrity-start.json').open('x',encoding='utf8') as f: json.dump(check,f,indent=2)
assert all(not g['changed'] for g in check.values()),check
targets=[repo/'scripts/mobility/build_car_turn_policy_v1.py',repo/'wiki/teams/mobility.md',root/'datasets/mobility/processed/mobility/road_graph_v2/turn_restrictions_v1.json',root/'datasets/mobility/REPORT.md']
backups=[]
for p in targets:
    b=p.parent/'_backup/2026-10-11_1515_単一方向ユータン' /p.name
    b.parent.mkdir(parents=True,exist_ok=True)
    assert not b.exists()
    shutil.copy2(p,b)
    backups.append({'original':str(p.relative_to(root)),'backup':str(b.relative_to(root)),'sha256':digest(b)})
    if p.suffix=='.py':
        legacy=repo/'legacy/2026-10-11_1515_유턴금지'/p.relative_to(repo)
        legacy.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,legacy)
with (out/'backups.json').open('x',encoding='utf8') as f: json.dump(backups,f,ensure_ascii=False,indent=2)
wiki=targets[1]
text=wiki.read_text(encoding='utf8')
marker='## 2026-10-11 단일 방향 동일 도로 유턴 금지 계약\n\n'
contract=('동일 OSM 도로의 from/to와 단일 via 교차로가 있고, 차량 진입·진출 방향이 각각 하나이며 진출 간선이 진입 간선의 정확한 역방향일 때만 정적 no_u_turn을 적용한다. '
          '원문·그래프 해시를 확인하고, 시간·차종 예외·다중 방향·다른 미해결 사유가 있으면 이 보강에서 제외한다. '
          '적용은 해당 교차로에서 되돌아가는 회전만 금지한다. 같은 도로 직진, 출발점에서의 자유 방향 선택, 보행·자전거에는 적용하지 않는다. '
          '기존 단순 회전 관계를 보존하며 전체 도로 규칙 충족이나 실주행 검증으로 표시하지 않는다.\n\n')
# 현재 계약보다 앞에 추가한다. 머리말/front matter는 그대로 둔다.
pos=text.index('\n## ')
wiki.write_text(text[:pos+1]+marker+contract+text[pos+1:],encoding='utf8')
debug=repo/'wiki/records/reports/debugs/2026-10-11_1515_단일방향_유턴금지_일괄제외.md'
debug.write_text('# 단일 방향 동일 도로 유턴 금지의 일괄 제외\n\n## 미해결\n\n'
 '원자료 6,258개 관계를 전수 검사했다. 다른 미해결 사유가 없는 동일 도로 no_u_turn 2,224개 중 2,219개는 진입·진출이 각각 하나이며 서로 정확한 역방향이다. 기존 생성기는 같은 도로라는 이유만으로 모두 제외한다. 남은 5개는 방향 모호/비역방향으로 계속 제외한다.\n\n'
 '위치: `scripts/mobility/build_car_turn_policy_v1.py`의 후보 목록 선택. 위험: 차량 탐색이 명시된 되돌아가기 금지를 누락할 수 있다. 실제 차량 운행·현장 법규 확인은 하지 않았다.\n\n'
 '재현: 이 회차 evidence의 `audit-and-replay.py` 및 `diagnosis.json`을 참조한다. 공식 의미는 [OSM no_u_turn](https://wiki.openstreetmap.org/wiki/Tag:restriction%3Dno_u_turn) 2026-10-11 조회에서 확인했다.\n',encoding='utf8')
print(json.dumps(check)); print(out)
