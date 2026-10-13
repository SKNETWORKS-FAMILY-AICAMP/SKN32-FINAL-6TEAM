from pathlib import Path
from datetime import datetime
from collections import Counter
from html import escape
import difflib
import hashlib
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT / 'final_project_cs'
SCRATCH = Path(__file__).parent
STATE = json.loads((SCRATCH / 'subway-train-identity-work-v1.json').read_text(encoding='utf8'))
EV = ROOT / STATE['evidence']
NOW = datetime.now().astimezone()
STAMP = NOW.strftime('%Y-%m-%d_%H%M%S')
REPORT = CS / 'wiki/records/reports' / (NOW.strftime('%Y-%m-%d_%H%M') + '_지하철_문자열열차번호_두단계_복구검증.md')
ASSETS = CS / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v44'
PRIOR = CS / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v43'
WIKI = CS / 'wiki/teams/mobility.md'
DEBUG = ROOT / STATE['debug']
DATA_REPORT = ROOT / 'datasets/mobility/REPORT.md'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: p.relative_to(ROOT).as_posix()
link = lambda source, dest: Path(os.path.relpath(dest, source.parent)).as_posix()


def save(path, value):
    with path.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


backups = list(STATE['backups'])


def backup(path):
    dst = path.parent / '_backup' / (STAMP + '_문자열차번호_결과기록전') / path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(path, dst)
    backups.append({'source': rel(path), 'backup': rel(dst), 'sha256': sha(dst)})
    return sha(path)


owned = [CS / x for x in (
    'app/domains/travel_ops/ports/data_sources/subway_boarding.py',
    'app/domains/travel_ops/instances/mobility/engine/subway_departure.py',
    'app/domains/travel_ops/ports/subway_train_identity.py',
    'tests/unit/travel/test_subway_train_identity_v1.py')]
hashes = dict(STATE['source_test_data_hashes'])
for name, digest in hashes.items():
    if name not in {rel(x) for x in owned}:
        assert sha(ROOT / name) == digest, ('다른 작업 변경 발견', name)
for path in owned:
    hashes[rel(path)] = sha(path)
assert len(hashes) == 259
before = ET.parse(EV / 'before-v1.xml').getroot()
after = ET.parse(EV / 'after-v3.xml').getroot()
assert len(before.findall('.//testcase')) == 28 and len(before.findall('.//failure')) == 11
assert len(after.findall('.//testcase')) == 337 and not after.findall('.//failure') and not after.findall('.//error')
assert json.loads((EV / 'after-run-v3.json').read_text(encoding='utf8'))['exit_code'] == 0
new_cases = [x for x in after.findall('.//testcase') if 'test_subway_train_identity_v1' in x.attrib.get('classname', '')]
assert len(new_cases) == 28
assert 'All checks passed!' in (EV / 'ruff-v1.log').read_text(encoding='utf8')
live = json.loads((EV / 'live-source-retry-v2.json').read_text(encoding='utf8'))
failed = json.loads((EV / 'live-source-v1.json').read_text(encoding='utf8'))
assert failed['actual_http_responses'] == 0
assert live['actual_http_responses'] == 1 and live['raw_rows'] == 18 and live['letter_number_rows'] == 6
assert live['number_validation_before'] == 0 and live['number_validation_after'] == 6
assert not live['native_callback_identity_match']
raw_path = ROOT / live['raw_path']
assert sha(raw_path) == live['raw_sha256']
actual_letters = [x for x in live['snapshot']['trains'] if any(c.isalpha() for c in x['train_number'])]
save(EV / 'actual-source-assessment-v1.json', {
    'created_at': NOW.isoformat(), 'request_attempts': 2, 'actual_responses': 1,
    'source': '서울특별시 OA-12764', 'response_rows': 18, 'response_total': 18,
    'letter_train_numbers': [{k: r.get(k) for k in ('train_number', 'direction', 'terminal_station_id',
        'terminal_station', 'arrival_code', 'eta_seconds', 'received_age_seconds', 'train_status')} for r in actual_letters],
    'number_format_acceptance': {'before': 0, 'after': 6, 'denominator': 6},
    'native_services': 12, 'native_selection_status': live['selection']['status'],
    'actual_live_boarding_connection_confirmed': False,
    'all_letter_rows_zero_eta': all(r['eta_seconds'] == 0 for r in actual_letters),
    'selection_exclusions': live['selection']['excluded'],
    'actual_eta_accuracy_samples': 0, 'actual_boardings': 0, 'new_map_web_samples': 0,
    'map_developer_api_calls': 0,
    'correction_to_collector_claim': '최초 live-source-v1.json의 고정 claim 문장은 실응답1개라고 쓰지만 실제0응답입니다. 계수·실패 기록을 우선하며 성공은retry-v2의1응답뿐입니다.',
    'limit': '형식 수용6/6은 선택 성공률이 아닙니다. 전6행이service_path_mismatch이고ETA0입니다. 제공 종착·방향 대응과 별도의 신선한 탑승 가능 응답 검증이 필요합니다.'})
save(EV / 'research-v1.json', {'checked_at': NOW.isoformat(), 'cutoff': '2026-10-09',
    'sources': [{'url': 'https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A',
        'finding': 'btrainNo는 운행 열차번호이고 btrainSttus는 별도 열차종류입니다. 역ID와 다른 필드이며 공식 문서와 실제 A번호를 대조했습니다.',
        'applicability': '역의 숫자ID 검사를 열차번호에 재사용하지 않고 원번호를 보존합니다. 접두사로 운영사·급행을 추정하지 않습니다.'}],
    'method': '예측 알고리즘 대신 입력 식별 계약을 수정합니다. 논문 계수·속도 보정·지도값 맞추기는 적용하지 않습니다.'})
for p in owned[:2]:
    old = ROOT / next(x['backup'] for x in backups if x['source'] == rel(p))
    diff = ''.join(difflib.unified_diff(old.read_text(encoding='utf8').splitlines(True),
        p.read_text(encoding='utf8').splitlines(True), fromfile='before/' + rel(p), tofile='after/' + rel(p)))
    with (EV / (p.stem + '-diff-v1.patch')).open('x', encoding='utf8') as f:
        f.write(diff)
test_backup = json.loads((EV / 'after-run-v1.json').read_text(encoding='utf8'))['test_description_backup']
for src, dst in [(owned[3], ROOT / test_backup),
    (SCRATCH / 'collect_subway_train_identity_v1.py', SCRATCH / '_backup/2026-10-09_123326_수집재시도_이름분리전/collect_subway_train_identity_v1.py')]:
    assert dst.is_file()
    backups.append({'source': rel(src), 'backup': rel(dst), 'sha256': sha(dst)})
assert not ASSETS.exists() and not REPORT.exists()
ASSETS.mkdir()
catalog = json.loads((PRIOR / 'readiness-catalog.json').read_text(encoding='utf8'))
for f in catalog['features']:
    if '실시간' in f['name']:
        f['prior_need_v43'] = f['need']
        f['need'] = 'v44: 숫자 역ID 검사를 열차번호에 재사용하던 두 단계를 수정. 신규28/28·관련337/337 통과. 새 공덕 응답1개18행 중 문자번호6개는 형식 판정0/6→6/6이지만 요청 경로 선택0개입니다. 6개 모두 ETA0이고 경로 조건 불일치로 제외됐습니다. 실제 출발 안내 성공·실제ETA정확도·탑승은 미확인입니다. 공항철도 일반/급행의 공식 방향·종착/경유 조건을 대조하고 별도 신선 응답으로 실제 제품 연결을 확인해야 합니다. 후속 환승은 모델 계산입니다.'
        f['train_number_evidence_v44'] = {'new_tests': 28, 'related_tests': 337, 'real_responses': 1,
            'raw_rows': 18, 'letter_rows': 6, 'format_before': 0, 'format_after': 6,
            'native_callback_connected': False, 'actual_eta_error_samples': 0}
catalog.update(created_at=NOW.isoformat(), scope='문자 포함 열차번호의 두 단계 누락 수정과 실제 응답의 선택 한계',
               prior_catalog_sha256=sha(PRIOR / 'readiness-catalog.json'), full_feature_completion=False)
assert len(catalog['features']) == 21
assert dict(Counter(x['status'] for x in catalog['features'])) == {'조건부 사용': 3, '개선 필요': 9, '추가 검증': 9}
save(ASSETS / 'readiness-catalog.json', catalog)
report_text = f'''# 문자 포함 지하철 열차번호의 선택·출발 대조 복구

문자가 붙은 열차번호를 버리던 두 단계를 수정했습니다. 통제 시험에서 도착 목록부터 출발 안내까지 번호가 보존되지만, 새 실제 공덕 응답으로 요청한 공항철도 경로의 실시간 안내 성공은 확인하지 못했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 새 결함·보존 조건 시험 | 통과 | 28/28 = 100% |
| 관련 회귀 시험 | 통과 | 337/337 = 100% |
| 목표 새 실제 응답 | 확보 | 1/1 = 100% |
| 실제 요청 경로의 선택·대조 확인 | 미확인 | 0/1 = 0% |

생성시각 {NOW.isoformat()}. 분모28은 이번 통제 시험 건수이고337에는28이 포함됩니다. 마지막1은 이번 공덕→홍대입구 조사 경로 하나이며 서울 전체 성공률이 아닙니다. 전체21개 기능 분류는 조건부3/21·개선9/21·추가검증9/21로 유지합니다. 완료율이 아닙니다.

## 원인과 바뀐 동작

서울시 [공식 응답 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)의 열차번호와 역ID는 다른 필드입니다. 기존 코드는 숫자 역ID 검사를 열차 중복 집계·승차 선택과 출발 콜백 대조에도 적용했습니다. 원자료에 있는 A2099 같은 번호를 탈 수 있는 조건에서도 거부하는 결함을 재현했습니다.

두 소비 지점이 공유하는 순수 입력 검사에서 ASCII 영숫자 문자열을 원문 그대로 받습니다. 숫자가 적어도 하나 있어야 하고 전부0인 번호는 거부합니다. 접두사·선행0·대소문자를 바꾸지 않으며 번호로 운영사나 급행을 추정하지 않습니다. 역ID 숫자 검사·중복번호 제외·일반열차 조건·노선/종착/경유 대응·응답 완전성·신선도 조건은 유지했습니다. 특정 A번호 목록이나 제공처 수치에 맞춘 보정값은 넣지 않았습니다. 예측 알고리즘의 결함이 아니라 입력 계약의 오류이므로 공식 문서와 실제 원문을 적용 근거로 삼았습니다.

변경: [승차 선택]({link(REPORT, owned[0])}), [출발 대조]({link(REPORT, owned[1])}), [공유 번호 검사]({link(REPORT, owned[2])}), [통제 시험]({link(REPORT, owned[3])}). 코드 두 파일의 전후 차이는 [검증 폴더]({link(REPORT, EV)}/)에 보존했습니다. 공개 고객 응답 계약은 바꾸지 않았습니다.

## 시험 근거와 실행 오류 기록

같은 신규28건은 수정 전11실패·17통과, 수정 후28통과입니다. 6개 번호 보존·15개 잘못된 입력 제외·중복/접두사 구분·역ID/급행 보존·두 출발 관측·원문 정규화/선택·출발 안내를 확인했습니다. A2099를 5호선 통제 입력에 넣은 시험은 실제 공항철도 운행이나 탑승 자료가 아닙니다. 주입한 HTTP transport를 사용한 소스 시험도 실제 호출이 아닙니다.

첫 관련 명령은 존재하지 않는 시험 경로를 지정해0건 실행(exit4)했습니다. 실제 파일 목록으로 고친 다음330통과·임시 폴더 생성 오류7건이 발생했습니다. 공유 폴더를 지우지 않고 이 작업의 새 basetemp 경로를 지정한 최종 실행은337/337 통과(exit0)입니다. 종료 후 콘솔 라이브러리의 WinError 출력은 로그에 남았으며 pytest 실패는 아닙니다. Ruff4파일 통과. 실행 명령·XML·실패 로그를 삭제하지 않았습니다.

## 새 실제 자료와 확인 한계

{live['started_at']}~{live['finished_at']} 서울시 무료 지하철 API를 공덕역에 조회했습니다. 전체 시도2회 중 처음은 연결 실패로 응답0개, 재시도는HTTP200·INFO-000 응답1개·18/18행입니다. 최초 수집 메타의 고정 claim 문장에는 응답1개라고 적혀 있지만 실제 계수0과 실패 기록이 맞습니다. 이 불일치를 새 [판정 기록]({link(REPORT, EV / 'actual-source-assessment-v1.json')})에 명시하고 원본은 보존했습니다. 인증키와 인증 URL은 기록하지 않았고 원문에 키 반사가 없는지 검사했습니다.

문자번호6개 중 일반3개·급행3개입니다. 번호 형식 수용만0/6→6/6으로 바뀌었고 열차 선택 성공률이 아닙니다. 실제 일반번호는 A3013·A2106·A3014이며6개 모두ETA0입니다. 12개 정적 운행 조합과 대조했을 때 문자번호6개는 service_path_mismatch, 다른12개 행은 다른 노선/역 식별로 제외돼 선택0개입니다. 일부 행은 이미 출발했고 오래된 제공 시각도 있습니다. 번호 수용만으로 이미 떠난 열차를 탈 수 있게 처리하지 않았습니다. 이 결과만으로 정적 경로가 틀렸다거나 모든 공항철도 경로가 없다고 단정하지 않습니다.

원문 SHA256 `{live['raw_sha256']}`. [실제 원문·수집정보]({link(REPORT, raw_path.parent)}/)와 [실패 시도 기록]({link(REPORT, ROOT / 'datasets/mobility/raw' / STATE['tag'])}/)은 git 제외 자료입니다. 출처 서울특별시 OA-12764. 새 지도 웹 경로0·지도 개발자 API0회·실제 ETA오차/탑승/결제0개입니다. 통제 시험을 독립 검증으로 부르지 않습니다.

mock 서버 시험(화면 반응): 이번 턴 안 했음.

실서버 확인(서버 응답): 서울시 무료 지하철 도착 API 응답1회 확인. cs 프로젝트 서버HTTP·실제 출발 알림 배달·배포 확인은 안 했음.

## 제품 경로·대체·다음 검증

제품 출발 관측→공식 역ID/정적 운행 조건→소스의 승차 선택→출발 대조→안내 경로의 두 번호 검사 결함을 제거했습니다. 소스 실패·적합 차량 없음은 기존 시각표 모델로 대체하고 근거가 둘 다 실패하면 기존 치명 결함 처리입니다. 보관30초·제공시각90초·미래2초는 신선도 정책이며 ETA 허용 오차나 실제 정확도 보장이 아닙니다. 첫 일반·비순환 열차 범위와 이후 환승 모델 계산의 제한은 남았습니다.

다음 최소 단위는 공덕의 공식 방향/종착ID/경유ID와 정적 운행 조합을 원문으로 대조하고, 접근 후 실제 탑승 가능한 새 응답을 제품 출발 관측기에서 확인하는 일입니다. 경로가 안 맞는 이유와 신선도/이미 출발 조건을 구분합니다. 급행/순환·이름 미대응180역·혼합 운임/누락 경로·1.2km 안 동일 출입점 웹 대조·실제 ETA/탑승 확인은 별도 미완료입니다.

[새21개 기능 시각화]({link(REPORT, ASSETS / 'mobility-readiness.html')})와 [이동 정본]({link(REPORT, WIKI)})에 연결합니다. 기존v43·기존 보고서를 덮어쓰지 않았습니다. [백업 명세]({link(REPORT, EV / 'backup-manifest-v1.json')})에 변경 전 코드·문서·스크립트를 보존합니다. 브라우저 렌더링은 확인하지 못했으며 HTML 내용·링크·JS 구문만 검사합니다. 커밋·푸시·배포·외부 메시지 전송을 수행하지 않았습니다.
'''
with REPORT.open('x', encoding='utf8') as f:
    f.write(report_text)
for p, addition in [(WIKI, f'''\n\n## {NOW.strftime('%Y-%m-%d_%H%M')} 문자 포함 열차번호의 두 단계 복구 결과

공식 응답의 열차번호에 역ID 숫자 검사를 재사용하던 선택·출발 대조를 공통 순수 입력 계약으로 수정했습니다. 신규28/28·관련337/337·Ruff4파일 통과. 수정 전 신규11실패·17통과이며 접두사/선행0/대소문자를 그대로 보존하고 역ID·중복·급행·시각·경유 검사를 유지합니다.

공덕 실제 응답1개18행 중 문자번호6개 형식 수용0/6→6/6. 이는 선택 성공률이 아닙니다. 6개 모두ETA0·경로 조건 불일치로 제외돼 공덕→홍대입구 실제 선택/콜백 연결0/1입니다. 호출 시도2회 중 응답1회이며 실제ETA오차/탑승·새웹경로0·지도개발자API0. 후속 환승은 모델 계산이고 전21개 분류3/9/9 유지·전체 미완료입니다. 다음은 공식 방향/종착/경유와 정적 운행 조합의 대조 및 신선한 실제 적합 열차 응답을 제품 관측기에서 확인합니다. [보고서]({link(WIKI, REPORT)})·[검증 원문]({link(WIKI, EV)}/)·[시각화v44]({link(WIKI, ASSETS / 'mobility-readiness.html')}).
'''), (DATA_REPORT, f'''\n\n## {NOW.strftime('%Y-%m-%d_%H%M')} 공덕 문자 포함 열차번호 실제 응답

[새 원문·수집정보]({link(DATA_REPORT, raw_path.parent)}/)는 {live['started_at']} 서울시 OA-12764 HTTP200·INFO-000 1응답18/18행입니다. 출처 서울특별시. 문자번호6개(일반3/급행3) 원문 SHA256 `{live['raw_sha256']}`. 인증키 반사 검사·키/인증URL 비저장. 앞선 [실패 시도]({link(DATA_REPORT, ROOT / 'datasets/mobility/raw' / STATE['tag'])}/)는0응답이며 고정claim문장보다 계수/실패 기록이 맞습니다.

형식 수용0/6→6/6은 경로 선택 성공률이 아니며6개 모두ETA0·운행 경로 조건 불일치로 제외됐습니다. 공덕→홍대입구 적합 선택/대조0/1. 접근2분 통제·실제ETA오차/탑승/결제/새지도웹0·지도개발자API0. 원자료는 git 제외 증거이며 운영 적재물이 아닙니다. [보고서]({link(DATA_REPORT, REPORT)})에337/337시험·정적경로12조합·다음 대조 범위를 기록합니다.
''')]:
    expected = backup(p)
    original = p.read_text(encoding='utf8')
    assert sha(p) == expected
    p.write_text(original + addition, encoding='utf8')
expected = backup(DEBUG)
old_debug = DEBUG.read_text(encoding='utf8')
assert sha(DEBUG) == expected
DEBUG.write_text(f'''# 문자 포함 열차번호의 선택·출발 대조 제외

## 해결됨 (부분, {NOW.isoformat()})

번호 계약 결함은 신규28/28·관련337/337로 해결했습니다. 두 소비 지점에서 숫자 역ID 검사 대신 원문 영숫자 열차번호 검사를 공유합니다. 급행/역ID/중복/경로/신선도 조건을 유지했습니다. 새 공덕 실응답18행 중 문자번호6개를 형식상 수용하지만6개 모두ETA0·경로 불일치로 실제 요청 방향의 선택0개입니다. 실시간 공항철도 출발 안내/실탑승 검증은 미해결입니다. [보고서]({link(DEBUG, REPORT)})·[검증 원문]({link(DEBUG, EV)}/).

발견 시점 기록(수정 전):

{old_debug.replace('## 미해결', '발견 당시 상태: 미해결')}
''', encoding='utf8')
save(EV / 'backup-manifest-v1.json', {'created_at': NOW.isoformat(), 'backups': backups})
assert all(sha(ROOT / x['backup']) == x['sha256'] for x in backups)
cards = ''.join(f'<article data-status="{escape(x["status"])}"><p class="tag">{escape(x["status"])}</p><h3>{escape(x["name"])}</h3><p>{escape(x["scope"])}</p><p>{escape(x["metric"])}</p><details><summary>근거와 남은 검증 보기</summary><p>{escape(x["reason"])}</p><p>{escape(x["need"])}</p></details></article>' for x in catalog['features'])
page = f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v44 — 열차번호 보존</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f7fa;color:#193a56;font-family:'Malgun Gothic',sans-serif;line-height:1.65}}main{{max-width:1140px;margin:auto;padding:40px 24px}}h1{{font-size:32px;line-height:1.3}}.lead{{font-size:20px}}article,.notice{{padding:20px;background:white;border:1px solid #d7e0e8;border-radius:8px}}.notice{{border-left:5px solid #a05a00}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:20px 0}}.tag,a,summary{{color:#126b67}}select{{font:inherit;padding:10px;max-width:100%}}label{{display:block}}summary{{cursor:pointer}}[hidden]{{display:none!important}}table{{border-collapse:collapse;width:100%;margin:20px 0}}th,td{{padding:12px;text-align:left;border-bottom:1px solid #d7e0e8}}svg{{width:100%;height:auto}}@media(max-width:650px){{.grid{{grid-template-columns:1fr}}main{{padding:24px 16px}}h1{{font-size:26px}}}}
</style><main><p>triPilot / 서울 이동 / v44 / {NOW.isoformat()}</p><h1>문자가 붙은 열차번호를 두 단계에서 보존합니다</h1><p class="lead">통제 시험의 출발 안내는 복구했습니다. 새 실제 응답에서 해당 경로의 승차 연결은 아직 확인하지 못했습니다.</p><div class="notice">번호 형식 수용 0/6 → 6/6은 실제 승차 성공률이 아닙니다. 요청 경로와 맞는 선택은 0개였습니다.</div>
<table><thead><tr><th>확인</th><th>이번 결과</th><th>의미</th></tr></thead><tbody><tr><td>신규 통제 시험</td><td>28/28 통과</td><td>번호·제외 조건·안내</td></tr><tr><td>관련 시험</td><td>337/337 통과</td><td>28건 포함 · 실제 정확도 아님</td></tr><tr><td>새 실제 응답</td><td>1개 · 18행</td><td>공덕 · 문자번호6개</td></tr><tr><td>실제 경로 연결</td><td>0/1 확인</td><td>ETA0·경로 조건 불일치</td></tr></tbody></table>
<svg viewBox="0 0 840 190" role="img" aria-labelledby="flow-title flow-desc"><title id="flow-title">열차번호와 승차 조건의 분리</title><desc id="flow-desc">원번호를 선택과 출발 대조에서 보존하되 노선, 경유, 종류, 시각 조건을 별도로 확인합니다. 실제 적합 응답과 실탑승은 별도 검증입니다.</desc><g font-size="17" fill="#193a56"><rect x="10" y="20" width="245" height="130" fill="#eaf4f1"/><text x="25" y="55">문자 포함 원번호</text><text x="25" y="88">선택 · 출발 대조 보존</text><text x="25" y="121">통제 시험 통과</text><text x="270" y="88">→</text><rect x="300" y="20" width="245" height="130" fill="#eef3f8"/><text x="315" y="55">역 · 노선 · 경유 · 종류</text><text x="315" y="88">도착 시각 · 신선도</text><text x="315" y="121">기존 조건 계속 확인</text><text x="560" y="88">→</text><rect x="590" y="20" width="240" height="130" fill="#fff1da"/><text x="605" y="55">새 적합 응답으로 확인</text><text x="605" y="88">이번 실제 선택 0개</text><text x="605" y="121">실제 ETA · 탑승 별도</text></g></svg>
<h2>21개 기능의 현재 분류</h2><p>조건부 사용3/21 · 개선 필요9/21 · 추가 검증9/21. 완료율이 아닙니다. 다른 기능의 비교 수치는 이전 근거이며 이번 재측정이 아닙니다.</p><label for="filter">판정별 보기</label><select id="filter"><option>전체</option><option>조건부 사용</option><option>개선 필요</option><option>추가 검증</option></select><div class="grid">{cards}</div>
<p>실제 ETA오차·탑승·결제0개 / 새 지도 웹 비교0개 / 지도 개발자API0회. 통제 자료는 독립 검증이 아닙니다.</p><p><a href="{link(ASSETS / 'mobility-readiness.html', REPORT)}">이번 보고서 읽기</a> · <a href="{link(ASSETS / 'mobility-readiness.html', EV)}">시험·원문 판정 보기</a> · <a href="readiness-catalog.json">21개 기능 근거 보기</a> · <a href="{link(ASSETS / 'mobility-readiness.html', EV / 'backup-manifest-v1.json')}">백업 보기</a></p><p>브라우저 렌더링 미확인. 내용·링크·스크립트 구문 검증 자료입니다.</p></main><script>
document.getElementById('filter').addEventListener('change',function(){{document.querySelectorAll('article[data-status]').forEach(card=>{{card.hidden=this.value!=='전체'&&card.dataset.status!==this.value;}});}});
</script></html>'''
with (ASSETS / 'mobility-readiness.html').open('x', encoding='utf8') as f:
    f.write(page)
assert len(re.findall('<article data-status=', page)) == 21
checked_links = []
for href in re.findall('href="([^"]+)"', page):
    target = (ASSETS / href).resolve()
    assert target.exists(), href
    checked_links.append(href)
with (EV / 'visual-script-v1.js').open('x', encoding='utf8') as f:
    f.write(re.search('<script>(.*?)</script>', page, re.S).group(1))
save(EV / 'visual-static-validation-v1.json', {'created_at': NOW.isoformat(), 'cards': 21,
    'counts': catalog['counts'], 'local_links': checked_links, 'browser_render_checked': False,
    'js_syntax_checked': False, 'next_step': 'node --check visual-script-v1.js를 별도로 실행'})
for folder in (raw_path.parent, ROOT / 'datasets/mobility/raw' / STATE['tag']):
    for p in folder.iterdir():
        if p.is_file(): hashes[rel(p)] = sha(p)
assert all(sha(ROOT / p) == h for p, h in hashes.items())
save(EV / 'verification-proof-v1.json', {'created_at': NOW.isoformat(),
    'source_test_data_hashes': hashes, 'source_hash_matches': len(hashes),
    'owned_sources': [rel(x) for x in owned], 'new_tests': 28, 'related_tests': 337,
    'new_actual_responses': 1, 'actual_eta_accuracy_samples': 0,
    'native_callback_connected': False, 'feature_count': 21, 'counts': catalog['counts'],
    'full_feature_completion': False})
shutil.copy2(Path(__file__), EV / Path(__file__).name)
save(SCRATCH / 'subway-train-identity-published-v1.json', {'report': rel(REPORT),
    'assets': rel(ASSETS), 'evidence': rel(EV), 'source_test_data_hashes': hashes,
    'backups': backups, 'created_at': NOW.isoformat()})
print(json.dumps({'report': rel(REPORT), 'assets': rel(ASSETS), 'evidence': rel(EV),
    'tests': 337, 'new_tests': 28, 'hashes': len(hashes), 'backups': len(backups)}, ensure_ascii=False))
