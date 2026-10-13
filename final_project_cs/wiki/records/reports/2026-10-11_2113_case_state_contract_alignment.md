# 재개 중 담당 변경의 상태 계약 정합성

실패 원인은 입력 재소비 전이가 아니라, 재개 중 최종 담당을 기록하는 `routed` 자기전이를 기존 v5 고정 기대표가 반영하지 못한 것이었습니다. 현재 wiki 계약을 먼저 보완한 뒤 기대표와 의미 시험을 갱신했습니다. 실행 가능한 전이를 더 늘리는 코드는 추가하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 상태 계약·리듀서 시험 | 통과 | 36/36 = 100% |
| 로컬 DB 재배분 회귀 | 통과 | 4/4 = 100% |
| 변경 시험 파일 린트 | 통과 | 1/1 = 100% |

## 판단 근거와 수정

통합 회귀의 실제 실패는 `allowed_next_statuses(resuming)`에 `resuming`이 추가되어 기존 기대값과 달라진 것입니다. 코드의 이벤트는 **`ROUTED`**이며 `VALID_INPUT`이 아닙니다. 자동 생성된 상태 문서에도 `resuming --routed--> resuming`이 이미 있었지만, 사람이 관리하는 생명주기 계약의 표와 v5를 기준으로 한 시험에는 빠져 있었습니다.

고객의 추가 답변으로 담당을 바꿀 때에는 입력을 반영한 같은 Case에서 최종 담당과 요청을 기록하고, 그 뒤 `RESUMED`를 거쳐 실행해야 합니다. 기존 [실행 가용성 계약](../../teams/team-contract/plugin-availability.md)의 `VALID_INPUT → ROUTED → RESUMED` 순서와 일치합니다. 재실행을 위해 입력을 두 번 소비하거나 `RESUMED` 없이 완료하는 방식으로 바꾸지 않았습니다.

- [현재 생명주기 계약](../../runtime/case-lifecycle.md): `routed`만 재개 중 자기전이로 허용하며 입력 재소비·직접 완료를 금지한다고 먼저 명시했습니다.
- [상태 계약 시험](../../../tests/contract/test_case_state_table.py): 현재 wiki 기대표를 실행 코드와 별도로 적었습니다. 기존 시험 식별자는 불변식 카탈로그 링크를 위해 유지했습니다. 상태마다 허용 다음 상태가 정확히 일치하는 검사를 유지하고, 전체 자기전이가 `(resuming, routed)` 하나뿐임을 추가 검사합니다.
- 새 의미 시험은 담당·요청 변경, 입력·토큰 사용 여부·대기 사유 보존, 버전 증가, 이어지는 `RESUMED`를 확인합니다. `resuming`에서 `VALID_INPUT` 재소비와 `COMPLETED` 직접 완료를 각각 거절하는 음성 시험도 추가했습니다.
- [이벤트 표](../../../app/core/case_lifecycle/events.py)의 정본 안내 주석을 현재 wiki로 정정했습니다. 전이 사전 자체는 변경하지 않았습니다.

## 실행 근거

- [상태 계약·리듀서 원문](../evidence/2026-10-11_1936_team_plugin_implementation/case-state-contract-alignment.log): `python -m pytest tests/contract/test_case_state_table.py tests/unit/core/test_case_reducer.py -q --tb=short` → 36 passed. 종료 후 Windows 콘솔 정리 경고가 있었으나 시험 프로세스 종료 코드는 0입니다.
- [로컬 DB 원문](../evidence/2026-10-11_1936_team_plugin_implementation/case-state-routing-db.log): `python -m pytest tests/integration/controller/test_conversation_resume.py -k 'customer_choice or route_persists or failed_reroute' -q --tb=short` → 4 passed, 15 deselected. 같은 Case의 담당 변경·요청 기록과 실패 시 입력·토큰 보존을 실제 로컬 개발 DB에서 확인했습니다. 선택하지 않은 15개를 통과 분모에 넣지 않았습니다.
- `python -m ruff check tests/contract/test_case_state_table.py` → All checks passed.

mock 서버 시험: 미실행(화면 반응 미확인).

실서버 확인(서버 응답): 안 했음. 운영 cs 프로젝트 서버 API를 호출하지 않았습니다. 로컬 개발 DB를 사용하는 Controller 통합 시험만 실행했습니다. 운영 반영·원격 A2A 확인·커밋·푸시는 하지 않았습니다.

문서 원본은 [wiki 백업](../../_backup/2026-10-11_2113_case_state_contract/wiki/runtime/case-lifecycle.md), 시험과 이벤트 표 원본은 [legacy 백업](../../../legacy/team_plugin_lifecycle/2026-10-11_2113/)에 보존했습니다.
