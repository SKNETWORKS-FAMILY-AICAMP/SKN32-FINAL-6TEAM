# -*- coding: utf-8 -*-
"""triPilot 유스케이스 v3 — 「유스케이스 2026-10-02 v6」 브리핑 「한눈에」 그림처럼 좌표를 손으로 잡아 그린다.

    python make_usecase_v3_hand.py   → ../triPilot_유스케이스_한장_v3.html · .svg

★배치 원칙
  - 칸 세 줄(가운데 경계 안) + 왼쪽 사람 · 앱 + 오른쪽 시스템 행위자. 상자는 칸 · 줄 격자에 놓는다.
  - 선은 칸 사이 통로(x 580~630 · 880~940)와 왼쪽 통로(x 250~330)로만 지나간다 — 선끼리 엇갈리지 않게 길을 직접 정했다.
  - 구역 사이 «include»(B · D → C 일정 조율)는 긴 선 대신 「참조 상자」로 잇는다(같은 유스케이스 UC-12).
  - 여러 구역에 걸린 시스템 행위자(AI 모델 · 장소 정보 · 알림 채널)는 구역마다 옆에 다시 그린다(같은 행위자).
★스타일은 그 문서의 CSS 그대로(흰 상자 · #dbe0ea 테두리 · 핵심만 옅은 금색 · 구역 판 #f1f4f8 · 선 1.15 · 고정폭 이름표).
"""
import html
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
SANS = "'Noto Sans KR','Malgun Gothic',sans-serif"
MONO = "'NanumGothicCoding','Consolas',monospace"

COL = {1: 330, 2: 630, 3: 940}
CW, NH, PITCH = 250, 56, 74
LEFT_X, LEFT_W = 40, 210
RIGHT_X, RIGHT_W = 1262, 236
FRAME_X1, FRAME_X2 = 300, 1212

S = []          # svg 조각
N = {}          # 이름 → (x, y, w, h)


def esc(t):
    return html.escape(t, quote=False)


def node(key, col, row_y, title, code="", note="", kind=""):
    x, y = COL[col], row_y
    cls = {"": "node", "core": "core-node", "ext": "ext-node", "proxy": "proxy-node"}[kind]
    N[key] = (x, y, CW, NH)
    S.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{CW}" height="{NH}" rx="6"/>')
    tx = x + 16
    if code:
        S.append(f'<text class="svg-letter" x="{tx}" y="{y + 24}">{code}</text>')
        tx2 = tx + 46
    else:
        tx2 = tx
    S.append(f'<text x="{tx2}" y="{y + 24}">{esc(title)}</text>')
    if note:
        S.append(f'<text class="svg-note" x="{x + 16}" y="{y + 44}">{esc(note)}</text>')


def actor(key, x, y, w, h, title, note, icons):
    N[key] = (x, y, w, h)
    S.append(f'<rect class="node" x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>')
    ix = x + 14
    for ic in icons:
        S.append(ICON[ic](ix, y + 14))
        ix += 30
    S.append(f'<text x="{ix + 6}" y="{y + 26}">{esc(title)}</text>')
    lines = note if isinstance(note, list) else [note]
    for i, ln in enumerate(lines):
        S.append(f'<text class="svg-note" x="{ix + 6}" y="{y + 46 + i * 18}">{esc(ln)}</text>')


def ic_person(x, y):
    return (f'<g class="icon"><circle cx="{x + 11}" cy="{y + 5}" r="5"/>'
            f'<path d="M{x + 11} {y + 10} V{y + 24} M{x + 1} {y + 16} H{x + 21} M{x + 11} {y + 24} L{x + 4} {y + 34} M{x + 11} {y + 24} L{x + 18} {y + 34}"/></g>')


def ic_bot(x, y):
    return (f'<g class="icon"><rect x="{x}" y="{y + 7}" width="22" height="19" rx="4"/>'
            f'<path d="M{x + 11} {y} V{y + 7} M{x + 6} {y + 15} H{x + 8} M{x + 14} {y + 15} H{x + 16} M{x + 6} {y + 21} H{x + 16}"/></g>')


def ic_clock(x, y):
    return f'<g class="icon"><circle cx="{x + 11}" cy="{y + 13}" r="10"/><path d="M{x + 11} {y + 7} V{y + 13} L{x + 16} {y + 16}"/></g>'


def ic_db(x, y):
    return (f'<g class="icon"><ellipse cx="{x + 11}" cy="{y + 4}" rx="10" ry="4"/>'
            f'<path d="M{x + 1} {y + 4} V{y + 24} M{x + 21} {y + 4} V{y + 24} M{x + 1} {y + 14} Q{x + 11} {y + 20} {x + 21} {y + 14} M{x + 1} {y + 24} Q{x + 11} {y + 30} {x + 21} {y + 24}"/></g>')


def ic_bell(x, y):
    return (f'<g class="icon"><path d="M{x + 3} {y + 21} V{y + 12} A8 8 0 0 1 {x + 19} {y + 12} V{y + 21} H{x} H{x + 22} '
            f'M{x + 9} {y + 26} H{x + 13}"/></g>')


def ic_spark(x, y):
    return (f'<g class="icon"><path d="M{x + 11} {y} V{y + 26} M{x - 2} {y + 13} H{x + 24} M{x + 2} {y + 4} L{x + 20} {y + 22} '
            f'M{x + 20} {y + 4} L{x + 2} {y + 22}"/></g>')


ICON = {"person": ic_person, "bot": ic_bot, "clock": ic_clock, "db": ic_db, "bell": ic_bell, "spark": ic_spark}


def path(pts, kind="assoc"):
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    cls, mk = {"assoc": ("edge", ""), "inc": ("edge inc", ' marker-end="url(#vee)"'),
               "ext": ("edge ext", ' marker-end="url(#vee-gold)"'), "gen": ("edge", ' marker-end="url(#tri)"')}[kind]
    S.append(f'<path class="{cls}" d="{d}"{mk}/>')


def R(k):   # 오른쪽 가운데
    x, y, w, h = N[k]
    return x + w, y + h / 2


def L(k):
    x, y, w, h = N[k]
    return x, y + h / 2


def group(y1, y2, letter, title, tone=""):
    S.append(f'<rect class="group-frame{tone}" x="{FRAME_X1 + 10}" y="{y1}" width="{FRAME_X2 - FRAME_X1 - 20}" height="{y2 - y1}" rx="8"/>')
    S.append(f'<text class="svg-label" x="{FRAME_X1 + 28}" y="{y1 + 24}">{letter} · {esc(title)}</text>')


def rows(top, n):
    return [top + 40 + i * PITCH for i in range(n)]


def build():
    # ── A 여행 준비 ─────────────────────────────
    gA = 128
    a = rows(gA, 4)
    group(gA, a[-1] + NH + 18, "A", "여행 준비 — 계획을 받아 일정으로 읽는다")
    node("u01", 1, a[0], "여행 시작하기", "UC-01", "언어 · 설문 6문항")
    node("u03", 1, a[1], "읽힌 일정 확인 · 고치기", "UC-03", "고치기 · 빼기 → 등록")
    node("u02", 1, a[2], "계획 올리기", "UC-02", "글 · 사진 · 파일 5개 · 10MB")
    node("u05", 1, a[3], "여행계획서 보기", "UC-05", "로그인 없는 링크 · 늘 최신")
    node("s", 2, a[1], "여행 등록 · 계획서 링크", "", "등록하면 링크가 바로 생김")
    node("r", 2, a[2], "계획 읽기", "", "매니저의 처리 단계 · 값 + 근거", "core")
    node("u04", 2, a[3], "일정 짜 달라고 하기", "UC-04", "계획이 비었거나 「일정 짜 줘」", "ext")
    node("r3", 3, a[0], "장소 하나로 정하기", "", "표 → 별칭 → 오타 → 외부")
    node("r1", 3, a[1], "정해진 모양 읽기", "", "코드: 시각 · 일차 · 예약번호")
    node("r2", 3, a[2], "원문 위치 가리키기", "", "AI: 남은 줄만 · 없으면 버림")
    node("r0", 3, a[3], "사진 받아쓰기", "", "한 줄씩 · 두 번 대조", "ext")
    actor("trav", LEFT_X, a[0] + 6, LEFT_W, 62, "여행자", "국적 무관 자유여행자", ["person"])
    actor("aiapp", LEFT_X, a[2] - 4, LEFT_W, 62, "개인 AI 비서 앱", "우리 API로 연결", ["bot"])
    actor("comp", LEFT_X, a[3] + 40, LEFT_W, 62, "동행자", "링크로 계획서만 본다", ["person"])
    actor("place", RIGHT_X, a[0], RIGHT_W, NH + 6, "장소 정보", "우리 표 · 카카오 · 관광공사", ["db"])
    actor("ai1", RIGHT_X, a[2] - 6, RIGHT_W, a[3] + NH + 6 - (a[2] - 6), "AI 모델", ["시험 중 — 로컬 · API 비교", "(정하지 않음)"], ["spark"])
    # 연관 — 여행자: u01 · u03 · u02 (통로 x=272)
    tx, ty = R("trav")
    path([(tx, ty), (COL[1], ty)])                                      # u01 (같은 줄)
    path([(272, ty), (272, a[1] + 28), (COL[1], a[1] + 28)])
    path([(272, a[1] + 28), (272, a[2] + 16), (COL[1], a[2] + 16)])
    # 개인 AI 비서 앱: u02 · u05 (통로 x=292)
    ax, ay = R("aiapp")
    path([(ax, a[2] + 34), (COL[1], a[2] + 34)])
    path([(ax, a[2] + 34), (292, a[2] + 34), (292, a[3] + 22), (COL[1], a[3] + 22)])
    # 동행자: u05 (통로 x=312)
    cx_, cy_ = R("comp")
    path([(cx_, cy_), (312, cy_), (312, a[3] + 44), (COL[1], a[3] + 44)])
    # 일반화: 여행자 → 동행자 (왼쪽 바깥)
    path([(LEFT_X, N["trav"][1] + 31), (22, N["trav"][1] + 31), (22, cy_), (LEFT_X - 2, cy_)], "gen")
    # 포함 · 확장
    path([(COL[1] + CW, a[1] + 28), (COL[2], a[1] + 28)], "inc")       # u03 → s
    path([(COL[1] + CW, a[2] + 24), (COL[2], a[2] + 24)], "inc")       # u02 → r
    path([(COL[2], a[3] + 28), (605, a[3] + 28), (605, a[2] + 44), (COL[1] + CW + 2, a[2] + 44)], "ext")   # u04 → u02
    path([(COL[2] + CW, a[2] + 28), (COL[3], a[2] + 28)], "inc")       # r → r2
    path([(905, a[2] + 28), (905, a[1] + 28), (COL[3], a[1] + 28)], "inc")   # r → r1
    path([(905, a[1] + 28), (905, a[0] + 28), (COL[3], a[0] + 28)], "inc")   # r → r3
    path([(COL[3], a[3] + 28), (922, a[3] + 28), (922, a[2] + 46), (COL[2] + CW + 2, a[2] + 46)], "ext")   # r0 → r
    # 시스템 행위자
    path([(COL[3] + CW, a[0] + 28), (RIGHT_X, a[0] + 28)])
    path([(COL[3] + CW, a[2] + 28), (RIGHT_X, a[2] + 28)])
    path([(COL[3] + CW, a[3] + 28), (RIGHT_X, a[3] + 28)])
    yA = a[-1] + NH + 18

    # ── B 여행 중 요청 ─────────────────────────
    gB = yA + 34
    b = rows(gB, 5)
    group(gB, b[-1] + NH + 18, "B", "여행 중 요청 — 읽고, 근거로 답하고, 바꿀 일은 조율로")
    node("u06", 1, b[0], "채팅으로 묻기", "UC-06", "하루 요약 · 다음 이동 · 규정")
    node("u07", 1, b[1], "바꿔 달라고 하기", "UC-07", "바로 바꾸고 다른 안 셋까지")
    node("pB", 1, b[2], "일정 조율 — C 구역", "UC-12", "↓ 반드시 거친다(아래 C)", "proxy")
    node("u08", 1, b[3], "문제 알리기", "UC-08", "늦음 · 휴무")
    node("u09", 1, b[4], "다른 안 고르기 · 되돌리기", "UC-09", "「선택이 필요해요」 · 앞 판")
    node("g", 2, b[0], "근거 찾기", "", "여행 규정 · 예약 취소 조건")
    node("q", 2, b[1], "요청 읽기", "", "요청 종류 · 대상 항목 · 문제 코드", "core")
    node("v", 2, b[4], "새 판 저장", "", "기준 판이 그대로일 때만")
    actor("req", LEFT_X, b[1] + 6, LEFT_W, 80, "여행자 · AI 앱", ["요청하는 쪽", "A의 두 행위자 · 웹 · API"], ["person", "bot"])
    actor("ai2", RIGHT_X, b[0], RIGHT_W, b[1] + NH - b[0], "AI 모델", ["같은 행위자 · 시험 중"], ["spark"])
    rx_, ry_ = R("req")
    for k, dy in (("u06", 28), ("u07", 28), ("u08", 28), ("u09", 28)):
        yy = N[k][1] + dy
        if k == "u07":
            path([(rx_, yy), (COL[1], yy)])
        else:
            path([(rx_, ry_), (282, ry_), (282, yy), (COL[1], yy)])
    path([(COL[1] + CW, b[0] + 28), (COL[2], b[0] + 28)], "inc")       # u06 → g
    path([(COL[1] + CW, b[0] + 44), (600, b[0] + 44), (600, b[1] + 14), (COL[2], b[1] + 14)], "inc")   # u06 → q
    path([(COL[1] + CW, b[1] + 28), (COL[2], b[1] + 28)], "inc")       # u07 → q
    path([(COL[1] + CW, b[3] + 28), (612, b[3] + 28), (612, b[1] + 44), (COL[2], b[1] + 44)], "inc")   # u08 → q
    path([(COL[1] + 125, b[1] + NH), (COL[1] + 125, b[2])], "inc")      # u07 → 일정 조율(참조)
    path([(COL[1] + 125, b[3]), (COL[1] + 125, b[2] + NH)], "inc")      # u08 → 일정 조율(참조)
    path([(COL[1] + CW, b[4] + 28), (COL[2], b[4] + 28)], "inc")       # u09 → v
    path([(COL[2] + CW, b[0] + 28), (RIGHT_X, b[0] + 28)])
    path([(COL[2] + CW, b[1] + 28), (RIGHT_X, b[1] + 28)])
    yB = b[-1] + NH + 18

    # ── C 일정 조율 ─────────────────────────────
    gC = yB + 34
    c = rows(gC, 5)
    group(gC, c[-1] + NH + 18, "C", "일정 조율 — 전부 통과할 때까지 다시 맞춘다", " gold")
    node("c", 1, c[1], "일정 조율", "UC-12", "UC-07 · 08 · 10 · 11 이 부른다", "core")
    node("e3", 1, c[2], "못 맞춤 알리기", "", "후보 소진 · 조건 푼 안 제시", "ext")
    node("a1", 2, c[0], "영향받는 항목 추리기", "", "바로 다음 · 오늘 · 이후 전부")
    node("a2", 2, c[1], "담당 에이전트 점검", "", "액티비티 → 요식 → 이동", "core")
    node("a3", 2, c[2], "적용", "", "근거 대조 → 새 판 1번")
    node("a4", 2, c[3], "변경 알리기", "UC-14", "알림 1번 · 계획서 새 판", "core")
    node("x1", 3, c[0], "액티비티 점검", "", "운영일 · 시간 · 날씨 · 대기질")
    node("x2", 3, c[1], "요식 점검", "", "영업 · 브레이크 · 라스트오더")
    node("x3", 3, c[2], "이동 재판정", "", "시간표로 앞뒤 구간 제시간?")
    node("e1", 3, c[3], "다음 후보로 다시", "", "전부 통과 못 함 · 후보 남음", "ext")
    node("e2", 3, c[4], "바꾸기 전에 묻기", "UC-13", "먼저 물어봐 · 고정 · 안전 경보", "ext")
    actor("info", RIGHT_X, c[0], RIGHT_W, c[2] + NH - c[0], "장소 · 영업 · 교통", ["같은 행위자", "관광공사 · 카카오", "Google · 시간표"], ["db"])
    actor("bell1", LEFT_X, c[4], LEFT_W, 62, "알림 채널", "디스코드 — 팀 시연 채널 하나", ["bell"])
    # c → a1 · a2 · a3 · a4 (통로 x=605)
    path([(COL[1] + CW, c[1] + 28), (COL[2], c[1] + 28)], "inc")
    for row in (c[0], c[2], c[3]):
        path([(605, c[1] + 28), (605, row + 28), (COL[2], row + 28)], "inc")
    path([(COL[1] + 125, c[2]), (COL[1] + 125, c[1] + NH)], "ext")     # e3 → c
    # 일반화: 액티비티 · 요식 · 이동 점검 → 담당 에이전트 점검 (통로 x=912)
    path([(COL[3], c[0] + 28), (912, c[0] + 28), (912, c[1] + 20)])
    path([(COL[3], c[2] + 28), (912, c[2] + 28), (912, c[1] + 20)])
    path([(COL[3], c[1] + 20), (COL[2] + CW + 1, c[1] + 20)], "gen")
    path([(COL[3], c[3] + 28), (898, c[3] + 28), (898, c[1] + 42), (COL[2] + CW + 2, c[1] + 42)], "ext")   # e1 → a2
    path([(COL[3], c[4] + 28), (886, c[4] + 28), (886, c[2] + 40), (COL[2] + CW + 2, c[2] + 40)], "ext")   # e2 → a3
    for row in (c[0], c[1], c[2]):
        path([(COL[3] + CW, row + 28), (RIGHT_X, row + 28)])
    path([(COL[2] + 125, c[3] + NH), (COL[2] + 125, c[4] + 31), (LEFT_X + LEFT_W, c[4] + 31)])   # a4 → 알림 채널
    yC = c[-1] + NH + 18

    # ── D 자동 관리 ─────────────────────────────
    gD = yC + 34
    d = rows(gD, 6)
    group(gD, d[-1] + NH + 18, "D", "자동 관리 — 시계가 깨워 여행 끝까지 돈다", " blue")
    node("u10", 1, d[0], "외부 변화 감시", "UC-10", "3분마다")
    node("pD", 1, d[1], "일정 조율 — C 구역", "UC-12", "↑ 반드시 거친다(위 C)", "proxy")
    node("u11", 1, d[2], "새벽 정기 점검", "UC-11", "03:00~08:00 · 하루 한 번")
    node("u15", 1, d[3], "일정 알림 보내기", "UC-15", "하루 시작 · 다음 일정 · 출발")
    node("u16", 1, d[5], "오류 알림 받기", "UC-16", "상시 작업이 연속 실패할 때")
    node("w1", 2, d[0], "소스 수집", "", "소스마다 한 번 · 값 · 지문")
    node("w2", 2, d[1], "바뀐 값에 걸린 항목", "", "변화 없으면 사건 0 · 알림 0")
    node("o1", 2, d[2], "영업시간 조회", "", "계획한 시각에 여나")
    node("n1", 2, d[3], "출발 시각 계산", "", "다음 시작 − 이동 − 여유")
    node("n2", 2, d[4], "문구틀 번역", "", "언어마다 처음 한 번")
    node("n3", 2, d[5], "알림 배달", "", "3번까지 다시 · 중복 0")
    node("w3", 3, d[0], "대체 소스로 다시 읽기", "", "1차 실패 시 · 대체도 실패면 오류", "ext")
    actor("clock", LEFT_X, d[1] + 10, LEFT_W, 80, "시계", ["3분 · 03:00 · 1분", "알림 보낼 시각"], ["clock"])
    actor("op", LEFT_X, d[5] - 3, LEFT_W, 62, "운영자", "오류 알림만 받는다", ["person"])
    actor("watch", RIGHT_X, d[0] - 20, RIGHT_W, 80, "외부 데이터 6종", ["날씨 · 특보 · 예보", "재난문자 · 교통 2"], ["db"])
    actor("google", RIGHT_X, d[2], RIGHT_W, NH + 6, "장소 · 영업 정보", "같은 행위자 · Google(새벽만)", ["db"])
    actor("ai3", RIGHT_X, d[4], RIGHT_W, NH + 6, "AI 모델", "같은 행위자 · 시험 중", ["spark"])
    actor("bell2", RIGHT_X, d[5] + 4, RIGHT_W, NH + 6, "알림 채널", "같은 행위자 · 디스코드", ["bell"])
    # 시계 → u10 · u11 · u15 · u16 (통로 x=282)
    kx, ky = R("clock")
    for k in ("u10", "u11", "u15", "u16"):
        yy = N[k][1] + 20
        path([(kx, ky), (282, ky), (282, yy), (COL[1], yy)])
    ox, oy = R("op")
    path([(ox, N["u16"][1] + 40), (COL[1], N["u16"][1] + 40)])        # u16 → 운영자
    # 감시 · 점검 → 일정 조율(참조)
    path([(COL[1] + 125, d[0] + NH), (COL[1] + 125, d[1])], "inc")
    path([(COL[1] + 125, d[2]), (COL[1] + 125, d[1] + NH)], "inc")
    # 포함 · 확장
    path([(COL[1] + CW, d[0] + 28), (COL[2], d[0] + 28)], "inc")       # u10 → w1
    path([(COL[1] + CW, d[0] + 44), (605, d[0] + 44), (605, d[1] + 28), (COL[2], d[1] + 28)], "inc")   # u10 → w2
    path([(COL[1] + CW, d[2] + 28), (COL[2], d[2] + 28)], "inc")       # u11 → o1
    path([(COL[1] + CW, d[3] + 28), (COL[2], d[3] + 28)], "inc")       # u15 → n1
    path([(COL[1] + CW, d[3] + 44), (612, d[3] + 44), (612, d[4] + 28), (COL[2], d[4] + 28)], "inc")   # u15 → n2
    path([(612, d[4] + 28), (612, d[5] + 28), (COL[2], d[5] + 28)], "inc")   # u15 → n3
    path([(COL[3], d[0] + 28), (COL[2] + CW + 2, d[0] + 28)], "ext")   # w3 → w1
    # 시스템 행위자
    path([(COL[2] + 125, d[0]), (COL[2] + 125, d[0] - 12), (RIGHT_X, d[0] - 12)])      # w1 → 외부 데이터(위로 돌아)
    path([(COL[3] + CW, d[0] + 28), (RIGHT_X, d[0] + 28)])
    path([(COL[2] + CW, d[2] + 28), (RIGHT_X, d[2] + 28)])
    path([(COL[2] + CW, d[4] + 28), (RIGHT_X, d[4] + 28)])
    path([(COL[2] + CW, d[5] + 28), (RIGHT_X, d[5] + 28 + 4)])
    return d[-1] + NH + 18


def main():
    bottom = build()
    H = bottom + 70
    W = RIGHT_X + RIGHT_W + 30
    head = (f'<text class="svg-label" x="{LEFT_X}" y="40">사람 · 앱</text>'
            f'<text class="svg-label" x="{FRAME_X1 + 10}" y="40">유스케이스 — triPilot</text>'
            f'<text class="svg-label" x="{RIGHT_X}" y="40">시스템 행위자</text>'
            f'<text class="title" x="{LEFT_X}" y="80">triPilot 유스케이스 — 전체 한 장</text>'
            f'<text class="svg-note" x="{LEFT_X}" y="104">v3 · 2026-10-02 · 실제 API · 코드 기준 · 실선 = 연관 · 회색 점선 → = 반드시 쓰는 공통 기능(«include») · '
            f'금색 점선 → = 조건이 맞을 때만(«extend») · 빈 삼각형 = 일반화 · 금색 상자 = 핵심 처리 · 점선 상자 = 다른 구역 참조</text>')
    frame = f'<rect class="sys-frame" x="{FRAME_X1}" y="116" width="{FRAME_X2 - FRAME_X1}" height="{bottom - 116 + 12}" rx="10"/>'
    foot = (f'<text class="svg-note" x="{LEFT_X}" y="{H - 24}">AI 모델 · 장소 정보 · 알림 채널은 같은 행위자를 구역마다 옆에 다시 그렸다. '
            f'고객 건을 사람에게 넘기는 유스케이스는 없다 — 운영자는 오류 알림만 받는다. 「AI 모델」은 아직 정하지 않았다(로컬 · API 시험 중).</text>')
    defs = ('<defs>'
            '<marker id="vee" viewBox="0 0 8 8" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path class="arrow" d="M0 0 L8 4 L0 8 Z"/></marker>'
            '<marker id="vee-gold" viewBox="0 0 8 8" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path class="arrow-gold" d="M0 0 L8 4 L0 8 Z"/></marker>'
            '<marker id="tri" viewBox="0 0 12 12" markerWidth="12" markerHeight="12" refX="11" refY="6" orient="auto"><path class="tri" d="M0 0 L12 6 L0 12 Z"/></marker>'
            '</defs>')
    css = f"""
:root{{--paper:#fbfcfd;--paper-2:#f1f4f8;--card:#ffffff;--ink:#161c28;--muted:#606b7e;--soft:#727d90;--rule-solid:#dbe0ea;
--accent:#a8720c;--accent-tint:rgba(168,114,12,.08);--accent-rule:rgba(168,114,12,.38);--blue-rule:rgba(47,108,154,.30);--blue-tint:rgba(47,108,154,.04)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--paper:#15181d;--paper-2:#20252d;--card:#1a1f26;--ink:#e9edf3;--muted:#b0bac9;--soft:#9aa6b9;
--rule-solid:#39424f;--accent:#e4b45c;--accent-tint:rgba(228,180,92,.09);--accent-rule:rgba(228,180,92,.42)}}}}
body{{margin:0;background:var(--paper);color:var(--ink)}}
.wrap{{max-width:{W}px;margin:0 auto;padding:16px}}
.diagram{{border:1px solid var(--rule-solid);border-radius:6px;background:var(--card);overflow-x:auto}}
.diagram svg{{display:block;width:100%;min-width:1100px;height:auto;color:var(--ink)}}
.diagram .sys-frame{{fill:none;stroke:var(--rule-solid);stroke-width:1.2}}
.diagram .group-frame{{fill:var(--paper-2);stroke:var(--rule-solid)}}
.diagram .group-frame.gold{{fill:var(--accent-tint);stroke:var(--accent-rule)}}
.diagram .group-frame.blue{{fill:var(--blue-tint);stroke:var(--blue-rule)}}
.diagram .node{{fill:var(--card);stroke:var(--rule-solid)}}
.diagram .core-node{{fill:#fbf6ec;stroke:var(--accent-rule)}}
.diagram .ext-node{{fill:var(--card);stroke:var(--accent-rule);stroke-dasharray:5 4}}
.diagram .proxy-node{{fill:var(--paper);stroke:var(--soft);stroke-dasharray:3 3}}
.diagram .edge{{fill:none;stroke:var(--muted);stroke-width:1.15;stroke-linejoin:round}}
.diagram .edge.inc{{stroke-dasharray:5 4}}
.diagram .edge.ext{{stroke:var(--accent);stroke-dasharray:5 4;opacity:.85}}
.diagram .arrow{{fill:var(--muted)}} .diagram .arrow-gold{{fill:var(--accent)}} .diagram .tri{{fill:var(--card);stroke:var(--muted);stroke-width:1.2}}
.diagram .icon{{fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}}
.diagram text{{fill:currentColor;font-family:{SANS};font-size:15px}}
.diagram .title{{font-size:22px;font-weight:700}}
.diagram .svg-label{{fill:var(--soft);font-family:{MONO};font-size:12px;letter-spacing:.08em}}
.diagram .svg-note{{fill:var(--muted);font-size:12px}}
.diagram .svg-letter{{fill:var(--accent);font-family:{MONO};font-size:12px}}
"""
    svg = (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="triPilot 유스케이스 전체 한 장">'
           f'{defs}{head}{frame}{"".join(S)}{foot}</svg>')
    page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>triPilot 유스케이스 한 장 v3</title><style>{css}</style></head><body><div class="wrap"><div class="diagram">{svg}</div></div></body></html>')
    (OUT / "triPilot_유스케이스_한장_v3.html").write_text(page, encoding="utf-8")
    print("ok", W, "x", H)


if __name__ == "__main__":
    main()
