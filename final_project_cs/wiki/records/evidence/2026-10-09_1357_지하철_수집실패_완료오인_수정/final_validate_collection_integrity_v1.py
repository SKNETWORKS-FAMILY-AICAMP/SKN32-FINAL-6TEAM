from pathlib import Path
import hashlib, json, subprocess, sys, os, re, shutil

ROOT=Path(__file__).resolve().parents[2]; CS=ROOT/'final_project_cs'
state=json.loads((Path(__file__).parent/'collection-integrity-state-v1.json').read_text(encoding='utf8')); EV=ROOT/state['evidence']
manifest=json.loads((EV/'final-integrity-v1.json').read_text(encoding='utf8'))
checks=[hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for section in ('source_test_data_hashes','artifact_hashes') for p,h in manifest[section].items()]
assert all(checks)
backup_checks=[hashlib.sha256((ROOT/b['backup']).read_bytes()).hexdigest()==b['sha256'] for b in manifest['backups']]
assert all(backup_checks)
html=ROOT/manifest['assets']/'mobility-readiness.html'
js=re.search(r'<script>(.*?)</script>',html.read_text(encoding='utf8'),re.S).group(1)
(EV/'visual-script-v1.js').write_text(js,encoding='utf8')
results={}
for name,args in [
 ('visual-js',[shutil.which('node'),'--check',str(EV/'visual-script-v1.js')]),
 ('visual-self-check',[sys.executable,'C:/Users/playdata2/.agents/skills/diagram-design/scripts/self_check.py',str(html)]),
 ('debug-status',[sys.executable,'-m','pytest','tests/unit/core/test_debug_report_status.py','-q','-p','no:cacheprovider',f'--basetemp={ROOT/".tmp/mobility_complete_20261008/collector_debug_status"}'])]:
    p=subprocess.run(args,cwd=CS,env=dict(os.environ,PYTHONIOENCODING='utf-8'),capture_output=True,text=True,encoding='utf8',errors='replace')
    (EV/f'{name}-v1.log').write_text(p.stdout+'\n'+p.stderr,encoding='utf8')
    results[name]={'exit_code':p.returncode,'command':args}
    print(name,p.returncode,p.stdout[-800:])
with (EV/'final-validation-v1.json').open('x',encoding='utf8') as f:json.dump({'hashes_matched':sum(checks),'hashes_checked':len(checks),'backups_matched':sum(backup_checks),'backups_checked':len(backup_checks),'checks':results,'browser_rendered':False},f,ensure_ascii=False,indent=2)
shutil.copy2(Path(__file__),EV/Path(__file__).name)
print('preserved hashes',len(checks),'backups',len(backup_checks))
sys.exit(int(any(r['exit_code'] for r in results.values())))
