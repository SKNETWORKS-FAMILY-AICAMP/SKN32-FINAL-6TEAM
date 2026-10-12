# LLM 없는 질문 인식: 규칙(날짜·끼니·시각·종류) → 후보 좁히기 → 임베딩(좁힌 안에서) + 관련성 문턱
# ★새 질문 묶음(HELD)은 규칙을 쓰기 전에 적었다. 규칙 단어는 질문 문장을 보고 고르지 않고 일반 표현 목록으로 적었다.
import json, math, re, time, urllib.request, sys
sys.path.insert(0,'.')
exec(open(sys.argv[1],encoding='utf-8').read().split("NOW=")[0].split("from app.modules")[0])  # imports only
from datetime import datetime, date, timedelta
from types import SimpleNamespace as N
from zoneinfo import ZoneInfo
KST=ZoneInfo('Asia/Seoul')
src=open(sys.argv[1],encoding='utf-8').read()
ns={}; exec(src[src.index("def it("):src.index("NOW=")], {'N':N,'datetime':datetime,'KST':KST}, ns)
ITEMS,Q=ns['ITEMS'],ns['Q']
HELD=[("경복궁 입장료 있어요?",1),("점심에 삼계탕 먹는 곳 예약 몇 시야",2),("카약 체험 준비물 있나요",3),("첫날 밤에 먹는 만두집 어디예요",4),
 ("산에 가는 날 몇 시에 모여요?",5),("시장 구경하는 날 점심 메뉴 뭐예요",6),("둘째 날 오후 전시 보는 곳 어디예요",7),("공연 몇 시에 시작해요?",8),
 ("타워 전망대 올라가는 날이 언제예요?",9),("3일차 점심 뭐 먹어요?",10),("놀이기구 타는 곳 몇 시에 가요?",11),("What time do we go hiking?",5),
 ("Is the kayak booked?",3),("오늘 저녁 뭐해?",None),("호텔 체크인 몇 시예요?",None),("환율 얼마예요?",None)]
NOW=datetime(2026,10,2,20,0,tzinfo=KST)
B='http://127.0.0.1:11434'
def post(p,b,t=300): return json.loads(urllib.request.urlopen(urllib.request.Request(B+p,data=json.dumps(b).encode(),headers={'content-type':'application/json'}),timeout=t).read())
def norm(v): n=math.sqrt(sum(x*x for x in v)); return [x/n for x in v]
def emb(xs): return [norm(v) for v in post('/api/embed',{'model':'bge-m3','input':xs})['embeddings']]
# 관광공사 분류 이름(조회로 얻을 수 있는 값)만 항목 설명에 붙인다 — 질문에 맞춘 별칭은 안 붙인다
CAT={1:'관광지 고궁',2:'음식점 한식',3:'레포츠 수상',4:'음식점 한식',5:'레포츠 등산',6:'쇼핑 전통시장',7:'문화시설 박물관',8:'행사·공연',9:'관광지 전망대',10:'쇼핑 전통시장 음식점',11:'레포츠 테마파크'}
KIND={'activity':'활동','dining':'식사'}
W='월화수목금토일'
days=sorted({i.starts_at.date() for i in ITEMS})
def desc(i): d=i.starts_at; return f"{days.index(d.date())+1}일차 {d.month}월 {d.day}일 {W[d.weekday()]}요일 {d:%H시 %M분} {KIND[i.kind]} {i.title} {i.place['name']} {CAT[i.item_id]}"
IV=emb([desc(i) for i in ITEMS])
ORD={'첫':1,'첫째':1,'둘째':2,'셋째':3,'넷째':4,'다섯째':5,'여섯째':6,'일곱째':7}
EN={'first':1,'second':2,'third':3,'fourth':4,'fifth':5}
def day_of(q):
    if m:=re.search(r'(\d{1,2})월\s*(\d{1,2})일',q): return date(2026,int(m[1]),int(m[2]))
    if m:=re.search(r'(\d)\s*일차',q): k=int(m[1]); return days[k-1] if k<=len(days) else 'none'
    for w,k in ORD.items():
        if re.search(w+r'\s*(날|째 날|날)',q) or (w=='첫' and '첫날' in q): return days[k-1] if k<=len(days) else 'none'
    if re.search(r'마지막\s*날|last day',q,re.I): return days[-1]
    for w,k in EN.items():
        if re.search(w+r'\s+day',q,re.I): return days[k-1]
    if '오늘' in q or 'today' in q.lower(): return NOW.date()
    if '내일' in q or 'tomorrow' in q.lower(): return NOW.date()+timedelta(1)
    return None
SLOT=[(('아침','오전','morning'),6,12),(('점심','lunch'),11,15),(('오후','afternoon'),12,18),(('저녁','밤','dinner','evening','night'),17,24)]
def slot_of(q):
    for ws,a,b in SLOT:
        if any(w in q.lower() for w in ws): return (a,b)
def clock_of(q):
    if m:=re.search(r'(\d{1,2}):(\d{2})',q): return int(m[1])
    if m:=re.search(r'(오후\s*)?(\d{1,2})\s*시(?!간)',q): h=int(m[2]); return h+12 if (m[1] or h<8) and h<12 else h
EAT=('먹','식당','밥','메뉴','맛집','dinner','lunch','breakfast','eat','restaurant')
def kind_of(q): return 'dining' if any(w in q.lower() for w in EAT) else None
def recognize(q, qv, tau):
    d,s,c,k=day_of(q),slot_of(q),clock_of(q),kind_of(q)
    signal = any(x is not None for x in (d,s,c,k))
    pool=ITEMS
    if d=='none': return None
    if d is not None: pool=[i for i in pool if i.starts_at.date()==d]
    if c is not None: pool=[i for i in pool if i.starts_at.hour==c] or pool
    if s is not None: pool=[i for i in pool if s[0]<=i.starts_at.hour<s[1]] or pool
    if k is not None: pool=[i for i in pool if i.kind==k] or pool
    if not pool: return None
    scored=sorted(((sum(a*b for a,b in zip(qv,IV[i.item_id-1])),i.item_id) for i in pool),reverse=True)
    top=scored[0]
    if len(pool)==1 and signal: return top[1]
    return top[1] if (top[0]>=tau or signal) else None
def run(QS, tau):
    QV=emb([q for q,_ in QS]); out=[recognize(q,qv,tau) for (q,_),qv in zip(QS,QV)]
    gold=[g for _,g in QS]; ok=sum(a==g for a,g in zip(out,gold)); rel=[g for g in gold if g is not None]
    okr=sum(a==g for a,g in zip(out,gold) if g is not None); fp=sum(a is not None for a,g in zip(out,gold) if g is None)
    return ok,len(QS),okr,len(rel),fp,len(QS)-len(rel),out
S={'type':'object','properties':{'item':{'type':['integer','null']}},'required':['item']}
def lab(i): d=i.starts_at; return f"{days.index(d.date())+1}일차 {d.month}/{d.day}({W[d.weekday()]}) {d:%H:%M} [{i.kind}] {i.title} @ {i.place['name']}"
plan='\n'.join(f"{i.item_id}. {lab(i)}" for i in ITEMS)
def llm(QS):
    out=[]
    for q,_ in QS:
        b={'model':'gemma4:12b','stream':False,'think':False,'format':S,'options':{'temperature':0},'messages':[{'role':'user','content':
          f"오늘은 2026-10-02 이다. 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n고객 질문: {q}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 일정의 어느 항목과도 관계없는 질문이면 null."}]}
        v=json.loads(post('/api/chat',b)['message']['content']).get('item')
        out.append(v if v in {i.item_id for i in ITEMS} else None)
    gold=[g for _,g in QS]
    return sum(a==g for a,g in zip(out,gold)), sum(a==g for a,g in zip(out,gold) if g is not None), sum(a is not None for a,g in zip(out,gold) if g is None), out
for tau in (0.45,0.50):
    for name,QS in (('처음 22',Q),('새 16',HELD)):
        ok,n,okr,nr,fp,nn,out=run(QS,tau)
        print(f"규칙+임베딩 τ={tau} [{name}] 전체 {ok}/{n} · 항목 있는 질문 {okr}/{nr} · 없는 질문 오짚음 {fp}/{nn}")
ok,n,okr,nr,fp,nn,outR=run(HELD,0.50)
t=time.time(); lok,lokr,lfp,outL=llm(HELD); tl=time.time()-t
print(f"LLM 번호 짚기 [새 16] 전체 {lok}/16 · 항목 있는 질문 {lokr}/13 · 없는 질문 오짚음 {lfp}/3 · {tl/16:.1f}s/질문")
print("\n[새 16] 질문 | 정답 | 규칙+임베딩(0.50) | LLM")
for (q,g),a,b in zip(HELD,outR,outL): print(f"  {q[:24]:<24} | {g} | {a} | {b}")
