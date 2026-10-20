# -*- coding: utf-8 -*-
"""guguroute 한눈에 — 멀티 에이전트 워크플로 · 시스템 아키텍처 (2026-10-02, v1)

    python make_arch_v1.py   → ../triPilot_아키텍처_멘토반영_v7.html

★근거는 셋뿐이다(팀이 예전에 쓴 아키텍처 · 구성도 문서는 반려본이라 쓰지 않는다 — 사용자 지시 2026-10-02).
  ① 부트캠프 양식 「AI 시스템 아키텍처(멀티 에이전트)」 · 「시스템 구성도」의 작성 가이드
  ② 교재 0715 · 0716 LangGraph 멀티에이전트 — 상태 · 노드 · 엣지, 감독자(Supervisor) 패턴, 조건 분기, 반복과 종료 조건, 실패 지점 표
  ③ final_project_cs 코드(2026-10-02 확인)
★0819 SW 요구사항 교재는 UML(유스케이스 · 클래스 · 시퀀스)만 있고 아키텍처 · 에이전트 흐름 그리는 법은 없다.
"""
import html
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
SANS = "'Noto Sans KR','Malgun Gothic',sans-serif"
MONO = "'Nanum Gothic Coding','NanumGothicCoding','D2Coding',monospace"
S = []


def esc(t):
    return html.escape(t, quote=False)


def T(x, y, s, cls="", anchor="middle"):
    c = f' class="{cls}"' if cls else ""
    S.append(f'<text{c} x="{x}" y="{y}" text-anchor="{anchor}">{esc(s)}</text>')


def R(x, y, w, h, cls="node", rx=10, dash=False):
    d = ' stroke-dasharray="6 5"' if dash else ""
    S.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}"{d}/>')


def node(x, y, w, h, title, lines=(), cls="node", tag=None):
    """가운데 맞춤 상자 — 제목 + 짧은 줄"""
    R(x, y, w, h, cls)
    n = len(lines)
    ty = y + h / 2 - (n * 17) / 2 + 5
    T(x + w / 2, ty, title, "h")
    for i, ln in enumerate(lines):
        T(x + w / 2, ty + 21 + i * 17, ln, "s")
    if tag:
        T(x + w - 10, y + 16, tag, "tag", "end")


def diamond(cx, cy, w, h, label, cls="dia"):
    S.append(f'<path class="{cls}" d="M{cx} {cy - h / 2} L{cx + w / 2} {cy} L{cx} {cy + h / 2} L{cx - w / 2} {cy} Z"/>')
    T(cx, cy + 5, label, "h2")


def P(pts, cls="edge", mk="a", both=False):
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    m = f' marker-end="url(#{mk})"' if mk else ""
    if both:
        m += f' marker-start="url(#{mk})"'
    S.append(f'<path class="{cls}" d="{d}"{m}/>')


def L(x, y, s, cls="lbl", anchor="middle"):
    T(x, y, s, cls, anchor)


DEFS = ('<defs>'
        + "".join(f'<marker id="{i}" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto-start-reverse"><path class="{c}" d="M0 0 L10 5 L0 10 Z"/></marker>'
                  for i, c in (("a", "ah"), ("g", "ah-g"), ("r", "ah-r"), ("b", "ah-b"), ("n", "ah-n"), ("o", "ah-o"), ("p", "ah-p"), ("t", "ah-t")))
        + '</defs>')


def svg(W, H, label):
    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(label)}">{DEFS}{"".join(S)}</svg>'


# ───────────── 그림 1 · 멀티 에이전트 플로우 v7 — 루프가 흐름 한가운데 보이게 (코덱스 검토 반영) ─────────────
def tag(x, y, kind):
    """상태 꼬리표 — 구현 · 진행 중 · 예정 · 검토 중"""
    cls, t = {"done": ("tg-done", "구현"), "wip": ("tg-wip", "진행 중"), "plan": ("tg-plan", "예정"), "look": ("tg-plan", "검토 중")}[kind]
    w = 14 + len(t) * 13
    R(x, y - 13, w, 18, cls, 9)
    T(x + w / 2, y + 1, t, "tg-t")
    return w


def nbox(x, y, w, h, title, lines=(), cls="node", status=None):
    """가운데 맞춤 상자 — 제목 + 짧은 줄 (+ 테두리 위 상태 꼬리표)"""
    R(x, y, w, h, cls, 10)
    n = len(lines)
    ty = y + h / 2 - n * 9 + 2
    T(x + w / 2, ty, title, "h2")
    for i, ln in enumerate(lines):
        T(x + w / 2, ty + 20 + i * 18, ln, "s")
    if status:
        tag(x + w - 10 - (14 + len({"done": "구현", "wip": "진행 중", "plan": "예정", "look": "검토 중"}[status]) * 13), y + 1, status)


def workflow():
    S.clear()
    W, H = 1800, 1480
    T(40, 40, "guguroute 멀티 에이전트 플로우 — 한 장", "big", "start")
    T(40, 66, "① 계획을 올릴 때 한 번 검증하고 ② 여행이 끝날 때까지 루프를 돈다 · 금색 굵은 선 = 되돌아가는 루프 · 붉은 점선 = 실패 · 판정은 코드(AI 아님)", "s", "start")
    tx = 1400
    for k in ("done", "wip", "plan"):
        tx += tag(tx, 62, k) + 8
    T(tx + 4, 66, "= 코드 상태", "s", "start")

    # 0 · 용어 + LLM 호출 vs 에이전트(그림으로)
    R(40, 84, 820, 118, "gloss", 10)
    T(58, 108, "용어", "h2", "start")
    terms = [("오케스트레이터", "흐름을 정하고 담당 에이전트 1개를 고르는 서버 코드"), ("에이전트", "트리거로 깨어나 툴로 조회 · 판단 · 재시도해 결과를 낸다"),
             ("툴", "에이전트가 부르는 조회 · 판정 기능"), ("케이스", "처리할 일 한 건 — 문제 항목 하나"), ("트리거", "에이전트를 깨우는 구체적 조건")]
    for i, (k, v) in enumerate(terms):
        cx, cy = (58, 132 + i * 20) if i < 3 else (470, 132 + (i - 3) * 20)
        T(cx, cy, k, "k-t", "start")
        T(cx + 100, cy, v, "s", "start")
    R(880, 84, 880, 118, "gloss", 10)
    T(898, 108, "LLM 호출과 에이전트의 차이", "h2", "start")
    T(898, 140, "LLM 호출", "k-in", "start")
    for i, t in enumerate(("질문", "LLM", "답")):
        R(990 + i * 110, 124, 80, 26, "mini", 6)
        T(1030 + i * 110, 142, t, "s2")
        if i:
            P([(1070 + (i - 1) * 110, 137), (988 + i * 110, 137)])
    T(1310, 142, "→ 끝 (한 번)", "s", "start")
    T(1420, 142, "우리: 줄 위치 · 분류 · 문장만", "s", "start")
    T(898, 180, "에이전트", "k-out", "start")
    for i, t in enumerate(("트리거", "툴로 조회", "판단")):
        R(990 + i * 110, 164, 80, 26, "mini-a", 6)
        T(1030 + i * 110, 182, t, "s2")
        if i:
            P([(1070 + (i - 1) * 110, 177), (988 + i * 110, 177)])
    P([(1290, 177), (1312, 177)])
    T(1316, 182, "결과 · 근거", "s2", "start")
    P([(1250, 190), (1250, 198), (1140, 198), (1140, 192)], "edge loop", "g")
    T(1420, 182, "안 되면 다시 조회 · 여행 끝까지 반복", "lbl-g", "start")

    # ① 계획 확인
    ay = 220
    R(40, ay, 1720, 330, "band-a", 14)
    T(60, ay + 28, "① 계획 확인 — 계획을 올릴 때 한 번", "band-t", "start")
    yc = ay + 110
    nbox(60, yc - 40, 170, 80, "계획 올리기", ["글 · 사진 · 파일"], "node", "done")
    nbox(250, yc - 40, 190, 80, "계획 읽기", ["LLM — 원문 줄 위치", "→ 일정 항목 + 근거 줄"], "node", "done")
    nbox(460, yc - 40, 170, 80, "장소 확인", ["툴 — 실제 장소 1곳"], "node", "done")
    nbox(650, yc - 40, 230, 80, "검증 체크리스트", ["유형별 검사 + 이동 가능 여부", "항목마다 ✔ / ✖ + 이유"], "agent", "wip")
    for x1, x2 in ((230, 248), (440, 458), (630, 648)):
        P([(x1, yc), (x2, yc)])
    diamond(980, yc, 150, 72, "전부 통과?")
    P([(880, yc), (903, yc)])
    nbox(1090, yc - 40, 200, 80, "등록 · 계획서 링크", ["감시 시작"], "core", "done")
    P([(1055, yc), (1088, yc)])
    L(1070, yc - 10, "예", "lbl")
    nbox(870, yc + 70, 220, 60, "✖ 항목 → 채팅", ["대안 추천 · 고쳐서 다시 입력"], "fail-soft", "wip")
    P([(980, yc + 36), (980, yc + 68)], "edge bad", "r")
    L(992, yc + 56, "아니오", "lbl-r", "start")
    P([(870, yc + 100), (765, yc + 100), (765, yc + 42)], "edge loop-b", "g")
    L(600, yc + 124, "고쳐서 다시 검증 (되돌림 루프)", "lbl-g", "start")
    nbox(870, yc + 150, 220, 50, "너무 부족하면 거절", ["다시 올리게 안내"], "plan-box", "plan")
    P([(980, yc + 130), (980, yc + 148)], "edge bad", "r")
    # 진행 화면 (SSE) — 업무 단계가 아니라 옆으로 나가는 표시
    sx, sw = 1320, 420
    R(sx, ay + 44, sw, 270, "screen", 12)
    T(sx + 16, ay + 68, "휴대폰 화면 — 검증 진행 표시 (SSE)", "h2", "start")
    tag(sx + sw - 60, ay + 66, "plan")
    rows = [("공통", None), ("장소가 실제로 있는지 확인", True), ("실제 이동 가능한 거리 · 시간인지 확인", True),
            ("음식점", None), ("그 시각 영업 · 브레이크 · 라스트오더", True), ("12:00 — 그날 휴무일", False),
            ("액티비티", None), ("운영일 · 운영시간 · 날씨 조건", True),
            ("부가 정보 (검증 아님)", None), ("주차 · 대기 시간 → 지도 링크", "info")]
    for i, (t, ok) in enumerate(rows):
        y = ay + 94 + i * 21
        if ok is None:
            T(sx + 16, y, t, "k-ck", "start")
        elif ok == "info":
            T(sx + 30, y, "· " + t, "s", "start")
        else:
            T(sx + 30, y, ("✔ " if ok else "✖ ") + t, "ck-ok" if ok else "ck-bad", "start")
    P([(765, yc - 40), (765, ay + 50), (sx - 2, ay + 50)], "edge dim", "a")
    L(1040, ay + 44, "검사 결과를 순서대로 화면에 표시 (예정)", "lbl")
    T(60, ay + 318, "사용자 성향: 고정 설문 대신 계획서 분석 + 대화형 질문", "s", "start")
    tag(392, ay + 316, "plan")

    # ② 지속 관리 — 원 모양 루프
    gy = ay + 350
    R(40, gy, 1720, 860, "band-b", 14)
    T(60, gy + 28, "② 여행 중 지속 관리 — 여행이 끝날 때까지 도는 루프", "band-t", "start")
    # 등록 → 감시 시작
    P([(1190, yc + 40), (1190, gy + 46), (155, gy + 46), (155, gy + 68)], "edge", "a")
    L(700, gy + 40, "등록하면 감시 시작", "lbl")
    top = gy + 70
    nbox(70, top, 170, 84, "다음 트리거 대기", ["(쉬는 상태)"], "node")
    nbox(280, top, 240, 84, "트리거", ["감시 1분 · 앞으로 90분 안 항목", "새벽 03~08시 · 고객 신고"], "node", "done")
    nbox(560, top, 210, 84, "오케스트레이터", ["문제 항목 → 케이스 열기", "→ 담당 에이전트 1개"], "core", "done")
    nbox(810, top, 240, 84, "에이전트 — 현재 항목 재점검", ["요식 또는 액티비티", "같은 외부 점검"], "agent", "done")
    for x1, x2 in ((240, 278), (520, 558), (770, 808)):
        P([(x1, top + 42), (x2, top + 42)])
    # 문제 있나?
    d1 = top + 150
    diamond(930, d1, 140, 64, "문제 있나?")
    P([(930, top + 84), (930, d1 - 34)])
    nbox(1570, d1 - 28, 170, 56, "그대로", ["영향 없음 · 근거만 남김"], "out")
    P([(1000, d1), (1568, d1)])
    L(1030, d1 - 8, "아니오", "lbl", "start")
    # 후보 재점검 (안쪽 루프)
    rt = top + 215
    nbox(810, rt, 240, 86, "다음 후보 1곳 재점검", ["순위순 · 같은 외부 점검", "+ 이동 판정 툴 (앞뒤 구간)", "통과하면 후보 목록에 담음"], "agent")
    P([(930, d1 + 32), (930, rt - 2)])
    L(942, d1 + 50, "예", "lbl", "start")
    d2 = rt + 43
    diamond(665, d2, 150, 70, "더 볼 후보?")
    P([(810, d2), (742, d2)])
    P([(665, d2 - 35), (665, rt - 22), (850, rt - 22), (850, rt - 2)], "edge loop-b", "g")
    L(560, rt - 30, "예 — 다음 후보 (안쪽 루프)", "lbl-g", "start")
    d3 = rt + 160
    diamond(665, d3, 160, 70, "통과한 곳 있나?")
    P([(665, d2 + 35), (665, d3 - 36)])
    L(677, d2 + 54, "아니오 — 다 봤거나 한도", "lbl", "start")
    L(677, d2 + 72, "(최대 3곳 · 툴 12회 · 90초)", "lbl", "start")
    nbox(280, d3 - 28, 240, 56, "못 함", ["일정 유지 · 사유 기록"], "fail")
    P([(585, d3), (522, d3)], "edge bad", "r")
    L(553, d3 - 8, "아니오", "lbl-r")
    # 검증 · 반영 → 묻기 / 새 버전 / 거부
    nbox(810, d3 - 34, 240, 68, "검증 · 반영", ["변경 제안 (최선 1 + 다른 안 2)", "근거 · 고객 소유 · 버전 확인"], "core", "done")
    P([(745, d3), (808, d3)])
    L(776, d3 - 8, "예", "lbl")
    diamond(1190, d3, 150, 70, "묻기 조건?")
    P([(1050, d3), (1113, d3)])
    nbox(1090, rt, 200, 86, "사용자에게 묻기", ["먼저 물어봐 · 고정 일정", "· 안전 경보일 때", "알림 · 채팅으로 다른 안"], "core", "done")
    P([(1190, d3 - 35), (1190, rt + 88)])
    L(1202, d3 - 50, "예", "lbl", "start")
    P([(1090, rt + 70), (1070, rt + 70), (1070, d3 - 20), (1052, d3 - 20)], "edge loop-b", "g")
    L(1190, rt - 10, "응답 오면 다시 검증", "lbl-g")
    nbox(1330, d3 - 34, 200, 68, "새 일정 버전 → 알림", ["이전 버전 보존", "디스코드 · 계획서 링크 갱신"], "core", "done")
    P([(1265, d3), (1328, d3)])
    L(1296, d3 - 8, "아니오", "lbl")
    # 모든 결과 → 여행 끝?
    bus = d3 + 110
    P([(1655, d1 + 28), (1655, bus), (227, bus)], "edge loop-b", "g")
    P([(1430, d3 + 34), (1430, bus - 3)], "edge", "a")
    P([(930, d3 + 34), (930, bus - 3)], "edge bad", "r")
    L(942, d3 + 62, "거부 → 일정 유지 · 오류 알림(운영자)", "lbl-r", "start")
    P([(400, d3 + 28), (400, bus - 3)], "edge bad", "r")
    L(700, bus - 10, "모든 결과가 여기로 모인다", "lbl-g")
    diamond(155, bus, 140, 70, "여행 끝?")
    P([(155, bus - 35), (155, top + 86)], "edge loop-b", "g")
    L(167, top + 250, "아니오", "lbl-g", "start")
    L(167, top + 270, "바깥 루프", "lbl-g", "start")
    L(167, top + 290, "다음 트리거로", "lbl", "start")
    S.append(f'<circle class="end" cx="155" cy="{bus + 80}" r="14"/><circle class="end-in" cx="155" cy="{bus + 80}" r="8"/>')
    P([(155, bus + 35), (155, bus + 64)])
    L(167, bus + 56, "예 — 끝", "lbl", "start")
    T(400, top + 300, "↻", "loop-mark")

    # 아래 — 에이전트마다 트리거 → 받음 → 냄 (한 줄씩)
    cy0 = bus + 120
    T(60, cy0 - 14, "에이전트마다 — 트리거 → 받음 → 냄 · 에이전트끼리는 직접 부르지 않는다(오케스트레이터를 거친다)", "h2", "start")
    specs = [("요식 에이전트", "agent", [("트리거", "90분 안 식사에 재난 · 지진 · 통제 / 새벽 휴무 / 늦음 신고"),
              ("받음", "식사 항목(장소 · 시각 · 인원) · 원인 · 식이 조건"), ("냄", "그대로 / 대체 식당 1 + 다른 안 2 / 못 함 + 사유"),
              ("부가", "대기 시간 — 공개 API 없음 → 지도 링크"), ("평가", "영업시간 사람 대조 100곳 중 99곳 일치")]),
             ("액티비티 에이전트", "agent", [("트리거", "90분 안 활동에 날씨 · 대기질 · 특보 · 지진 / 새벽 운영 안 함"),
              ("받음", "활동 항목(장소 · 시각 · 실내 여부) · 원인 · 설문"), ("냄", "그대로 / 대체 활동 + 다른 안 / 「바꿀까요?」 / 못 함"),
              ("부가", "주차 · 혼잡 — 확인할 수 없어 검증 안 함"), ("평가", "추천 적합도 — 사람 판정 기준 만드는 중")]),
             ("이동 판정 툴 (공용 · 에이전트 아님)", "tool", [("부르는 때", "후보 재점검 · 반영 때 앞뒤 구간 · 일정 생성 · 교통 사건"),
              ("받음", "출발지 · 도착지 · 출발 시각"), ("냄", "제시간? 성립 / 불가 · 경로 · 소요 · 근거 등급"),
              ("", "코드에는 아직 팀으로 등록 — 툴로 정리 필요"), ("평가", "판정 회귀 시험 168건 어긋남 0")])]
    for i, (name, cls, rows) in enumerate(specs):
        x = 60 + i * 565
        R(x, cy0, 550, 160, cls, 12)
        T(x + 16, cy0 + 26, name, "h2", "start")
        for j, (k, v) in enumerate(rows):
            y = cy0 + 52 + j * 23
            if k:
                T(x + 16, y, k, "k-" + {"트리거": "t", "부르는 때": "t", "받음": "in", "냄": "out", "부가": "ex", "평가": "ev"}[k], "start")
            T(x + 92, y, v, "s2" if k in ("트리거", "부르는 때", "받음", "냄") else "s", "start")

    T(40, H - 40, "※ 지금 코드: 감시 경로는 오케스트레이터가 에이전트를 부른다. 새벽 점검과 채팅은 같은 요식 · 액티비티 판단 코드를 직접 부른다(결과는 같다).", "s", "start")
    T(40, H - 18, "※ 평가 수치: 요식 영업시간 사람 대조(100곳) · 이동 판정 회귀 시험(168건) — 해당 시험 범위의 값이다. 알림은 지금 팀 디스코드 채널 하나로 나간다(개인 등록 · 시험 발송은 됨).", "s", "start")
    return svg(W, H, "멀티 에이전트 플로우")


# ───────────── 그림 2 · 시스템 구성도 — 부트캠프 참고 그림(AI Agent 구현실습3 원본 7 · 29쪽) 형식 ─────────────
def ic_person(x, y, s=1.0):
    S.append(f'<g class="ic"><circle cx="{x}" cy="{y}" r="{11*s}"/><path d="M{x-20*s} {y+40*s} Q{x-20*s} {y+14*s} {x} {y+14*s} Q{x+20*s} {y+14*s} {x+20*s} {y+40*s} Z"/></g>')


def ic_phone(x, y):
    S.append(f'<g class="ic-o"><rect x="{x-14}" y="{y-24}" width="28" height="48" rx="5"/><path d="M{x-5} {y+17} H{x+5}"/></g>')


def ic_db(x, y, cls="ic-o"):
    S.append(f'<g class="{cls}"><ellipse cx="{x}" cy="{y-12}" rx="16" ry="6"/><path d="M{x-16} {y-12} V{y+12} Q{x} {y+20} {x+16} {y+12} V{y-12} M{x-16} {y} Q{x} {y+8} {x+16} {y}"/></g>')


def ic_bolt(x, y):
    S.append(f'<circle class="bolt-bg" cx="{x}" cy="{y}" r="16"/><path class="bolt" d="M{x+2} {y-11} L{x-7} {y+2} H{x} L{x-2} {y+11} L{x+7} {y-2} H{x} Z"/>')


def ic_clock(x, y):
    S.append(f'<g class="ic-o"><circle cx="{x}" cy="{y}" r="12"/><path d="M{x} {y-7} V{y} L{x+5} {y+4}"/></g>')


def chip(x, y, w, h, cls, title, lines=(), tcls="h2"):
    R(x, y, w, h, cls, 8)
    T(x + w / 2, y + 22, title, tcls)
    for i, ln in enumerate(lines):
        T(x + w / 2, y + 41 + i * 17, ln, "s")


def flow(pts, kind="n", both=False):
    cls = {"n": "f-main", "a": "f-int", "o": "f-watch", "p": "f-state", "r": "f-bad"}[kind]
    P(pts, cls, kind, both)


def architecture():
    S.clear()
    W, H = 1500, 1160
    R(330, 14, 840, 48, "titlebar", 10)
    T(750, 47, "guguroute — 시스템 구성도", "title-w")
    T(750, 90, "모바일 앱 + FastAPI 서버 + 오케스트레이터 + 에이전트 2 + 공용 툴 + 상시 감시 — 여행 일정을 끝날 때까지 지킨다", "sub")

    R(306, 100, 728, 294, "srv-bound", 14)
    T(1028, 390, "같은 FastAPI 서버 안 (함수 호출)", "bound-t", "end")
    # 1 사용자
    R(30, 110, 180, 270, "b-blue", 12)
    T(120, 138, "1. 사용자 — 모바일", "bh-blue")
    ic_person(80, 168)
    ic_phone(155, 188)
    for i, t in enumerate(("· 모바일 웹앱", "  (자체 채팅 · 일정)", "· 여행계획서 링크", "· 외부 AI 앱 (보조)")):
        T(46, 246 + i * 21, t, "s2", "start")
    # 2 FastAPI
    R(320, 110, 250, 270, "b-green", 12)
    R(320, 110, 250, 34, "h-green", 12)
    T(445, 133, "2. FastAPI Application", "bh-w")
    ic_bolt(370, 172)
    T(395, 180, "FastAPI", "logo", "start")
    for i, t in enumerate(("· REST API — 계획 · 채팅 · 신고", "· SSE — 바뀜 신호 (구현)", "· MCP — 외부 AI 앱용 (보조)")):
        T(336, 214 + i * 19, t, "s2", "start")
    R(334, 276, 222, 46, "plan-box", 8)
    T(346, 295, "로그인", "h2", "start")
    tag(404, 293, "plan")
    T(346, 314, "지금은 브라우저 키로 식별", "s", "start")
    R(334, 328, 222, 46, "plan-box", 8)
    T(346, 347, "SSE — 검증 진행 표시", "s2", "start")
    tag(500, 345, "plan")
    T(346, 366, "계획 확인 중 화면 이탈해도 유지", "s", "start")
    flow([(210, 190), (318, 190)])
    T(264, 178, "계획 · 채팅 · 신고", "fl")
    T(264, 207, "(HTTP Request)", "fl2")
    flow([(318, 300), (212, 300)])
    T(264, 288, "답변 · 새 일정", "fl")
    T(264, 317, "(HTTP · SSE)", "fl2")

    # 3 처리 서버
    R(660, 110, 360, 270, "b-purple", 12)
    T(840, 136, "3. 일정 처리 · 오케스트레이터", "bh-purple")
    T(840, 155, "(판정은 코드)", "fl2")
    cards = [(676, 168, "계획 읽기", "규칙 우선", "AI는 줄 위치만"), (848, 168, "계획 검증", "유형별 검사 ✔ / ✖", "(진행 중)"),
             (676, 272, "채팅 처리", "대안 추천", "재입력 안내"), (848, 272, "오케스트레이터", "케이스 열기", "담당 에이전트 1개")]
    for x, y, t, a, b in cards:
        R(x, y, 158, 92, "core" if t == "오케스트레이터" else "card", 8)
        T(x + 79, y + 30, t, "h2")
        T(x + 79, y + 54, a, "s")
        T(x + 79, y + 73, b, "s")
    flow([(570, 190), (658, 190)])
    T(614, 178, "요청 전달", "fl")
    T(614, 207, "(함수 호출)", "fl2")
    flow([(658, 300), (572, 300)])
    T(614, 288, "결과", "fl")
    T(614, 317, "(JSON)", "fl2")

    # 4 AI 모델
    R(1140, 110, 330, 270, "b-lav", 12)
    T(1305, 138, "4. AI 모델 — 시험 중", "bh-purple")
    chip(1158, 156, 140, 66, "card", "로컬 모델", ["(Ollama)"])
    chip(1312, 156, 140, 66, "card", "API 모델", ["(비교 중)"])
    for i, t in enumerate(("· 아직 정하지 않음 — 로컬 · API 비교", "· 쓰는 곳: 줄 위치 · 분류 · 문장", "· 일정 판정에는 쓰지 않음")):
        T(1158, 250 + i * 22, t, "s2", "start")
    flow([(1020, 190), (1138, 190)])
    T(1080, 178, "원문 · 문장", "fl")
    T(1080, 207, "(프롬프트)", "fl2")
    flow([(1138, 300), (1022, 300)])
    T(1080, 288, "줄 위치 · 분류 · 문장", "fl")
    T(1080, 317, "(응답)", "fl2")

    # 공유 State (왼쪽)
    R(30, 460, 220, 190, "b-purple-d", 12)
    ic_db(140, 494, "ic-p")
    T(140, 530, "공유 State", "bh-purple")
    T(140, 548, "(PostgreSQL 16 + pgvector)", "fl2")
    for i, t in enumerate(("· 케이스 · 상태 12개", "· 일정 버전 (이력 보존)", "· 아웃박스 큐 (보낼 알림)")):
        T(48, 576 + i * 21, t, "s2", "start")
    flow([(140, 458), (140, 412), (700, 412), (700, 382)], "p", both=True)
    T(420, 430, "상태 읽기 · 쓰기 (버전이 맞을 때만)", "fl-p")

    # 5 에이전트 · 툴
    R(290, 450, 770, 262, "b-navy", 12)
    T(675, 476, "5. 담당 에이전트 1개 + 공용 툴", "bh-navy")
    flow([(860, 396), (860, 448)], "a")
    T(852, 430, "할 일 · 허용 툴 · 현재 일정 · 원인", "fl", "end")
    S.append('<path class="f-int-s" d="M393 500 H579"/>')
    T(486, 494, "둘 중 하나", "fl2")
    S.append('<path class="f-int" d="M670 492 V676"/>')
    T(864, 506, "공용 툴 — 에이전트 · 반영이 부른다", "fl2")
    tools = [(306, "요식 에이전트", "Worker Agent", "card-blue", "요식 DB · 1,225곳", "영업 · 라스트오더 점검"),
             (492, "액티비티 에이전트", "Worker Agent", "card-blue", "관광공사 장소 805곳", "운영 · 날씨 조건 점검"),
             (678, "이동 판정 툴", "공용 (에이전트 아님)", "card-green", "시간표 46만 행", "제시간? 판정 · 경로"),
             (864, "규정 검색 툴", "RAG 툴", "card-orange", "bge-m3 · pgvector", "규정 · 취소 조건 근거")]
    for x, t, role, cls, data, cap in tools:
        if cls == "card-blue":
            P([(x + 87, 500), (x + 87, 518)], "f-int", "a")
        R(x, 520, 174, 150, cls, 8)
        T(x + 87, 546, t, "h2")
        T(x + 87, 565, role, "fl2")
        R(x + 10, 580, 154, 40, "data", 6)
        T(x + 87, 605, data, "s")
        T(x + 87, 650, cap, "s2")
    T(675, 696, "두 에이전트는 같은 안쪽 루프 (후보 재점검 → 다음 후보 · 그림 1) · 데이터는 허용된 툴로만 조회", "fl2")

    # 6 상시 감시 파이프라인 (오른쪽)
    R(1100, 430, 370, 404, "b-orange", 12)
    T(1285, 458, "6. 상시 감시 파이프라인", "bh-orange")
    T(1285, 476, "(별도 프로세스 · 백그라운드 워커)", "fl2")
    steps = [("스케줄러", "1분 감시 · 새벽 03~08시 (따로 시작)"), ("외부 API 6종 수집", "기상 · 특보 · 지진 · 재난문자 · 교통 · 대기질"),
             ("1차 실패 → 폴백 소스", "대체까지 실패하면 오류로 기록"), ("현재 일정 버전 읽어 점검", "90분 안 항목 · 새벽엔 그날 영업(Google)"),
             ("문제 항목 · 원인 전달", "케이스는 오케스트레이터가 연다")]
    for i, (t, sub) in enumerate(steps):
        y = 490 + i * 66
        R(1118, y, 334, 54, "card-o", 8)
        T(1285, y + 22, t, "h2")
        T(1285, y + 41, sub, "s")
        if i:
            flow([(1285, y - 12), (1285, y - 2)], "o")
    ic_clock(1136, 517)
    R(1100, 846, 370, 58, "plan-box", 10)
    T(1285, 869, "사용자 제보 공유 (주 경로 아님)", "h2")
    T(1285, 890, "내비 앱처럼 다른 사용자가 본 상황 받기", "s")
    tag(1400, 866, "look")
    flow([(1118, 781), (1086, 781), (1086, 350), (1022, 350)], "o")
    T(1094, 420, "문제 항목 · 원인", "fl-o", "start")

    # 아랫줄 — 검증 · 반영 → 알림 → 사용자
    R(560, 742, 330, 90, "b-navy", 12)
    T(725, 766, "검증 · 반영 (오케스트레이터)", "bh-navy")
    T(725, 788, "근거 · 고객 소유 · 버전 확인 → 새 일정 버전", "s")
    T(725, 807, "물어봐 · 고정 · 안전 경보 → 사용자에게 묻기", "s")
    flow([(725, 712), (725, 740)])
    T(735, 731, "결과 · 변경 제안", "fl", "start")
    R(250, 742, 260, 90, "b-green", 12)
    T(380, 766, "7. 휴대폰 알림 · 계획서", "bh-green")
    T(380, 788, "아웃박스 → 워커 → 디스코드 (팀 채널)", "s")
    T(380, 807, "개인 디스코드: 등록 · 시험 발송만 됨", "s")
    flow([(560, 787), (512, 787)])
    T(536, 777, "새 버전", "fl")
    T(536, 805, "· 묻기", "fl2")
    flow([(105, 652), (105, 740)], "p")
    T(117, 700, "바뀜 신호 (SSE)", "fl-p", "start")
    R(30, 742, 150, 90, "b-blue", 12)
    ic_person(75, 768, 0.8)
    T(130, 795, "사용자", "h2")
    flow([(250, 787), (182, 787)])
    T(216, 777, "알림", "fl")
    R(926, 752, 140, 70, "b-red", 10)
    T(996, 780, "운영자", "h2")
    T(996, 801, "오류 알림만 · 콘솔", "s")
    flow([(890, 787), (924, 787)], "r")

    # 아래 네 칸
    by = 930
    panels = [(30, 520, "데이터 소스", ["요식 DB — 서울 식당 1,225곳", "관광공사 장소 — 서울 활동 805곳", "지하철 · 버스 시간표 46만 행",
                                       "규정 문서 (조각 + 임베딩)", "외부 API 6종 (무료 소스)"]),
              (565, 300, "인프라 · 배포", ["FastAPI · React(Next.js) · PostgreSQL", "CI — GitHub Actions 시험 · 빌드 (완료)", "CD — AWS 자동 배포 (아직 안 됨)", "AI — Ollama 로컬 모델 (시험 중)"]),
              (880, 400, "주요 특징", ["판정은 코드 — AI는 위치 · 분류 · 문장만", "1차 실패하면 폴백 소스로 다시", "일정 버전 보존 → 되돌리기 가능",
                                     "같은 알림은 한 번만 · 고객 건을 사람에게 안 넘김"]),
              (1295, 175, "범례", [])]
    for x, w, t, items in panels:
        R(x, by, w, 160, "panel", 10)
        T(x + w / 2, by + 24, t, "bh-navy")
        for i, it in enumerate(items):
            T(x + 18, by + 52 + i * 21, "✓ " + it if t == "주요 특징" else "· " + it, "s2", "start")
    for i, (k, t) in enumerate((("n", "주요 데이터 흐름"), ("a", "내부 연동"), ("o", "감시 데이터 흐름"), ("p", "State 흐름"), ("r", "실패 · 오류 알림"))):
        y = by + 50 + i * 22
        flow([(1310, y), (1356, y)], k)
        T(1364, y + 4, t, "s", "start")
    T(30, H - 22, "※ 점선 회색 상자 = 예정 · 검토 중. 이동은 코드에 아직 팀으로 등록 — 툴로 정리 필요. 사용자가 올린 계획은 서버가 일정으로 읽고, 감시가 깨진 일정을 찾으면 오케스트레이터가 담당 에이전트에 맡겨 대안을 정한 뒤 검증 · 반영하고 알린다. 여행이 끝날 때까지 되풀이한다.", "fl2", "start")
    return svg(W, H, "시스템 구성도")


CSS = f"""
:root{{--paper:#fbfcfd;--paper-2:#f1f4f8;--card:#ffffff;--ink:#161c28;--muted:#606b7e;--soft:#727d90;--rule:#dbe0ea;
--gold:#a8720c;--gold-t:rgba(168,114,12,.09);--gold-r:rgba(168,114,12,.42);--blue:#2f6c9a;--blue-t:rgba(47,108,154,.07);--blue-r:rgba(47,108,154,.38);
--red:#a33b3b;--red-t:rgba(163,59,59,.06);--red-r:rgba(163,59,59,.4);--green:#3d7a4f;--green-t:rgba(61,122,79,.07);--green-r:rgba(61,122,79,.4)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--paper:#15181d;--paper-2:#20252d;--card:#1a1f26;--ink:#e9edf3;--muted:#b0bac9;--soft:#9aa6b9;--rule:#39424f;
--gold:#e4b45c;--gold-t:rgba(228,180,92,.1);--gold-r:rgba(228,180,92,.45);--blue:#7fb2dc;--blue-t:rgba(127,178,220,.08);--blue-r:rgba(127,178,220,.4);
--red:#e08a8a;--red-t:rgba(224,138,138,.08);--red-r:rgba(224,138,138,.45);--green:#8cc79c;--green-t:rgba(140,199,156,.08);--green-r:rgba(140,199,156,.45)}}}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:{SANS};line-height:1.6}}
main{{max-width:1540px;margin:0 auto;padding:24px 16px 60px}}
h1{{font-size:28px;margin:0 0 6px}} h2{{font-size:21px;margin:34px 0 8px}}
.lead{{background:var(--gold-t);border:1px solid var(--gold-r);border-radius:8px;padding:14px 18px;font-size:15.5px}}
.note{{font-size:13.5px;color:var(--muted)}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:var(--card);margin-top:8px}}th,td{{border:1px solid var(--rule);padding:7px 10px;text-align:left;vertical-align:top}}th{{background:var(--paper-2)}}
.diagram{{border:1px solid var(--rule);border-radius:6px;background:var(--card);overflow-x:auto}}
.diagram svg{{display:block;width:100%;min-width:1100px;height:auto;color:var(--ink)}}
.diagram text{{fill:currentColor;font-family:{SANS};font-size:14px}}
.diagram .h{{font-size:16.5px;font-weight:700}} .diagram .h2{{font-size:15px;font-weight:700}}
.diagram .s{{fill:var(--muted);font-size:13px}} .diagram .s2{{font-size:13.5px}}
.diagram .cap{{fill:var(--soft);font-family:{MONO};font-size:12.5px;letter-spacing:.06em}}
.diagram .tag{{fill:var(--gold);font-family:{MONO};font-size:11px}} .diagram .tag2{{fill:var(--gold);font-size:13px;font-weight:700}}
.diagram .lbl{{fill:var(--muted);font-size:12.5px}} .diagram .lbl-g{{fill:var(--gold);font-size:13px;font-weight:700}} .diagram .lbl-r{{fill:var(--red);font-size:13px;font-weight:700}}
.diagram .node{{fill:var(--card);stroke:var(--rule)}} .diagram .user{{fill:var(--card);stroke:var(--soft)}}
.diagram .core{{fill:var(--gold-t);stroke:var(--gold-r)}} .diagram .agent{{fill:var(--blue-t);stroke:var(--blue-r)}}
.diagram .fail{{fill:var(--red-t);stroke:var(--red-r);stroke-dasharray:5 4}} .diagram .dia{{fill:var(--card);stroke:var(--soft)}}
.diagram .state{{fill:var(--green-t);stroke:var(--green-r)}} .diagram .band{{fill:var(--paper-2);stroke:var(--rule)}} .diagram .lane{{fill:var(--card);stroke:var(--rule)}}
.diagram .job{{fill:var(--card);stroke:var(--rule)}} .diagram .queue{{fill:var(--gold-t);stroke:var(--gold-r);stroke-dasharray:5 4}}
.diagram .db{{fill:var(--green-t);stroke:var(--green-r)}} .diagram .model{{fill:var(--card);stroke:var(--soft);stroke-dasharray:5 4}} .diagram .ext{{fill:var(--paper-2);stroke:var(--rule)}}
.diagram .start{{fill:var(--ink)}} .diagram .end{{fill:none;stroke:var(--ink);stroke-width:2}} .diagram .end-in{{fill:var(--ink)}}
.diagram .edge{{fill:none;stroke:var(--muted);stroke-width:1.4;stroke-linejoin:round}}
.diagram .edge.loop{{stroke:var(--gold);stroke-width:1.8;stroke-dasharray:8 5}} .diagram .edge.bad{{stroke:var(--red);stroke-dasharray:5 4}}
.diagram .edge.async{{stroke:var(--gold);stroke-width:1.6;stroke-dasharray:6 5}} .diagram .edge.dim{{stroke-dasharray:4 4}}
.diagram .role{{fill:var(--gold);font-family:{MONO};font-size:12px}} .diagram .role-b{{fill:var(--blue);font-family:{MONO};font-size:12px}}
.diagram .pill{{font-size:11.5px;font-weight:700;fill:#fff}} .diagram .pill-in{{fill:var(--blue)}} .diagram .pill-out{{fill:var(--gold)}}
.diagram .agent-band{{fill:var(--blue-t);stroke:var(--blue-r)}} .diagram .bar{{fill:var(--card);stroke:var(--blue-r)}}
.diagram .out{{fill:var(--card);stroke:var(--gold-r)}} .diagram .out-bad{{fill:var(--red-t);stroke:var(--red-r);stroke-dasharray:5 4}}
.diagram .brace{{fill:none;stroke:var(--blue);stroke-width:1.4}}
.diagram .tool{{fill:var(--green-t);stroke:var(--green-r)}} .diagram .tool-note{{fill:var(--green-t);stroke:var(--green-r);stroke-dasharray:5 4}}
.diagram .ah{{fill:var(--muted)}} .diagram .ah-g{{fill:var(--gold)}} .diagram .ah-r{{fill:var(--red)}} .diagram .ah-b{{fill:var(--blue)}}
.diagram .titlebar{{fill:#1f3a6e}} .diagram .title-w{{fill:#fff;font-size:24px;font-weight:800}} .diagram .sub{{fill:#1f3a6e;font-size:16px;font-weight:700}}
.diagram .b-blue{{fill:#fff;stroke:#5b8fd6;stroke-width:1.6}} .diagram .b-green{{fill:#fff;stroke:#3f9a5c;stroke-width:1.6}} .diagram .h-green{{fill:#3f9a5c}}
.diagram .b-purple{{fill:#f7f5ff;stroke:#8a7bd8;stroke-width:1.6}} .diagram .b-lav{{fill:#f4f1ff;stroke:#a596e6;stroke-width:1.6}}
.diagram .b-purple-d{{fill:#f7f5ff;stroke:#8a7bd8;stroke-width:1.6;stroke-dasharray:6 4}} .diagram .b-navy{{fill:#fff;stroke:#1f3a6e;stroke-width:1.6}}
.diagram .b-orange{{fill:#fffaf3;stroke:#e08a2c;stroke-width:1.6;stroke-dasharray:7 5}} .diagram .b-red{{fill:#fff6f6;stroke:#c95555;stroke-width:1.4}}
.diagram .endpoint{{fill:#f3faf5;stroke:#9fd0ad}} .diagram .card{{fill:#fff;stroke:#c9c2ee}} .diagram .card-blue{{fill:#f2f7ff;stroke:#7aa6e0}}
.diagram .card-green{{fill:#f1f9f3;stroke:#6fb383}} .diagram .card-orange{{fill:#fff6ec;stroke:#e9a35a}} .diagram .card-o{{fill:#fff;stroke:#f0b878}}
.diagram .data{{fill:#fff;stroke:#c8ced8}} .diagram .panel{{fill:#fff;stroke:#c3cad6;stroke-dasharray:5 4}}
.diagram .bh-blue{{fill:#2f5fae;font-size:16px;font-weight:700}} .diagram .bh-w{{fill:#fff;font-size:16px;font-weight:700}} .diagram .bh-green{{fill:#2f7d47;font-size:15px;font-weight:700}}
.diagram .bh-purple{{fill:#4b3aa8;font-size:16px;font-weight:700}} .diagram .bh-navy{{fill:#1f3a6e;font-size:16px;font-weight:700}} .diagram .bh-orange{{fill:#c56a10;font-size:16px;font-weight:700}}
.diagram .logo{{fill:#0e8a7a;font-size:24px;font-weight:700}} .diagram .mono{{font-family:{MONO};font-size:11.5px;fill:#2b3442}}
.diagram .fl{{fill:#1f2937;font-size:12.5px;font-weight:600}} .diagram .fl2{{fill:#5d6878;font-size:12px}} .diagram .fl-p{{fill:#6a54c9;font-size:12.5px;font-weight:600}} .diagram .fl-o{{fill:#c56a10;font-size:12.5px;font-weight:600}}
.diagram .ic{{fill:#1f3a6e}} .diagram .ic-o{{fill:none;stroke:#1f3a6e;stroke-width:2}} .diagram .ic-p{{fill:none;stroke:#6a54c9;stroke-width:2}}
.diagram .bolt-bg{{fill:#0e8a7a}} .diagram .bolt{{fill:#fff}}
.diagram .f-main{{fill:none;stroke:#1f3a6e;stroke-width:1.8}} .diagram .f-int{{fill:none;stroke:#7a8597;stroke-width:1.4;stroke-dasharray:6 4}} .diagram .f-int-s{{fill:none;stroke:#1f3a6e;stroke-width:1.4}}
.diagram .f-watch{{fill:none;stroke:#e08a2c;stroke-width:2}} .diagram .f-state{{fill:none;stroke:#7d68d6;stroke-width:1.6;stroke-dasharray:6 4}} .diagram .f-bad{{fill:none;stroke:#c95555;stroke-width:1.5;stroke-dasharray:5 4}}
.diagram .ah-n{{fill:#1f3a6e}} .diagram .ah-o{{fill:#e08a2c}} .diagram .ah-p{{fill:#7d68d6}}
.diagram .big{{font-size:26px;font-weight:800}} .diagram .band-a{{fill:#f6f9ff;stroke:#9db8e6;stroke-width:1.4}} .diagram .band-b{{fill:#fbfaf6;stroke:#d9c79a;stroke-width:1.4}}
.diagram .band-t{{fill:#1f3a6e;font-size:18px;font-weight:800}} .diagram .gloss{{fill:#fff;stroke:#c3cad6}} .diagram .num{{fill:var(--gold);font-family:{MONO};font-size:15px;font-weight:700}}
.diagram .tg-done{{fill:#e6f4ea;stroke:#5fae78}} .diagram .tg-wip{{fill:#e8f0fd;stroke:#6f9be0}} .diagram .tg-plan{{fill:#f3f3f3;stroke:#9aa3ae;stroke-dasharray:3 2}} .diagram .tg-t{{font-size:11.5px;font-weight:700;fill:#2b3442}}
.diagram .k-t{{fill:#8a5a00;font-size:13px;font-weight:700}} .diagram .k-in{{fill:#2f6c9a;font-size:13px;font-weight:700}} .diagram .k-ck{{fill:#3d7a4f;font-size:13px;font-weight:700}}
.diagram .k-out{{fill:#a8720c;font-size:13px;font-weight:700}} .diagram .k-ex{{fill:#727d90;font-size:13px;font-weight:700}} .diagram .k-ev{{fill:#6a54c9;font-size:13px;font-weight:700}}
.diagram .screen{{fill:#fff;stroke:#1f3a6e;stroke-width:1.6}} .diagram .ck-ok{{fill:#2f6cd0;font-size:13.5px;font-weight:600}} .diagram .ck-bad{{fill:#c0392b;font-size:13.5px;font-weight:600}}
.diagram .res{{fill:#fff;stroke:#c3cad6}} .diagram .plan-box{{fill:#fafafa;stroke:#9aa3ae;stroke-dasharray:5 4}} .diagram .role-g{{fill:#3d7a4f;font-family:{MONO};font-size:12px}}
.diagram .agent-wrap{{fill:#fff;stroke:#7aa6e0;stroke-width:1.4;stroke-dasharray:6 4}} .diagram .edge.tl{{stroke:#3d7a4f;stroke-width:1.5;stroke-dasharray:6 4}} .diagram .lbl-gr{{fill:#3d7a4f;font-size:12.5px;font-weight:600}} .diagram .ah-t{{fill:#3d7a4f}}
.diagram .mini{{fill:#fff;stroke:#9db8e6}} .diagram .mini-a{{fill:#eef4fd;stroke:#6f9be0}} .diagram .fail-soft{{fill:#fff6f6;stroke:#d98b8b}}
.diagram .edge.loop-b{{stroke:#c98a0c;stroke-width:3;stroke-dasharray:none}} .diagram .loop-mark{{fill:#c98a0c;font-size:120px;font-weight:700;opacity:.22}}
.diagram .srv-bound{{fill:none;stroke:#1f3a6e;stroke-width:1.4;stroke-dasharray:8 5}} .diagram .bound-t{{fill:#1f3a6e;font-size:12.5px;font-weight:700}}
@media print{{.diagram{{break-inside:avoid;overflow:visible}}.diagram svg{{min-width:0 !important;max-height:250mm;width:auto !important;max-width:100%;margin:0 auto}}}}
"""

MENTOR = [
    ("2회차 09-11", "아키텍처는 세부 컨트롤러 구조 말고 큰 그림으로", "그림 2 — 상태 머신 · 엔드포인트 목록 같은 세부를 빼고 블록 7개로"),
    ("2회차", "「팀 모듈」 같은 개발 용어 대신 에이전트 설명으로", "「모듈」을 빼고 「이동 판정 툴」 · 에이전트 카드로 설명"),
    ("2회차 · 3회차", "각 에이전트를 트리거 → 인풋 → 아웃풋으로 정의 · 트리거는 구체적으로", "그림 1 ② 에이전트 카드 — 트리거 · 받음 · 점검 · 냄 줄 (「일정 사고 문의」 대신 「식사 90분 전 재난문자 · 지진 · 도로 통제」처럼)"),
    ("2회차", "단순 LLM 호출과 에이전트 플로우를 구분", "그림 1 위 오른쪽 상자 — LLM 호출은 줄 위치 · 분류 · 문장만, 에이전트는 트리거 → 조회 → 판단 → 반복"),
    ("2회차 · 3회차", "에이전트 플로우 전체 아키텍처를 한눈에", "그림 1 한 장에 ① 계획 확인 + ② 지속 관리"),
    ("2회차 · 3회차", "정량 평가 기준을 미리 정의", "에이전트 카드 「평가」 줄 — 잰 값만 적고, 없는 것은 「기준 만드는 중」"),
    ("2회차", "진입은 외부 서비스(ChatGPT) 경유 말고 자체 채팅", "그림 2 사용자 블록 — 모바일 웹앱 자체 채팅이 주, 외부 AI 앱은 보조"),
    ("2회차", "실시간 대기 시간은 직접 제공 어려움 → 링크 안내", "요식 카드 「부가」 — 지도 링크로 안내"),
    ("3회차 09-14", "용어(「여행코어」 등)를 먼저 정의하고 쓰기", "그림 1 맨 위 용어 상자"),
    ("3회차", "CI/CD — AWS 자동 배포", "그림 2 아래 「인프라 · 배포」 — CI 완료 · CD 아직 안 됨"),
    ("4회차 10-01", "한 장으로 이해되는 플로우, 인풋 · 아웃풋 명시", "그림 1 전체 — 상자마다 받음 · 냄"),
    ("4회차", "계획 확인 중 SSE 스트림 처리 (화면 이탈 시 재처리 문제)", "그림 1 ① 5단계 · 그림 2 FastAPI 블록 — 예정으로 표시 (바뀜 신호 SSE 는 이미 있음)"),
    ("4회차", "Validation 체크리스트 고도화 — 유형별 세분화 · 진행 상황 노출 · 파랑/빨강", "그림 1 ① 4 · 5단계 — 음식점 · 액티비티 항목, ✔ 파랑 · ✖ 빨강"),
    ("4회차", "Validation 항목과 부가 정보 구분 (예: 주차)", "그림 1 ① 결과 줄 · 카드 「부가」 줄"),
    ("4회차", "실패 항목은 채팅으로 대안 · 재입력 유도, 확인 불가면 거절", "그림 1 ① 6 결과"),
    ("4회차", "고정 설문 대신 계획서 분석 + 대화형 질문", "그림 1 ① 6 결과 아래 — 예정"),
    ("4회차", "로그인 우선 (복구 이메일보다 먼저)", "그림 2 FastAPI 블록 — 로그인 예정"),
    ("4회차", "모바일 우선 · 폰으로 실제 알림", "그림 2 사용자 블록 · 7 휴대폰 알림"),
    ("4회차", "실시간 정보 공유 구조 (내비 앱 방식) 리서치", "그림 1 트리거 · 그림 2 감시 파이프라인 — 검토 중"),
]
CODEX = [
    ("안쪽 루프가 글 한 줄뿐 — 되돌아가는 화살표 없음", "반영", "그림 1 ② — 재점검 → ◇더 볼 후보? → 예면 재점검으로 되돌아가는 굵은 금색 선 · ◇통과한 곳 있나? 로 변경 제안 / 못 함 분기"),
    ("바깥 루프가 「사용자 제보 공유(검토 중)」로 돌아감 · 「여행 끝?」 없음", "반영", "모든 결과가 한 줄로 모여 ◇여행 끝? → 아니오면 「다음 트리거 대기」로, 예면 끝"),
    ("실패 · 영향 없음 뒤 감시로 돌아가는 길 없음", "반영", "그대로 · 못 함 · 검증 거부 · 새 버전 모두 같은 줄로 합류"),
    ("「현재 항목 재점검 → 문제 있나?」 단계가 사라짐", "반영", "에이전트 상자를 「현재 항목 재점검」으로 · ◇문제 있나? 아니오 → 그대로"),
    ("묻기와 새 버전이 한 결과로 섞임 · 안전 경보 빠짐 · 응답 후 경로 없음", "반영", "◇묻기 조건?(먼저 물어봐 · 고정 일정 · 안전 경보) → 사용자에게 묻기 → 응답 오면 다시 검증(금색 되돌림)"),
    ("계획 등록과 지속 관리가 이어지지 않음", "반영", "「등록 · 계획서 링크」 → 「다음 트리거 대기」 선"),
    ("SSE 진행 화면을 업무 단계처럼 직렬로 둠 · 현재형 설명", "반영", "검증 상자에서 옆으로 나가는 점선 · 「(예정)」 표기"),
    ("✖ → 채팅 → 고쳐서 다시 검증 화살표 없음", "반영", "그림 1 ① 금색 되돌림 루프"),
    ("트리거 「90분 전」이 감시 범위와 헷갈림", "반영", "「90분 안 식사 · 활동에」로 통일"),
    ("구성도: 감시가 케이스를 만드는 것처럼 그림", "반영", "그림 2 ⑥ 마지막 단계 「문제 항목 · 원인 전달 — 케이스는 오케스트레이터가 연다」"),
    ("구성도: 네 칸 모두 「담당」처럼 보임", "반영", "그림 2 ⑤ 「둘 중 하나」 화살표는 에이전트 둘에만, 툴은 「공용 툴」 칸으로 분리"),
    ("구성도: 2 · 3이 서로 다른 서버처럼 보임", "반영", "점선 경계 「같은 FastAPI 서버 안」"),
    ("구성도: 현재 식별 방식 · 바뀜 신호 경로 없음 · 제보 공유가 주 경로 안", "반영", "「지금은 브라우저 키」 · 공유 State → 사용자 「바뀜 신호(SSE)」 · 제보 공유를 경계 밖으로"),
    ("구성도: 모델 칸에 임베딩이 섞임", "반영", "임베딩(bge-m3)은 규정 검색 툴 칸으로"),
    ("용어 · LLM 차이 상자를 줄여라", "일부", "멘토 2 · 3회차가 직접 요구한 것이라 남김 — 대신 LLM 차이는 글 대신 작은 그림(한 번 vs 반복)으로"),
    ("Google 영업시간 · Next.js · 「중복 0」 · 「되돌리기」는 근거 없음", "코드로 확인", "새벽 점검 코드(dawn_check)가 Google 장소를 부름 · 웹 package.json 에 next · react · 알림 표 UNIQUE 중복 방지 키 · 되돌리기 API(/rollback) 있음 — 「중복 0」은 「같은 알림은 한 번만」으로 바꿔 씀"),
    ("타임라인 UI · 앱 배포 · 6명 사용 · 실제 사례 · 경쟁 비교", "그림 밖", "화면 설계 · 시연 · 발표 장표 몫"),
]
NOT_HERE = [
    ("타겟 — 외국인 제외 · 「유능한 개인 여행 비서」", "서비스 기획 · 발표 내용 — 그림에는 국적 표시를 넣지 않았다"),
    ("발표 자료 구성 · 경쟁 서비스 비교 · 근거 데이터", "발표 자료 몫"),
    ("타임라인 UI · 검사 단계 화면 디자인", "화면 설계 몫 — 플로우에는 ✔/✖ 표시 방식만 넣었다"),
    ("앱 배포 후 6명 직접 사용 · 토요일 시연", "할 일 — 그림 대상 아님"),
]


def table(head, rows):
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


def main():
    f1, f2 = workflow(), architecture()
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>guguroute 멘토 반영 플로우</title><style>{CSS}</style></head><body><main>
<h1>guguroute — 멀티 에이전트 플로우 · 시스템 구성도 (멘토링 반영)</h1>
<p class="note">2026-10-02 · v7 · 멘토링 수행일지 2~4회차(09-11 · 09-14 · 10-01)에서 시스템 아키텍처 · 에이전트 플로우에 대한 지적만 골라 반영 · 형식은 부트캠프 참고 구성도(AI Agent 구현실습3 원본 7 · 29쪽) · 사실은 final_project_cs 코드</p>
<div class="lead">멘토 지적 19개와 코덱스 독립 검토를 반영했습니다. 두 루프(안쪽 = 다음 후보, 바깥 = 여행 끝까지)를 흐름 한가운데 굵은 금색 선으로 그렸습니다. 그림 1은 <b>한 장</b>에 ① 계획을 올릴 때의 검증과 ② 여행 중 지속 관리를 담고, 에이전트마다 <b>트리거 · 받음 · 점검 · 냄 · 평가</b>를 적었습니다. 그림 2는 세부를 빼고 <b>큰 그림</b>으로 줄였습니다. 아직 없는 것(SSE 검증 스트림 · 로그인 · 대화형 성향 질문 · AWS 배포)은 「예정」으로 표시했습니다.</div>

<h2>1. 멀티 에이전트 플로우 — 한 장</h2>
<div class="diagram">{f1}</div>

<h2>2. 시스템 구성도</h2>
<div class="diagram">{f2}</div>

<h2>3. 멘토 지적 → 그림에서</h2>
{table(["회차", "멘토 지적", "그림에서"], MENTOR)}

<h2>4. 코덱스 독립 검토 → v7 에서</h2>
<p class="note">코덱스(gpt-6.1-sol)에게 v6 그림 · 멘토 일지 원문 · 참고 구성도 · 루프가 보이던 v4 를 주고 따로 검토하게 했다. 지적마다 반영 여부를 적는다.</p>
{table(["코덱스 지적", "처리", "v7 에서"], CODEX)}

<h2>5. 일지에 있지만 이 그림의 대상이 아닌 것</h2>
{table(["지적", "왜 여기 없나"], NOT_HERE)}
</main></body></html>"""
    (OUT / "triPilot_아키텍처_멘토반영_v7.html").write_text(page, encoding="utf-8")
    print("ok", len(page) // 1024, "KB")


if __name__ == "__main__":
    main()
