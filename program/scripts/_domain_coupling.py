import sys,glob,re,collections,os
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
DOMAIN=re.compile("환불|반품|주문|배송|상담원|쇼핑몰|VOC|고객 문의|취소|택배|커머스")
b=collections.defaultdict(list)
for f in glob.glob("program/wiki/**/*.md",recursive=True):
    n=f.replace(os.sep,"/")
    t=open(f,encoding="utf-8",errors="replace").read()
    parts=n.split("/")
    area=parts[2] if len(parts)>3 else "(루트)"
    b[area].append(len(DOMAIN.findall(t))/max(t.count(chr(10))+1,1)*100)
print("영역".ljust(16),"문서".rjust(4),"밀도".rjust(8)," 성격")
print("-"*54)
for a in sorted(b,key=lambda k:-sum(b[k])/len(b[k])):
    v=b[a]; d=sum(v)/len(v)
    k="★갈아엎어야" if d>6 else "손봐야" if d>2 else "그대로 쓴다"
    print(a.ljust(16),str(len(v)).rjust(4),(f"{d:.1f}%").rjust(8)," ",k)

print()
print("── final_project_cs/wiki ──")
b2=collections.defaultdict(list)
for f in glob.glob("program/final_project_cs/wiki/**/*.md",recursive=True):
    n=f.replace(os.sep,"/"); t=open(f,encoding="utf-8",errors="replace").read()
    parts=n.split("/"); area=parts[3] if len(parts)>4 else "(루트)"
    b2[area].append(len(DOMAIN.findall(t))/max(t.count(chr(10))+1,1)*100)
for a in sorted(b2,key=lambda k:-sum(b2[k])/len(b2[k])):
    v=b2[a]; d=sum(v)/len(v)
    k="★도메인" if d>6 else "혼재" if d>2 else "그대로 쓴다"
    print(a.ljust(16),str(len(v)).rjust(4),(f"{d:.1f}%").rjust(8)," ",k)
print()
tot=sum(len(v) for v in b2.values())
reuse=sum(len(v) for a,v in b2.items() if sum(v)/len(v)<=2)
print(f"cs wiki {tot}건 중 도메인 무관 {reuse}건")
