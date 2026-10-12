from pathlib import Path
from datetime import datetime
from collections import Counter
import hashlib, html, json, os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
CS = ROOT/'final_project_cs'
sys.stdout.reconfigure(encoding='utf8')
TAG = '2026-10-10_1521_동일요청좌표_도보웹대조'
EV = CS/'wiki/records/evidence'/TAG
RAW = ROOT/'datasets/mobility/raw'/TAG
ASSETS = CS/'wiki/records/reports/assets/2026-10-10_mobility_readiness_v53'
REPORT = CS/'wiki/records/reports'/f'{TAG}.md'
BASE = json.loads((EV/'baseline-v1.json').read_text(encoding='utf8'))['hashes']

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rel(p):
    return p.relative_to(ROOT).as_posix()

def write(p, text):
    with p.open('x', encoding='utf8') as f:
        f.write(text)

def save(p, obj):
    write(p, json.dumps(obj, ensure_ascii=False, indent=2))

assert all(sha(ROOT/k)==v for k,v in BASE.items())
data = json.loads((EV/'product-replay-v1.json').read_text(encoding='utf8'))
assert data['product']=={'status':'available','m':743,'min':12}
assert data['blocked_network_attempts']==0
files = ['test_walk_comparison_scope_v1.py', 'test_walk_comparison_values_v1.py', 'test_walk_duration_contract_v1.py']
command = [sys.executable,'-m','pytest', *['tests/unit/travel/mobility/'+f for f in files],'-q','-p','no:cacheprovider',f'--junitxml={EV/"walk-contract-v1.xml"}',f'--basetemp={ROOT/".tmp/mobility_complete_20261008/walk_web_pytest_v1"}']
p = subprocess.run(command,cwd=CS,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf8',errors='replace')
write(EV/'walk-contract-v1.log',p.stdout+'\n'+p.stderr)
save(EV/'walk-contract-run-v1.json',{'command':command,'exit_code':p.returncode,'finished_at':datetime.now().astimezone().isoformat()})
assert p.returncode==0, p.stdout[-2000:]
import xml.etree.ElementTree as ET
suite = ET.parse(EV/'walk-contract-v1.xml').getroot()
cases = list(suite.iter('testcase'))
assert cases and not list(suite.iter('failure')) and not list(suite.iter('error'))
tests = len(cases)
save(EV/'runner-recovery-v1.json',{'first_attempt':'검증 스크립트가 입력 폴더에 불필요한 mobility 하위 폴더를 붙여 필수6자료 적재 전에 중단했습니다.', 'corrected_data_dir':'datasets/mobility/processed','product_code_changed':False,'limited_api_calls':0})
write(RAW/'REPORT.md',f'''# 동일 요청 좌표 도보 개발 대조 — 2026-10-10

공개 지도 화면의 거리·시간 사실과 공항철도 표시 계약 조사입니다. 사용자 현재 위치·개인 자료가 아닌 서울 공개 기준점입니다. 사진·지도 타일·소개글·전체 HTML을 보관하지 않았습니다.

- [웹 사실값](web-facts-v1.json): 카카오 도보 동일 요청 좌표 1쌍, 기본 큰길우선/최단거리/편안한길. 구글 도보 미제공·네이버 POI 전환은 제외합니다.
- [공항철도 조사](arex-assessment-v1.json): 공덕 표시 10행, 공개 inline 코드의 5초 갱신과 선택 역 검사 부재. 응답 원문 전체·숨은 필드는 조사하지 않았습니다.
- [제품 재생](../../../../final_project_cs/wiki/records/evidence/{TAG}/product-replay-v1.json): 직선 498.13m, 제품 도보 제공. 요청 좌표 일치와 실제 선택 경로/출입점 일치는 구분합니다.

제품 계산 전 최단거리 기준을 고정했습니다. 거리 허용 차이 ±10%, 시간 ±5분은 기존 개발 비교 기준이며 실제 이용 보장이나 독립 검증 기준이 아닙니다. 실제 도보·탑승·결제 측정은 하지 않았습니다.
지도 개발자 API 호출 0회. 공유 사용량·잔여량·갱신 시각은 미확인이므로 제한 API를 호출하지 않았습니다. API 일일 예비량 최소20% 규칙을 유지합니다.
''')
ASSETS.mkdir(exist_ok=False)
previous = CS/'wiki/records/reports/assets/2026-10-10_mobility_readiness_v52/readiness-catalog.json'
catalog = json.loads(previous.read_text(encoding='utf8'))
assert len(catalog['features'])==21
assert dict(Counter(f['status'] for f in catalog['features']))==catalog['counts']
catalog['created_at']=datetime.now().astimezone().isoformat()
catalog['scope']='동일 요청 좌표 도보 새 개발 표본1쌍; 경로·출입점 정렬 및 전체 완료 아님'
catalog['latest_web_development_sample']={'new_pairs':1,'requested_coordinate_alignment':1,'geometry_alignment':0,'distance_within_10_percent_vs_shortest':0,'time_within_5_min_vs_shortest':1,'distance_difference_percent':10.56547619047619,'time_difference_min':1}
for i in (9,10):
    catalog['features'][i]['latest_evidence']='2026-10-10 새 요청좌표 일치 개발1쌍: 최단 대비 거리+10.6%·시간+1분, 거리0/1·시간1/1. 경로/출입점/실제 도보 미확인; 기존 집계와 합산하지 않음.'
save(ASSETS/'readiness-catalog.json',catalog)
rows=''.join('<tr><td>'+html.escape(f['name'])+'</td><td>'+html.escape(f['status'])+'</td></tr>' for f in catalog['features'])
write(ASSETS/'mobility-readiness.html',f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v53</title><style>body{{font:17px/1.7 system-ui;margin:32px auto;padding:0 20px;max-width:920px;color:#182b3a;background:#fafbfc}}table{{width:100%;border-collapse:collapse;margin:20px 0}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #ccd5dc}}strong{{color:#9b3d1c}}a{{color:#135c93}}</style><h1>같은 요청 좌표의 도보 개발 대조</h1><p>새 표본 1쌍. 웹 최단 대비 <strong>거리 +10.6%</strong>, 시간 +1분. 경로·출입점 일치는 미확인입니다.</p><table><tr><th>확인 항목</th><th>이번 결과</th></tr><tr><td>요청 좌표 일치</td><td>1/1 = 100%</td></tr><tr><td>최단 대비 거리 ±10%</td><td>0/1 = 0%</td></tr><tr><td>최단 대비 시간 ±5분</td><td>1/1 = 100%</td></tr><tr><td>기본 큰길우선 대비 거리 ±10%</td><td>1/1 = 100% (+4.5%)</td></tr><tr><td>동일 경로·출입점 확인</td><td>0/1 = 0%</td></tr></table><p>개발 표본이며 독립 정확도 검증·실제 도보 측정이 아닙니다. 기존 표본과 합산하지 않았습니다. 지도 개발자 API 0회, 일일 예비량 최소20% 유지.</p><h2>전체 21개 기능의 기존 분류 유지</h2><p>조건부 사용3 / 개선 필요9 / 추가 검증9. 이 분류는 완료율이 아닙니다.</p><table><tr><th>기능</th><th>분류</th></tr>{rows}</table><p><a href="../../{REPORT.name}">검증 보고서</a> · <a href="readiness-catalog.json">21개 기능 근거 목록</a></p></html>''')
write(REPORT,f'''# 동일 요청 좌표 도보 웹 대조 — 2026-10-10

새 도보 개발 표본 1쌍에서 최단 웹 경로 대비 거리 차이가 +10.6%로 기존 허용 차이 10%를 넘었습니다. 시간 차이는 +1분입니다. 제품 경로를 한 표본에 맞춰 조정하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 최신 코드·시험·자료·산출물 해시 | 일치 | 407/407 = 100% |
| 같은 요청 좌표의 새 도보 웹 대조 | 확보 | 1/1 = 100% |
| 최단 대비 거리 ±10% | 초과 | 0/1 = 0% |
| 최단 대비 시간 ±5분 | 통과 | 1/1 = 100% |
| 공개 도보 옵션 관련 기존 시험 | 통과 | {tests}/{tests} = 100% |

분모는 이번 새 좌표 쌍 1개, 기존 관련 pytest 사례 {tests}개, 직전 보존 명세의 코드·시험·데이터·산출물 407파일입니다. 전체 21개 기능의 완료율이 아닙니다. 21개 분류 조건부 사용3 / 개선 필요9 / 추가 검증9를 유지합니다.

## 비교 조건과 결과

공개 기준점 2곳의 위도·경도를 [카카오 공식 도보 링크 형식](https://apis.map.kakao.com/web/guide/)으로 요청했습니다. 사용자 실제 위치가 아닙니다. 15:16 KST 화면에서 큰길우선·최단거리·편안한길을 보존하고, 제품 실행 전에 기존 대조 규칙인 **최단거리**를 기준으로 정했습니다. 지도 이미지·타일은 보존하지 않았습니다. 좌표와 공급자 쌍별 사실값은 git 밖 [로컬 원자료](../../../../datasets/mobility/raw/{TAG}/web-facts-v1.json)에 있습니다.

직선거리 498.13m로 1.2km 도보 정책 안입니다. 제품 공개 도보 옵션은 743m·12분이며, 원시 계산 진단값을 제품 결과로 대신하지 않았습니다. 최단 대비 +71m/+10.5655%·+1분, 기본 큰길우선 대비 +32m/+4.5007%·0분입니다. 기본 경로와 비교하면 거리 허용 차이 안이지만, 최단 기준의 실패를 기본 기준 통과로 바꿔 세지 않았습니다.

제품 입력은 성인 기본 동행·초행·walk만·2026-10-10 16:00 KST 도착 목표입니다. 계산된 출발 15:38은 이동12분+정책 여유10분을 역산한 모델 결과입니다. 웹은 성인 시속4km 환산이며 출발 시각 입력이 없었습니다. 같은 날짜의 관찰이지 동일 시각의 실제 이동 오차 측정은 아닙니다. 제품 재생에서 외부 연결 시도0회입니다. [제품 응답·비교 원문](../evidence/{TAG}/product-replay-v1.json).

**같은 요청 좌표**는 확인했으나 공급자별 좌표 붙임·출입점·실제 경로 형상은 확인하지 않았습니다. 거리 차이 원인을 도로 누락이나 계산 오류로 확정하지 않았습니다. 구글은 도보 서비스 범위 밖으로 제외했고, 네이버는 이름이 붙은 POI 경로로 바뀌어 좌표 정렬 미확인으로 제외했습니다. 기존 개발 표본 집계와 합산하지 않으며 독립 검증·실제 도보 정확도로 부르지 않습니다. 다음 검증은 같은 출입점/경로 형상 대조와 별도 새 표본 확보입니다.

## 실시간 대체 소스 조사

[공항철도 공식 실시간 화면](https://www.airportrailroad.com/train/normal/live)의 공덕10행과 공개 inline 코드를 확인했습니다. 5초 주기 갱신, 대기분·출발 표시·출발역·남은 역 수를 확인했습니다. 0분과 1개 역 전이 함께 표시되어 0분을 실제 도착으로 판정할 수 없습니다. 렌더링된10행/부모 속성과 해당 공개 코드 범위에서 열차 고유 식별자·예측 생성시각을 확보하지 못했습니다. 원 응답의 숨은 필드는 조사하지 않아 백엔드에 없다고 단정하지 않습니다.

공개 함수는 비동기 응답을 받은 뒤 현재 선택 역 또는 요청 순서를 확인하지 않고 목록을 덮습니다. 이는 응답 역전 시 선택 역과 목록이 달라질 수 있는 코드상 원인 후보입니다. 이번 회차에 응답 역전 횟수를 직접 계측하지 않았으며 외부 사이트 결함을 확정하지 않습니다. 표시 시각의 기준 역 의미와 동일 열차 대응도 미확인이므로 제품 대체 소스로 연결하지 않았습니다. [소스 평가](../../../../datasets/mobility/raw/{TAG}/arex-assessment-v1.json).

## 검증·보존·제한

제품 코드·운영 설정·일정 주기·알림 정책을 바꾸지 않았습니다. 실제 도보·탑승·결제·동일 열차 ETA 오차 측정0쌍입니다. 실행 스크립트의 첫 자료 경로에 불필요한 하위 폴더를 붙여 적재 전에 중단했고, 입력 경로를 고친 별도 실행으로 재개했습니다. 제품 결함으로 세지 않았습니다. [기존 시험 로그](../evidence/{TAG}/walk-contract-v1.log)·[명령](../evidence/{TAG}/walk-contract-run-v1.json).

mock 서버 시험: 안 했음 (화면 반응 미확인).

실서버 확인 (서버 응답): cs 프로젝트 서버 확인 안 했음. 공개 지도·공항철도 웹 화면만 조회했습니다. 배포·커밋·푸시·외부 메시지·결제를 하지 않았습니다.

제한 API 호출0회입니다. 공급자 공유 사용량·잔여량·갱신 시각은 조회 전후 미확인으로 기록하며 0으로 적지 않았습니다. 원자 예산 확보가 불가해 API를 부르지 않았고 일일 예비량 최소20% 규칙을 유지했습니다. 공식 공항철도 폴링 탭은 조사 후 닫았습니다. [일일 소비 기록](../evidence/{TAG}/api-budget-v1.json).

덮어쓰기 전 [이동 wiki 백업](../../teams/_backup/{TAG}/mobility.md)과 [데이터 보고서 백업](../../../../datasets/mobility/_backup/{TAG}/REPORT.md)을 보존했습니다. [최종 해시·보존 검사](../evidence/{TAG}/final-integrity-v1.json)·[시각화 v53](assets/2026-10-10_mobility_readiness_v53/mobility-readiness.html). 새 시각화는 정적 구조/링크를 검사했으며 브라우저 렌더링 시험은 하지 않았습니다.
''')
save(EV/'api-budget-v1.json',{'limited_api_calls':0,'limited_api_retries':0,'minimum_daily_reserve_percent':20,'quota_usage_before':'미확인','quota_usage_after':'미확인','remaining_before':'미확인','remaining_after':'미확인','reset_at':'미확인','reservation':'공유 사용량 미확인으로 API 미호출','official_web_observations_separate':True,'runtime_limits_changed':False})
backups=[]
for path, addition in [
 (CS/'wiki/teams/mobility.md', f'\n\n## 2026-10-10_1521 동일 요청 좌표 도보 웹 대조\n\n새 개발1쌍에서 최단 웹 대비 거리+10.6%(허용±10% 0/1)·시간+1분(±5분 1/1)을 확인했습니다. 같은 요청 좌표이지만 출입점·형상·실제 도보 미확인으로 독립 정확도나 전체 완료 근거가 아닙니다. 공항철도10행/공개코드에서5초갱신·0분과1역전 동시표시·비동기 선택역 재확인 부재를 확인했으나ID/생성시각/응답역전실측은 미확보라 대체연결하지 않았습니다. 제한API0·제품코드/배포변경없음·21분류3/9/9유지. [보고서](../records/reports/{REPORT.name})·[시각화v53](../records/reports/assets/2026-10-10_mobility_readiness_v53/mobility-readiness.html)·[검증](../records/evidence/{TAG}/).\n'),
 (ROOT/'datasets/mobility/REPORT.md',f'\n\n## 2026-10-10 동일 요청 좌표 도보 개발 대조\n\n공개 기준점1쌍의 카카오 요청좌표와 제품 입력을 맞췄습니다. 최단 대비 거리+10.6%·시간+1분, 거리허용0/1·시간허용1/1. 경로 형상·출입점·실제 도보는 미확인이고 기존 집계와 합산하지 않았습니다. 공항철도 공덕10행의 표시/공개 코드 조사도 별도로 보존했습니다. 제한API0회이며 기존 원자료·가공자료를 바꾸지 않았습니다. [새 원자료](raw/{TAG}/REPORT.md)·[검증 보고서](../../final_project_cs/wiki/records/reports/{REPORT.name}).\n')]:
    oldtext=path.read_text(encoding='utf8')
    before=sha(path)
    if rel(path) in BASE:
        assert before==BASE[rel(path)]
    target=path.parent/'_backup'/TAG/path.name
    target.parent.mkdir(parents=True,exist_ok=False)
    shutil.copy2(path,target)
    assert sha(target)==before and sha(path)==before
    path.write_text(oldtext+addition,encoding='utf8')
    backups.append({'source':rel(path),'backup':rel(target),'sha256':before})
for script in ['walk_web_20261010_v1.py','walk_web_retry_20261010_v1.py','publish_walk_web_20261010_v1.py']:
    shutil.copy2(Path(__file__).parent/script, EV/script)
changed=[k for k,v in BASE.items() if sha(ROOT/k)!=v]
assert changed==['final_project_cs/wiki/teams/mobility.md'], changed
assert all(sha(ROOT/b['backup'])==b['sha256'] for b in backups)
from html.parser import HTMLParser
class Links(HTMLParser):
    links=[]
    def handle_starttag(self, tag, attrs):
        if tag=='a':
            self.links.extend(v for k,v in attrs if k=='href')
check=Links();check.feed((ASSETS/'mobility-readiness.html').read_text(encoding='utf8'))
assert all((ASSETS/url).resolve().exists() for url in check.links)
save(EV/'visual-validation-v1.json',{'features':21,'counts':catalog['counts'],'relative_links_checked':len(check.links),'relative_links_valid':len(check.links),'browser_render_verified':False,'javascript_used':False})
source_hashes={k:sha(ROOT/k) for k in BASE}
artifacts={rel(p):sha(p) for folder in (EV,RAW,ASSETS) for p in folder.iterdir() if p.is_file()}
artifacts[rel(REPORT)]=sha(REPORT)
artifacts[rel(ROOT/'datasets/mobility/REPORT.md')]=sha(ROOT/'datasets/mobility/REPORT.md')
save(EV/'final-integrity-v1.json',{'created_at':datetime.now().astimezone().isoformat(),'source_test_data_hashes':source_hashes,'artifact_hashes':artifacts,'baseline_checked':len(BASE),'allowed_changed':changed,'unchanged':len(BASE)-len(changed),'backups':backups,'tests_passed':tests,'full_feature_completion':False})
print(json.dumps({'tests':tests,'preserved':len(BASE)-len(changed),'backups':len(backups),'artifacts':len(artifacts),'report':rel(REPORT)},ensure_ascii=False))
