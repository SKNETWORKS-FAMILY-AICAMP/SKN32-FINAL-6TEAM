"""Read-only audits of source identity, frozen project identity and document links."""
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit, unquote
import datetime, hashlib, importlib.util, json, shutil
from bs4 import BeautifulSoup
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
checks=[]
def add(name, passed, detail):
    checks.append(dict(name=name,passed=bool(passed),detail=detail))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

sources=json.loads((HERE/'source-manifest.json').read_text(encoding='utf-8'))['sources']
for r in sources:
    p=HERE/r['file']
    good=p.is_file() and p.stat().st_size==r['bytes'] and digest(p)==r['sha256']
    if p.suffix=='.pdf': good=good and len(PdfReader(p).pages)==r['pdf_pages']
    add('source-'+r['id'],good,dict(bytes=r['bytes'],sha256=r['sha256'],pages=r.get('pdf_pages')))

spec=importlib.util.spec_from_file_location('capture',HERE/'capture_project.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
now,tree=capture.inventory()
frozen=json.loads((HERE/'project-manifest.json').read_text(encoding='utf-8'))
old={r['path']:r['sha256'] for r in frozen['files']}
new={r['path']:r['sha256'] for r in now}
drift=[p for p in sorted(set(old)|set(new)) if old.get(p)!=new.get(p)]
add('project-snapshot',not drift,dict(frozen_files=len(old),current_files=len(new),changed_paths=drift,current_tree_sha256=tree))

for filename in ['triPilot-baseline-v1.html','baseline-writing-guide.html']:
    soup=BeautifulSoup((HERE/filename).read_text(encoding='utf-8'),'html.parser')
    ids=Counter(x['id'] for x in soup.select('[id]'))
    bad=[]; local_count=0;remote_count=0
    for a in soup.select('a[href]'):
        url=urlsplit(a['href'])
        if url.scheme in {'http','https'}:
            remote_count+=1
            if a['href'] not in {s['url'] for s in sources}:bad.append(a['href'])
            continue
        if url.scheme:bad.append(a['href']);continue
        local_count+=1
        target=(HERE/unquote(url.path)).resolve() if url.path else HERE/filename
        if not target.exists():bad.append(a['href']);continue
        if url.fragment and target.suffix=='.html':
            other=soup if target==HERE/filename else BeautifulSoup(target.read_text(encoding='utf-8'),'html.parser')
            if not other.find(id=unquote(url.fragment)):bad.append(a['href'])
    add(filename+':links',not bad,dict(local=local_count,remote_citations=remote_count,broken=bad))
    add(filename+':unique-ids',all(n==1 for n in ids.values()),dict(duplicate=[k for k,v in ids.items() if v>1]))
    svgs=soup.find_all('svg')
    svg_errors=[]
    for svg in svgs:
        children=[c for c in svg.children if getattr(c,'name',None)]
        refs=svg.get('aria-labelledby','').split()
        if not children or children[0].name!='title' or svg.get('role')!='img' or len(refs)!=2 or not all(svg.find(id=k) for k in refs):svg_errors.append(svg.get('aria-labelledby'))
    add(filename+':accessible-svg',len(svgs)==2 and not svg_errors,dict(diagrams=len(svgs),errors=svg_errors))
    remote_assets=soup.select('script,iframe,embed,object,link[href],img[src],audio[src],video[src]')
    add(filename+':offline',not remote_assets and 'url(' not in soup.style.get_text(),dict(external_asset_tags=len(remote_assets)))
    add(filename+':document-structure',soup.html.get('lang')=='ko' and len(soup.find_all('h1'))==1 and bool(soup.find('main')) and bool(soup.find('nav')) and not soup.find(string=lambda s:s and '\ufffd' in s),dict(sections=len(soup.select('main > section'))))
    text=soup.get_text(' ',strip=True)
    add(filename+':status-and-evidence',all(k in text for k in ['검토','채택','235','238','claude-draft','S01','S11']), '후보·채택 지위, 실제 시험 분모, AI 초안과 출처 구분')

baseline=BeautifulSoup((HERE/'triPilot-baseline-v1.html').read_text(encoding='utf-8'),'html.parser')
dod_table=baseline.find(id='acceptance').find('table')
dod=[int(tr.find('td').get_text()) for tr in dod_table.select('tbody tr')]
add('mvp-18',dod==list(range(1,14))+list(range(22,27)),dict(ids=dod,total=len(dod)))
add('source-scope-language',all('公開' not in r['scope'] for r in sources),'다운로드 범위 한국어 표시')
document_checks=[c for c in checks if c['name']!='project-snapshot']
report=dict(date_kst='2026-10-10',checks=checks,passed=sum(c['passed'] for c in checks),total=len(checks),document_passed=sum(c['passed'] for c in document_checks),document_total=len(document_checks),state_observations=[c for c in checks if c['name']=='project-snapshot'],limitations='문서·원문 동일성 검사이며 제품 출시, 사람 정답 검수, 팀 채택을 대신하지 않음. project-snapshot은 문서 합격 항목과 별도로 표시하는 현재 작업 상태 관측임')
target=HERE/'checks/document-audit.json'
if target.exists():
    backup=HERE/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_audit')
    backup.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup/target.name)
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
