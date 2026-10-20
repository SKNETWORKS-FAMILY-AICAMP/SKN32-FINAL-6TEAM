# -*- coding: utf-8 -*-
"""guguroute 유스케이스 다이어그램 — 공식 Graphviz(16)로 로컬에서 그린다. 바깥 서버로 보내지 않는다.

    python make_usecase.py   → ../usecase_v1.dot · .svg · .png

표기 기준: 「SW 요구사항 · 아키텍처 설계」 교재(2026-08-19) 유스케이스 장
  - 액터는 경계 밖, 유스케이스는 경계 안. 사람 아닌 것도 액터(외부 시스템 · 시간)
  - 연관 = 실선(액터 ↔ 유스케이스만) · 포함 = 점선 «include»(기본 → 공통, 재사용일 때만)
  - 확장 = 점선 «extend»(추가 → 기본) · 일반화 = 실선 + 빈 삼각형(액터끼리 · 유스케이스끼리)
  - 유스케이스끼리 순서를 그리지 않는다(순서는 시나리오에 글로)
"""
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DOT = r"C:\Program Files\Graphviz\bin\dot.exe"
FONT = "Malgun Gothic"


def stick(path: Path, color=(29, 42, 35)) -> None:
    """사람 액터 그림(막대 인형). 4배로 그려 줄인다."""
    k = 4
    w, h = 44 * k, 70 * k
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = 3 * k
    cx = w // 2
    d.ellipse((cx - 9 * k, 3 * k, cx + 9 * k, 21 * k), outline=color, width=lw)
    d.line((cx, 21 * k, cx, 46 * k), fill=color, width=lw)
    d.line((cx - 16 * k, 30 * k, cx + 16 * k, 30 * k), fill=color, width=lw)
    d.line((cx, 46 * k, cx - 13 * k, 66 * k), fill=color, width=lw)
    d.line((cx, 46 * k, cx + 13 * k, 66 * k), fill=color, width=lw)
    im.resize((44, 70), Image.LANCZOS).save(path)


def person(key, name):
    return (f'{key} [shape=none, margin=0, label=<<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="2">'
            f'<TR><TD><IMG SRC="actor.png"/></TD></TR><TR><TD><B>{name}</B></TD></TR></TABLE>>];')


def system(key, name, stereo="시스템", note=""):
    sub = f'<BR/><FONT POINT-SIZE="11" COLOR="#5f6b64">{note}</FONT>' if note else ""
    return (f'{key} [shape=box, style="rounded,filled", fillcolor="#f6ead4", color="#c8913a", penwidth=1.6, '
            f'label=<<FONT POINT-SIZE="11" COLOR="#8a5f1c">«{stereo}»</FONT><BR/><B>{name}</B>{sub}>];')


def uc(key, code, name, kind=""):
    fill = {"core": "#e5efe8", "ext": "#fbf4e6", "": "#fffdf7"}[kind]
    line = {"core": "#2d5f48", "ext": "#c8913a", "": "#7f8f86"}[kind]
    return (f'{key} [shape=ellipse, style=filled, fillcolor="{fill}", color="{line}", penwidth=1.6, '
            f'label=<<FONT POINT-SIZE="10" COLOR="#7d867f">{code}</FONT><BR/>{name}>];')


LINES = [
    "digraph UC {",
    f'  graph [rankdir=LR, splines=true, nodesep=0.32, ranksep=1.25, pad=0.3, fontname="{FONT}", bgcolor="#ffffff",'
    f'         label=<<B>guguroute 유스케이스 다이어그램</B> <FONT POINT-SIZE="12" COLOR="#5f6b64">v1 · 2026-10-02 · 실제 API · 코드 기준</FONT>>,'
    '         labelloc=t, fontsize=20];',
    f'  node [fontname="{FONT}", fontsize=13];',
    f'  edge [fontname="{FONT}", fontsize=11, color="#5f6b64", penwidth=1.3, arrowhead=none];',
    # 왼쪽 — 시작하는 쪽(주 액터)
    "  { rank=min;",
    "    " + person("traveler", "여행자"),
    "    " + person("companion", "동행자"),
    "    " + system("aiapp", "개인 AI 비서 앱", note="우리 API로 연결"),
    "  }",
    # 경계 — 우리가 만드는 것
    '  subgraph cluster_sys { label=<<B>guguroute</B>>; fontsize=17; style="rounded"; color="#2d5f48"; penwidth=2.2; margin=22;',
    "    " + uc("u01", "UC-01", "여행 시작하기<BR/>(언어 · 취향 설문)"),
    "    " + uc("u02", "UC-02", "계획 올리기"),
    "    " + uc("u03", "UC-03", "읽힌 일정<BR/>확인 · 고치기"),
    "    " + uc("u04", "UC-04", "일정 짜 달라고 하기", "ext"),
    "    " + uc("u05", "UC-05", "여행계획서 보기"),
    "    " + uc("u06", "UC-06", "채팅으로 묻기"),
    "    " + uc("u07", "UC-07", "바꿔 달라고 하기"),
    "    " + uc("u08", "UC-08", "문제 알리기<BR/>(늦음 · 휴무)"),
    "    " + uc("u09", "UC-09", "다른 안 고르기<BR/>· 되돌리기"),
    "    " + uc("u10", "UC-10", "외부 변화 감시<BR/>(3분마다)"),
    "    " + uc("u11", "UC-11", "새벽 정기 점검<BR/>(03:00)"),
    "    " + uc("u12", "UC-12", "<B>일정 조율</B><BR/>(전부 통과할 때까지)", "core"),
    "    " + uc("u13", "UC-13", "바꾸기 전에 묻기", "ext"),
    "    " + uc("u14", "UC-14", "변경 알리기", "core"),
    "    " + uc("u15", "UC-15", "일정 알림 보내기<BR/>(하루 시작 · 출발 시각)"),
    "    " + uc("u16", "UC-16", "오류 알림 받기<BR/>· 운영 화면 보기"),
    "  }",
    # 오른쪽 — 지원 액터(외부 시스템 · 시간 · 운영자)
    "  { rank=max;",
    "    " + system("timer", "시간", stereo="시간", note="3분 · 03:00 · 알림 시각"),
    "    " + system("watch", "외부 데이터 6종", note="날씨 · 특보 · 예보 · 재난문자 · 교통 사건 2"),
    "    " + system("places", "장소 · 영업 정보", note="관광공사 · 카카오 · Google · 시간표"),
    "    " + system("discord", "디스코드", note="지금은 팀 시연 채널 하나"),
    "    " + person("operator", "운영자"),
    "  }",
    # 일반화: 여행자는 동행자가 하는 일(계획서 보기)을 다 하고 더 한다(자식 → 부모, 빈 삼각형은 부모 쪽)
    '  traveler -> companion [arrowhead=empty, arrowsize=1.3, penwidth=1.5, constraint=false];',
    # 연관(실선) — 주 액터. 왼쪽 줄에 둔다
    "  traveler -> u01; traveler -> u02; traveler -> u03; traveler -> u06; traveler -> u07; traveler -> u08; traveler -> u09;",
    "  companion -> u05;",
    "  aiapp -> u02; aiapp -> u05; aiapp -> u06; aiapp -> u07; aiapp -> u08; aiapp -> u09;",
    # 왼쪽 줄 위아래 순서(보이지 않는 선)
    '  u01 -> u02 -> u03 -> u06 -> u07 -> u08 -> u09 -> u05 -> u13 [style=invis, constraint=false];',
    # 포함 — 기본 → 공통. 일정 조율은 넷이 반드시 쓴다(재사용)
    '  u07 -> u12 [style=dashed, arrowhead=vee, xlabel="«include»", fontcolor="#2d5f48", color="#2d5f48"];',
    '  u08 -> u12 [style=dashed, arrowhead=vee, xlabel="«include»", fontcolor="#2d5f48", color="#2d5f48"];',
    # 오른쪽 줄(시간 · 외부 데이터가 시작) — 조율보다 오른쪽에 두려고 선을 거꾸로 적고 화살촉은 조율 쪽에
    '  u12 -> u10 [style=dashed, dir=back, arrowtail=vee, xlabel="«include»", fontcolor="#2d5f48", color="#2d5f48"];',
    '  u12 -> u11 [style=dashed, dir=back, arrowtail=vee, xlabel="«include»", fontcolor="#2d5f48", color="#2d5f48"];',
    '  u12 -> u14 [style=dashed, arrowhead=vee, xlabel="«include»", fontcolor="#2d5f48", color="#2d5f48"];',
    '  u12 -> u15 [style=invis]; u12 -> u16 [style=invis];',
    '  u16 -> u10 -> u11 -> u15 -> u14 [style=invis, constraint=false];',
    # 확장 — 추가 → 기본
    '  u02 -> u04 [style=dashed, dir=back, arrowtail=vee, label="«extend»", fontcolor="#8a5f1c", color="#c8913a"];',
    '  u13 -> u12 [style=dashed, arrowhead=vee, label="«extend»", fontcolor="#8a5f1c", color="#c8913a"];',
    # 연관 — 지원 액터(오른쪽)
    "  u10 -> timer; u11 -> timer; u15 -> timer;",
    "  u10 -> watch;",
    "  u11 -> places; u12 -> places;",
    "  u14 -> discord; u15 -> discord;",
    "  u16 -> operator;",
    "}",
]


def main() -> None:
    stick(OUT / "actor.png")
    dot_path = OUT / "usecase_v1.dot"
    dot_path.write_text("\n".join(LINES), encoding="utf-8")
    env = dict(os.environ)
    for fmt in ("svg", "png"):
        args = [DOT, f"-T{fmt}", f"-Gimagepath={OUT}", str(dot_path), "-o", str(OUT / f"usecase_v1.{fmt}")]
        if fmt == "png":
            args.insert(2, "-Gdpi=150")
        subprocess.run(args, check=True, cwd=OUT, env=env)
    print("ok →", OUT)


if __name__ == "__main__":
    main()
