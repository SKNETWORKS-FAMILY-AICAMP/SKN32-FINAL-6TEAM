"""v11 §12 완료 기준(26항목)을 **실행으로** 센다. MVP 판정은 18항목(14~21 제외, 결정 16).

    python -m scripts.verify_dod_v11            # 전체 26
    python -m scripts.verify_dod_v11 --mvp      # MVP 18 만
    python -m scripts.verify_dod_v11 --list     # 무엇을 무엇으로 재는지만 본다(시험 안 돌림)

★왜 새로 만들었나(`[2026-09-21]`). `scripts/verify_dod.py` 는 **v8 의 29항목**(쇼핑몰 시절)을 센다.
  기준선은 2026-09-10 에 v11 26항목으로 바뀌었는데 세는 도구가 따라가지 않아, 「DoD 26/29 = 90%」
  같은 수가 **다른 기준의 분모**로 보고되고 있었다. 옛 스크립트는 지우지 않는다 — 그때 무엇을
  통과했는지의 기록이다.

★**세는 방법이 다르다.** 옛 스크립트는 `wiki/records/evidence/DoD-NN_*.md` 의 「판정:」 줄을 읽는다
  (사람이 쓴 판정). 이 스크립트는 **항목마다 어떤 시험이 그것을 보는지 적어 두고 그 시험을 돌린다.**
  시험 이름이 사라지면 「시험 없음」으로 빨갛게 난다 — 문서만 고쳐서 통과시킬 수 없다.

★★**재는 것이 없으면 「미측정」이라고 적는다. 통과로도 실패로도 세지 않는다.** 분모를 채우려고
  비슷한 시험을 끌어다 붙이면 그 순간 이 표가 거짓이 된다. 지금 미측정인 항목과 이유는 아래 표의
  `note` 에 그대로 적혀 있다.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Item:
    number: int
    title: str
    kind: str                       # 자동 · 아키텍처 · 측정
    checks: tuple[str, ...] = ()    # pytest node id — 비면 미측정
    note: str = ""
    #: MVP 판정에서 빠지는 항목(결정 16 — Booking Handoff 몫 14~21)
    mvp: bool = field(default=True)


T = "tests/"
ITEMS: tuple[Item, ...] = (
    Item(1, "외부 일정을 받아 저장하고 최신 버전을 반환한다", "자동", (
        T + "e2e/test_trip_api.py::test_create_is_idempotent_and_the_first_notice_carries_the_plan_link",
        T + "e2e/test_trip_api.py::test_a_second_trip_reuses_known_places_without_overwriting_them",
    )),
    Item(2, "예약 시간 충돌·이동 여유·예산·동행 조건을 코드로 판정한다", "자동", (
        T + "unit/travel/test_itinerary_checks.py::test_two_items_that_overlap",
        T + "unit/travel/test_itinerary_checks.py::test_a_move_shorter_than_the_planned_option",
        T + "unit/travel/test_itinerary_checks.py::test_zero_minutes_between_two_districts",
        T + "unit/travel/test_itinerary_checks.py::test_outside_opening_hours_and_inside_the_break",
        T + "unit/travel/test_itinerary_checks.py::test_a_place_that_does_not_take_the_agreed_payment",
        T + "unit/travel/test_itinerary_checks.py::test_a_plan_over_the_budget_counts_heads",
        T + "unit/travel/test_itinerary_checks.py::test_what_we_do_not_know_is_not_a_violation",
        T + "e2e/test_trip_api.py::test_create_rejects_unknown_references_and_needs_the_write_scope",
    ), note="`[2026-09-21]` 보낸 값으로 판정한다 — 겹침·이동 소요·영업시간·브레이크·결제·예산. "
            "**모르는 칸은 판정하지 않는다**(결정 15) — 이동 항목이 없는 구간은 구가 다를 때만 본다"),
    Item(3, "불가능한 일정을 이유와 완화 조건을 붙여 거절한다", "자동", (
        T + "e2e/test_trip_api.py::test_an_impossible_itinerary_is_refused_with_reasons_and_remedies",
        T + "e2e/test_trip_api.py::test_the_confirmed_day_is_accepted_as_submitted",
        T + "unit/travel/test_itinerary_checks.py::test_every_violation_carries_a_reason_and_a_remedy",
    ), note="422 `itinerary_infeasible` + 위반마다 `reason`·`remedy`. 거절하면 아무것도 저장하지 않는다"),
    Item(4, "모든 판정 근거에 출처와 확인 시각이 붙는다", "자동", (
        T + "contract/test_contracts.py::test_answer_without_evidence_is_rejected",
        T + "contract/test_contracts.py::test_proposal_cannot_cite_unknown_evidence",
        T + "unit/travel/test_evidence_accumulates.py::test_activity_keeps_every_source_it_read",
        T + "unit/travel/test_evidence_accumulates.py::test_a_missing_value_adds_no_evidence_but_keeps_the_earlier_ones",
    )),
    Item(5, "대체 소스로 값을 내고, 대체까지 안 되면 멈춘다(결정 15)", "자동", (
        T + "unit/travel/test_air_fallback.py::test_a_dead_airkorea_falls_back_to_the_model_instead_of_going_fatal",
        T + "unit/travel/test_air_fallback.py::test_when_every_air_source_fails_it_is_fatal_and_names_them_all",
        T + "scenario/test_trip_reminders.py::test_a_route_that_cannot_be_read_is_not_announced",
    )),
    Item(6, "다음 확인 시점이 도래하면 시스템이 Case 를 만든다", "자동", (
        T + "scenario/test_case_version_day.py::test_the_case_version_runs_the_whole_day_like_the_trip_version",
        T + "scenario/test_case_version_day.py::test_the_same_disruption_opens_one_case",
    )),
    Item(7, "재계획하고 재검증을 통과한 뒤에만 통지한다", "자동", (
        T + "scenario/test_confirmed_scenario.py::test_act02_air_alert_one_hour_ahead_moves_the_sky_deck_to_the_aquarium",
        T + "scenario/test_confirmed_scenario.py::test_the_whole_day_in_order",
    )),
    Item(8, "다시 요청하면 되돌리거나 제시했던 다른 안으로 바꾼다", "자동", (
        T + "e2e/test_trip_api.py::test_swap_to_the_other_option_and_back",
        T + "e2e/test_trip_api.py::test_rollback_restores_and_the_watcher_leaves_it_alone",
        T + "scenario/test_case_version_day.py::test_re_requests_run_through_cases",
    )),
    Item(9, "되돌림 후에도 이력이 남는다(append-only)", "자동", (
        T + "e2e/test_trip_api.py::test_rollback_restores_and_the_watcher_leaves_it_alone",
        T + "contract/test_case_state_table.py::test_rejection_does_not_resume",
    ), note="일정 이력은 되돌림 뒤에도 버전이 는다. Case 이벤트의 append-only 는 상태표 시험이 본다"),
    Item(10, "자동 처리 한계에서 근거를 붙여 사람에게 넘긴다", "자동", (
        T + "e2e/test_trip_api.py::test_a_sentence_the_desk_cannot_use_is_escalated_not_guessed",
        T + "scenario/test_case_version_day.py::test_a_failing_interpreter_is_recorded_and_the_case_still_routes_by_classification",
        T + "contract/test_contracts.py::test_escalate_requires_failure_code_or_warnings",
    )),
    Item(11, "다른 여행의 상태에 접근할 수 없다", "자동", (
        T + "scenario/test_case_version_day.py::test_another_customers_trip_is_not_found",
        T + "security/test_query_scope.py::test_case_list_does_not_leak_across_customers_in_one_tenant",
        T + "e2e/test_trip_api.py::test_the_plan_link_always_shows_the_latest_version",
    )),
    Item(12, "같은 변경을 두 번 받아도 일정이 두 번 바뀌지 않는다", "자동", (
        T + "e2e/test_trip_api.py::test_a_repeated_message_does_not_open_a_second_case",
        T + "e2e/test_trip_api.py::test_create_is_idempotent_and_the_first_notice_carries_the_plan_link",
        T + "scenario/test_case_version_day.py::test_the_same_disruption_opens_one_case",
    )),
    Item(13, "Team 이 side effect 를 직접 실행하지 않는다", "아키텍처", (
        T + "contract/test_team_tool_discipline.py::test_team_does_not_import_infrastructure_directly",
        T + "contract/test_team_tool_discipline.py::test_tool_outside_allowed_tools_is_refused_at_runtime",
        T + "contract/test_contracts.py::test_approval_required_proposal_forces_wait_for_approval",
    )),
    Item(14, "실제 공급자에는 자동 실행이 걸리지 않는다", "아키텍처", (
        T + "architecture/test_supplier_tier_gate.py::test_no_booking_handler_applies_without_human_approval",
        T + "architecture/test_supplier_tier_gate.py::test_the_tier_column_defaults_to_the_real_supplier",
        T + "integration/controller/test_travel_approval_proposal_reaches_waiting.py::"
            "test_an_approved_cancel_on_a_real_supplier_never_touches_the_ledger",
    ), mvp=False,
         note="`[2026-09-22]` 공급자 등급이 **데이터에** 생겼다(마이그레이션 017 `supplier_bookings.tier`, "
              "기본값 `real`). 등급이 `simulated` 가 아니면 적용기가 원장을 건드리지 않고 `ActionRejected` "
              "→ 코어가 전부 되돌리고 `action_rejected` 로 사람에게 넘긴다. 예약 적용기는 전부 "
              "`auto_apply=False` 라 **승인 뒤에만** 온다 — 두 문을 같이 잠근다"),
    Item(15, "자동 실행 분기는 tier=='simulated' 에서만 열린다", "아키텍처", (
        T + "architecture/test_supplier_tier_gate.py::"
            "test_every_write_to_the_supplier_ledger_passes_the_tier_gate_first",
        T + "architecture/test_supplier_tier_gate.py::test_the_gate_actually_catches_an_ungated_write",
        T + "architecture/test_supplier_tier_gate.py::test_the_gate_opens_only_for_the_simulated_tier",
        T + "integration/controller/test_travel_approval_proposal_reaches_waiting.py::"
            "test_a_supplier_row_without_a_tier_is_treated_as_real",
        T + "integration/controller/test_travel_approval_proposal_reaches_waiting.py::"
            "test_the_ledger_only_moves_for_the_simulated_tier",
    ), mvp=False,
         note="`[2026-09-22]` AST 로 **공급자 원장을 바꾸는 SQL 전부**를 찾아 같은 함수 안에서 게이트가 "
              "그보다 **앞에** 불리는지 센다 — 새 적용기가 한 줄 더 써도 잡힌다. ★검사기 자신도 시험한다"
              "(게이트 없는 코드·순서 뒤바뀐 코드를 넣어 빨간지 확인) — DoD-23 의 「통과하면서 못 잡는 "
              "가드」를 되풀이하지 않으려는 것이다. 게이트를 실제로 지워 5건이 빨간 것을 확인하고 원복했다"),
    Item(16, "업체 건은 실행하지 않고 변경 링크를 만든다", "자동", (
        T + "e2e/test_booking_change_link.py::"
            "test_a_real_supplier_booking_is_handed_off_by_link_and_the_ledger_stays_put",
        T + "e2e/test_booking_change_link.py::test_a_wrong_token_never_says_whether_the_booking_exists",
    ), mvp=False,
         note="`[2026-09-22]` 변경 링크가 생겼다 — `GET /booking-change/{booking_id}?t=…` "
              "(`app/modules/travel_ops/change_link.py`, 예약별 HMAC 토큰·로그인 없음·토큰이 틀리면 "
              "404). **아무것도 쓰지 않으므로 승인도 scope 도 없다.** `booking.change` 적용기는 "
              "공급자 원장을 어느 등급에서도 건드리지 않고 그 링크를 인계 메시지(`booking.handoff`)에 "
              "싣는다 — 등급 `real` 로 두고 원장이 한 글자도 안 바뀌는 것을 실측한다"),
    Item(17, "변경 링크에 바뀔 항목·대안·차액이 들어 있다", "자동", (
        T + "e2e/test_booking_change_link.py::"
            "test_the_link_shows_the_item_the_alternatives_and_the_difference",
        T + "e2e/test_booking_change_link.py::"
            "test_a_difference_we_cannot_compute_says_so_instead_of_inventing_one",
    ), mvp=False,
         note="`[2026-09-22]` 바뀔 항목=`bookings`+`places.name`+`supplier_bookings` · 대안=그 예약에 "
              "걸린 일정 항목의 `detail.alternates`(감시 루프가 들고 둔 「다른 안」, 새로 계산하지 "
              "않는다) · 차액=양쪽 **1인 가격**(`places.attributes.price_krw`) 차 × 인원. "
              "★★**차액을 지어내지 않는다** — 한쪽 가격이라도 없으면 `difference_krw=None` 이고 "
              "화면은 「확인되지 않았습니다」+ 어느 쪽을 몰라서인지 적는다(결정 15). 둘째 시험이 "
              "가격 없는 장소를 일부러 넣어 그것을 본다"),
    Item(18, "(시연) 위임 범위를 벗어난 자동 실행이 0건", "측정", (
        T + "integration/controller/test_delegation_scope.py::"
            "test_no_out_of_scope_automatic_execution_in_the_measured_flood",
        T + "integration/controller/test_delegation_scope.py::test_every_limit_actually_blocked_something",
        T + "integration/controller/test_delegation_scope.py::test_every_rejection_names_its_gate",
    ), mvp=False,
         note="`[2026-09-22]` 재는 것은 스크립트다 — `python -m scripts.measure_delegation_scope`. "
              "**실측 13건을 흘려 범위 밖 10건 중 자동 실행 0건**(분모는 범위 밖 시도 10건). 같이 본 것 — "
              "범위 안인데 막힌 건수 0/3 · 기대와 다른 문이 막은 건수 0/10. 위임 범위는 설정 "
              "`travel.delegation`(건당·누적·횟수·종류·무료취소·되돌림창, **우리가 고른 값**)과 데이터 "
              "`delegations`(살아 있나 — 행이 없으면 위임이 없다)에 있다. 시험은 그 스크립트를 불러 수를 "
              "고정하고, 한계마다 실제로 막은 경우가 있는지도 센다. ★게이트를 열어 두고 재봤다 — 같은 "
              "13건에서 **9건이 새고**(90%) 시험 6건이 빨갛다. ☆표본은 한계마다 한 경우씩이며 운영 분포가 아니다"),
    Item(19, "(시연) 위임을 철회하면 진행 중인 자동 실행이 멈춘다", "자동", (
        T + "integration/controller/test_delegation_scope.py::"
            "test_revoking_after_the_approval_stops_the_execution",
        T + "integration/controller/test_delegation_scope.py::test_after_a_revocation_no_new_execution_opens",
        T + "integration/controller/test_delegation_scope.py::"
            "test_one_out_of_scope_proposal_rolls_the_whole_batch_back",
    ), mvp=False,
         note="`[2026-09-22]` 판정을 **적용 순간에** 한다(위임 행을 `FOR UPDATE` 로 잠가 읽는다) — 적용이 한 "
              "트랜잭션이라 「반쯤 나간 자동 실행」이 없고, 승인과 적용 사이(사람이 누른 뒤 재개가 도는 사이)에 "
              "철회되면 원장이 한 글자도 안 바뀌고 `action_rejected` 로 사람에게 간다. ★한 Case 의 제안 둘 중 "
              "하나가 범위 밖이면 **첫째까지 되돌린다** — 위임 없는 상태에서 원장에 한 건이라도 남는 쪽이 더 나쁘다"),
    Item(20, "(시연) 자동 실행에 무엇을·왜·얼마에·되돌림 기한이 기록된다", "자동", (
        T + "integration/controller/test_delegation_scope.py::"
            "test_the_ledger_records_what_why_how_much_and_the_revert_deadline",
        T + "integration/controller/test_delegation_scope.py::"
            "test_an_amount_we_do_not_know_is_left_empty_not_invented",
    ), mvp=False,
         note="`[2026-09-22]` 마이그레이션 019 가 `action_requests` 에 칸을 더했다 — `amount_cents`+"
              "`amount_source`(★DB CHECK 가 둘을 같이 채우거나 같이 비우게 한다) · `reason` · "
              "`revert_deadline` · `delegation_json`(판정 근거) · `prior_state_json`(되돌릴 때 돌아갈 상태). "
              "★**모르는 금액은 비운다** — NULL 은 0 이 아니라 「확인되지 않았다」다(인계 `booking.change` 는 "
              "차액을 모르므로 NULL). 적용기가 채우고 코어가 그대로 적는다 — 코어는 뜻을 모른다"),
    Item(21, "(시연) 되돌림이 실패하면 사람에게 넘어간다", "자동", (
        T + "integration/controller/test_delegation_scope.py::test_a_revert_restores_both_ledgers",
        T + "integration/controller/test_delegation_scope.py::"
            "test_a_revert_after_the_deadline_goes_to_a_human",
        T + "integration/controller/test_delegation_scope.py::"
            "test_a_revert_without_a_recorded_prior_state_goes_to_a_human",
        T + "integration/controller/test_delegation_scope.py::"
            "test_a_revert_on_a_real_supplier_never_touches_the_ledger",
    ), mvp=False,
         note="`[2026-09-22]` 되돌림 경로가 생겼다 — `booking.revert` 적용기 + 준비 capability "
              "`booking.prepare_revert`(issue_code `booking_revert_request`). 실패 사유 셋을 실측했다: 기한 "
              "경과 · 돌아갈 상태 미기록(★`confirmed` 를 **지어내지 않는다**) · 공급자 등급. 셋 다 되돌림 "
              "요청의 `action_requests` 행이 `failed` 로 남고 Case 가 `escalated` 로 간다(사유는 `case_events` "
              "에 append-only). ★되는 경우도 함께 본다 — 안 되는 것만 보면 늘 실패하는 코드도 초록이다"),
    Item(22, "평가 시나리오에서 필수 조건 위반 0건", "측정", (
        T + "scenario/test_travel_eval_scenarios.py::test_a_scenario_runs_without_breaking_a_hard_constraint",
        T + "scenario/test_travel_eval_scenarios.py::test_the_dataset_and_the_runner_still_match",
    ), note="`[2026-09-22]` 여행 평가 데이터셋 `eval/datasets/travel_scenarios.jsonl`(시나리오 10건)과 "
            "러너 `python -m eval.runners.travel_scenarios`. 적용된 **모든 일정 버전**을 등록 때와 같은 "
            "판정기로 다시 본다. 실측 10/10 통과 · 위반 0건(보고서 `eval/reports/`). ★표본은 하루 1종 · "
            "서울 1도시다 — 다른 일정을 대표하지 않는다. 시험은 성격이 다른 네 건만 돌린다"),
    Item(23, "등록된 모든 Team 에 도달하는 issue_code 접두가 있다", "아키텍처", (
        T + "unit/travel/test_feedback_case_type_alignment.py::test_every_routable_case_type_has_at_least_one_issue_code",
        T + "unit/travel/test_feedback_case_type_alignment.py::test_every_issue_code_either_routes_or_is_deliberately_unroutable",
        T + "unit/travel/test_feedback_case_type_alignment.py::test_request_kinds_are_not_used_as_case_types",
    )),
    Item(24, "한 Case 에서 대상 객체가 다른 제안 둘이 각각 저장된다", "자동", (
        T + "integration/controller/test_travel_approval_proposal_reaches_waiting.py::test_two_proposals_for_two_bookings_in_one_case_both_survive",
        T + "integration/controller/test_travel_approval_proposal_reaches_waiting.py::test_a_second_proposal_that_would_be_swallowed_goes_to_a_human",
    ), note="적용기가 있는 제안은 각각 저장된다. 적용기가 없는 제안은 아직 합쳐지되 **조용히 사라지지 않고** "
            "사람에게 간다 — 둘째 시험이 그것을 본다"),
    Item(25, "알림을 못 받아도 링크에서 최신 버전과 「무엇이 왜 바뀌었나」를 본다", "자동", (
        T + "e2e/test_trip_api.py::test_the_plan_link_always_shows_the_latest_version",
        T + "scenario/test_trip_reminders.py::test_a_change_notice_carries_the_plan_link",
    )),
    Item(26, "때가 되면 어디로·언제·어떻게 가는지 안내가 나가고, 두 번 나가지 않는다", "자동", (
        T + "scenario/test_trip_reminders.py::test_a_day_of_ticks_sends_each_reminder_once",
        T + "scenario/test_trip_reminders.py::test_the_same_moment_twice_is_already_sent",
        T + "scenario/test_trip_reminders.py::test_windows_follow_the_first_item_and_each_move",
    )),
)


def _run(node_ids: list[str]) -> tuple[dict[str, str], str]:
    """node id → PASSED/FAILED/… . 없는 시험은 결과에 안 나타난다(호출부가 「시험 없음」으로 센다)."""
    if not node_ids:
        return {}, ""
    # ★이름이 하나라도 틀리면 pytest 는 **아무것도 안 돌리고** 끝난다 — 그러면 전 항목이 「시험 없음」
    #   으로 보여 진짜 상태를 가린다. 먼저 모아 보고, 있는 것만 돌린다(없는 것은 없는 대로 보고한다).
    collect = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                              "-p", "no:cacheprovider", *node_ids],
                             cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                             capture_output=True)
    found = {line.strip().replace("\\", "/") for line in (collect.stdout or "").splitlines()
             if "::" in line}
    # ★매개변수가 붙은 시험은 `…::test_x[param]` 으로 모인다 — 적어 둔 이름은 그 **앞부분**이다.
    runnable = [node for node in node_ids
                if node in found or any(f.startswith(node + "[") for f in found)]
    if not runnable:
        return {}, (collect.stdout or "") + (collect.stderr or "")
    completed = subprocess.run([sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider",
                                "--no-header", "-rN", *runnable],
                               cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                               capture_output=True)
    output = (completed.stdout or "") + (completed.stderr or "")
    results: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"(\S+::\S+?)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)", line)
        if match:
            results[match.group(1).replace("\\", "/")] = match.group(2)
    return results, output


def _state_of(results: dict[str, str], check: str) -> str | None:
    """적어 둔 이름의 결과. 매개변수가 붙은 시험은 **전부 통과해야** 통과다."""
    if check in results:
        return results[check]
    params = [state for node, state in results.items() if node.startswith(check + "[")]
    if not params:
        return None
    return "PASSED" if all(state == "PASSED" for state in params) else "FAILED"


def main() -> int:
    # ★윈도 콘솔 기본 인코딩(cp949)으로는 이 표의 글자가 안 나간다 — 출력만 UTF-8 로 돌린다.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--mvp", action="store_true", help="MVP 판정 18항목만 센다(결정 16)")
    parser.add_argument("--list", action="store_true", help="무엇을 무엇으로 재는지만 본다")
    args = parser.parse_args()

    items = [item for item in ITEMS if item.mvp] if args.mvp else list(ITEMS)
    scope = "MVP 18항목" if args.mvp else "전체 26항목"
    print("=" * 78)
    print(f"triPilot DoD 검증 — 기준선 v11 §12 · {scope} (판정: 자동 20 · 아키텍처 4 · 측정 2)")
    print("=" * 78)

    if args.list:
        for item in items:
            mark = "" if item.mvp else "  [MVP 제외]"
            print(f"{item.number:>2}  {item.title}{mark}")
            for check in item.checks or ("(재는 시험 없음)",):
                print(f"      {check}")
            if item.note:
                print(f"      ☆{item.note}")
        return 0

    node_ids = sorted({check for item in items for check in item.checks})
    results, output = _run(node_ids)

    print(f"{' #':>3}  {'항목':<52} {'판정':<6} {'근거':<7} 결과")
    passed = failed = unmeasured = broken = 0
    for item in items:
        if not item.checks:
            state, unmeasured = "미측정", unmeasured + 1
            evidence = "-"
        else:
            states = [_state_of(results, check) for check in item.checks]
            evidence = f"{sum(s == 'PASSED' for s in states)}/{len(item.checks)}"
            if None in states:
                state, broken = "시험 없음", broken + 1
            elif all(s == "PASSED" for s in states):
                state, passed = "통과", passed + 1
            else:
                state, failed = "미통과", failed + 1
        mark = "" if item.mvp else "*"
        print(f"{item.number:>2}{mark} {item.title[:52]:<52} {item.kind:<6} {evidence:<7} {state}")

    total = len(items)
    print("-" * 78)
    print(f"통과 {passed}/{total} = {passed / total:.0%} · 미통과 {failed} · "
          f"미측정 {unmeasured} · 시험 없음 {broken}")
    print(f"★분모는 v11 §12 의 {scope}다. **미측정은 통과로도 실패로도 세지 않는다** — "
          f"무엇이 왜 미측정인지는 `--list` 가 적는다.")
    if not args.mvp:
        mvp_items = [item for item in ITEMS if item.mvp]
        mvp_pass = sum(bool(item.checks) and all(_state_of(results, c) == "PASSED" for c in item.checks)
                       for item in mvp_items)
        print(f"참고 — MVP 판정(14~21 제외) {mvp_pass}/{len(mvp_items)} = {mvp_pass / len(mvp_items):.0%}")
    if broken or failed:
        print("-" * 78)
        for item in items:
            for check in item.checks:
                state = _state_of(results, check)
                if state is None:
                    print(f"★{item.number}: 시험이 없다 — {check}")
                elif state != "PASSED":
                    print(f"★{item.number}: {state} — {check}")
        if broken and "error" in output.lower():
            print(output[-2000:])
    return 1 if (failed or broken) else 0


if __name__ == "__main__":
    raise SystemExit(main())
