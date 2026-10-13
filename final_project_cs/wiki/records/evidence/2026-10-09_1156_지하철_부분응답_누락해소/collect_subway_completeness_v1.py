from pathlib import Path
from datetime import datetime
import json,hashlib,httpx,urllib.parse
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';now=datetime.now().astimezone();tag=now.strftime('%Y-%m-%d_%H%M')+'_지하철_부분응답_누락해소';ev=CS/'wiki/records/evidence'/tag;ev.mkdir(parents=True,exist_ok=False);raw=ROOT/'datasets/mobility/raw'/tag;raw.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
prior=CS/'wiki/records/evidence/2026-10-09_1143_지하철_실제키_승차조회/final-integrity-v1.json';d=json.loads(prior.read_text(encoding='utf8'));check=[]
for k in ('source_test_data_hashes','artifact_hashes'):
 bad=[p for p,h in d[k].items() if not (ROOT/p).exists() or sha(ROOT/p)!=h];assert not bad;check.append({'scope':k,'checked':len(d[k]),'matches':len(d[k]),'mismatches':bad})
save(ev/'preflight-v1.json',{'created_at':now.isoformat(),'checks':check})
key=(dotenv_values(CS/'.env.apikeys').get('ACOP_SEOUL_METRO_API_KEY') or '').strip();assert key
entries=[]
for i,end in enumerate((20,1000,1000,20),1):
 start=datetime.now().astimezone();response=httpx.get('http://swopenapi.seoul.go.kr/api/subway/'+key+'/json/realtimeStationArrival/0/'+str(end)+'/'+urllib.parse.quote('서울'),timeout=20);finish=datetime.now().astimezone();body=response.content;echoed=key.encode() in body;p=raw/f'response-{i}-v1.json';p.write_bytes(body.replace(key.encode(),b'<redacted>') if echoed else body)
 data=response.json();info=data.get('errorMessage',data);rows=data.get('realtimeArrivalList',[])
 entries.append({'station':'서울','page_start':0,'page_end':end,'started_at':start.isoformat(),'finished_at':finish.isoformat(),'http_status':response.status_code,'code':info.get('code'),'provider_total':info.get('total'),'returned_rows':len(rows),'raw_path':p.relative_to(ROOT).as_posix(),'raw_sha256':sha(p),'key_redacted':echoed,'provider_times':sorted({r.get('recptnDt') for r in rows}),'row_identities':[[r.get(k) for k in ('subwayId','statnId','btrainNo','ordkey')] for r in rows]})
result={'created_at':datetime.now().astimezone().isoformat(),'order':'A20 B1000 B1000 A20','requests':entries,'actual_http_attempts':4,'map_developer_api_calls':0,'actual_eta_error_boarding_payment':0,'claim':'동일역 두 조회범위의 교대 실응답 행수 대조. 운행목록 전세계 완전성·실제ETA오차·독립웹경로 아님.'}
save(raw/'acquisition-v1.json',result);save(ev/'page-size-live-v1.json',result);save(Path(__file__).parent/'subway-completeness-work-v1.json',{'tag':tag,'evidence':ev.relative_to(ROOT).as_posix(),'raw':raw.relative_to(ROOT).as_posix(),'baseline_source_hashes':d['source_test_data_hashes']})
print(json.dumps({'tag':tag,'requests':[{k:e[k] for k in ('page_end','http_status','code','provider_total','returned_rows','provider_times')} for e in entries]},ensure_ascii=False))