import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
new = open(os.path.join(HERE, "wf6.py"), encoding="utf-8").read()
i = s.index("# ───────────── 그림 1"); j = s.index("# ───────────── 그림 2")
s = s[:i] + new + s[j:]


def R_(a, b):
    global s
    assert s.count(a) == 1, (a[:90], s.count(a))
    s = s.replace(a, b)


# 화살촉 · 클래스
R_('("n", "ah-n"), ("o", "ah-o"), ("p", "ah-p")))', '("n", "ah-n"), ("o", "ah-o"), ("p", "ah-p"), ("t", "ah-t")))')
R_('@media print{{.diagram', '''.diagram .big{{font-size:26px;font-weight:800}} .diagram .band-a{{fill:#f6f9ff;stroke:#9db8e6;stroke-width:1.4}} .diagram .band-b{{fill:#fbfaf6;stroke:#d9c79a;stroke-width:1.4}}
.diagram .band-t{{fill:#1f3a6e;font-size:18px;font-weight:800}} .diagram .gloss{{fill:#fff;stroke:#c3cad6}} .diagram .num{{fill:var(--gold);font-family:{MONO};font-size:15px;font-weight:700}}
.diagram .tg-done{{fill:#e6f4ea;stroke:#5fae78}} .diagram .tg-wip{{fill:#e8f0fd;stroke:#6f9be0}} .diagram .tg-plan{{fill:#f3f3f3;stroke:#9aa3ae;stroke-dasharray:3 2}} .diagram .tg-t{{font-size:11.5px;font-weight:700;fill:#2b3442}}
.diagram .k-t{{fill:#8a5a00;font-size:13px;font-weight:700}} .diagram .k-in{{fill:#2f6c9a;font-size:13px;font-weight:700}} .diagram .k-ck{{fill:#3d7a4f;font-size:13px;font-weight:700}}
.diagram .k-out{{fill:#a8720c;font-size:13px;font-weight:700}} .diagram .k-ex{{fill:#727d90;font-size:13px;font-weight:700}} .diagram .k-ev{{fill:#6a54c9;font-size:13px;font-weight:700}}
.diagram .screen{{fill:#fff;stroke:#1f3a6e;stroke-width:1.6}} .diagram .ck-ok{{fill:#2f6cd0;font-size:13.5px;font-weight:600}} .diagram .ck-bad{{fill:#c0392b;font-size:13.5px;font-weight:600}}
.diagram .res{{fill:#fff;stroke:#c3cad6}} .diagram .plan-box{{fill:#fafafa;stroke:#9aa3ae;stroke-dasharray:5 4}} .diagram .role-g{{fill:#3d7a4f;font-family:{MONO};font-size:12px}}
.diagram .agent-wrap{{fill:#fff;stroke:#7aa6e0;stroke-width:1.4;stroke-dasharray:6 4}} .diagram .edge.tl{{stroke:#3d7a4f;stroke-width:1.5;stroke-dasharray:6 4}} .diagram .lbl-gr{{fill:#3d7a4f;font-size:12.5px;font-weight:600}} .diagram .ah-t{{fill:#3d7a4f}}
@media print{{.diagram''')

# 그림 2 — 멘토 지적 반영
R_('"FastAPI 서버 + 오케스트레이터 + 워커 에이전트 2 + 공용 툴 + 상시 감시 — 여행 일정을 끝날 때까지 지킨다"',
   '"모바일 앱 + FastAPI 서버 + 오케스트레이터 + 에이전트 2 + 공용 툴 + 상시 감시 — 여행 일정을 끝날 때까지 지킨다"')
R_('T(120, 138, "1. 사용자 / Client", "bh-blue")', 'T(120, 138, "1. 사용자 — 모바일", "bh-blue")')
R_('for i, t in enumerate(("· 휴대폰 웹 (Next.js)", "· 개인 AI 비서 앱", "· 여행계획서 링크")):',
   'for i, t in enumerate(("· 모바일 웹앱", "  (자체 채팅 · 일정)", "· 여행계획서 링크", "· 외부 AI 앱 (보조)")):')
R_('T(46, 250 + i * 22, t, "s2", "start")', 'T(46, 246 + i * 21, t, "s2", "start")')
R_('''    for i, t in enumerate(("· 웹 API · 여행 API", "· 케이스 API · 계획서 페이지", "· MCP 서버 (툴 3개)")):
        T(336, 214 + i * 19, t, "s2", "start")
    R(334, 270, 222, 102, "endpoint", 8)
    T(445, 287, "주요 Endpoint", "bh-green")
    for i, t in enumerate(("POST /v1/web/trip-intakes", "POST /v1/trips/{id}/messages", "POST /v1/trips/{id}/reports", "GET  /plan/{trip_id}")):
        T(346, 305 + i * 17, t, "mono", "start")''', '''    for i, t in enumerate(("· REST API — 계획 · 채팅 · 신고", "· SSE — 바뀜 신호 (구현)", "· MCP — 외부 AI 앱용 (보조)")):
        T(336, 214 + i * 19, t, "s2", "start")
    R(334, 278, 222, 40, "plan-box", 8)
    T(346, 303, "로그인", "h2", "start")
    tag(404, 301, "plan")
    T(456, 303, "우선 구현", "s", "start")
    R(334, 326, 222, 44, "plan-box", 8)
    T(346, 345, "SSE — 검증 진행 스트림", "s2", "start")
    tag(500, 343, "plan")
    T(346, 363, "계획 확인 중 화면 이탈해도 유지", "s", "start")''')
R_('T(264, 317, "(HTTP Response)", "fl2")', 'T(264, 317, "(HTTP · SSE)", "fl2")')
R_('T(840, 155, "(같은 FastAPI 프로세스 안 · 파이썬 코드)", "fl2")', 'T(840, 155, "(같은 FastAPI 서버 안)", "fl2")')
R_('''    cards = [(676, 168, "계획서 파싱", "규칙 우선", "AI는 줄 위치만"), (848, 168, "일정 생성", "후보는 우리 DB에서", "AI는 순서만"),
             (676, 272, "채팅 처리", "분류 → 대안 선택", "에이전트 안 거침"), (848, 272, "오케스트레이터", "상태 머신 12개", "담당 라우팅")]''',
   '''    cards = [(676, 168, "계획 읽기", "규칙 우선", "AI는 줄 위치만"), (848, 168, "계획 검증", "체크리스트 ✔ / ✖", "유형별 항목 (진행 중)"),
             (676, 272, "채팅 처리", "대안 추천", "재입력 안내"), (848, 272, "오케스트레이터", "담당 에이전트 고르기", "흐름 관리")]''')
R_('"이동 판정 모듈", "공용 툴 (에이전트 아님)"', '"이동 판정 툴", "공용 (에이전트 아님)"')
R_('R(1100, 430, 370, 400, "b-orange", 12)', 'R(1100, 430, 370, 470, "b-orange", 12)')
R_('''    ic_clock(1136, 517)''', '''    ic_clock(1136, 517)
    R(1118, 820, 334, 60, "plan-box", 8)
    T(1285, 843, "사용자 제보 공유", "h2")
    T(1285, 864, "내비 앱처럼 다른 사용자가 본 상황 받기", "s")
    tag(1376, 841, "look")''')
R_('T(380, 766, "7. 알림 · 계획서 갱신", "bh-green")', 'T(380, 766, "7. 휴대폰 알림 · 계획서", "bh-green")')
R_('T(380, 788, "아웃박스 큐 → 워커 → 디스코드", "s")', 'T(380, 788, "아웃박스 → 워커 → 디스코드 → 휴대폰", "s")')
R_('T(380, 807, "재시도 3회 · 중복 0 · 링크는 늘 최신", "s")', 'T(380, 807, "개인 디스코드 등록 됨 · 발송은 팀 채널", "s")')
R_('    W, H = 1500, 1090\n', '    W, H = 1500, 1160\n')
R_('    by = 860\n', '    by = 930\n')
R_('''(565, 300, "인프라 / 라이브러리", ["FastAPI · Next.js 16", "PostgreSQL 16 + pgvector", "Ollama (로컬 모델 시험)", "Docker (CI 빌드) · GitHub Actions"]),''',
   '''(565, 300, "인프라 · 배포", ["FastAPI · React(Next.js) · PostgreSQL", "CI — GitHub Actions 시험 · 빌드 (완료)", "CD — AWS 자동 배포 (아직 안 됨)", "AI — Ollama 로컬 모델 (시험 중)"]),''')
R_('(("n", "주요 데이터 흐름"), ("a", "내부 연동"), ("o", "감시 데이터 흐름"), ("p", "State 흐름"), ("r", "실패 · 오류 알림"))',
   '(("n", "주요 데이터 흐름"), ("a", "내부 연동"), ("o", "감시 데이터 흐름"), ("p", "State 흐름"), ("r", "실패 · 오류 알림"))')
R_('T(30, H - 22, "※ 사용자가 올린 계획은', 'T(30, H - 22, "※ 점선 회색 상자 = 예정 · 검토 중. 사용자가 올린 계획은')

# 파일 이름 · 문서
s = s.replace("triPilot_아키텍처_한눈에_v5.html", "triPilot_아키텍처_멘토반영_v6.html").replace("· v5 ·", "· v6 ·")
i = s.index("CHECK_WF = ["); j = s.index("def table(")
s = s[:i] + '''MENTOR = [
    ("2회차 09-11", "아키텍처는 세부 컨트롤러 구조 말고 큰 그림으로", "그림 2 — 상태 머신 · 엔드포인트 목록 같은 세부를 빼고 블록 7개로"),
    ("2회차", "「팀 모듈」 같은 개발 용어 대신 에이전트 설명으로", "「모듈」을 빼고 「이동 판정 툴」 · 에이전트 카드로 설명"),
    ("2회차 · 3회차", "각 에이전트를 트리거 → 인풋 → 아웃풋으로 정의 · 트리거는 구체적으로", "그림 1 ② 에이전트 카드 — 트리거 · 받음 · 점검 · 냄 줄 (「일정 사고 문의」 대신 「식사 90분 전 재난문자 · 지진 · 도로 통제」처럼)"),
    ("2회차", "단순 LLM 호출과 에이전트 플로우를 구분", "그림 1 위 오른쪽 상자 — LLM 호출은 줄 위치 · 분류 · 문장만, 에이전트는 트리거 → 조회 → 판단 → 반복"),
    ("2회차 · 3회차", "에이전트 플로우 전체 아키텍처를 한눈에", "그림 1 한 장에 ① 계획 확인 + ② 지속 관리"),
    ("2회차 · 3회차", "정량 평가 기준을 미리 정의", "에이전트 카드 「평가」 줄 — 잰 값만 적고, 없는 것은 「기준 만드는 중」"),
    ("2회차", "진입은 외부 서비스(ChatGPT) 경유 말고 자체 채팅", "그림 2 사용자 블록 — 모바일 웹앱 자체 채팅이 주, 외부 AI 앱은 보조"),
    ("2회차", "실시간 대기 시간은 직접 제공 어려움 → 링크 안내", "요식 카드 「부가」 — 지도 링크로 안내"),
    ("3회차 09-14", "용어(「여행코어」 등)를 먼저 정의하고 쓰기", "그림 1 맨 위 용어 상자"),
    ("3회차", "CI/CD — AWS 자동 배포", "그림 2 아래 「인프라 · 배포」 — CI 완료 · CD 아직 안 됨"),
    ("4회차 10-01", "한 장으로 이해되는 플로우, 인풋 · 아웃풋 명시", "그림 1 전체 — 상자마다 받음 · 냄"),
    ("4회차", "계획 확인 중 SSE 스트림 처리 (화면 이탈 시 재처리 문제)", "그림 1 ① 5단계 · 그림 2 FastAPI 블록 — 예정으로 표시 (바뀜 신호 SSE 는 이미 있음)"),
    ("4회차", "Validation 체크리스트 고도화 — 유형별 세분화 · 진행 상황 노출 · 파랑/빨강", "그림 1 ① 4 · 5단계 — 음식점 · 액티비티 항목, ✔ 파랑 · ✖ 빨강"),
    ("4회차", "Validation 항목과 부가 정보 구분 (예: 주차)", "그림 1 ① 결과 줄 · 카드 「부가」 줄"),
    ("4회차", "실패 항목은 채팅으로 대안 · 재입력 유도, 확인 불가면 거절", "그림 1 ① 6 결과"),
    ("4회차", "고정 설문 대신 계획서 분석 + 대화형 질문", "그림 1 ① 6 결과 아래 — 예정"),
    ("4회차", "로그인 우선 (복구 이메일보다 먼저)", "그림 2 FastAPI 블록 — 로그인 예정"),
    ("4회차", "모바일 우선 · 폰으로 실제 알림", "그림 2 사용자 블록 · 7 휴대폰 알림"),
    ("4회차", "실시간 정보 공유 구조 (내비 앱 방식) 리서치", "그림 1 트리거 · 그림 2 감시 파이프라인 — 검토 중"),
]
NOT_HERE = [
    ("타겟 — 외국인 제외 · 「유능한 개인 여행 비서」", "서비스 기획 · 발표 내용 — 그림에는 국적 표시를 넣지 않았다"),
    ("발표 자료 구성 · 경쟁 서비스 비교 · 근거 데이터", "발표 자료 몫"),
    ("타임라인 UI · 검사 단계 화면 디자인", "화면 설계 몫 — 플로우에는 ✔/✖ 표시 방식만 넣었다"),
    ("앱 배포 후 6명 직접 사용 · 토요일 시연", "할 일 — 그림 대상 아님"),
]


''' + s[j:]
i = s.index('    page = f"""'); j = s.index('    (OUT / "triPilot_아키텍처_멘토반영_v6.html")')
s = s[:i] + '''    page = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>triPilot 멘토 반영 플로우</title><style>{CSS}</style></head><body><main>
<h1>triPilot — 멀티 에이전트 플로우 · 시스템 구성도 (멘토링 반영)</h1>
<p class="note">2026-10-02 · v6 · 멘토링 수행일지 2~4회차(09-11 · 09-14 · 10-01)에서 시스템 아키텍처 · 에이전트 플로우에 대한 지적만 골라 반영 · 형식은 부트캠프 참고 구성도(AI Agent 구현실습3 원본 7 · 29쪽) · 사실은 final_project_cs 코드</p>
<div class="lead">멘토 지적 19개를 반영했습니다. 그림 1은 <b>한 장</b>에 ① 계획을 올릴 때의 검증과 ② 여행 중 지속 관리를 담고, 에이전트마다 <b>트리거 · 받음 · 점검 · 냄 · 평가</b>를 적었습니다. 그림 2는 세부를 빼고 <b>큰 그림</b>으로 줄였습니다. 아직 없는 것(SSE 검증 스트림 · 로그인 · 대화형 성향 질문 · AWS 배포)은 「예정」으로 표시했습니다.</div>

<h2>1. 멀티 에이전트 플로우 — 한 장</h2>
<div class="diagram">{f1}</div>

<h2>2. 시스템 구성도</h2>
<div class="diagram">{f2}</div>

<h2>3. 멘토 지적 → 그림에서</h2>
{table(["회차", "멘토 지적", "그림에서"], MENTOR)}

<h2>4. 일지에 있지만 이 그림의 대상이 아닌 것</h2>
{table(["지적", "왜 여기 없나"], NOT_HERE)}
</main></body></html>"""
''' + s[j:]
open(p, "w", encoding="utf-8").write(s)
print("patched")
