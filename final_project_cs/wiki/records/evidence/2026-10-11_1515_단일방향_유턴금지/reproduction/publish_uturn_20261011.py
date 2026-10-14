from pathlib import Path
from datetime import datetime
import hashlib, json, shutil, difflib
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[2];repo=root/'final_project_cs'
ev=repo/'wiki/records/evidence/2026-10-11_1515_단일방향_유턴금지'
report=repo/'wiki/records/reports/2026-10-11_1525_차량유턴금지_2219개_탐색적용.md'
wiki=repo/'wiki/teams/mobility.md'
debug=repo/'wiki/records/reports/debugs/2026-10-11_1515_단일방향_유턴금지_일괄제외.md'
data_report=root/'datasets/mobility/REPORT.md'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
backups=json.loads((ev/'backups.json').read_text(encoding='utf8'))
for p in (wiki,debug,data_report):
    b=p.parent/'_backup/2026-10-11_1525_유턴검증완료'/p.name
    b.parent.mkdir(parents=True,exist_ok=True);assert not b.exists();shutil.copy2(p,b)
    backups.append({'original':str(p.relative_to(root)),'backup':str(b.relative_to(root)),'sha256':digest(b)})
with (ev/'backups-final.json').open('x',encoding='utf8') as f:json.dump(backups,f,ensure_ascii=False,indent=2)
d=json.loads((ev/'diagnosis.json').read_text(encoding='utf8'))
c=json.loads((ev/'car-comparison.json').read_text(encoding='utf8'))
s=json.loads((ev/'scope-validation.json').read_text(encoding='utf8'))
p=json.loads((ev/'product-replay.json').read_text(encoding='utf8'))
xml=ET.parse(ev/'related-v1.xml');tests=xml.findall('.//testcase')
assert len(tests)==56 and not xml.findall('.//failure') and not xml.findall('.//error')
assert len(p['rows'])==4 and c['after_success']==100
report_text='''# 차량 유턴 금지 2,219개를 실제 탐색에 적용했습니다

기존 자료에서 빠졌던 단일 방향 유턴 금지 2,219개를 추가했습니다. 서울 개발 좌표 100쌍 중 2쌍에서 금지 유턴을 피하는 경로로 바뀌었고, 자동차·택시 판정에서도 새 경로를 사용했습니다. 로컬 수정이며 운영 배포·실주행 확인은 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 추가 관계의 도로·교차로 대조 | 통과 | 2,219/2,219 = 100% |
| 다른 진출 방향 보존 | 통과 | 4,526/4,526 = 100% |
| 서울 개발 경로 계산 | 성공 | 100/100 = 100% |
| 관련 회귀 시험 | 통과 | 56/56 = 100% |

![회전 적용과 개발 경로 전후 비교](assets/2026-10-11_same_way_uturn/uturn-before-after-v1.png)

## 사용자에게 달라지는 경로

| 같은 좌표의 구간 | 수정 전 | 수정 후 | 변화 |
|---|---:|---:|---|
| 회현역 → 광장시장 | 3,289.90m | 3,385.83m | 누락 유턴 회피 · +95.93m |
| 화곡역 → 구로디지털단지역 | 10,534.77m | 10,558.78m | 누락 유턴 회피 · +24.01m |

100쌍에서 추가 대상 유턴을 포함한 경로는 2/100 → 0/100이며 나머지 98쌍의 거리는 동일했습니다. 거리 감소를 목표로 한 수정이 아니라 원자료의 회전 금지를 지키는 수정입니다. 초기 시각별 교통 모델을 적용한 자동차·택시 판정 4/4도 새 거리·적용 관계 수를 받았습니다. 라우터의 정적 시간 비용과 제품의 TOPIS 시간 모델은 서로 다르므로 이 표에서 실주행 소요를 주장하지 않습니다.

이 표본은 기존 개발 좌표 100쌍을 다시 사용했습니다. 이번에 새로 수집한 웹 경로·독립 보류 표본·실제 운행 측정이 아닙니다. 시작/도착 좌표는 [재생 원문](../evidence/2026-10-11_1515_단일방향_유턴금지/product-replay.json)에 기록했습니다. 이번에 다음·네이버·구글 지도 경로 대조 표본을 추가하지 않았습니다.

## 원인과 수정

기존 추출기는 동일 OSM 도로를 from/to로 쓰면 진입 방향이 모호할 수 있어 모두 제외했습니다. 전수 재검사한 6,258관계 중 다른 미해결 사유가 없는 동일 도로 no_u_turn은 2,224개였습니다. 그중 2,219개는 진입·진출이 각각 하나이며, 진출은 진입 간선의 정확한 역방향이었습니다. 나머지 5개는 다중 방향 또는 비역방향이므로 계속 제외했습니다.

[OSM 공식 no_u_turn 문서](https://wiki.openstreetmap.org/wiki/Tag:restriction%3Dno_u_turn)는 동일 도로를 from/to로 사용하는 교차로 유턴 금지 표현을 설명합니다(2026-10-11 조회). 이를 해당 교차로의 정확한 역방향 간선 쌍에 한정해 적용했습니다. 시간·차종 예외, via-way, 다른 미해결 사유, 방향 중복을 확장 적용하지 않았습니다.

- [생성기](../../../scripts/mobility/build_car_turn_policy_v1.py): `--include-same-way-uturn`을 명시할 때 원문 전체 해시·분모를 검사하고 유일한 역방향 관계만 추가합니다. 기본 실행 결과와 기존 규칙 2,487개는 보존합니다.
- [새 시험](../../../tests/unit/travel/mobility/test_same_way_uturn_policy_v1.py): 모호한 관계 제외, 원문 변조 거부, 금지 회전을 즉시 유턴으로 우회하던 재현, 보행·자전거 및 자유 출발 보존을 검사합니다.
- 로컬 도로 자료의 회전 파일은 백업 후 원자 교체했습니다. 도로 노드·간선 자체와 운영 설정은 바꾸지 않았습니다. 기존 런타임의 내용 해시 감지가 새 자료를 읽는 것을 확인했습니다.

2,219개 모두 OSM 도로 ID·교차로 ID·차량 양방향 통행과 일치했습니다. 수정 전에는 2,218개가 허용됐고 1개는 기존 다른 회전 규칙으로 이미 차단됐습니다. 수정 후 2,219개 모두 금지되며 해당 진입에서 다른 진출 방향 4,526개는 허용 상태가 같았습니다.

적용된 자료 관계 수는 2,487/6,258 = 39.7% → 4,706/6,258 = 75.2%입니다. 분모는 보유 그래프와 관련된 OSM 관계 수입니다. **이 비율은 전체 실사용 준비도, 현행 도로 법규 완전성 또는 경로 정확도가 아닙니다.** 미적용 1,552관계에는 via-way·조건·미대응·모호한 관계 등이 남아 있습니다. 응답의 기존 `excluded_candidate_relations=6`은 초기 단순 후보 2,493개에서 제외한 6개를 뜻하며 미적용 전체 수가 아닙니다.

## 검증 기록

| 확인 | 실제 결과 | 범위 |
|---|---|---|
| 시작 무결성 | 500/500 코드·시험·데이터, 48/48 기존 산출물 일치 | 직전 검증 명세와 비교 |
| 새 시험 | 17/17 통과 | 합성·통제 조건 |
| 관련 시험 | 56/56 통과, 2개 별도 실제 그래프 시험 제외 | 새 17개 포함, 건너뜀 0 |
| 실제 저장 그래프 재생 | 전·후 각각 100/100 경로 계산 성공 | 같은 기존 개발 좌표 |
| 두 탐색 방식 비교 | 2/2 거리·비용 일치 | 변경된 두 구간, A*·다익스트라 |
| 제품 판정 연결 | 4/4 feasible·새 적용 수 4,706 전달 | 두 구간 × 자동차/택시 |
| 정적 검사 | 수정 생성기·새 시험 2파일 통과 | Ruff |

mock 서버 시험 (화면 반응): 안 했습니다. 이번 범위는 이동 계산기와 저장 도로 자료입니다.

실서버 확인 (서버 응답): 안 했습니다. 로컬 저장 자료를 실제 계산기 조립 경로로 읽어 오프라인 판정을 확인했으며 HTTP 응답·실제 탑승·실제 결제는 확인하지 않았습니다.

pytest 완료 뒤 pyreadline3 종료 정리 과정의 Windows 경고가 출력됐습니다. 시험 결과 XML은 56개 통과, 프로세스 종료 코드는 0이며 경고 원문을 로그에 보존했습니다.

[원문·재생 로그](../evidence/2026-10-11_1515_단일방향_유턴금지/) · [범위 검증](../evidence/2026-10-11_1515_단일방향_유턴금지/scope-validation.json) · [제품 판정](../evidence/2026-10-11_1515_단일방향_유턴금지/product-replay.json) · [백업 명세](../evidence/2026-10-11_1515_단일방향_유턴금지/backups-final.json).

## 재현

저장소 루트에서 생성할 때 `python -m scripts.mobility.build_car_turn_policy_v1 --audit <기존 추출 폴더> --graph <동일 해시 도로 폴더> --out <존재하지 않는 새 파일> --include-same-way-uturn`을 사용합니다. 기존 파일로 출력하면 배타적 생성이 거부됩니다. 원문 해시와 도로 해시가 다르면 중단합니다.

이 회차 재생 스크립트는 [reproduction](../evidence/2026-10-11_1515_단일방향_유턴금지/reproduction/)에 보존했습니다. 최초 감사 스크립트는 로컬 회전 자료를 교체하므로 재검증에는 사본과 새 출력 폴더를 사용해야 합니다. 실행 로그·JSON을 덮어쓰지 않습니다.

## API 예비량과 남은 범위

일일 제한 API 호출 0회, 오프라인 감사·재생·시험의 외부 연결 시도 모두 0회입니다. 공급자별 공유 누적량·실제 제한 단위·갱신 시각은 확인하지 못했으므로 API를 부르지 않았습니다. 조회 전후 누적량·잔여량·갱신 시각은 모두 미확인, 이번 작업 차감량은 0입니다. 20% 예비량, 월/비용 상한, 운영 서비스 한도·예약 주기·알림 정책을 바꾸지 않았습니다.

전체 21기능 판정은 기존 조건부 사용 3개·개선 필요 9개·추가 검증 9개를 승격하지 않습니다. 이번 수정만으로 21기능의 실사용 완료를 선언하지 않습니다. 실시간 출발 후속 재계산의 실제 시각 대조, 복잡한 회전 관계, 도보 신규 웹 표본, 운임 실제 태그·결제 검증이 남아 있습니다. 커밋·푸시·배포·외부 메시지는 실행하지 않았습니다.
'''
with report.open('x',encoding='utf8') as f:f.write(report_text)
text=wiki.read_text(encoding='utf8');pos=text.index('## 2026-10-11 단일 방향')
summary=('## 2026-10-11 유턴 금지 2,219개 추가 검증\n\n'
 '동일 도로의 유일한 역방향 유턴 금지를 추가하여 로컬 차량 탐색 적용이4,706/6,258관계가 됐습니다. 기존2,487관계와 다른 진출4,526개를 보존했습니다. '
 '기존 서울 개발 좌표100쌍 중 유턴 누락2쌍을 회피하는 경로로 수정했고, 자동차·택시 판정4/4에도 새 경로가 전달됐습니다. 신규17/17·관련56/56통과, 제한API0·실주행0·운영 배포0입니다. '
 '적용 관계 비율은 전체 준비도가 아니며 복잡한 제약1,552관계와21기능 전체 검증은 남습니다. '
 '[수정·검증 보고서](../records/reports/2026-10-11_1525_차량유턴금지_2219개_탐색적용.md) · '
 '[전후 그림](../records/reports/assets/2026-10-11_same_way_uturn/uturn-before-after-v1.png).\n\n')
wiki.write_text(text[:pos]+summary+text[pos:],encoding='utf8')
text=debug.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-11, 단일 방향 범위)',1)
text+='\n검증: 신규17/17·관련56/56통과, 실제 그래프2,219/2,219차단·다른 진출4,526/4,526보존, 개발100쌍 중 누락2쌍→0쌍. '
text+='[결과 보고서](../2026-10-11_1525_차량유턴금지_2219개_탐색적용.md)와 [증거](../../evidence/2026-10-11_1515_단일방향_유턴금지/)에 명령·원문·해시를 보존했습니다. 모호한 동일 도로5관계 및 다른 복잡한 제약은 해결 범위 밖으로 남습니다.\n'
debug.write_text(text,encoding='utf8')
with data_report.open('a',encoding='utf8') as f:f.write('\n## 단일 방향 유턴 금지 추가 적용 (2026-10-11)\n\n'
 '기존 도로 노드·간선과 추출 원문은 보존하고 회전 자료만 백업 후 원자 교체했습니다. 동일 도로의 단일 역방향 no_u_turn 2,219관계를 추가해 적용4,706/6,258관계, 미적용1,552관계입니다. 원문 기준일2026-10-03T20:20:50Z·ODbL 출처는 같습니다. 기존 단순2,487관계 보존·실제도로ID/교차로ID2,219/2,219대조·개발100쌍 중 유턴 누락2쌍→0쌍·제품4/4연결입니다. 실제 법규 완전성·실주행·운영 배포를 확인하지 않았습니다. '
 '[결과·백업·해시](../../final_project_cs/wiki/records/reports/2026-10-11_1525_차량유턴금지_2219개_탐색적용.md).\n')
reproduction=ev/'reproduction';reproduction.mkdir(exist_ok=False)
for name in ('prepare_uturn_20261011.py','audit_uturn_20261011.py','test_uturn_related_20261011.py',
             'replay_uturn_product_20261011.py','check_uturn_scope_20261011.py','render_uturn_20261011.py','publish_uturn_20261011.py'):
    shutil.copy2(root/'.tmp/mobility_complete_20261008'/name,reproduction/name)
script=repo/'scripts/mobility/build_car_turn_policy_v1.py'
original=script.parent/'_backup/2026-10-11_1515_単一方向ユータン'/script.name
diff=''.join(difflib.unified_diff(original.read_text(encoding='utf8').splitlines(True),script.read_text(encoding='utf8').splitlines(True),fromfile='before/build_car_turn_policy_v1.py',tofile='after/build_car_turn_policy_v1.py'))
with (ev/'own-code-diff.patch').open('x',encoding='utf8') as f:f.write(diff)
prior=json.loads((repo/'wiki/records/evidence/2026-10-11_0918_버스접근방향_진단/integrity-final-v2.json').read_text(encoding='utf8'))
sources={path:digest(root/path) for path in prior['source_test_data_hashes']}
for p in (script,repo/'tests/unit/travel/mobility/test_same_way_uturn_policy_v1.py',data_report,
          root/'datasets/mobility/processed/mobility/turn_restrictions_20261008_v1/restrictions-graph-audit.jsonl',
          root/'datasets/mobility/processed/mobility/turn_restrictions_20261008_v1/manifest.json'):
    sources[p.relative_to(root).as_posix()]=digest(p)
changed=[path for path,h in prior['source_test_data_hashes'].items() if sources[path]!=h]
allowed={wiki.relative_to(root).as_posix(),script.relative_to(root).as_posix(),
         'datasets/mobility/processed/mobility/road_graph_v2/turn_restrictions_v1.json',data_report.relative_to(root).as_posix()}
assert set(changed)<=allowed,changed
artifacts={}
for p in [report,debug,*ev.rglob('*'),* (report.parent/'assets/2026-10-11_same_way_uturn').rglob('*')]:
    if p.is_file():artifacts[p.relative_to(root).as_posix()]=digest(p)
manifest={'created_at':datetime.now().astimezone().isoformat(),'source_test_data_hashes':sources,
          'artifact_hashes':artifacts,'changed_from_previous_manifest':changed,
          'tests':{'new_passed':17,'related_passed':56,'related_total':56,'deselected':2},'limited_api_calls':0}
with (ev/'integrity-final-v1.json').open('x',encoding='utf8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2)
print(json.dumps({'sources':len(sources),'artifacts':len(artifacts),'changed':changed},ensure_ascii=True))
