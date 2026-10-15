from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import json,hashlib,re,subprocess,shutil
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';w=json.loads((Path(__file__).parent/'subway-completeness-work-v4.json').read_text(encoding='utf8'));ev=ROOT/w['evidence'];state=json.loads((ev/'publication-state-v1.json').read_text(encoding='utf8'));assets=ROOT/state['assets'];report=ROOT/state['report'];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
proof=json.loads((ev/'verification-proof-v1.json').read_text(encoding='utf8'));pub=json.loads((ev/'publication-validation-v1.json').read_text(encoding='utf8'));checks=[]
for name,d in [('source_test_data_hashes',proof['source_test_data_hashes']),('artifact_hashes',pub['artifact_hashes'])]:
 bad=[p for p,h in d.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h];assert not bad,bad;checks.append({'scope':name,'checked':len(d),'matches':len(d),'mismatches':bad})
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.cards=0;self.filter=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a' and a.get('href'):self.links.append(a['href'])
  if tag=='article':self.cards+=1
  if tag=='select' and a.get('id')=='filter':self.filter+=1
htmlpath=assets/'mobility-readiness.html';text=htmlpath.read_text(encoding='utf8');parser=Parser();parser.feed(text);assert parser.cards==21 and parser.filter==1
links=[]
for p,items in [(htmlpath,parser.links),(report,re.findall(r'\[[^\]]*\]\(([^)]+)\)',report.read_text(encoding='utf8')))]:
 for x in items:
  if urlsplit(x).scheme or x.startswith('#'):continue
  assert (p.parent/unquote(x.split('#',1)[0])).exists(),(p,x);links.append({'file':p.relative_to(ROOT).as_posix(),'target':x,'exists':True})
script=ev/'visual-script-v1.js';script.write_text(re.search(r'<script>(.*?)</script>',text,re.S).group(1),encoding='utf8');node='C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/bin/node.exe';run=subprocess.run([node,'--check',str(script)],capture_output=True,text=True,encoding='utf8');assert run.returncode==0,run.stderr
key=(dotenv_values(CS/'.env.apikeys').get('ACOP_SEOUL_METRO_API_KEY') or '').encode();assert key
paths=[*ev.iterdir(),*assets.iterdir(),*(ROOT/w['raw']).iterdir(),report,ROOT/state['debug'],CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md'];files=[p for p in paths if p.is_file()];bad=[p.relative_to(ROOT).as_posix() for p in files if key in p.read_bytes()];assert not bad
backups=json.loads((ev/'backup-manifest-v1.json').read_text(encoding='utf8'))['backups'];assert all(sha(ROOT/x['backup'])==x['sha256'] for x in backups)
result={'created_at':datetime.now().astimezone().isoformat(),'hash_checks':checks,'backup_matches':len(backups),'feature_cards':parser.cards,'filter_count':parser.filter,'local_links':links,'javascript_syntax_exit_code':0,'credential_files_checked':len(files),'credential_matches':0,'browser_render_checked':False,'browser_policy':'앞 판 file: URL 차단을 우회/재시도하지 않고 정적 검사만 수행했습니다.','full_feature_completion':False}
save(ev/'visual-validation-v1.json',result);shutil.copy2(Path(__file__),ev/Path(__file__).name)
paths=[*ev.iterdir(),*assets.iterdir(),*(ROOT/w['raw']).iterdir(),report,ROOT/state['debug'],CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md'];hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths if p.is_file()}
save(ev/'final-integrity-v1.json',{'created_at':datetime.now().astimezone().isoformat(),'source_test_data_hashes':proof['source_test_data_hashes'],'artifact_hashes':hashes,'source_hash_matches':len(proof['source_test_data_hashes']),'artifact_hash_matches':len(hashes),'backup_hash_matches':len(backups),'full_feature_completion':False})
print(json.dumps({'source_matches':len(proof['source_test_data_hashes']),'artifact_matches':len(hashes),'backups':len(backups),'cards':parser.cards,'links':len(links),'syntax_exit_code':0,'credential_matches':0,'credential_files_checked':len(files),'browser_render_checked':False},ensure_ascii=False))