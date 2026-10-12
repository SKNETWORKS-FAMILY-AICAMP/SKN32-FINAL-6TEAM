import re,glob,sys,os
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
def text(p):
    d=Document(p); return "\n".join(t.text or "" for t in d.element.body.iter(W+"t"))
def allt(folder):
    return " \n".join(text(p) for p in glob.glob(folder+"/*.docx") if not os.path.basename(p).startswith("~$"))
v3=allt(sys.argv[1]); v4=allt(sys.argv[2])
def words(t):
    ids=set(re.findall(r"[A-Za-z_][\w./-]{4,}", t))
    kor=set(re.findall(r"[가-힣]{3,}", t))
    return ids, kor
i3,k3=words(v3); i4,k4=words(v4)
print("영문 식별자 누락:", sorted(i3-i4))
print("한글 낱말(3자+) 누락 수:", len(k3-k4))
print(sorted(k3-k4))
