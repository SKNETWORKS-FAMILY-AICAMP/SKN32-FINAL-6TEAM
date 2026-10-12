from pathlib import Path
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf8')
root = Path(__file__).resolve().parents[2]
cs = root / 'final_project_cs'
state = json.loads((Path(__file__).parent / 'transfer-product-work-v1.json').read_text(encoding='utf8'))
ev = cs / 'wiki/records/evidence' / state['tag']
stage = sys.argv[1]
paths = ['tests/unit/travel/mobility/test_transfer_fare_product_v1.py']
if stage.startswith('related'):
    paths += [str(p.relative_to(cs)) for p in sorted((cs / 'tests/unit/travel/mobility').glob('test*fare*.py'))
              if p.name != 'test_transfer_fare_product_v1.py']
    paths += ['tests/unit/travel/mobility/test_plan_v1.py',
              'tests/unit/travel/mobility/test_review_fixes_plan.py']
base = Path(__file__).parent / ('pytest-transfer-product-' + stage)
assert not base.exists()
log = ev / (stage + '.log')
assert not log.exists()
guard = '''import socket,sys,json
from pathlib import Path
calls=[]
def deny(*args,**kwargs):
    calls.append(1)
    raise RuntimeError('offline test blocks network')
socket.socket.connect=deny
socket.socket.connect_ex=deny
from app.domains.travel_ops.instances.mobility.engine import runtime
original=runtime.build_verifier
def offline(**kwargs):
    kwargs.setdefault('local_router',True)
    kwargs.setdefault('seoul_key','')
    kwargs.setdefault('gh_url','')
    return original(**kwargs)
runtime.build_verifier=offline
import pytest
code=pytest.main(sys.argv[1:])
Path(''' + repr(str(ev / (stage + '-network.json'))) + ''').write_text(json.dumps({'blocked_network_attempts':len(calls),'limited_api_calls':0}),encoding='utf8')
sys.exit(code)
'''
cmd = [sys.executable, '-c', guard, *paths, '-q', '--basetemp=' + str(base),
       '--junitxml=' + str(ev / (stage + '.xml'))]
p = subprocess.run(cmd, cwd=cs, env=dict(os.environ, PYTHONIOENCODING='utf8'),
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf8')
log.write_text(p.stdout, encoding='utf8')
(ev / (stage + '-run.json')).write_text(json.dumps({'command': cmd, 'exit_code': p.returncode}, indent=2), encoding='utf8')
print(p.stdout[-4500:])
sys.exit(p.returncode)
