# -*- coding: utf-8 -*-
"""guguroute 유스케이스 다이어그램 v7 — v5 를 코덱스 · Claude 검토(2026-10-03)로 고친 판. 규칙은 멘토링 자료 「유스케이스 & 멀티 에이전트 다이어그램」.

v5 → v6: UC-07 은 UC-10 을 «include» 가 아니라 UC-10 이 «extend»(품절 · 늦어도 되는 신고는 안 바꾼다) ·
  UC-11 을 UC-10 아래로 · 부모 액터(요청자 · 동행자)를 자식 액터(여행자 · AI 앱) 위로(Ambler) ·
  UC-14 「내 설정을 관리한다」 추가(연락처 · 취향 · 키) · 「일정 짜 줘」(UC-03)는 v5 그대로(UC-02 확장).

    python make_usecase_v7.py   → ../triPilot_유스케이스_다이어그램_v7.html · .svg

자료의 그리기 규칙
  · 주 액터는 왼쪽, 보조 액터(외부 시스템)는 오른쪽 · «actor» · «external» 표시
  · 맥락 수준 그림에는 사용자 목표 수준 유스케이스만 넣는다 — v4 의 처리 단계(계획 읽기 · 요청 읽기 · 점검 …)는 명세 시나리오로 옮겼다
  · 유스케이스는 타원 + 「동사 + 목적어」, 이름은 액터의 목표로
  · «include» = 기본 → 포함(반드시 · 여러 곳이 공통으로), «extend» = 확장 → 기본(조건부), 확장점 · 조건은 노트로
  · 정해진 시각에 시작하는 유스케이스는 「시간」 액터로 시작시킨다
선이 한 번 건너뛰는 곳(외부 정보 서비스 앞)이 있다 — 액터를 한 번씩만 그리면서 피할 배치를 찾지 못했다. 이어진 선이 아니다.
"""
import html
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
SANS = "'Noto Sans KR','Malgun Gothic',sans-serif"
MONO = "'NanumGothicCoding','Consolas',monospace"

C1, C2, C3 = 330, 650, 960          # 칸 왼쪽 끝
CW, NH, PITCH, TOP = 270, 72, 96, 170
RX, RY = CW / 2, NH / 2
LEFT_X, LEFT_W = 40, 200
TRUNK = 285                          # 요청자 줄기
FRAME_X1, FRAME_X2 = 300, 1240
ROUTE = 1250                         # 프레임 밖 · 보조 액터 앞 통로
RIGHT_X, RIGHT_W = 1272, 236
S, U = [], {}


def esc(t):
    return html.escape(t, quote=False)


def ry(r):
    return TOP + r * PITCH


def uc(key, col, r, code, name, kind=""):
    x, y = {1: C1, 2: C2, 3: C3}[col], ry(r)
    cx, cy = x + RX, y + RY
    U[key] = (cx, cy)
    cls = "core-node" if kind == "core" else "node"
    S.append(f'<ellipse class="{cls}" cx="{cx}" cy="{cy}" rx="{RX}" ry="{RY}"/>')
    S.append(f'<text class="svg-letter" x="{cx}" y="{cy - 8}" text-anchor="middle">{esc(code)}</text>')
    S.append(f'<text x="{cx}" y="{cy + 15}" text-anchor="middle">{esc(name)}</text>')


def ex(key, y, side):
    """타원 경계에서 높이 y 의 x."""
    cx, cy = U[key]
    d = min(abs(y - cy) / RY, 0.999)
    return cx + side * RX * math.sqrt(1 - d * d)


def top(key):
    cx, cy = U[key]
    return cx, cy - RY


def bot(key):
    cx, cy = U[key]
    return cx, cy + RY


def actor(x, y, w, h, stereo, title, notes, icon, italic=False):
    S.append(f'<rect class="node" x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>')
    S.append(ICON[icon](x + 14, y + 16))
    tx = x + 50
    S.append(f'<text class="svg-label" x="{tx}" y="{y + 18}">{esc(stereo)}</text>')
    st = ' font-style="italic"' if italic else ""
    S.append(f'<text x="{tx}" y="{y + 38}"{st}>{esc(title)}</text>')
    for i, n in enumerate(notes):
        S.append(f'<text class="svg-note" x="{tx}" y="{y + 56 + i * 16}">{esc(n)}</text>')


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


def line(pts, kind="assoc", hop_x=None):
    """kind: assoc(실선) · inc · ext(점선 + 열린 화살촉) · gen(빈 삼각형). hop_x: 가로 구간이 그 x 에서 건너뛴다."""
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if hop_x is not None and y1 == y2 and min(x1, x2) < hop_x < max(x1, x2):
            s = 1 if x2 > x1 else -1
            d += f" L{hop_x - 6 * s:.1f} {y1:.1f} A6 6 0 0 {1 if s > 0 else 0} {hop_x + 6 * s:.1f} {y1:.1f}"
        d += f" L{x2:.1f} {y2:.1f}"
    cls, mk = {"assoc": ("edge", ""), "inc": ("edge inc", ' marker-end="url(#vee)"'),
               "ext": ("edge ext", ' marker-end="url(#vee-gold)"'), "gen": ("edge", ' marker-end="url(#tri)"')}[kind]
    S.append(f'<path class="{cls}" d="{d}"{mk}/>')


def label(x, y, kind, anchor="middle"):
    cls = "rel" if kind == "inc" else "rel gold"
    S.append(f'<text class="{cls}" x="{x}" y="{y}" text-anchor="{anchor}">«{"include" if kind == "inc" else "extend"}»</text>')


def note(x, y, w, lines_, to):
    h = 14 + 17 * len(lines_)
    S.append(f'<path class="note" d="M{x} {y} H{x + w - 10} L{x + w} {y + 10} V{y + h} H{x} Z M{x + w - 10} {y} V{y + 10} H{x + w}"/>')
    for i, t in enumerate(lines_):
        S.append(f'<text class="svg-note" x="{x + 10}" y="{y + 20 + i * 17}">{esc(t)}</text>')
    fx, fy = to
    S.append(f'<path class="edge anchor" d="M{x} {y + h / 2:.1f} L{fx:.1f} {fy:.1f}"/>')


def build():
    # ── 유스케이스(타원) — 행: 요청자 묶음(0~4) · 확장(5) · 시간(6~7) · 운영자(8) · 동행자(9) · 여행자(10~11)
    uc("u05", 1, 0, "UC-05", "여행 중에 묻는다")
    uc("u02", 1, 1, "UC-02", "쓰던 계획으로 여행을 등록한다")
    uc("u08", 1, 2, "UC-08", "다른 안을 고르거나 되돌린다")
    uc("u06", 1, 3, "UC-06", "일정을 바꿔 달라고 한다")
    uc("u07", 1, 4, "UC-07", "생긴 문제를 알린다")
    uc("u09", 1, 6, "UC-09", "일정이 깨졌는지 검증한다")
    uc("u12", 1, 7, "UC-12", "일정 알림을 보낸다")
    uc("u13", 1, 8, "UC-13", "서비스 장애를 알아챈다")
    uc("u04", 1, 9, "UC-04", "여행계획서를 본다")
    uc("u01", 1, 10, "UC-01", "여행을 시작한다")
    uc("u14", 1, 11, "UC-14", "내 설정을 관리한다")
    uc("u03", 2, 2, "UC-03", "일정을 짜 달라고 한다")
    uc("u10", 2, 4, "UC-10 · 하위 기능", "일정을 다시 맞추고 알린다", "core")
    uc("u11", 2, 5, "UC-11 · 하위 기능", "바꾸기 전에 묻는다")

    # ── 주 액터(왼쪽) — 부모(일반) 액터를 위에, 자식(특수) 액터를 아래에 둔다(Ambler)
    actor(LEFT_X, ry(0) + 48, LEFT_W, 86, "«actor» 추상", "요청자", ["여행자 또는", "그의 AI 비서 앱"], "person", italic=True)
    actor(LEFT_X, ry(2) + 20, LEFT_W, 68, "«actor»", "개인 AI 비서 앱", ["API · MCP 로 연결"], "bot")
    actor(LEFT_X, ry(6) + 8, LEFT_W, ry(7) + 66 - (ry(6) + 8), "«actor»", "시간", ["3분마다 · 새벽 3시", "알림 보낼 시각"], "clock")
    actor(LEFT_X, ry(8) + 2, LEFT_W, 68, "«actor»", "운영자", ["장애 알림을 받는다"], "person")
    actor(LEFT_X, ry(9) + 2, LEFT_W, 68, "«actor»", "동행자", ["링크로 계획서만 본다"], "person")
    actor(LEFT_X, ry(10) + 2, LEFT_W, ry(11) + 70 - (ry(10) + 2), "«actor»", "여행자", ["자유여행자"], "person")
    # 요청자 줄기 → 05 · 02 · 08 · 06 · 07
    jy = ry(1)
    line([(LEFT_X + LEFT_W, jy), (TRUNK, jy)])
    S.append(f'<path class="edge" d="M{TRUNK} {ry(0) + 36} V{ry(4) + 36}"/>')
    for k, r in (("u05", 0), ("u02", 1), ("u08", 2), ("u06", 3), ("u07", 4)):
        y = ry(r) + 36
        line([(TRUNK, y), (ex(k, y, -1), y)])
    for k, r in (("u09", 6), ("u12", 7), ("u13", 8), ("u04", 9), ("u01", 10), ("u14", 11)):
        y = ry(r) + 36
        line([(LEFT_X + LEFT_W, y), (ex(k, y, -1), y)])
    # 일반화 — AI 앱 ⊳ 요청자 · 여행자 ⊳ 요청자 · 여행자 ⊳ 동행자
    line([(LEFT_X + 100, ry(2) + 19), (LEFT_X + 100, ry(1) + 39)], "gen")
    line([(LEFT_X, ry(10) + 56), (22, ry(10) + 56), (22, ry(1)), (LEFT_X - 1, ry(1))], "gen")
    line([(LEFT_X + 100, ry(10) + 1), (LEFT_X + 100, ry(9) + 71)], "gen")

    # ── 유스케이스끼리 ─────────────────────────────────
    # UC-03 ⇢ UC-02 «extend» — UC-03 의 왼쪽에서 통로를 따라 올라가 UC-02 오른쪽 아래로
    y3, y2 = ry(2) + 22, ry(1) + 66
    line([(ex("u03", y3, -1), y3), (625, y3), (625, y2), (ex("u02", y2, 1) + 1, y2)], "ext")
    S.append(f'<text class="rel gold" x="621" y="{ry(2) + 4}" text-anchor="middle" transform="rotate(-90 621 {ry(2) + 4})">«extend»</text>')
    n3x, n3y = C2 + 10, ry(3) + 4
    S.append(f'<path class="note" d="M{n3x} {n3y} H{n3x + 240} L{n3x + 250} {n3y + 10} V{n3y + 65} H{n3x} Z M{n3x + 240} {n3y} V{n3y + 10} H{n3x + 250}"/>')
    for i, t in enumerate(["확장점: 계획을 읽은 뒤", "조건: 계획이 비었거나", "「일정 짜 줘」를 골랐다"]):
        S.append(f'<text class="svg-note" x="{n3x + 10}" y="{n3y + 20 + i * 17}">{esc(t)}</text>')
    S.append(f'<path class="edge anchor" d="M{n3x} {n3y + 20} L625 {ry(2) + 40}"/>')
    # UC-06 → UC-10 «include»
    y6, y10 = ry(3) + 46, ry(4) + 16
    line([(ex("u06", y6, 1), y6), (625, y6), (625, y10), (ex("u10", y10, -1), y10)], "inc")
    label(621, ry(3) + 84, "inc", "end")
    # UC-10 ⇢ UC-07 «extend»(바꿔야 할 때만 — 품절 · 늦어도 되는 경우는 바꾸지 않는다)
    y7 = ry(4) + 42
    line([(ex("u10", y7, -1), y7), (ex("u07", y7, 1) + 1, y7)], "ext")
    label(625, y7 - 6, "ext")
    # UC-10 ⇢ UC-09 «extend»
    ys, y9 = ry(4) + 62, ry(6) + 20
    line([(ex("u10", ys, -1), ys), (632, ys), (632, y9), (ex("u09", y9, 1) + 1, y9)], "ext")
    S.append(f'<text class="rel gold" x="628" y="{ry(5) + 82}" text-anchor="middle" transform="rotate(-90 628 {ry(5) + 82})">«extend»</text>')
    nx, ny = C1 + 10, ry(5) + 4
    S.append(f'<path class="note" d="M{nx} {ny} H{nx + 240} L{nx + 250} {ny + 10} V{ny + 65} H{nx} Z M{nx + 240} {ny} V{ny + 10} H{nx + 250}"/>')
    for i, t in enumerate(["조건: 일정을 바꿔야 한다", "확장점: UC-07 신고를 읽은 뒤", "· UC-09 깨진 항목을 찾은 뒤"]):
        S.append(f'<text class="svg-note" x="{nx + 10}" y="{ny + 20 + i * 17}">{esc(t)}</text>')
    S.append(f'<path class="edge anchor" d="M{nx + 230} {ny} L{614} {y7 + 3}"/>')
    S.append(f'<path class="edge anchor" d="M{nx + 250} {ny + 40} L{632} {ny + 40}"/>')
    # UC-11 ⇢ UC-10 «extend»(확장은 기본 아래)
    a, b = top("u11"), bot("u10")
    line([a, (b[0], b[1] + 1)], "ext")
    label(a[0] - 6, a[1] - 8, "ext", "end")
    note(C3, ry(5) + 2, 270, ["확장점: 변경 저장 직전", "조건: 보호 일정 · 「먼저 물어봐」", "· 날씨만 걸림 등(5절 결정표)"], (b[0], b[1] + 12))

    # ── 보조 액터(오른쪽) ──────────────────────────────
    actor(RIGHT_X, ry(0) + 6, RIGHT_W, ry(1) + 30 - (ry(0) + 6), "«external»", "AI 모델", ["시험 중 — 로컬 · API 비교", "(아직 정하지 않음)"], "spark")
    iy1, iy2 = ry(1) + 42, ry(6) + 66
    actor(RIGHT_X, iy1, RIGHT_W, iy2 - iy1, "«external»", "외부 정보 서비스",
          ["장소 · 영업시간 · 교통 시간표", "날씨 · 기상 특보 · 단기예보", "재난문자 · 교통 사건", "", "관광공사 · 카카오 · Google", "기상청 등 공공 API"], "db")
    actor(RIGHT_X, ry(7) + 4, RIGHT_W, ry(11) + 68 - (ry(7) + 4), "«external»", "알림 채널",
          ["디스코드 웹훅", "일정 알림은 지금 팀 시연", "채널 하나로 간다", "(고객 주소는 저장 · 시험", "발송까지 — 배달 연결 전)"], "bell")
    y = ry(0) + 36
    line([(ex("u05", y, 1), y), (RIGHT_X, y)])
    y = ry(1) + 18
    line([(ex("u02", y, 1), y), (RIGHT_X, y)])
    y = ry(1) + 56
    line([(ex("u02", y, 1), y), (RIGHT_X, y)])
    y = ry(4) + 14
    line([(ex("u10", y, 1), y), (RIGHT_X, y)])
    y = ry(4) + 56
    line([(ex("u10", y, 1), y), (ROUTE, y), (ROUTE, ry(7) + 18), (RIGHT_X, ry(7) + 18)])
    y = ry(6) + 52
    line([(ex("u09", y, 1), y), (RIGHT_X, y)], hop_x=ROUTE)
    for k, r in (("u12", 7), ("u13", 8), ("u14", 11)):
        y = ry(r) + 40
        line([(ex(k, y, 1), y), (RIGHT_X, y)])
    return ry(11) + NH


CSS = f"""
:root{{--paper:#fbfcfd;--paper-2:#f1f4f8;--card:#ffffff;--ink:#161c28;--muted:#606b7e;--soft:#727d90;--rule-solid:#dbe0ea;
--accent:#a8720c;--accent-tint:rgba(168,114,12,.08);--accent-rule:rgba(168,114,12,.38);--core-fill:#fbf6ec;--note-fill:#fffdf6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--paper:#15181d;--paper-2:#20252d;--card:#1a1f26;--ink:#e9edf3;--muted:#b0bac9;--soft:#9aa6b9;
--rule-solid:#39424f;--accent:#e4b45c;--accent-tint:rgba(228,180,92,.09);--accent-rule:rgba(228,180,92,.42);--core-fill:#2a2418;--note-fill:#23211b}}}}
.diagram{{border:1px solid var(--rule-solid);border-radius:6px;background:var(--card);overflow-x:auto}}
.diagram svg{{display:block;width:100%;min-width:1100px;height:auto;color:var(--ink)}}
.diagram .sys-frame{{fill:var(--paper-2);stroke:var(--rule-solid);stroke-width:1.2}}
.diagram .node{{fill:var(--card);stroke:var(--rule-solid)}}
.diagram .core-node{{fill:var(--core-fill);stroke:var(--accent-rule)}}
.diagram .note{{fill:var(--note-fill);stroke:var(--rule-solid)}}
.diagram .edge{{fill:none;stroke:var(--muted);stroke-width:1.15;stroke-linejoin:round}}
.diagram .edge.inc{{stroke-dasharray:5 4}}
.diagram .edge.ext{{stroke:var(--accent);stroke-dasharray:5 4}}
.diagram .edge.anchor{{stroke:var(--soft);stroke-dasharray:2 3;stroke-width:1}}
.diagram .vee{{fill:none;stroke:var(--muted);stroke-width:1.3}} .diagram .vee-gold{{fill:none;stroke:var(--accent);stroke-width:1.3}}
.diagram .tri{{fill:var(--card);stroke:var(--muted);stroke-width:1.2}}
.diagram .icon{{fill:none;stroke:currentColor;stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}}
.diagram text{{fill:currentColor;font-family:{SANS};font-size:15px}}
.diagram .title{{font-size:22px;font-weight:700}}
.diagram .svg-label{{fill:var(--soft);font-family:{MONO};font-size:11px;letter-spacing:.04em}}
.diagram .svg-note{{fill:var(--muted);font-size:12px}}
.diagram .svg-letter{{fill:var(--accent);font-family:{MONO};font-size:12px}}
.diagram .sys-name{{font-weight:700;font-size:16px}}
.diagram .rel{{fill:var(--soft);font-family:{MONO};font-size:10.5px}} .diagram .rel.gold{{fill:var(--accent)}}
"""


def render(out="triPilot_유스케이스_다이어그램_v7", title="guguroute 유스케이스 다이어그램 — 맥락 수준"):
    S.clear(); U.clear()
    bottom = build()
    H, W = bottom + 96, RIGHT_X + RIGHT_W + 30
    head = (f'<text class="svg-label" x="{LEFT_X}" y="40">주 액터</text>'
            f'<text class="svg-label" x="{FRAME_X1}" y="40">시스템 경계</text>'
            f'<text class="svg-label" x="{RIGHT_X}" y="40">보조 액터(외부 시스템)</text>'
            f'<text class="title" x="{LEFT_X}" y="80">{esc(title)}</text>'
            f'<text class="svg-note" x="{LEFT_X}" y="104">v7 · 2026-10-03 · 멘토링 자료 규칙 · 사용자 목표 12개 + 공통 하위 기능 2개(UC-10 · 11) · 처리 단계는 명세 시나리오에 적었다</text>')
    frame = (f'<rect class="sys-frame" x="{FRAME_X1}" y="122" width="{FRAME_X2 - FRAME_X1}" height="{bottom - 122 + 16}" rx="10"/>'
             f'<text class="sys-name" x="{FRAME_X1 + 16}" y="146">guguroute</text>'
             f'<text class="svg-note" x="{FRAME_X1 + 86}" y="146">여행 계획을 받아 여행 끝까지 지키는 서비스</text>')
    foot = (f'<text class="svg-note" x="{LEFT_X}" y="{H - 48}">실선 = 연관(액터가 그 유스케이스에 참여 — 순서가 아님) · 회색 점선 «include» = 반드시 · 여러 유스케이스가 공통으로(기본 → 포함) · '
            f'금색 점선 «extend» = 조건이 맞을 때만(확장 → 기본, 확장점 · 조건은 노트) · 빈 삼각형 = 일반화</text>'
            f'<text class="svg-note" x="{LEFT_X}" y="{H - 28}">요청자(기울임) = 추상 액터: 여행자와 개인 AI 비서 앱이 같은 일을 한다 · 외부 정보 서비스 앞에서 선이 반원으로 건너뛰는 곳은 서로 이어지지 않는다 · '
            f'고객 건을 사람에게 넘기는 유스케이스는 없다</text>')
    defs = ('<defs>'
            '<marker id="vee" viewBox="0 0 10 10" markerWidth="9" markerHeight="9" refX="9" refY="5" orient="auto"><path class="vee" d="M1 1 L9 5 L1 9"/></marker>'
            '<marker id="vee-gold" viewBox="0 0 10 10" markerWidth="9" markerHeight="9" refX="9" refY="5" orient="auto"><path class="vee-gold" d="M1 1 L9 5 L1 9"/></marker>'
            '<marker id="tri" viewBox="0 0 14 14" markerWidth="13" markerHeight="13" refX="13" refY="7" orient="auto"><path class="tri" d="M1 1 L13 7 L1 13 Z"/></marker>'
            '</defs>')
    svg = (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(title)}">'
           f'{defs}{head}{frame}{"".join(S)}{foot}</svg>')
    page = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>guguroute 유스케이스 v7</title><style>body{{margin:0;background:var(--paper);color:var(--ink)}}.wrap{{max-width:{W}px;margin:0 auto;padding:16px}}{CSS}</style>'
            f'</head><body><div class="wrap"><div class="diagram">{svg}</div></div></body></html>')
    (OUT / f"{out}.html").write_text(page, encoding="utf-8")
    style = CSS.replace(".diagram ", "")
    (OUT / f"{out}.svg").write_text(svg.replace("<defs>", f"<style>{style}</style><defs>", 1), encoding="utf-8")
    print("ok", out, W, "x", H)


if __name__ == "__main__":
    render()
