# -*- coding: utf-8 -*-
"""triPilot 한눈에 — 멀티 에이전트 워크플로 · 시스템 아키텍처 (2026-10-02, v1)

    python make_arch_v1.py   → ../triPilot_아키텍처_한눈에_v1.html

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


def P(pts, cls="edge", mk="a"):
    d = "M" + " L".join(f"{x} {y}" for x, y in pts)
    m = f' marker-end="url(#{mk})"' if mk else ""
    S.append(f'<path class="{cls}" d="{d}"{m}/>')


def L(x, y, s, cls="lbl", anchor="middle"):
    T(x, y, s, cls, anchor)


DEFS = ('<defs>'
        + "".join(f'<marker id="{i}" viewBox="0 0 10 10" markerWidth="8" markerHeight="8" refX="9" refY="5" orient="auto"><path class="{c}" d="M0 0 L10 5 L0 10 Z"/></marker>'
                  for i, c in (("a", "ah"), ("g", "ah-g"), ("r", "ah-r"), ("b", "ah-b")))
        + '</defs>')


def svg(W, H, label):
    return f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(label)}">{DEFS}{"".join(S)}</svg>'


# ───────────── 그림 1 · 멀티 에이전트 워크플로 ─────────────
def workflow():
    S.clear()
    W, H = 1500, 860
    T(40, 44, "그림 1 · 멀티 에이전트 워크플로 — 감독자(Supervisor) 패턴 · 상태 그래프", "cap", "start")
    T(40, 66, "상자 = 하는 일(노드) · 마름모 = 갈림길(조건 분기) · 금색 = 되풀이(루프) · 붉은색 = 못 했을 때 · 파란 상자 = 에이전트 · 금색 상자 = 코어(감독자)", "s", "start")

    # 윗줄 — 왼쪽에서 오른쪽
    yc = 230
    S.append(f'<circle class="start" cx="66" cy="{yc}" r="14"/>')
    L(66, yc + 34, "시작")
    node(110, yc - 45, 200, 90, "깨우기", ["감시 1분마다 · 새벽 점검", "고객 신고"])
    node(360, yc - 45, 200, 90, "처리 건 열기", ["깨진 일정 항목마다 1건", "AI 분류 안 부름"], "core", "코어")
    node(610, yc - 55, 230, 110, "감독자 — 담당 고르기", ["문제 코드 앞부분으로", "에이전트 하나 (규칙 라우터)", "일감 + 근거 묶음을 넘김"], "core", "코어")
    P([(80, yc), (108, yc)])
    P([(310, yc), (358, yc)])
    P([(560, yc), (608, yc)])

    ax, aw, ah = 930, 250, 78
    agents = [("요식 에이전트", "영업 · 라스트오더 · 외부 6종"), ("액티비티 에이전트", "운영 · 날씨 · 대기질 · 특보"), ("이동 에이전트", "경로 · 교통 사건 · 시간표")]
    ays = [yc - 150, yc - 39, yc + 72]
    for (nm, sub), ay in zip(agents, ays):
        node(ax, ay, aw, ah, nm, [sub, "깨졌으면 대체 후보"], "agent")
        P([(840, yc), (880, yc), (880, ay + ah / 2), (ax - 2, ay + ah / 2)])
    L(880, ays[2] + ah + 24, "조건 분기 — 셋 중 하나", "lbl", "middle")

    # 안쪽 루프 — 에이전트 오른쪽
    lx = ax + aw + 40
    P([(ax + aw, ays[2] + 60), (lx, ays[2] + 60), (lx, ays[0] + 18), (ax + aw + 2, ays[0] + 18)], "edge loop", "g")
    L(lx + 12, yc - 36, "안쪽 루프", "lbl-g", "start")
    L(lx + 12, yc - 16, "다시 점검에 걸리면", "lbl", "start")
    L(lx + 12, yc + 2, "다음 후보로", "lbl", "start")
    L(lx + 12, yc + 26, "종료 조건", "lbl-g", "start")
    L(lx + 12, yc + 44, "후보 최대 3곳", "lbl", "start")
    L(lx + 12, yc + 62, "조회 12번 · 90초", "lbl", "start")

    # 에이전트 → 결과 검사 (오른쪽으로 모여 아래로)
    jx = ax + aw / 2
    yb = 540
    P([(jx, ays[2] + ah), (jx, yb - 47)])
    L(jx + 10, ays[2] + ah + 30, "결과지 — 제안만 낸다 (직접 안 바꿈)", "lbl", "start")

    # 아랫줄 — 오른쪽에서 왼쪽
    node(jx - 120, yb - 45, 240, 90, "결과 검사", ["근거가 있나 · 정말 그 고객 것인가", "판 번호가 그대로인가"], "core", "코어")
    diamond(845, yb, 160, 90, "통과?")
    P([(jx - 120, yb), (927, yb)])
    node(520, yb - 45, 210, 90, "적용 — 새 일정 판", ["설문 「먼저 물어봐」·고정 일정", "·안전 경보면 묻기만"], "core", "코어")
    P([(765, yb), (732, yb)])
    L(748, yb - 10, "예", "lbl")
    node(270, yb - 45, 200, 90, "알림 · 계획서", ["디스코드 1번 · 링크 새 판", "다른 안 · 되돌리기 가능"], "core", "코어")
    P([(520, yb), (472, yb)])
    diamond(140, yb, 150, 84, "여행 끝?")
    P([(270, yb), (217, yb)])
    S.append(f'<circle class="end" cx="140" cy="{yb + 120}" r="14"/><circle class="end-in" cx="140" cy="{yb + 120}" r="8"/>')
    P([(140, yb + 42), (140, yb + 104)])
    L(152, yb + 76, "예", "lbl", "start")
    L(140, yb + 156, "끝", "lbl")

    # 바깥 루프 — 여행 끝? 아니오 → 깨우기
    P([(140, yb - 42), (140, yc + 47)], "edge loop", "g")
    L(152, (yb + yc) / 2 - 8, "아니오 — 바깥 루프", "lbl-g", "start")
    L(152, (yb + yc) / 2 + 12, "여행이 끝날 때까지 다음 감시 · 새벽 · 신고", "lbl", "start")

    # 못 했을 때
    node(720, yb + 90, 250, 74, "일정 그대로", ["바꿀 것 없음 · 못 함이면 오류 기록", "운영자에게 오류 알림만"], "fail")
    P([(845, yb + 45), (845, yb + 88)], "edge bad", "r")
    L(857, yb + 72, "아니오", "lbl-r", "start")
    P([(720, yb + 127), (180, yb + 127), (180, yb + 22)], "edge bad", "r")

    # 공유 상태 띠
    sy = 760
    R(40, sy, W - 80, 74, "state", 8)
    T(60, sy + 26, "공유 상태 (DB)", "h2", "start")
    T(60, sy + 50, "처리 건 — 상태 12종 · 판 번호 · 무엇이 깨졌나 · 담당 에이전트   |   여행 — 일정 판(옛 판 보존)   |   보낼 함 — 알림 대기열", "s", "start")
    T(60, sy + 68, "모든 노드가 이 상태를 읽고, 판 번호가 맞을 때만 쓴다 — 사이에 다른 쓰기가 있었으면 그 결과는 버린다", "s", "start")
    T(W - 60, sy + 26, "이 경로에서 AI 모델 호출 0 — 판정은 전부 코드", "tag2", "end")
    return svg(W, H, "멀티 에이전트 워크플로")


# ───────────── 그림 2 · 시스템 아키텍처 ─────────────
def architecture():
    S.clear()
    W, H = 1500, 1040
    T(40, 44, "그림 2 · 시스템 아키텍처 — 접점 · 백엔드 · 상시 작업 · 저장소 · 외부", "cap", "start")
    T(40, 66, "실선 = 요청 · 금색 점선 = 비동기(대기열) · 회색 점선 = 있으나 연결 확인 안 됨 (MCP 서버: 도구 3개는 있으나 바깥에서 접속하게 띄우는 경로를 코드에서 못 찾음)", "s", "start")

    # 1층 접점
    T(40, 108, "사용자 접점", "cap", "start")
    ux = [(40, "휴대폰 웹", "Next.js 16 · React 19"), (330, "개인 AI 비서 앱", "우리 API로 연결 (REST · MCP)"),
          (620, "여행계획서 링크", "로그인 없음 · 늘 최신"), (910, "운영자", "오류 알림 · 읽기 전용 화면(별도 앱)"), (1200, "디스코드", "고객 알림 (지금은 채널 하나)")]
    for x, t, s in ux:
        node(x, 120, 260, 70, t, [s], "user")

    # 2층 백엔드
    by, bh = 240, 380
    R(40, by, W - 80, bh, "band", 12)
    T(60, by + 28, "백엔드 — FastAPI (한 대 PC에 상주)", "h", "start")
    lanes = [(60, "API 층", ["웹 API", "여행 API", "사건 접수 API", "여행계획서 페이지", "MCP 서버 (도구 3개)"]),
             (390, "코어 처리 — 에이전트 안 거침", ["계획 읽기 (규칙 먼저 · AI는 줄 위치만)", "일정 짜기 (AI는 순서만)", "채팅 창구 (분류 → 대체 고르기)"]),
             (750, "에이전트 제어 — 감독자", ["컨트롤러 · 상태기계 12종", "결과 검사 · 적용기", "에이전트 3 — 요식 · 액티비티 · 이동"]),
             (1110, "외부 연동 층", ["조회 도구 (허용 목록 · 12번)", "외부 API 연결 (1차 ↔ 대체)", "시간표 판정기"])]
    lw = [300, 330, 330, 330]
    for (x, t, items), w in zip(lanes, lw):
        R(x, by + 46, w, bh - 66, "lane", 10)
        T(x + w / 2, by + 74, t, "h2")
        for i, it in enumerate(items):
            cls = "agent" if "에이전트 3" in it else ("core" if x in (390, 750) else "node")
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
    L(330, 209, "REST · MCP", "lbl")
    L(520, 219, "링크 열기", "lbl")
    P([(1040, by), (1040, 192)])
    L(1052, 222, "오류 알림", "lbl", "start")

    # 3층 상시 작업
    jy = 660
    R(40, jy, W - 80, 104, "band", 12)
    T(60, jy + 28, "상시 작업 — 따로 도는 프로세스", "h", "start")
    jobs = [(60, "감시 · 1분마다", "앞으로 90분 안의 항목 점검"), (330, "새벽 점검 · 03~08시", "그날 영업 확인"),
            (600, "일정 알림", "하루 시작 · 다음 일정 · 출발"), (870, "되잡기", "멈춘 처리 건 다시 잡기"), (1140, "배달 일꾼", "보낼 함 → 디스코드 · 3번 재시도")]
    for x, t, s in jobs:
        node(x, jy + 40, 250, 54, t, [s], "job" if x < 1140 else "queue")
    P([(165, jy), (165, by + bh + 2)])
    L(177, jy - 14, "처리 건을 열어 감독자에게", "lbl", "start")
    # 비동기: 배달 일꾼 → 디스코드
    P([(1390, jy + 67), (1474, jy + 67), (1474, 155), (1462, 155)], "edge async", "g")
    L(1466, jy - 12, "비동기 대기열", "lbl-g", "end")

    # 4층 저장소 · 모델
    sy = 800
    node(40, sy, 700, 96, "PostgreSQL 16 + pgvector", ["처리 건 · 실행 기록(상태) · 여행 · 일정 판 · 보낼 함(알림 대기열)", "장소 표 · 요식 원장(식당 1,225곳) · 규정 조각 임베딩"], "db")
    node(770, sy, 330, 96, "AI 모델 — 시험 중", ["로컬 · API 비교 중 (아직 안 정함)", "임베딩 bge-m3"], "model")
    node(1145, sy, 315, 96, "시간표 파일", ["지하철 · 버스 46만 행", "이동 판정에 씀"], "db")
    P([(320, by + bh), (320, sy - 2)])
    P([(860, by + bh), (860, sy - 2)], "edge dim", "a")
    L(872, sy - 16, "계획 읽기 · 분류 · 문장만", "lbl", "start")

    # 5층 외부
    ey = 930
    node(40, ey, W - 80, 70, "외부 API", ["기상(Open-Meteo ↔ 기상청) · 기상 특보 · 지진 · 재난문자 · 교통(ITS ↔ UTIC) · 대기질 · 관광공사 · 카카오 · Google 장소(새벽만)"], "ext")
    P([(1130, by + bh), (1130, ey - 2)])
    P([(1130, sy + 48), (1143, sy + 48)])
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
.diagram .ah{{fill:var(--muted)}} .diagram .ah-g{{fill:var(--gold)}} .diagram .ah-r{{fill:var(--red)}} .diagram .ah-b{{fill:var(--blue)}}
@media print{{.diagram{{break-inside:avoid;overflow:visible}}.diagram svg{{min-width:0 !important;max-height:250mm;width:auto !important;max-width:100%;margin:0 auto}}}}
"""

CHECK_WF = [
    ("멀티에이전트 = 역할별로 도구를 나누고 흐름을 코드로 설계 (0715)", "요식 · 액티비티 · 이동이 각자 쓸 조회 도구 목록을 따로 갖고, 흐름은 코어(감독자)가 코드로 정한다"),
    ("감독자(Supervisor) 패턴 — 가운데 라우터가 하나를 골라 맡김 (0715 · 0716)", "감독자가 문제 코드 앞부분으로 에이전트 하나를 고른다. 에이전트끼리 직접 부르지 않는다"),
    ("라우터는 허용 범위 밖이면 조용한 기본값 대신 사유를 남긴다 (0715)", "받는 에이전트가 정확히 하나가 아니면 「담당 없음」 오류로 기록한다"),
    ("반복에는 반드시 종료 조건 · 상한 (0716 실패 지점 표)", "안쪽 루프 — 후보 3곳 · 조회 12번 · 90초 / 바깥 루프 — 여행이 끝나면 멈춤"),
    ("상태 충돌 · 재실행 부작용 방지 (0716)", "판 번호가 맞을 때만 쓴다 · 같은 변경 · 같은 알림은 한 번만(중복 방지 키)"),
    ("부분 실패는 대체 · 부분 결과로 (0716)", "1차 데이터가 안 되면 대체 소스, 대체까지 안 되면 「문제 없음」으로 넘기지 않고 오류 기록"),
    ("양식 2.3 — 공유 상태 키를 밝힌다", "그림 아래 초록 띠 — 처리 건 · 일정 판 · 보낼 함"),
]
CHECK_SA = [
    ("프론트엔드와 백엔드를 나눈다", "휴대폰 웹(Next.js) ↔ 백엔드(FastAPI)"),
    ("백엔드 안에서 에이전트 제어와 외부 연동 층을 나눠 그린다", "API 층 · 코어 처리 · 에이전트 제어(감독자) · 외부 연동 층 네 칸"),
    ("에이전트 사이 공유 상태와 상태 전이를 보인다", "그림 1의 초록 띠(공유 상태)와 상태기계 12종"),
    ("오래 걸리는 처리의 비동기 경로를 밝힌다", "보낼 함(DB 대기열) → 배달 일꾼 → 디스코드, 금색 점선"),
    ("MCP 호스트 ↔ 서버 연결선", "개인 AI 비서 앱(호스트) → 우리 MCP 서버(도구 3개). 외부 접속을 띄우는 경로는 코드에서 못 찾아 점선"),
]
NOT_USED = [
    ("LangGraph", "쓰지 않는다 — 같은 역할(상태 · 노드 · 분기 · 반복)을 컨트롤러와 상태기계 12종이 한다"),
    ("Redis · MySQL", "쓰지 않는다 — 상태 · 대기열 · 데이터 모두 PostgreSQL 하나"),
    ("GraphDB(Neo4j)", "쓰지 않는다 — 문서 검색은 규정 조각 벡터 검색(pgvector) 하나"),
    ("평가 에이전트 · 복구 에이전트", "따로 없다 — 검사는 코어의 코드, 복구는 안쪽 루프 · 대체 소스"),
    ("고객 건을 사람에게 넘기기", "없다 — 운영자는 오류 알림만 받는다"),
]


def table(head, rows):
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>"


def main():
    f1, f2 = workflow(), architecture()
    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>triPilot 한눈에</title><style>{CSS}</style></head><body><main>
<h1>triPilot 한눈에 — 멀티 에이전트 워크플로 · 시스템 아키텍처</h1>
<p class="note">2026-10-02 · v1 · 그리는 내용: 부트캠프 양식 「AI 시스템 아키텍처(멀티 에이전트)」 · 「시스템 구성도」 작성 가이드 · 그리는 법: 교재 0715 · 0716 LangGraph 멀티에이전트 · 사실: final_project_cs 코드</p>
<div class="lead">일정이 깨지면 <b>감독자(코어)</b>가 담당 에이전트 하나에게 맡기고, 에이전트는 대체 후보를 통과할 때까지 다시 점검해 <b>제안</b>만 돌려줍니다. 코어가 검사해 새 일정 판과 알림을 내고, 이것을 <b>여행이 끝날 때까지</b> 되풀이합니다. 시스템은 휴대폰 웹 · 개인 AI 비서 앱으로 들어와 백엔드 한 곳에서 처리되고, 상태와 알림 대기열은 PostgreSQL 하나에 둡니다.</div>

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
    (OUT / "triPilot_아키텍처_한눈에_v1.html").write_text(page, encoding="utf-8")
    print("ok", len(page) // 1024, "KB")


if __name__ == "__main__":
    main()
