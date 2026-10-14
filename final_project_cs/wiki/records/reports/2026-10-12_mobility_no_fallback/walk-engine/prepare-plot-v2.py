from pathlib import Path
p=Path(__file__).resolve().parent
s=(p/'plot-v1.py').read_text(encoding='utf-8').replace("xy=xy([d['snaps'][1]['snap']])","xy=tuple(z[0] for z in xy([d['snaps'][1]['snap']]))").replace('route-diagnosis-v1','route-diagnosis-v2')
with (p/'plot-v2.py').open('x',encoding='utf-8') as f:f.write(s)
