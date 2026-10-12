# -*- coding: utf-8 -*-
"""triPilot 유스케이스 — 전부 한 장(합성판). 깔끔하게 나온 세부 그림 넷을 구역으로 위에서 아래로 쌓고,
구역 사이 «include»(2 여행 중 요청 · 4 자동 관리 → 3 일정 조율)만 직접 그어 한 장으로 만든다.

    python make_usecase_onepage.py   → ../uc_onepage.svg · ../uc_onepage.html (PNG 는 Edge 로 찍는다)

★왜 합성인가: 한 그래프에 다 넣으면(uc_all) 지원 액터가 여러 구역에 걸려 선이 그림 전체를 가로지른다.
  지원 액터(AI 모델 · 장소 정보 · 디스코드)는 구역마다 옆에 다시 그린다 — 같은 액터다(그림 아래 주석).
"""
import json
import re
import subprocess
from pathlib import Path

import make_usecase_v2 as V

OUT = V.OUT
DOT = V.DOT
G1, GOLD, BLUE = V.G1, V.GOLD, V.BLUE


class Band(V.D):
    def __init__(self, name, region, color):
        super().__init__(name, "", "")
        self.region, self.color = region, color
        self.head[1] = (f'  graph [rankdir=LR, splines=spline, nodesep=0.42, ranksep=0.9, pad=0.2, fontname="{V.FONT}", '
                        f'bgcolor="transparent", ordering=out];')

    def render(self):
        body = (self.head + (["  { rank=min; " + " ".join(self.L) + " }"] if self.L else [])
                + [f'  subgraph cluster_sys {{ label=<<B>triPilot · {self.region}</B>>; fontsize=16; fontcolor="{self.color}"; '
                   f'style="rounded"; color="{self.color}"; penwidth=2.2; margin=20;']
                + ["    " + u for u in self.U] + ["  }"]
                + (["  { rank=max; " + " ".join(self.R) + " }"] if self.R else [])
                + ["  " + e for e in self.E] + ["}"])
        p = OUT / f"{self.name}.dot"
        p.write_text("\n".join(body), encoding="utf-8")
        svg = subprocess.run([DOT, "-Tsvg", f"-Gimagepath={OUT}", str(p)], check=True, cwd=OUT, capture_output=True).stdout.decode("utf-8")
        js = json.loads(subprocess.run([DOT, "-Tjson", f"-Gimagepath={OUT}", str(p)], check=True, cwd=OUT, capture_output=True).stdout.decode("utf-8", errors="replace"), strict=False)
        return svg, js


def band1():
    d = Band("band1", "1 여행 준비", G1)
    d.person("traveler", "여행자"); d.person("companion", "동행자")
    d.system("aiapp", "개인 AI 비서 앱", "우리 API로 연결", side="L")
    d.uc("u01", "여행 시작하기", "UC-01", note="언어 · 설문 6문항")
    d.uc("u02", "계획 올리기", "UC-02", note="글 · 사진 · 파일 5개 · 10MB")
    d.uc("u03", "읽힌 일정 확인 · 고치기", "UC-03", note="고치기 · 빼기 → 등록")
    d.uc("u05", "여행계획서 보기", "UC-05", note="로그인 없는 링크 · 늘 최신")
    d.uc("u04", "일정 짜 달라고 하기", "UC-04", "ext")
    d.uc("r", "<B>계획 읽기</B>", "", "core", note="항목마다 값 · 방법 · 근거(원문 줄)")
    d.uc("r1", "정해진 모양 읽기", "", "sub", note="코드: 시각 · 일차 · 날짜 · 예약번호")
    d.uc("r2", "원문 위치 가리키기", "", "sub", note="AI: 남은 줄만 · 원문에 없으면 버림")
    d.uc("r3", "장소 하나로 정하기", "", "sub", note="우리 표 → 별칭 → 오타 → 카카오 · 관광공사")
    d.uc("r0", "사진 받아쓰기", "", "ext", note="한 줄씩 · 두 번 대조")
    d.uc("s", "여행 등록 · 계획서 링크 만들기", "", "sub")
    d.system("ai", "AI 모델", "시험 중 — 로컬 · API 비교"); d.system("place", "장소 정보", "우리 표 · 카카오 · 관광공사 · Places")
    d.raw('traveler -> companion [arrowhead=empty, arrowsize=1.3, penwidth=1.5, constraint=false];')
    d.assoc("traveler", "u01"); d.assoc("traveler", "u02"); d.assoc("traveler", "u03"); d.assoc("companion", "u05")
    d.assoc("aiapp", "u02"); d.assoc("aiapp", "u05")
    d.ext("u04", "u02"); d.inc("u02", "r"); d.inc("r", "r1"); d.inc("r", "r2"); d.inc("r", "r3"); d.ext("r0", "r"); d.inc("u03", "s")
    d.assoc("r2", "ai"); d.assoc("r0", "ai"); d.assoc("r3", "place")
    d.raw("u01 -> u02 -> u03 -> u05 [style=invis, constraint=false];")
    return d.render()


def band2():
    d = Band("band2", "2 여행 중 요청", G1)
    d.person("traveler", "여행자"); d.system("aiapp", "개인 AI 비서 앱", "우리 API로 연결", side="L")
    d.raw('req [shape=none, margin=0, label=<<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="2"><TR><TD><IMG SRC="actor.png"/></TD></TR><TR><TD><B>요청하는 쪽</B></TD></TR><TR><TD><FONT POINT-SIZE="10" COLOR="#5f6b64">여행자 · AI 비서 앱</FONT></TD></TR></TABLE>>];')
    d.uc("u06", "채팅으로 묻기", "UC-06", note="하루 요약 · 다음 이동 · 규정")
    d.uc("u07", "바꿔 달라고 하기", "UC-07", note="바로 바꾸고 다른 안 셋까지")
    d.uc("u08", "문제 알리기", "UC-08", note="늦음 · 휴무")
    d.uc("u09", "다른 안 고르기 · 되돌리기", "UC-09", note="「선택이 필요해요」 · 앞 판으로")
    d.uc("q", "<B>요청 읽기</B>", "", "core", note="요청 종류 5 · 대상 항목 · 문제 코드")
    d.uc("g", "근거 찾기", "", "sub", note="여행 규정 · 예약 취소 조건")
    d.uc("v", "새 판 저장", "", "sub", note="기준 판이 그대로일 때만")
    d.system("ai", "AI 모델", "같은 액터 · 시험 중")
    d.raw('traveler -> req [arrowhead=empty, arrowsize=1.3, penwidth=1.5];'); d.raw('aiapp -> req [arrowhead=empty, arrowsize=1.3, penwidth=1.5];')
    d.assoc("req", "u06"); d.assoc("req", "u07"); d.assoc("req", "u08"); d.assoc("req", "u09")
    d.inc("u06", "q"); d.inc("u06", "g"); d.inc("u07", "q"); d.inc("u08", "q"); d.inc("u09", "v")
    d.assoc("q", "ai"); d.assoc("g", "ai")
    d.raw("u06 -> u07 -> u08 -> u09 [style=invis, constraint=false];")
    return d.render()


def band3():
    d = Band("band3", "3 일정 조율 — 전부 통과할 때까지", GOLD)
    d.uc("c", "<B>일정 조율</B>", "UC-12", "core", note="UC-07 · 08 · 10 · 11 이 반드시 부른다")
    d.uc("a1", "영향받는 항목 추리기", "", "sub", note="바로 다음 · 오늘 · 이후 전부")
    d.uc("a2", "<B>담당 에이전트 점검</B>", "", "core", note="액티비티 → 요식 → 이동 · 앞 초안을 넘김")
    d.uc("a3", "적용", "", "sub", note="근거 대조(기준 판 · 항목 · 장소) → 새 판 1번")
    d.uc("a4", "변경 알리기", "UC-14", "core", note="알림 1번 · 계획서 새 판")
    d.uc("x1", "액티비티 점검", "", "sub", note="운영일 · 시간 · 날씨 · 대기질")
    d.uc("x2", "요식 점검", "", "sub", note="영업 · 브레이크 · 라스트오더")
    d.uc("x3", "이동 재판정", "", "sub", note="시간표로 앞뒤 구간 제시간?")
    d.uc("e1", "다음 후보로 다시", "", "ext", note="전부 통과 못 함 · 후보 남음")
    d.uc("e2", "바꾸기 전에 묻기", "UC-13", "ext", note="설문 「먼저 물어봐」 · 고정 · 안전 경보")
    d.uc("e3", "못 맞춤 알리기", "", "ext", note="후보 소진 · 조건 푼 안 제시")
    d.system("info", "장소 · 영업 · 교통 정보", "같은 액터 · 관광공사 · 카카오 · Google · 시간표"); d.system("discord", "디스코드", "지금은 팀 시연 채널 하나")
    d.inc("c", "a4"); d.inc("c", "a3"); d.inc("c", "a2"); d.inc("c", "a1")
    d.gen("a2", "x1"); d.gen("a2", "x2"); d.gen("a2", "x3")
    d.ext("e1", "a2"); d.ext("e2", "a3"); d.ext("e3", "c")
    d.assoc("x1", "info"); d.assoc("x2", "info"); d.assoc("x3", "info"); d.assoc("a4", "discord")
    return d.render()


def band4():
    d = Band("band4", "4 자동 관리", BLUE)
    d.system("timer", "시간", "3분 · 03:00 · 알림 시각 · 1분", stereo="시간", side="L")
    d.uc("u10", "외부 변화 감시", "UC-10", note="3분마다")
    d.uc("u11", "새벽 정기 점검", "UC-11", note="03:00~08:00 · 항목 · 날짜마다 한 번")
    d.uc("u15", "일정 알림 보내기", "UC-15", note="하루 시작 · 다음 일정 · 출발")
    d.uc("u16", "오류 알림 받기", "UC-16", note="상시 작업이 연속 실패할 때")
    d.uc("w1", "소스 수집", "", "sub", note="소스마다 한 번 · 값 · 지문")
    d.uc("w2", "바뀐 값에 걸린 항목 고르기", "", "sub", note="변화 없으면 사건 0 · 알림 0")
    d.uc("w3", "대체 소스로 다시 읽기", "", "ext", note="1차 실패 시 · 대체도 실패면 오류")
    d.uc("o1", "영업시간 조회", "", "sub", note="계획한 시각에 여나")
    d.uc("n1", "출발 시각 계산", "", "sub", note="다음 시작 − 이동 − 여유")
    d.uc("n2", "문구틀 번역", "", "sub", note="언어마다 처음 한 번 · 값은 원값")
    d.uc("n3", "알림 배달", "", "sub", note="3번까지 다시 · 중복 0")
    d.system("watch", "외부 데이터 6종", "날씨 · 특보 · 예보 · 재난문자 · 교통 2"); d.system("google", "장소 · 영업 정보", "같은 액터 · Google(새벽만)")
    d.system("ai", "AI 모델", "같은 액터 · 시험 중"); d.system("discord", "디스코드", "같은 액터"); d.person("operator", "운영자", side="R")
    d.assoc("timer", "u10"); d.assoc("timer", "u11"); d.assoc("timer", "u15"); d.assoc("timer", "u16")
    d.inc("u10", "w1"); d.inc("u10", "w2"); d.ext("w3", "w1"); d.inc("u11", "o1")
    d.inc("u15", "n1"); d.inc("u15", "n2"); d.inc("u15", "n3")
    d.assoc("w1", "watch"); d.assoc("w3", "watch"); d.assoc("o1", "google"); d.assoc("n2", "ai"); d.assoc("n3", "discord"); d.assoc("u16", "operator")
    d.raw("u10 -> u11 -> u15 -> u16 [style=invis, constraint=false];")
    return d.render()


def parse(svg, js):
    """svg 크기와 graphviz 좌표 → svg 좌표 변환값, 노드 중심 · 크기."""
    m = re.search(r'viewBox="([\d.\-]+) ([\d.\-]+) ([\d.]+) ([\d.]+)"', svg)
    vw, vh = float(m.group(3)), float(m.group(4))
    t = re.search(r'<g id="graph0" class="graph" transform="[^"]*translate\(([\d.\-]+) ([\d.\-]+)\)"', svg)
    tx, ty = float(t.group(1)), float(t.group(2))
    nodes = {}
    for o in js.get("objects", []):
        if "pos" in o and "name" in o:
            x, y = map(float, o["pos"].split(","))
            nodes[o["name"]] = (tx + x, ty - y, float(o.get("width", 1)) * 72, float(o.get("height", 0.5)) * 72)
    inner = re.sub(r"^.*?<svg[^>]*>", "", svg, count=1, flags=re.S)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.S)
    return vw, vh, nodes, inner


def main():
    V.stick(OUT / "actor.png")
    bands = [band1(), band2(), band3(), band4()]
    parsed = [parse(s, j) for s, j in bands]
    gap, top = 46, 92
    W = max(p[0] for p in parsed) + 40
    ys, y = [], top
    for vw, vh, _, _ in parsed:
        ys.append(y)
        y += vh + gap
    H = y + 70
    xs = [(W - p[0]) / 2 for p in parsed]
    parts = []
    for (vw, vh, nodes, inner), x0, y0 in zip(parsed, xs, ys):
        parts.append(f'<svg x="{x0:.1f}" y="{y0:.1f}" width="{vw:.1f}" height="{vh:.1f}" viewBox="0 0 {vw:.1f} {vh:.1f}" overflow="visible">{inner}</svg>')

    def at(b, n):
        x, y, w, h = parsed[b][2][n]
        return x + xs[b], y + ys[b], w, h

    cx, cy, cw, ch = at(2, "c")
    links = []
    # 2 → 3: 바꿔 달라고 하기 · 문제 알리기 → 일정 조율 (아래로)
    # ★요청하는 쪽의 연관선과 겹치지 않게 — 왼쪽이 아니라 두 열 사이 빈 통로로 내려가 구역 아래 틈에서 조율로 간다
    col_r = max(at(1, k)[0] + at(1, k)[2] / 2 for k in ("u06", "u07", "u08", "u09"))
    col_l = min(at(1, k)[0] - at(1, k)[2] / 2 for k in ("q", "g", "v"))
    band2_bottom = ys[1] + parsed[1][1]
    for i, n in enumerate(("u07", "u08")):
        x, y, w, h = at(1, n)
        sx, sy = x + w / 2 * 0.86, y + h * 0.28
        lane = col_r + (col_l - col_r) * (0.10 + 0.09 * i)
        gy = band2_bottom + 12 + i * 12
        ex, ey = cx - cw / 2 + 24 + i * 30, cy - ch / 2
        links.append((f"M{sx:.1f},{sy:.1f} L{lane:.1f},{sy:.1f} L{lane:.1f},{gy:.1f} L{ex:.1f},{gy:.1f} L{ex:.1f},{ey - 2:.1f}",
                      "«include»" if i == 0 else "", (lane + 40, band2_bottom + 44)))
    # 4 → 3: 외부 변화 감시 · 새벽 정기 점검 → 일정 조율 (위로)
    for i, n in enumerate(("u10", "u11")):
        x, y, w, h = at(3, n)
        sx, sy = x - w / 2 - 6, y
        lane = at(3, "u10")[0] - max(at(3, k)[2] for k in ("u10", "u11", "u15", "u16")) / 2 - 22 - i * 16
        ex, ey = cx - cw / 2 + 18 + (i + 2) * 30, cy + ch / 2
        links.append((f"M{sx:.1f},{sy:.1f} L{lane:.1f},{sy:.1f} L{lane:.1f},{ey + 34 + i * 12:.1f} L{ex:.1f},{ey + 34 + i * 12:.1f} L{ex:.1f},{ey + 2:.1f}", "«include»", (lane + 6, (sy + ey) / 2)))
    link_svg = "".join(f'<path d="{d}" fill="none" stroke="{G1}" stroke-width="2" stroke-dasharray="7 5" marker-end="url(#vee)"/>'
                       f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" fill="{G1}" font-family="Malgun Gothic">{t}</text>' for d, t, (lx, ly) in links)
    title = (f'<text x="{W / 2:.1f}" y="40" text-anchor="middle" font-size="26" font-weight="700" fill="#1d2a23" font-family="Malgun Gothic">triPilot 유스케이스 — 전체 한 장</text>'
             f'<text x="{W / 2:.1f}" y="66" text-anchor="middle" font-size="14" fill="#5f6b64" font-family="Malgun Gothic">'
             f'v2 · 2026-10-02 · 실제 API · 코드 기준 · 구역 넷은 하나의 시스템(triPilot) · 굵은 점선 = 구역 사이 «include»</text>')
    foot = (f'<text x="40" y="{H - 30:.1f}" font-size="13" fill="#5f6b64" font-family="Malgun Gothic">'
            f'실선 = 연관 · 점선 «include» = 반드시 쓰는 공통 기능 · 점선 «extend» = 조건이 맞을 때만 · 빈 삼각형 = 일반화 · '
            f'AI 모델 · 장소 정보 · 디스코드는 같은 액터를 구역마다 옆에 다시 그렸다(선을 짧게)</text>')
    defs = (f'<defs><marker id="vee" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10" fill="none" stroke="{G1}" stroke-width="1.8"/></marker></defs>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}">'
           f'<rect width="100%" height="100%" fill="#ffffff"/>{defs}{title}{"".join(parts)}{link_svg}{foot}</svg>')
    (OUT / "uc_onepage.svg").write_text(svg, encoding="utf-8")
    import base64
    png64 = base64.b64encode((OUT / "actor.png").read_bytes()).decode()
    one = re.sub(r'xlink:href="[^"]*actor\.png"', f'xlink:href="data:image/png;base64,{png64}"', svg)
    (OUT / "uc_onepage.html").write_text(f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>triPilot 유스케이스 전체 한 장</title>'
                                         f'<style>body{{margin:0;background:#fff}}svg{{display:block}}</style></head><body>{one}</body></html>', encoding="utf-8")
    print("ok", int(W), "x", int(H))


if __name__ == "__main__":
    main()
