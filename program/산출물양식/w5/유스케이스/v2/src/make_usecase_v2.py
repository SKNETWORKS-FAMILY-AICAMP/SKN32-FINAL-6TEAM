# -*- coding: utf-8 -*-
"""triPilot 유스케이스 v2 — 한 장에 다 넣지 않고 다섯 장으로 나눈다(선 겹침을 줄이고 세부 처리 구조를 보인다).

    python make_usecase_v2.py   → ../uc0_overview.* · uc1_prepare.* · uc2_request.* · uc3_coordinate.* · uc4_auto.*

  0 개요        액터 ↔ 묶음 4개
  1 여행 준비    계획 올리기 → 계획 읽기(규칙 · AI 위치 · 장소 정하기 · 사진 받아쓰기)
  2 여행 중 요청 요청 읽기(분류) → 일정 조율 / 근거 찾기 / 새 판 저장
  3 일정 조율    영향 항목 → 담당 에이전트 점검(액티비티 · 요식 · 이동) → 적용(근거 대조 · 새 판) → 변경 알리기
  4 자동 관리    감시(3분 · 대체 소스) · 새벽 점검 · 일정 알림 · 오류 알림

표기(교재 유스케이스 장): 실선 = 연관 · 점선 «include»(기본 → 공통) · 점선 «extend»(추가 → 기본) · 빈 삼각형 = 일반화.
★고객 건을 사람에게 넘기는 유스케이스는 없다(사용자 결정 2026-09-28). 운영자는 오류 알림만 받는다.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
DOT = r"C:\Program Files\Graphviz\bin\dot.exe"
FONT = "Malgun Gothic"
G1, GOLD, BLUE = "#2d5f48", "#c8913a", "#2f6c9a"


def stick(path: Path) -> None:
    k, color = 4, (29, 42, 35)
    w, h = 44 * k, 70 * k
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw, cx = 3 * k, w // 2
    d.ellipse((cx - 9 * k, 3 * k, cx + 9 * k, 21 * k), outline=color, width=lw)
    d.line((cx, 21 * k, cx, 46 * k), fill=color, width=lw)
    d.line((cx - 16 * k, 30 * k, cx + 16 * k, 30 * k), fill=color, width=lw)
    d.line((cx, 46 * k, cx - 13 * k, 66 * k), fill=color, width=lw)
    d.line((cx, 46 * k, cx + 13 * k, 66 * k), fill=color, width=lw)
    im.resize((44, 70), Image.LANCZOS).save(path)


class D:
    """다이어그램 하나. 왼쪽 액터 → 경계(유스케이스) → 오른쪽 액터 순으로 rank 가 흐르게 선을 적는다."""

    def __init__(self, name, title, sub):
        self.name, self.L, self.R, self.U, self.E = name, [], [], [], []
        self.head = [
            "digraph UC {",
            f'  graph [rankdir=LR, splines=spline, nodesep=0.42, ranksep=0.9, pad=0.35, fontname="{FONT}", bgcolor="#ffffff",'
            f'         label=<<B>{title}</B><BR/><FONT POINT-SIZE="12" COLOR="#5f6b64">{sub}</FONT>>, labelloc=t, fontsize=19, ordering=out];',
            f'  node [fontname="{FONT}", fontsize=13];',
            f'  edge [fontname="{FONT}", fontsize=11, color="#5f6b64", penwidth=1.4, arrowhead=none, arrowsize=0.9];',
        ]

    def person(self, key, name, side="L"):
        (self.L if side == "L" else self.R).append(
            f'{key} [shape=none, margin=0, label=<<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="2">'
            f'<TR><TD><IMG SRC="actor.png"/></TD></TR><TR><TD><B>{name}</B></TD></TR></TABLE>>];')

    def system(self, key, name, note="", stereo="시스템", side="R"):
        sub = f'<BR/><FONT POINT-SIZE="11" COLOR="#5f6b64">{note}</FONT>' if note else ""
        (self.L if side == "L" else self.R).append(
            f'{key} [shape=box, style="rounded,filled", fillcolor="#f6ead4", color="{GOLD}", penwidth=1.6, '
            f'label=<<FONT POINT-SIZE="11" COLOR="#8a5f1c">«{stereo}»</FONT><BR/><B>{name}</B>{sub}>];')

    def uc(self, key, name, code="", kind="", note=""):
        fill, line = {"": ("#fffdf7", "#7f8f86"), "core": ("#e5efe8", G1), "ext": ("#fbf4e6", GOLD),
                      "sub": ("#f3f6f1", "#9fb0a6"), "ghost": ("#f4f4f0", "#b9c2bc")}[kind]
        top = f'<FONT POINT-SIZE="10" COLOR="#7d867f">{code}</FONT><BR/>' if code else ""
        bot = f'<BR/><FONT POINT-SIZE="10" COLOR="#5f6b64">{note}</FONT>' if note else ""
        style = "filled,dashed" if kind == "ghost" else "filled"
        self.U.append(f'{key} [shape=ellipse, style="{style}", fillcolor="{fill}", color="{line}", penwidth=1.6, margin="0.12,0.04", '
                      f'label=<{top}{name}{bot}>];')

    def pkg(self, key, name, items, color=G1):
        rows = "".join(f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="11">{i}</FONT></TD></TR>' for i in items)
        self.U.append(f'{key} [shape=tab, style=filled, fillcolor="#fffdf7", color="{color}", penwidth=1.8, '
                      f'label=<<TABLE BORDER="0" CELLPADDING="2"><TR><TD><B>{name}</B></TD></TR>{rows}</TABLE>>];')

    def assoc(self, a, b):
        self.E.append(f"{a} -> {b};")

    def inc(self, base, add, back=False):
        if back:   # add 를 base 보다 왼쪽에 두고 싶을 때
            self.E.append(f'{add} -> {base} [style=dashed, dir=back, arrowtail=vee, label="«include»", fontcolor="{G1}", color="{G1}"];')
        else:
            self.E.append(f'{base} -> {add} [style=dashed, arrowhead=vee, label="«include»", fontcolor="{G1}", color="{G1}"];')

    def ext(self, extension, base):
        # 확장 쪽을 기본보다 오른쪽에 두려고 base -> extension 으로 적고 화살촉은 base 쪽에
        self.E.append(f'{base} -> {extension} [style=dashed, dir=back, arrowtail=vee, label="«extend»", fontcolor="#8a5f1c", color="{GOLD}"];')

    def gen(self, parent, child):
        # 자식(오른쪽) → 부모, 빈 삼각형은 부모 쪽
        self.E.append(f'{parent} -> {child} [dir=back, arrowtail=empty, arrowsize=1.3, penwidth=1.5];')

    def raw(self, line):
        self.E.append(line)

    def render(self):
        body = (self.head + ["  { rank=min; " + " ".join(self.L) + " }" if self.L else ""]
                + [f'  subgraph cluster_sys {{ label=<<B>triPilot</B>>; fontsize=16; style="rounded"; color="{G1}"; penwidth=2.2; margin=20;']
                + ["    " + u for u in self.U] + ["  }"]
                + (["  { rank=max; " + " ".join(self.R) + " }"] if self.R else [])
                + ["  " + e for e in self.E] + ["}"])
        p = OUT / f"{self.name}.dot"
        p.write_text("\n".join(body), encoding="utf-8")
        for fmt in ("svg", "png"):
            args = [DOT, f"-T{fmt}", f"-Gimagepath={OUT}", str(p), "-o", str(OUT / f"{self.name}.{fmt}")]
            if fmt == "png":
                args.insert(2, "-Gdpi=144")
            subprocess.run(args, check=True, cwd=OUT)


def overview():
    d = D("uc0_overview", "그림 0 · 전체 개요 — 무엇이 어디로 이어지나", "액터와 유스케이스 묶음 4개 · 묶음 안은 그림 1~4")
    d.person("traveler", "여행자"); d.person("companion", "동행자")
    d.system("aiapp", "개인 AI 비서 앱", "우리 API로 연결", side="L"); d.system("timer", "시간", "3분 · 03:00 · 알림 시각", stereo="시간")
    d.pkg("p1", "1 여행 준비", ["UC-01 여행 시작하기(설문)", "UC-02 계획 올리기", "UC-03 읽힌 일정 확인 · 고치기", "UC-04 일정 짜 달라고 하기", "UC-05 여행계획서 보기"])
    d.pkg("p2", "2 여행 중 요청", ["UC-06 채팅으로 묻기", "UC-07 바꿔 달라고 하기", "UC-08 문제 알리기", "UC-09 다른 안 고르기 · 되돌리기"])
    d.pkg("p4", "4 자동 관리", ["UC-10 외부 변화 감시(3분)", "UC-11 새벽 정기 점검(03:00)", "UC-15 일정 알림 보내기", "UC-16 오류 알림"], color=BLUE)
    d.pkg("p3", "3 일정 조율", ["UC-12 일정 조율(전부 통과할 때까지)", "UC-13 바꾸기 전에 묻기", "UC-14 변경 알리기"], color=GOLD)
    d.system("info", "장소 · 영업 · 교통 정보", "관광공사 · 카카오 · Google · 시간표"); d.system("watch", "외부 데이터 6종", "날씨 · 특보 · 예보 · 재난문자 · 교통 2")
    d.system("discord", "디스코드", "지금은 팀 시연 채널 하나")
    d.person("operator", "운영자", side="R")
    d.gen("companion", "traveler") if False else d.raw('traveler -> companion [arrowhead=empty, arrowsize=1.3, penwidth=1.5, constraint=false];')
    d.assoc("traveler", "p1"); d.assoc("traveler", "p2"); d.assoc("companion", "p1"); d.assoc("aiapp", "p1"); d.assoc("aiapp", "p2"); d.assoc("p4", "timer")
    d.inc("p2", "p3"); d.inc("p3", "p4", back=False) if False else d.raw(f'p3 -> p4 [style=invis];')
    d.raw(f'p4 -> p3 [style=dashed, arrowhead=vee, constraint=false, label="«include»", fontcolor="{G1}", color="{G1}"];')
    d.assoc("p3", "info"); d.assoc("p3", "discord"); d.assoc("p4", "watch"); d.assoc("p4", "operator")
    d.raw('p1 -> p2 [style=invis];')
    d.render()


def prepare():
    d = D("uc1_prepare", "그림 1 · 여행 준비 — 계획을 받아 일정으로 읽는다", "계획 읽기는 에이전트가 아니라 매니저(코어)의 처리 단계")
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
    d.ext("u04", "u02")
    d.inc("u02", "r"); d.inc("r", "r1"); d.inc("r", "r2"); d.inc("r", "r3"); d.ext("r0", "r")
    d.inc("u03", "s")
    d.assoc("r2", "ai"); d.assoc("r0", "ai"); d.assoc("r3", "place")
    d.raw("u01 -> u02 -> u03 -> u05 [style=invis, constraint=false];")
    d.render()


def request():
    d = D("uc2_request", "그림 2 · 여행 중 요청 — 요청을 읽고, 묻는 말엔 근거로 답하고, 바꿀 일은 조율로", "채팅 · API로 들어온 말은 먼저 요청 종류와 대상 항목으로 읽는다")
    d.person("traveler", "여행자"); d.system("aiapp", "개인 AI 비서 앱", "우리 API로 연결", side="L")
    d.raw('req [shape=none, margin=0, label=<<TABLE BORDER="0" CELLPADDING="0" CELLSPACING="2"><TR><TD><IMG SRC="actor.png"/></TD></TR><TR><TD><B>요청하는 쪽</B></TD></TR><TR><TD><FONT POINT-SIZE="10" COLOR="#5f6b64">여행자 · AI 비서 앱</FONT></TD></TR></TABLE>>];')
    d.uc("u06", "채팅으로 묻기", "UC-06", note="하루 요약 · 다음 이동 · 규정")
    d.uc("u07", "바꿔 달라고 하기", "UC-07", note="바로 바꾸고 다른 안 셋까지")
    d.uc("u08", "문제 알리기", "UC-08", note="늦음 · 휴무")
    d.uc("u09", "다른 안 고르기 · 되돌리기", "UC-09", note="「선택이 필요해요」 · 앞 판으로")
    d.uc("q", "<B>요청 읽기</B>", "", "core", note="요청 종류 5 · 대상 항목 · 문제 코드")
    d.uc("g", "근거 찾기", "", "sub", note="여행 규정 · 예약 취소 조건")
    d.uc("c", "<B>일정 조율</B>", "UC-12", "core", note="→ 그림 3")
    d.uc("v", "새 판 저장", "", "sub", note="기준 판이 그대로일 때만")
    d.system("ai", "AI 모델", "시험 중 — 로컬 · API 비교")
    d.raw('traveler -> req [arrowhead=empty, arrowsize=1.3, penwidth=1.5];'); d.raw('aiapp -> req [arrowhead=empty, arrowsize=1.3, penwidth=1.5];')
    d.assoc("req", "u06"); d.assoc("req", "u07"); d.assoc("req", "u08"); d.assoc("req", "u09")
    d.inc("u06", "q"); d.inc("u06", "g"); d.inc("u07", "c"); d.inc("u07", "q"); d.inc("u08", "c"); d.inc("u08", "q"); d.inc("u09", "v")
    d.assoc("q", "ai"); d.assoc("g", "ai")
    d.raw("u06 -> u07 -> u08 -> u09 [style=invis, constraint=false];")
    d.render()


def coordinate():
    d = D("uc3_coordinate", "그림 3 · 일정 조율 — 전부 통과할 때까지 다시 맞춘다", "네 유스케이스가 반드시 부른다 · 바꾸는 것은 코어, 에이전트는 점검과 제안만")
    d.uc("k07", "바꿔 달라고 하기", "UC-07", "ghost"); d.uc("k08", "문제 알리기", "UC-08", "ghost")
    d.uc("k10", "외부 변화 감시", "UC-10", "ghost"); d.uc("k11", "새벽 정기 점검", "UC-11", "ghost")
    d.uc("c", "<B>일정 조율</B>", "UC-12", "core")
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
    d.system("info", "장소 · 영업 · 교통 정보", "관광공사 · 카카오 · Google · 시간표"); d.system("discord", "디스코드", "지금은 팀 시연 채널 하나")
    for k in ("k07", "k08", "k10", "k11"):
        d.raw(f'{k} -> c [style=dashed, arrowhead=vee, label="«include»", fontcolor="{G1}", color="{G1}"];')
    d.inc("c", "a4"); d.inc("c", "a3"); d.inc("c", "a2"); d.inc("c", "a1")
    d.gen("a2", "x1"); d.gen("a2", "x2"); d.gen("a2", "x3")
    d.ext("e1", "a2"); d.ext("e2", "a3"); d.ext("e3", "c")
    d.assoc("x1", "info"); d.assoc("x2", "info"); d.assoc("x3", "info"); d.assoc("a4", "discord")
    d.raw("a1 -> a2 -> a3 -> a4 [style=invis, constraint=false];")
    d.render()


def auto():
    d = D("uc4_auto", "그림 4 · 자동 관리 — 시간이 깨워 여행 끝까지 돈다", "감시 · 점검은 조율을 부르고, 알림은 일정에 맞춰 나간다 · 사람은 오류 알림만")
    d.system("timer", "시간", "3분 · 03:00 · 알림 시각 · 1분", stereo="시간", side="L")
    d.uc("u10", "외부 변화 감시", "UC-10", note="3분마다")
    d.uc("u11", "새벽 정기 점검", "UC-11", note="03:00~08:00 · 항목 · 날짜마다 한 번")
    d.uc("u15", "일정 알림 보내기", "UC-15", note="하루 시작 · 다음 일정 · 출발")
    d.uc("u16", "오류 알림 받기", "UC-16", note="상시 작업이 연속 실패할 때")
    d.uc("w1", "소스 수집", "", "sub", note="소스마다 한 번 · 값 · 지문")
    d.uc("w2", "바뀐 값에 걸린 항목 고르기", "", "sub", note="변화 없으면 사건 0 · 알림 0")
    d.uc("w3", "대체 소스로 다시 읽기", "", "ext", note="1차 실패 시 · 대체도 실패면 오류")
    d.uc("o1", "영업시간 조회", "", "sub", note="계획한 시각에 여나")
    d.uc("c", "<B>일정 조율</B>", "UC-12", "core", note="→ 그림 3")
    d.uc("n1", "출발 시각 계산", "", "sub", note="다음 시작 − 이동 − 여유")
    d.uc("n2", "문구틀 번역", "", "sub", note="언어마다 처음 한 번 · 값은 원값")
    d.uc("n3", "알림 배달", "", "sub", note="3번까지 다시 · 중복 0")
    d.system("watch", "외부 데이터 6종", "날씨 · 특보 · 예보 · 재난문자 · 교통 2"); d.system("google", "장소 · 영업 정보", "Google(새벽만)")
    d.system("ai", "AI 모델", "시험 중"); d.system("discord", "디스코드", "지금은 팀 시연 채널 하나"); d.person("operator", "운영자", side="R")
    d.assoc("timer", "u10"); d.assoc("timer", "u11"); d.assoc("timer", "u15"); d.assoc("timer", "u16")
    d.inc("u10", "w1"); d.inc("u10", "w2"); d.ext("w3", "w1"); d.inc("u10", "c"); d.inc("u11", "o1"); d.inc("u11", "c")
    d.inc("u15", "n1"); d.inc("u15", "n2"); d.inc("u15", "n3")
    d.assoc("w1", "watch"); d.assoc("w3", "watch"); d.assoc("o1", "google"); d.assoc("n2", "ai"); d.assoc("n3", "discord"); d.assoc("u16", "operator")
    d.raw("u10 -> u11 -> u15 -> u16 [style=invis, constraint=false];")
    d.render()


if __name__ == "__main__":
    stick(OUT / "actor.png")
    for f in (overview, prepare, request, coordinate, auto):
        f()
    print("ok →", OUT)
