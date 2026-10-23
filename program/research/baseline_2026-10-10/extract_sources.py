from pathlib import Path
from bs4 import BeautifulSoup
from pypdf import PdfReader
import json

ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'source-manifest.json').read_text(encoding='utf-8'))
target=ROOT/'source-text'
target.mkdir(exist_ok=True)
pdf_pages={'S01':[0,189,190,192,199], 'S02':[0,41], 'S03':[112,113,215,216,254]}
for record in manifest['sources']:
    source=ROOT/record['file']
    if source.suffix=='.pdf':
        reader=PdfReader(source)
        text='\n\n'.join(f'=== PDF page {i+1} ===\n'+(reader.pages[i].extract_text() or '') for i in pdf_pages[record['id']])
    else:
        soup=BeautifulSoup(source.read_bytes(),'html.parser')
        for el in soup.select('script,style,nav,footer,header'): el.decompose()
        main=soup.find('main') or soup.find('article') or soup.body or soup
        text=main.get_text('\n',strip=True)
    out=target/(record['id']+'.txt')
    if out.exists(): raise RuntimeError('Choose a new extraction or back up before overwriting')
    out.write_text(record['title']+'\n'+record['url']+'\n\n'+text,encoding='utf-8')
    print(record['id'],len(text),'chars')
