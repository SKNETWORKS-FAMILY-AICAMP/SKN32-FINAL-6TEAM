from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
import difflib

ROOT=Path(__file__).resolve().parents[2]
CS=ROOT/'final_project_cs'
E=CS/'wiki/records/evidence/2026-10-11_2116_departure_time_bounds'
OLD=CS/'wiki/records/evidence/2026-10-11_parallel_sonnet_finish'
stamp=datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d_%H%M%S')
for stage in ('heartbeat-access-before','heartbeat-access-after','heartbeat-access-final'):
    for suffix in ('.log','.xml','-network.json','-run.json'):
        shutil.copy2(OLD/(stage+suffix), E/(stage+suffix))
before=ET.parse(E/'heartbeat-access-before.xml').getroot().find('testsuite')
after=ET.parse(E/'heartbeat-access-final.xml').getroot().find('testsuite')
before_cases={c.get('name'):c for c in before.findall('testcase')}
after_cases={c.get('name'):c for c in after.findall('testcase') if 'test_departure_access_bounds_v1' in c.get('classname','')}
assert len(before_cases)==33 and len(after_cases)==43
assert set(before_cases)<=set(after_cases)
assert all(after_cases[n].find('failure') is None and after_cases[n].find('error') is None for n in before_cases)
assert int(after.get('tests'))==160 and int(after.get('failures'))==int(after.get('errors'))==0
exception_count=sum('OverflowError' in (c.find('failure').get('message','')) for c in before_cases.values() if c.find('failure') is not None)
summary={'same_development_cases':33,'before_passed':18,'before_failed':15,'before_overflow_failures':exception_count,
         'after_same_cases_passed':33,'additional_boundaries_passed':10,'new_test_total':43,
         'related_passed':160,'related_total':160,'skipped':0,'data_api_calls':0,'claude_cli_reviews':1,
         'actual_boarding_payment_samples':0,'deployment':False,'strict_feature_completion':{'passed':0,'total':21}}
(E/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
review=json.loads((E/'claude-review-stdout.json').read_text(encoding='utf8'))
assert review.get('is_error') is False and 'claude-sonnet-5-5' in review.get('modelUsage',{})
(E/'claude-review-readable.md').write_text(review['result'],encoding='utf8')

assets=CS/'wiki/records/reports/assets/2026-10-11_departure_bounds_v57'
assets.mkdir(exist_ok=False)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family']='Malgun Gothic'
fig,ax=plt.subplots(figsize=(10.8,4.2))
fig.patch.set_facecolor('#f7f8fa');ax.set_facecolor('#f7f8fa')
ax.barh([1,0],[18,33],color='#19866e',height=.45,label='통과')
ax.barh([1,0],[15,0],left=[18,33],color='#c75848',height=.45,label='실패')
ax.text(9,1,'18/33 통과',ha='center',va='center',color='white',fontsize=12)
ax.text(25.5,1,'15/33 실패',ha='center',va='center',color='white',fontsize=12)
ax.text(16.5,0,'33/33 통과',ha='center',va='center',color='white',fontsize=12)
ax.set_yticks([1,0],['수정 전','수정 후']);ax.set_xlim(0,33)
ax.set_xticks([0,11,22,33]);ax.set_xlabel('같은 개발 회귀 조건 33개 · 독립 웹/실탑승 검증 아님')
ax.set_title('손상된 접근 시간: 예외 대신 재계획으로 반환',loc='left',fontsize=16,pad=23)
for spine in ax.spines.values():spine.set_visible(False)
ax.tick_params(axis='y',length=0,pad=10)
fig.text(.12,.01,'추가 경계 10/10 · 신규 합계 43/43 · 관련 회귀 160/160 (신규 포함) · 데이터 API 0회',fontsize=10,color='#455268')
fig.tight_layout(rect=(0,.07,1,.96))
fig.savefig(assets/'departure-access-before-after-v1.png',dpi=180,bbox_inches='tight')
plt.close(fig)

backs=json.loads((E/'backups.json').read_text(encoding='utf8'))
source=CS/backs[0]['file'];original=ROOT/backs[0]['backup']
diff=''.join(difflib.unified_diff(original.read_text(encoding='utf8').splitlines(True),source.read_text(encoding='utf8').splitlines(True),fromfile='before/departure_observer.py',tofile='after/departure_observer.py'))
(E/'source-change.diff').write_text(diff,encoding='utf8')
ruff=subprocess.run([r'C:\Users\playdata2\anaconda3\python.exe','-m','ruff','check',backs[0]['file'],'tests/unit/travel/mobility/test_departure_access_bounds_v1.py'],cwd=CS,capture_output=True,text=True)
(E/'ruff.log').write_text(ruff.stdout+ruff.stderr,encoding='utf8');assert ruff.returncode==0

def backup(p):
    b=p.parent/'_backup'/(stamp+'_departure_bounds_result')/p.name
    b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
    return str(b.relative_to(ROOT)).replace('\\','/')
report=CS/'wiki/records/reports'/f'{stamp[:16]}_출발접근시간_범위검사_복구검증.md'
assert not report.exists()
report.write_text(f'''# 출발 접근 시간 범위 검사 복구 검증

잘못 저장된 대중교통 접근 시간이 예외로 안내 호출을 중단하던 결함을 수정했습니다. 손상 문맥은 API 조회 전에 재계획으로 반환하고 다음 정상 안내는 계속 생성합니다. 정상 제품 생성값이 손상됐다는 관측이나 운영 장애 측정은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 접근 시간 결함 수정 | 완료 | 1/1 = 100% |
| 신규 경계 회귀 | 통과 | 43/43 = 100% |
| 출발·안내·감시 관련 회귀 | 통과 | 160/160 = 100% |
| 전체21기능 실사용 기준 충족 | 미충족 | 0/21 = 0% |

신규43개는 관련160개에 포함됩니다. 0/21은 제품 경로·대체 소스·허용 오차·새 표본 검증을 기능별로 모두 확인한 개수이며 코드 구현률이 아닙니다. 앞 회차283개와 중복이 있으므로 더하지 않습니다.

![같은33개 조건 전후](assets/{assets.name}/departure-access-before-after-v1.png)

## 범위와 원인

현재 wiki의 출발 문맥·현재 출발 재검증 계약 안에서 최소 단위로 처리했습니다. 시작 시 앞 회차507개 코드·시험·자료 해시를 다시 읽었습니다. 다른 작업자의6개 변경은 보존했고 소유한 출발 관측 파일1개만 수정했습니다. 저장된 접근 시간은 내부 JSON의 int/float이며 `math.isfinite`만으로 초대형 정수를 검사하면 OverflowError가 나고, 유한한 초대형 실수도 timedelta 변환에서 실패합니다. [Python 공식 datetime 문서](https://docs.python.org/3/library/datetime.html)와 [공식 예외 문서](https://docs.python.org/3.12/library/exceptions.html)의 범위 예외를 확인하고 실제 입력으로 재현했습니다.

각 접근·이탈 시간 및 두 항목의 합을 기존 SERVICE_DAY_MAX_MIN=1800 안에서 먼저 검사합니다. bool·NaN·무한대·음수·초대형 정수/실수·누락은 access_context_invalid로 반환하며 자르기·0 대체를 하지 않습니다. 정상 0·소수 분·상한 값은 유효하고 실제 기한 성립 여부는 기존 판정이 결정합니다. 거리1.2km 정책·공개 계약·운영 서비스 한도는 변경하지 않았습니다.

## 실행 근거

수정 전 신규33조건은18통과·15실패였고, 그중 OverflowError 실패는{exception_count}개였습니다. 15개 전부가 예외라는 뜻은 아닙니다. 수정 후 같은33조건33통과, Sonnet 검토 후 추가한 누락·정확 상한 경계10조건도 통과했습니다. 최종160/160, 실패·오류·skip0입니다. [수정 전 로그](../evidence/{E.name}/heartbeat-access-before.log) · [최종 로그](../evidence/{E.name}/heartbeat-access-final.log) · [XML](../evidence/{E.name}/heartbeat-access-final.xml) · [실행 명령](../evidence/{E.name}/heartbeat-access-final-run.json). 종료 뒤 pyreadline3 정리 경고는 pytest의 성공 종료코드0과 구분합니다. Ruff2파일 통과입니다.

사용자가 승인한12개 파일 중 departure_observer.py 하나의 발췌만 Claude CLI Sonnet5.5에 보냈습니다. 도구·외부 파일 접근을 끄고 모델 응답의 claude-sonnet-5-5를 확인했습니다. 구체 반례를 찾지 못했다는 코드 검토이며 Claude가 시험을 실행했다고 주장하지 않습니다. 검토 제안의 정확 상한·합 상한·누락 시험을 추가했습니다. [검토 원문](../evidence/{E.name}/claude-review-readable.md) · [전송 범위](../evidence/{E.name}/claude-export-manifest.json).

## API 예비량과 한계

지도·공공데이터 API는 호출하지 않았습니다. 공유 누적 사용량·실제 제한 단위·갱신 시각을 이 실행에서 신뢰할 수 있게 확인하지 못했으므로 사용 가능 예산을0으로 취급했습니다. 조회 전후 공급자 누적·잔여·갱신 시각은 미확인이고 이번 데이터 호출0회, 실패·재시도0회입니다. 별도로 승인된 Claude CLI 코드 검토1회는 데이터 수집 호출과 구분합니다. [API 기록](../evidence/{E.name}/api-budget.json).

실제 탑승·결제·배포된 cs 프로젝트 서버 확인은 안 했습니다. mock 서버 화면 시험은 시행하지 않았습니다. 단위·안내 소비 시험은 통제한 개발 자료이며 독립 검증이 아닙니다. 실시간 후속 환승·급행/순환선·복잡한 회전 제약·정렬된 새 웹 표본은 계속 남습니다. 커밋·푸시·배포·외부 메시지는 수행하지 않았습니다.

## 변경과 보존

- [수정 코드](../../../app/domains/travel_ops/instances/mobility/engine/departure_observer.py) — 시간 범위 검사.
- [신규 시험](../../../tests/unit/travel/mobility/test_departure_access_bounds_v1.py) —43조건.
- [검토 가능한 차이](../evidence/{E.name}/source-change.diff).
- [원본 백업 목록](../evidence/{E.name}/backups.json) — 소스·wiki 원본; 코드 원본은 legacy에도 보존.
- [시작 해시](../evidence/{E.name}/start-integrity.json) · [최종 해시](../evidence/{E.name}/final-integrity.json).
''',encoding='utf8')

bug=CS/'wiki/records/reports/debugs/2026-10-11_2116_출발접근시간_범위누락.md'
bug_backup=backup(bug)
bug.write_text(bug.read_text(encoding='utf8').replace('## 미해결','## 해결됨 (2026-10-11)',1)+f'\n검증: 신규43/43·관련160/160. [최종 실행](../../evidence/{E.name}/heartbeat-access-final.log), [수정 결과](../{report.name}).\n',encoding='utf8')
wiki=CS/'wiki/teams/mobility.md'
wiki_backup=backup(wiki)
wiki.write_text(wiki.read_text(encoding='utf8')+f'\n현재 접근 시간의 초대형·누락 값으로 안내 호출이 중단되는 결함을 수정했습니다. 신규43/43·관련160/160 로컬 통과이며 전체 실사용 완료·운영 반영은 아닙니다. [복구 검증 결과](../records/reports/{report.name}).\n',encoding='utf8')
open_items=ROOT/'wiki/delivery/open-items.md'
open_backup=backup(open_items)
open_items.write_text(open_items.read_text(encoding='utf8')+f'\n2026-10-11 추가: 대중교통 출발 접근 시간의 손상값 예외1건을 로컬에서 수정했습니다. 신규43/43·관련160/160(신규 포함) 통과이며 기존 미해결 범위·전체21기능 완료 판정은 유지합니다. [결과](../../final_project_cs/wiki/records/reports/{report.name}).\n',encoding='utf8')
(E/'api-budget.json').write_text(json.dumps({'policy_reserve_fraction':0.2,'provider_usage_before':None,'provider_usage_after':None,'remaining_before':None,'remaining_after':None,'reset_time':None,'data_api_budget_allocated':0,'data_api_calls':0,'failed_calls':0,'retry_calls':0,'reason':'Shared usage and provider daily units/reset clocks unverified; no data API was called','claude_cli_approved_reviews':1},ensure_ascii=False,indent=2),encoding='utf8')
start=json.loads((E/'start-integrity.json').read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
hashes={rel:sha(ROOT/rel) for rel in start['hashes']}
new_test=CS/'tests/unit/travel/mobility/test_departure_access_bounds_v1.py'
hashes[str(new_test.relative_to(ROOT)).replace('\\','/')]=sha(new_test)
deltas=[rel for rel in start['hashes'] if hashes[rel]!=start['hashes'][rel]]
own_rel=str(source.relative_to(ROOT)).replace('\\','/')
assert not any(rel.startswith('datasets/') for rel in deltas)
out={'at':datetime.now(timezone(timedelta(hours=9))).isoformat(),'source_test_data_hashes':hashes,
     'changed_during_turn':deltas,'other_changes_preserved':[r for r in deltas if r!=own_rel],
     'summary':summary,'additional_backups':[bug_backup,wiki_backup,open_backup],
     'artifact_hashes':{str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [report,wiki,bug,open_items,*E.iterdir(),*assets.iterdir()] if p.is_file()}}
(E/'final-integrity.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'report':str(report),'visual':str(assets/'departure-access-before-after-v1.png'),'summary':summary,'changed_during_turn':len(deltas),'other_changes':out['other_changes_preserved']},ensure_ascii=True))
