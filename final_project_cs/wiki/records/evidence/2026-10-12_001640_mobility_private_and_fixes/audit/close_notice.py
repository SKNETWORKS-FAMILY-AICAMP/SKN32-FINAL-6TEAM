from pathlib import Path
import ast
import difflib
import hashlib
import json
import re
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[3]
out = root/'.tmp/mobility_finish_20261011/subway_notice'
source = root/'final_project_cs/app/domains/travel_ops/ports/data_sources/subway_notice.py'
test = root/'final_project_cs/tests/unit/travel/test_subway_notice.py'
new = root/'final_project_cs/tests/unit/travel/test_subway_notice_station_lists_v1.py'
old_source = source.parent/'_backup/2026-10-11_station_list_matching'/source.name
old_test = test.parent/'_backup/2026-10-11_station_list_matching'/test.name

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def summary(path):
    xml = ET.parse(path).getroot()
    suites = list(xml.iter('testsuite'))
    keys = ['tests','errors','failures','skipped']
    d = {k:sum(int(x.attrib.get(k,0)) for x in suites) for k in keys}
    d['passed'] = d['tests']-d['errors']-d['failures']-d['skipped']
    d['testcases'] = [x.attrib['name'] for x in xml.iter('testcase')]
    return d

def matcher(path):
    tree=ast.parse(path.read_text(encoding='utf-8'))
    ns={'re':re}
    functions=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in ['_clean','mentions_station']]
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(path),'exec'),ns)
    return ns['mentions_station']

title='4호선 시위로 혜화, 한성대입구역(하선) 무정차 통과'
before_fn,after_fn=matcher(old_source),matcher(source)
same_conditions=[{'title':title,'station':s,'before':before_fn(title,s),'after':after_fn(title,s)} for s in ['혜화','한성대입구','대방']]
changes=''
for previous,current in [(old_source,source),(old_test,test)]:
    changes += ''.join(difflib.unified_diff(previous.read_text(encoding='utf-8').splitlines(keepends=True),current.read_text(encoding='utf-8').splitlines(keepends=True),fromfile=str(previous.relative_to(root)),tofile=str(current.relative_to(root))))
(out/'source-change.diff').write_text(changes,encoding='utf-8')
record=dict(scope='무정차 다역 공지 파싱 최소 수정. 실제 사건 탐지율·배포 완료 아님',before=summary(out/'before.xml'),after=summary(out/'after.xml'),same_conditions=same_conditions,api_calls=0,external_connection_attempts_before=json.loads((out/'before-run.json').read_text(encoding='utf-8'))['external_connection_attempts'],external_connection_attempts_after=json.loads((out/'after-run.json').read_text(encoding='utf-8'))['external_connection_attempts'],source_evidence={'kind':'과거 조사 보고의 표기와 기존 개발 회귀 문구','report':'final_project_cs/wiki/records/reports/2026-10-04_0400_이동_파이썬_길찾기_서버없이_리포트.md','section':'12-7','raw_provider_response_available':False,'search_scope':'datasets/mobility 및 datasets/travel의 json/jsonl/csv에서 noftTtl, 기록 폴더의 정확 문구 검색. 공식 사이트 웹 검색에서 원문 확보 못함. 보존되지 않은 다른 위치의 자료는 놓칠 수 있음.','caution':'보유 공급자 원응답 재생·새 실제 사건 정답 표본으로 세지 않음'},files={p.relative_to(root).as_posix():sha(p) for p in [source,test,new,old_source,old_test]},deployment_verified=False)
(out/'completion.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
report=f'''# 무정차 다역 공지 누락 수정

쉼표로 역을 나열하고 마지막에만 「역」을 붙인 공지에서 앞 역의 무정차 사건이 누락되던 결함을 수정했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 다역 표기 결함 수정 | 완료 | 1/1 = 100% |
| 신규 단위 조건 | 통과 | 37/37 = 100% |
| 관련 회귀 | 통과 | 85/85 = 100% |

신규37개는85개에 포함되며 더하지 않습니다. 수정 전 동일37조건은16통과·21실패, 수정 후37통과입니다. 관련85개는 신규37개와 기존 무정차·도로 사건·대체 소스·사건 판정48개입니다.

같은 「{title}」에서 혜화는 누락→탐지, 한성대입구는 탐지→탐지이며 관계없는 대방은 계속 제외됩니다. 이는 개발 회귀 문구 재현입니다. 과거10/04 조사 보고12-7에는 「혜화, 한성대입구역」 표기가 기록돼 있지만 공급자 원응답은 이번 검색 범위에서 확보하지 못했습니다. 실제 공지 원응답 재생·새 사건 탐지율로 부르지 않습니다. 통제 시험의 시각·호선·행 구조를 실제 원값이라고 주장하지 않습니다.

전체 역명 경계와 쉼표·가운뎃점·빗금으로 이은 목록만 읽습니다. 관련 없는 자유 문장을 건너뛰지 않으며 역명 일부·「역사/역할」 단어를 제외합니다. 기존 종료 공지의 최신 우선 판정·3시간 창·호선 필터를 유지하고 다역 시작/다역 종료/한 역만 종료/본문 목록을 검사했습니다. 괄호 부역명 생략형·호선 누락·모든 자연어 목록 형태의 복원은 이번 범위 밖입니다.

제품 수정은 subway_notice.py 한 파일, 기존 누락 기대 시험1개, 신규 시험 파일1개입니다. 기존 시험이 잘못된 누락을 계속 기대하므로 이를 양쪽 역 탐지 기대값으로 수정했습니다. 원본은 각각의 `_backup/2026-10-11_station_list_matching/`에 보존했고 [차이](source-change.diff)와 [실행·해시 요약](completion.json)을 남겼습니다. Ruff3파일은 별도 실행에서 통과했습니다.

외부 연결을 차단한 시험에서 연결 시도0회·제한 API0회입니다. 공유 사용량을 확인하지 못해 데이터 호출을 하지 않았습니다. 공식 웹 검색은 했으나 해당 과거 공지 원문을 확보하지 못했습니다. 사용자 영수증·개인 골든셋은 접근하지 않았습니다.

mock 서버 시험(화면 반응): 안 했음. HTTP transport 대역·보유 문구를 사용한 단위 회귀입니다.

실서버 확인(cs 프로젝트 서버 응답): 안 했음. 실제 무정차 발생·탐지율·cs 프로젝트 서버 HTTP·배포·외부 알림 확인은 하지 않았습니다. 커밋·푸시·wiki 수정도 하지 않았습니다.
'''
(out/'REPORT.md').write_text(report,encoding='utf-8')
print(json.dumps({'before':{k:v for k,v in record['before'].items() if k!='testcases'},'after':{k:v for k,v in record['after'].items() if k!='testcases'},'same_conditions':same_conditions},ensure_ascii=False))
