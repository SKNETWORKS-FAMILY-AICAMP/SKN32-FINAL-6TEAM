# -*- coding: utf-8 -*-
"""guguroute Multi-Agent 구조도 v9 — md(v8→v9) 내용 · 순서를 그대로 둔 「그림」판 (2026-10-02)

    python make_visual_v9.py   → ../triPilot_Multi-Agent구조도_v9.html · .png
                                  ../그림1_전체구조도_v9.svg · .png · ../그림2_툴데이터계층_v9.svg · .png

★md 와 같은 순서: 요약 문단 → 전체 구조도 → Agent 와 Tool/Data 계층 → I/O 요약표 → 순환 문장 → 지금 상태.
★글자 그림이 아니라 상자 · 화살표 그림(SVG). 상자 안에 I / O 를 적는다(참고 md 형식).
★두 루프를 굵은 금색 선으로: 안쪽(다음 후보) · 바깥(여행 끝? → 트리거). 결과 합류선은 왼쪽, 바깥 루프는 오른쪽.
★사실은 코드 확인(2026-10-02) + 코덱스 대조 — 자세한 근거는 같은 폴더 코덱스_검토결과_v8.md.
"""
import html as _h
import shutil
import subprocess
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SANS = "'Noto Sans KR','Malgun Gothic',sans-serif"
MONO = "'Cascadia Mono','Consolas',monospace"
S = []


def esc(t):
    return _h.escape(t, quote=False)


def T(x, y, s, cls="", a="start"):
    c = f' class="{cls}"' if cls else ""
    S.append(f'<text{c} x="{x}" y="{y}" text-anchor="{a}">{esc(s)}</text>')


def R(x, y, w, h, cls, rx=0):
    """md 글자 그림 느낌 — 모서리는 각지게"""
    S.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}"/>')


def P(pts, cls="e", mk="a"):
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    m = f' marker-end="url(#{mk})"' if mk else ""
    S.append(f'<path class="{cls}" d="{d}"{m}/>')


def diamond(cx, cy, w, h, t):
    """md 의 「┌ 전부 통과 ? ┐」 처럼 분기도 상자로 — 이음점은 마름모와 같게(위 · 아래 · 좌우 끝)"""
    S.append(f'<rect class="dia" x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}"/>')
    T(cx, cy + 5, t.replace("?", " ?"), "h3", "middle")


def tag(x, y, kind):
    t = {"done": "(구현)", "wip": "(진행 중)", "plan": "(예정)", "look": "(검토 중)"}[kind]
    T(x, y + 15, t, "tg-" + kind)   # 상자 안 오른쪽 위
    return len(t) * 13 + 6


def iobox(x, y, w, title, ins, outs, cls="b", sub=None, status=None, h=None):
    """참고 md 형식 — 제목(가운데) + I: · O: 줄"""
    n = len(ins) + len(outs)
    h = h or (46 + (20 if sub else 0) + n * 20 + 12)
    R(x, y, w, h, cls)
    T(x + w / 2, y + 26, title, "h2", "middle")
    yy = y + 26
    if sub:
        yy += 20
        T(x + w / 2, yy, sub, "sub", "middle")
    yy += 26
    for k, rows in (("I", ins), ("O", outs)):
        for i, s in enumerate(rows):
            if i == 0:
                T(x + 18, yy, k + ":", "k-" + k, "start")
            T(x + 42, yy, s, "v", "start")
            yy += 20
    if status:
        tag(x + w - 70, y + 2, status)
    return y + h


def down(x, y1, y2, cls="e", mk="a"):
    P([(x, y1), (x, y2 - 2)], cls, mk)


DEFS = ('<defs>' + "".join(
    f'<marker id="{i}" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto-start-reverse"><path fill="{c}" d="M0 0 L10 5 L0 10 Z"/></marker>'
    for i, c in (("a", "#1f2328"), ("g", "#1f2328"), ("r", "#6e7681"), ("t", "#1f2328"))) + '</defs>')

MD = "'D2Coding','NanumGothicCoding','Nanum Gothic Coding','Cascadia Mono','Consolas','Malgun Gothic',monospace"
CSS = f"""
.fig text{{font-family:{MD};fill:#1f2328}}
.fig .h2{{font-size:16px;font-weight:700}} .fig .h3{{font-size:14px;font-weight:700}} .fig .sub{{font-size:13px;fill:#57606a}}
.fig .v{{font-size:13.5px}} .fig .s{{font-size:12.8px;fill:#24292f}} .fig .k-I,.fig .k-O{{font-size:13.5px;font-weight:700;fill:#1f2328}}
.fig .lbl{{font-size:12.5px;fill:#57606a}} .fig .lg{{font-size:13px;font-weight:700;fill:#1f2328}} .fig .lr{{font-size:12.5px;fill:#6e7681}}
.fig .ft{{font-size:15px;font-weight:700;fill:#1f2328}} .fig .mono{{font-size:13px;font-weight:700}}
.fig .tg-done,.fig .tg-wip,.fig .tg-plan,.fig .tg-look{{font-size:11.5px;fill:#6e7681}}
.fig rect{{fill:#fff;stroke:#1f2328;stroke-width:1.2}}
.fig .frame-a,.fig .frame-w{{fill:#fff;stroke:#1f2328;stroke-width:1.2}} .fig .frame-w{{stroke-dasharray:none}}
.fig .b-fail,.fig .b-plan{{stroke-dasharray:5 4;stroke:#57606a}}
.fig .e{{fill:none;stroke:#1f2328;stroke-width:1.2}} .fig .loop{{fill:none;stroke:#1f2328;stroke-width:2.6}}
.fig .bus{{fill:none;stroke:#1f2328;stroke-width:1.2;stroke-dasharray:6 4}} .fig .bad{{fill:none;stroke:#6e7681;stroke-width:1.2;stroke-dasharray:5 4}}
.fig .tl{{fill:none;stroke:#1f2328;stroke-width:1.2;stroke-dasharray:6 4}}
"""


# ───────────── 그림 1 · 전체 구조도 ─────────────
MX, MW = 150, 700          # 가운데 기둥(주 경로)
RX, RW = 900, 300          # 오른쪽 기둥(에이전트를 거치지 않는 경로)
LOOP, BUS = 1245, 85       # 바깥 루프 선 · 결과 합류 선
CX = MX + MW // 2


def fig1():
    S.clear()
    W = 1290
    T(40, 34, "그림 1 · Multi-Agent 전체 구조도", "ft")
    T(40, 56, "I = 받는 것 · O = 내보내는 것 · 굵은 선 = 되돌아가는 루프 · 점선 = 결과 합류 · 회색 점선 = 실패 · (구현) (진행 중) (예정) = 코드 상태", "s")

    y = 80
    y = iobox(MX, y, MW, "여행자 / 모바일 웹앱 (자체 채팅)",
              ["여행 계획(글 · 사진 · 파일), 채팅 질문 · 신고, 다른 안 선택 · 되돌리기"],
              ["판정을 통과한 일정, 바뀐 일정 + 이유 · 다른 안, Discord 알림 · 계획서 링크"], "b-user")
    down(CX, y, y + 34); y += 34
    y = iobox(MX, y, MW, "FastAPI 서버 (REST API)",
              ["HTTP 요청 + 브라우저 키 (로그인은 예정)"],
              ["고객 확인, 여행 ID, JSON 응답, 진행 · 변경 신호(SSE)"], "b-api", sub="같은 서버 안에서 아래 처리 코드를 부른다")
    down(CX, y, y + 34); y += 34

    # ── 1. 계획 읽기 · 확인 · 등록 (틀)
    fy = y
    R(MX - 10, fy, RX + RW - MX + 10, 336, "frame-a", 14)
    T(MX + 8, fy + 28, "1. 계획 읽기 · 확인 · 등록", "h2")
    T(MX + 300, fy + 28, "계획을 올릴 때 — 고객이 고치면 다시 확인", "sub")
    r = fy + 46
    R(MX + 10, r, 210, 92, "b"); T(MX + 115, r + 30, "계획 읽기", "h3", "middle")
    T(MX + 115, r + 52, "규칙이 먼저 · 남은 줄은 LLM", "s", "middle"); T(MX + 115, r + 70, "사진은 받아쓰기", "s", "middle"); tag(MX + 160, r + 1, "done")
    R(MX + 250, r, 180, 92, "b"); T(MX + 340, r + 30, "장소 확인", "h3", "middle")
    T(MX + 340, r + 52, "우리 표 → 별칭 →", "s", "middle"); T(MX + 340, r + 70, "카카오 · 관광공사", "s", "middle"); tag(MX + 370, r + 1, "done")
    R(MX + 460, r, 330, 92, "b-agent"); T(MX + 625, r + 26, "등록 판정 (코드)", "h3", "middle")
    T(MX + 625, r + 48, "시각 순서 · 겹침 · 이동 시간 · 결제 · 예산", "s", "middle")
    T(MX + 625, r + 66, "휴무 · 영업 · 브레이크 · 마감 (값이 있을 때만)", "s", "middle")
    T(MX + 625, r + 84, "외부 날씨는 여기서 안 봄 — 감시가 본다", "s", "middle"); tag(MX + 730, r + 1, "done")
    P([(MX + 220, r + 46), (MX + 248, r + 46)]); P([(MX + 430, r + 46), (MX + 458, r + 46)])
    R(MX + 820, r, 230, 92, "b"); T(MX + 935, r + 30, "일정 짜 줘 → 생성", "h3", "middle")
    T(MX + 935, r + 52, "후보는 우리 DB · AI는 순서 제안", "s", "middle"); T(MX + 935, r + 70, "코드로 배치 · 검사 · 수정", "s", "middle"); tag(MX + 990, r + 1, "done")
    P([(MX + 820, r + 46), (MX + 792, r + 46)])
    d = r + 150
    diamond(MX + 625, d, 190, 64, "위반 없음?")
    P([(MX + 625, r + 92), (MX + 625, d - 33)])
    R(MX + 820, d - 30, 230, 60, "b-core"); T(MX + 935, d - 6, "등록 + 계획서 링크", "h3", "middle"); T(MX + 935, d + 14, "로그인 없이 열림", "s", "middle")
    P([(MX + 720, d), (MX + 818, d)]); T(MX + 765, d - 8, "예", "lbl", "middle")
    R(MX + 160, d - 32, 300, 64, "b-fail"); T(MX + 310, d - 8, "이유 + 고칠 방법 표시", "h3", "middle"); T(MX + 310, d + 14, "필수값 부족 · 수행 불가면 거절", "s", "middle")
    tag(MX + 400, d - 31, "done")
    P([(MX + 530, d), (MX + 462, d)], "bad", "r"); T(MX + 496, d - 8, "아니오", "lr", "middle")
    P([(MX + 310, d - 32), (MX + 310, r + 105), (MX + 590, r + 105), (MX + 590, r + 94)], "loop", "g")
    T(MX + 160, d + 54, "↑ 고객이 고쳐서 다시 확인 (되돌림 루프)", "lg")
    T(MX + 20, fy + 306, "진행 상황 실시간 표시(SSE): 서버는 구현 · 웹 화면 연결은 진행 중", "s"); tag(MX + 610, fy + 291, "wip")
    T(MX + 20, fy + 326, "실패 항목을 채팅으로 대안 추천: 아직 없음 (멘토 요청)", "s"); tag(MX + 610, fy + 311, "plan")
    y = fy + 336
    P([(MX + 935, d + 30), (MX + 935, y + 26), (CX - 80, y + 26), (CX - 80, y + 64)])
    T(CX - 70, y + 50, "등록된 여행을 감시 작업이 1분마다 조회", "lbl")
    y += 66

    # ── 트리거 (바깥 루프가 돌아오는 곳)
    ty = y
    R(MX - 10, ty, RX + RW - MX + 10, 122, "b", 14)
    T(MX + 8, ty + 26, "트리거 — 다음 점검 대기", "h2")
    T(MX + 226, ty + 26, "← 바깥 루프가 여기로 돌아온다", "lg")
    R(MX + 10, ty + 40, 560, 70, "b-agent"); T(MX + 22, ty + 62, "낮 감시 · 1분마다", "h3")
    T(MX + 22, ty + 82, "I: 앞으로 90분 안 항목 + 외부 6범주 점검 결과", "s")
    T(MX + 22, ty + 100, "O: 문제 항목 + 원인 → Case 1건", "s"); tag(MX + 512, ty + 41, "done")
    R(RX, ty + 40, 145, 70, "b"); T(RX + 72, ty + 62, "새벽 영업 확인", "h3", "middle"); T(RX + 72, ty + 82, "03~08시 · Google", "s", "middle"); T(RX + 72, ty + 100, "그날 식사 · 활동", "s", "middle")
    R(RX + 155, ty + 40, 145, 70, "b"); T(RX + 227, ty + 62, "고객 채팅 · 신고", "h3", "middle"); T(RX + 227, ty + 82, "바꿔 줘 · 늦어요", "s", "middle"); T(RX + 227, ty + 100, "다른 안 · 되돌리기", "s", "middle")
    loop_y = ty + 60
    y = ty + 122
    P([(CX - 80, ty + 110), (CX - 80, y + 32)])
    P([(RX + 72, ty + 110), (RX + 72, y + 32)]); P([(RX + 227, ty + 110), (RX + 227, y + 32)])
    y += 34

    # ── 오른쪽 기둥: 에이전트를 거치지 않는 경로
    by = y
    R(RX - 6, by, RW + 12, 232, "b-plan", 12)
    T(RX + RW / 2, by + 24, "에이전트를 거치지 않는 경로", "h3", "middle")
    T(RX + RW / 2, by + 42, "같은 계산 코드 · 같은 반영을 쓴다", "s", "middle")
    R(RX + 8, by + 54, RW - 16, 76, "b"); T(RX + 20, by + 76, "새벽 점검 — 직접 계산", "h3")
    T(RX + 20, by + 96, "닫힌 곳 → 같은 시각 근처 대체", "s"); T(RX + 20, by + 114, "→ 묻기 또는 반영", "s")
    R(RX + 8, by + 140, RW - 16, 82, "b"); T(RX + 20, by + 162, "채팅 처리 (TripDesk)", "h3")
    T(RX + 20, by + 182, "해석 → 변경 · 제안 · 되돌리기", "s"); T(RX + 20, by + 200, "질문은 근거로 답만 (일정 그대로)", "s")

    # ── 오케스트레이터
    y = iobox(MX, y, MW - 160, "오케스트레이터 (Supervisor)",
              ["Case (문제 코드 · 원인)"],
              ["담당 에이전트 1개 (요식 또는 액티비티)", "할 일 + 허용 툴 + 컨텍스트 · Team 시간 제한 90초"], "b-core",
              sub="규칙 라우팅: 문제 코드 앞부분 + 서버가 확인한 대상")
    down(CX - 80, y, y + 34); y += 34

    # ── Worker Agent (틀) — 안쪽 루프
    wy = y
    WH = 640
    R(MX - 10, wy, MW + 20, WH, "frame-w", 14)
    T(MX + 8, wy + 28, "Worker Agent — 둘 중 하나가 받는다", "h2")
    T(MX + 340, wy + 28, "에이전트끼리 직접 안 부름 · 툴로만 조회(12회)", "sub")
    a = wy + 44
    R(MX + 10, a, 330, 84, "b-agent"); T(MX + 175, a + 24, "요식 에이전트", "h3", "middle")
    T(MX + 22, a + 48, "I: 식사 항목 · 원인 · 식이 조건", "s"); T(MX + 22, a + 68, "O: 대체 식당 1 + 다른 안 최대 2 / 그대로 / 못 함", "s")
    R(MX + 360, a, 330, 84, "b-agent"); T(MX + 525, a + 24, "액티비티 에이전트", "h3", "middle")
    T(MX + 372, a + 48, "I: 활동 항목 · 원인 · 실내 여부 · 설문", "s"); T(MX + 372, a + 68, "O: 대체 활동 + 다른 안 / 바꿀까요? / 못 함", "s")
    P([(MX + 175, a + 84), (MX + 175, a + 100), (MX + 525, a + 100), (MX + 525, a + 84)], "e", None)
    P([(CX, a + 100), (CX, a + 118)])
    k = a + 120
    R(CX - 170, k, 340, 46, "b"); T(CX, k + 28, "현재 항목 재점검 (같은 외부 점검)", "h3", "middle")
    d1 = k + 96
    diamond(CX, d1, 170, 60, "지금 상태?")
    P([(CX, k + 46), (CX, d1 - 31)])
    R(MX + 10, d1 - 52, 150, 44, "b-out"); T(MX + 85, d1 - 25, "그대로", "h3", "middle")
    R(MX + 10, d1 + 8, 150, 44, "b-fail"); T(MX + 85, d1 + 35, "확인 실패 · 기록", "h3", "middle")
    P([(CX - 85, d1), (CX - 120, d1), (CX - 120, d1 - 30), (MX + 162, d1 - 30)]); T(CX - 106, d1 - 38, "clear", "lbl")
    P([(CX - 120, d1), (CX - 120, d1 + 30), (MX + 162, d1 + 30)], "bad", "r"); T(CX - 106, d1 + 48, "fatal", "lr")
    c = d1 + 60
    R(CX - 200, c, 400, 82, "b-agent"); T(CX, c + 24, "다음 후보 1곳 점검", "h3", "middle")
    T(CX, c + 46, "영업 · 거리 · 조건 + 같은 외부 재점검", "s", "middle")
    T(CX, c + 66, "요식: 순위순 최대 3곳 재점검 · 통과하면 담아 둠", "s", "middle")
    P([(CX, d1 + 30), (CX, c - 2)]); T(CX + 10, d1 + 50, "disrupted", "lbl")
    d2 = c + 130
    diamond(CX, d2, 170, 60, "더 볼 후보?")
    P([(CX, c + 82), (CX, d2 - 31)])
    P([(CX + 85, d2), (CX + 280, d2), (CX + 280, c + 41), (CX + 202, c + 41)], "loop", "g")
    T(CX + 150, d2 - 10, "예", "lg"); T(CX + 288, c + 96, "안쪽 루프", "lg"); T(CX + 288, c + 114, "다음 후보로", "lbl")
    d3 = d2 + 100
    diamond(CX, d3, 190, 60, "통과한 곳 있나?")
    P([(CX, d2 + 30), (CX, d3 - 31)]); T(CX + 10, d2 + 52, "아니오 (다 봤음)", "lbl")
    R(MX + 10, d3 - 22, 150, 44, "b-fail"); T(MX + 85, d3 + 5, "못 함 · 일정 유지", "h3", "middle")
    P([(CX - 95, d3), (MX + 162, d3)], "bad", "r"); T(CX - 130, d3 - 8, "아니오", "lr", "middle")
    P([(CX, d3 + 30), (CX, wy + WH - 2)]); T(CX + 10, d3 + 52, "예 — 변경 제안 (최선 1 + 다른 안 최대 2)", "lbl")
    y = wy + WH + 34
    P([(CX, wy + WH), (CX, y - 2)])

    # ── 검증 · 반영 (틀) — 묻기 루프
    gy = y
    GH = 252
    R(MX - 10, gy, MW + 20, GH, "b-core", 14)
    T(MX + 8, gy + 28, "검증 + 반영 (오케스트레이터)", "h2")
    v = gy + 46
    R(MX + 10, v, 260, 76, "b"); T(MX + 140, v + 24, "검증", "h3", "middle")
    T(MX + 140, v + 46, "고객 소유 · Case 버전", "s", "middle"); T(MX + 140, v + 64, "여행 기준 버전 · 항목 · 장소", "s", "middle")
    d4 = v + 38
    diamond(MX + 395, d4, 150, 60, "묻기 조건?")
    P([(MX + 270, d4), (MX + 318, d4)])
    R(MX + 512, v - 6, 180, 88, "b-out"); T(MX + 602, v + 18, "새 일정 버전", "h3", "middle")
    T(MX + 602, v + 40, "이전 판 보존", "s", "middle"); T(MX + 602, v + 58, "+ 앞뒤 이동 재계산", "s", "middle"); T(MX + 602, v + 76, "(이동 판정 툴)", "s", "middle")
    P([(MX + 470, d4), (MX + 510, d4)]); T(MX + 490, d4 - 8, "아니오", "lbl", "middle")
    q = v + 104
    R(MX + 290, q, 210, 92, "b"); T(MX + 395, q + 22, "사용자에게 묻기", "h3", "middle")
    T(MX + 395, q + 44, "보호 일정 · 먼저 물어봐", "s", "middle"); T(MX + 395, q + 62, "(안전 경보면 안전 알림)", "s", "middle"); T(MX + 395, q + 80, "날씨만 + 실내 모름 → 바꿀까요?", "s", "middle")
    P([(MX + 395, d4 + 30), (MX + 395, q - 2)]); T(MX + 405, d4 + 50, "예", "lbl")
    P([(MX + 290, q + 46), (MX + 140, q + 46), (MX + 140, v + 78)], "loop", "g")
    T(MX + 20, q + 72, "응답(다른 안 선택)", "lg"); T(MX + 20, q + 90, "→ 다시 검증", "lg")
    P([(MX - 10, v + 38), (BUS, v + 38)], "bad", None); T(MX - 34, v + 30, "거부", "lr", "middle")
    P([(RX + RW / 2, by + 232), (RX + RW / 2, gy + 30), (MX + MW + 12, gy + 30)], "e", "a")
    T(RX + RW / 2 + 10, gy + 20, "같은 반영으로", "lbl")
    y = gy + GH
    P([(MX + 595, v + 82), (MX + 595, y + 32)])
    y += 34

    # ── 알림 + SSE
    ny = y
    y = iobox(MX, y, MW, "알림 (아웃박스 → 워커 → Discord)",
              ["등록 · 변경 · 묻기 알림 + 정기 안내(하루 시작 · 다음 일정 · 출발 — 별도 작업)"],
              ["Discord 웹훅 알림 + 최신 계획서 링크 (지금은 팀 채널 하나 · 개인은 등록 · 시험까지)",
               "적재 중복은 중복 방지 키로 막음 · 첫 발송 포함 최대 3회 · 시간 초과는 다시 안 보냄"], "b-api")
    R(RX, ny + 10, RW, 92, "b-user"); T(RX + RW / 2, ny + 34, "웹 화면 — 일정 변경 SSE", "h3", "middle")
    T(RX + RW / 2, ny + 56, "DB 변화 신호 → 웹이 다시 읽음", "s", "middle"); T(RX + RW / 2, ny + 76, "Discord 와 별도 경로", "s", "middle")
    P([(MX + MW + 12, gy + GH - 30), (875, gy + GH - 30), (875, ny + 56), (RX - 2, ny + 56)], "e", "a")

    # ── 여행 기간 남음? — 결과 합류 · 바깥 루프
    P([(CX, y), (CX, y + 33)])
    e = y + 70
    diamond(CX, e, 210, 70, "여행 기간 남음?")
    for yy in (d1 - 30, d1 + 30, d3):
        P([(MX + 10, yy), (BUS, yy)], "bus", None)
    P([(BUS, d1 - 30), (BUS, e), (CX - 107, e)], "bus", "g")
    T(BUS + 10, e - 10, "모든 결과가 모인다", "lg")
    P([(CX + 105, e), (LOOP, e), (LOOP, loop_y), (RX + RW + 12, loop_y)], "loop", "g")
    T(CX + 124, e - 10, "예 — 바깥 루프: 다음 점검 대기", "lg")
    S.append(f'<circle cx="{CX}" cy="{e + 92}" r="14" fill="none" stroke="#1f2328" stroke-width="2"/><circle cx="{CX}" cy="{e + 92}" r="8" fill="#1f2328"/>')
    P([(CX, e + 35), (CX, e + 76)]); T(CX + 12, e + 60, "아니오 — 점검할 항목이 없음", "lbl")
    R(RX, e + 40, RW, 64, "b-fail"); T(RX + RW / 2, e + 64, "운영자", "h3", "middle"); T(RX + RW / 2, e + 86, "작업 연속 실패 시 오류 알림만", "s", "middle")
    H = e + 130
    return f'<svg class="fig" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{DEFS}{"".join(S)}</svg>'


# ───────────── 그림 2 · Agent 와 Tool / Data 계층 ─────────────
def fig2():
    S.clear()
    W, H = 1150, 760
    T(40, 34, "그림 2 · Agent 와 Tool / Data 계층", "ft")
    T(40, 56, "에이전트는 DB · 외부 API 를 직접 열지 않고 허용된 툴로만 읽는다 · 판정은 코드", "s")
    R(250, 80, 260, 60, "b-agent"); T(380, 116, "요식 에이전트", "h3", "middle")
    R(640, 80, 260, 60, "b-agent"); T(770, 116, "액티비티 에이전트", "h3", "middle")
    P([(380, 140), (380, 160), (770, 160), (770, 140)], "e", None)
    P([(575, 160), (575, 186)])
    T(587, 178, "툴 호출 (허용된 것만 · 한 실행 최대 12회)", "lbl")
    ty = 188
    R(150, ty, 850, 214, "b-tool", 12)
    T(575, ty + 28, "툴 레이어 (ReadToolbox) — 같은 서버 안 호출 · MCP 아님", "h2", "middle")
    tools = [("read.itinerary", "지금 일정 버전 (고객 소유 확인)"), ("read.disruptions", "외부 6범주 점검"),
             ("read.dining_state", "그 시각 영업 · 라스트오더"), ("read.dining_alternatives", "대체 식당 후보"),
             ("read.place_catalog", "대체 장소 후보"), ("read.policy", "규정 조각")]
    for i, (n, d) in enumerate(tools):
        col, row = i % 2, i // 2
        x0, y0 = 175 + col * 420, ty + 62 + row * 30
        T(x0, y0, n, "mono"); T(x0 + 190, y0, d, "s")
    T(175, ty + 160, "주요 툴 예시 — 전체 허용 목록은 에이전트 등록 정보(manifest)에 있다 (이전 버전 · 고객 문장 · 예약 툴 포함)", "s")
    T(175, ty + 182, "목록 밖 툴 거부 · 같은 툴 + 같은 인자 다시 부르면 거부 · 12회 넘으면 멈춤", "s")
    T(175, ty + 202, "조회가 안 되거나 값이 비면 「모름」, 정상 조회의 빈 결과는 「없음」으로 구분", "s")
    by = ty + 214
    P([(575, by), (575, by + 22)], "e", None)
    P([(225, by + 22), (925, by + 22)], "e", None)
    for xx in (225, 575, 925):
        P([(xx, by + 22), (xx, by + 46)])
    dy = by + 48
    boxes = [(80, "PostgreSQL + pgvector", ["여행 · 일정 버전(이전 판 보존)", "Case · 실행 기록", "장소 · 요식 원장", "규정 조각 + 임베딩", "(로컬 기본 bge-m3 — 설정으로 선택)"], "b-api"),
             (430, "외부 데이터 6범주", ["기상(Open-Meteo ↔ 기상청)", "기상 특보 · 지진 (기상청)", "재난문자 · 대기질", "교통: ITS + UTIC 합침", "대체 소스는 일부 범주만"], "b"),
             (780, "이동 자료 + 이동 판정 툴", ["지하철 열차 시간표", "버스 노선 · 배차 · 구간", "사용 파일 444,915행", "반영 때 앞뒤 이동 재계산", "일정 생성 때 이동 배치"], "b-tool")]
    for x0, t, ls, cls in boxes:
        R(x0, dy, 290, 170, cls, 10)
        T(x0 + 145, dy + 26, t, "h3", "middle")
        for i, ln in enumerate(ls):
            T(x0 + 16, dy + 54 + i * 22, ln, "s")
    T(780 + 145, dy + 196, "공용 툴 · 에이전트 아님 (코드에는 아직 팀 등록)", "lbl", "middle")
    ey = dy + 222
    for xx in (225, 575, 925):
        P([(xx, dy + 170), (xx, ey)], "e", None)
    P([(225, ey), (925, ey)], "e", None)
    P([(575, ey), (575, ey + 26)])
    R(375, ey + 28, 400, 44, "b-core"); T(575, ey + 56, "근거(무엇을 · 언제 확인) + 판정 → 에이전트", "h3", "middle")
    H = ey + 90
    return f'<svg class="fig" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{DEFS}{"".join(S)}</svg>'


TABLE = [
    ("트리거 — 낮 감시", "앞으로 90분 안 항목, 외부 6범주", "문제 항목 + 원인 → Case 1건", "1분마다 점검 — 깨진 것만 Case 로"),
    ("트리거 — 새벽 영업 확인", "그날 식사 · 활동, Google 영업 정보", "닫힌 곳의 근처 대체 → 묻기 / 반영", "03~08시 · 에이전트를 거치지 않는 직접 계산"),
    ("채팅 처리 (TripDesk)", "고객 문장(바꿔 줘 · 늦어요 · 다른 안 · 되돌리기 · 질문)", "변경 · 제안 · 답변 (질문은 일정 그대로)", "에이전트와 같은 계산 코드를 직접 부른다"),
    ("오케스트레이터", "Case (문제 코드 · 원인)", "담당 에이전트 1개, 할 일 · 허용 툴 · 컨텍스트", "규칙 라우팅 · Team 시간 제한 90초"),
    ("요식 에이전트", "식사 항목 · 원인 · 식이 조건", "그대로 / 대체 식당 1 + 다른 안 최대 2 / 못 함", "영업 · 브레이크 · 라스트오더 · 휴무 점검, 순위순 최대 3곳 재점검"),
    ("액티비티 에이전트", "활동 항목 · 원인 · 실내 여부 · 설문", "그대로 / 대체 활동 + 다른 안 / 바꿀까요? / 못 함", "운영 · 날씨 · 대기질 점검 → 후보 점검 후 순위"),
    ("이동 판정 툴 (공용 · 에이전트 아님)", "두 장소 · 목표 도착 시각 · 앞 일정 종료 시각", "경로 · 소요 · 판정(성립 / 불가 / 모름)", "반영 때 앞뒤 이동 재계산 · 일정 생성 (후보 재점검 연결은 아직)"),
    ("검증 + 반영 (오케스트레이터)", "변경 제안", "새 일정 버전 / 사용자에게 묻기 / 거부", "고객 소유 · Case 버전 · 여행 기준 버전 · 항목 · 장소 확인"),
    ("알림 (아웃박스 워커)", "등록 · 변경 · 묻기 알림, 정기 안내", "Discord 웹훅 알림 + 계획서 링크", "중복 방지 키 · 첫 발송 포함 최대 3회"),
    ("계획 읽기 · 일정 생성", "계획 원문 / 「일정 짜 줘」 선호", "일정 항목 + 근거 줄 / 판정을 통과한 초안", "규칙 먼저 · AI 는 줄 위치 · 받아쓰기 · 순서 제안만"),
]

INTRO = ("guguroute 의 <b>Multi-Agent 구조</b>는 다음처럼 정리할 수 있습니다. 핵심은 <b>낮 감시가 깨진 일정 항목을 Case 로 열면 오케스트레이터가 담당 에이전트 1개(요식 또는 액티비티)를 고르고, "
         "에이전트는 허용된 툴로만 데이터를 읽어 대체 후보를 하나씩 다시 점검하며(안쪽 루프), 결과는 검증 · 묻기 · 반영 · 알림을 거쳐 여행 기간 동안 다음 점검을 기다리는(바깥 루프)</b> 구조입니다. "
         "고객 채팅과 새벽 영업 확인은 에이전트를 거치지 않고 <b>같은 계산 코드와 같은 반영</b>을 씁니다. 이동은 에이전트가 아니라 <b>공용 판정 툴</b>입니다.")
TOOLS_NOTE = ("특히 <b>에이전트가 DB · 외부 API 에 직접 접근하는 것이 아니라 툴 레이어(허용 목록)를 통해서만 조회</b>하도록 보는 것이 중요합니다. "
              "판정은 코드가 하고, 조회가 안 되면 「없음」이 아니라 「모름」으로 돌려줍니다.")
CLOSING = ("이 구조에서 에이전트 사이의 연결은 <b>오케스트레이터</b>(에이전트끼리 직접 부르지 않음), 에이전트와 데이터의 연결은 <b>툴 레이어</b>(허용 목록 · 12회 상한), "
           "데이터는 <b>PostgreSQL + 외부 6범주 + 이동 자료</b>가 담당합니다. AI 모델은 계획서 줄 위치 찾기 · 사진 받아쓰기 · 문장 해석 · 일정 후보 순서 제안 · 영업시간 원문 정리 · 문장 작성에 쓰고, "
           "일정 성립 · 영업 · 시간 판정과 반영 여부는 코드가 정합니다. 모델은 로컬 · API 비교 시험 중입니다.")
CYCLE = ("시스템 구성도에서는 낮 감시의 대표 순환을 <b><code>트리거 → Case → 오케스트레이터 → Worker Agent(후보 재점검 루프) → 검증 · 묻기 · 반영 → 알림 → 다음 점검 대기</code></b>로 "
         "표현하면 guguroute 의 핵심 — 계획을 받아 여행이 끝날 때까지 지킨다 — 이 가장 명확하게 드러납니다. 고객 채팅 · 새벽 영업 확인 · 일정 생성 · 정기 안내는 별도 경로이며 같은 계산과 버전 저장을 공유합니다.")
STATUS = ("지금 상태: 일정 등록 거절 · 고객 채팅 · 다른 안 · 되돌리기 · 일정 생성 · 정기 안내 · 일정 변경 SSE 는 구현. 접수 · 생성 · 채팅 진행 SSE 는 서버 구현 · 웹 연결 진행 중. "
          "실패 항목의 채팅 대안 추천 · 후보 재점검의 이동 판정 연결은 아직 없음. 알림은 팀 Discord 채널 하나(개인 Discord 는 등록 · 시험 발송까지). "
          "로그인 · AWS 자동 배포는 팀 계획(코드 없음). 이동은 코드에 아직 팀으로 등록돼 있어 툴로 정리가 필요하다.")

PAGE_CSS = f"""
body{{margin:0;background:#fff;color:#1f2328;font-family:{SANS};font-size:16px;line-height:1.7}}
main{{max-width:1320px;margin:0 auto;padding:36px 28px 56px}}
h1{{font-size:28px;margin:0 0 6px}} h2{{font-size:23px;margin:36px 0 14px;padding-bottom:8px;border-bottom:1px solid #d1d9e0}} h3{{font-size:19px;margin:28px 0 12px}}
p{{margin:0 0 14px}} code{{font-family:{MONO};background:rgba(175,184,193,.2);padding:.1em .4em;border-radius:6px;font-size:90%}}
.figwrap{{border:1px solid #d1d9e0;border-radius:10px;padding:10px;overflow-x:auto;background:#fff}} .figwrap svg{{display:block;max-width:100%;height:auto}}
table{{border-collapse:collapse;width:100%;font-size:14.5px}} th,td{{border:1px solid #d1d9e0;padding:8px 12px;text-align:left;vertical-align:top}} th{{background:#f6f8fa}}
tr:nth-child(2n) td{{background:#fbfcfd}} blockquote{{margin:16px 0;padding:6px 16px;color:#59636e;border-left:4px solid #d1d9e0}}
.note{{font-size:13.5px;color:#59636e}}
{CSS}
"""


def page_html(f1, f2):
    rows = "".join(f"<tr><td><b>{esc(a)}</b></td><td>{esc(b)}</td><td>{esc(c)}</td><td>{esc(d)}</td></tr>" for a, b, c, d in TABLE)
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>guguroute Multi-Agent 구조도</title><style>{PAGE_CSS}</style></head><body><main>
<p class="note">v9 · 2026-10-02 · 형식: team_branch/me/Multi-Agent구조도참고.md 와 같은 순서 · 사실: final_project_cs 코드 대조 + 코덱스 독립 검토</p>
<p>{INTRO}</p>
<h2>Multi-Agent 전체 구조도</h2>
<div class="figwrap">{f1}</div>
<h2>Agent와 Tool / Data 계층 관계</h2>
<p>{TOOLS_NOTE}</p>
<div class="figwrap">{f2}</div>
<h3>Agent별 I/O 요약</h3>
<table><thead><tr><th>구성</th><th>주요 Input</th><th>주요 Output</th><th>주요 역할</th></tr></thead><tbody>{rows}</tbody></table>
<p style="margin-top:18px">{CLOSING}</p>
<p>{CYCLE}</p>
<blockquote>{STATUS}</blockquote>
</main></body></html>"""


def page_md():
    """md 판 — 같은 순서, 그림은 PNG 로 넣는다"""
    import re as _re
    strip = lambda s: _re.sub(r"</?b>", "**", s).replace("<code>", "`").replace("</code>", "`")
    rows = "\n".join(f"| **{a}** | {b} | {c} | {d} |" for a, b, c, d in TABLE)
    return f"""{strip(INTRO)}

## Multi-Agent 전체 구조도

![Multi-Agent 전체 구조도](그림1_전체구조도_v9.png)

## Agent와 Tool / Data 계층 관계

{strip(TOOLS_NOTE)}

![Agent와 Tool / Data 계층](그림2_툴데이터계층_v9.png)

### Agent별 I/O 요약

| 구성 | 주요 Input | 주요 Output | 주요 역할 |
|---|---|---|---|
{rows}

{strip(CLOSING)}

{strip(CYCLE)}

> {STATUS}
"""


def shot(html, png, width, height=4000):
    tmp = Path(tempfile.mkdtemp(prefix="v9_png_"))
    p = tmp / "p.html"
    p.write_text(html, encoding="utf-8")
    raw = tmp / "p.png"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    "--virtual-time-budget=4000", f"--window-size={width},{height}", f"--screenshot={raw}", p.as_uri()],
                   capture_output=True, timeout=180)
    from PIL import Image, ImageChops
    im = Image.open(raw).convert("RGB")
    box = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
    if box:
        im = im.crop((0, 0, im.size[0], min(im.size[1], box[3] + 40)))
    im.save(png)
    shutil.rmtree(tmp, ignore_errors=True)
    print("ok", png.name, im.size)


def main():
    f1, f2 = fig1(), fig2()
    for name, svg in (("그림1_전체구조도_v9", f1), ("그림2_툴데이터계층_v9", f2)):
        W = int(svg.split('width="')[1].split('"')[0]); H = int(svg.split('height="')[1].split('"')[0])
        solo = svg.replace("<svg ", '<svg style="background:#fff" ', 1).replace(DEFS, DEFS + f"<style>{CSS}</style>", 1)
        (OUT / f"{name}.svg").write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + solo, encoding="utf-8")
        shot(f'<!doctype html><meta charset="utf-8"><style>html,body{{margin:0;background:#fff}}</style>{solo}', OUT / f"{name}.png", W, H)
    page = page_html(f1, f2)
    (OUT / "triPilot_Multi-Agent구조도_v9.html").write_text(page, encoding="utf-8")
    shot(page, OUT / "triPilot_Multi-Agent구조도_v9.png", 1376, 6000)
    (OUT / "triPilot_Multi-Agent구조도_v9.md").write_text(page_md(), encoding="utf-8")
    print("ok md")


if __name__ == "__main__":
    main()
