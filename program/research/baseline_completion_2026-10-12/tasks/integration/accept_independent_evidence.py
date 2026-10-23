"""독립 최종 재시험 원본을 검토본에 연결합니다. 제품 인수 상태는 보류합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import hashlib, json, shutil
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
CS=ROOT/'final_project_cs'
VERIFY=HERE.parent/'verification'
RUN=VERIFY/'runs/2026-10-12_followup_064826'
now=datetime.now(ZoneInfo('Asia/Seoul'))
stamp=now.strftime('%Y-%m-%d_%H%M%S')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
handoff=read(RUN/'final-handoff.json')
audit=read(RUN/'integration-original-audit.json')
assert audit['all_original_counts_and_hashes_match']
assert audit['whole_common_travel_overlap']==0
assert handoff['unique_tests']==7850 and handoff['remaining_test_count']==23
assert handoff['latest_unique_test_observations']==dict(passed=7827,skipped=7,failed=2,error=14)
evidence=[]
for item in handoff['independent_final_runs']:
    label=item['label']
    junit=RUN/(label+'.xml')
    assert sha(junit)==item['junit_sha256']
    cases=ET.parse(junit).getroot().findall('.//testcase')
    counts=Counter('failed' if c.find('failure') is not None else 'error' if c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed' for c in cases)
    assert counts==dict(passed=item['passed'])
    before=read(RUN/(label+'-source-before.json'))
    after=read(RUN/(label+'-source-after.json'))
    assert len(before)==1410 and before==after
    changed=[rel for rel,digest in after.items() if not (CS/rel).is_file() or sha(CS/rel)!=digest]
    assert not changed,changed
    evidence.append(dict(label=label,passed=item['passed'],total=len(cases),junit=junit.relative_to(ROOT).as_posix(),junit_sha256=sha(junit),source_files=1410,source_changed=[]))
assert sum(x['passed'] for x in evidence)==192
backup=HERE/'_backup'/(stamp+'_independent_evidence')
def write(p,s):
    target=backup/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    p.write_text(s,encoding='utf-8')
report_path=VERIFY/'final-handoff-2026-10-12.md'
report_rel=report_path.relative_to(ROOT).as_posix()
baseline=ROOT/'program/baseline/triPilot-baseline-2026-10-12.md'
b=baseline.read_text(encoding='utf-8')
anchor='규칙 등록은70개'
paragraph=f'독립 검증 담당의 마지막 재시험은 **이전 실패22/22·로그인/권한156/156·이력 분류14/14**를 통과했습니다. 세 실행 각각 시작·종료의 소스1,410파일이 같고 이번 대조에서도 변경0개입니다. [최종 독립 검증 인계](../../{report_rel})에서 JUnit 원문·SHA-256·전체 원본7/7회 대조와 자료 조건23개를 확인합니다. 통합 전체 실행기의 소스1,237파일 범위에는 eval173개가 없었으며 독립 실행은 이를 포함했습니다. 이 범위 차이를 전체 실행 당시의 동결 증거로 확대하지 않습니다.\n\n'
assert '[최종 독립 검증 인계]' not in b
write(baseline,b.replace(anchor,paragraph+anchor))
guide=ROOT/'program/plan/triPilot_구현계획서_v12.md'
g=guide.read_text(encoding='utf-8')
anchor='최신 여행 전체 회귀와 계약·보안·관문의 최종 해시 대조를 마칩니다.'
if anchor in g:raise AssertionError('Stale guide')
g+='\n독립 검증 담당은 수정 영향192/192와 전체·후속 원본7/7회 대조를 완료했습니다. [최종 독립 인계](../../'+report_rel+')의 미충족23개·외부 종단·환경 한계를 그대로 따릅니다. 독립 재시험 통과도 제품 전체 인수 완료를 뜻하지 않습니다.\n'
write(guide,g)
output=HERE/'checks'/('independent-evidence-review-'+stamp+'.json')
output.write_text(json.dumps(dict(at_kst=now.isoformat(),runs=evidence,original_runs_match=7,original_runs_total=7,
    handoff=dict(path=(RUN/'final-handoff.json').relative_to(ROOT).as_posix(),sha256=sha(RUN/'final-handoff.json')),
    remaining_tests=23,product_acceptance='not_accepted',backup=backup.relative_to(ROOT).as_posix()),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
state=read(HERE/'status.json')
state.update(updated_at_kst=now.isoformat(),latest_independent_review=output.relative_to(ROOT).as_posix(),latest_independent_report=report_rel,product_complete=False)
state['tests']+=evidence
write(HERE/'status.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
own=HERE/'report.md'
write(own,own.read_text(encoding='utf-8')+f'\n\n## 독립 최종 결과 대조 — {now.isoformat()}\n\n[독립 인계](../../../../../{report_rel})의 원본 JUnit 세 개와1,410파일을 직접 대조했습니다. 이전 실패22·로그인/권한156·이력14를 모두 통과했고 현재 소스 변경0개입니다. [집계·해시](checks/{output.name})를 남겼으며 자료23개와 실제 연결·환경 조건은 인수 보류로 유지합니다. [변경 전 백업]({backup.relative_to(HERE).as_posix()}/).\n')
print(json.dumps(dict(output=output.relative_to(ROOT).as_posix(),passed=192,total=192,originals=7,product_complete=False),ensure_ascii=True))
