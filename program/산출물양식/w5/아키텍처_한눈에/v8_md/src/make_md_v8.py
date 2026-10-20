# -*- coding: utf-8 -*-
"""guguroute Multi-Agent 구조도 — 참고 md(team_branch/me/Multi-Agent구조도참고.md) 형식 그대로 (2026-10-02, v8)

    python make_md_v8.py   → ../triPilot_Multi-Agent구조도_v8.md

★줄 맞춤: 칸(셀) 단위 그림판에 그린다. 한글은 2칸, 상자 선 · 영문은 1칸.
  폭이 글꼴마다 달라지는 글자(가운뎃점 · 줄표 · 동그라미 숫자 · ▼◀)는 그림 안에 쓰지 않는다 — 검사로 막는다.
★사실 기준: v7 그림과 같다(코드 확인 2026-10-02) — 에이전트는 요식 · 액티비티 둘, 이동은 공용 툴,
  판정은 코드, AI 모델은 시험 중, 계획 검증 SSE · 로그인 · AWS 배포는 아직 없음.
"""
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent
LINES = set("─│┌┐└┘┬┴├┤┼")


def cw(c):
    return 2 if unicodedata.east_asian_width(c) in "WF" else 1


def dw(s):
    return sum(cw(c) for c in s)


class Canvas:
    def __init__(self, w, h):
        self.w, self.g = w, [[" "] * w for _ in range(h)]

    def put(self, x, y, s):
        for c in s:
            assert c in LINES or unicodedata.east_asian_width(c) != "A", f"폭이 애매한 글자: {c!r} in {s!r}"
            if cw(c) == 2:
                self.g[y][x], self.g[y][x + 1] = c, None
                x += 2
            else:
                self.g[y][x] = c
                x += 1
        return x

    def center(self, x1, x2, y, s):
        self.put(x1 + (x2 - x1 + 1 - dw(s)) // 2, y, s)

    def hline(self, x1, x2, y, c="─"):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.g[y][x] = c

    def vline(self, x, y1, y2, c="│"):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.g[y][x] = c

    def box(self, x, y, w, h, title=None, lines=(), ctitle=False):
        self.hline(x, x + w - 1, y)
        self.hline(x, x + w - 1, y + h - 1)
        self.vline(x, y, y + h - 1)
        self.vline(x + w - 1, y, y + h - 1)
        self.g[y][x], self.g[y][x + w - 1], self.g[y + h - 1][x], self.g[y + h - 1][x + w - 1] = "┌", "┐", "└", "┘"
        yy = y + 1
        for t in ([title] if isinstance(title, str) else (title or [])):
            assert dw(t) <= w - 4, (t, dw(t), w)
            if ctitle:
                self.center(x + 1, x + w - 2, yy, t)
            else:
                self.put(x + 2, yy, t)
            yy += 1
        for ln in lines:
            assert dw(ln) <= w - 4, (ln, dw(ln), w)
            self.put(x + 2, yy, ln)
            yy += 1
        return y + h

    def frame_title(self, x, y, w, t):
        self.center(x + 1, x + w - 2, y, " " + t + " ")

    def render(self):
        return "\n".join("".join(c for c in row if c is not None).rstrip() for row in self.g)


def io_box(cv, x, y, w, title, ins, outs, sub=None):
    lines = []
    for i, s in enumerate(ins):
        lines.append(("I: " if i == 0 else "   ") + s)
    for i, s in enumerate(outs):
        lines.append(("O: " if i == 0 else "   ") + s)
    titles = [title] + ([sub] if sub else [])
    h = len(titles) + len(lines) + 2
    cv.box(x, y, w, h, titles, lines, ctitle=True)
    return y + h


def diagram1():
    BW, CX, LOOP = 80, 39, 84      # 상자 폭, 가운데 열, 바깥 루프 선 열
    cv = Canvas(90, 140)
    y = 0
    y = io_box(cv, 0, y, BW, "여행자 / 모바일 웹앱 (자체 채팅)",
               ["여행 계획(글, 사진, 파일), 채팅 요청, 신고(늦어요, 문 닫았어요)"],
               ["검증된 일정, 바뀐 일정 + 바꾼 이유, 다른 안, 휴대폰 알림"])
    cv.g[y - 1][CX] = "┬"; cv.put(CX, y, "│"); cv.put(CX, y + 1, "v"); y += 2
    y = io_box(cv, 0, y, BW, "FastAPI 서버 (REST API, 같은 서버 안에서 아래를 부른다)",
               ["HTTP 요청 + 브라우저 키 (로그인은 예정)"],
               ["고객 확인, 여행 ID, JSON 응답, 바뀜 신호(SSE)"])
    cv.g[y - 1][CX] = "┬"; cv.put(CX, y, "│"); cv.put(CX, y + 1, "v"); y += 2

    # ── 1. 계획 확인 (틀)
    fy = y
    a = y + 2
    a_end = cv.box(4, a, 50, 6, "계획 읽기 + 장소 확인", ["I : 계획 원문", "O : 일정 항목(시각, 장소) + 근거 줄", "    LLM 은 원문 줄 위치만 찾는다"])
    cv.g[a_end - 1][20] = "┬"; cv.put(20, a_end, "v")
    b = a_end + 1
    b_end = cv.box(4, b, 56, 9, "검증 체크리스트", ["I : 일정 항목", "O : 항목마다 통과 / 실패 + 이유",
                                                "    음식점: 영업, 브레이크, 라스트오더, 휴무", "    액티비티: 운영일, 운영시간, 날씨 조건",
                                                "    부가 정보(검증 아님): 주차, 대기 시간 링크",
                                                "    진행 상황을 화면에 순서대로 표시 (SSE, 예정)"])
    cv.g[b_end - 1][31] = "┬"
    cv.put(31, b_end, "│"); cv.put(31, b_end + 1, "v")
    d = b_end + 2
    cv.box(22, d, 21, 3, "전부 통과 ?", ctitle=True)
    cv.g[d + 2][26] = "┬"; cv.g[d + 2][38] = "┬"
    cv.put(27, d + 3, "YES"); cv.put(39, d + 3, "NO")
    cv.vline(26, d + 3, d + 11); cv.put(26, d + 12, "v"); cv.vline(38, d + 3, d + 4); cv.put(38, d + 5, "v")
    f = d + 6
    cv.box(28, f, 36, 4, None, ["실패 항목: 채팅으로 대안 추천", "고쳐서 다시 입력 / 부족하면 거절"])
    # 되돌림 루프: f 상자 오른쪽 → 위로 → 검증 체크리스트 아래 선으로
    cv.hline(64, 68, f + 2); cv.g[f + 2][68] = "┘"
    cv.vline(68, b_end + 1, f + 1); cv.g[b_end][68] = "┐"
    cv.hline(32, 67, b_end); cv.put(32, b_end, "<")
    cv.put(70, f + 1, "다시 검증"); cv.put(70, f + 2, "(되돌림)")
    cv.put(46, f + 4, "(거절은 예정)")
    cv.put(16, d + 13, "등록 + 여행계획서 링크 (로그인 없이 열림)")
    fh = (d + 16) - fy
    cv.box(0, fy, BW, fh)
    cv.frame_title(0, fy, BW, "1. 계획 확인 (등록할 때 한 번)")
    cv.vline(26, d + 14, d + 14)
    y = fy + fh
    cv.g[y - 1][26] = "┬"; cv.vline(26, y, y + 1); cv.put(28, y, "등록하면 감시 시작"); cv.put(26, y + 2, "v"); y += 3

    # ── 트리거 (바깥 루프가 돌아오는 곳)
    trig = y
    y = io_box(cv, 0, y, BW, "트리거 (다음 트리거 대기)",
               ["현재 일정 버전", "외부 데이터 6종(기상, 특보, 지진, 재난문자, 교통, 대기질)"],
               ["문제 항목 + 원인"],
               sub="감시 1분(앞으로 90분 안 항목), 새벽 03~08시(그날 영업), 고객 신고")
    loop_top = trig + 2
    cv.hline(BW, LOOP, loop_top); cv.put(BW, loop_top, "<")
    cv.g[y - 1][CX] = "┬"; cv.put(CX, y, "│"); cv.put(CX, y + 1, "v"); y += 2
    y = io_box(cv, 0, y, BW, "오케스트레이터 (Supervisor)",
               ["문제 항목 + 원인"],
               ["케이스 1건, 담당 에이전트 1개(요식 또는 액티비티)",
                "할 일 + 허용 툴 + 90초 + 컨텍스트(현재 일정, 원인, 규정)",
                "에이전트끼리 직접 부르지 않는다: 모든 연결은 오케스트레이터를 거친다"],
               sub="규칙 라우팅: 문제 코드 앞부분 -> 담당 1개")
    cv.g[y - 1][CX] = "┬"; cv.put(CX, y, "│"); cv.put(CX, y + 1, "v"); y += 2

    # ── Worker Agent (틀) — 안쪽 루프
    wy = y
    r = y + 2
    cv.box(3, r, 36, 6, "요식 에이전트", ["I : 식사 항목, 원인, 식이 조건", "O : 대체 식당 1 + 다른 안 2", "    또는 그대로 / 못 함"])
    cv.box(41, r, 36, 6, "액티비티 에이전트", ["I : 활동 항목, 원인, 실내 여부", "O : 대체 활동 + 다른 안,", "    바꿀까요? / 그대로 / 못 함"])
    j = r + 6
    cv.g[r + 5][21] = "┬"; cv.g[r + 5][59] = "┬"
    cv.vline(21, j, j); cv.vline(59, j, j)
    cv.hline(21, 59, j + 1); cv.g[j + 1][21] = "└"; cv.g[j + 1][59] = "┘"; cv.g[j + 1][CX] = "┬"
    cv.put(44, j, "둘 다 같은 흐름")
    cv.put(CX, j + 2, "v")
    k = j + 3
    cv.box(20, k, 40, 3, "현재 항목 재점검 (같은 외부 점검)", ctitle=True)
    cv.g[k + 2][CX] = "┬"; cv.put(CX, k + 3, "v")
    d1 = k + 4
    cv.box(30, d1, 19, 3, "문제 있나 ?", ctitle=True)
    cv.hline(49, 55, d1 + 1); cv.put(50, d1 + 1, "NO"); cv.put(56, d1 + 1, "> 그대로 (영향 없음)")
    cv.g[d1 + 2][CX] = "┬"; cv.put(CX + 2, d1 + 3, "YES"); cv.vline(CX, d1 + 3, d1 + 3); cv.put(CX, d1 + 4, "v")
    r1 = d1 + 5
    cv.box(18, r1, 44, 6, "다음 후보 1곳 재점검", ["순위순, 같은 외부 점검", "+ 이동 판정 툴 (앞뒤 구간 제시간?)", "통과하면 후보 목록에 담는다"])
    cv.g[r1 + 5][CX] = "┬"; cv.put(CX, r1 + 6, "v")
    d2 = r1 + 7
    cv.box(30, d2, 19, 3, "더 볼 후보 ?", ctitle=True)
    # 안쪽 루프: d2 오른쪽 → 위로 → r1 오른쪽으로 들어감
    cv.hline(49, 68, d2 + 1); cv.put(51, d2 + 1, "YES"); cv.g[d2 + 1][68] = "┘"
    cv.vline(68, r1 + 2, d2); cv.g[r1 + 2][68] = "┐"
    cv.hline(62, 67, r1 + 2); cv.put(62, r1 + 2, "<")
    cv.put(70, r1 + 3, "안쪽 루프"); cv.put(70, r1 + 4, "다음 후보")
    cv.g[d2 + 2][CX] = "┬"; cv.vline(CX, d2 + 3, d2 + 3); cv.put(CX + 2, d2 + 3, "NO (다 봤거나 최대 3곳, 툴 12회, 90초)"); cv.put(CX, d2 + 4, "v")
    d3 = d2 + 5
    cv.box(29, d3, 21, 3, "통과한 곳 있나 ?", ctitle=True)
    cv.hline(50, 55, d3 + 1); cv.put(51, d3 + 1, "NO"); cv.put(56, d3 + 1, "> 못 함 (일정 유지)")
    cv.g[d3 + 2][CX] = "┬"; cv.put(CX + 2, d3 + 3, "YES"); cv.vline(CX, d3 + 3, d3 + 3); cv.put(CX, d3 + 4, "v")
    cv.center(1, BW - 2, d3 + 5, "변경 제안 (최선 1곳 + 다른 안 최대 2개)")
    wh = d3 + 7 - wy
    cv.box(0, wy, BW, wh)
    cv.frame_title(0, wy, BW, "Worker Agent (둘 중 하나가 받는다)")
    y = wy + wh
    cv.g[y - 1][CX] = "┬"; cv.put(CX, y, "│"); cv.put(CX, y + 1, "v"); y += 2

    y = io_box(cv, 0, y, BW, "검증 + 반영 (오케스트레이터)",
               ["변경 제안 + 근거"],
               ["새 일정 버전(이전 보존) / 사용자에게 묻기 / 거부(일정 유지, 오류 알림)",
                "묻기 조건: 설문 먼저 물어봐, 고객이 고정한 일정, 안전 경보",
                "묻기 -> 알림, 채팅으로 다른 안 제시 -> 응답 오면 다시 검증"],
               sub="근거가 있나, 그 고객 것인가, 케이스 버전이 그대로인가")
    cv.g[y - 1][CX] = "┬"; cv.put(CX, y, "│"); cv.put(CX, y + 1, "v"); y += 2
    y = io_box(cv, 0, y, BW, "알림 (아웃박스 -> 워커 -> 디스코드)",
               ["새 일정 버전 + 알림 문구"],
               ["휴대폰 알림(디스코드, 지금은 팀 채널 하나), 계획서 링크 갱신",
                "바뀜 신호(SSE) / 같은 알림은 한 번만, 실패하면 3번까지 다시"])
    cv.g[y - 1][CX] = "┬"; cv.put(CX, y, "│"); cv.put(CX, y + 1, "v"); y += 2
    # 여행 끝?
    cv.box(29, y, 21, 3, "여행 끝 ?", ctitle=True)
    cv.put(2, y + 1, "그대로 / 못 함 / 거부"); cv.hline(24, 28, y + 1); cv.put(28, y + 1, ">")
    cv.put(2, y + 2, "(모든 결과가 모인다)")
    cv.hline(50, LOOP, y + 1); cv.put(52, y + 1, "NO"); cv.put(56, y, "바깥 루프: 트리거로")
    cv.g[y + 1][LOOP] = "┘"
    cv.vline(LOOP, loop_top + 1, y); cv.g[loop_top][LOOP] = "┐"
    cv.g[y + 2][CX] = "┬"; cv.put(CX + 2, y + 3, "YES"); cv.vline(CX, y + 3, y + 3); cv.put(CX, y + 4, "v"); cv.put(CX - 1, y + 5, "끝")
    cv.g = cv.g[:y + 6]
    return cv.render()


def diagram2():
    cv = Canvas(90, 60)
    cv.put(8, 0, "요식 에이전트"); cv.put(36, 0, "액티비티 에이전트")
    cv.vline(14, 1, 1); cv.vline(44, 1, 1)
    cv.hline(14, 44, 2); cv.g[2][14] = "└"; cv.g[2][44] = "┘"; cv.g[2][29] = "┬"
    cv.vline(29, 3, 3); cv.put(31, 3, "툴 호출 (허용된 툴만)"); cv.put(29, 4, "v")
    y = cv.box(10, 5, 66, 13, ["툴 레이어 (ReadToolbox)", "MCP 가 아니라 같은 서버 안 호출"],
               ["read.itinerary()           지금 일정 버전", "read.disruptions()         외부 데이터 6종 점검",
                "read.dining_state()        그 시각 영업, 라스트오더", "read.dining_alternatives() 대체 식당 후보",
                "read.place_catalog()       대체 장소 후보", "read.policy()              규정 조각 (규정 질문일 때)",
                "", "목록 밖 툴은 거부, 같은 호출 두 번 거부, 12번 넘으면 멈춤", "값이 없으면 없음이 아니라 모름으로 돌려준다"], ctitle=False)
    cv.g[y - 1][43] = "┬"; cv.vline(43, y, y)
    cv.hline(14, 72, y + 1); cv.g[y + 1][14] = "┌"; cv.g[y + 1][72] = "┐"; cv.g[y + 1][43] = "┴"
    cv.put(14, y + 2, "v"); cv.put(43, y + 2, "v"); cv.put(72, y + 2, "v")
    b = y + 3
    cv.box(0, b, 28, 10, "PostgreSQL + pgvector", ["여행, 일정 버전", "케이스, 실행 기록", "장소, 요식 DB", "규정 조각 + 임베딩", "(bge-m3)", "상태와 근거의 정본"], ctitle=False)
    cv.box(29, b, 28, 10, "외부 API 6종", ["기상(Open-Meteo/기상청)", "기상 특보, 지진", "재난문자", "교통(ITS/UTIC)", "대기질", "1차 실패 -> 대체 소스"], ctitle=False)
    cv.box(58, b, 28, 10, "시간표 데이터", ["지하철, 버스", "시간표 46만 행", "", "이동 판정 툴", "(공용, 에이전트 아님)", "제시간? 성립 / 불가"], ctitle=False)
    e = b + 10
    for x in (14, 43, 72):
        cv.g[e - 1][x] = "┬"; cv.vline(x, e, e + 1)
    cv.put(16, e, "일정, 장소"); cv.put(45, e, "외부 점검"); cv.put(74, e, "이동 판정")
    cv.hline(14, 72, e + 2); cv.g[e + 2][14] = "└"; cv.g[e + 2][72] = "┘"; cv.g[e + 2][43] = "┬"
    cv.vline(43, e + 3, e + 3); cv.put(43, e + 4, "v")
    cv.center(0, 86, e + 5, "근거(무엇을, 언제 확인) + 판정")
    cv.vline(43, e + 6, e + 6); cv.put(43, e + 7, "v")
    cv.center(0, 86, e + 8, "요식 / 액티비티 에이전트")
    cv.g = cv.g[:e + 9]
    return cv.render()


TABLE = """| 구성 | 주요 Input | 주요 Output | 주요 역할 |
|---|---|---|---|
| **트리거** (감시 · 새벽 점검 · 고객 신고) | 현재 일정 버전, 외부 데이터 6종, 고객 신고 문장 | 문제 항목 + 원인 | 깨어날 때를 정한다 — 1분마다 앞으로 90분 안 항목, 새벽 03~08시 그날 영업 |
| **오케스트레이터** | 문제 항목 + 원인 | 케이스, 담당 에이전트 1개, 할 일 · 허용 툴 · 90초 · 컨텍스트 | 규칙 라우팅 · 흐름 관리 (에이전트끼리 직접 부르지 않는다) |
| **요식 에이전트** | 식사 항목(장소 · 시각 · 인원), 원인, 식이 조건 | 그대로 / 대체 식당 1 + 다른 안 2 / 못 함 + 사유 | 영업 · 브레이크 · 라스트오더 · 휴무 점검 → 후보 재점검 루프 |
| **액티비티 에이전트** | 활동 항목(장소 · 시각 · 실내 여부), 원인, 설문 | 그대로 / 대체 활동 + 다른 안 / 「바꿀까요?」 / 못 함 | 운영일 · 운영시간 · 날씨 · 대기질 점검 → 후보 재점검 루프 |
| **이동 판정 툴** (공용 · 에이전트 아님) | 출발지, 도착지, 출발 시각 | 제시간? 성립 / 불가, 경로 · 소요 · 요금, 근거 등급 | 후보 재점검 · 반영 때 앞뒤 구간 판정 (시간표 46만 행) |
| **검증 + 반영** (오케스트레이터) | 변경 제안 + 근거 | 새 일정 버전 / 사용자에게 묻기 / 거부 | 근거 · 고객 소유 · 버전 확인, 먼저 물어봐 · 고정 일정 · 안전 경보면 묻기 |
| **알림** (아웃박스 워커) | 새 일정 버전 + 알림 문구 | 휴대폰 알림, 계획서 링크 갱신, 바뀜 신호(SSE) | 같은 알림은 한 번만, 실패하면 3번까지 다시 |
| **계획 읽기** (LLM 호출) | 계획 원문(글 · 사진 · 파일) | 일정 항목 + 근거 줄 | 규칙이 먼저 읽고, LLM 은 원문 줄 위치만 — 판정에는 쓰지 않는다 |"""


def main():
    md = f"""guguroute 의 **Multi-Agent 구조**는 다음처럼 정리할 수 있습니다. 핵심은 **오케스트레이터가 문제 하나마다 담당 에이전트 1개(요식 또는 액티비티)를 고르고, 에이전트는 허용된 툴로만 데이터를 읽어 대체 후보를 통과할 때까지 다시 점검하며(안쪽 루프), 결과는 검증 · 반영 · 알림을 거쳐 여행이 끝날 때까지 다시 트리거를 기다리는(바깥 루프)** 구조입니다. 이동은 에이전트가 아니라 두 에이전트와 반영 단계가 함께 부르는 **공용 판정 툴**입니다.

## Multi-Agent 전체 구조도

```text
{diagram1()}
```

## Agent와 Tool / Data 계층 관계

특히 **에이전트가 DB · 외부 API 에 직접 접근하는 것이 아니라 툴 레이어(허용 목록)를 통해서만 조회**하도록 보는 것이 중요합니다. 판정은 코드가 하고, 값이 없으면 「없음」이 아니라 「모름」으로 돌려줍니다.

```text
{diagram2()}
```

### Agent별 I/O 요약

{TABLE}

이 구조에서 에이전트 사이의 연결은 **오케스트레이터**(에이전트끼리 직접 부르지 않음), 에이전트와 데이터의 연결은 **툴 레이어**(허용 목록 · 12회 상한), 데이터는 **PostgreSQL + 외부 API 6종 + 시간표**, 담당 선택과 결과 검증은 **오케스트레이터**가 담당하는 구조입니다. AI 모델은 계획서 줄 위치 찾기 · 분류 · 문장에만 쓰고(모델은 로컬 · API 비교 시험 중), 일정 판정에는 쓰지 않습니다.

시스템 구성도에서는 이를 **`트리거 → 오케스트레이터 → Worker Agent(후보 재점검 루프) → 검증 · 반영 → 알림 → 여행 끝? → 트리거`**의 순환형 구조로 표현하면 guguroute 의 핵심 — 계획을 받아 여행이 끝날 때까지 지킨다 — 이 가장 명확하게 드러납니다.

> 지금 상태: 계획 검증 진행 표시(SSE) · 로그인 · AWS 자동 배포는 아직 없음(예정). 알림은 팀 디스코드 채널 하나로 나간다(개인 디스코드는 등록 · 시험 발송까지). 이동은 코드에 아직 팀으로 등록돼 있어 툴로 정리가 필요하다.
"""
    (OUT / "triPilot_Multi-Agent구조도_v8.md").write_text(md, encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
