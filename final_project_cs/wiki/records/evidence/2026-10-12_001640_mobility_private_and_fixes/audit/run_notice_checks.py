from pathlib import Path
import contextlib
import json
import os
import socket
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[3]
out = root / '.tmp/mobility_finish_20261011/subway_notice'
out.mkdir(parents=True,exist_ok=True)
temp = out / 'temp'
temp.mkdir(exist_ok=True)
tempfile.tempdir = str(temp)
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(root / 'final_project_cs')
sys.path.insert(0,str(root / 'final_project_cs'))
network_attempts = []
def reject_network(*args,**kwargs):
    network_attempts.append('blocked')
    raise AssertionError('이 검증에서는 외부 연결을 허용하지 않습니다.')
socket.create_connection = reject_network
socket.socket.connect = reject_network
mode = sys.argv[1]
paths = ['tests/unit/travel/test_subway_notice_station_lists_v1.py']
if mode == 'after':
    paths += ['tests/unit/travel/test_subway_notice.py','tests/unit/travel/test_utic_route_events.py','tests/unit/travel/test_its_route_events_alternate.py','tests/unit/travel/test_its_traffic.py','tests/unit/travel/test_disruption_check.py']
args = paths + ['-q','--junitxml='+str(out/(mode+'.xml'))]
import pytest
start = time.time()
with (out/(mode+'.log')).open('w',encoding='utf-8') as handle, contextlib.redirect_stdout(handle),contextlib.redirect_stderr(handle):
    code = pytest.main(args)
record = dict(mode=mode,args=args,exit_code=code,elapsed_s=time.time()-start,external_connection_attempts=len(network_attempts),api_calls=0)
(out/(mode+'-run.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(record,ensure_ascii=False))
