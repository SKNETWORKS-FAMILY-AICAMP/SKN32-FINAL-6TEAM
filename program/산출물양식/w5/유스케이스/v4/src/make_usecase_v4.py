# -*- coding: utf-8 -*-
"""guguroute 유스케이스 v4 — v3(「한눈에」 스타일 배치)에 v2 의 정확한 문구 · UML 관계 표기를 되살리고,
코덱스(gpt-6.1-sol)와 Claude 의 v2 · v3 비교 검토에서 합의한 고칠 점을 반영한다(2026-10-02).

    python make_usecase_v4.py   → ../triPilot_유스케이스_한장_v4.html · .svg · uc_v4_A~D.html · .svg

v3 → v4 에서 바뀐 것
  관계  · 「반드시」가 아닌 것은 «extend» 로: UC-12 → UC-10 · UC-11(깨졌을 때만) · 원문 위치 가리키기 → 계획 읽기(규칙이 못 읽은 줄만)
          · 근거 찾기 → UC-06(규정 · 예약 조건을 물을 때) · 문구틀 번역 → UC-15(그 언어로 처음 보낼 때)
        · UC-13 은 UC-12 를 확장(확장점: 변경 저장 직전) — v3 는 「적용」에 걸었다. 조건에 설문 무응답 추가
        · UC-13 · UC-14 ↔ 여행자 연관 추가 · 요청하는 쪽 ← 여행자 · AI 비서 앱 일반화 복원
        · 일반화 빈 삼각형을 관계마다 따로 · 모든 «include» · «extend» 선에 이름표 · 열린 화살촉
  모양  · 사용자에게 보이는 유스케이스(UC 번호) = 알약(타원 대신), 그 안의 처리 단계 = 모서리 상자
        · 회색 점선 상자 = UC-12 의 반복 표현(별도 기능 아님) · 금색 점선 상자 = 조건이 맞을 때만 끼어드는 기능
  문구  · v2 문구 복원(항목 · 날짜마다 한 번 · 기준 판 · 항목 · 장소 대조 · 값은 원값 · 요청 종류 5 · Places · 「만들기」 · 「고르기」)
        · UC-16 = 오류 알림 받기 · 운영 화면 보기(읽기 전용) · 시스템 행위자 이름 통일
"""
import html
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
SANS = "'Noto Sans KR','Malgun Gothic',sans-serif"
MONO = "'NanumGothicCoding','Consolas',monospace"

COL = {1: 330, 2: 630, 3: 940}
CW, NH, PITCH = 250, 68, 86
LEFT_X, LEFT_W = 40, 210
RIGHT_X, RIGHT_W = 1262, 236
FRAME_X1, FRAME_X2 = 300, 1212
S, N = [], {}


def esc(t):
    return html.escape(t, quote=False)


def node(key, col, y, title, code="", notes=(), kind=""):
    """kind: uc(사용자 기능 · 알약) · ucore(핵심 UC · 금색 알약) · step(처리 단계) · core(핵심 처리 단계) · ext(조건부 단계) · uext(조건부 UC) · proxy"""
    x = COL[col]
    N[key] = (x, y, CW, NH)
    cls, rx = {"uc": ("node", NH / 2), "ucore": ("core-node", NH / 2), "uext": ("ext-node", NH / 2), "step": ("step-node", 6),
               "core": ("core-node", 6), "ext": ("ext-node", 6), "proxy": ("proxy-node", NH / 2)}[kind]
    S.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{CW}" height="{NH}" rx="{rx}"/>')
    pad = 24 if rx > 6 else 16
    tx = x + pad
    if code:
        S.append(f'<text class="svg-letter" x="{tx}" y="{y + 25}">{code}</text>')
        tx += 46
    S.append(f'<text x="{tx}" y="{y + 25}">{esc(title)}</text>')
    for i, n in enumerate([notes] if isinstance(notes, str) else notes):
        S.append(f'<text class="svg-note" x="{x + pad}" y="{y + 45 + i * 16}">{esc(n)}</text>')


def actor(key, x, y, w, h, title, notes, icons):
    N[key] = (x, y, w, h)
    S.append(f'<rect class="node" x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>')
    ix = x + 14
    for ic in icons:
        S.append(ICON[ic](ix, y + 14))
        ix += 30
    S.append(f'<text x="{ix + 6}" y="{y + 26}">{esc(title)}</text>')
    for i, ln in enumerate([notes] if isinstance(notes, str) else notes):
        S.append(f'<text class="svg-note" x="{ix + 6}" y="{y + 46 + i * 17}">{esc(ln)}</text>')


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


def path(pts, kind="assoc", lab=None):
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    cls, mk = {"assoc": ("edge", ""), "inc": ("edge inc", ' marker-end="url(#vee)"'),
               "ext": ("edge ext", ' marker-end="url(#vee-gold)"'), "gen": ("edge", ' marker-end="url(#tri)"')}[kind]
    S.append(f'<path class="{cls}" d="{d}"{mk}/>')
    if kind in ("inc", "ext"):
        name = lab or ("include" if kind == "inc" else "extend")
        # 가장 긴 가로 구간 위에 이름표, 없으면 세로 구간 옆
        best, horiz = None, True
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if y1 == y2 and (best is None or abs(x2 - x1) > best[0]):
                best = (abs(x2 - x1), (x1 + x2) / 2, y1)
        if best is None or best[0] < 44:
            horiz = False
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                if x1 == x2 and (best is None or not horiz and abs(y2 - y1) > best[0]):
                    best = (abs(y2 - y1), x1, (y1 + y2) / 2)
        cls2 = "rel" if kind == "inc" else "rel gold"
        if horiz:
            S.append(f'<text class="{cls2}" x="{best[1]}" y="{best[2] - 4}" text-anchor="middle">{name}</text>')
        elif best[0] >= 60:   # 긴 세로 구간 — 통로 안에 세로로 눕혀 노드 글자와 겹치지 않게
            S.append(f'<text class="{cls2}" x="{best[1] - 4}" y="{best[2]}" text-anchor="middle" transform="rotate(-90 {best[1] - 4} {best[2]})">{name}</text>')
        else:
            S.append(f'<text class="{cls2}" x="{best[1] + 5}" y="{best[2] + 3}">{name}</text>')


def RX(k):
    x, y, w, h = N[k]
    return x + w


def group(y1, y2, letter, title, tone=""):
    S.append(f'<rect class="group-frame{tone}" x="{FRAME_X1 + 10}" y="{y1}" width="{FRAME_X2 - FRAME_X1 - 20}" height="{y2 - y1}" rx="8"/>')
    S.append(f'<text class="svg-label" x="{FRAME_X1 + 28}" y="{y1 + 24}">{letter} · {esc(title)}</text>')


def rows(top, n):
    return [top + 40 + i * PITCH for i in range(n)]


E1, E2, E3 = COL[1] + CW, COL[2] + CW, COL[3] + CW     # 각 칸 오른쪽 끝
MID1, MID2 = COL[1] + CW / 2, COL[2] + CW / 2


def build(which="ABCD"):
    y_end = 94
    # ── A 여행 준비 ─────────────────────────────
    if "A" in which:
        g = y_end + 34
        a = rows(g, 4)
        group(g, a[-1] + NH + 18, "A", "여행 준비 — 계획을 받아 일정으로 읽는다")
        node("u01", 1, a[0], "여행 시작하기", "UC-01", "언어 · 설문 6문항", "uc")
        node("u03", 1, a[1], "읽힌 일정 확인 · 고치기", "UC-03", "고치기 · 빼기 → 등록", "uc")
        node("u02", 1, a[2], "계획 올리기", "UC-02", "글 · 사진 · 파일 5개 · 10MB", "uc")
        node("u05", 1, a[3], "여행계획서 보기", "UC-05", "로그인 없는 링크 · 늘 최신", "uc")
        node("s", 2, a[1], "여행 등록 · 계획서 링크 만들기", "", "등록하면 링크가 바로 생김", "step")
        node("r", 2, a[2], "계획 읽기", "", ["매니저(코어)의 처리 단계", "항목마다 값 · 방법 · 근거(원문 줄)"], "core")
        node("u04", 2, a[3], "일정 짜 달라고 하기", "UC-04", "계획이 비었거나 「일정 짜 줘」", "uext")
        node("r3", 3, a[0], "장소 하나로 정하기", "", "표 → 별칭 → 오타 → 카카오 · 관광공사", "step")
        node("r1", 3, a[1], "정해진 모양 읽기", "", "코드: 시각 · 일차 · 날짜 · 예약번호", "step")
        node("r2", 3, a[2], "원문 위치 가리키기", "", ["AI: 규칙이 못 읽은 줄만", "원문에 없는 인용은 버림"], "ext")
        node("r0", 3, a[3], "사진 받아쓰기", "", ["사진일 때만 · 한 줄씩", "두 번 대조해 빠진 줄 확인"], "ext")
        actor("trav", LEFT_X, a[0] + 4, LEFT_W, 62, "여행자", "국적 무관 자유여행자", ["person"])
        actor("aiapp", LEFT_X, a[2] - 4, LEFT_W, 62, "개인 AI 비서 앱", "우리 API로 연결", ["bot"])
        actor("comp", LEFT_X, a[3] + 44, LEFT_W, 62, "동행자", "링크로 계획서만 본다", ["person"])
        actor("place", RIGHT_X, a[0] - 4, RIGHT_W, 78, "장소 · 영업 · 교통 정보", ["여기서는: 우리 표 · 카카오", "관광공사 · Places"], ["db"])
        actor("ai1", RIGHT_X, a[2] - 4, RIGHT_W, a[3] + NH + 4 - (a[2] - 4), "AI 모델", ["시험 중 — 로컬 · API 비교", "(아직 정하지 않음)"], ["spark"])
        ty = N["trav"][1] + 31
        path([(LEFT_X + LEFT_W, ty), (COL[1], ty)])
        path([(272, ty), (272, a[1] + 34), (COL[1], a[1] + 34)])
        path([(272, a[1] + 34), (272, a[2] + 18), (COL[1], a[2] + 18)])
        ay = a[2] + 40
        path([(LEFT_X + LEFT_W, ay), (COL[1], ay)])
        path([(292, ay), (292, a[3] + 24), (COL[1], a[3] + 24)])
        cy = N["comp"][1] + 31
        path([(LEFT_X + LEFT_W, cy), (312, cy), (312, a[3] + 50), (COL[1], a[3] + 50)])
        path([(LEFT_X, ty), (22, ty), (22, cy), (LEFT_X - 1, cy)], "gen")
        path([(E1, a[1] + 34), (COL[2], a[1] + 34)], "inc")                                   # UC-03 → 등록
        path([(E1, a[2] + 26), (COL[2], a[2] + 26)], "inc")                                   # UC-02 → 계획 읽기
        path([(COL[2], a[3] + 34), (605, a[3] + 34), (605, a[2] + 52), (E1 + 1, a[2] + 52)], "ext")   # UC-04 → UC-02
        path([(E2, a[2] + 14), (905, a[2] + 14), (905, a[1] + 34), (COL[3], a[1] + 34)], "inc")   # 계획 읽기 → 정해진 모양
        path([(905, a[1] + 34), (905, a[0] + 34), (COL[3], a[0] + 34)], "inc")                # 계획 읽기 → 장소 하나로
        path([(COL[3], a[2] + 34), (E2 + 1, a[2] + 34)], "ext")                               # 원문 위치 → 계획 읽기
        path([(COL[3], a[3] + 34), (922, a[3] + 34), (922, a[2] + 56), (E2 + 1, a[2] + 56)], "ext")   # 사진 받아쓰기 → 계획 읽기
        path([(E3, a[0] + 34), (RIGHT_X, a[0] + 34)])
        path([(E3, a[2] + 34), (RIGHT_X, a[2] + 34)])
        path([(E3, a[3] + 34), (RIGHT_X, a[3] + 34)])
        y_end = a[-1] + NH + 18
    # ── B 여행 중 요청 ─────────────────────────
    if "B" in which:
        g = y_end + 34
        b = rows(g, 5)
        group(g, b[-1] + NH + 18, "B", "여행 중 요청 — 읽고, 근거로 답하고, 바꿀 일은 조율로")
        node("u06", 1, b[0], "채팅으로 묻기", "UC-06", "하루 요약 · 다음 이동 · 규정", "uc")
        node("u07", 1, b[1], "바꿔 달라고 하기", "UC-07", "바로 바꾸고 다른 안 셋까지", "uc")
        node("pB", 1, b[2], "일정 조율 (반복 표현)", "UC-12", "↓ 아래 C 구역의 UC-12", "proxy")
        node("u08", 1, b[3], "문제 알리기", "UC-08", "늦음 · 휴무", "uc")
        node("u09", 1, b[4], "다른 안 고르기 · 되돌리기", "UC-09", "「선택이 필요해요」 · 앞 판으로", "uc")
        node("g", 2, b[0], "근거 찾기", "", ["규정 · 예약 조건을 물을 때만", "여행 규정 · 예약 취소 조건"], "ext")
        node("q", 2, b[1], "요청 읽기", "", ["요청 종류 5 · 대상 항목", "문제 코드"], "core")
        node("v", 2, b[4], "새 판 저장", "", "기준 판이 그대로일 때만", "step")
        actor("tv2", LEFT_X, b[0], 100, 54, "여행자", [], ["person"])
        actor("ap2", LEFT_X + 110, b[0], 100, 54, "AI 앱", [], ["bot"])
        actor("req", LEFT_X, b[2] - 10, LEFT_W, 80, "요청하는 쪽", ["여행자 · AI 비서 앱의", "공통 역할(같은 행위자)"], ["person"])
        actor("ai2", RIGHT_X, b[0], RIGHT_W, b[1] + NH - b[0], "AI 모델", ["같은 행위자 · 시험 중"], ["spark"])
        path([(LEFT_X + 50, b[0] + 54), (LEFT_X + 50, N["req"][1] - 1)], "gen")
        path([(LEFT_X + 160, b[0] + 54), (LEFT_X + 160, N["req"][1] - 1)], "gen")
        ry = N["req"][1] + 40
        for k in ("u06", "u07", "u08", "u09"):
            yy = N[k][1] + 34
            path([(LEFT_X + LEFT_W, ry), (282, ry), (282, yy), (COL[1], yy)])
        path([(COL[2], b[0] + 22), (E1 + 1, b[0] + 22)], "ext")                               # 근거 찾기 → UC-06
        path([(E1, b[0] + 52), (600, b[0] + 52), (600, b[1] + 16), (COL[2], b[1] + 16)], "inc")   # UC-06 → 요청 읽기
        path([(E1, b[1] + 34), (COL[2], b[1] + 34)], "inc")                                   # UC-07 → 요청 읽기
        path([(E1, b[3] + 34), (612, b[3] + 34), (612, b[1] + 52), (COL[2], b[1] + 52)], "inc")   # UC-08 → 요청 읽기
        path([(MID1, b[1] + NH), (MID1, b[2])], "inc")                                        # UC-07 → UC-12
        path([(MID1, b[3]), (MID1, b[2] + NH)], "inc")                                        # UC-08 → UC-12
        path([(E1, b[4] + 34), (COL[2], b[4] + 34)], "inc")                                   # UC-09 → 새 판 저장
        path([(E2, b[0] + 34), (RIGHT_X, b[0] + 34)])
        path([(E2, b[1] + 34), (RIGHT_X, b[1] + 34)])
        y_end = b[-1] + NH + 18
    # ── C 일정 조율 ─────────────────────────────
    if "C" in which:
        g = y_end + 34
        c = rows(g, 4)
        group(g, c[-1] + NH + 18, "C", "일정 조율 — 전부 통과할 때까지 다시 맞춘다", " gold")
        node("e3", 1, c[0], "못 맞춤 알리기", "", ["후보가 다 떨어졌을 때", "이유와 조건 푼 안 제시"], "ext")
        node("c", 1, c[1], "일정 조율", "UC-12", ["07 · 08 은 반드시 부른다", "10 · 11 엔 깨졌을 때만 끼어든다"], "ucore")
        node("e2", 1, c[2], "바꾸기 전에 묻기", "UC-13", ["확장점: 변경 저장 직전", "먼저 물어봐 · 무응답 · 고정 · 안전 경보"], "uext")
        node("a1", 2, c[0], "영향받는 항목 추리기", "", "바로 다음 · 오늘 · 이후 전부", "step")
        node("a2", 2, c[1], "담당 에이전트 점검", "", ["액티비티 → 요식 → 이동", "앞 에이전트의 초안을 넘김"], "core")
        node("a3", 2, c[2], "적용", "", ["근거 대조(기준 판 · 항목 · 장소)", "→ 새 판 1번"], "step")
        node("a4", 2, c[3], "변경 알리기", "UC-14", "알림 1번 · 계획서 새 판", "ucore")
        node("x1", 3, c[0], "액티비티 점검", "", "운영일 · 시간 · 날씨 · 대기질", "step")
        node("x2", 3, c[1], "요식 점검", "", "영업 · 브레이크 · 라스트오더", "step")
        node("x3", 3, c[2], "이동 재판정", "", "시간표로 앞뒤 구간 제시간?", "step")
        node("e1", 3, c[3], "다음 후보로 다시", "", ["전부 통과 못 함 · 후보 남음", "→ 점검부터 다시(반복)"], "ext")
        actor("info", RIGHT_X, c[0], RIGHT_W, c[2] + NH - c[0], "장소 · 영업 · 교통 정보", ["같은 행위자", "여기서는: 관광공사 · 카카오", "Google · 지하철 · 버스 시간표"], ["db"])
        actor("tv3", LEFT_X, c[2], LEFT_W, 62, "여행자", "같은 행위자 · 묻고 알림 받음", ["person"])
        actor("bell1", LEFT_X, c[3] + 8, LEFT_W, 62, "알림 채널", "디스코드 — 팀 시연 채널 하나", ["bell"])
        path([(MID1, c[0] + NH), (MID1, c[1])], "ext")                                        # 못 맞춤 → UC-12
        path([(MID1, c[2]), (MID1, c[1] + NH)], "ext")                                        # UC-13 → UC-12
        path([(E1, c[1] + 34), (COL[2], c[1] + 34)], "inc")                                   # UC-12 → 점검
        for row in (c[0], c[2], c[3]):
            path([(605, c[1] + 34), (605, row + 34), (COL[2], row + 34)], "inc")
        # 일반화(관계마다 삼각형 하나) — 액티비티 · 요식 · 이동 점검 → 담당 에이전트 점검
        path([(COL[3], c[0] + 34), (912, c[0] + 34), (912, c[1] + 12), (E2 + 1, c[1] + 12)], "gen")
        path([(COL[3], c[1] + 30), (E2 + 1, c[1] + 30)], "gen")
        path([(COL[3], c[2] + 34), (912, c[2] + 34), (912, c[1] + 48), (E2 + 1, c[1] + 48)], "gen")
        path([(COL[3], c[3] + 34), (897, c[3] + 34), (897, c[1] + 62), (E2 + 1, c[1] + 62)], "ext")   # 다음 후보로 다시 → 점검
        for row in (c[0], c[1], c[2]):
            path([(E3, row + 34), (RIGHT_X, row + 34)])
        path([(COL[1], c[2] + 34), (LEFT_X + LEFT_W, c[2] + 34)])                              # UC-13 — 여행자
        path([(COL[2], c[3] + 48), (270, c[3] + 48), (270, c[2] + 62), (LEFT_X + LEFT_W, c[2] + 62)])   # UC-14 — 여행자
        path([(COL[2], c[3] + 60), (LEFT_X + LEFT_W, c[3] + 60)])                              # UC-14 — 알림 채널
        y_end = c[-1] + NH + 18
    # ── D 자동 관리 ─────────────────────────────
    if "D" in which:
        g = y_end + 34
        d = rows(g, 6)
        group(g, d[-1] + NH + 18, "D", "자동 관리 — 시계가 깨워 여행 끝까지 돈다", " blue")
        node("u10", 1, d[0], "외부 변화 감시", "UC-10", "3분마다", "uc")
        node("pD", 1, d[1], "일정 조율 (반복 표현)", "UC-12", "깨졌을 때만 끼어든다 · 위 C", "proxy")
        node("u11", 1, d[2], "새벽 정기 점검", "UC-11", "03:00~08:00 · 항목 · 날짜마다 한 번", "uc")
        node("u15", 1, d[3], "일정 알림 보내기", "UC-15", "하루 시작 · 다음 일정 · 출발", "uc")
        node("u16", 1, d[5], "오류 알림 · 운영 화면 보기", "UC-16", "상시 작업 연속 실패 · 화면은 읽기 전용", "uc")
        node("w1", 2, d[0], "소스 수집", "", "소스마다 한 번 · 값 · 지문", "step")
        node("w2", 2, d[1], "바뀐 값에 걸린 항목 고르기", "", "변화 없으면 사건 0 · 알림 0", "step")
        node("o1", 2, d[2], "영업시간 조회", "", "계획한 시각에 여나", "step")
        node("n1", 2, d[3], "출발 시각 계산", "", "다음 시작 − 이동 − 여유", "step")
        node("n2", 2, d[4], "문구틀 번역", "", ["그 언어로 처음 보낼 때만", "값(시각 · 이름 · 금액)은 원값"], "ext")
        node("n3", 2, d[5], "알림 배달", "", "3번까지 다시 · 중복 0", "step")
        node("w3", 3, d[0], "대체 소스로 다시 읽기", "", ["1차 실패 시", "대체도 실패면 오류로 기록"], "ext")
        actor("clock", LEFT_X, d[1] + 14, LEFT_W, 80, "시계", ["3분 · 03:00 · 1분", "알림 보낼 시각"], ["clock"])
        actor("op", LEFT_X, d[5] + 2, LEFT_W, 62, "운영자", "오류 알림만 · 고객 건 없음", ["person"])
        actor("watch", RIGHT_X, d[0] - 22, RIGHT_W, 84, "외부 데이터 6종", ["날씨 · 기상 특보 · 단기예보", "재난문자 · 교통 사건 2"], ["db"])
        actor("google", RIGHT_X, d[2], RIGHT_W, NH, "장소 · 영업 · 교통 정보", "같은 행위자 · 여기서는 Google(새벽만)", ["db"])
        actor("ai3", RIGHT_X, d[4], RIGHT_W, NH, "AI 모델", "같은 행위자 · 시험 중", ["spark"])
        actor("bell2", RIGHT_X, d[5] + 2, RIGHT_W, NH, "알림 채널", "같은 행위자 · 디스코드", ["bell"])
        ky = N["clock"][1] + 40
        for k in ("u10", "u11", "u15", "u16"):
            yy = N[k][1] + 22
            path([(LEFT_X + LEFT_W, ky), (282, ky), (282, yy), (COL[1], yy)])
        path([(LEFT_X + LEFT_W, N["op"][1] + 40), (COL[1], N["op"][1] + 40)])
        path([(MID1, d[1]), (MID1, d[0] + NH + 1)], "ext")                                     # UC-12 → UC-10
        path([(MID1, d[1] + NH), (MID1, d[2] - 1)], "ext")                                     # UC-12 → UC-11
        path([(E1, d[0] + 34), (COL[2], d[0] + 34)], "inc")                                   # UC-10 → 소스 수집
        path([(E1, d[0] + 54), (605, d[0] + 54), (605, d[1] + 34), (COL[2], d[1] + 34)], "inc")   # UC-10 → 고르기
        path([(E1, d[2] + 34), (COL[2], d[2] + 34)], "inc")                                   # UC-11 → 영업시간 조회
        path([(E1, d[3] + 26), (COL[2], d[3] + 26)], "inc")                                   # UC-15 → 출발 시각
        path([(E1, d[3] + 58), (605, d[3] + 58), (605, d[5] + 34), (COL[2], d[5] + 34)], "inc")   # UC-15 → 배달
        path([(COL[2], d[4] + 34), (618, d[4] + 34), (618, d[3] + 44), (E1 + 1, d[3] + 44)], "ext")   # 번역 → UC-15
        path([(COL[3], d[0] + 34), (E2 + 1, d[0] + 34)], "ext")                               # 대체 소스 → 소스 수집
        path([(MID2, d[0]), (MID2, d[0] - 14), (RIGHT_X, d[0] - 14)])                          # 소스 수집 — 외부 데이터
        path([(E3, d[0] + 34), (RIGHT_X, d[0] + 34)])
        path([(E2, d[2] + 34), (RIGHT_X, d[2] + 34)])
        path([(E2, d[4] + 34), (RIGHT_X, d[4] + 34)])
        path([(E2, d[5] + 36), (RIGHT_X, d[5] + 36)])
        y_end = d[-1] + NH + 18
    return y_end


CSS = f"""
:root{{--paper:#fbfcfd;--paper-2:#f1f4f8;--card:#ffffff;--ink:#161c28;--muted:#606b7e;--soft:#727d90;--rule-solid:#dbe0ea;
--accent:#a8720c;--accent-tint:rgba(168,114,12,.08);--accent-rule:rgba(168,114,12,.38);--core-fill:#fbf6ec;--blue-rule:rgba(47,108,154,.30);--blue-tint:rgba(47,108,154,.04)}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--paper:#15181d;--paper-2:#20252d;--card:#1a1f26;--ink:#e9edf3;--muted:#b0bac9;--soft:#9aa6b9;
--rule-solid:#39424f;--accent:#e4b45c;--accent-tint:rgba(228,180,92,.09);--accent-rule:rgba(228,180,92,.42);--core-fill:#2a2418}}}}
.diagram{{border:1px solid var(--rule-solid);border-radius:6px;background:var(--card);overflow-x:auto}}
.diagram svg{{display:block;width:100%;min-width:1100px;height:auto;color:var(--ink)}}
.diagram .sys-frame{{fill:none;stroke:var(--rule-solid);stroke-width:1.2}}
.diagram .group-frame{{fill:var(--paper-2);stroke:var(--rule-solid)}}
.diagram .group-frame.gold{{fill:var(--accent-tint);stroke:var(--accent-rule)}}
.diagram .group-frame.blue{{fill:var(--blue-tint);stroke:var(--blue-rule)}}
.diagram .node{{fill:var(--card);stroke:var(--rule-solid)}}
.diagram .step-node{{fill:var(--paper);stroke:var(--rule-solid)}}
.diagram .core-node{{fill:var(--core-fill);stroke:var(--accent-rule)}}
.diagram .ext-node{{fill:var(--card);stroke:var(--accent-rule);stroke-dasharray:5 4}}
.diagram .proxy-node{{fill:var(--paper);stroke:var(--soft);stroke-dasharray:3 3}}
.diagram .edge{{fill:none;stroke:var(--muted);stroke-width:1.15;stroke-linejoin:round}}
.diagram .edge.inc{{stroke-dasharray:5 4}}
.diagram .edge.ext{{stroke:var(--accent);stroke-dasharray:5 4}}
.diagram .vee{{fill:none;stroke:var(--muted);stroke-width:1.3}} .diagram .vee-gold{{fill:none;stroke:var(--accent);stroke-width:1.3}}
.diagram .tri{{fill:var(--card);stroke:var(--muted);stroke-width:1.2}}
.diagram .icon{{fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}}
.diagram text{{fill:currentColor;font-family:{SANS};font-size:15px}}
.diagram .title{{font-size:22px;font-weight:700}}
.diagram .svg-label{{fill:var(--soft);font-family:{MONO};font-size:12px;letter-spacing:.08em}}
.diagram .svg-note{{fill:var(--muted);font-size:12px}}
.diagram .svg-letter{{fill:var(--accent);font-family:{MONO};font-size:12px}}
.diagram .rel{{fill:var(--soft);font-family:{MONO};font-size:10px}} .diagram .rel.gold{{fill:var(--accent)}}
"""


def render(which="ABCD", out="triPilot_유스케이스_한장_v4", title="guguroute 유스케이스 — 전체 한 장"):
    S.clear(); N.clear()
    bottom = build(which)
    H, W = bottom + 74, RIGHT_X + RIGHT_W + 30
    head = (f'<text class="svg-label" x="{LEFT_X}" y="40">사람 · 앱</text>'
            f'<text class="svg-label" x="{FRAME_X1 + 10}" y="40">유스케이스 — guguroute</text>'
            f'<text class="svg-label" x="{RIGHT_X}" y="40">시스템 행위자</text>'
            f'<text class="title" x="{LEFT_X}" y="80">{esc(title)}</text>'
            f'<text class="svg-note" x="{LEFT_X}" y="104">v4 · 2026-10-02 · 실제 API · 코드 기준 · 알약 = 사용자에게 보이는 유스케이스(UC 번호) · 모서리 상자 = 그 안의 처리 단계 · '
            f'금색 = 핵심 · 금색 점선 상자 = 조건이 맞을 때만 · 회색 점선 알약 = 다른 구역 UC-12 의 반복 표현</text>')
    frame = f'<rect class="sys-frame" x="{FRAME_X1}" y="116" width="{FRAME_X2 - FRAME_X1}" height="{bottom - 116 + 12}" rx="10"/>'
    foot = (f'<text class="svg-note" x="{LEFT_X}" y="{H - 40}">선: 실선 = 연관 · 회색 점선 «include» = 반드시 쓰는 기능(기본 → 공통) · 금색 점선 «extend» = 조건이 맞을 때만(추가 → 기본) · 빈 삼각형 = 일반화</text>'
            f'<text class="svg-note" x="{LEFT_X}" y="{H - 20}">AI 모델 · 장소 · 영업 · 교통 정보 · 알림 채널 · 여행자는 같은 행위자를 구역마다 다시 그렸다. 고객 건을 사람에게 넘기는 유스케이스는 없다 — 운영자는 오류 알림만 받는다.</text>')
    defs = ('<defs>'
            '<marker id="vee" viewBox="0 0 10 10" markerWidth="9" markerHeight="9" refX="9" refY="5" orient="auto"><path class="vee" d="M1 1 L9 5 L1 9"/></marker>'
            '<marker id="vee-gold" viewBox="0 0 10 10" markerWidth="9" markerHeight="9" refX="9" refY="5" orient="auto"><path class="vee-gold" d="M1 1 L9 5 L1 9"/></marker>'
            '<marker id="tri" viewBox="0 0 14 14" markerWidth="13" markerHeight="13" refX="13" refY="7" orient="auto"><path class="tri" d="M1 1 L13 7 L1 13 Z"/></marker>'
            '</defs>')
    svg = (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(title)}">'
           f'{defs}{head}{frame}{"".join(S)}{foot}</svg>')
    page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)} v4</title><style>body{{margin:0;background:var(--paper);color:var(--ink)}}.wrap{{max-width:{W}px;margin:0 auto;padding:16px}}{CSS}</style>'
            f'</head><body><div class="wrap"><div class="diagram">{svg}</div></div></body></html>')
    (OUT / f"{out}.html").write_text(page, encoding="utf-8")
    print("ok", out, W, "x", H)


FIGS = [("ABCD", "triPilot_유스케이스_한장_v4", "guguroute 유스케이스 — 전체 한 장"),
        ("A", "uc_v4_A", "A · 여행 준비 — 계획을 받아 일정으로 읽는다"),
        ("B", "uc_v4_B", "B · 여행 중 요청 — 읽고, 근거로 답하고, 바꿀 일은 조율로"),
        ("C", "uc_v4_C", "C · 일정 조율 — 전부 통과할 때까지 다시 맞춘다"),
        ("D", "uc_v4_D", "D · 자동 관리 — 시계가 깨워 여행 끝까지 돈다")]

if __name__ == "__main__":
    for w_, o_, t_ in FIGS:
        render(w_, o_, t_)
