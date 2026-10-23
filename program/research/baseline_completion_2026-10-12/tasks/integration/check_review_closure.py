"""검토본 증거를 마지막으로 대조하고 미충족 인수 조건을 그대로 보존합니다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, shutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.now(ZoneInfo('Asia/Seoul'))
stamp=now.strftime('%Y-%m-%d_%H%M%S')
state=read(HERE/'status.json')
manifest_path=ROOT/state['latest_review_manifest']
manifest=read(manifest_path)
changed=[rel for rel,digest in manifest['files'].items() if not (ROOT/rel).is_file() or sha(ROOT/rel)!=digest]
assert not changed,changed
audit_path=max((HERE/'checks').glob('review-audit-*.json'))
audit=read(audit_path)
assert audit['passed'] and len(audit['documents'])==2
render_path=max((HERE/'checks').glob('review-screens-*/render-checks.json'))
render=read(render_path)
assert len(render['checks'])==4 and all(c['passed'] for c in render['checks'])
wiki_path=HERE/'checks/2026-10-12_0645_wiki.json'
assert read(wiki_path)['total_violations']==0
gate_path=HERE/'checks/final-gate-2026-10-12_064132/summary.json'
gate=read(gate_path)
assert gate['unique_nodes']==7850 and gate['overlap']==0 and gate['legacy_linked_gate']['passed']==26
assert gate['frozen_files']['passed'] and gate['historical_commit_phase']['passed']
documents=[]
for rel in ('program/plan/triPilot_구현계획서_v12.md','program/baseline/triPilot-baseline-2026-10-12.md'):
    p=ROOT/rel
    assert 'status: draft' in p.read_text(encoding='utf-8')
    assert sha(p) in p.with_suffix('.html').read_text(encoding='utf-8')
    documents.append(dict(path=rel,sha256=sha(p),html_sha256=sha(p.with_suffix('.html')),status='draft_unaccepted'))
evidence=[manifest_path,audit_path,render_path,wiki_path,gate_path,ROOT/state['latest_suite_review']]
output=HERE/'checks'/('review-closure-'+stamp+'.json')
report=dict(at_kst=now.isoformat(),review_checks_passed=True,product_complete=False,documents=documents,
            source_files_checked=len(manifest['files']),source_changed=[],evidence=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in evidence],
            visual_review='1440px 안내서 상단·375px 기준선 상단 실제 이미지 육안 확인. 앞선 두 흐름도 육안 확인 유지.',
            requirements_pending=state['dependencies_remaining'],automation='후속 확인 유지; 최종 인수 조건 충족 전 종료하지 않음')
output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
backup=HERE/'_backup'/(stamp+'_review_closure')
backup.mkdir()
shutil.copy2(HERE/'status.json',backup/'status.json')
state.update(updated_at_kst=now.isoformat(),review_closure_evidence=output.relative_to(ROOT).as_posix(),review_checks_passed=True,product_complete=False)
(HERE/'status.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(output=output.relative_to(ROOT).as_posix(),source_files_checked=len(manifest['files']),source_changed=changed,documents=2,render_checks=4,product_complete=False),ensure_ascii=True))
