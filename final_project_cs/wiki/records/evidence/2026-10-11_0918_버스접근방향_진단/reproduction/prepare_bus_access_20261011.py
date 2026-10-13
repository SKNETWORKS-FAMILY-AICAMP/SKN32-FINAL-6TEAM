from pathlib import Path
import shutil,json,hashlib
root=Path(__file__).resolve().parents[2];cs=root/'final_project_cs'
tag='2026-10-11_0920_버스정류장_접근후보'
ev=cs/'wiki/records/evidence/2026-10-11_0918_버스접근방향_진단'
files=['app/domains/travel_ops/instances/mobility/engine/bus.py','app/domains/travel_ops/instances/mobility/engine/plan.py','wiki/teams/mobility.md']
rows=[]
for name in files:
    p=cs/name;backup=p.parent/'_backup'/tag/p.name;backup.parent.mkdir(parents=True,exist_ok=True)
    assert not backup.exists();shutil.copy2(p,backup)
    if name.startswith('app/'):
        legacy=cs/'legacy'/tag/name;legacy.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,legacy)
    rows.append({'path':str(p.relative_to(root)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'backup':str(backup.relative_to(root)).replace('\\','/')})
with (ev/'backups-v1.json').open('x',encoding='utf8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
debug=cs/'wiki/records/reports/debugs/2026-10-11_0920_最短停留所間だけでバス候補を落とす.md'
debug=debug.with_name('2026-10-11_0920_정류장최소구간_버스후보누락.md')
with debug.open('x',encoding='utf8') as f:f.write('''# 정류장 최소 구간만 남겨 버스 후보를 누락한다

## 미해결

위치: `engine/bus.py:155`의 `routes_between`, `engine/plan.py:530`의 버스 직행 생성.

노선별로 정류장 수가 가장 적은 한 쌍만 남긴다. 장소에서 더 가까운 승하차 정류장 쌍은 차를 조금 더 타더라도 전체 소요가 줄 수 있으나 판정에 도달하지 않는다. 기존 개발 서울 좌표 100쌍을 스캔하여 송파역→압구정로데오 345번 등에서 접근 도보를 포함한 단순 모델의 개선 가능성을 찾았다. 모델 값은 가설이며 제품 결과는 변경 전후 재생으로 확인한다.

수정 범위: 기존 최소 구간 쌍을 유지하고 노선마다 직선 접근 도보 합이 최소인 쌍을 최대 한 개 추가한다. 방향·반경·1.2km 직선 정책·운행 검증·같은 출발 재검증·표시 상한은 유지한다. 전체 최적 탐색으로 주장하지 않는다.

위험: 실제로 가능한 버스가 후보 생성 단계에서 사라지거나 불필요하게 걷게 된다. 제한 API 없이 정적 자료로 재현한다.

재현: 워크스페이스 루트에서 `python .tmp/mobility_complete_20261008/replay_bus_access_20261011.py before` 및 `scan_bus_access_20261011.py`. 원문 근거: [진단 자료](../../evidence/2026-10-11_0918_버스접근방향_진단/).

405번 남산↔이태원은 두 방향 모두 현재 보행망에서 공통 출발보다 먼저 떠나야 해서 제외되었다. 이 사례를 이번 생성 결함과 혼동하지 않는다.
''')
p=cs/'wiki/teams/mobility.md';text=p.read_text(encoding='utf8')
contract='''## 2026-10-11 버스 직행 접근 정류장 후보 계약

버스 직행 탐색은 노선마다 기존 최소 정류장 구간 쌍을 보존하고, 같은 반경 안에서 승차 전·하차 후 직선 접근 도보 합이 최소인 별도 쌍을 최대 한 개 추가하여 판정한다. 같은 쌍이면 중복하지 않는다. 따라서 노선당 후보는 최대 두 개이며 모든 정류장 조합의 최적해를 보장하지 않는다. 직선 도보 정책·도로망 접근 재계산·방향 순서·운행 여부·공통 출발 재검증·표시 상한은 기존대로 적용한다. 공개 응답 필드는 바꾸지 않는다. 기존 `routes_between`의 기본 동작은 보존하며 제품의 버스 직행 생성에서만 추가 후보를 요청한다.

'''
text=text.replace('# Mobility Team\n\n','# Mobility Team\n\n'+contract,1);p.write_text(text,encoding='utf8')
print('백업 3개와 수정 전 결함·계약 기록 저장')
