# -*- coding: utf-8 -*-
"""guguroute 한눈에 — 멀티 에이전트 워크플로 · 시스템 아키텍처 (2026-10-02, v1)

    python make_arch_v1.py   → ../triPilot_아키텍처_한눈에_v4.html

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
                  for i, c in (("a", "ah"), ("g", "ah-g"), ("r", "ah-r"), ("b", "ah-b")))
        + '</defs>')


def svg(W, H, label):
    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(label)}">{DEFS}{"".join(S)}</svg>'


# ───────────── 그림 1 · 멀티 에이전트 워크플로 ─────────────
def ionode(x, y, w, h, title, role, gets, gives, cls="node"):
    """상자 안에 이름 · 실무 용어 · 받음 · 냄 — 참고 예시(I · O)와 같은 모양"""
    R(x, y, w, h, cls)
    T(x + 16, y + 27, title, "h", "start")
    T(x + w - 12, y + 25, role, "role", "end")
    yy = y + 54
    for tag, rows, pc in (("받음", gets, "pill-in"), ("냄", gives, "pill-out")):
        for i, g in enumerate(rows):
            if i == 0:
                R(x + 14, yy - 13, 38, 18, pc, 4)
                T(x + 33, yy + 1, tag, "pill")
            T(x + 62, yy, g, "s2", "start")
            yy += 19
        yy += 5


def step(x, y, w, h, title, sub=None, cls="node"):
    R(x, y, w, h, cls, 8)
    if sub:
        T(x + w / 2, y + h / 2 - 3, title, "h2")
        T(x + w / 2, y + h / 2 + 16, sub, "s")
    else:
        T(x + w / 2, y + h / 2 + 5, title, "h2")


def workflow():
    S.clear()
    W, H = 1720, 1300
    T(40, 40, "그림 1 · 멀티 에이전트 워크플로 — 오케스트레이터(Supervisor) 패턴 · 상태 그래프", "cap", "start")
    T(40, 62, "받음 = 이 단계가 받는 것 · 냄 = 다음 단계로 넘기는 것 · 마름모 = 조건 분기 · 금색 선 = 루프 · 붉은 선 = 실패 경로 · 금색 상자 = 오케스트레이터 · 파란 영역 = 에이전트 · 초록 상자 = 공용 툴(모듈)", "s", "start")

    # ── 윗줄: 트리거 → 케이스 → 오케스트레이터
    top, h = 100, 170
    yc = top + 85
    S.append(f'<circle class="start" cx="54" cy="{yc}" r="13"/>')
    L(54, yc + 32, "시작")
    ionode(90, top, 286, h, "트리거", "Scheduler · Event",
           ["현재 일정 버전", "외부 데이터 6종 점검 결과"], ["깨진 일정 항목 + 원인", "모니터링 1분 · 새벽 점검 · 고객 신고"])
    ionode(410, top, 270, h, "케이스 생성", "Case Intake",
           ["깨진 항목 · 원인"], ["케이스 1건 (요청 종류 · 문제 코드)", "이 경로는 AI 분류를 쓰지 않음"], "core")
    ionode(716, top, 330, h, "오케스트레이터 · 라우팅", "Supervisor",
           ["케이스 (문제 코드 · 요청 종류)"], ["담당 에이전트 1개 선택 (문제 코드 앞부분)", "태스크 — 할 일 · 허용 툴 · 90초", "컨텍스트 — 상태 · 원인 · 규정 (12k 토큰)"], "core")
    P([(67, yc), (88, yc)])
    P([(376, yc), (408, yc)])
    P([(680, yc), (714, yc)])
    ionode(1090, top, 590, h, "이동 판정 모듈 (Mobility Engine)", "공용 툴 · 에이전트 아님",
           ["출발지 · 도착지 · 출발 시각 (구간)"], ["제시간에 닿나? 성립 / 불가 + 경로 · 소요 · 요금",
                                                "근거 등급 — 확정(시간표 계산) · 추정 · 근거 없음"], "tool")
    T(1106, top + 142, "부르는 곳 — 에이전트의 후보 재점검 · 반영의 앞뒤 이동 재계산 · 일정 생성", "s", "start")
    T(1106, top + 160, "교통 사건으로 이동 구간이 깨지면 오케스트레이터가 직접 불러 경로를 다시 찾는다", "s", "start")

    # ── 가운데: 에이전트 실행 영역 (셋 중 하나)
    cx0, cy0, cw, ch = 40, 320, W - 80, 480
    P([(881, top + h), (881, cy0 + 40)])
    L(893, top + h + 30, "담당 1개 호출 · 태스크 + 컨텍스트", "lbl", "start")
    R(cx0, cy0, cw, ch, "agent-band", 14)
    T(60, cy0 + 28, "에이전트 실행 (Worker Agent)", "h", "start")
    T(300, cy0 + 28, "— 오케스트레이터가 둘 중 하나를 부른다. 둘은 같은 계약(받음 · 냄)과 같은 내부 루프를 쓰고, 점검 항목과 후보 출처만 다르다", "s", "start")
    R(60, cy0 + 42, cw - 40, 32, "bar", 6)
    R(72, cy0 + 49, 38, 18, "pill-in", 4)
    T(91, cy0 + 63, "받음", "pill")
    T(122, cy0 + 63, "태스크 (할 일 · 허용 툴 목록 · 90초)  +  컨텍스트 (무엇이 깨졌나 · 케이스 상태 · 규정)  —  데이터는 허용된 툴로만 조회", "s2", "start")

    # 왼쪽: 영역마다 다른 것
    T(60, cy0 + 104, "영역마다 다른 것", "h2", "start")
    cards = [("요식 에이전트", "점검  외부 6종 · 그 시각 영업 · 라스트오더", "후보  요식 DB (덜 붐빔 · 비슷함 · 가까움) → 장소 목록", None),
             ("액티비티 에이전트", "점검  외부 6종 (날씨 · 대기질 · 특보 · 지진)", "후보  같은 대분류 · 비슷한 순 (관광공사 장소)", "실내 여부를 모르면 대안 대신 「바꿀까요?」만 낸다"),
            ]
    for i, (nm, a, b, note) in enumerate(cards):
        y = cy0 + 118 + i * 112
        R(60, y, 440, 100, "agent", 8)
        T(76, y + 25, nm, "h2", "start")
        T(486, y + 24, "Worker Agent", "role-b", "end")
        T(76, y + 50, a, "s2", "start")
        T(76, y + 71, b, "s2", "start")
        if note:
            T(76, y + 91, note, "s", "start")
    # 이동은 에이전트가 아님 — 빈 자리에 표시
    R(60, cy0 + 342, 440, 100, "tool-note", 8)
    T(76, cy0 + 367, "이동은 에이전트가 아니다", "h2", "start")
    T(76, cy0 + 392, "위 오른쪽 「이동 판정 모듈」을 두 에이전트와", "s2", "start")
    T(76, cy0 + 413, "오케스트레이터가 툴로 부른다 (공용)", "s2", "start")
    # 카드 → 공통 흐름
    S.append(f'<path class="brace" d="M508 {cy0 + 118} L520 {cy0 + 118} L520 {cy0 + 330} L508 {cy0 + 330}"/>')
    P([(520, cy0 + 150), (543, cy0 + 150)])
    L(526, cy0 + 350, "둘 다 같은 흐름", "lbl", "start")

    # 오른쪽: 셋이 똑같이 도는 내부 흐름
    T(548, cy0 + 104, "내부 흐름 — 두 에이전트가 같은 코드로 돈다", "h2", "start")
    r1 = cy0 + 150   # 첫 줄 가운데
    step(548, r1 - 28, 170, 56, "① 지금 일정 읽기", "툴")
    step(748, r1 - 28, 170, 56, "② 다시 점검 (툴)", "외부 6종 · 영업 · 교통")
    P([(718, r1), (746, r1)])
    diamond(1000, r1, 130, 64, "깨졌나?")
    P([(918, r1), (933, r1)])
    r2 = cy0 + 300   # 둘째 줄 가운데
    step(548, r2 - 28, 170, 56, "③ 대안 후보 목록", "순위순")
    step(748, r2 - 28, 170, 56, "④ 후보 1곳 재점검", "같은 점검 + 앞뒤 이동")
    P([(1000, r1 + 32), (1000, r1 + 58), (633, r1 + 58), (633, r2 - 30)])
    L(1012, r1 + 50, "예", "lbl", "start")
    P([(718, r2), (746, r2)])
    diamond(1000, r2, 150, 70, "더 볼 후보?")
    P([(918, r2), (923, r2)])
    # 안쪽 루프
    P([(1000, r2 + 35), (1000, r2 + 72), (833, r2 + 72), (833, r2 + 30)], "edge loop", "g")
    L(548, r2 + 96, "예 — 다음 후보로 (안쪽 루프). 통과한 곳은 모아 둔다", "lbl-g", "start")
    L(548, r2 + 116, "종료 조건: 최대 3곳 확인 · 툴 12회 · 90초 — 넘은 후보는 「확인 안 함」으로 빼고 고르지 않는다 · 앞뒤 이동은 이동 판정 모듈(툴)", "lbl", "start")
    diamond(1250, r2, 160, 70, "통과한 곳 있나?")
    P([(1075, r2), (1168, r2)])
    L(1120, r2 - 10, "아니오", "lbl")

    # 냄 — 결과 셋 중 하나
    ox, ow = 1420, 240
    T(ox, cy0 + 104, "냄 — 셋 중 하나", "h2", "start")
    R(ox + 150, cy0 + 90, 38, 18, "pill-out", 4)
    T(ox + 169, cy0 + 104, "냄", "pill")
    step(ox, r1 - 30, ow, 60, "영향 없음", "답변만 · 일정 그대로", "out")
    R(ox, r2 - 40, ow, 80, "out", 8)
    T(ox + ow / 2, r2 - 15, "변경 제안", "h2")
    T(ox + ow / 2, r2 + 6, "최선 1곳 + 다른 안 최대 2개", "s")
    T(ox + ow / 2, r2 + 25, "일정은 직접 바꾸지 않음", "s")
    step(ox, r2 + 58, ow, 60, "못 함 (사유)", "대안 없음 · 데이터 대체까지 실패", "out-bad")
    P([(1065, r1), (ox - 2, r1)])
    L(1240, r1 - 10, "아니오", "lbl")
    P([(1330, r2), (ox - 2, r2)])
    L(1375, r2 - 10, "예", "lbl")
    P([(1250, r2 + 35), (1250, r2 + 88), (ox - 2, r2 + 88)], "edge bad", "r")
    L(1262, r2 + 62, "아니오", "lbl-r", "start")

    # ── 아랫줄 (오른쪽 → 왼쪽)
    bt, bh = 860, 170
    yb = bt + 85
    P([(ox + ow / 2, cy0 + ch), (ox + ow / 2, bt - 2)])
    L(ox + ow / 2 + 12, cy0 + ch + 34, "결과 (Agent Result)", "lbl", "start")
    ionode(1300, bt, 380, bh, "검증", "Validator",
           ["에이전트 결과"], ["통과 / 거부", "근거가 있나 · 그 고객 것인가", "케이스 버전이 그대로인가"], "core")
    diamond(1180, yb, 150, 90, "통과?")
    P([(1300, yb), (1257, yb)])
    ionode(740, bt, 340, bh, "반영", "Apply · Commit",
           ["변경 제안 (기준 버전 · 바뀐 항목 · 대안)"], ["새 일정 버전 (이전 버전 보존)", "앞뒤 이동은 이동 판정 모듈로 재계산", "또는 사용자 확인 요청 — 설문 「먼저", "물어봐」 · 고정 일정 · 안전 경보일 때"], "core")
    P([(1105, yb), (1082, yb)])
    L(1094, yb - 10, "예", "lbl")
    ionode(400, bt, 300, bh, "알림", "Notifier · Outbox",
           ["새 일정 버전 · 알림 문구"], ["디스코드 알림 1회 (재시도 3회)", "여행계획서 링크 갱신", "→ 사용자: 다른 안 · 되돌리기 가능"], "core")
    P([(740, yb), (702, yb)])
    diamond(290, yb, 140, 84, "여행 끝?")
    P([(400, yb), (362, yb)])
    S.append(f'<circle class="end" cx="290" cy="{yb + 115}" r="14"/><circle class="end-in" cx="290" cy="{yb + 115}" r="8"/>')
    P([(290, yb + 42), (290, yb + 99)])
    L(302, yb + 74, "예", "lbl", "start")
    L(290, yb + 151, "끝", "lbl")
    # 바깥 루프 — 왼쪽 가장자리로 돌아 트리거로
    P([(220, yb), (24, yb), (24, top + 140), (88, top + 140)], "edge loop", "g")
    L(36, cy0 + ch + 36, "아니오 — 바깥 루프: 여행이 끝날 때까지 다음 모니터링 · 새벽 점검 · 신고를 기다려 다시", "lbl-g", "start")
    # 실패 경로
    ionode(1030, bt + 200, 300, 104, "변경 없음 · 실패", "Fallback",
           ["거부 · 실패 사유"], ["일정 유지 · 오류 로그", "운영자에게 오류 알림만"], "fail")
    P([(1180, yb + 45), (1180, bt + 198)], "edge bad", "r")
    L(1192, yb + 80, "아니오", "lbl-r", "start")
    P([(1030, bt + 252), (330, bt + 252), (330, yb + 18)], "edge bad", "r")

    sy = 1200
    R(40, sy, W - 80, 74, "state", 8)
    T(60, sy + 26, "공유 State — PostgreSQL", "h2", "start")
    T(60, sy + 50, "케이스 — 상태 12개 · 버전 · 원인 · 담당 에이전트   |   여행 — 일정 버전(이력 보존)   |   아웃박스 큐 — 보낼 알림", "s", "start")
    T(60, sy + 68, "모든 단계가 이 State 를 읽고, 버전이 맞을 때만 쓴다 (낙관적 동시성) — 사이에 다른 쓰기가 있으면 그 결과는 버린다", "s", "start")
    T(W - 60, sy + 26, "이 경로의 AI 모델 호출 0 — 판정은 전부 코드", "tag2", "end")
    return svg(W, H, "멀티 에이전트 워크플로")


# ───────────── 그림 2 · 시스템 아키텍처 ─────────────
def architecture():
    S.clear()
    W, H = 1500, 1130
    T(40, 44, "그림 2 · 시스템 아키텍처 — 클라이언트 · 백엔드 서버 · 백그라운드 워커 · 저장소 · 외부 API", "cap", "start")
    T(40, 66, "화살표 = 데이터가 흐르는 방향 (양쪽 화살촉 = 주고받음) · 금색 점선 = 비동기(큐) · 회색 점선 = 있으나 연결 확인 안 됨 (MCP 서버: 툴 3개는 있으나 바깥 접속용 기동 경로를 코드에서 못 찾음)", "s", "start")

    # 1층 접점
    T(40, 108, "클라이언트", "cap", "start")
    ux = [(40, "휴대폰 웹", "Next.js 16 · React 19"), (330, "개인 AI 비서 앱", "우리 API로 연결 (REST · MCP)"),
          (620, "여행계획서 링크", "로그인 없음 · 늘 최신"), (910, "운영자", "오류 알림 · 운영 콘솔(읽기 전용)"), (1200, "디스코드", "고객 알림 (지금은 채널 하나)")]
    for x, t, s in ux:
        node(x, 120, 260, 70, t, [s], "user")

    # 2층 백엔드
    by, bh = 240, 470
    R(40, by, W - 80, bh, "band", 12)
    T(60, by + 28, "백엔드 서버 — FastAPI (단일 PC)", "h", "start")
    lanes = [(60, "API 레이어 — REST", ["웹 API", "여행 API", "케이스 API", "여행계획서 페이지", "MCP 서버 (툴 3개)"],
              "HTTP 요청 (웹 · AI 앱 · MCP)", "JSON 응답 · 계획서 페이지"),
             (390, "서비스 레이어 — 에이전트 미경유", ["계획서 파싱 (규칙 우선 · AI는 위치만)", "일정 생성 (AI는 순서만)", "채팅 처리 (분류 → 대안 선택)"],
              "계획 원문(글 · 사진 · 파일) · 채팅 문장", "일정 항목(값 · 근거 줄) · 새 버전"),
             (750, "오케스트레이션 레이어", ["오케스트레이터 · 상태 머신 12개", "검증기 (Validator) · 반영기 (Apply)", "에이전트 2 — 요식 · 액티비티"],
              "케이스", "새 일정 버전 · 아웃박스 메시지"),
             (1110, "툴 · 통합 레이어", ["툴 레이어 (허용 목록 · 12회)", "외부 API 어댑터 (1차 ↔ 폴백)", "이동 판정 모듈 (공용 툴)"],
              "툴 이름 · 인자", "조회 값 또는 「모름」 (지어내지 않음)")]
    lw = [300, 330, 330, 330]
    for (x, t, items, gets, gives), w in zip(lanes, lw):
        R(x, by + 46, w, bh - 66, "lane", 10)
        T(x + w / 2, by + 74, t, "h2")
        R(x + 14, by + 371, 38, 18, "pill-in", 4)
        T(x + 33, by + 385, "받음", "pill")
        T(x + 60, by + 384, gets, "s", "start")
        R(x + 14, by + 401, 38, 18, "pill-out", 4)
        T(x + 33, by + 415, "냄", "pill")
        T(x + 60, by + 414, gives, "s", "start")
        for i, it in enumerate(items):
            cls = "agent" if "에이전트 2" in it else "tool" if "이동 판정" in it else ("core" if x in (390, 750) else "node")
            dash = "MCP" in it
            R(x + 16, by + 92 + i * 52, w - 32, 40, cls, 8, dash)
            T(x + w / 2, by + 117 + i * 52, it, "s2")
    # 레인 사이 화살표
    for x1, x2 in ((360, 390), (720, 750), (1080, 1110)):
        P([(x1, by + 200), (x2 - 2, by + 200)])

    # 접점 → API 층 (서로 엇갈리지 않게 꺾어 내림)
    P([(170, 190), (170, 205), (100, 205), (100, by - 2)])
    P([(460, 190), (460, 215), (190, 215), (190, by - 2)])
    P([(750, 190), (750, 225), (280, 225), (280, by - 2)])
    L(330, 209, "REST · MCP 요청", "lbl")
    L(520, 219, "링크 열기", "lbl")
    P([(1040, by), (1040, 192)])
    L(1052, 222, "오류 알림", "lbl", "start")

    # 3층 상시 작업
    jy = 750
    R(40, jy, W - 80, 104, "band", 12)
    T(60, jy + 28, "백그라운드 워커 — 별도 프로세스 (스케줄러가 1분마다 실행)", "h", "start")
    jobs = [(60, "모니터링 · 1분", "90분 안 일정 항목 점검"), (330, "새벽 점검 · 03~08시", "그날 영업시간 확인"),
            (600, "일정 알림", "하루 시작 · 다음 일정 · 출발"), (870, "복구 스위퍼", "멈춘 케이스 재처리"), (1140, "아웃박스 워커", "큐 → 디스코드 · 재시도 3회")]
    for x, t, s in jobs:
        node(x, jy + 40, 250, 54, t, [s], "job" if x < 1140 else "queue")
    P([(165, jy), (165, by + bh + 2)])
    L(177, jy - 14, "케이스 생성 → 오케스트레이터", "lbl", "start")
    # 비동기: 아웃박스 워커 → 디스코드
    P([(1390, jy + 67), (1474, jy + 67), (1474, 155), (1462, 155)], "edge async", "g")
    L(1466, jy - 12, "비동기 큐", "lbl-g", "end")

    # 4층 저장소 · 모델
    sy = 890
    node(40, sy, 700, 96, "PostgreSQL 16 + pgvector", ["케이스 · 실행 기록(State) · 여행 · 일정 버전 · 아웃박스 큐", "장소 · 요식 DB(식당 1,225곳) · 규정 문서 임베딩"], "db")
    node(770, sy, 330, 96, "AI 모델 — 시험 중", ["로컬 · API 비교 중 (아직 안 정함)", "임베딩 bge-m3"], "model")
    node(1145, sy, 315, 96, "시간표 데이터", ["지하철 · 버스 46만 행", "이동 판정 모듈이 읽음"], "db")
    P([(590, by + bh + 2), (590, sy - 2)], both=True)
    L(602, sy - 16, "읽기 · 쓰기", "lbl", "start")
    P([(860, by + bh + 2), (860, sy - 2)], "edge dim", "a", both=True)
    L(872, sy - 16, "요청 · 응답 (계획서 파싱 · 분류 · 문장만)", "lbl", "start")

    # 5층 외부
    ey = 1020
    node(40, ey, W - 80, 70, "외부 API", ["기상(Open-Meteo ↔ 기상청) · 기상 특보 · 지진 · 재난문자 · 교통(ITS ↔ UTIC) · 대기질 · 관광공사 · 카카오 · Google 장소(새벽만)"], "ext")
    P([(1130, ey), (1130, by + bh + 2)])
    L(1118, ey - 12, "조회 결과 (읽기만)", "lbl", "end")
    P([(1145, sy + 48), (1130, sy + 48)], mk=None)
    L(1140, sy + 40, "시간표", "lbl", "end")
    return svg(W, H, "시스템 아키텍처")


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
@media print{{.diagram{{break-inside:avoid;overflow:visible}}.diagram svg{{min-width:0 !important;max-height:250mm;width:auto !important;max-width:100%;margin:0 auto}}}}
"""

CHECK_WF = [
    ("멀티에이전트 = 역할별로 도구를 나누고 흐름을 코드로 설계 (0715)", "요식 · 액티비티가 각자 쓸 조회 툴 목록을 따로 갖고(이동은 둘이 같이 부르는 공용 판정 모듈), 흐름은 오케스트레이터가 코드로 정한다"),
    ("감독자(Supervisor) 패턴 — 가운데 라우터가 하나를 골라 맡김 (0715 · 0716)", "오케스트레이터가 문제 코드 앞부분으로 에이전트 하나를 고른다. 에이전트끼리 직접 부르지 않는다"),
    ("라우터는 허용 범위 밖이면 조용한 기본값 대신 사유를 남긴다 (0715)", "받는 에이전트가 정확히 하나가 아니면 「담당 없음」 오류로 기록한다"),
    ("반복에는 반드시 종료 조건 · 상한 (0716 실패 지점 표)", "안쪽 루프 — 후보 3곳 · 조회 12번 · 90초 / 바깥 루프 — 여행이 끝나면 멈춤"),
    ("상태 충돌 · 재실행 부작용 방지 (0716)", "판 번호가 맞을 때만 쓴다 · 같은 변경 · 같은 알림은 한 번만(중복 방지 키)"),
    ("부분 실패는 대체 · 부분 결과로 (0716)", "1차 데이터가 안 되면 대체 소스, 대체까지 안 되면 「문제 없음」으로 넘기지 않고 오류 기록"),
    ("양식 2.3 — 공유 상태 키를 밝힌다", "그림 아래 초록 띠 — 케이스 · 일정 버전 · 아웃박스 큐"),
]
CHECK_SA = [
    ("프론트엔드와 백엔드를 나눈다", "휴대폰 웹(Next.js) ↔ 백엔드(FastAPI)"),
    ("백엔드 안에서 에이전트 제어와 외부 연동 층을 나눠 그린다", "API 레이어 · 서비스 레이어 · 오케스트레이션 레이어 · 툴/통합 레이어 네 칸"),
    ("에이전트 사이 공유 상태와 상태 전이를 보인다", "그림 1의 초록 띠(공유 상태)와 상태기계 12종"),
    ("오래 걸리는 처리의 비동기 경로를 밝힌다", "아웃박스 큐(DB) → 아웃박스 워커 → 디스코드, 금색 점선"),
    ("MCP 호스트 ↔ 서버 연결선", "개인 AI 비서 앱(호스트) → 우리 MCP 서버(도구 3개). 외부 접속을 띄우는 경로는 코드에서 못 찾아 점선"),
]
NOT_USED = [
    ("LangGraph", "쓰지 않는다 — 같은 역할(상태 · 노드 · 분기 · 반복)을 컨트롤러와 상태기계 12종이 한다"),
    ("Redis · MySQL", "쓰지 않는다 — 상태 · 대기열 · 데이터 모두 PostgreSQL 하나"),
    ("GraphDB(Neo4j)", "쓰지 않는다 — 문서 검색은 규정 조각 벡터 검색(pgvector) 하나"),
    ("평가 에이전트 · 복구 에이전트", "따로 없다 — 검사는 오케스트레이터의 검증기(코드), 복구는 안쪽 루프 · 대체 소스"),
    ("고객 건을 사람에게 넘기기", "없다 — 운영자는 오류 알림만 받는다"),
]


def table(head, rows):
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


def main():
    f1, f2 = workflow(), architecture()
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>guguroute 한눈에</title><style>{CSS}</style></head><body><main>
<h1>guguroute 한눈에 — 멀티 에이전트 워크플로 · 시스템 아키텍처</h1>
<p class="note">2026-10-02 · v4 · 그리는 내용: 부트캠프 양식 「AI 시스템 아키텍처(멀티 에이전트)」 · 「시스템 구성도」 작성 가이드 · 그리는 법: 교재 0715 · 0716 LangGraph 멀티에이전트 · 사실: final_project_cs 코드</p>
<div class="lead">일정이 깨지면 <b>오케스트레이터</b>(흐름을 정하는 서버 코드 — 우리 문서에서 「코어」라고 부르던 것)가 담당 에이전트 하나에게 맡기고, 에이전트는 대체 후보를 통과할 때까지 다시 점검해 <b>제안</b>만 돌려줍니다. 코어가 검사해 새 일정 판과 알림을 내고, 이것을 <b>여행이 끝날 때까지</b> 되풀이합니다. 시스템은 휴대폰 웹 · 개인 AI 비서 앱으로 들어와 백엔드 한 곳에서 처리되고, 공유 State 와 알림 큐는 PostgreSQL 하나에 둡니다.</div>

<h2>1. 멀티 에이전트 워크플로</h2>
<div class="diagram">{f1}</div>
<p class="note">그리는 법(교재) → 이 그림에서</p>
{table(["교재 · 양식의 기준", "이 그림에서"], CHECK_WF)}

<h2>2. 시스템 아키텍처</h2>
<div class="diagram">{f2}</div>
<p class="note">양식 「시스템 구성도」 작성 가이드 → 이 그림에서</p>
{table(["양식의 기준", "이 그림에서"], CHECK_SA)}

<h2>3. 양식 예시에는 있지만 우리는 쓰지 않는 것</h2>
{table(["양식 예시", "우리"], NOT_USED)}
</main></body></html>"""
    (OUT / "triPilot_아키텍처_한눈에_v4.html").write_text(page, encoding="utf-8")
    print("ok", len(page) // 1024, "KB")


if __name__ == "__main__":
    main()
