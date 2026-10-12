import re,glob,sys,os
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def text(p):
    d=Document(p); return "\n".join(t.text or "" for t in d.element.body.iter(W+"t"))
def allt(folder):
    return " \n".join(text(p) for p in glob.glob(folder+"/*.docx") if not os.path.basename(p).startswith("~$"))
def tokens(t): return {x.rstrip(",.") for x in re.findall(r"\d[\d,]*\.?\d*%?", t)}
v3=allt(sys.argv[1]); v4=allt(sys.argv[2])
t3,t4=tokens(v3),tokens(v4)
miss=sorted(t for t in t3-t4 if len(t.replace(',','').replace('.',''))>=2)
print(len(t3),len(t4),len(miss))
for t in miss:
    i=v3.find(t); print(repr(t), '|', v3[max(0,i-28):i+22].replace("\n"," "))
