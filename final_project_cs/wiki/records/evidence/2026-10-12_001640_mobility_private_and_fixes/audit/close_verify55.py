from pathlib import Path
import difflib
import hashlib
import json
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[3]
out=root/'.tmp/mobility_finish_20261011/verify55'
run=json.loads((out/'run.json').read_text(encoding='utf-8'))
source=root/'final_project_cs/tests/unit/travel/mobility/test_verify55_v1.py'
old=source.parent/'_backup/2026-10-12_verify55_offline'/source.name
def summary(path):
    node=ET.parse(path).getroot()
    suites=list(node.iter('testsuite'))
    result={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ['tests','failures','errors','skipped']}
    result['passed']=result['tests']-result['failures']-result['errors']-result['skipped']
    result['cases']=[{'name':c.attrib['name'],'passed':c.find('failure') is None and c.find('error') is None and c.find('skipped') is None} for c in node.iter('testcase')]
    return result
before,after=summary(out/'before-two-targets.xml'),summary(out/'after.xml')
diff=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(keepends=True),source.read_text(encoding='utf-8').splitlines(keepends=True),fromfile=str(old.relative_to(root)),tofile=str(source.relative_to(root))))
(out/'source-change.diff').write_text(diff,encoding='utf-8')
result={'scope':'과거회귀의 환경 의존 초기화를 오프라인 자료로 명시. 제품 계산 불변식 변경 없음','before':before,'after':after,'run':run,'source_before_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'source_after_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'product_code_modified':False,'assertions_weakened':False,'api_calls':0,'original_failed_targets':['test_d_p90_multi_seoul_itaewon','test_d_wondeok_no_yangpyeong_transfer']}
(out/'completion.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
text=f'''# 이전 이동 회귀의 오프라인 초기화 복구

확대 검증에서 실패한 두 시험은 실제 계산 비교에 도달하기 전 외부 라우터 상태 조회가 차단돼 실패했습니다. 시험 초기화에 오프라인 로컬 도로망과 실시간 키 비활성을 명시했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 초기화 원인 확인·수정 | 완료 | 1/1 = 100% |
| 기존 실패 두 조건 | 통과 | {sum(x['passed'] for x in after['cases'] if x['name'] in result['original_failed_targets'])}/2 = {sum(x['passed'] for x in after['cases'] if x['name'] in result['original_failed_targets'])/2:.0%} |
| 같은 파일 전체 회귀 | 실행 결과 | {after['passed']}/{after['tests']} = {after['passed']/after['tests']:.0%} |

원래 build_verifier(quiet=True)는 환경 설정의 GraphHopper /info를 조회했습니다. 네트워크 금지 검증에서 socket 연결 차단에 걸려 p90·동명이역 불변식을 검사하기 전에 실패했습니다. gh_url="", seoul_key="", local_router=True를 명시해 보유 자료만 사용합니다. 이는 제품 라우터 동작 변경이 아니라 시험의 자료·환경 고정입니다.

p90≥평균 ETA와 p90≤최악 ETA, 도보 포함 p90 후보 존재, 양평 동명이역 사이 환승 금지, 실제 이촌 환승 보존, 노선별 물리적 역·출구·동명이역 구간의 기존 기대는 수정하지 않았습니다. 통과만 위해 값을 낮추거나 기대를 삭제하지 않았습니다.

수정 전 두 실패는 부모 확대 실행의 원본 로그/JUnit에서 보존했습니다. before-two-targets.xml은 원본 두 testcase를 그대로 추출한 것이며 새 실행이라고 주장하지 않습니다. 수정 후 전체 파일 {after['tests']}조건 중 통과{after['passed']}·실패{after['failures']}·오류{after['errors']}·skip{after['skipped']}입니다. [원본 확대 로그](before-full-gate-v4.log) · [수정 전 두 조건 XML](before-two-targets.xml) · [수정 후 로그](after.log) · [수정 후 JUnit](after.xml).

시험 전후 자료/규칙과 관련 코드 해시 {len(run['start_hashes'])}개를 비교했습니다. 실행 중 변경 항목은 {run['changed_during_run']}입니다. 이는 전체 저장소 해시 검증이 아니며 대상 자료는 기존 감사의35개 데이터/규칙과 현재 관련5파일입니다. [실행·해시](run.json) · [결과 요약](completion.json) · [수정 차이](source-change.diff).

원본 시험은 [백업](../../../final_project_cs/tests/unit/travel/mobility/_backup/2026-10-12_verify55_offline/test_verify55_v1.py)에 보존했습니다. 제품 소스와 데이터는 수정하지 않았습니다. Ruff 해당 시험1파일은 별도 실행에서 통과했습니다. 외부 연결 차단 아래 시도{run['blocked_connection_attempts']}회·API0회이며 개인자료 접근·외부 송신·커밋·wiki 변경을 하지 않았습니다.

mock 서버 시험(화면 반응): 안 했음.

실서버 확인(cs 프로젝트 서버 응답): 안 했음. 보유 자료의 단위·통합 회귀이며 실제 p90 정확도·실탑승·운영 배포 검증이 아닙니다.
'''
(out/'REPORT.md').write_text(text,encoding='utf-8')
print(json.dumps({'before':{k:v for k,v in before.items() if k!='cases'},'after':{k:v for k,v in after.items() if k!='cases'},'changes_during_test':run['changed_during_run'],'api_calls':0},ensure_ascii=False))
