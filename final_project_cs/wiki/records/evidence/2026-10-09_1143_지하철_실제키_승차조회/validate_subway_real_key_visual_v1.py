from pathlib import Path
from datetime import datetime
from urllib.parse import urlsplit,unquote
from html.parser import HTMLParser
import hashlib,json,re,subprocess,shutil
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2];CS=ROOT/'final_project_cs';work=json.loads((Path(__file__).parent/'subway-real-key-work-v1.json').read_text(encoding='utf8'));ev=ROOT/work['evidence'];state=json.loads((ev/'publication-state-v1.json').read_text(encoding='utf8'));assets=ROOT/state['assets'];report=ROOT/state['report']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):
 with p.open('x',encoding='utf8') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False)
pub=json.loads((ev/'publication-validation-v1.json').read_text(encoding='utf8'));checks=[]
for k in ('source_test_data_hashes','artifact_hashes'):
 d=pub[k];bad=[p for p,h in d.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h];assert not bad,bad;checks.append({'scope':k,'checked':len(d),'matches':len(d),'mismatches':bad})
class Parser(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.articles=0;self.filters=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a' and a.get('href'):self.links.append(a['href'])
  if tag=='article':self.articles+=1
  if tag=='select' and a.get('id')=='filter':self.filters+=1
text=(assets/'mobility-readiness.html').read_text(encoding='utf8');parser=Parser();parser.feed(text);assert parser.articles==21 and parser.filters==1
links=[]
for src,values in [(assets/'mobility-readiness.html',parser.links),(report,re.findall(r'\[[^\]]*\]\(([^)]+)\)',report.read_text(encoding='utf8')))]:
 for target in values:
  if urlsplit(target).scheme or target.startswith('#'):continue
  dest=src.parent/unquote(target.split('#',1)[0]);assert dest.exists(),(src,target);links.append({'from':src.relative_to(ROOT).as_posix(),'target':target,'exists':True})
script=re.search(r'<script>(.*?)</script>',text,re.S).group(1);scriptpath=ev/'visual-script-v1.js';scriptpath.write_text(script,encoding='utf8')
node=Path('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1007-641-0_26.1007.641.0_x64__3k8sg7r9htsxt/dependencies/node/bin/node.exe');run=subprocess.run([str(node),'--check',str(scriptpath)],capture_output=True,text=True,encoding='utf8');assert run.returncode==0,run.stderr
key=(dotenv_values(CS/'.env.apikeys').get('ACOP_SEOUL_METRO_API_KEY') or '').encode();assert key
privacy_paths=[p for p in ev.iterdir() if p.is_file()]+[p for p in assets.iterdir() if p.is_file()]+[p for p in (ROOT/work['raw']).iterdir() if p.is_file()]+[report,CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md'];bad=[p.relative_to(ROOT).as_posix() for p in privacy_paths if key in p.read_bytes()];assert not bad
backups=json.loads((ev/'backup-manifest-v1.json').read_text(encoding='utf8'))['backups'];assert all(sha(ROOT/b['backup'])==b['sha256'] for b in backups)
result={'created_at':datetime.now().astimezone().isoformat(),'hash_checks':checks,'backups_checked':len(backups),'backup_matches':len(backups),'feature_cards':parser.articles,'filter_select_count':parser.filters,'local_links_checked':len(links),'local_links':links,'javascript_syntax_exit_code':run.returncode,'privacy_files_checked':len(privacy_paths),'credential_matches':0,'browser_render_checked':False,'browser_failure':'브라우저 URL 정책이 file: 주소 탐색을 차단했습니다. 차단을 우회하지 않고 정적 검사만 수행했습니다.','deployment_or_cs_http_checked':False}
save(ev/'visual-validation-v1.json',result);shutil.copy2(Path(__file__),ev/Path(__file__).name)
new_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in [*ev.iterdir(),*assets.iterdir(),*(ROOT/work['raw']).iterdir(),report,CS/'wiki/teams/mobility.md',ROOT/'datasets/mobility/REPORT.md'] if p.is_file()}
save(ev/'final-integrity-v1.json',{'created_at':datetime.now().astimezone().isoformat(),'source_test_data_hashes':pub['source_test_data_hashes'],'artifact_hashes':new_hashes,'source_hash_matches':len(pub['source_test_data_hashes']),'artifact_hash_matches':len(new_hashes),'backup_hash_matches':len(backups),'full_feature_completion':False})
print(json.dumps({'source_matches':len(pub['source_test_data_hashes']),'artifact_matches':len(new_hashes),'backup_matches':len(backups),'cards':parser.articles,'links':len(links),'syntax_exit_code':run.returncode,'privacy_files':len(privacy_paths),'credential_matches':0,'browser_render_checked':False},ensure_ascii=False))