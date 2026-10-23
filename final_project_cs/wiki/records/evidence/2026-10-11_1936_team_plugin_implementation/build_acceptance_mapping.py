"""실제 PASSED 행만 인수 조건에 연결한다. 시험 수와 시나리오 수를 분리한다."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

folder = Path(__file__).resolve().parent
root = folder.parents[3]
logs = [folder / "acceptance-execution-v2.log", folder / "acceptance-read-boundaries-v1.log"]
rows = [
    (1, "비활성 구현 패키지 없음: import 0회·독립 앱 기동", ["clean_process_imports_no_disabled_team_implementation", "disabled_package_not_imported_and_other_team_loaded", "saved_trip_remains_readable_with_every_team_disabled"]),
    (2, "Team 선언 제거: 해당 업무 불가·독립 Team 요청 정상", ["removed_team_rejects_only_its_business_and_independent_team_runs"]),
    (3, "모든 선택 Team 비활성: Core·기존 계획 조회 유지", ["saved_trip_remains_readable_with_every_team_disabled", "all_teams_off_default_round_keeps_independent_cleanup"]),
    (4, "선택 import·생성 실패 격리·독립 실행", ["optional_load_failure_keeps_independent_team_executable"]),
    (5, "자동·직접 지정 disabled 실행 0회", ["declared_unavailable_is_operational", "local_disabled_team_execute_is_never_called", "routing_disabled_owner_creates_no_run_and_never_reroutes"]),
    (6, "기존 owner disabled: 변경 0회·운영 실패 기록", ["unavailable_resume_preserves_case_token_input_events_and_runs"]),
    (7, "필수 계산 disabled: 이전 callback·어림값 성공 0회", ["missing_request_context_never_uses_legacy_callback", "batch_does_not_use_legacy_disabled_planner", "review_does_not_swallow_disabled_required_calculation"]),
    (8, "후보 실패 시 게시 Controller·계산 표·revision 불변", ["invalid_candidate_keeps_published_controller_hooks_revision", "required_hook_failure_keeps_published_generation", "failed_optional_hook_discards_partial_registrations"]),
    (9, "같은 요청 hook 읽기 사이 reload: 같은 판", ["request_two_hook_reads_keep_old_generation_across_disable"]),
    (10, "실행 중 disable: 옛 요청 종료·신규 거절·일정 1회 적용", ["inflight_disable_keeps_old_team_and_applies_real_itinerary_once"]),
    (11, "연속 enabled reload 중 일시 부재·부분 등록 없음", ["repeated_enabled_reload_never_changes_pinned_callbacks"]),
    (12, "waiting_input disable 뒤 답변: 버전·답변·토큰 불변", ["unavailable_resume_preserves_case_token_input_events_and_runs"]),
    (13, "재활성화 동일 답변: 호환 계약·실제 일정 1회 변경", ["reactivation_same_reply_changes_real_itinerary_only_once"]),
    (14, "Local/A2A disabled: 같은 불가 의미·transport 0회", ["local_disabled_team_execute_is_never_called", "a2a_disabled_and_missing_registry_never_resolve_or_send"]),
    (15, "JSON/SSE/MCP 불가: 422·completed 위장 없음", ["json_and_mcp_keep_disabled_reason_while_independent_reads_work", "stream_error_preserves_reason", "message_http503_and_read_view_expose_unavailable_without_consuming_token"]),
    (16, "중복 capability·계약 불일치 후보 거절·이전 판 보존", ["invalid_candidate_keeps_published_controller_hooks_revision"]),
    (17, "최종 ROUTED 관문 unavailable: owner 잔류·후보 쓰기 없음", ["unavailable_at_final_route_gate_leaves_no_owner_or_candidate_write"]),
    (18, "enabled 엔진 off: disabled 구별·어림값 성공 없음", ["enabled_engine_off_never_returns_estimate"]),
    (19, "독립 정렬 유사도 생략·이유 표시·Activity 업무 우회 없음", ["independent_candidate_sort_omits_similarity_without_replacing_activity_business"]),
    (20, "감시 한 종류 disabled: 미실행 기록·독립 종류 계속", ["disabled_kind_not_checked_while_independent_kind_continues"]),
    (21, "sync·백그라운드 한 요청/회차 같은 판", ["sync_resolver_copies_context_and_supports_awaitable_result", "stream_worker_and_deferred_work_keep_request_generation", "nested_jobs_hold_one_controller_and_new_round_sees_new_generation"]),
    (22, "A2A endpoint·결과 식별자 불일치 거절", ["a2a_endpoint_mismatch_is_rejected_before_submit", "a2a_wrong_result_identity_rejected", "a2a_unknown_status_cannot_accept_completed_artifact"]),
    (23, "remote_unavailable과 resolver 구현·전송 실패 구분", ["a2a_valid_result_and_remote_unavailable_are_distinct", "resolver_implementation_errors_are_not_turned_into_unavailability", "controller_remote_deadline_leaves_budget_for_cancel_and_original_failure"]),
    (24, "필수 Team·Core 실패 숨기지 않음·옛 종료 revision 보존", ["import_failure_optional_vs_required", "publication_rejects_mixed_registry_or_revision", "inflight_disable_keeps_old_team_and_applies_real_itinerary_once"]),
]
entries = []
for number, condition, names in rows:
    evidence = []
    for name in names:
        matches = []
        for log in logs:
            for line_number, line in enumerate(log.read_text(encoding="utf-8-sig").splitlines(), 1):
                if "::test_" + name in line and " PASSED " in line:
                    matches.append({"test": line.split(" PASSED ")[0], "log": log.relative_to(root).as_posix(), "line": line_number, "result": "passed"})
        if not matches:
            raise RuntimeError(f"실행 근거 없음: {number} {name}")
        evidence.extend(matches)
    entries.append({"scenario": number, "condition": condition, "status": "passed", "evidence": evidence})
executed = {line.split(" PASSED ")[0] for log in logs
            for line in log.read_text(encoding="utf-8-sig").splitlines() if " PASSED " in line}
result = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "authority": "wiki/teams/team-plugin-lifecycle.md 인수 시나리오 24개",
    "scope": "로컬 제품 코드·계약 시험·로컬 개발 DB 격리 여행. 운영 배포·실제 A2A 원격 기계의 실측 아님.",
    "scenario_passed": len(entries), "scenario_total": 24,
    "pytest_passed": len(executed), "pytest_total": len(executed),
    "limitations": ["인수 조건 통과는 제품 전체 무결함 보장이 아님.", "A2A cancel은 async transport 대역으로 검증했으며 실제 원격 기계의 취소를 실측한 것은 아님.", "mock 서버 화면 시험이 아니라 Python 실행과 로컬 개발 DB 시험임. x600 서버의 cs 프로젝트 서버에는 미배포."],
    "logs": [{"path": p.relative_to(root).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in logs],
    "scenarios": entries,
}
(folder / "acceptance-mapping.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"시나리오 {len(entries)}/24, 시험 {len(executed)}/{len(executed)} 근거 연결")
