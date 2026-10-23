from pathlib import Path
from datetime import datetime
import json, os, subprocess, sys, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
CS=ROOT/'final_project_cs'
EV=CS/'wiki/records/evidence/2026-10-10_2120_출발안내_탑승환승시각_연결'
sys.stdout.reconfigure(encoding='utf8')
files=sorted((CS/'tests/unit/travel').glob('test_departure*.py'))
files+=sorted((CS/'tests/unit/travel/mobility').glob('test_departure*.py'))
files+=[CS/'tests/unit/travel/mobility/test_subway_departure_v1.py']
args=[sys.executable,'-m','pytest',*[p.relative_to(CS).as_posix() for p in files],'-q','-p','no:cacheprovider',f'--junitxml={EV/"after-all-v3.xml"}',f'--basetemp={ROOT/".tmp/mobility_complete_20261008/boarding_afterall_v3"}']
p=subprocess.run(args,cwd=CS,env=dict(os.environ,PYTHONIOENCODING='utf8'),capture_output=True,text=True,encoding='utf8',errors='replace')
with (EV/'after-all-v3.log').open('x',encoding='utf8') as f:
    f.write(p.stdout+'\n'+p.stderr)
suite=ET.parse(EV/'after-all-v3.xml').getroot()
result={'command':args,'file_count':len(files),'cases':len(list(suite.iter('testcase'))),'failures':len(list(suite.iter('failure'))),'errors':len(list(suite.iter('error'))),'skipped':len(list(suite.iter('skipped'))),'exit_code':p.returncode,'finished_at':datetime.now().astimezone().isoformat()}
with (EV/'after-all-run-v3.json').open('x',encoding='utf8') as f:
    json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='command'},ensure_ascii=False))
if p.returncode:print(p.stdout[-4500:])
sys.exit(p.returncode)
