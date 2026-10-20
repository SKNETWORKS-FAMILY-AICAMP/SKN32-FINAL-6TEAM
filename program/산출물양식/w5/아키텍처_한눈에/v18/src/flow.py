# -*- coding: utf-8 -*-
"""멀티에이전트 플로우 상세 — Case 한 건이 오케스트레이터 → 에이전트 → 검증 · 반영 → 알림을 지나는 길 (2026-10-02, v11)

diagram-design 스킬: Flowchart + 구역(zone). 상세판(faithful)이라 상자 9개 상한 대신 구역으로 나누고 24개까지 둔다.
선 규칙(둥근 직각 · 이름표 간격 · 겹침 · 남의 상자 뒤 지나감 금지)은 그대로 검사한다.

코드 근거 (final_project_cs/app 기준, 2026-10-02 읽음)
- 라우팅: application/routing.py case_type_of — issue_code 의 `_` 앞부분 → 담당 팀. 없으면 ROUTING_FAILED(멈춤)
- 할 일 묶음: application/controller.py _task — capability · ContextPack(근거 묶음) · allowed_tools · deadline(team_timeout_seconds)
- 90초 넘으면 GUARDRAIL_ESCALATED: controller.py run_case B 단계
- 감시가 여는 Case: modules/travel_ops/trip_watch_cases.py — 식사 dining_other · 활동 activity_weather_risk / activity_other
- 요식: modules/travel_ops/dining/team.py handle_trigger → itinerary_changes.plan_dining_disrupted (DINING_RECHECK_LIMIT)
- 액티비티: modules/travel_ops/activity/team.py handle_trigger · needs_consent → 「바꿀까요?」 · plan_activity_adjustment
- 공통: itinerary_team.py run_itinerary(read.itinerary) · recheck(read.disruptions, 모르면 fatal) · settle(제안 approval_required=False)
- 툴 규칙: tools/read_tools.py call — 목록 밖 ToolNotAllowed · 같은 호출 ToolLoopExceeded · max_steps 12 ToolBudgetExceeded
- 대조: controller.py _reject_unverified — degraded 면 자동 실행 금지, check_proposal 로 근거 대조
- 적용기: itinerary_actions.py apply — 고객 소유 · 기준 버전(ActionConflict) · 항목 · 장소 실재, pending.decide 로 묻기,
  고객이 고른 것(CHOSEN_BY_CUSTOMER)은 묻기 판정을 건너뜀, 새 버전 + refresh_moves_around + 되돌리기 제안 + 바깥함 알림
"""
from dd import Fig


def fig_flow():
    W, H = 1400, 2160
    f = Fig("tp-flow", W, H, "guguroute 멀티에이전트 플로우 — Case 한 건이 지나가는 길",
            "낮 감시가 연 Case 를 오케스트레이터가 문제 코드 앞부분으로 요식 또는 액티비티 에이전트 하나에 배정하고, "
            "할 일 묶음(할 일 종류 · 근거 묶음 · 허용 툴 · 90초)을 넘긴다. 에이전트는 허용된 툴로 일정을 읽고 지금 항목을 다시 점검한 뒤 "
            "대체 후보를 한 곳씩 다시 점검해 변경 제안을 낸다. 오케스트레이터는 제안을 근거와 대조하고 적용기가 다시 확인한 뒤 "
            "물어볼 일정이면 묻고 아니면 새 일정 버전을 저장해 알린다. 고객이 고르면 다시 확인하고, 감시는 다음 1분에 다시 돈다.")
    f.max_nodes, f.max_arrows, f.max_accents = 24, 32, 4   # 상세판 — 구역으로 나눈다. 강조색은 루프 넷에만
    MX, MW = 540, 320          # 가운데 열
    LX, RX, CW = 80, 880, 440  # 왼쪽(요식) · 오른쪽(액티비티) 열

    f.zone(24, 24, 1304, 144, "① 들어오는 곳")
    f.zone(24, 184, 1304, 376, "② 오케스트레이터 — 배정하고 할 일을 묶어 넘긴다")
    f.zone(24, 576, 1304, 648, "③ 워커 에이전트 — 둘 중 하나가 받는다 · 에이전트끼리 직접 부르지 않는다", lx=304)
    f.zone(24, 1240, 1304, 640, "④ 검증 · 반영 — 오케스트레이터 + 일정 적용기")
    f.zone(24, 1896, 1304, 176, "⑤ 알림 · 고객 · 다음 차례", lx=160)

    # ① 들어오는 곳
    f.box("T1", MX, 56, MW, 96, title="낮 감시 작업 (1분마다)", tag="JOB",
          io=[("I", "앞 90분 항목 · 외부 6범주 점검"), ("O", "깨진 항목 1개 → Case 1건")])
    f.box("T2", 960, 56, MW, 96, kind="optional", title="에이전트를 거치지 않는 길", tag="CHAT · MCP",
          io=[("I", "고객 채팅 · 개인 AI · 새벽 점검"), ("O", "같은 계산 → 같은 반영")])
    # ② 오케스트레이터
    f.box("O1", MX, 216, MW, 96, title="라우팅", tag="ROUTE",
          io=[("I", "Case 문제 코드 (dining_ …)"), ("O", "담당 1개 · 없으면 멈춤")])
    f.box("O2", MX, 344, MW, 96, title="할 일 묶음 만들기", tag="TASK",
          io=[("I", "Case · 지금 상태 · 담당"), ("O", "할 일 · 근거 묶음 · 툴 · 90초")])
    f.diamond("Od", 700, 504, 240, 80, "누구에게?")
    # ③ 요식 에이전트
    f.box("DH", LX, 616, CW, 96, title="요식 에이전트", tag="AGENT · DINING",
          io=[("I", "식사 항목 · 원인(감시 결과) · 할 일 묶음"), ("O", "변경 제안 / 그대로 답 / 멈춤")])
    f.box("D2", LX, 744, CW, 96, title="1. 일정 읽기 + 지금 항목 재점검",
          lines=[("mono", "read.itinerary · read.disruptions"), "문제 없음 → 그대로 · 확인 불가 → 멈춤"])
    f.box("D3", LX, 872, CW, 96, title="2. 대체 식당 후보 만들기",
          lines=[("mono", "read.place_catalog · read.dining_alternatives"), "요식 원장 후보 → 순위 매김"])
    f.box("D4", LX, 1000, CW, 96, title="3. 후보 1곳씩 다시 점검",
          lines=[("mono", "read.disruptions · read.dining_state"), "순위순 최대 3곳 · 못 본 곳은 안 고름"])
    f.box("D5", LX, 1128, CW, 80, title="4. 결과",
          lines=["통과 → 최선 1곳 + 다른 안 최대 2곳 = 변경 제안"])
    # ③ 액티비티 에이전트
    f.box("AH", RX, 616, CW, 96, title="액티비티 에이전트", tag="AGENT · ACTIVITY",
          io=[("I", "활동 항목 · 원인 · 실내 여부 · 설문 선호"), ("O", "변경 제안 / 바꿀까요? / 그대로 / 멈춤")])
    f.box("A2", RX, 744, CW, 96, title="1. 일정 읽기 + 지금 항목 재점검",
          lines=[("mono", "read.itinerary · read.disruptions"), "문제 없음 → 그대로 · 확인 불가 → 멈춤"])
    f.diamond("A3", 1100, 912, 240, 80, "날씨만 · 실내 모름?")
    f.box("A4", RX, 1000, CW, 96, title="2. 후보 1곳씩 다시 점검",
          lines=[("mono", "read.place_catalog · read.disruptions"), "비슷한 곳(분류 · 구) → 가까운 곳 · 설문 선호"])
    f.box("A5", RX, 1128, CW, 80, title="3. 결과",
          lines=["통과 → 변경 제안 · 못 찾고 날씨만 → 바꿀까요?"])
    # ④ 검증 · 반영
    f.box("V1", MX, 1272, MW, 96, title="결과 받기", tag="RESULT",
          io=[("I", "답 · 제안 · 멈춤 (에이전트 결과)"), ("O", "제안 → 대조 · 멈춤 → 기록")])
    f.oval("E", 80, 1288, 360, 64, title="멈춤 — 일정 그대로", lines=["이유 코드만 기록 · 사람 대기 없음"])
    f.box("V2", MX, 1400, MW, 96, title="사실 대조",
          lines=["근거 묶음이 깎였으면 자동 실행 안 함", "제안 값을 오케스트레이터 근거와 대조"])
    f.box("V3", MX, 1528, MW, 96, title="적용기 다시 확인",
          lines=["고객 소유 · 기준 버전 · 항목 · 장소", "버전이 밀렸으면 반영 안 함"])
    f.diamond("V4", 700, 1696, 240, 80, "물어볼 일정?")
    f.box("V5", MX, 1768, MW, 96, title="새 일정 버전 저장",
          lines=["이전 판 보존 · 앞뒤 이동 재계산", "자동 변경엔 되돌리기 버튼"])
    f.box("V6", 920, 1648, MW, 96, title="묻기 열기",
          lines=["보호 일정 · 먼저 물어봐 · 실내 모름", "보류 제안 + 묻는 알림"])
    # ⑤ 알림 · 고객
    f.box("N1", MX, 1928, MW, 96, title="알림 워커 → Discord", tag="OUTBOX",
          io=[("I", "새 버전 · 묻기 알림 · 정기 안내"), ("O", "Discord + 계획서 링크 · 최대 3회")])
    f.box("C1", 80, 1928, 360, 96, kind="input", title="고객 응답",
          lines=["링크 · 채팅에서 다른 안 고르기", "되돌리기 · 「바꿔 줘」"])

    # 화살표 — ①②
    f.path("f1", [(700, 152), (700, 216)], "T1", "O1")
    f.label("f1", 708, 176, "Case 1건", anchor="left")
    f.path("f2", [(700, 312), (700, 344)], "O1", "O2")
    f.path("f3", [(700, 440), (700, 464)], "O2", "Od")
    f.path("f4", [(580, 504), (300, 504), (300, 616)], "Od", "DH")
    f.label("f4", 440, 480, "식사 항목 → 요식")
    f.path("f5", [(820, 504), (1100, 504), (1100, 616)], "Od", "AH")
    f.label("f5", 960, 480, "활동 항목 → 액티비티")
    # ③ 요식
    f.path("f6", [(300, 712), (300, 744)], "DH", "D2")
    f.path("f7", [(300, 840), (300, 872)], "D2", "D3")
    f.label("f7", 308, 848, "깨짐", anchor="left")
    f.path("f8", [(300, 968), (300, 1000)], "D3", "D4")
    f.path("f9", [(520, 1072), (552, 1072), (552, 1024), (520, 1024)], "D4", "D4", color="accent")
    f.label("f9", 560, 1040, "다음 후보", anchor="left")
    f.path("f10", [(300, 1096), (300, 1128)], "D4", "D5")
    f.label("f10", 308, 1104, "다 봤음", anchor="left")
    # ③ 액티비티
    f.path("f11", [(1100, 712), (1100, 744)], "AH", "A2")
    f.path("f12", [(1100, 840), (1100, 872)], "A2", "A3")
    f.label("f12", 1108, 848, "깨짐", anchor="left")
    f.path("f13", [(1100, 952), (1100, 1000)], "A3", "A4")
    f.label("f13", 1108, 968, "아니오", anchor="left")
    f.path("f14", [(1220, 912), (1344, 912), (1344, 1168), (1320, 1168)], "A3", "A5")
    f.label("f14", 1232, 888, "예 → 바꿀까요?", anchor="left")
    f.path("f15", [(880, 1072), (848, 1072), (848, 1024), (880, 1024)], "A4", "A4", color="accent")
    f.label("f15", 840, 1040, "다음 후보", anchor="right")
    f.path("f16", [(1100, 1096), (1100, 1128)], "A4", "A5")
    f.label("f16", 1108, 1104, "다 봤음", anchor="left")
    # ④ 검증 · 반영
    f.path("f17", [(300, 1208), (300, 1232), (660, 1232), (660, 1272)], "D5", "V1")
    f.path("f18", [(1100, 1208), (1100, 1232), (740, 1232), (740, 1272)], "A5", "V1")
    f.path("f19", [(540, 1320), (440, 1320)], "V1", "E")
    f.label("f19", 492, 1296, "멈춤")
    f.path("f20", [(700, 1368), (700, 1400)], "V1", "V2")
    f.label("f20", 708, 1376, "제안", anchor="left")
    f.path("f21", [(540, 1448), (260, 1448), (260, 1352)], "V2", "E")
    f.label("f21", 400, 1424, "대조 실패")
    f.path("f22", [(700, 1496), (700, 1528)], "V2", "V3")
    f.label("f22", 708, 1504, "통과", anchor="left")
    f.path("f23", [(540, 1576), (200, 1576), (200, 1352)], "V3", "E")
    f.label("f23", 360, 1552, "거부 · 충돌")
    f.path("f24", [(700, 1624), (700, 1656)], "V3", "V4")
    f.path("f25", [(700, 1736), (700, 1768)], "V4", "V5")
    f.label("f25", 708, 1744, "아니오", anchor="left")
    f.path("f26", [(820, 1696), (920, 1696)], "V4", "V6")
    f.label("f26", 868, 1672, "예")
    # ⑤ 알림 · 고객 · 루프
    f.path("f27", [(700, 1864), (700, 1928)], "V5", "N1")
    f.label("f27", 708, 1888, "새 버전 알림", anchor="left")
    f.path("f28", [(1080, 1744), (1080, 1960), (860, 1960)], "V6", "N1")
    f.label("f28", 968, 1936, "묻는 알림")
    f.path("f29", [(540, 1976), (440, 1976)], "N1", "C1", color="link")
    f.label("f29", 492, 1952, "알림 + 링크")
    f.path("f30", [(160, 1928), (160, 1608), (540, 1608)], "C1", "V3", color="accent")
    f.label("f30", 376, 1584, "다시 확인 · 고객이 고른 것")
    f.path("f31", [(1280, 104), (1360, 104), (1360, 1592), (860, 1592)], "T2", "V3", dash="5,4")
    f.label("f31", 1352, 272, "같은 계산 · 같은 반영", anchor="right")
    f.path("f32", [(700, 2024), (700, 2056), (1392, 2056), (1392, 40), (760, 40), (760, 56)], "N1", "T1", color="accent")
    f.label("f32", 1200, 2032, "다음 1분 · 다시 감시")

    f.legend(H - 56, [("input", "고객"), ("backend", "처리 단계"), ("optional", "에이전트 안 거침"), ("diamond", "판단"),
                      ("line:muted", "흐름"), ("line:link", "고객에게"), ("line:accent", "되돌아가는 루프")])
    return f
