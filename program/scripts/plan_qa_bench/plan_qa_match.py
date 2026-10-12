import json, time, math, urllib.request, sys
from datetime import datetime
from types import SimpleNamespace as N
from zoneinfo import ZoneInfo
KST=ZoneInfo('Asia/Seoul')
sys.path.insert(0,'.')
from app.modules.travel_ops.itinerary_team import mentioned_item
from app.modules.travel_ops.trip_facts import target
def it(i,d,hm,kind,title,place):
    h,m=map(int,hm.split(':')); return N(item_id=i,seq=i,kind=kind,title=title,place={'name':place},starts_at=datetime(2026,10,d,h,m,tzinfo=KST))
ITEMS=[it(1,3,'10:00','activity','경복궁 관람','경복궁'),it(2,3,'12:30','dining','토속촌 삼계탕','토속촌삼계탕'),
 it(3,3,'15:00','activity','한강 카약 체험','뚝섬한강공원'),it(4,3,'19:00','dining','명동교자 저녁','명동교자 본점'),
 it(5,4,'09:30','activity','북한산 둘레길','북한산 둘레길'),it(6,4,'13:00','dining','광장시장 빈대떡','광장시장'),
 it(7,4,'15:30','activity','국립중앙박물관','국립중앙박물관'),it(8,4,'19:00','activity','난타 공연','명동난타극장'),
 it(9,5,'10:00','activity','N서울타워 전망대','N서울타워'),it(10,5,'12:00','dining','남대문시장 갈치조림','남대문시장'),
 it(11,5,'14:00','activity','롯데월드 어드벤처','롯데월드 어드벤처')]
Q=[("경복궁 몇 시에 가요?",1),("궁궐 구경은 언제예요?",1),("What time is the palace tour?",1),("카약 비 오면 취소돼요?",3),
 ("강에서 노 젓는 거 몇 시예요?",3),("둘째 날 저녁 공연 어디서 해요?",8),("첫날 점심 어디예요?",2),("마지막 날 놀이공원 예약돼 있어요?",11),
 ("빈대떡집 주소 알려주세요",6),("박물관 휴관일 아니에요?",7),("남산타워 몇 시까지 해요?",9),("등산 코스 얼마나 걸려요?",5),
 ("10월 4일 1시에 뭐 먹어요?",6),("Where is dinner on the first day?",4),("갈치 먹는 데 예약 필요해요?",10),("토속촌 몇 명 예약이에요?",2),
 ("롯대월드 몇시에 가",11),("셋째 날 오전 일정 뭐예요?",9),("삼계탕집 가는 길 알려줘",2),
 ("비트코인 시세 알려줘",None),("환불 규정 알려주세요",None),("대한민국 수도가 어디야?",None)]
NOW=datetime(2026,10,2,20,0,tzinfo=KST)
B='http://127.0.0.1:11434'
def post(p,b,t=300): return json.loads(urllib.request.urlopen(urllib.request.Request(B+p,data=json.dumps(b).encode(),headers={'content-type':'application/json'}),timeout=t).read())
W='월화수목금토일'
def label(i): d=i.starts_at; return f"{(d.day-3)+1}일차 {d.month}/{d.day}({W[d.weekday()]}) {d:%H:%M} [{i.kind}] {i.title} @ {i.place['name']}"
res={}
# A1 현행: mentioned_item
res['A1 현행(제목 단어)']=[(getattr(mentioned_item(ITEMS,q),'item_id',None)) for q,_ in Q]
res['A2 현행+날짜(target)']=[(getattr(target(ITEMS,q,NOW)[1],'item_id',None)) for q,_ in Q]
# B 임베딩
def norm(v): n=math.sqrt(sum(x*x for x in v)); return [x/n for x in v]
t=time.time(); IV=[norm(v) for v in post('/api/embed',{'model':'bge-m3','input':[label(i) for i in ITEMS]})['embeddings']]
QV=[norm(v) for v in post('/api/embed',{'model':'bge-m3','input':[q for q,_ in Q]})['embeddings']]; tb=time.time()-t
best=[]; 
for qv in QV:
    s=sorted(((sum(a*b for a,b in zip(qv,iv)),i.item_id) for iv,i in zip(IV,ITEMS)),reverse=True); best.append(s[0])
res['B 임베딩 1위']=[b[1] for b in best]
# C LLM pointer
plan='\n'.join(f"{i.item_id}. {label(i)}" for i in ITEMS)
S={'type':'object','properties':{'item':{'type':['integer','null']}},'required':['item']}
C=[]; t=time.time()
for q,_ in Q:
    b={'model':'gemma4:12b','stream':False,'think':False,'format':S,'options':{'temperature':0},'messages':[{'role':'user','content':
      f"여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n고객 질문: {q}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. 일정의 어느 항목과도 관계없는 질문이면 null."}]}
    C.append(json.loads(post('/api/chat',b)['message']['content']).get('item'))
tc=time.time()-t
res['C LLM 번호 짚기']=C
gold=[g for _,g in Q]
print(f"질문 {len(Q)}개 (가리키는 항목 있음 {sum(g is not None for g in gold)} · 없음 {sum(g is None for g in gold)})")
for k,v in res.items():
    ok=sum(a==g for a,g in zip(v,gold)); okr=sum(a==g for a,g in zip(v,gold) if g is not None); fp=sum(a is not None for a,g in zip(v,gold) if g is None)
    print(f"{k}: 전체 {ok}/{len(Q)} · 항목 있는 질문 {okr}/{sum(g is not None for g in gold)} · 없는 질문에 항목 짚음 {fp}/{sum(g is None for g in gold)}")
print(f"임베딩 시간 {tb:.2f}s(항목 11 + 질문 22), LLM 시간 {tc:.1f}s / 22 = {tc/22:.1f}s/질문")
print("임베딩 1위 점수 — 맞음:", sorted(round(b[0],3) for b,g in zip(best,gold) if g is not None and b[1]==g))
print("                 틀림:", sorted(round(b[0],3) for b,g in zip(best,gold) if g is not None and b[1]!=g))
print("                 항목 없는 질문:", sorted(round(b[0],3) for b,g in zip(best,gold) if g is None))
print('\n질문별: 정답 | A1 A2 B C')
for (q,g),a1,a2,b,c in zip(Q,*res.values()):
    print(f"  {q[:26]:<26} | {g} | {a1} {a2} {b} {c}")
