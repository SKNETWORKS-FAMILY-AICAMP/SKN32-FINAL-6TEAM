"""Verify rendered print content and extracted inline diagrams with the skill checker."""
from pathlib import Path
import datetime, json, shutil, subprocess, sys
from bs4 import BeautifulSoup
from pypdf import PdfReader
import fitz
HERE=Path(__file__).resolve().parent
CHECKER=Path('C:/Users/playdata2/.agents/skills/diagram-design/scripts/self_check.py')
def save(p,data):
 if p.exists():
  b=HERE/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_print_diagram');b.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b/p.name)
 p.write_text(data,encoding='utf-8')
diagrams=[];prints=[]
for stem in ['triPilot-baseline-v1','baseline-writing-guide']:
 soup=BeautifulSoup((HERE/(stem+'.html')).read_text(encoding='utf-8'),'html.parser')
 for i,svg in enumerate(soup.find_all('svg')):
  p=HERE/'checks'/f'{stem}-diagram-{i+1}.html'
  save(p,'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>그림 검사</title></head><body>'+str(svg)+'</body></html>')
  result=subprocess.run([sys.executable,'-X','utf8',str(CHECKER),str(p)],capture_output=True,text=True,encoding='utf-8')
  diagrams.append(dict(file=p.name,passed=result.returncode==0,output=result.stdout.strip()))
 pdf=HERE/'checks/screens'/(stem+'-print.pdf')
 reader=PdfReader(pdf);text='\n'.join(p.extract_text() or '' for p in reader.pages)
 expected=['S01','S11','triPilot-BL-2026-10-10-v1']
 if stem=='triPilot-baseline-v1':expected+=['python -m scripts.verify_travel_eval_datasets','채택자·날짜:']
 # PDF extraction inserts spaces between Hangul glyph runs in monospace blocks.
 compact=lambda s:''.join(s.split())
 missing=[x for x in expected if compact(x) not in compact(text)]
 prints.append(dict(file=pdf.name,pages=len(reader.pages),passed=not missing,missing_markers=missing))
 doc=fitz.open(pdf)
 for page_number in [0,len(doc)-1]:
  shot=HERE/'checks/screens'/f'{stem}-print-page-{page_number+1}.png'
  if shot.exists():
   b=HERE/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_print_render');b.mkdir(parents=True,exist_ok=True);shutil.copy2(shot,b/shot.name)
  doc[page_number].get_pixmap(matrix=fitz.Matrix(1.2,1.2)).save(shot)
 doc.close()
for filename,rows in [('diagram-audit.json',diagrams),('print-audit.json',prints)]:
 report=dict(results=rows,passed=sum(x['passed'] for x in rows),total=len(rows))
 save(HERE/'checks'/filename,json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False,indent=2))
