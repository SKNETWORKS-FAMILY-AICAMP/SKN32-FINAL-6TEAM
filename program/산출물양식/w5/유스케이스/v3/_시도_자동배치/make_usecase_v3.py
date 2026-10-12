# -*- coding: utf-8 -*-
"""triPilot 유스케이스 v3 — 「유스케이스 2026-10-02 v6」 브리핑의 「한눈에」 그림 스타일로 다시 그린다.

스타일(그 문서의 CSS 그대로):
  흰 상자 · 옅은 회색 테두리(#dbe0ea) · 핵심 상자만 옅은 금색(accent-tint · accent-rule) · 구역은 옅은 회색 판(#f1f4f8)
  선은 가늘고(1.15) 직각으로만 꺾인다(splines=ortho) · 이름표는 고정폭 작은 글씨 · 본문 Noto Sans KR
내용은 v2 와 같다(실제 API · 코드 기준). 구역 넷을 위에서 아래로 쌓아 한 장으로 합친다.

    python make_usecase_v3.py   → ../uc_onepage_v3.svg · .html · (PNG 는 Edge 로)
"""
import base64
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DOT = r"C:\Program Files\Graphviz\bin\dot.exe"
SANS, MONO = "Malgun Gothic", "NanumGothicCoding"   # 그래프 도구가 글자 폭을 바로 재는 글꼴(Noto 는 폭을 잘못 잼)
INK, MUTED, SOFT, RULE = "#161c28", "#606b7e", "#727d90", "#dbe0ea"
PAPER2, CARD = "#f1f4f8", "#ffffff"
ACC, ACC_TINT, ACC_RULE = "#a8720c", "#f8f3ea", "#d6b680"   # accent · 옅은 금색(불투명으로 환산) · 금색 테두리


# ── 아이콘(참고 그림처럼 가는 선) ─────────────────────────────
def icon(name: str) -> None:
    k, s = 6, 34
    im = Image.new("RGBA", (s * k, s * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, lw = (22, 28, 40), int(1.6 * k)
    if name == "person":
        d.ellipse((12 * k, 3 * k, 22 * k, 13 * k), outline=c, width=lw)
        d.line((17 * k, 13 * k, 17 * k, 23 * k), fill=c, width=lw)
        d.line((9 * k, 17 * k, 25 * k, 17 * k), fill=c, width=lw)
        d.line((17 * k, 23 * k, 11 * k, 31 * k), fill=c, width=lw)
        d.line((17 * k, 23 * k, 23 * k, 31 * k), fill=c, width=lw)
    elif name == "bot":
        d.rounded_rectangle((7 * k, 9 * k, 27 * k, 26 * k), radius=3 * k, outline=c, width=lw)
        d.line((17 * k, 4 * k, 17 * k, 9 * k), fill=c, width=lw)
        d.line((12 * k, 16 * k, 14 * k, 16 * k), fill=c, width=lw)
        d.line((20 * k, 16 * k, 22 * k, 16 * k), fill=c, width=lw)
        d.line((13 * k, 21 * k, 21 * k, 21 * k), fill=c, width=lw)
    elif name == "clock":
        d.ellipse((6 * k, 6 * k, 28 * k, 28 * k), outline=c, width=lw)
        d.line((17 * k, 11 * k, 17 * k, 17 * k), fill=c, width=lw)
        d.line((17 * k, 17 * k, 22 * k, 20 * k), fill=c, width=lw)
    elif name == "db":
        d.ellipse((8 * k, 5 * k, 26 * k, 11 * k), outline=c, width=lw)
        d.line((8 * k, 8 * k, 8 * k, 27 * k), fill=c, width=lw)
        d.line((26 * k, 8 * k, 26 * k, 27 * k), fill=c, width=lw)
        d.arc((8 * k, 24 * k, 26 * k, 30 * k), 0, 180, fill=c, width=lw)
        d.arc((8 * k, 15 * k, 26 * k, 21 * k), 0, 180, fill=c, width=lw)
    elif name == "bell":
        d.arc((9 * k, 6 * k, 25 * k, 26 * k), 180, 360, fill=c, width=lw)
        d.line((9 * k, 16 * k, 9 * k, 24 * k), fill=c, width=lw)
        d.line((25 * k, 16 * k, 25 * k, 24 * k), fill=c, width=lw)
        d.line((6 * k, 24 * k, 28 * k, 24 * k), fill=c, width=lw)
        d.line((15 * k, 28 * k, 19 * k, 28 * k), fill=c, width=lw)
    elif name == "spark":
        for a, b in (((17, 4), (17, 30)), ((4, 17), (30, 17)), ((8, 8), (26, 26)), ((26, 8), (8, 26))):
            d.line((a[0] * k, a[1] * k, b[0] * k, b[1] * k), fill=c, width=lw)
    im.resize((s, s), Image.LANCZOS).save(OUT / f"ic_{name}.png")


# ── 그래프 조각 ───────────────────────────────────────────────
def actor(key, name, note, ic):
    return (f'{key} [shape=box, style="rounded,filled", fillcolor="{CARD}", color="{RULE}", penwidth=1, margin="0.10,0.06", '
            f'label=<<TABLE BORDER="0" CELLPADDING="1" CELLSPACING="4"><TR><TD ROWSPAN="2"><IMG SRC="ic_{ic}.png"/></TD>'
            f'<TD ALIGN="LEFT"><FONT FACE="{SANS}" POINT-SIZE="14" COLOR="{INK}">{name}</FONT></TD></TR>'
            f'<TR><TD ALIGN="LEFT"><FONT FACE="{SANS}" POINT-SIZE="11" COLOR="{MUTED}">{note}</FONT></TD></TR></TABLE>>];')


def uc(key, name, code="", note="", kind=""):
    fill, line, dash = {"": (CARD, RULE, ""), "core": (ACC_TINT, ACC_RULE, ""), "ext": (CARD, ACC_RULE, ",dashed"),
                        "sub": (CARD, RULE, "")}[kind]
    tag = f'<FONT FACE="{MONO}" POINT-SIZE="11" COLOR="{ACC}">{code}  </FONT>' if code else ""
    sub = f'<BR ALIGN="LEFT"/><FONT FACE="{SANS}" POINT-SIZE="11" COLOR="{MUTED}">{note}</FONT>' if note else ""
    return (f'{key} [shape=box, style="rounded,filled{dash}", fillcolor="{fill}", color="{line}", penwidth=1, margin="0.14,0.07", '
            f'label=<{tag}<FONT FACE="{SANS}" POINT-SIZE="14" COLOR="{INK}">{name}</FONT>{sub}<BR ALIGN="LEFT"/>>];')


class Band:
    def __init__(self, name, letter, title):
        self.name, self.letter, self.title = name, letter, title
        self.L, self.U, self.R, self.E = [], [], [], []

    def assoc(self, a, b, **kw):
        extra = "".join(f", {k}={v}" for k, v in kw.items())
        self.E.append(f"{a} -> {b} [arrowhead=none{extra}];")

    def inc(self, base, add, back=False):
        if back:
            self.E.append(f'{add} -> {base} [style=dashed, dir=back, arrowtail=vee];')
        else:
            self.E.append(f'{base} -> {add} [style=dashed, arrowhead=vee];')

    def ext(self, extension, base):
        self.E.append(f'{base} -> {extension} [style=dashed, dir=back, arrowtail=vee, color="{ACC_RULE}"];')

    def gen(self, parent, child):
        self.E.append(f'{parent} -> {child} [dir=back, arrowtail=empty, arrowsize=1.1];')

    def dot(self):
        head = [
            "digraph UC {",
            f'  graph [rankdir=LR, splines=ortho, nodesep=0.42, ranksep=0.95, pad=0.15, bgcolor="transparent", fontname="{SANS}", forcelabels=true];',
            f'  node [fontname="{SANS}", fontsize=14];',
            f'  edge [color="{MUTED}", penwidth=1.15, arrowsize=0.7, fontname="{MONO}", fontsize=9];',
        ]
        body = head + (["  { rank=min; " + " ".join(self.L) + " }"] if self.L else [])
        body += [f'  subgraph cluster_g {{ label=<<FONT FACE="{MONO}" POINT-SIZE="12" COLOR="{SOFT}">{self.letter} · {self.title}</FONT>>; '
                 f'labeljust=l; style="rounded,filled"; fillcolor="{PAPER2}"; color="{RULE}"; penwidth=1; margin=16;']
        body += ["    " + u for u in self.U] + ["  }"]
        body += (["  { rank=max; " + " ".join(self.R) + " }"] if self.R else []) + ["  " + e for e in self.E] + ["}"]
        return "\n".join(body)

    def render(self):
        p = OUT / f"{self.name}.dot"
        p.write_text(self.dot(), encoding="utf-8")
        svg = subprocess.run([DOT, "-Tsvg", f"-Gimagepath={OUT}", str(p)], check=True, cwd=OUT, capture_output=True).stdout.decode("utf-8")
        js = json.loads(subprocess.run([DOT, "-Tjson", f"-Gimagepath={OUT}", str(p)], check=True, cwd=OUT,
                                       capture_output=True).stdout.decode("utf-8", errors="replace"), strict=False)
        return svg, js


# ── 구역 넷(v2 와 같은 내용) ───────────────────────────────────
def band_a():
    b = Band("v3_a", "A", "여행 준비 — 계획을 받아 일정으로 읽는다")
    b.L += [actor("traveler", "여행자", "국적 무관 자유여행자", "person"), actor("companion", "동행자", "링크로 계획서만 본다", "person"),
            actor("aiapp", "개인 AI 비서 앱", "우리 API로 연결", "bot")]
    b.U += [uc("u01", "여행 시작하기", "UC-01", "언어 · 설문 6문항"), uc("u03", "읽힌 일정 확인 · 고치기", "UC-03", "고치기 · 빼기 → 등록"),
            uc("u02", "계획 올리기", "UC-02", "글 · 사진 · 파일 5개 · 10MB"), uc("u05", "여행계획서 보기", "UC-05", "로그인 없는 링크 · 늘 최신"),
            uc("s", "여행 등록 · 계획서 링크", "", "", "sub"), uc("r", "계획 읽기", "", "매니저(코어)의 처리 단계 · 값 · 방법 · 근거", "core"),
            uc("u04", "일정 짜 달라고 하기", "UC-04", "계획이 비었거나 「일정 짜 줘」", "ext"),
            uc("r3", "장소 하나로 정하기", "", "표 → 별칭 → 오타 → 카카오 · 관광공사", "sub"),
            uc("r1", "정해진 모양 읽기", "", "코드: 시각 · 일차 · 예약번호", "sub"),
            uc("r2", "원문 위치 가리키기", "", "AI: 남은 줄만 · 원문에 없으면 버림", "sub"),
            uc("r0", "사진 받아쓰기", "", "한 줄씩 · 두 번 대조", "ext")]
    b.R += [actor("place", "장소 정보", "우리 표 · 카카오 · 관광공사 · Places", "db"), actor("ai", "AI 모델", "시험 중 — 로컬 · API 비교", "spark")]
    b.E.append(f'traveler -> companion [dir=back, arrowtail=empty, arrowsize=1.1, constraint=false];')
    for a, c in (("traveler", "u01"), ("traveler", "u03"), ("traveler", "u02"), ("aiapp", "u02"), ("aiapp", "u05"), ("companion", "u05")):
        b.assoc(a, c)
    b.inc("u03", "s"); b.inc("u02", "r"); b.ext("u04", "u02")
    b.inc("r", "r3"); b.inc("r", "r1"); b.inc("r", "r2"); b.ext("r0", "r")
    b.assoc("r3", "place"); b.assoc("r2", "ai"); b.assoc("r0", "ai")
    return b.render()


def band_d():
    b = Band("v3_d", "B", "여행 중 요청 — 읽고, 근거로 답하고, 바꿀 일은 조율로")
    b.L += [actor("req", "요청하는 쪽", "여행자 · AI 비서 앱(위와 같은 행위자)", "person")]
    b.U += [uc("u06", "채팅으로 묻기", "UC-06", "하루 요약 · 다음 이동 · 규정"), uc("u07", "바꿔 달라고 하기", "UC-07", "바로 바꾸고 다른 안 셋까지"),
            uc("u08", "문제 알리기", "UC-08", "늦음 · 휴무"), uc("u09", "다른 안 고르기 · 되돌리기", "UC-09", "「선택이 필요해요」 · 앞 판으로"),
            uc("g", "근거 찾기", "", "여행 규정 · 예약 취소 조건", "sub"), uc("q", "요청 읽기", "", "요청 종류 5 · 대상 항목 · 문제 코드", "core"),
            uc("v", "새 판 저장", "", "기준 판이 그대로일 때만", "sub")]
    b.R += [actor("ai", "AI 모델", "같은 행위자 · 시험 중", "spark")]
    for c in ("u06", "u07", "u08", "u09"):
        b.assoc("req", c)
    b.inc("u06", "g"); b.inc("u06", "q"); b.inc("u07", "q"); b.inc("u08", "q"); b.inc("u09", "v")
    b.assoc("g", "ai"); b.assoc("q", "ai")
    return b.render()


def band_c():
    b = Band("v3_c", "C", "일정 조율 — 전부 통과할 때까지 다시 맞춘다")
    b.U += [uc("c", "일정 조율", "UC-12", "UC-07 · 08 · 10 · 11 이 반드시 부른다", "core"),
            uc("e3", "못 맞춤 알리기", "", "후보 소진 · 조건 푼 안 제시", "ext"),
            uc("a1", "영향받는 항목 추리기", "", "바로 다음 · 오늘 · 이후 전부", "sub"),
            uc("a2", "담당 에이전트 점검", "", "액티비티 → 요식 → 이동 · 앞 초안을 넘김", "core"),
            uc("a3", "적용", "", "근거 대조(기준 판 · 항목 · 장소) → 새 판 1번", "sub"),
            uc("a4", "변경 알리기", "UC-14", "알림 1번 · 계획서 새 판", "core"),
            uc("x1", "액티비티 점검", "", "운영일 · 시간 · 날씨 · 대기질", "sub"), uc("x2", "요식 점검", "", "영업 · 브레이크 · 라스트오더", "sub"),
            uc("x3", "이동 재판정", "", "시간표로 앞뒤 구간 제시간?", "sub"),
            uc("e1", "다음 후보로 다시", "", "전부 통과 못 함 · 후보 남음", "ext"),
            uc("e2", "바꾸기 전에 묻기", "UC-13", "「먼저 물어봐」 · 고정 · 안전 경보", "ext")]
    b.R += [actor("info", "장소 · 영업 · 교통 정보", "같은 행위자 · 관광공사 · 카카오 · Google · 시간표", "db"),
            actor("discord", "알림 채널", "디스코드 — 지금은 팀 시연 채널 하나", "bell")]
    b.ext("e3", "c"); b.inc("c", "a1"); b.inc("c", "a2"); b.inc("c", "a3"); b.inc("c", "a4")
    b.gen("a2", "x1"); b.gen("a2", "x2"); b.gen("a2", "x3"); b.ext("e1", "a2"); b.ext("e2", "a3")
    b.assoc("x1", "info"); b.assoc("x2", "info"); b.assoc("x3", "info"); b.assoc("a4", "discord")
    return b.render()


def band_b():
    b = Band("v3_b", "D", "자동 관리 — 시간이 깨워 여행 끝까지 돈다")
    b.L += [actor("timer", "시계", "3분 · 03:00 · 알림 시각 · 1분", "clock")]
    b.U += [uc("u10", "외부 변화 감시", "UC-10", "3분마다"), uc("u11", "새벽 정기 점검", "UC-11", "03:00~08:00 · 항목 · 날짜마다 한 번"),
            uc("u15", "일정 알림 보내기", "UC-15", "하루 시작 · 다음 일정 · 출발"), uc("u16", "오류 알림 받기", "UC-16", "상시 작업이 연속 실패할 때"),
            uc("w2", "바뀐 값에 걸린 항목 고르기", "", "변화 없으면 사건 0 · 알림 0", "sub"), uc("w1", "소스 수집", "", "소스마다 한 번 · 값 · 지문", "sub"),
            uc("w3", "대체 소스로 다시 읽기", "", "1차 실패 시 · 대체도 실패면 오류", "ext"), uc("o1", "영업시간 조회", "", "계획한 시각에 여나", "sub"),
            uc("n1", "출발 시각 계산", "", "다음 시작 − 이동 − 여유", "sub"), uc("n2", "문구틀 번역", "", "언어마다 처음 한 번 · 값은 원값", "sub"),
            uc("n3", "알림 배달", "", "3번까지 다시 · 중복 0", "sub")]
    b.R += [actor("watch", "외부 데이터 6종", "날씨 · 특보 · 예보 · 재난문자 · 교통 2", "db"), actor("google", "장소 · 영업 정보", "같은 행위자 · Google(새벽만)", "db"),
            actor("ai", "AI 모델", "같은 행위자 · 시험 중", "spark"), actor("discord", "알림 채널", "같은 행위자 · 디스코드", "bell"),
            actor("operator", "운영자", "오류 알림만 — 고객 건은 받지 않음", "person")]
    for c in ("u10", "u11", "u15", "u16"):
        b.assoc("timer", c)
    b.inc("u10", "w2"); b.inc("u10", "w1"); b.ext("w3", "w1"); b.inc("u11", "o1")
    b.inc("u15", "n2"); b.inc("u15", "n3"); b.inc("u15", "n1")
    b.assoc("w1", "watch"); b.assoc("w3", "watch"); b.assoc("o1", "google"); b.assoc("n2", "ai"); b.assoc("n3", "discord"); b.assoc("u16", "operator")
    return b.render()


def parse(svg, js):
    m = re.search(r'viewBox="([\d.\-]+) ([\d.\-]+) ([\d.]+) ([\d.]+)"', svg)
    vw, vh = float(m.group(3)), float(m.group(4))
    t = re.search(r'<g id="graph0" class="graph" transform="[^"]*translate\(([\d.\-]+) ([\d.\-]+)\)"', svg)
    tx, ty = float(t.group(1)), float(t.group(2))
    nodes = {}
    for o in js.get("objects", []):
        if "pos" in o and "name" in o:
            x, y = map(float, o["pos"].split(","))
            nodes[o["name"]] = (tx + x, ty - y, float(o.get("width", 1)) * 72, float(o.get("height", 0.5)) * 72)
    clus = None
    for o in js.get("objects", []):
        if o.get("name") == "cluster_g" and "bb" in o:
            x1, y1, x2, y2 = map(float, o["bb"].split(","))
            clus = (tx + x1, ty - y2, tx + x2, ty - y1)
    inner = re.sub(r"^.*?<svg[^>]*>", "", svg, count=1, flags=re.S)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.S)
    inner = re.sub(r'<polygon fill="white" stroke="none"[^>]*>', "", inner, count=1)   # 바탕 흰 판 빼기
    return vw, vh, nodes, clus, inner


def main():
    for n in ("person", "bot", "clock", "db", "bell", "spark"):
        icon(n)
    bands = [band_a(), band_d(), band_c(), band_b()]
    P = [parse(s, j) for s, j in bands]
    # 구역 판의 왼쪽 끝을 한 줄로 맞춘다
    left = max(p[3][0] for p in P) + 10
    xs = [left - p[3][0] for p in P]
    gap, top = 40, 118
    ys, y = [], top
    for p in P:
        ys.append(y)
        y += p[1] + gap
    W = max(x + p[0] for x, p in zip(xs, P)) + 30
    H = y + 50
    frame_x1 = min(x + p[3][0] for x, p in zip(xs, P)) - 18
    frame_x2 = max(x + p[3][2] for x, p in zip(xs, P)) + 18
    frame_y1, frame_y2 = ys[0] + P[0][3][1] - 34, ys[-1] + P[-1][3][3] + 18

    def at(i, n):
        x, y, w, h = P[i][2][n]
        return x + xs[i], y + ys[i], w, h

    cx, cy, cw, ch = at(2, "c")
    links = []
    # B(여행 중 요청) → C: 바꿔 달라고 하기 · 문제 알리기 → 일정 조율
    col_r = max(at(1, k)[0] + at(1, k)[2] / 2 for k in ("u06", "u07", "u08", "u09"))
    col_l = min(at(1, k)[0] - at(1, k)[2] / 2 for k in ("q", "g", "v"))
    b_bottom = ys[1] + P[1][3][3]
    for i, n in enumerate(("u07", "u08")):
        x, y, w, h = at(1, n)
        sx, sy = x + w / 2, y + h * 0.30
        lane = col_r + (col_l - col_r) * (0.14 + 0.12 * i)
        gy = b_bottom + 10 + i * 10
        ex, ey = cx - cw / 2 + 26 + i * 26, cy - ch / 2
        links.append(f"M{sx:.1f},{sy:.1f} H{lane:.1f} V{gy:.1f} H{ex:.1f} V{ey - 1:.1f}")
    # D(자동 관리) → C: 외부 변화 감시 · 새벽 정기 점검 → 일정 조율
    lane0 = min(at(3, k)[0] - at(3, k)[2] / 2 for k in ("u10", "u11", "u15", "u16")) - 18
    for i, n in enumerate(("u10", "u11")):
        x, y, w, h = at(3, n)
        sx, sy = x - w / 2, y - h * 0.20
        lane = lane0 + 8 * i
        gy = ys[3] + P[3][3][1] - 10 - i * 10
        ex, ey = cx - cw / 2 + 26 + (i + 2) * 26, cy + ch / 2
        links.append(f"M{sx:.1f},{sy:.1f} H{lane:.1f} V{gy:.1f} H{ex:.1f} V{ey + 1:.1f}")
    link_svg = "".join(f'<path d="{d}" fill="none" stroke="{MUTED}" stroke-width="1.3" stroke-dasharray="5 4" marker-end="url(#vee)"/>' for d in links)
    lab_y = (b_bottom + ys[2] + P[2][3][1]) / 2 + 4
    link_lab = (f'<text x="{col_r + 60:.1f}" y="{lab_y:.1f}" font-family="{MONO}" font-size="11" fill="{SOFT}">include — 바꿔 달라고 하기 · 문제 알리기 → 일정 조율</text>'
                f'<text x="{lane0 + 30:.1f}" y="{ys[3] + P[3][3][1] - 26:.1f}" font-family="{MONO}" font-size="11" fill="{SOFT}">include — 외부 변화 감시 · 새벽 정기 점검 → 일정 조율</text>')
    parts = "".join(f'<svg x="{x:.1f}" y="{y0:.1f}" width="{p[0]:.1f}" height="{p[1]:.1f}" viewBox="0 0 {p[0]:.1f} {p[1]:.1f}" overflow="visible">{p[4]}</svg>'
                    for x, y0, p in zip(xs, ys, P))
    head = (f'<text x="30" y="40" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{SOFT}">사람 · 앱</text>'
            f'<text x="{frame_x1 + 22:.1f}" y="40" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{SOFT}">유스케이스 — triPilot</text>'
            f'<text x="{frame_x2 + 26:.1f}" y="40" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{SOFT}">시스템 행위자</text>'
            f'<text x="30" y="78" font-family="{SANS}" font-size="22" font-weight="700" fill="{INK}">triPilot 유스케이스 — 전체 한 장</text>'
            f'<text x="30" y="100" font-family="{SANS}" font-size="13" fill="{MUTED}">v3 · 2026-10-02 · 실제 API · 코드 기준 · 실선 = 연관 · 회색 점선 = 반드시 쓰는 공통 기능(«include») · 금색 점선 = 조건이 맞을 때만(«extend») · 빈 삼각형 = 일반화 · 금색 상자 = 핵심 처리</text>')
    frame = f'<rect x="{frame_x1:.1f}" y="{frame_y1:.1f}" width="{frame_x2 - frame_x1:.1f}" height="{frame_y2 - frame_y1:.1f}" rx="10" fill="none" stroke="{RULE}" stroke-width="1.2"/>'
    foot = (f'<text x="30" y="{H - 18:.1f}" font-family="{SANS}" font-size="12" fill="{MUTED}">'
            f'AI 모델 · 장소 정보 · 알림 채널은 같은 행위자를 구역마다 옆에 다시 그렸다(선을 짧게). 고객 건을 사람에게 넘기는 유스케이스는 없다 — 운영자는 오류 알림만 받는다.</text>')
    defs = (f'<defs><marker id="vee" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">'
            f'<path d="M0,0 L8,4 L0,8" fill="none" stroke="{MUTED}" stroke-width="1.3"/></marker></defs>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}">'
           f'<rect width="100%" height="100%" fill="#fbfcfd"/>{defs}{head}{frame}{parts}{link_svg}{link_lab}{foot}</svg>')
    (OUT / "uc_onepage_v3.svg").write_text(svg, encoding="utf-8")
    one = svg
    for n in ("person", "bot", "clock", "db", "bell", "spark"):
        b64 = base64.b64encode((OUT / f"ic_{n}.png").read_bytes()).decode()
        one = re.sub(rf'xlink:href="[^"]*ic_{n}\.png"', f'xlink:href="data:image/png;base64,{b64}"', one)
    (OUT / "uc_onepage_v3.html").write_text(
        f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>triPilot 유스케이스 전체 한 장 v3</title>'
        f'<style>body{{margin:0;background:#fbfcfd}}svg{{display:block}}</style></head><body>{one}</body></html>', encoding="utf-8")
    print("ok", int(W), "x", int(H))


if __name__ == "__main__":
    main()
