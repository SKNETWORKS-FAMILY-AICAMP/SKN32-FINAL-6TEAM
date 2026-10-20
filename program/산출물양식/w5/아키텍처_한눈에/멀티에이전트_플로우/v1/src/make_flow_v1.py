# -*- coding: utf-8 -*-
"""guguroute 멀티 에이전트 흐름 v1 — 참고 구조(층마다 「받는 것 · 돌려주는 것」, 도구 층, 검사 · 복구 순환)의 모양으로
우리 실제 구조를 그린다. 2026-10-02.

    python make_flow_v1.py   → ../triPilot_멀티에이전트_플로우_v1.html · ../triPilot_멀티에이전트_플로우_v1.txt

★사실 기준: final_project_cs 코드(2026-10-02 확인) · w5/코어_에이전트_입출력/코어_에이전트_입출력_v3.html(코드 줄 근거).
★「인풋 · 아웃풋」이라는 낱말을 쓰지 않는다(멘토 피드백) — 「받는 것 · 돌려주는 것」.
★코드에 없는 것은 그리지 않거나 「설계 · 미구현」으로 따로 표시한다. AI 모델은 「시험 중」.
"""
import html
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
SANS = "'Noto Sans KR','Malgun Gothic',sans-serif"
MONO = "'Nanum Gothic Coding','NanumGothicCoding','D2Coding',monospace"
S = []


def esc(t):
    return html.escape(t, quote=False)


def box(x, y, w, h, cls="node", rx=8):
    S.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"/>')


def text(x, y, s, cls="", anchor=None):
    a = f' text-anchor="{anchor}"' if anchor else ""
    c = f' class="{cls}"' if cls else ""
    S.append(f'<text{c} x="{x}" y="{y}"{a}>{esc(s)}</text>')


def path(pts, cls="edge", mk="arrow"):
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    m = f' marker-end="url(#{mk})"' if mk else ""
    S.append(f'<path class="{cls}" d="{d}"{m}/>')


def stage(x, y, w, num, title, role, gets, gives, cls="node", h=None, tag=""):
    """한 층 상자 — 번호 · 제목 · 역할 한 줄 + 받는 것 · 돌려주는 것 줄들"""
    lines = len(gets) + len(gives)
    h = h or 62 + lines * 19 + 8
    box(x, y, w, h, cls)
    text(x + 20, y + 28, num, "svg-letter")
    text(x + 50, y + 28, title, "h")
    if tag:
        text(x + w - 18, y + 28, tag, "tag", "end")
    text(x + 50, y + 48, role, "svg-note")
    yy = y + 74
    for i, g in enumerate(gets):
        if i == 0:
            text(x + 20, yy, "받는 것", "k")
        text(x + 110, yy, g, "v")
        yy += 19
    for i, g in enumerate(gives):
        if i == 0:
            text(x + 20, yy, "돌려주는 것", "k2")
        text(x + 110, yy, g, "v")
        yy += 19
    return h


def mini(x, y, w, h, title, lines, cls="node", icon=None):
    box(x, y, w, h, cls)
    text(x + 16, y + 24, title, "h2")
    for i, ln in enumerate(lines):
        text(x + 16, y + 44 + i * 17, ln, "svg-note")


CSS = f"""
:root{{--paper:#fbfcfd;--paper-2:#f1f4f8;--card:#ffffff;--ink:#161c28;--muted:#606b7e;--soft:#727d90;--rule-solid:#dbe0ea;
--accent:#a8720c;--accent-tint:rgba(168,114,12,.08);--accent-rule:rgba(168,114,12,.38);--core-fill:#fbf6ec;
--blue:#2f6c9a;--blue-tint:rgba(47,108,154,.05);--blue-rule:rgba(47,108,154,.32);--red:#a33b3b;--red-tint:rgba(163,59,59,.05);--red-rule:rgba(163,59,59,.35);
--green:#3d7a4f;--green-tint:rgba(61,122,79,.06);--green-rule:rgba(61,122,79,.38)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--paper:#15181d;--paper-2:#20252d;--card:#1a1f26;--ink:#e9edf3;--muted:#b0bac9;--soft:#9aa6b9;
--rule-solid:#39424f;--accent:#e4b45c;--accent-tint:rgba(228,180,92,.09);--accent-rule:rgba(228,180,92,.42);--core-fill:#2a2418;
--blue:#7fb2dc;--blue-tint:rgba(127,178,220,.07);--blue-rule:rgba(127,178,220,.35);--red:#e08a8a;--red-tint:rgba(224,138,138,.07);--red-rule:rgba(224,138,138,.4);
--green:#8cc79c;--green-tint:rgba(140,199,156,.07);--green-rule:rgba(140,199,156,.4)}}}}
.diagram{{border:1px solid var(--rule-solid);border-radius:6px;background:var(--card);overflow-x:auto;margin:10px 0 6px}}
.diagram svg{{display:block;width:100%;min-width:1080px;height:auto;color:var(--ink)}}
.diagram .node{{fill:var(--card);stroke:var(--rule-solid)}}
.diagram .core{{fill:var(--core-fill);stroke:var(--accent-rule)}}
.diagram .agent{{fill:var(--blue-tint);stroke:var(--blue-rule)}}
.diagram .tool{{fill:var(--green-tint);stroke:var(--green-rule)}}
.diagram .fail{{fill:var(--red-tint);stroke:var(--red-rule);stroke-dasharray:5 4}}
.diagram .plan{{fill:none;stroke:var(--soft);stroke-dasharray:4 4}}
.diagram .band{{fill:var(--paper-2);stroke:var(--rule-solid)}}
.diagram .band-blue{{fill:var(--blue-tint);stroke:var(--blue-rule)}}
.diagram .edge{{fill:none;stroke:var(--muted);stroke-width:1.3;stroke-linejoin:round}}
.diagram .edge.loop{{stroke:var(--accent);stroke-width:1.6;stroke-dasharray:7 5}}
.diagram .edge.bad{{stroke:var(--red);stroke-dasharray:5 4}}
.diagram .edge.tooll{{stroke:var(--green);stroke-width:1.3}}
.diagram .ah{{fill:var(--muted)}} .diagram .ah-gold{{fill:var(--accent)}} .diagram .ah-red{{fill:var(--red)}} .diagram .ah-green{{fill:var(--green)}}
.diagram text{{fill:currentColor;font-family:{SANS};font-size:14px}}
.diagram .title{{font-size:22px;font-weight:700}}
.diagram .h{{font-size:16px;font-weight:700}} .diagram .h2{{font-size:15px;font-weight:700}}
.diagram .svg-label{{fill:var(--soft);font-family:{MONO};font-size:12px;letter-spacing:.08em}}
.diagram .svg-note{{fill:var(--muted);font-size:12.5px}}
.diagram .svg-letter{{fill:var(--accent);font-family:{MONO};font-size:15px;font-weight:700}}
.diagram .k{{fill:var(--blue);font-size:12.5px;font-weight:700}} .diagram .k2{{fill:var(--accent);font-size:12.5px;font-weight:700}}
.diagram .v{{font-size:13px}}
.diagram .tag{{fill:var(--soft);font-family:{MONO};font-size:11px}}
.diagram .lbl{{fill:var(--muted);font-size:12px}} .diagram .lbl-gold{{fill:var(--accent);font-size:12.5px;font-weight:700}}
.diagram .lbl-red{{fill:var(--red);font-size:12.5px;font-weight:700}} .diagram .lbl-green{{fill:var(--green);font-size:12px}}
"""

DEFS = ('<defs>'
        '<marker id="arrow" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto"><path class="ah" d="M0 0 L10 5 L0 10 Z"/></marker>'
        '<marker id="arrow-gold" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto"><path class="ah-gold" d="M0 0 L10 5 L0 10 Z"/></marker>'
        '<marker id="arrow-red" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto"><path class="ah-red" d="M0 0 L10 5 L0 10 Z"/></marker>'
        '<marker id="arrow-green" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto"><path class="ah-green" d="M0 0 L10 5 L0 10 Z"/></marker>'
        '</defs>')


def svg_wrap(W, H, label):
    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(label)}">{DEFS}{"".join(S)}</svg>'


# ───────────────────────── 그림 1 — 전체 흐름 ─────────────────────────
def fig1():
    S.clear()
    W = 1560
    CX, CW = 330, 820          # 가운데 기둥
    RX = CX + CW + 50          # 오른쪽 기둥(도구 · 복구)
    RW = W - RX - 30
    text(40, 40, "그림 1 · 사건 하나가 에이전트를 거쳐 새 일정이 되기까지 — 여행이 끝날 때까지 되풀이", "svg-label")
    text(40, 74, "guguroute 멀티 에이전트 흐름", "title")
    text(40, 98, "2026-10-02 · final_project_cs 코드 기준 · 가운데 = 코어(매니저)와 에이전트 · 오른쪽 = 조회 도구 층 · 금색 점선 = 되풀이(루프) · 붉은 점선 = 못 했을 때", "svg-note")

    # 왼쪽: 깨우는 것
    text(40, 140, "깨우는 것", "svg-label")
    trig = [("감시 — 1분마다", ["앞으로 90분 안에 시작할", "항목의 장소 · 경로 점검"]),
            ("새벽 점검 — 03:00~08:00", ["그날 식사 · 활동이 계획한", "시각에 여는지(Google)"]),
            ("사건 접수 API", ["개인 AI 비서 앱 · 시험이", "여행 건을 직접 연다"])]
    ty = 152
    for t, ls in trig:
        mini(40, ty, 250, 78, t, ls)
        path([(290, ty + 39), (300, ty + 39), (300, 232), (CX - 2, 232)])
        ty += 92
    text(40, ty + 18, "★감시 · 새벽 점검은 처리 건을", "svg-note")
    text(40, ty + 36, "  만들기만 하고 판정은 안 한다", "svg-note")

    y = 150
    # ① 처리 건 열기
    h = stage(CX, y, CW, "①", "처리 건 열기", "깨진 항목마다 한 건 · 같은 원인이면 같은 건으로 모은다(여행 · 항목 · 원인 지문)",
              ["깨진 일정 항목 · 감시가 본 원인(날씨 · 교통 · 영업 …)"],
              ["처리 건 1건 + 분류 값 — 요청 종류 「사건 신고」 · 문제 코드(예: dining_other)", "감시 건은 AI 분류를 부르지 않는다 — 무엇이 문제인지 이미 안다"], "core", tag="코어")
    y1b = y + h
    y = y1b + 34
    path([(CX + CW / 2, y1b), (CX + CW / 2, y - 2)])
    # ② 담당 고르기
    h = stage(CX, y, CW, "②", "담당 고르기 · 일감 만들기", "문제 코드 앞부분(dining → 요식) × 요청 종류로 담당 에이전트 하나 — 에이전트끼리 직접 부르지 않는다",
              ["처리 건(문제 코드 · 요청 종류 · 상태 · 판 번호)"],
              ["일감 1장 — 담당 · 일감 종류(예: dining.itinerary) · 쓸 수 있는 조회 도구 목록 · 마감 90초",
               "근거 묶음 — 처리 건 상태 · 무엇이 깨졌나(항목 · 시각) · 규정 조각, 12,000 토큰 안"], "core", tag="코어")
    y2b = y + h
    y = y2b + 40
    path([(CX + CW / 2, y2b), (CX + CW / 2, y - 2)])

    # ③ 에이전트 띠
    AH = 316
    box(CX - 16, y - 14, CW + 32, AH + 28, "band-blue", 10)
    text(CX, y + 6, "③ 담당 에이전트 — 셋 중 하나가 일감을 받는다 (MVP: 요식 · 액티비티 · 이동)", "lbl")
    aw, gap = (CW - 2 * 18) / 3, 18
    agents = [
        ("요식", ["외부 6종 다시 점검", "그 시각 영업 · 라스트오더", "(도착 + 20분)"],
         ["대체: 요식 원장 후보(덜 밀림 ·", "비슷함 · 가까움) → 장소 목록", "후보마다 다시 점검, 최대 3곳"]),
        ("액티비티", ["외부 6종 다시 점검", "(날씨 · 대기질 · 특보 · 지진 …)", "실내인지 모르면 「바꿀까요?」"],
         ["대체: 같은 대분류(자연 · 인문 ·", "레포츠 · 쇼핑) · 비슷한 순", "후보마다 다시 점검 · 취향 점수"]),
        ("이동", ["계획 경로(구간 · 수단)", "구간 교통 사건(UTIC)", ""],
         ["대체: 막히지 않은 다른 선택지", "→ 다 막히면 시간표 판정기로", "다시 찾기(지하철 · 버스 46만 행)"]),
    ]
    ay = y + 22
    for i, (nm, chk, alt) in enumerate(agents):
        ax = CX + i * (aw + gap)
        box(ax, ay, aw, 214, "agent")
        text(ax + 16, ay + 26, nm, "h")
        text(ax + aw - 14, ay + 26, "판정은 코드", "tag", "end")
        text(ax + 16, ay + 50, "점검", "k")
        for j, ln in enumerate(chk):
            text(ax + 60, ay + 50 + j * 18, ln, "v")
        text(ax + 16, ay + 112, "깨졌으면", "k")
        for j, ln in enumerate(alt):
            text(ax + 16, ay + 132 + j * 18, ln, "v")
        # 안쪽 루프 표시
        path([(ax + aw - 26, ay + 196), (ax + aw - 10, ay + 196), (ax + aw - 10, ay + 120), (ax + aw - 18, ay + 120)], "edge loop", "arrow-gold")
    text(CX + 4, ay + 238, "돌려주는 것 (셋 공통 · 결과지 1장)", "k2")
    text(CX + 4, ay + 258, "다음 할 일(답하고 끝 · 못 함) · 고객용 문장 · 근거(무엇을 · 언제 확인) · 일정 변경 제안(기준 판 · 바뀐 항목 · 알림 문구 · 다른 안 둘)", "v")
    text(CX + 4, ay + 278, "★에이전트는 일정을 직접 바꾸지 않는다 — 제안만 낸다. AI 모델도 부르지 않는다(세 에이전트 코드에서 사용처 0).", "svg-note")
    text(CX + CW - 4, ay + 238, "↺ 금색 = 후보가 다시 점검에 걸리면 다음 후보로", "lbl-gold", "end")
    y3t, y3b = y - 14, y - 14 + AH + 28

    # 오른쪽: 조회 도구 층
    ty0 = y3t
    box(RX, ty0, RW, AH + 28, "tool")
    text(RX + 16, ty0 + 26, "조회 도구 층", "h")
    text(RX + 16, ty0 + 46, "에이전트는 DB · API 를 직접 열지 않는다", "svg-note")
    tl = ["일감에 적힌 도구만 — 목록 밖은 거부", "같은 도구 · 같은 값 두 번 거부", "12번 넘으면 멈춤", "",
          "read.itinerary   지금 일정 판", "read.disruptions 외부 6종 점검", "read.dining_state 그 시각 영업",
          "read.dining_alternatives 대체 식당", "read.place_catalog 대체 장소", "read.route_events 구간 교통 사건", "read.policy 규정 조각 …"]
    for j, ln in enumerate(tl):
        text(RX + 16, ty0 + 74 + j * 19, ln, "v" if j < 3 else "svg-note")
    text(RX + 16, ty0 + AH + 14, "→ 그림 2", "lbl-green")
    path([(CX + CW + 16, y3t + 120), (RX - 2, y3t + 120)], "edge tooll", "arrow-green")
    path([(RX, y3t + 150), (CX + CW + 18, y3t + 150)], "edge tooll", "arrow-green")
    text(CX + CW + 33, y3t + 112, "부름", "lbl-green", "middle")
    text(CX + CW + 33, y3t + 168, "값", "lbl-green", "middle")

    y = y3b + 36
    path([(CX + CW / 2, y3b), (CX + CW / 2, y - 2)])
    # ④ 결과 검사
    h = stage(CX, y, CW, "④", "결과 검사", "에이전트가 아니라 코어의 코드가 본다 — 참고 구조의 「평가 에이전트」 자리",
              ["결과지"],
              ["통과 / 막음 — ⓐ 답에는 근거가 있어야 · 제안의 근거는 같은 결과지 안에 ⓑ 여행 · 예약이 정말 그 고객 것인가(DB 다시 읽기)",
               "ⓒ 처리 건 판 번호가 그대로인가(사이에 다른 쓰기가 있었으면 이 결과를 버린다)"], "core", tag="코어")
    y4b = y + h
    # 판정 마름모
    dy = y4b + 30
    dcx = CX + CW / 2
    S.append(f'<path class="core" d="M{dcx} {dy} L{dcx + 120} {dy + 32} L{dcx} {dy + 64} L{dcx - 120} {dy + 32} Z"/>')
    text(dcx, dy + 37, "통과 · 바꿀 안 있음?", "h2", "middle")
    path([(dcx, y4b), (dcx, dy - 2)])

    # 못 했을 때 — 오른쪽
    fy = y4b - 20
    box(RX, fy, RW, 214, "fail")
    text(RX + 16, fy + 26, "⑤ 못 했을 때", "lbl-red")
    fl = ["그대로(영향 없음) → 답만 기록, 끝", "판이 밀림 → 이 결과만 버림, 다음 감시에 다시",
          "못 함(대안 없음 · 소스가 대체까지 실패", "· 90초 넘김) → 오류 기록, 일정 그대로",
          "→ 운영자에게 오류 알림만", "★고객 건을 사람에게 넘기지 않는다",
          "★「모름」을 「문제 없음」으로 읽지 않는다"]
    for j, ln in enumerate(fl):
        text(RX + 16, fy + 50 + j * 21, ln, "v" if j < 5 else "svg-note")
    path([(dcx + 120, dy + 32), (RX - 30, dy + 32), (RX - 30, fy + 100), (RX - 2, fy + 100)], "edge bad", "arrow-red")
    text(dcx + 140, dy + 25, "아니오", "lbl-red")

    y = dy + 64 + 36
    path([(dcx, dy + 64), (dcx, y - 2)])
    text(dcx + 8, dy + 84, "예", "lbl")
    # ⑥ 적용
    h = stage(CX, y, CW, "⑥", "적용 — 새 일정 판", "적용기가 한 번에: 기준 판 확인 → 항목 갈아 끼우기 → 앞뒤 이동 다시 계산 → 설문 확인",
              ["일정 변경 제안(기준 판 · 바뀐 항목 · 알림 문구 · 다른 안)"],
              ["새 판 1개(옛 판은 지우지 않음) — 또는 바꾸지 않고 묻기(보류 제안)",
               "묻는 때: 설문 「먼저 물어봐」 · 고객이 고정한 일정 · 안전 경보(지진 · 재난) / 설문 「바꿔 줘」면 바로 적용"], "core", tag="코어")
    y6b = y + h
    y = y6b + 34
    path([(dcx, y6b), (dcx, y - 2)])
    # ⑦ 알림
    h = stage(CX, y, CW, "⑦", "알림 · 여행계획서", "새 판과 같은 저장 단위로 「보낼 함」에 넣고, 배달 일꾼이 보낸다",
              ["새 판 · 알림 문구"],
              ["디스코드 알림 1번(3번까지 다시 보냄 · 같은 알림 두 번 안 감) · 여행계획서 링크가 새 판을 보여 줌",
               "고객이 다른 안 고르기 · 되돌리기 → 채팅 창구(아래 4절)에서 새 판"], "core", tag="코어")
    y7b = y + h

    # 바깥 루프 — 왼쪽으로 돌아 ①로
    lx = 316
    path([(CX, y7b - 30), (lx, y7b - 30), (lx, 190), (CX - 2, 190)], "edge loop", "arrow-gold")
    text(lx - 10, (y7b + 190) / 2 - 30, "바깥 루프", "lbl-gold", "end")
    text(lx - 10, (y7b + 190) / 2 - 10, "여행이 끝날 때까지", "lbl-gold", "end")
    text(lx - 10, (y7b + 190) / 2 + 10, "다음 감시(1분) ·", "lbl", "end")
    text(lx - 10, (y7b + 190) / 2 + 28, "새벽 3시 · 신고", "lbl", "end")

    H = y7b + 70
    text(40, H - 30, "출처: final_project_cs — 감시 trip_watch_cases.py · 처리 건 case_intake.py · 담당 routing.py · registry.py · 일감 contracts.py TeamTask · 에이전트 dining/activity/mobility team.py · itinerary_team.py ·", "svg-note")
    text(40, H - 12, "결과 검사 contracts.py TeamResult · controller.py _reject_unverified · 적용 itinerary_actions.py · 설문 pending.py · 알림 messaging/worker.py · notify/discord.py (줄 근거: w5/코어_에이전트_입출력 v3)", "svg-note")
    return svg_wrap(W, H, "guguroute 멀티 에이전트 흐름")


# ───────────────────────── 그림 2 — 도구 · 데이터 층 ─────────────────────────
def fig2():
    S.clear()
    W, H = 1560, 724
    text(40, 40, "그림 2 · 에이전트와 조회 도구 · 데이터 층 — 에이전트는 조회 도구로만 값을 읽는다", "svg-label")
    text(40, 74, "조회 도구 · 데이터 층", "title")
    # 에이전트 셋
    ag = [("요식", ["+ read.dining_state · read.dining_alternatives", "+ read.disruptions · read.place · read.policy", "+ read.booking · read.booking_terms"]),
          ("액티비티", ["+ read.disruptions · read.place · read.policy", "+ read.booking · read.booking_terms", ""]),
          ("이동", ["+ read.route_events · read.policy", "+ read.route · read.transit (미구현 — 늘 빈 값)", ""])]
    for i, (nm, tl) in enumerate(ag):
        x = 40 + i * 500
        box(x, 100, 480, 122, "agent")
        text(x + 16, 126, nm + " 에이전트", "h")
        text(x + 16, 148, "공통 read.itinerary · read.itinerary_version", "svg-note")
        text(x + 16, 165, "     read.place_catalog · read.customer_report", "svg-note")
        for j, ln in enumerate([t for t in tl if t]):
            text(x + 16, 182 + j * 17, ln, "svg-note")
        path([(x + 240, 222), (x + 240, 256)], "edge tooll", "arrow-green")
    # 도구 층
    box(40, 258, 1480, 92, "tool")
    text(60, 288, "조회 도구 층 (ReadToolbox)", "h")
    text(60, 312, "일감마다 쓸 수 있는 도구 목록이 정해져 있다 — 목록 밖 거부 · 같은 호출 두 번 거부 · 12번 넘으면 멈춤 · 값이 없으면 「없음」이 아니라 「모름」으로 돌려준다", "v")
    text(60, 334, "참고 구조의 「MCP 도구 서버」 자리지만 MCP 규약을 쓰지는 않는다 — 같은 서버 안의 파이썬 호출이다(MCP 는 바깥 AI 앱이 우리에게 붙는 입구로만 있다)", "svg-note")
    # 데이터 셋
    cols = [(40, 470, "PostgreSQL 16 + pgvector", ["여행 · 일정 판 · 항목(옛 판 보존)", "장소 표 · 관광공사 장소 목록", "요식 원장 — 서울 식당 1,225곳",
                                                   "처리 건 · 실행 기록 · 보낼 함", "규정 조각 + 임베딩(bge-m3, 1024차원)"], "db"),
            (545, 470, "외부 API — 6종을 한 번에 점검", ["예보 Open-Meteo ↔ 기상청(대체)", "기상 특보 · 지진 — 기상청", "재난문자 — 행정안전부",
                                                 "교통통제 ITS ↔ UTIC(대체) · 대기질 에어코리아", "Google 장소 영업시간 — 새벽 점검에서만"], "api"),
            (1050, 470, "시간표 파일 → 시간표 판정기", ["지하철 · 버스 시간표 46만 행", "「이 시각에 나가면 제시간?」", "근거 등급: 확정 · 추정 · 근거 없음",
                                              "이동 에이전트의 다시 찾기 ·", "적용기의 앞뒤 이동 계산이 쓴다"], "tt")]
    for x, w, t, ls, k in cols:
        box(x, 406, w, 176, "node")
        text(x + 16, 434, t, "h2")
        for j, ln in enumerate(ls):
            text(x + 16, 460 + j * 22, ln, "v")
        path([(x + w / 2, 350), (x + w / 2, 404)], "edge tooll", "arrow-green")
    text(40, 620, "★1차 소스가 안 되면 대체 소스로 다시 읽고, 대체까지 안 되면 「문제 없음」으로 넘기지 않고 오류(fatal)로 끝낸다.", "v")
    text(40, 642, "★참고 구조의 GraphRAG(Neo4j · 여러 단계 관계 추론)는 우리에게 없다. 문서 검색은 규정 조각을 벡터로 찾는 것 하나(pgvector)이고, 규정 질문 답에만 쓴다.", "v")
    text(40, 664, "★근거 묶음(12,000 토큰)을 만드는 것은 코어다 — 에이전트가 읽은 근거와 코어가 대조하는 근거를 나눠, 에이전트가 근거와 제안을 함께 지어내도 대조가 돌지 않게 했다.", "svg-note")
    text(40, 694, "출처: app/tools/read_tools.py · app/infrastructure/travel/disruptions.py · app/core/context.py · 도구 목록은 각 에이전트 team.py 의 allowed_tools", "svg-note")
    return svg_wrap(W, H, "조회 도구 · 데이터 층")


# ───────────────────────── 표 ─────────────────────────
STAGES = [
    ("① 처리 건 열기", "코어 · 감시", "깨진 일정 항목 · 원인", "처리 건 1건 · 분류 값(요청 종류 · 문제 코드)", "구현"),
    ("② 담당 고르기", "코어 · 컨트롤러", "처리 건", "일감(담당 · 일감 종류 · 도구 목록 · 마감 90초) + 근거 묶음(12,000 토큰)", "구현"),
    ("③ 요식 에이전트", "에이전트", "일감 · 근거 묶음", "결과지 — 그대로 / 대체 식당 제안(+다른 안) / 못 함", "구현"),
    ("③ 액티비티 에이전트", "에이전트", "일감 · 근거 묶음", "결과지 — 그대로 / 대체 활동 제안 / 「바꿀까요?」 / 못 함", "구현"),
    ("③ 이동 에이전트", "에이전트", "일감 · 근거 묶음", "결과지 — 그대로 / 다른 경로 제안 / 못 함", "구현 · 고객 신고는 처리 안 함"),
    ("조회 도구 층", "도구", "도구 이름 · 값", "일정 · 영업 · 외부 점검 · 교통 사건 · 규정 조각 — 못 읽으면 「모름」", "구현 · read.route · read.transit 미구현"),
    ("④ 결과 검사", "코어", "결과지", "통과 / 막음(근거 · 실제 고객 것 · 판 번호)", "구현"),
    ("⑤ 못 했을 때", "코어", "막힘 · 못 함 · 시간 초과", "오류 기록 · 일정 그대로 · 운영자 오류 알림", "구현"),
    ("⑥ 적용", "코어 · 적용기", "일정 변경 제안", "새 판 1개 또는 묻기(보류 제안)", "구현"),
    ("⑦ 알림", "코어 · 배달 일꾼", "새 판 · 알림 문구", "디스코드 알림 1번 · 여행계획서 새 판", "구현 · 채널은 팀 시연용 하나"),
]

ENTRIES = [
    ("계획 올리기", "글 · 사진 · 파일(5개 · 10MB · 글 20,000자)", "계획 읽기(코어) — 규칙이 먼저 읽고, 남은 줄만 AI 가 원문 위치를 가리킴 → 장소 하나로 정하기 → 확인 화면 → 등록", "거치지 않음", "AI: 사진 받아쓰기 · 원문 위치(시험 중)"),
    ("일정 짜 줘", "빈 계획 · 「일정 짜 줘」", "일정 짜기(코어) — 후보는 우리 장소 표 · 관광공사 목록에서만, AI 는 줄 번호 순서만 냄 → 판정 통과 → 등록", "거치지 않음", "AI: 순서(시험 중) · 없으면 규칙 순위"),
    ("채팅 — 묻기 · 바꿔 줘 · 늦어요 · 다른 안 · 되돌리기", "고객 문장", "분류 → 여행 창구 → 에이전트와 같은 계산 함수로 대체 고르기 → 설문 확인 → 새 판 · 알림", "거치지 않음(같은 계산을 공유)", "AI: 분류 · 신고 뽑기(시험 중)"),
    ("감시 · 새벽 점검 · 사건 접수 API", "깨진 항목 · 여행 건", "그림 1 — 처리 건 → 담당 고르기 → 에이전트 → 검사 → 적용 → 알림", "거침", "AI 안 부름"),
    ("일정 알림 — 하루 시작 · 다음 일정 · 출발", "시각", "저장된 최신 판을 읽어 「지금 할 일」을 알림 — 처리 건을 만들지 않음", "거치지 않음", "AI: 문구틀 번역만, 언어마다 처음 한 번"),
]

MAP = [
    ("Identity & Delegation", "브라우저 사용자 키 · 여행계획서 링크 토큰 · 고객 번호 조건으로 다시 읽기", "있음 — 로그인은 없다"),
    ("TARA++ (신뢰 · 비용 · 확신도로 에이전트 선택 · 재라우팅)", "② 담당 고르기 — 문제 코드 × 요청 종류로 하나를 고른다", "있음 — 단 신뢰 · 비용 점수로 고르지 않는다. 규칙으로 고르고, 받는 에이전트가 하나가 아니면 오류"),
    ("A2A 에이전트 네트워크", "에이전트끼리 직접 부르지 않는다 — 코어를 거친다. A2A 원격 실행 통로는 코드에 있으나 시뮬레이터이고 꺼져 있다", "없음(쓰지 않음)"),
    ("Planner Agent", "계획 읽기 · 일정 짜기 — 코어의 처리 단계", "에이전트 아님"),
    ("Knowledge / Domain Agent", "③ 요식 · 액티비티 · 이동 — 영역마다 하나, 판정은 코드", "있음"),
    ("MCP Tool Server", "조회 도구 층(허용 목록 · 횟수 한도) — 같은 서버 안 호출. MCP 는 바깥 AI 앱의 입구로만", "자리는 있음 · 규약은 다름"),
    ("Vector RAG (pgvector)", "규정 조각 검색(bge-m3) — 규정 질문 답에만", "있음"),
    ("GraphRAG (Neo4j)", "—", "없음"),
    ("Evaluator Agent", "④ 결과 검사 — 코어의 코드(근거 · 실제 고객 것 · 판 번호) + 적용기 검사", "에이전트 아님 · 코드"),
    ("Recovery Agent", "에이전트 안 「다음 후보로 다시」(최대 3곳) · 대체 소스 · 판이 밀리면 다음 감시에 다시 · 고객의 다른 안 · 되돌리기", "별도 에이전트 없음"),
    ("Collusion Monitor", "에이전트가 한 건에 하나뿐이라 서로 맞춰 줄 여지가 없다", "해당 없음"),
    ("Trust Update", "실행 중 신뢰 점수 갱신은 없다. 품질은 평가셋 → 재측정 루프(계획 읽기 90.2% → 97.0% 등)로 밖에서 본다", "없음"),
]

GAPS = [
    ("외부 소스를 3분마다 한 번 모아 여러 여행에 나눠 씀", "설계(D-017) · 미구현 — 지금은 1분마다 90분 앞 항목을 하나씩 점검"),
    ("한 사건을 액티비티 → 요식 → 이동 차례로 넘기며 앞 에이전트의 초안을 넘김", "설계(피그마 공통 흐름) · 미구현 — 지금은 처리 건 하나에 에이전트 하나, 앞뒤 이동은 적용기가 다시 계산"),
    ("이동 에이전트가 고객 신고(늦음 등)를 처리", "미구현 — 이동 신고는 오류로 끝남(채팅 창구는 별도로 처리)"),
    ("고객마다 알림 받을 곳", "미구현 — 디스코드 채널 하나(팀 시연용)"),
    ("낮 임시휴무를 시스템이 스스로 찾기", "결정(2026-09-29) · 미구현 — 지금은 고객 신고로"),
]


def table(head, rows):
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


# ───────────────────────── 글자 그림(참고 자료와 같은 모양) ─────────────────────────
AMBIG = [(" · ", ", "), ("·", ","), ("—", "-"), ("→", "->"), ("↔", "<->"), ("×", "x"), ("…", "..."), ("★", "*"),
         ("①", "(1)"), ("②", "(2)"), ("③", "(3)"), ("④", "(4)"), ("⑤", "(5)"), ("⑥", "(6)"), ("⑦", "(7)")]


def plain(t):
    for a, b in AMBIG:
        t = t.replace(a, b)
    return t


def wlen(t):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in t)


def pad(t, n):
    return t + " " * max(0, n - wlen(t))


def tbox(title, lines, w):
    out = ["+" + "-" * (w - 2) + "+", "| " + pad(plain(title), w - 4) + " |", "|" + " " * (w - 2) + "|"]
    out += ["| " + pad(plain(ln), w - 4) + " |" for ln in lines]
    out.append("+" + "-" * (w - 2) + "+")
    return out


def side(a, b, mid):
    """상자 a 오른쪽에 상자 b — 가운데 줄 mid(줄 번호 → 글자)"""
    wa = max(wlen(x) for x in a)
    n = max(len(a), len(b))
    a = a + [""] * (n - len(a)); b = b + [""] * (n - len(b))
    return [pad(x, wa) + pad(mid.get(k, ""), 9) + y for k, (x, y) in enumerate(zip(a, b))]


def ascii_art():
    W = 96
    C = " " * (W // 2)
    down = [C + "|", C + "v"]
    L = []
    L += tbox("깨우는 것 — 감시(1분마다) · 새벽 점검(03~08시) · 사건 접수 API",
              ["받는 것     : 지금 일정 판(앞으로 90분 안 항목) · 외부 6종 점검 결과", "돌려주는 것 : 깨진 항목 · 원인"], W) + down
    L += tbox("① 처리 건 열기  [코어]",
              ["받는 것     : 깨진 항목 · 원인", "돌려주는 것 : 처리 건 1건 · 요청 종류 · 문제 코드 (감시 건은 AI 분류 안 부름)"], W) + down
    L += tbox("② 담당 고르기 · 일감 만들기  [코어 — 참고 구조의 TARA++ 자리]",
              ["받는 것     : 처리 건 (문제 코드 × 요청 종류)", "돌려주는 것 : 일감 (담당 하나 · 일감 종류 · 쓸 도구 목록 · 마감 90초)",
               "              + 근거 묶음 (처리 건 상태 · 깨진 항목 · 규정 조각, 12,000 토큰)"], W) + down
    agent = tbox("③ 담당 에이전트 — 셋 중 하나  [판정은 코드]",
                 ["요식      점검 : 외부 6종 · 그 시각 영업 · 라스트오더", "          대체 : 요식 원장 후보 → 다시 점검 (최대 3곳)",
                  "액티비티  점검 : 외부 6종 (날씨 · 대기질 · 특보 · 지진)", "          대체 : 같은 대분류 · 비슷한 순 → 다시 점검",
                  "이동      점검 : 계획 경로 · 구간 교통 사건 (UTIC)", "          대체 : 다른 경로 → 시간표 판정기로 다시 찾기", "",
                  "안쪽 루프 : 다시 점검에 걸리면 다음 후보로 — 통과할 때까지", "",
                  "돌려주는 것 : 결과지 — 다음 할 일 · 고객용 문장 · 근거", "              + 일정 변경 제안 (기준 판 · 바뀐 항목 · 다른 안 둘)",
                  "★ 일정을 직접 바꾸지 않는다 · AI 모델을 부르지 않는다"], 70)
    tool = tbox("조회 도구 층", ["일감에 적힌 도구만", "같은 호출 두 번 거부", "12번 넘으면 멈춤", "못 읽으면 「모름」", "",
                              "-> PostgreSQL+pgvector", "-> 외부 API 6종", "-> 시간표 파일"], 26)
    L += side(agent, tool, {3: " 부름 -->", 5: " <-- 값 "})
    L += down
    L += tbox("④ 결과 검사  [코어의 코드 — 참고 구조의 평가 에이전트 자리]",
              ["받는 것     : 결과지", "돌려주는 것 : 통과 / 막음 — 근거가 있나 · 정말 그 고객 것인가 · 판 번호가 그대로인가"], W)
    L += [C + "|",
          C[:-9] + "+-------------------+",
          C[:-9] + "| 통과 · 바꿀 안?   |-- 아니오 --> ⑤ 못 했을 때",
          C[:-9] + "+-------------------+      그대로면 답만 기록 · 판이 밀렸으면 버리고 다음 감시에",
          C + "| 예                못 함이면 오류 기록 · 일정 그대로 · 운영자 오류 알림만",
          C + "v                  (고객 건을 사람에게 넘기지 않는다)"]
    L += tbox("⑥ 적용 — 새 일정 판  [코어 · 적용기]",
              ["받는 것     : 일정 변경 제안", "돌려주는 것 : 새 판 1개 (옛 판 보존) 또는 묻기 (보류 제안)",
               "              묻는 때 — 설문 「먼저 물어봐」 · 고객이 고정한 일정 · 안전 경보",
               "              설문 「바꿔 줘」면 바로 적용 · 앞뒤 이동은 여기서 다시 계산"], W) + down
    L += tbox("⑦ 알림 · 여행계획서  [코어 · 배달 일꾼]",
              ["받는 것     : 새 판 · 알림 문구", "돌려주는 것 : 디스코드 알림 1번 (재시도 3번 · 중복 0) · 링크가 새 판을 보여 줌"], W)
    L += [C + "|", C + "+--> 바깥 루프 : 다음 감시(1분) · 새벽 3시 · 신고 → 다시 ① — 여행이 끝날 때까지"]
    return chr(10).join(plain(x) for x in L)


def main():
    f1, f2 = fig1(), fig2()
    art = ascii_art()
    (OUT / "triPilot_멀티에이전트_플로우_v1.txt").write_text(art + "\n", encoding="utf-8")
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>guguroute 멀티 에이전트 흐름</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nanum+Gothic+Coding&display=swap"><style>
body{{margin:0;background:var(--paper);color:var(--ink);font-family:{SANS};line-height:1.6}}
main{{max-width:1600px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:28px;margin:0 0 6px}} h2{{font-size:21px;margin:34px 0 8px;border-bottom:1px solid var(--rule-solid);padding-bottom:6px}}
.lead{{background:var(--accent-tint);border:1px solid var(--accent-rule);border-radius:8px;padding:14px 18px;font-size:15.5px}}
.note{{font-size:13.5px;color:var(--muted)}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:var(--card)}}th,td{{border:1px solid var(--rule-solid);padding:7px 10px;text-align:left;vertical-align:top}}th{{background:var(--paper-2);white-space:nowrap}}
pre{{background:var(--card);border:1px solid var(--rule-solid);border-radius:6px;padding:14px;overflow-x:auto;font-family:{MONO};font-size:13px;line-height:1.45}}
{CSS}
@media print{{.diagram{{break-inside:avoid;overflow:visible}}.diagram svg{{min-width:0 !important;max-height:250mm;width:auto !important;max-width:100%;margin:0 auto}}pre{{font-size:9px}}}}
</style></head><body><main>
<h1>guguroute 멀티 에이전트 흐름 v1</h1>
<p class="note">2026-10-02 · 참고 구조(층마다 받는 것 · 돌려주는 것, 도구 층, 검사 · 복구 순환)의 모양으로 우리 실제 구조를 그렸다 · 사실 기준: final_project_cs 코드 · 줄 근거는 w5/코어_에이전트_입출력 v3</p>
<div class="lead">일정이 깨지면 코어가 처리 건을 열고, 담당 에이전트 하나(요식 · 액티비티 · 이동)에게 일감을 줍니다. 에이전트는 조회 도구로만 값을 읽어 다시 점검하고, 대체 후보를 차례로 다시 점검해 통과한 안을 <b>제안</b>으로 돌려줍니다. 코어가 그 제안을 코드로 검사하고, 통과하면 새 일정 판과 알림 1번을 냅니다. 이 일을 감시(1분) · 새벽 점검 · 신고가 여행이 끝날 때까지 되풀이합니다.<br>
참고 구조와 다른 점 셋 — <b>판정은 AI 가 아니라 코드</b>가 합니다(세 에이전트는 AI 모델을 부르지 않음) · <b>검사와 복구는 별도 에이전트가 아니라 코어</b>가 합니다 · <b>에이전트끼리 서로 부르지 않습니다</b>(코어를 거침).</div>

<h2>1. 전체 흐름 — 사건 하나가 새 일정이 되기까지</h2>
<div class="diagram">{f1}</div>

<h2>2. 층마다 받는 것 · 돌려주는 것</h2>
{table(["층", "누가", "받는 것", "돌려주는 것", "지금 상태"], STAGES)}

<h2>3. 조회 도구 · 데이터 층</h2>
<div class="diagram">{f2}</div>

<h2>4. 입구마다 — 에이전트를 거치는 것과 안 거치는 것</h2>
<p class="note">에이전트를 거치는 것은 감시 · 새벽 점검 · 사건 접수 API 로 열린 여행 건뿐이다. 고객 채팅은 여행 창구가 처리하지만 에이전트와 <b>같은 계산 함수</b>를 써서 결과가 갈리지 않는다.</p>
{table(["입구", "받는 것", "처리", "에이전트", "AI 모델이 하는 일"], ENTRIES)}

<h2>5. 참고 구조와 우리 구조 대응</h2>
{table(["참고 구조", "우리 구조", "있나"], MAP)}

<h2>6. 설계와 코드가 다른 곳 — 발표 · 문서에서 구현된 것처럼 쓰지 않는다</h2>
{table(["설계 · 자료에 있는 것", "지금 코드"], GAPS)}

<h2>7. 글자 그림 — 참고 자료와 같은 모양(복사해 쓰기용)</h2>
<p class="note">같은 내용을 상자 글자로 그렸다. 한글이 두 칸 폭인 고정폭 글꼴(나눔고딕코딩 · D2Coding)에서 줄이 맞는다 — 그래서 폭이 글꼴마다 달라지는 글자(가운뎃점 · 화살표 · 동그라미 숫자)는 쉼표 · -> · (1) 로 바꿔 썼다. 같은 폴더의 .txt 파일과 같다.</p>
<pre>{esc(art)}</pre>
</main></body></html>"""
    (OUT / "triPilot_멀티에이전트_플로우_v1.html").write_text(page, encoding="utf-8")
    print("ok", len(page) // 1024, "KB")


if __name__ == "__main__":
    main()
