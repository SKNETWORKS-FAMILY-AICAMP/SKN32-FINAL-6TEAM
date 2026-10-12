# -*- coding: utf-8 -*-
"""Claude 판 멘토 발표 자료 — claude/index.html 을 만든다. 숫자는 assets/facts.md 에 있는 것만 쓴다."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from svgkit import Flow

HERE = Path(__file__).parent
OUT = Path(r"C:\Users\playdata2\Documents\final_workspace\program\산출물양식\w4\멘토발표_2026-10-02\claude\index.html")
A = "../assets/"
S = []


def slide(body, notes="", cls=""):
    S.append(f'<section class="slide {cls}">{body}<div class="notes">{notes}</div></section>')


def phone(img, cap="", step=0, w=250):
    h = int(w * 2.16)
    return (f'<div class="{"step " if step else ""}col" style="align-items:center;gap:12px">'
            f'<div class="phone" style="width:{w}px;height:{h}px"><img src="{A}{img}" alt=""></div>'
            + (f'<div class="small" style="text-align:center;max-width:{w + 40}px;color:#1d2a23;font-weight:600">{cap}</div>' if cap else "") + "</div>")


# 1. 표지 ---------------------------------------------------------------
slide(f'''
<div class="row" style="height:100%;align-items:center;gap:60px">
  <div style="flex:1">
    <div class="kicker">A-COPilot · 멘토링 2026-10-02</div>
    <h1>계획은 여행자가,<br><span class="hl">지키는 건 triPilot이.</span></h1>
    <p class="lead" style="margin-top:30px">외국인 자유여행자가 만든 여행 계획을 받아<br>여행이 끝날 때까지 지켜보는 여행 운영 에이전트</p>
    <div class="row" style="margin-top:44px;gap:14px"><span class="pill">서울 · 최대 7일 · 4인</span><span class="pill gold">팀당 49,000원</span><span class="pill blue">지금 실제로 동작</span></div>
  </div>
  <div class="row" style="gap:26px;align-items:flex-end">
    {phone("s1_home.jpg", w=230)}
    <div style="margin-bottom:60px">{phone("s3_choice.jpg", w=250)}</div>
  </div>
</div>''', "오늘은 개발 구조가 아니라 ‘누구의 어떤 문제를, 어떻게 풀고, 얼마나 잘 푸는지’를 보여 드립니다. 오른쪽은 지금 돌아가는 실제 화면입니다.")

# 2. 역지사지 -------------------------------------------------------------
nine = ["문제 발견", "검색", "번역", "영업 확인", "대안 찾기", "이동 다시 계산", "예약 충돌 확인", "일정 고치기", "동행자에게 공유"]
chips = "".join(f'<div class="step card" style="padding:16px 20px;font-size:24px;font-weight:700;display:flex;gap:14px;align-items:center"><span class="mid" style="font-size:30px;color:var(--gold)">{i + 1}</span>{t}</div>' for i, t in enumerate(nine))
slide(f'''
<div class="kicker">왜 필요한가</div>
<h2>일본 여행 둘째 날,<br>1시에 예약한 식당이 <span class="warn">임시휴무</span>입니다. 3시엔 체험 예약이 있습니다.</h2>
<p class="lead" style="margin:10px 0 30px">혼자라면, 지금부터 이걸 다 해야 합니다.</p>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">{chips}</div>
<p class="step lead" style="margin-top:30px;color:var(--ink);font-weight:700">외국인에게 식당 하나는 <span class="warn">남은 하루 전체를 다시 검증</span>하는 일이 됩니다.</p>''',
      "심사위원 자신의 해외여행 경험에서 출발합니다. 한 번 클릭할 때마다 9단계가 하나씩 쌓입니다.")

# 3. 데이터 ---------------------------------------------------------------
slide('''
<div class="kicker">문제의 크기</div>
<h2>대부분 혼자 다니고, 현지에서 다시 찾고, 다시 짭니다</h2>
<div class="row" style="margin-top:40px;gap:24px">
  <div class="step card" style="flex:1"><div class="mid">1,893.7<span style="font-size:34px">만</span></div><div class="small" style="margin-top:14px;color:#1d2a23;font-weight:700">2025년 방한 외래객</div><div class="small">야놀자리서치</div></div>
  <div class="step card" style="flex:1"><div class="mid">82.9<span style="font-size:34px">%</span></div><div class="small" style="margin-top:14px;color:#1d2a23;font-weight:700">개별여행 비중</div><div class="small">2025년 1분기 · 2019년 77.1%</div></div>
  <div class="step card" style="flex:1"><div class="mid">96.4<span style="font-size:34px">%</span></div><div class="small" style="margin-top:14px;color:#1d2a23;font-weight:700">현지에서 정보를 다시 검색</div><div class="small">야놀자리서치</div></div>
  <div class="step card" style="flex:1"><div class="mid warn">42.5<span style="font-size:34px">%</span></div><div class="small" style="margin-top:14px;color:#1d2a23;font-weight:700">현지에서 일정 변경</div><div class="small">야놀자리서치</div></div>
</div>
<div class="step row" style="margin-top:34px;gap:40px;align-items:center">
  <div style="flex:1.3">
    <div class="small" style="font-weight:700;color:#1d2a23;margin-bottom:10px">만족도, 여행 전 → 현장</div>
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:10px"><div style="height:30px;width:84.6%;max-width:560px;background:var(--g2);border-radius:6px"></div><b style="font-size:26px">84.6%</b></div>
    <div style="display:flex;align-items:center;gap:14px"><div style="height:30px;width:70.8%;max-width:469px;background:var(--red);border-radius:6px"></div><b style="font-size:26px" class="warn">70.8%</b></div>
  </div>
  <div class="card" style="flex:1"><div class="small" style="font-weight:700;color:#1d2a23">불편 언급 비율</div><div class="row" style="gap:30px;margin-top:8px"><div><div class="mid" style="font-size:52px">11%</div><div class="small">한국</div></div><div><div class="mid" style="font-size:52px;color:#9aa39d">7%</div><div class="small">일본</div></div></div><div class="small">한국은 예약·지도검색·결제 단계에서 막힌다</div></div>
</div>
<div class="src">출처: 야놀자리서치 브리프 705·558(원자료 문체부 외래관광객조사), 야놀자리서치 2026-05 보도. 숫자는 팀 조사 문서에서 옮김.</div>''',
      "앞단에서 데이터를 한 번에 설명하라는 지적 반영. 개별여행이 대부분이고, 현지에서 절반 가까이 일정을 바꾸며, 그만큼 만족도가 떨어집니다.")

# 4. 페르소나 ---------------------------------------------------------------
tl = [("09:00", "경복궁", "", ""), ("12:00", "성수 점심", "임시휴무", "요식"), ("15:00", "잠실 전망대", "미세먼지·소나기", "액티비티"), ("22:30", "숙소로", "역 무정차 · 막차", "이동")]
items = ""
for i, (t, p, ev, ag) in enumerate(tl):
    left = 60 + i * 340
    items += f'<div style="position:absolute;left:{left}px;top:0;width:300px"><div class="small" style="font-weight:700">{t}</div><div style="font-size:28px;font-weight:800;margin-top:6px">{p}</div></div>'
    if ev:
        items += (f'<div class="step" style="position:absolute;left:{left}px;top:140px;width:290px"><div class="card" style="border-color:var(--red);background:var(--red2);padding:18px 20px">'
                  f'<div style="font-size:24px;font-weight:800" class="warn">{ev}</div><div class="small" style="margin-top:6px">→ <b style="color:var(--g1)">{ag} 에이전트</b>가 먼저 봅니다</div></div></div>')
slide(f'''
<div class="kicker">누구의 문제인가</div>
<div class="row" style="gap:40px;align-items:center">
  <div class="card" style="width:430px;background:var(--g1);color:#fff;border:none">
    <div style="font-size:18px;opacity:.8;font-weight:700">대표 고객 (예시 인물)</div>
    <div style="font-size:40px;font-weight:800;margin:10px 0">대만에서 온 친구 2명</div>
    <div style="font-size:22px;line-height:1.7;opacity:.95">K-콘텐츠로 온 첫 서울 · 한국어 못함<br>쇼핑·맛집 자유여행 · 앱 여러 개를 번갈아 씀</div>
  </div>
  <p class="lead" style="flex:1">여행 계획은 이미 <b style="color:#1d2a23">본인이 다 짰습니다.</b><br>문제는 <b class="warn">여행 중에</b> 계획이 깨질 때입니다.</p>
</div>
<div style="position:relative;height:300px;margin-top:50px">
  <div style="position:absolute;left:40px;right:40px;top:92px;height:4px;background:var(--line)"></div>
  {items}
</div>
<div class="src">대표 시연 시나리오(계획서 v11 §8-A): 잠실 → 성수 → 경복궁 → 롯데마트, 사건 6개(기상 · 역 화재 무정차 · 70분 지연 · 구역 통제 · 임시휴무 · 품절) 중 셋.</div>''',
      "현실적인 페르소나 지적 반영. 이 두 사람의 하루에 실제로 생길 수 있는 사건 세 개를, 각각 어느 에이전트가 먼저 보는지로 연결합니다.")

# 5. 무엇을 하나 -----------------------------------------------------------------
three = [("1", "올린다", "쓰던 그대로 올리면<br>일정으로 읽어 등록", "글 · 사진 · PDF · 워드 · 엑셀", "s2_upload.jpg"),
         ("2", "지킨다", "하루 시작 · 출발 전 · 변경 직후<br>스스로 다시 확인", "영업시간 · 휴무 · 날씨 · 막차", "s4_schedule.jpg"),
         ("3", "알린다", "대안을 먼저 적용하고<br>다른 안 3개를 함께", "디스코드 알림 · 늘 최신인 여행계획서 링크", "s5_alerts.jpg")]
cols = ""
for n, t, d, sub, img in three:
    cols += (f'<div class="step card" style="flex:1;display:flex;gap:22px;align-items:center;padding:26px">'
             f'<div style="flex:1"><div class="mid" style="font-size:56px;color:var(--gold)">{n}</div><div style="font-size:40px;font-weight:800;margin:8px 0 12px">{t}</div>'
             f'<div style="font-size:23px;line-height:1.5;font-weight:600">{d}</div><div class="small" style="margin-top:14px">{sub}</div></div>'
             f'<div class="phone" style="width:150px;height:324px;border-radius:26px;padding:6px"><img src="{A}{img}" style="border-radius:21px"></div></div>')
slide(f'''
<div class="kicker">triPilot이 하는 일</div>
<h2>계획을 만들어 주는 앱이 아니라, <span class="hl">이미 있는 계획을 지키는 에이전트</span></h2>
<div class="row" style="margin-top:40px;gap:24px">{cols}</div>
<p class="small" style="margin-top:26px">계획이 없으면 짜 주기도 합니다 — 서울 3일 2인 요청 시 후보 1,779곳 중 12곳을 골라 등록.</p>''',
      "기능이 뭔지 모르겠다는 지적 반영. 올린다·지킨다·알린다 세 동사로만 설명합니다.")

# 6. 비교 --------------------------------------------------------------------------
rows = [("TripIt Pro", "항공편", "항공 지연·취소 알림", "식당·활동 영향은 확인 못 함", "연 $49"),
        ("TripMazer", "여행 일정", "날씨·파업·지연 감시", "AI 제안은 약관상 추정치", "—"),
        ("Tripsy", "여행 일정", "일정 편집(API)", "자동 감지→재제안 루프 확인 못 함", "—"),
        ("토모트래블 (사람)", "설계 상담", "사람이 일정 설계", "여행 중 실시간 감시는 사람 몫", "29,000원~249,000원"),
        ("triPilot", "내 계획 전체", "식당·활동·이동을 스스로 재확인", "대안 적용 + 다른 안 3개 + 알림", "팀당 49,000원")]
trs = ""
for i, r in enumerate(rows):
    me = r[0] == "triPilot"
    st = "background:var(--g1);color:#fff;" if me else ""
    trs += (f'<tr class="step" style="{st}"><td style="font-weight:800;font-size:26px">{r[0]}</td>' + "".join(f'<td>{c}</td>' for c in r[1:]) + "</tr>")
slide(f'''
<div class="kicker">무엇이 다른가</div>
<h2>겹치는 경쟁자와 <span class="hl">사람이 해 주는 서비스</span>만 비교했습니다</h2>
<table class="cmp"><thead><tr><th>서비스</th><th>무엇을 지키나</th><th>하는 것</th><th>여행 중 문제가 생기면</th><th>가격</th></tr></thead><tbody>{trs}</tbody></table>
<p class="small" style="margin-top:20px">「확인 못 함」은 기능이 없다는 뜻이 아니라, 공개 자료와 팀의 직접 시험에서 확인하지 못했다는 뜻입니다.<br>팀 조사 실제 사례: KAYAK은 추석 롯데마트 서울역점 휴무를 몰랐고, Tripomatic은 트릭아이미술관 영업시간이 틀렸습니다.</p>
<style>.cmp{{width:100%;border-collapse:separate;border-spacing:0 8px;margin-top:26px;font-size:21px}}.cmp th{{text-align:left;color:var(--muted);font-size:18px;padding:0 18px}}.cmp td{{padding:16px 18px;background:var(--paper)}}.cmp tr[style] td{{background:transparent}}.cmp td:first-child{{border-radius:14px 0 0 14px}}.cmp td:last-child{{border-radius:0 14px 14px 0;font-weight:700}}</style>''',
      "실제 타겟이 겹치는 경쟁사만, 그리고 사람이 해 주는 서비스(토모트래블)까지 비교. 과장하지 않기 위해 ‘확인 못 함’으로 표현합니다.")

# 7·8. 유스케이스 ---------------------------------------------------------------
slide(f'''
<div class="kicker">유스케이스 ① 여행 전 — 들어와서 올리기까지</div>
<h2>로그인 없이, 계획을 붙여 넣으면 끝</h2>
<div class="row" style="margin-top:26px;gap:34px;align-items:flex-start;justify-content:center">
  {phone("s1_home.jpg", "① 첫 화면 — 언어 고르고<br>「내 여행」만 보인다", 1, 230)}
  <div class="step col" style="width:300px;margin-top:40px">
    <div class="card"><div style="font-size:26px;font-weight:800">② 설문 6문항</div><div class="small" style="margin-top:8px">테마 · 누구와 · 우선순위 · 실내/실외 · 여유<br><b style="color:var(--g1)">일정이 꼬이면: 바꿔 줘 / 먼저 물어봐</b></div></div>
    <div class="small" style="text-align:center">이메일은 저장하지 않습니다<br>(브라우저에 열쇠 하나만)</div>
  </div>
  {phone("s2_upload.jpg", "③ 쓰던 계획을 그대로<br>글 · 사진 · 파일 5개까지", 1, 230)}
  <div class="step col" style="width:300px;margin-top:40px">
    <div class="card"><div style="font-size:26px;font-weight:800">④ 함께 확인</div><div class="small" style="margin-top:8px">읽은 항목마다 근거 표시<br>고치기 · 빼기 → <b style="color:var(--g1)">등록하고 관리 시작</b></div></div>
    <div class="card" style="background:var(--g3)"><div style="font-size:22px;font-weight:800">등록 즉시</div><div class="small">디스코드 알림 + 로그인 없이 열리는<br>여행계획서 링크(늘 최신)</div></div>
  </div>
</div>''', "첫 화면에는 일정 보기와 버튼만 — 멘토 지적 반영. 사용자가 실제로 보는 화면 순서 그대로입니다.")

slide(f'''
<div class="kicker">유스케이스 ② 여행 중 — 문제가 생기면</div>
<h2>먼저 고쳐 두고, 고를 수 있게 알려 줍니다</h2>
<div class="row" style="margin-top:22px;gap:30px;justify-content:center;align-items:flex-start">
  {phone("s3_choice.jpg", "선택이 필요해요 — 먼저 바꾼 안<br>+ 다른 안 3개 + 그대로 두기", 1, 230)}
  {phone("s5_alerts.jpg", "받은 알림 — 변경 · 선택 요청<br>· 출발 안내", 1, 230)}
  {phone("s6_map.jpg", "지도 — 일차별 번호 핀", 1, 230)}
  {phone("s7_chat.jpg", "채팅 — 하루 요약 · 다음 일정<br>이동은 시간표로 판정", 1, 230)}
</div>
<div class="step card" style="margin-top:14px;padding:16px 24px;font-size:21px"><b>실제 알림 문구</b> · 「요청하신 대로 페스타 바이 중후 대신 서울다이닝(으)로 바꿨습니다(12:00 시작). 다른 안: 1) 필동면옥 · 2) 평안도족발집 · 3) 12:30으로 늦추면 송원. <b class="hl">답이 없으면 지금대로 둡니다.</b>」</div>''',
      "알림은 승인 요청이 아닙니다. 최선안을 먼저 적용하고, 마음에 안 들면 고르게 합니다. 알림을 못 봐도 여행계획서 링크가 늘 최신입니다.")

# 9. LLM vs 에이전트 ------------------------------------------------------------
f = Flow(1420, 470)
f.node("q", 40, 170, 200, 90, "질문", "ghost", 1, 24)
f.node("a", 330, 170, 200, 90, "답 한 번", "ghost", 1, 24)
f.edge("q", "a", step=1)
f.label(40, 330, "시각을 스스로 모름 · 틀려도 확인 안 함", 19, "#8a938d", 1)
loop = [("w", 690, 40, "① 스스로 깨어남\n시각 · 사건 · 앞 에이전트", "trig"), ("t", 1020, 40, "② 일감 받기\n무슨 일 · 지킬 것 · 도구", "proc"),
        ("c", 1100, 200, "③ 조회\n시간표 · 영업시간 · API", "dec"), ("j", 1020, 350, "④ 따져 보기\n최대 6단계 반복", "proc"),
        ("act", 690, 350, "⑤ 행동\n일정 새 판 · 알림", "out"), ("m", 610, 200, "⑥ 답 기다림\n다음 변경에 다시", "agent")]
for k, x, y, t, kd in loop:
    f.node(k, x, y, 290 if k != "c" else 280, 90, t, kd, 2, 20)
f.edge("w", "t", step=2); f.edge("t", "c", "r", "t", step=2); f.edge("c", "j", "b", "r", step=2); f.edge("j", "act", "l", "r", step=2); f.edge("act", "m", "l", "b", step=2); f.edge("m", "w", "t", "l", step=2)
f.label(40, 40, "LLM 호출", 30, "#6f7872", 1, weight=800)
f.label(610, 20, "에이전트", 30, "#2d5f48", 2, weight=800)
slide(f'''
<div class="kicker">LLM 호출과 에이전트는 무엇이 다른가</div>
<h2>물으면 답하는 것이 아니라, <span class="hl">스스로 깨어나 확인하고 행동</span>합니다</h2>
<div style="height:500px;margin-top:10px">{f.svg()}</div>
<div class="step card" style="padding:16px 24px;font-size:23px;background:var(--gold2);border-color:#e7c98f"><b>원칙: 판정은 코드가, 말은 LLM이.</b> 시각·영업시간·막차는 시간표와 데이터로 계산하고, LLM이 짓지 않습니다.</div>''',
      "멘토가 두 번 물은 질문. 에이전트는 트리거로 깨어나 도구로 확인하고 결과를 남기고 기다리는 루프입니다.")

# 10. 사람 팀 --------------------------------------------------------------
people = [("계획 읽기", "여행사 접수 담당", "받은 계획서를 한 줄씩 옮겨 적고 모호한 것만 묻는다", "gold"),
          ("요식 에이전트", "맛집 컨시어지", "영업·브레이크·라스트오더를 확인하고 대신 갈 곳을 고른다", ""),
          ("액티비티 에이전트", "현지 가이드", "휴무·날씨를 보고 비슷한 활동으로 바꾼다", ""),
          ("이동 에이전트", "교통 안내원", "시간표로 제시간 도착을 계산하고 막차를 챙긴다", "blue")]
cards = "".join(f'<div class="step card" style="width:330px"><span class="pill {c}">{n}</span><div style="font-size:30px;font-weight:800;margin:14px 0 8px">{p}</div><div class="small" style="color:#1d2a23">{d}</div></div>' for n, p, d, c in people)
slide(f'''
<div class="kicker">에이전트 = 여행 매니저 팀의 사람들</div>
<h2>사람이 하던 여행 관리를 <span class="hl">역할별로 쪼갰습니다</span></h2>
<div class="row" style="margin-top:36px;align-items:center;gap:30px">
  <div class="card" style="width:330px;background:var(--g1);color:#fff;border:none;text-align:center;padding:40px 26px">
    <div style="font-size:18px;opacity:.8;font-weight:700">코어</div><div style="font-size:40px;font-weight:800;margin:10px 0">여행 매니저</div>
    <div style="font-size:20px;line-height:1.6;opacity:.95">언제 볼지 정하고, 누구에게 맡길지 고르고,<br>결과를 확인해 일정에 반영·안내</div></div>
  <div style="flex:1;display:grid;grid-template-columns:1fr 1fr;gap:20px">{cards}</div>
</div>
<p class="small" style="margin-top:24px">전문 에이전트끼리는 직접 부르지 않습니다. 모든 요청과 결과는 매니저(코어)를 거칩니다 — 누가 무엇을 바꿨는지가 한 곳에 남습니다.</p>''',
      "에이전트 하나하나를 사람으로 보라는 지적 반영. 실제 여행사·컨시어지가 하는 일을 역할별로 나눈 구조입니다.")

# 11. 공동 플로우 -----------------------------------------------------------------
g = Flow(1440, 640)
trig = ["하루 시작 08:00", "하루 종료 22:00", "일정 생성·변경 직후", "사용자 요청", "새벽 3시 정기 확인"]
for i, t in enumerate(trig):
    g.node(f"t{i}", 0, 20 + i * 92, 210, 66, t, "trig", 1, 18)
g.node("rng", 270, 220, 190, 90, "확인 범위 선택\n다음 · 오늘 · 이후 전부", "dec", 2, 18)
g.node("pick", 270, 380, 190, 76, "점검할 곳 추리기", "proc", 2, 18)
for i in range(5):
    g.edge(f"t{i}", "rng", step=2)
g.edge("rng", "pick", "b", "t", step=2)
ag = [("요식", "영업·브레이크·라스트오더"), ("액티비티", "휴무·운영·날씨"), ("이동", "제시간·막차·환승")]
for i, (n, d) in enumerate(ag):
    g.node(f"a{i}", 520, 110 + i * 150, 230, 96, f"{n} 에이전트\n{d}", "agent", 3, 18)
    g.edge("pick", f"a{i}", "r", "l", step=3)
g.node("db", 810, 200, 170, 76, "데이터 조회", "proc", 4, 19)
g.node("alt", 810, 320, 170, 90, "실패하면\n다른 소스로", "fail", 4, 18)
for i in range(3):
    g.edge(f"a{i}", "db", step=4)
g.edge("db", "alt", "b", "t", step=4)
g.node("q", 1030, 200, 170, 90, "방문에\n문제 있나?", "dec", 5, 20)
g.edge("db", "q", step=5)
g.node("keep", 1030, 40, 170, 70, "그대로 유지", "ghost", 5, 19)
g.edge("q", "keep", "t", "b", step=5, text="없음")
g.node("rep", 1030, 360, 170, 130, "대체 검토\n1 비슷한 곳\n2 취향 반영\n3 가까운 곳", "proc", 6, 18)
g.edge("q", "rep", "b", "t", step=6, text="있음")
g.node("apply", 1255, 250, 180, 110, "먼저 적용\n+ 다른 안 3개\n(허용 범위 안)", "out", 7, 18)
g.edge("rep", "apply", step=7)
g.node("tell", 1255, 430, 180, 90, "알림 ·\n여행계획서 갱신", "out", 7, 18)
g.edge("apply", "tell", "b", "t", step=7)
g.edge("tell", "t2", "b", "b", step=8, via=[(1345, 600), (105, 600)], text="고객 답 → 다시 「변경 직후」로")
slide(f'''
<div class="kicker">에이전트 공동 플로우 · 피그마 「액티비티&요식업 공통플로우」 기반</div>
<h2 style="font-size:44px">언제 깨어나서 → 무엇을 보고 → 어떻게 바꾸나</h2>
<div style="height:650px;margin-top:6px">{g.svg()}</div>''',
      "트리거·입력·출력을 전체 에이전트 흐름에서 보여 달라는 지적 반영. 클릭마다 트리거 → 범위 → 에이전트별 점검 → 조회(실패 시 대체 소스) → 판단 → 대체 → 적용·알림 순으로 나타납니다. 조회가 끝까지 실패하면 조용히 넘기지 않고 ‘확인 필요’로 알립니다.")


# 12~15 에이전트별 ---------------------------------------------------------------
def agent_slide(kicker, title, nodes, edges, side, notes, h=520):
    fl = Flow(980, h)
    for k, x, y, w, hh, t, kd, st in nodes:
        fl.node(k, x, y, w, hh, t, kd, st, 18)
    for e in edges:
        fl.edge(*e[:4], step=e[4], text=(e[5] if len(e) > 5 else None))
    slide(f'''<div class="kicker">{kicker}</div><h2 style="font-size:44px">{title}</h2>
<div class="row" style="margin-top:16px;gap:30px;align-items:flex-start"><div style="width:980px;height:{h + 20}px">{fl.svg()}</div><div style="flex:1" class="col">{side}</div></div>''', notes)


agent_slide("에이전트 ① 계획 읽기 · 여행사 접수 담당", "쓰던 그대로 올려도, <span class='hl'>근거 있는 값</span>만 일정이 됩니다",
            [("in", 0, 40, 200, 90, "글 · 사진\nPDF · 워드 · 엑셀", "trig", 1),
             ("ocr", 260, 40, 210, 90, "사진은 한 줄씩\n받아쓰기(2번 대조)", "proc", 2),
             ("rule", 530, 40, 200, 90, "규칙이 먼저 읽기\n시각·일차·예약번호", "proc", 3),
             ("llm", 530, 200, 200, 110, "남은 줄만 LLM이\n원문 위치를 가리킴\n(없는 말은 버림)", "dec", 4),
             ("place", 260, 200, 210, 110, "장소 하나로 정하기\n우리 표 → 별칭 →\n오타 → 관광공사", "proc", 5),
             ("chk", 0, 360, 200, 90, "고객 확인 화면\n고치기 · 빼기", "agent", 6),
             ("out", 260, 360, 470, 90, "일정 등록 — 항목마다 값 · 방법 · 근거(원문 줄)", "out", 7)],
            [("in", "ocr", "r", "l", 2), ("ocr", "rule", "r", "l", 3), ("rule", "llm", "b", "t", 4), ("llm", "place", "l", "r", 5), ("place", "chk", "l", "t", 6), ("chk", "out", "r", "l", 7)],
            '<div class="step card"><div class="mid">97.0%</div><div class="small">항목 재현율 326/336 (합성 평가셋 60건, 1회차 90.2%)</div></div>'
            '<div class="step card"><div class="mid">0<span style="font-size:30px">/1,828</span></div><div class="small">근거 없는 값</div></div>'
            '<div class="step card" style="border-color:var(--red)"><div class="mid warn" style="font-size:48px">3.4%</div><div class="small">값 변조(목표 0 미달) — 사진 속 긴 가게 이름 오독. 형식별 재현율: 사진 91.2%</div></div>',
            "코어의 첫 에이전트. LLM에게 값을 짓게 하지 않고, 원문 몇 번째 줄 몇 번째 글자인지만 가리키게 한 것이 핵심입니다. 약점(값 변조 3.4%)도 그대로 보여 줍니다.", 470)

agent_slide("에이전트 ② 요식 · 맛집 컨시어지", "식사가 <span class='hl'>성립하는지</span> 먼저 계산하고, 안 되면 대신 갈 곳을 고릅니다",
            [("t1", 0, 20, 210, 66, "일정 변경 직후", "trig", 1), ("t2", 0, 100, 210, 66, "지연·휴무 신고", "trig", 1), ("t3", 0, 180, 210, 66, "새벽 3시 확인", "trig", 1),
             ("chk", 270, 80, 230, 120, "요일별 영업시간\n브레이크 · 휴무\n라스트오더", "agent", 2),
             ("lo", 270, 250, 230, 110, "라스트오더 규칙\n도착+20분 넘으면 탈락\n모르면 60분 전 경고", "dec", 3),
             ("ok", 560, 20, 190, 66, "그대로 유지", "ghost", 4),
             ("alt", 560, 130, 200, 120, "대체 후보 축별로\n덜 밀리는 곳\n비슷한 곳 · 가까운 곳", "proc", 4),
             ("out", 800, 130, 180, 120, "하나 먼저 적용\n나머지는\n「다른 안」", "out", 5),
             ("go", 560, 300, 420, 70, "이동 에이전트가 앞뒤 이동을 다시 계산", "agent", 6)],
            [("t1", "chk", "r", "l", 2), ("t2", "chk", "r", "l", 2), ("t3", "chk", "r", "l", 2), ("chk", "lo", "b", "t", 3), ("chk", "ok", "r", "l", 4, "성립"), ("chk", "alt", "r", "l", 4, "불성립"), ("alt", "out", "r", "l", 5), ("out", "go", "b", "t", 6)],
            '<div class="step card"><div class="mid">1,225<span style="font-size:30px">곳</span></div><div class="small">서울 식당 목록 (관광공사 음식점 + 비건·할랄·미쉐린)</div></div>'
            '<div class="step card"><div class="mid">99<span style="font-size:30px">/100</span></div><div class="small">영업시간 사람 대조 일치 (개선 전 87%)</div></div>'
            '<div class="step card" style="border-color:var(--red)"><div style="font-size:22px;font-weight:800" class="warn">실시간 웨이팅 API 없음</div><div class="small">캐치테이블 등은 자동 수집 안 함 → 지도 링크로 확인. 낮 임시휴무 자동 감지는 다음 단계(지금은 고객 신고로)</div></div>',
            "예시(자료): 점심 70분 지연 → 브레이크타임에 걸림 → 도보 6분 식당으로. 멘토가 물은 ‘대기시간 API가 들어가 있나’에 대한 답: 없음, 링크로 대신.", 400)

agent_slide("에이전트 ③ 액티비티 · 현지 가이드", "휴무·날씨로 못 가게 되면, <span class='hl'>가장 비슷한 활동</span>부터 찾습니다",
            [("t", 0, 60, 200, 90, "운영 공지 변동\n날씨·대기질 경보", "trig", 1),
             ("chk", 250, 50, 220, 110, "운영일 · 운영시간\n휴무 · 날씨 조건", "agent", 2),
             ("base", 250, 230, 220, 120, "공통 기준\n대분류·중분류·소분류\n구 · 운영시간 · 휴무일", "dec", 3),
             ("p1", 530, 200, 220, 70, "1순위 소분류만 다른 곳", "proc", 4),
             ("p2", 530, 285, 220, 70, "2순위 중분류까지 다른 곳", "proc", 4),
             ("p3", 530, 370, 220, 70, "3순위 구가 다른 곳", "proc", 4),
             ("out", 790, 250, 190, 120, "대체 이유와 함께\n적용 · 안내", "out", 5)],
            [("t", "chk", "r", "l", 2), ("chk", "base", "b", "t", 3, "문제 있음"), ("base", "p1", "r", "l", 4), ("base", "p2", "r", "l", 4), ("base", "p3", "r", "l", 4), ("p1", "out", "r", "l", 5), ("p2", "out", "r", "l", 5), ("p3", "out", "r", "l", 5)],
            '<div class="step card"><div class="mid">805<span style="font-size:30px">행</span></div><div class="small">관광공사 서울 활동 후보 (자연·인문·레포츠·쇼핑)</div></div>'
            '<div class="step card"><div style="font-size:24px;font-weight:800">예시 (자료)</div><div class="small" style="margin-top:6px;color:#1d2a23">잠실 전망대 → 미세먼지·소나기 경보 → 실내 아쿠아리움</div></div>'
            '<div class="step card" style="border-color:var(--red)"><div class="small"><b class="warn">한계</b> — 추천 적합도를 사람이 평가한 자료는 아직 없음</div></div>',
            "피그마의 ‘액티비티 대체장소 우선순위 결정’ 그대로입니다. 같은 대분류를 고정하고, 소분류 → 중분류 → 지역 순으로 조건을 풀어 가며 찾습니다.", 460)

agent_slide("에이전트 ④ 이동 · 교통 안내원 (모든 에이전트가 쓰는 이동 판정기)", "제시간에 도착하는지 <span class='hl'>시간표로 계산</span>합니다",
            [("a", 0, 10, 220, 70, "일정 짜기 (처음)", "trig", 1), ("b", 0, 95, 220, 70, "식당 바꿀 때 앞뒤", "trig", 1),
             ("c", 0, 180, 220, 70, "활동 바꿀 때 앞뒤", "trig", 1), ("d", 0, 265, 220, 70, "운행 중단 · 무정차 뒤", "trig", 1),
             ("calc", 280, 90, 250, 170, "시간표 판정\n지하철·버스 46만 행\n역 출구 · 환승 도보\n따릉이 · 혼잡", "agent", 2),
             ("q", 590, 130, 150, 90, "제시간?", "dec", 3),
             ("ok", 790, 30, 190, 120, "성립\n출발 시각 · 경로\n요금을 일정에", "out", 4),
             ("ng", 790, 200, 190, 120, "불가\n막차·배차 이유\n→ 다른 경로·시간", "fail", 4),
             ("grade", 280, 330, 700, 60, "모든 답에 근거 등급 — 확정(시간표) · 추정(통계) · 근거 없음(말하지 않음) + 확인 시각", "dec", 5)],
            [("a", "calc", "r", "l", 2), ("b", "calc", "r", "l", 2), ("c", "calc", "r", "l", 2), ("d", "calc", "r", "l", 2), ("calc", "q", "r", "l", 3), ("q", "ok", "r", "l", 4), ("q", "ng", "r", "l", 4)],
            '<div class="step card"><div class="mid">168<span style="font-size:30px">/168</span></div><div class="small">판정 회귀 시험 어긋남 0 · 자동 생성 점검 12,032건</div></div>'
            '<div class="step card"><div class="small" style="color:#1d2a23">실제 채팅 답: 「09:04 출발 · 2호선 신대방→을지로3가 → 3호선 → 경복궁 · 약 62분 <b>(시간표 판정)</b>」</div></div>'
            '<div class="step card" style="background:var(--gold2);border-color:#e7c98f"><div class="small" style="color:#1d2a23">학습 모델(정확도 0.848)은 <b>근거 부족을 「성립」으로 바꿔</b> 채택하지 않음 — 판정은 코드</div></div>',
            "피그마 ‘이동 판정기 · 발표용’ 그대로. 다른 에이전트가 식당·활동을 바꾸면 이 판정기가 앞뒤 이동을 다시 계산합니다. LLM이 시각을 짓지 않는 이유를 여기서 설명.", 400)

# 16. 아키텍처 -----------------------------------------------------------------
ar = Flow(1440, 600)
ar.node("u1", 0, 60, 230, 80, "휴대폰 웹", "trig", 1, 22)
ar.node("u2", 0, 180, 230, 80, "여행계획서 링크", "trig", 1, 22)
ar.node("u3", 0, 300, 230, 80, "디스코드 알림", "trig", 1, 22)
ar.node("core", 330, 40, 420, 150, "코어 = 여행 매니저\n분류 → 담당 고르기 → 판정 확인\n→ 일정 새 판 저장", "out", 2, 22)
ar.node("ag1", 330, 240, 130, 90, "계획 읽기", "agent", 3, 20)
ar.node("ag2", 475, 240, 90, 90, "요식", "agent", 3, 20)
ar.node("ag3", 580, 240, 110, 90, "액티비티", "agent", 3, 20)
ar.node("ag4", 705, 240, 80, 90, "이동", "agent", 3, 20)
ar.node("loop", 330, 380, 455, 80, "상시 작업: 감시 루프(1분) · 알림 배달 일꾼", "proc", 4, 20)
ar.node("db", 860, 40, 260, 150, "데이터베이스\n여행 · 일정 판 · 사건\n식당 1,225 · 시간표 46만", "dec", 5, 20)
ar.node("ai", 860, 240, 260, 110, "로컬 AI\nGemma 4 12B · bge-m3", "dec", 5, 20)
ar.node("ext", 1180, 40, 250, 310, "외부 데이터\n관광공사\n카카오 · Google\n기상청 · 대기질\n교통(ITS·UTIC)\n공휴일 · 공항", "ghost", 6, 20)
ar.edge("u1", "core", step=2); ar.edge("u2", "core", step=2); ar.edge("loop", "u3", "l", "r", step=4)
ar.edge("core", "ag1", "b", "t", step=3); ar.edge("core", "ag4", "b", "t", step=3)
ar.edge("core", "db", step=5); ar.edge("core", "ai", "r", "l", step=5)
ar.edge("db", "ext", step=6); ar.edge("ai", "ext", step=6)
slide(f'''
<div class="kicker">시스템 아키텍처</div>
<h2>사람 셋이 보는 곳 · 매니저와 에이전트 · 데이터와 AI</h2>
<div style="height:620px;margin-top:10px">{ar.svg()}</div>''',
      "컨트롤러·라우터 같은 내부 이름은 뺐습니다. 왼쪽(사용자가 보는 곳) → 가운데(매니저와 에이전트, 상시 작업) → 오른쪽(데이터·AI·외부)만 기억하면 됩니다. 조회가 실패하면 대체 소스를 쓰고, 그것도 안 되면 조용히 넘기지 않습니다.")

# 17. CI/CD ------------------------------------------------------------------
ci = Flow(1440, 470)
br = [("f", "기능 브랜치"), ("r", "역할 브랜치\n매니저·액티비티\n요식·이동·평가"), ("d", "develop"), ("m", "main")]
for i, (k, t) in enumerate(br):
    ci.node(k, 20 + i * 360, 30, 250, 110, t, "agent" if k in "dm" else "proc", 1, 21)
for a, b in (("f", "r"), ("r", "d"), ("d", "m")):
    ci.edge(a, b, step=1, text="PR")
ci.node("g1", 740, 200, 300, 170, "develop 관문\n린트(ruff)\n+ DB 띄워 구조·계약·단위 시험\n1,015건", "dec", 2, 19)
ci.node("g2", 1100, 200, 320, 170, "main 관문\n구조 시험 먼저\n→ 전체 시험 1,400건\n→ Docker 빌드", "dec", 3, 19)
ci.node("g3", 380, 200, 300, 170, "웹 관문 (웹이 바뀔 때)\n린트·타입·단위·빌드\n→ 브라우저 e2e 시험", "dec", 2, 19)
ci.edge("d", "g1", "b", "t", step=2); ci.edge("m", "g2", "b", "t", step=3); ci.edge("r", "g3", "b", "t", step=2)
ci.node("cd", 740, 395, 680, 64, "CD: 빌드까지 · 배포는 상시 운영을 약속하는 시점에", "ghost", 4, 19)
slide(f'''
<div class="kicker">CI/CD · 협업</div>
<h2>팀원 다섯 명이 한 코드에 올려도 <span class="hl">자동 관문</span>이 먼저 막습니다</h2>
<div style="height:480px;margin-top:10px">{ci.svg()}</div>
<div class="row" style="gap:20px;margin-top:6px">
  <div class="step card" style="flex:1"><div class="mid" style="font-size:52px">2,309</div><div class="small">전체 시험 통과 (60건 건너뜀 · 09-28)</div></div>
  <div class="step card" style="flex:2;background:var(--gold2);border-color:#e7c98f"><div style="font-size:22px;font-weight:800">관문이 잡은 사고</div><div class="small" style="color:#1d2a23">GitHub 서버는 UTC라 43건이 9시간 밀림(경복궁 09:00 → 00:00) → 서버·DB 시간대를 한국 시간으로 고정</div></div>
</div>''', "중간발표 뒤 멘토가 권한 CI/CD 구성. 실제로 이동 팀 PR 2건이 이 관문을 거쳐 develop에 합쳐졌습니다.")

# 18. 평가 ------------------------------------------------------------------
lp = Flow(560, 520)
lp.node("s", 180, 0, 200, 80, "평가셋", "trig", 1, 22)
lp.node("r", 380, 180, 170, 80, "실행", "proc", 1, 22)
lp.node("m", 180, 360, 200, 80, "지표\n(분자/분모)", "dec", 1, 20)
lp.node("fx", 0, 180, 170, 80, "원인 고침", "agent", 1, 22)
lp.edge("s", "r", "r", "t", step=1); lp.edge("r", "m", "b", "r", step=1); lp.edge("m", "fx", "l", "b", step=1); lp.edge("fx", "s", "t", "l", step=1)
bars = [("계획 읽기 재현율", 90.2, 97.0, "같은 60건 · 코드 수정 뒤"), ("요식 영업시간 일치", 87.0, 99.0, "사람 대조 100곳"), ("대체 식당 분류 일치@3", 76.7, 91.5, "대리 지표 · 1회 · 제품 미적용")]
bh = ""
for n, a, b, c in bars:
    bh += (f'<div class="step" style="margin-bottom:26px"><div style="font-size:24px;font-weight:800">{n} <span class="small">· {c}</span></div>'
           f'<div style="display:flex;align-items:center;gap:12px;margin-top:8px"><div style="height:22px;width:{a * 6}px;background:#c9cdc6;border-radius:5px"></div><b style="font-size:20px;color:#8a938d">{a}%</b></div>'
           f'<div style="display:flex;align-items:center;gap:12px;margin-top:6px"><div style="height:22px;width:{b * 6}px;background:var(--g2);border-radius:5px"></div><b style="font-size:24px" class="hl">{b}%</b></div></div>')
slide(f'''
<div class="kicker">에이전트를 어떻게 평가하나</div>
<h2>정답 있는 곳은 정답셋, 정답 없는 추천은 <span class="hl">대리 지표 + 사람 판정</span></h2>
<div class="row" style="margin-top:26px;gap:50px;align-items:flex-start">
  <div style="width:560px;height:520px">{lp.svg()}</div>
  <div style="flex:1">{bh}<div class="step card"><div class="small" style="color:#1d2a23">이동 판정 회귀 <b>168/168</b> · 분류 모델 기준 라벨 일치율 0.831·0.802(사람 정답 아님) · 대체 추천 사람 판정 시트 237행 작성 중</div></div></div>
</div>''', "정량 평가 루프가 가능해야 한다는 지적 반영. 모든 수치는 분모와 조건을 함께 말합니다. 추천처럼 정답이 없는 문제는 대리 지표와 사람 판정으로 나눠 봅니다.")

# 19. 트러블슈팅 ------------------------------------------------------------------
slide('''
<div class="kicker">트러블슈팅 하나</div>
<h2>사진 속 일정표를 <span class="warn">한 번에</span> 읽히면, 하루가 통째로 사라졌습니다</h2>
<div class="row" style="margin-top:36px;gap:30px;align-items:stretch">
  <div class="step card" style="flex:1;border-color:var(--red)"><span class="pill red">처음</span><div style="font-size:32px;font-weight:800;margin:16px 0 10px">사진 → 일정 JSON 한 번에</div><div class="mid warn">3<span style="font-size:32px">/6</span></div><div class="small" style="margin-top:10px">일차 통째 누락 · 없는 칸 추가 · 95초</div></div>
  <div class="step card" style="flex:1"><span class="pill blue">원인</span><div style="font-size:32px;font-weight:800;margin:16px 0 10px">읽기와 해석을 한꺼번에</div><div class="small" style="color:#1d2a23;font-size:22px">모델이 보는 것과 짓는 것이 섞여,<br>틀려도 어디서 틀렸는지 모른다</div></div>
  <div class="step card" style="flex:1;border-color:var(--g1)"><span class="pill">바꾼 뒤</span><div style="font-size:32px;font-weight:800;margin:16px 0 10px">한 줄씩 받아쓰기 + 규칙</div><div class="mid">6<span style="font-size:32px">/6</span></div><div class="small" style="margin-top:10px">값 변조 없음 · 전체·반쪽 두 번 대조로 빠진 줄 확인</div></div>
</div>
<div class="step card" style="margin-top:26px;padding:18px 26px;font-size:22px;background:var(--gold2);border-color:#e7c98f"><b>남은 문제</b> — 평가셋 60건에서 값 변조 3.4%(긴 가게 이름 오독). 다음: 두 번 받아쓴 결과가 다른 줄을 「확인 필요」로 표시.</div>
<div class="src">합성 사진 1장 · 시각 항목 6개 · 방식마다 1회 측정(설계서 2026-09-26)</div>''',
      "트러블슈팅은 하나만 잘 — 멘토 지적 반영. 숫자와 원인, 바꾼 방법, 남은 문제까지 한 장에.")

# 20. 향후 계획 ------------------------------------------------------------------
fut = [("요식", "낮 임시휴무를 스스로 찾기 · 대체 추천을 사람 판정으로 수치화"), ("액티비티", "추천 적합도 사람 평가 · 날씨·대기질 조건 확대"),
       ("이동", "실시간 도착 정보 · 택시 편입"), ("코어", "사람 정답으로 계획 읽기·분류 평가 · 자체 분류 모델 18종 재학습 후 연결 검토")]
fc = "".join(f'<div class="step card" style="display:flex;gap:30px;align-items:center;padding:30px 34px"><span class="pill" style="min-width:150px;text-align:center;font-size:26px;padding:10px 18px">{a}</span><div style="font-size:31px;font-weight:600">{b}</div></div>' for a, b in fut)
slide(f'''
<div class="kicker">향후 계획 — 에이전트별로</div>
<h2>다음 한 달, 각 에이전트가 <span class="hl">더 잘하게 될 것</span></h2>
<div class="col" style="margin-top:34px;gap:16px">{fc}</div>
<p class="small" style="margin-top:22px">서비스 범위: 서울에서 테스트 검증을 마친 뒤 다른 도시로.</p>''', "향후 계획은 에이전트와 기능 중심으로 — 멘토 지적 반영.")

# 21. 마무리 -----------------------------------------------------------------------
slide(f'''
<div class="row" style="height:100%;align-items:center;gap:70px">
  <div style="flex:1">
    <div class="kicker">정리</div>
    <h1 style="font-size:64px">여행 계획은 한 번 짜면 끝이 아니라,<br><span class="hl">여행 내내 깨집니다.</span></h1>
    <div class="col" style="margin-top:40px;gap:14px;font-size:28px;font-weight:700">
      <div class="step">올린다 — 쓰던 그대로, 근거 있는 값만</div>
      <div class="step">지킨다 — 요식·액티비티·이동이 스스로 다시 확인</div>
      <div class="step">알린다 — 먼저 고치고, 고를 수 있게</div>
    </div>
    <p class="lead" style="margin-top:44px">질문 받겠습니다.</p>
  </div>
  {phone("s7_chat.jpg", w=250)}
</div>''', "마지막 질문 예상: 왜 LLM 대신 코드 판정? / 추천 품질은? / 웨이팅은? / 사람 서비스 대비 가격?")

html = (HERE / "base.html").read_text(encoding="utf-8").replace("{{SLIDES}}", "\n".join(S))
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")
print("장표", len(S), "장 →", OUT)
