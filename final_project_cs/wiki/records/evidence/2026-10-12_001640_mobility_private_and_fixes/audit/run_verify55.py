from pathlib import Path
import contextlib
import copy
import hashlib
import json
import os
import socket
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

root=Path(__file__).resolve().parents[3]
out=root/'.tmp/mobility_finish_20261011/verify55'
temp=out/'temp'
temp.mkdir(exist_ok=True)
tempfile.tempdir=str(temp)
os.chdir(root/'final_project_cs')
sys.path.insert(0,str(root/'final_project_cs'))
attempts=[]
def reject(*args,**kwargs):
    attempts.append('blocked')
    raise AssertionError('이 오프라인 회귀에서는 외부 연결을 허용하지 않습니다.')
socket.create_connection=reject
socket.socket.connect=reject
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads((root/'.tmp/mobility_finish_20261011/audit/readiness-current.json').read_text(encoding='utf-8'))
paths=[root/p for p in audit['data_hashes']]
source=root/'final_project_cs/tests/unit/travel/mobility/test_verify55_v1.py'
paths += [source,root/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/runtime.py',root/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/verify_time.py',root/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/candidates.py',root/'final_project_cs/app/domains/travel_ops/instances/mobility/engine/options.py']
start_hashes={p.relative_to(root).as_posix():sha(p) for p in paths}
(out/'start-hashes.json').write_text(json.dumps(start_hashes,indent=2),encoding='utf-8')
targets={'test_d_p90_multi_seoul_itaewon','test_d_wondeok_no_yangpyeong_transfer'}
original=ET.parse(out/'before-full-gate-v4.xml').getroot()
subset=ET.Element('testsuites')
suite=ET.SubElement(subset,'testsuite',name='v4_original_target_failures',tests='2',failures='2',errors='0',skipped='0')
for case in original.iter('testcase'):
    if case.attrib.get('name') in targets:
        suite.append(copy.deepcopy(case))
assert len(suite)==2
ET.ElementTree(subset).write(out/'before-two-targets.xml',encoding='utf-8',xml_declaration=True)
args=['tests/unit/travel/mobility/test_verify55_v1.py','-q','-m','not live and (mobility_full or not mobility_full)','--junitxml='+str(out/'after.xml')]
import pytest
start=time.time()
with (out/'after.log').open('w',encoding='utf-8') as handle,contextlib.redirect_stdout(handle),contextlib.redirect_stderr(handle):
    code=pytest.main(args)
end_hashes={p.relative_to(root).as_posix():sha(p) for p in paths}
record=dict(args=args,exit_code=code,elapsed_s=time.time()-start,blocked_connection_attempts=len(attempts),api_calls=0,start_hashes=start_hashes,end_hashes=end_hashes,changed_during_run=[k for k,v in start_hashes.items() if end_hashes[k]!=v],original_v4_log_hash=sha(out/'before-full-gate-v4.log'),original_v4_xml_hash=sha(out/'before-full-gate-v4.xml'))
(out/'run.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if not k.endswith('hashes')},ensure_ascii=False))
