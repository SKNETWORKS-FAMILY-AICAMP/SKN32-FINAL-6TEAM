# -*- coding: utf-8 -*-
"""에이전트(Team) 기능 정의서를 만든다.

★**전부 코드에서 뽑는다.** 2026-09-10 개정 — 앞판은 브리핑의 *설계안*을 옮겨
  적어서 실제 코드와 어긋났다. 지금은 `app/modules/travel_ops/` 의 manifest 를
  AST 로 읽어 넣는다.

  앞판이 틀렸던 것 — activity.request_change·refund.calculate·booking.status·
  dining.request_reservation 은 **구현에 없다.** mobility.route 는 실제로
  `mobility.check_route` 다. Lodging·Flight 는 capability 가 없다고 적었으나
  실제로는 `lodging.status`·`flight.status` 가 있다.

근거
  · final_project_cs/app/modules/travel_ops/*.py       여행 팀 manifest (AST)
  · final_project_cs/app/modules/customer_ops/*.py     커머스 팀 manifest (AST)
  · final_project_cs/config/project.yaml               등록 상태 · 모듈 토글
  · final_project_cs/app/presentation/a2a/             A2A 엔드포인트
  · program/plan/A-COP_Team모듈_계약사전과_빠진두단계.md  execute() 7단계

실행: python program/산출물양식/_build/build_에이전트기능정의서.py
"""
import ast
import os
import sys

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(FORMS))
CS = os.path.join(REPO, "final_project_cs")
OUT = os.path.join(FORMS, "[기획] 에이전트 기능 정의서_여행.xlsx")

# ── 서식 ──────────────────────────────────────────────────────────────
NAVY = "1F3864"
HEAD = PatternFill("solid", fgColor=NAVY)
SUB = PatternFill("solid", fgColor="D9E2F3")
MVP = PatternFill("solid", fgColor="FCE4E4")
CUT = PatternFill("solid", fgColor="F2F2F2")
STUB = PatternFill("solid", fgColor="EDEDED")
WARN = PatternFill("solid", fgColor="FFF2CC")
OFF = PatternFill("solid", fgColor="E7E6E6")
HEADF = Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF")
BOLD = Font(name="맑은 고딕", size=10, bold=True)
BASE = Font(name="맑은 고딕", size=10)
SMALL = Font(name="맑은 고딕", size=9, color="595959")
TITLE = Font(name="맑은 고딕", size=14, bold=True, color=NAVY)
THIN = Side(style="thin", color="B4C6E7")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
TOP = Alignment(vertical="top", wrap_text=True)
CTR = Alignment(vertical="center", horizontal="center", wrap_text=True)


def head(ws, row, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths), start=1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.fill, cell.font, cell.alignment, cell.border = HEAD, HEADF, CTR, BOX
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 30


def put(ws, row, values, fill=None, bold_first=False, height=None):
    for i, v in enumerate(values, start=1):
        cell = ws.cell(row=row, column=i, value=v)
        cell.font = BOLD if (bold_first and i == 1) else BASE
        cell.alignment, cell.border = TOP, BOX
        if fill:
            cell.fill = fill
    if height:
        ws.row_dimensions[row].height = height


def title(ws, text, sub=None, span=6):
    ws.cell(row=1, column=1, value=text).font = TITLE
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    if sub:
        c = ws.cell(row=2, column=1, value=sub)
        c.font, c.alignment = SMALL, Alignment(vertical="top", wrap_text=True)
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
        ws.row_dimensions[2].height = 28


def note(ws, row, text, span, fill=None, bold=False):
    c = ws.cell(row=row, column=1, value=text)
    c.font, c.alignment = (BOLD if bold else SMALL), TOP
    if fill:
        for i in range(1, span + 1):
            ws.cell(row=row, column=i).fill = fill
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    ws.row_dimensions[row].height = 30


# ── 코드에서 manifest 를 읽는다 ────────────────────────────────────────
def manifests(folder):
    """폴더 안 모든 .py 에서 `manifest = TeamManifest(...)` 를 AST 로 읽는다."""
    out = {}
    for root, _, names in os.walk(folder):
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError:
                continue
            for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
                for st in cls.body:
                    if not (isinstance(st, ast.Assign)
                            and getattr(st.targets[0], "id", "") == "manifest"):
                        continue
                    d = {}
                    for kw in st.value.keywords:
                        try:
                            d[kw.arg] = ast.literal_eval(kw.value)
                        except Exception:
                            d[kw.arg] = "<expr>"
                    d["_file"] = name
                    d["_class"] = cls.name
                    out[d.get("team_id", cls.name)] = d
    return out


TRAVEL = manifests(os.path.join(CS, "app/modules/travel_ops"))
COMMERCE = manifests(os.path.join(CS, "app/modules/customer_ops"))

# project.yaml 에 등록된 team_id (라우팅되는 것)
_yaml = open(os.path.join(CS, "config/project.yaml"), encoding="utf-8").read()
REGISTERED = set()
for line in _yaml.splitlines():
    s = line.strip()
    if s.startswith("- team_id:"):
        REGISTERED.add(s.split(":", 1)[1].strip())

j = lambda v: "\n".join(v) if isinstance(v, list) else ("—" if v in (None, "") else str(v))

wb = openpyxl.Workbook()

# ══════════════════════════════════════════════════════════ 1. 개요
ws = wb.active
ws.title = "개요"
title(ws, "에이전트(Team) 기능 정의서 — 여행 지속관리 CS 플랫폼",
      "A-COP · 2026-09-10 · manifest 는 코드에서 AST 로 읽었다. "
      "등록 여부는 config/project.yaml.", span=4)
r = 4
put(ws, r, ["항목", "내용"], bold_first=True)
for c in ws[r]:
    c.fill, c.font = SUB, BOLD
ws.column_dimensions["A"].width = 22
ws.column_dimensions["B"].width = 100
r += 1
for k, v in [
    ("이 문서가 정하는 것",
     "에이전트(Team) 하나가 무엇을 할 수 있고, 무엇을 입력받아, 어떻게 판정하고, "
     "무엇을 돌려주는가. capability 단위로 적는다."),
    ("이 문서가 안 정하는 것",
     "코어(Core)의 기능. Team 은 side effect 를 실행하지 않으므로 실행·통지·승인은 "
     "코어 몫이다 — 「코어 경계」 시트."),
    ("에이전트 = Team",
     "Registry 에 등록되는 Team 모듈을 뜻한다. 선언(manifest)·주입(도구)·"
     "단일 진입점(execute)·근거(evidence) 넷으로 이루어진다."),
    ("★등록과 구현은 다르다",
     "코드가 있어도 config/project.yaml 에 없으면 라우팅되지 않는다. "
     "커머스 6팀이 그 상태다 — 코드는 남기고 등록만 뺐다. 「기존 팀」 시트."),
    ("판정과 생성을 나눈다",
     "도메인 규칙 판정은 코드가 한다. LLM 은 깨졌을 때 대안을 만드는 데만 쓰고, "
     "만든 대안은 판정을 다시 통과해야 나간다(execute 7단계 ⑤→⑥)."),
    ("근거 의무",
     "모든 판정에 Evidence(출처·확인 시각)를 붙인다. 근거 없는 문장은 계약 단계에서 막힌다."),
    ("상태 표기",
     "[실측] 코드에서 확인 · [설계] 문서에 있으나 미구현 · [미정] 안 정해짐"),
]:
    put(ws, r, [k, v], bold_first=True, height=32)
    r += 1
r += 1
note(ws, r, "★ 2026-09-10 개정 — 앞판은 브리핑의 설계안을 옮겨 적어 코드와 어긋나 있었다. "
            "activity.request_change · refund.calculate · booking.status · dining.request_reservation 은 "
            "구현에 없고, mobility.route 는 실제로 mobility.check_route 다. 지금은 전부 코드에서 읽는다.",
     2, WARN, bold=True)

# ══════════════════════════════════════════════════════ 2. 에이전트 목록
ws = wb.create_sheet("에이전트 목록")
title(ws, "에이전트(Team) 목록 — 여행 도메인",
      "manifest 를 app/modules/travel_ops/ 에서 AST 로 읽었다. "
      "등록 여부는 config/project.yaml 의 teams 절.", span=11)
head(ws, 4, ["Team", "구분", "등록", "team_id", "capabilities", "accepted_case_types",
             "allowed_tools", "knowledge_scope", "max_steps", "default_capability", "구현 파일"],
     [16, 11, 9, 16, 30, 15, 22, 22, 9, 24, 20])

ORDER = [("activity", "MVP 필수", MVP), ("booking_handoff", "MVP 필수", MVP),
         ("dining", "절삭 가능", CUT), ("mobility", "절삭 가능", CUT),
         ("lodging", "등록만", STUB), ("flight", "등록만", STUB)]
r = 5
for tid, kind, fill in ORDER:
    d = TRAVEL.get(tid, {})
    put(ws, r, [d.get("display_name", tid), kind,
                "●" if tid in REGISTERED else "×", tid,
                j(d.get("capabilities")), j(d.get("accepted_case_types")),
                j(d.get("allowed_tools")), j(d.get("knowledge_scope")),
                d.get("max_steps"), d.get("default_capability"),
                f"travel_ops/{d.get('_file','?')}"],
        fill=fill, bold_first=True, height=62)
    r += 1
r += 1
for n in [
    "★ max_steps 는 Team 이 직접 넘겨야 상한이 걸린다 — tools.call(..., budget=self.manifest.max_steps).",
    "★ 여섯 팀 모두 required_context 가 같다 — case_state · policy · db_facts · history.",
    "★ 공통 계약 처리는 travel_ops/_base.py 에 모았다. 커머스에서 315줄 복붙돼 가드가 팀마다 달랐던 것(team_id 가드 1/6)을 막으려고 처음부터 한 곳에 뒀다.",
]:
    note(ws, r, n, 11)
    r += 1

# ══════════════════════════════════════════════════════ 3. 기존 팀
ws = wb.create_sheet("기존 팀")
title(ws, "기존 팀(커머스 v9) — 코드는 남고 등록만 빠졌다",
      "app/modules/customer_ops/ 는 지우지 않았다. 쇼핑몰 시절 기록이자 비교 대상이다. "
      "Registry 등록형이라 코어는 한 줄도 안 바뀐다 — 되돌리려면 project.yaml 의 teams 절만 되돌린다.",
      span=8)
head(ws, 4, ["기존 Team", "team_id", "capabilities", "accepted_case_types",
             "등록", "지금 상태", "→ 여행에서", "무엇이 같아서 이어받나"],
     [22, 22, 30, 18, 8, 16, 18, 52])

MAP = [
    ("return_refund", "미등록", "Activity",
     "취소 가능 판정 → 접수 → 환급액 계산의 3단 구조가 같다. "
     "반품 기한↔취소 기한, 배송비 부담↔우천 위약금율, 수량 초과↔인원 초과"),
    ("procurement_order_payment", "미등록", "Booking Handoff",
     "예약 생성·변경·취소·결제 상태의 자리가 같다"),
    ("fulfillment_logistics", "미등록", "Mobility",
     "움직이는 것을 추적하고 예외를 잡는 구조가 같다. "
     "배송 지연 판정↔환승·막차 지연, 미수령 조사↔경로 이탈"),
    ("catalog_verification", "미등록", "(자리 비어 있음)",
     "★외부 원장을 조회해 표시 내용을 대조하는 구조. **v9 의 A2A Remote 자리였다.** "
     "여행에 대응 팀을 안 만들어 A2A 시연 대상이 없다 — 「A2A · MCP」 시트"),
    ("response_generation_review", "미등록 · 토글 off",
     "(각 Team 내부 규칙으로 흡수)",
     "생성과 검수를 다른 주체가 하는 원칙은 살리되 별도 Team 으로 두지 않는다(v10 §5). "
     "★project.yaml 의 response_review.owner_team_id 가 아직 이 팀을 가리킨다 — "
     "enabled: false 라 안 터지지만 켜면 기동이 막힌다(가드가 잡는다)"),
    ("voc_store_manager", "미등록", "(만들지 않음)",
     "커머스에서도 껍데기였다(집계는 코어 1 소유). 여행에 자리를 안 만들었다"),
]
r = 5
for tid, state, to, why in MAP:
    d = COMMERCE.get(tid, {})
    put(ws, r, [d.get("display_name", tid), tid, j(d.get("capabilities")),
                j(d.get("accepted_case_types")),
                "●" if tid in REGISTERED else "×", state, to, why],
        fill=OFF, bold_first=True, height=64)
    r += 1
r += 1
note(ws, r, "★ 등록 열이 전부 × 다. 코드는 실재하고 KNOWN_IMPLEMENTATION_REFS 허용 목록에도 남아 있지만 "
            "config/project.yaml 의 teams 절에 없어서 라우팅되지 않는다. "
            "「코드가 있다」와 「돈다」는 다르다.", 8, WARN, bold=True)
r += 1
note(ws, r, "★ 이 표는 「무엇을 베꼈나」이지 「무엇인가」가 아니다. return_refund 줄이 Activity 를 환불 팀으로 "
            "만들지 않는다 — Activity 는 여행지에서 하는 활동 그 자체(경복궁 관람 포함)를 맡는다.", 8)

# ══════════════════════════════════════════════════════ 4. 기능 정의
ws = wb.create_sheet("기능 정의")
title(ws, "기능 정의 — capability 단위 (코드 실측)",
      "capability 하나가 기능 하나다. Registry 는 task 의 capability 가 manifest 에 있는지 보고 라우팅한다.",
      span=11)
head(ws, 4, ["기능 ID", "에이전트", "capability", "기능명", "하는 일",
             "판정 방식", "출력 NextAction", "쓰는 도구", "근거(Evidence)", "MVP", "상태"],
     [11, 15, 26, 18, 46, 22, 22, 20, 24, 7, 9])

FUNCS = [
    ("FN-ACT-01", "activity", "activity.check_feasible", "성립 판정",
     "이 시각에 이 활동이 성립하는지 본다. 운영일·운영시간·인원·이동 여유. "
     "★기본 capability(default_capability)다. 예약 없는 항목(경복궁 관람 등)도 여기로 온다.",
     "코드 — LLM 안 부름", "RESPOND\nESCALATE", "read.place\nread.policy",
     "운영 정보 출처 · 확인 시각", "●", "[실측]"),
    ("FN-ACT-02", "activity", "activity.check_cancelable", "취소 가능·위약금 판정",
     "지금 취소할 수 있는지와 위약금이 얼마인지 본다. "
     "예약 시각 − 현재 시각을 규정 시간과 대조하고 남은 시간 구간별 위약금율을 적용한다. "
     "★규정을 모르면 금액을 만들지 않는다.",
     "코드 — LLM 안 부름", "RESPOND\nWAIT_FOR_APPROVAL", "read.booking\nread.policy",
     "규정 조항 · 예약 원문 · 확인 시각", "●", "[실측]"),
    ("FN-ACT-03", "activity", "activity.propose_change", "대안 제안",
     "깨졌을 때 대안을 제안한다(승인 대기). 같은 시간대 대체 · 날짜 이동. "
     "생성한 대안은 판정을 다시 통과해야 나간다.",
     "코드 판정 → LLM 생성 → 코드 재검증", "WAIT_FOR_APPROVAL\nESCALATE (대안 없음)",
     "read.place\nread.policy\nread.booking", "운영 공지 · 규정 · 확인 시각", "●", "[실측]"),
    ("FN-ACT-W1", "activity", "(내부 · _weather_note)", "날씨 조건 판정",
     "규정에 기상 판단 기준 시각이 있는 경우만 본다(예: 티타임 2시간 전 강수량). "
     "capability 가 아니라 위 판정 안에서 부르는 내부 함수다.",
     "코드 — 규정에 기준이 있을 때만", "(판정 결과에 반영)", "read.weather",
     "예보 발표 시각 · 관측 시각", "●", "[실측]"),
    ("FN-BKG-01", "booking_handoff", "booking.verify", "예약 확인",
     "예약이 실재하고 우리가 아는 것과 같은지 대조한다. ★기본 capability다.",
     "코드 — LLM 안 부름", "RESPOND\nESCALATE (불일치)", "read.booking\nread.supplier",
     "공급자 응답 · 조회 시각", "●", "[실측]"),
    ("FN-BKG-02", "booking_handoff", "booking.prepare_change", "변경 인계 준비",
     "★기본 동작은 인계다. 무엇을 어떻게 바꿔야 하는지 정리해 넘긴다 — "
     "변경 링크 + 차액 + 대안. Team 이 실행하지 않는다.",
     "코드 — LLM 안 부름", "RESPOND (인계)\nWAIT_FOR_APPROVAL", "read.booking\nread.policy\nread.supplier",
     "공급자 규정 · 차액 근거", "●", "[실측]"),
    ("FN-BKG-03", "booking_handoff", "booking.prepare_cancel", "취소 인계 준비",
     "취소 조건·위약금을 정리해 인계한다. 실행하지 않는다.",
     "코드 — LLM 안 부름", "RESPOND (인계)\nWAIT_FOR_APPROVAL", "read.booking\nread.policy",
     "취소 규정 · 위약금 근거", "●", "[실측]"),
    ("FN-DIN-01", "dining", "dining.check_open", "영업 여부 판정",
     "★오늘 여는지가 아니라 그 일정 시각에 여는지를 본다. 제공자 영업시간은 "
     "오늘부터 7일의 예정이지 조회 순간의 개점 확인이 아니다 — confirmed_at 과 출처를 함께 남긴다. "
     "★기본 capability다.",
     "코드 — 확인 수준을 같이 저장", "RESPOND\nRESPOND(미확인 표시)", "read.place",
     "출처 · 확인 시각 · 확인 수준", "○", "[실측]"),
    ("FN-DIN-02", "dining", "dining.check_conditions", "동행 조건 판정",
     "아이 동반 · 할랄 · 채식 조건을 만족하는지 본다.",
     "코드 — LLM 안 부름", "RESPOND\nRESPOND(미확인 표시)", "read.place\nread.policy",
     "장소 속성 출처 · 확인 시각", "○", "[실측]"),
    ("FN-MOB-01", "mobility", "mobility.check_route", "구간 이동 성립 판정",
     "구간 이동 시간이 일정 간격 안에 드는지(여유), 환승이 성립하는지, 막차를 넘기지 않는지. "
     "★기본 capability다.",
     "코드 — 저장한 시간표로 판정", "RESPOND\nESCALATE (불성립)", "read.route\nread.transit",
     "시간표 출처 · 확인 시각", "○", "[실측]"),
    ("FN-MOB-02", "mobility", "mobility.status", "운행 상태 조회",
     "해당 구간의 현재 운행 정보를 조회해 돌려준다.",
     "코드 — LLM 안 부름", "RESPOND", "read.transit", "운행 정보 출처 · 조회 시각", "○", "[실측]"),
    ("FN-MOB-03", "mobility", "mobility.exception", "사건 대안 생성",
     "막차를 놓친 것처럼 이동이 깨진 경우 경로·순서를 재배열한다. "
     "★문의와 사건을 가르는 문구 판정이 함정이다 — 「막차가 몇 시인가요」(문의) 대 "
     "「막차를 놓쳤어요」(사건). 이 팀만 select_capability 훅을 갖는다.",
     "코드 판정 → 규칙 열거 → 코드 재검증", "RESPOND\nESCALATE (대안 없음)",
     "read.route\nread.transit\nread.policy", "시간표 · 규정 · 확인 시각", "○", "[실측]"),
    ("FN-LDG-01", "lodging", "lodging.status", "잠긴 예약 상태 조회",
     "숙박 예약을 잠긴 항목(locked)으로 취급해 상태만 돌려준다. 바꾸지 않는다. "
     "코어가 다른 일정을 짤 때 고정 항목으로 쓴다. max_steps 2.",
     "코드 — 조회만", "RESPOND", "read.booking", "예약 원문 · 조회 시각", "×", "[실측]"),
    ("FN-FLT-01", "flight", "flight.status", "잠긴 예약 상태 조회",
     "항공 예약을 잠긴 항목(locked)으로 취급해 상태만 돌려준다. 바꾸지 않는다. max_steps 2.",
     "코드 — 조회만", "RESPOND", "read.booking", "예약 원문 · 조회 시각", "×", "[실측]"),
]
r = 5
for f in FUNCS:
    fill = MVP if f[9] == "●" else (STUB if f[9] == "×" else CUT)
    put(ws, r, list(f), fill=fill, bold_first=True, height=74)
    r += 1
r += 1
note(ws, r, "MVP — ● 필수 · ○ 절삭 가능 · × 등록만.   상태 — [실측] 코드에서 확인 · [설계] 미구현. "
            "★기능 14개가 전부 [실측]이다(2026-09-10). 앞판은 전 행 [설계]로 적었는데 그 사이 구현됐다.",
     11, WARN, bold=True)

# ══════════════════════════════════════════════════════ 5. A2A · MCP
ws = wb.create_sheet("A2A · MCP")
title(ws, "외부 에이전트 연동 — A2A · MCP",
      "부트캠프 요구사항의 「다중 에이전트 서빙」과 「개인 AI 연동」이 여기 걸린다. "
      "★둘 다 들어오는 문이다 — 남이 우리를 부른다. 알림처럼 우리가 남을 부르는 것은 outbox 몫이다.",
      span=5)
head(ws, 4, ["구분", "무엇", "위치", "상태", "비고"], [14, 34, 40, 14, 46])
A2A = [
    ("A2A", "Agent Card 발견", "GET /.well-known/agent-card.json", "[실측] 구현",
     "app/presentation/a2a/agent_card.py 의 build_agent_card(registry) 가 만든다"),
    ("A2A", "Task 제출", "POST /a2a/tasks", "[실측] 구현", ""),
    ("A2A", "상태 조회", "GET /a2a/tasks/{task_id}", "[실측] 구현", "working → input-required 로 넘어간다"),
    ("A2A", "추가 입력 → 재개", "POST /a2a/tasks/{task_id}/input", "[실측] 구현",
     "v7 DoD-26 의 Card 발견 → working → input-required → 추가 입력 → Artifact 완료 왕복"),
    ("A2A", "취소", "POST /a2a/tasks/{task_id}/cancel", "[실측] 구현", ""),
    ("A2A", "원격 Team 실행기", "app/core/remote_team/a2a_executor.py",
     "[실측] 토글 off",
     "★config/project.yaml 의 modules.a2a_executor.enabled = false. "
     "코드는 있고 켜져 있지 않다"),
    ("A2A", "★원격 Team 데모 — 여행용", "app/modules/customer_ops/team_modules/remote_team_demo/",
     "[미확보] 빈 폴더",
     "★파일이 하나도 없다. v9 에서는 catalog_verification 이 A2A Remote 자리였는데 "
     "미등록이 되면서 여행에 대응 팀을 안 만들었다 — 시연 대상이 없다"),
    ("MCP", "list_cases", "app/presentation/api/mcp.py", "[실측] 구현", "required_scope = mcp:read"),
    ("MCP", "get_case_detail", "app/presentation/api/mcp.py", "[실측] 구현", "required_scope = mcp:read"),
    ("MCP", "open_support_case", "app/presentation/api/mcp.py", "[실측] 구현",
     "required_scope = mcp:read. Case 를 만들지만 바깥 세계를 안 바꾸므로 read 로 본다"),
    ("MCP", "모듈 토글", "config/project.yaml → modules.mcp.enabled", "[실측] true", ""),
]
r = 5
for a in A2A:
    fill = WARN if a[3].startswith("[미확보]") or "off" in a[3] else None
    put(ws, r, list(a), fill=fill, bold_first=True, height=46)
    r += 1
r += 1
note(ws, r, "★ 결론 — A2A 는 프로토콜 표면(엔드포인트 5개)이 다 구현돼 있는데 "
            "①실행기 토글이 꺼져 있고 ②여행 도메인에 원격 Team 이 없다. "
            "「구현이 없다」가 아니라 「켜고 붙일 대상을 안 정했다」가 맞는 서술이다.",
     5, WARN, bold=True)
r += 1
note(ws, r, "확인한 범위 — config/project.yaml, app/presentation/a2a/, app/core/remote_team/, "
            "app/presentation/api/mcp.py 를 열어 봤다. "
            "이 방법이 놓칠 수 있는 것: 런타임에 조립되는 등록이나 테스트 전용 배선은 정적 확인으로 안 잡힌다.", 5)

# ══════════════════════════════════════════════════════ 6. 처리 흐름
ws = wb.create_sheet("처리 흐름")
title(ws, "execute() 7단계 — 모든 에이전트가 같은 순서로 돈다",
      "브리핑은 다섯 칸으로 적었으나 v10 §5 는 일곱을 요구한다. ⑤ 생성과 ⑥ 재검증이 빠져 있었다.",
      span=5)
head(ws, 4, ["단계", "이름", "누가", "하는 일", "안 지키면"], [8, 14, 12, 56, 46])
for i, s in enumerate([
    ("1", "가드", "코드",
     "team_id 가 내 것인지 · capability 가 manifest 에 있는지 · context 가 degraded 인지",
     "다른 팀 일을 받거나 자료 없이 판정한다. 커머스에서 team_id 가드가 1/6 뿐이었다"),
    ("2", "준비", "코드", "seen 집합으로 같은 도구·같은 인자 재호출을 막고 근거 누적을 시작한다",
     "같은 조회를 반복해 비용이 늘고 도구 상한이 무의미해진다"),
    ("3", "조회", "코드", "tools.call(..., budget=max_steps) 로 필요한 것만 읽는다",
     "budget 을 안 넘기면 도구 호출 상한이 안 걸린다"),
    ("4", "판정", "코드", "도메인 규칙은 전부 여기. LLM 을 부르지 않는다. 성립하면 바로 반환",
     "규칙을 LLM 에 맡기면 같은 입력에 다른 답이 나온다"),
    ("⑤", "생성", "LLM", "④가 깨졌을 때만 대안을 만든다. llm 이 없으면 건너뛴다",
     "④→⑦ 로 가면 「안 된다」만 말하는 제품이 된다"),
    ("⑥", "재검증", "코드", "★④와 같은 함수를 다시 부른다. 통과한 대안만 남긴다",
     "다른 함수를 쓰면 「생성용 느슨한 판정」이 생긴다. ⑤→⑦ 로 가면 검증 안 된 대안이 나간다"),
    ("7", "반환", "코드", "TeamResult 로 돌려준다. 근거와 NextAction 을 함께 싣는다",
     "근거 없는 답변은 계약 단계에서 막힌다"),
], start=5):
    put(ws, i, list(s), fill=(WARN if s[0] in ("⑤", "⑥") else None), bold_first=True, height=40)
note(ws, 13, "★ ⑥이 이 아키텍처의 실체다. v9 에서는 별도 Team(response_review)이었는데 "
             "v10 이 각 Team 안으로 넣었다. 공통 부품은 travel_ops/_base.py 에 있다.", 5, WARN, bold=True)

# ══════════════════════════════════════════════════════ 7. 코어 경계
ws = wb.create_sheet("코어 경계")
title(ws, "에이전트가 안 하는 것 — 코어 몫",
      "Team 은 side effect 를 실행하지 않는다(v10 §6). 제안까지가 Team 이고 실행은 코어다.", span=3)
head(ws, 4, ["일", "누가", "왜"], [34, 18, 74])
for i, b in enumerate([
    ("도메인 판정 · 대안 생성 · 근거 수집", "Team", "자기 객체의 규칙은 그 팀이 가장 잘 안다"),
    ("전체 일정 정합성(시간 충돌·예산·이동 여유)", "코어 검증 층",
     "한 팀이 자기 객체만 보면 되도록 나눈 분리다. 팀이 전체를 보면 팀마다 같은 검사를 갖게 된다"),
    ("Case 생성 — 고객 요청 · 감시 사건", "코어",
     "감시가 Case 를 여는 것이 여행 도메인의 새 구조다. 주기 실행은 app/application/ 의 sweeper 셋"),
    ("실제 실행(예약 변경·취소·결제)", "코어 Action 층",
     "Team 은 ActionProposal 로 제안만 한다. 실행 권한을 팀에 주면 승인 경계가 무너진다"),
    ("고객 통지 발송", "코어 outbox",
     "★MCP·A2A 는 들어오는 문이라 알림을 못 민다. 나가는 문은 outbox 다"),
    ("승인 대기 · 되돌림", "코어", "승인 상태와 일정 버전은 코어가 소유한다"),
    ("사람 인계(escalated)", "코어", "Team 은 escalated 를 반환하고, 넘기는 처리는 코어가 한다"),
], start=5):
    put(ws, i, list(b), bold_first=True, height=34)

# ══════════════════════════════════════════════════════ 8. 미해결
ws = wb.create_sheet("미해결")
title(ws, "정하지 않은 것 — 만들기 전에 정해야 한다", "지어내지 않고 미정으로 둔 항목이다.", span=3)
head(ws, 4, ["항목", "무엇이 문제인가", "누가 정하나"], [30, 76, 18])
for i, o in enumerate([
    ("A2A 시연 대상이 없다",
     "엔드포인트 5개는 구현돼 있는데 원격 Team 이 없다(remote_team_demo 는 빈 폴더). "
     "v9 의 catalog_verification 이 그 자리였으나 미등록. 실행기 토글도 off. "
     "부트캠프 「다중 에이전트 서빙」 채점 항목이다.", "팀 · 코어"),
    ("response_review owner 가 옛 팀을 가리킨다",
     "project.yaml 의 response_review.owner_team_id = response_generation_review 인데 "
     "그 팀은 미등록이다. enabled: false 라 안 터지지만 켜면 기동이 막힌다"
     "(validate_response_review_owner 가 잡는다). 여행용 검토 팀을 만들지, 이 절을 지울지 미정.",
     "코어"),
    ("Activity 담당이 둘",
     "2026-09-09 회의록에 팀모듈1과 팀모듈3이 모두 「액티비티 모듈」로 적혀 있다.", "팀"),
    ("Dining 담당이 둘",
     "팀모듈4가 요식업 데이터·모듈 제안서를, 검증이 Dining 모듈 구조 설계를 하고 있다.", "팀"),
    ("Booking Handoff 담당 미정",
     "회의록에 담당이 나오지 않는다. MVP 필수 둘 중 하나다.", "팀"),
    ("무료·무예약 활동의 판정 규칙",
     "경복궁 관람처럼 취소 기한·위약금이 없는 항목에서 ④판정이 무엇을 보는지 안 정했다. "
     "휴관일·운영시간·이동 여유가 후보다.", "팀"),
    ("Case 에 타는 도메인 객체 id 규칙",
     "코어는 이미 도메인 중립이다(business_subject 라는 문자열 한 칸). "
     "그 칸에 무엇을 넣는지 규칙이 없다.", "코어"),
], start=5):
    put(ws, i, list(o), fill=WARN, bold_first=True, height=48)

for sheet in wb.worksheets:
    sheet.freeze_panes = "A5"
    sheet.sheet_view.showGridLines = False
wb["개요"].freeze_panes = "A4"

wb.save(OUT)
print(f"{os.path.basename(OUT)}")
print(f"  시트 {len(wb.worksheets)}개 · 여행 팀 {len(TRAVEL)} · 커머스 팀 {len(COMMERCE)} "
      f"· 기능 {len(FUNCS)}행 · A2A/MCP {len(A2A)}행")
print(f"  등록된 team_id ({len(REGISTERED)}): {sorted(REGISTERED)}")
