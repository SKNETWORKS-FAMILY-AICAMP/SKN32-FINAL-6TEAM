from pathlib import Path
import os, socket, sys, json
root=Path(__file__).resolve().parents[2]; repo=root/'final_project_cs'
os.chdir(repo); sys.path.insert(0,str(repo))
out=repo/'wiki/records/evidence/2026-10-11_1515_단일방향_유턴금지'
calls=[]
def deny(*a,**kw):calls.append('blocked');raise RuntimeError('offline test')
socket.socket.connect=socket.socket.connect_ex=deny
import pytest
files=['tests/unit/travel/mobility/test_same_way_uturn_policy_v1.py',
       'tests/unit/travel/mobility/test_car_turn_restrictions_v1.py',
       'tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py',
       'tests/unit/travel/mobility/test_graph_router.py']
args=files+['-q','-k','not real_graph','--basetemp='+str(root/'.tmp/mobility_uturn_related_20261011'),
            '--junitxml='+str(out/'related-v1.xml')]
status=pytest.main(args)
with (out/'related-command.json').open('x',encoding='utf8') as f:json.dump({'args':args,'exit_code':status,'network_attempts':len(calls)},f,indent=2)
raise SystemExit(status)
