# -*- coding: utf-8 -*-
"""guguroute 유스케이스 — 전부 한 장(그림 0~4 의 내용을 하나로). 경계 안을 묶음 4구역으로 나눠 선이 구역 안에서 흐르게 한다.

    python make_usecase_all.py   → ../uc_all.dot · .svg · .png

배치(왼 → 오): 주 액터 | 1 여행 준비 · 2 여행 중 요청 | 3 일정 조율 | 4 자동 관리 | 지원 액터
★cluster 는 두 단계까지(경계 → 구역). rank=same 은 쓰지 않는다(dot 16 이 cluster 와 함께 죽는다 — 메모리).
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DOT = r"C:\Program Files\Graphviz\bin\dot.exe"
FONT = "Malgun Gothic"
G1, GOLD, BLUE = "#2d5f48", "#c8913a", "#2f6c9a"
L = []


def w(x):
    L.append(x)


def person(key, name, sub=""):
    s = f'<TR><TD><FONT POINT-SIZE="10" COLOR="#5f6b64">{sub}</FONT></TD></TR>' if sub else ""
    return (f'{key} [shape=none, margin=0, label=<<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="2">'
            f'<TR><TD><IMG SRC="actor.png"/></TD></TR><TR><TD><B>{name}</B></TD></TR>{s}</TABLE>>];')


def system(key, name, note="", stereo="시스템"):
    sub = f'<BR/><FONT POINT-SIZE="11" COLOR="#5f6b64">{note}</FONT>' if note else ""
    return (f'{key} [shape=box, style="rounded,filled", fillcolor="#f6ead4", color="{GOLD}", penwidth=1.6, '
            f'label=<<FONT POINT-SIZE="11" COLOR="#8a5f1c">«{stereo}»</FONT><BR/><B>{name}</B>{sub}>];')


def uc(key, name, code="", kind="", note=""):
    fill, line = {"": ("#fffdf7", "#7f8f86"), "core": ("#e5efe8", G1), "ext": ("#fbf4e6", GOLD),
                  "sub": ("#f3f6f1", "#9fb0a6")}[kind]
    top = f'<FONT POINT-SIZE="10" COLOR="#7d867f">{code}</FONT><BR/>' if code else ""
    bot = f'<BR/><FONT POINT-SIZE="10" COLOR="#5f6b64">{note}</FONT>' if note else ""
    return (f'{key} [shape=ellipse, style=filled, fillcolor="{fill}", color="{line}", penwidth=1.5, margin="0.10,0.03", '
            f'label=<{top}{name}{bot}>];')


def inc(base, add, back=False):
    if back:
        w(f'{add} -> {base} [style=dashed, dir=back, arrowtail=vee, label="«include»", fontcolor="{G1}", color="{G1}"];')
    else:
        w(f'{base} -> {add} [style=dashed, arrowhead=vee, label="«include»", fontcolor="{G1}", color="{G1}"];')


def ext(extension, base):
    w(f'{base} -> {extension} [style=dashed, dir=back, arrowtail=vee, label="«extend»", fontcolor="#8a5f1c", color="{GOLD}"];')


def gen(parent, child):
    w(f'{parent} -> {child} [dir=back, arrowtail=empty, arrowsize=1.2, penwidth=1.4];')


def cluster(key, title, color, nodes):
    w(f'  subgraph cluster_{key} {{ label=<<B>{title}</B>>; fontsize=15; style="rounded,dashed"; color="{color}"; penwidth=1.6; margin=14; fontcolor="{color}";')
    for n in nodes:
        w("    " + n)
    w("  }")


w("digraph UC {")
w(f'  graph [rankdir=LR, splines=spline, nodesep=0.28, ranksep=0.75, pad=0.4, fontname="{FONT}", bgcolor="#ffffff", newrank=false,'
  f'         label=<<B>guguroute 유스케이스 — 전체 한 장</B><BR/><FONT POINT-SIZE="13" COLOR="#5f6b64">v2 · 2026-10-02 · 실제 API · 코드 기준 · 구역별 세부는 그림 1~4</FONT>>, labelloc=t, fontsize=22];')
w(f'  node [fontname="{FONT}", fontsize=12];')
w(f'  edge [fontname="{FONT}", fontsize=10, color="#5f6b64", penwidth=1.3, arrowhead=none, arrowsize=0.8];')
# 주 액터
w("  " + person("traveler", "여행자"))
w("  " + person("companion", "동행자"))
w("  " + system("aiapp", "개인 AI 비서 앱", "우리 API로 연결"))
w("  " + person("req", "요청하는 쪽", "여행자 · AI 비서 앱"))
# 경계
w(f'  subgraph cluster_sys {{ label=<<B>guguroute</B>>; fontsize=18; style="rounded"; color="{G1}"; penwidth=2.4; margin=20;')
cluster("prep", "1 여행 준비", G1, [
    uc("u01", "여행 시작하기", "UC-01", note="언어 · 설문 6문항"),
    uc("u02", "계획 올리기", "UC-02", note="글 · 사진 · 파일 5개 · 10MB"),
    uc("u04", "일정 짜 달라고 하기", "UC-04", "ext"),
    uc("u03", "읽힌 일정 확인 · 고치기", "UC-03"),
    uc("s", "여행 등록 · 계획서 링크", "", "sub"),
    uc("u05", "여행계획서 보기", "UC-05", note="로그인 없는 링크 · 늘 최신"),
    uc("r", "<B>계획 읽기</B>", "", "core", note="값 · 방법 · 근거(원문 줄)"),
    uc("r1", "정해진 모양 읽기", "", "sub", note="코드: 시각 · 일차 · 예약번호"),
    uc("r2", "원문 위치 가리키기", "", "sub", note="AI: 남은 줄만"),
    uc("r3", "장소 하나로 정하기", "", "sub", note="표 → 별칭 → 오타 → 외부"),
    uc("r0", "사진 받아쓰기", "", "ext", note="한 줄씩 · 두 번 대조"),
])
cluster("req", "2 여행 중 요청", G1, [
    uc("u06", "채팅으로 묻기", "UC-06"),
    uc("u07", "바꿔 달라고 하기", "UC-07"),
    uc("u08", "문제 알리기", "UC-08", note="늦음 · 휴무"),
    uc("u09", "다른 안 고르기 · 되돌리기", "UC-09"),
    uc("q", "<B>요청 읽기</B>", "", "core", note="요청 종류 · 대상 항목"),
    uc("g", "근거 찾기", "", "sub", note="규정 · 예약 취소 조건"),
    uc("v", "새 판 저장", "", "sub", note="기준 판이 그대로일 때만"),
])
cluster("coord", "3 일정 조율 — 전부 통과할 때까지", GOLD, [
    uc("c", "<B>일정 조율</B>", "UC-12", "core"),
    uc("a1", "영향받는 항목 추리기", "", "sub", note="바로 다음 · 오늘 · 이후"),
    uc("a2", "<B>담당 에이전트 점검</B>", "", "core", note="액티비티 → 요식 → 이동"),
    uc("x1", "액티비티 점검", "", "sub", note="운영 · 날씨 · 대기질"),
    uc("x2", "요식 점검", "", "sub", note="영업 · 브레이크 · 라스트오더"),
    uc("x3", "이동 재판정", "", "sub", note="시간표로 앞뒤 제시간?"),
    uc("e1", "다음 후보로 다시", "", "ext", note="통과 못 함 · 후보 남음"),
    uc("a3", "적용", "", "sub", note="근거 대조 → 새 판 1번"),
    uc("e2", "바꾸기 전에 묻기", "UC-13", "ext", note="먼저 물어봐 · 고정 · 안전 경보"),
    uc("e3", "못 맞춤 알리기", "", "ext", note="후보 소진 · 조건 푼 안"),
    uc("a4", "변경 알리기", "UC-14", "core", note="알림 1번 · 계획서 새 판"),
])
cluster("auto", "4 자동 관리", BLUE, [
    uc("u10", "외부 변화 감시", "UC-10", note="3분마다"),
    uc("w1", "소스 수집", "", "sub", note="소스마다 한 번"),
    uc("w3", "대체 소스로 다시 읽기", "", "ext", note="1차 실패 시"),
    uc("w2", "바뀐 값에 걸린 항목 고르기", "", "sub", note="변화 없으면 사건 0"),
    uc("u11", "새벽 정기 점검", "UC-11", note="03:00~08:00"),
    uc("o1", "영업시간 조회", "", "sub"),
    uc("u15", "일정 알림 보내기", "UC-15", note="하루 시작 · 다음 · 출발"),
    uc("n1", "출발 시각 계산", "", "sub", note="시작 − 이동 − 여유"),
    uc("n2", "문구틀 번역", "", "sub", note="언어마다 처음 한 번"),
    uc("n3", "알림 배달", "", "sub", note="3번까지 다시 · 중복 0"),
    uc("u16", "오류 알림 받기", "UC-16", note="상시 작업 연속 실패"),
])
w("  }")
# 지원 액터
for x in (system("timer", "시간", "3분 · 03:00 · 알림 시각 · 1분", stereo="시간"),
          system("watch", "외부 데이터 6종", "날씨 · 특보 · 예보 · 재난문자 · 교통 2"),
          system("info", "장소 · 영업 · 교통 정보", "관광공사 · 카카오 · Google · 시간표"),
          system("ai", "AI 모델", "시험 중 — 로컬 · API 비교"),
          system("discord", "디스코드", "지금은 팀 시연 채널 하나"),
          person("operator", "운영자", "오류 알림만")):
    w("  " + x)

# ── 연관(주 액터) ──
w('  traveler -> companion [arrowhead=empty, arrowsize=1.2, penwidth=1.4, constraint=false];')
w('  traveler -> req [arrowhead=empty, arrowsize=1.2, penwidth=1.4, constraint=false];')
w('  aiapp -> req [arrowhead=empty, arrowsize=1.2, penwidth=1.4, constraint=false];')
for a, b in (("traveler", "u01"), ("traveler", "u02"), ("traveler", "u03"), ("aiapp", "u02"), ("companion", "u05"),
             ("req", "u06"), ("req", "u07"), ("req", "u08"), ("req", "u09")):
    w(f"  {a} -> {b};")
# ── 1 여행 준비 ──
ext("u04", "u02"); inc("u02", "r"); inc("r", "r1"); inc("r", "r2"); inc("r", "r3"); ext("r0", "r"); inc("u03", "s")
# ── 2 여행 중 요청 ──
inc("u06", "q"); inc("u06", "g"); inc("u07", "q"); inc("u08", "q"); inc("u09", "v")
# ── 3 일정 조율 ── (2 · 4 가 부른다)
inc("u07", "c"); inc("u08", "c")
inc("c", "a4"); inc("c", "a3"); inc("c", "a2"); inc("c", "a1")
gen("a2", "x1"); gen("a2", "x2"); gen("a2", "x3")
ext("e1", "a2"); ext("e2", "a3"); ext("e3", "c")
# ── 4 자동 관리 ── 조율보다 오른쪽: 조율 → 감시 쪽으로 적고 화살촉은 조율 쪽
w(f'  c -> u10 [style=dashed, dir=back, arrowtail=vee, label="«include»", fontcolor="{G1}", color="{G1}"];')
w(f'  c -> u11 [style=dashed, dir=back, arrowtail=vee, label="«include»", fontcolor="{G1}", color="{G1}"];')
w('  c -> u15 [style=invis]; c -> u16 [style=invis];')
inc("u10", "w1"); inc("u10", "w2"); ext("w3", "w1"); inc("u11", "o1"); inc("u15", "n1"); inc("u15", "n2"); inc("u15", "n3")
# ── 지원 액터 연관 ──
for a, b in (("u10", "timer"), ("u11", "timer"), ("u15", "timer"), ("u16", "timer"),
             ("w1", "watch"), ("w3", "watch"),
             ("r3", "info"), ("x1", "info"), ("x2", "info"), ("x3", "info"), ("o1", "info"),
             ("r2", "ai"), ("r0", "ai"), ("q", "ai"), ("g", "ai"), ("n2", "ai"),
             ("a4", "discord"), ("n3", "discord"), ("u16", "operator")):
    w(f"  {a} -> {b};")
w("}")

p = OUT / "uc_all.dot"
p.write_text("\n".join(L), encoding="utf-8")
for fmt in ("svg", "png"):
    args = [DOT, f"-T{fmt}", f"-Gimagepath={OUT}", str(p), "-o", str(OUT / f"uc_all.{fmt}")]
    if fmt == "png":
        args.insert(2, "-Gdpi=120")
    subprocess.run(args, check=True, cwd=OUT)
print("ok →", OUT / "uc_all.png")
