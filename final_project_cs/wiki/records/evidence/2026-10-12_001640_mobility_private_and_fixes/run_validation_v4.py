from pathlib import Path
import json,os,time,tempfile
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs'
OUT=ROOT/'.tmp/mobility_finish_20261011/final-gate-v4';OUT.mkdir(exist_ok=False)
TEMP=OUT/'collection-temp';TEMP.mkdir()
os.environ['TEMP']=os.environ['TMP']=str(TEMP);tempfile.tempdir=str(TEMP)
import pytest
class OfflineOnly:
 @pytest.fixture(autouse=True)
 def prevent_external_connections(self,monkeypatch):
  import socket
  def reject(*a,**k):
   raise AssertionError('This validation run forbids network connections')
  monkeypatch.setattr(socket.socket,'connect',reject)
  monkeypatch.setattr(socket,'create_connection',reject)
os.chdir(CS)
args=['tests/unit/travel/mobility','tests/unit/travel/test_subway_notice.py',
 'tests/unit/travel/test_subway_notice_station_lists_v1.py','tests/contract','tests/security',
 '-q','--maxfail=5','--basetemp',str(OUT/'temp'),
 '--junitxml',str(OUT/'result.xml')]
start=time.monotonic();rc=pytest.main(args,plugins=[OfflineOnly()])
(OUT/'execution.json').write_text(json.dumps({'args':args,'exit_code':int(rc),'elapsed_s':round(time.monotonic()-start,2),'network_connections':'blocked by autouse socket guard','scope':'default mobility gate + notice + contract + security; mobility_full deselected'},ensure_ascii=False,indent=2),encoding='utf8')
raise SystemExit(rc)
