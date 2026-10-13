"""검토본 링크·내용 일치·용어·비밀값과 보존 해시를 검사한다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import unquote
import hashlib, html, json, re
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
paths=[ROOT/'program/plan/triPilot_구현계획서_v12.md',ROOT/'program/baseline/triPilot-baseline-2026-10-12.md']
results=[]
class Text(HTMLParser):
    def __init__(self):super().__init__();self.text=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('style','script','svg'):self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ('style','script','svg'):self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:self.text.append(data)
for p in paths:
    raw=p.read_text(encoding='utf-8');doc=p.with_suffix('.html').read_text(encoding='utf-8')
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    links=[]
    for target in re.findall(r'\]\(([^)]+)\)',raw):
        if target.startswith(('https://','http://','#')):continue
        file=unquote(target.split('#',1)[0]);file=file[1:-1] if file.startswith('<') else file
        links.append(dict(target=target,exists=(p.parent/file).resolve().exists()))
    forbidden=re.findall(r'목 서버|가짜 서버|모방 서버|스텁 서버|사장님|대표님|선생님|고객님',raw)
    sensitive=re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])|webhooks/|@[0-9]|BEGIN (?:RSA |OPENSSH )?PRIVATE KEY',raw)
    hanja=re.findall(r'[\u4e00-\u9fff]',raw)
    parsed=Text();parsed.feed(doc)
    visible=' '.join(parsed.text)
    # 각 본문 문단의 주요 문장이 HTML에도 존재하는지 대조한다.
    sentences=[line for line in raw.splitlines() if len(line)>30 and not line.startswith(('|','!','-','sha','title:','description:'))]
    absent=[]
    for line in sentences:
        plain=re.sub(r'!?\[([^\]]+)\]\([^)]+\)',r'\1',line)
        plain=re.sub(r'[*`#]','',plain)
        if re.sub(r'\s+','',plain) not in re.sub(r'\s+','',html.unescape(visible)):absent.append(line[:80])
    row=dict(path=p.relative_to(ROOT).as_posix(),markdown_sha256=digest,hash_in_html=digest in doc,
             local_links=links,missing_links=[x for x in links if not x['exists']],forbidden_terms=forbidden,
             sensitive_patterns=sensitive,unexpected_hanja=hanja,paragraphs_checked=len(sentences),absent_paragraphs=absent,
             explicit_unaccepted='최종 인수 전 검토본' in raw and 'status: draft' in raw)
    results.append(row)
figures=[]
ns={'s':'http://www.w3.org/2000/svg'}
for p in HERE.glob('travel-*-flow.svg'):
    root=ET.fromstring(p.read_text(encoding='utf-8'))
    figures.append(dict(path=p.relative_to(ROOT).as_posix(),valid_xml=True,ovals=len(root.findall('s:ellipse',ns)),
       diamonds=len(root.findall('s:polygon',ns)),title=root.find('s:title',ns).text,
       descriptions=bool(root.find('s:desc',ns).text)))
v11=hashlib.sha256((ROOT/'program/plan/A-COP_구현계획서_v11.md').read_bytes()).hexdigest()
passed=all(r['hash_in_html'] and not any(r[k] for k in ('missing_links','forbidden_terms','sensitive_patterns','unexpected_hanja','absent_paragraphs')) and r['explicit_unaccepted'] for r in results)
passed=passed and v11=='f4ad43d9154d723d13c816d42a8bf54b78491d3f706d76a08dade79795e9dca9'
out=HERE/'checks'/('review-audit-'+datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')+'.json')
out.write_text(json.dumps(dict(passed=passed,documents=results,figures=figures,v11_sha256=v11,scope='이 검토본 두 문서 정적 검사. 전체 저장소 보안·제품 인수 아님'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(output=out.relative_to(ROOT).as_posix(),passed=passed,documents=[{k:r[k] for k in ('path','hash_in_html','missing_links','forbidden_terms','sensitive_patterns','unexpected_hanja','paragraphs_checked','absent_paragraphs')} for r in results]),ensure_ascii=False))
raise SystemExit(not passed)
