"""Read-only inventory for a review candidate, never a production attestation."""
from pathlib import Path
from collections import Counter
import ast, datetime, hashlib, importlib.metadata, json, subprocess, sys, shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
CS=ROOT/'final_project_cs'
EXCLUDED={'_backup','.archive','__pycache__','node_modules','.git','.pytest_cache','dist','build','legacy'}
DIRS=['app','tests','config','prompts','knowledge/travel','eval/travel_classification','migrations',
      'frontend/apps/web/src','frontend/packages']
FILES=['requirements.txt','pyproject.toml','pytest.ini','frontend/package.json','frontend/pnpm-lock.yaml',
       'frontend/apps/web/package.json','scripts/verify_travel_eval_datasets.py','scripts/verify_dod_v11.py',
       'eval/datasets/travel_golden.jsonl','eval/datasets/travel_holdout.jsonl',
       'frontend/apps/web/package-lock.json','scripts/service_improvement.py']
DOCS=['README.md','AGENTS.md','program/plan/A-COP_구현계획서_v11.md','wiki/decisions/D-018-decision15-stop-paths.md',
      'wiki/decisions/D-023-no-commerce-assets-in-use.md','wiki/delivery/roles.md',
      'final_project_cs/wiki/teams/team-contract/index.md','final_project_cs/wiki/teams/team-boundary.md',
      'final_project_cs/wiki/teams/activity.md','final_project_cs/wiki/teams/dining.md','final_project_cs/wiki/teams/mobility.md',
      'final_project_cs/wiki/quality/slm-model-evaluation.md','final_project_cs/wiki/quality/selection-grounded-answer-evaluation.md',
      'final_project_cs/wiki/operations/service-improvement.md','final_project_cs/wiki/operations/retention.md',
      'program/research/daily_rag_slm/saluki_finetune_plan_2026-10-09.md',
      'program/research/daily_rag_slm/saluki_finetune_2026-10-09.json']

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8',errors='replace').strip()
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def inventory():
    paths=set()
    for name in DIRS:
        base=CS/name
        if base.exists():
            paths.update(p for p in base.rglob('*') if p.is_file() and not EXCLUDED.intersection(p.relative_to(CS).parts)
                         and not p.name.startswith('.env') and p.suffix not in {'.pyc','.png','.jpg','.avif','.pdf','.woff2'})
    paths.update(CS/f for f in FILES if (CS/f).is_file())
    paths.update(ROOT/f for f in DOCS if (ROOT/f).is_file())
    records=[dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p),bytes=p.stat().st_size) for p in sorted(paths)]
    canonical=''.join(r['path']+'\0'+r['sha256']+'\n' for r in records).encode()
    return records,hashlib.sha256(canonical).hexdigest()

def capture():
    records,tree=inventory()
    status=git('status','--porcelain=v1','-uall').splitlines()
    datasets={}
    for name in ['travel_golden.jsonl','travel_holdout.jsonl']:
        p=CS/'eval/datasets'/name
        rows=[json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
        datasets[name]={'rows':len(rows),'sha256':digest(p),'label_by':dict(Counter(r.get('label_by') for r in rows))}
    versions={}
    for name in ['pytest','pydantic','fastapi','PyYAML','psycopg','httpx']:
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]='not installed'
    before=json.loads((OUT/'project-manifest.json').read_text(encoding='utf-8'))
    old={r['path']:r['sha256'] for r in before['files']}
    current={r['path']:r['sha256'] for r in records}
    changed=[{'path':p,'kind':'added' if p not in old else 'deleted' if p not in current else 'modified'}
             for p in sorted(old.keys()|current.keys()) if old.get(p)!=current.get(p)]
    node=Path('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/bin/node.exe')
    manifest=dict(id='triPilot-BL-2026-10-10-v2',status='review-candidate',date_kst='2026-10-10',
       captured_at_kst=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec='seconds'),
       previous_id=before['id'],changes_vs_v1=changed,
       git_head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),
       git_status_counts=dict(Counter(line[:2] for line in status)),
       git_status_scope='워크스페이스 전체. 이 작업 이전 변경을 포함하며 제품 완료율이 아님',
       python=sys.version.split()[0],packages=versions,node=subprocess.check_output([str(node),'--version']).decode().strip(),
       selection_dirs=DIRS,selection_files=FILES,selection_docs=DOCS,exclusions=sorted(EXCLUDED),
       tree_sha256=tree,file_count=len(records),files=records,datasets=datasets,
       reproducibility='해시는 파일 동일성 확인용이다. 미커밋 작업 트리는 HEAD만으로 복구할 수 없다. 코드·외부 자료·DB·모델 전체 복제본이 아니다.')
    target=OUT/'project-manifest-v2.json'
    if target.exists():
        backup=OUT/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_capture_v2')
        backup.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup/target.name)
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k not in {'files','selection_dirs','selection_files','exclusions'}},ensure_ascii=False,indent=2))

if __name__=='__main__': capture()
