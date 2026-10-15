# 확대 검증 v5/v6 읽기 검토 — 2026-10-12

v6의 실행 기록과 JUnit XML을 대조했으며, 실행된 412개가 모두 통과했습니다. 이 검토에서는 제품·시험 코드 수정이나 시험 재실행을 하지 않았습니다.

| 확인할 일 | 상태 | 진행 |
|---|---|---|
| v6 개별 시험 결과 대조 | 통과 | 412/412 = 100% |
| v5 실패·오류 표시의 시험명 매핑 | 확인 | 7/7 = 100% |
| 같은 7개 시험의 v6 통과 확인 | 통과 | 7/7 = 100% |

## 최종 실행 근거

- `../remaining-gate-v6/result.xml`: tests=412, failures=0, errors=0, skipped=0. testcase 요소 412개를 직접 세었으며 failure/error/skipped 자식 요소 0개입니다.
- `../remaining-gate-v6/execution.json`: exit_code=0, elapsed_s=20.34. 기록된 오프라인 차단은 동일 스레드 표준 socketpair 내부 IPC만 예외로 허용합니다.
- `../remaining-gate-v6.log`: 412 passed, 3 warnings in 18.38s. XML 시간은 18.371초입니다.
- `../run_remaining_v5.py`와 `../run_remaining_v6.py`: 같은 시험 파일·디렉터리를 선택하고 같은 OfflineOnly 플러그인을 사용합니다. 출력 위치만 v5/v6로 구분합니다.
- 실행 기록의 pytest 인자에는 `-m not live`가 포함됩니다. v5 수집 결과 412개와 v6 실행 결과 412개가 같고 skipped=0이므로 관찰한 412개 분모가 축소된 것은 아닙니다.

## v5에서 확인할 수 있는 범위

`../remaining-gate-v5.log`는 72개짜리 진행 행 3개(총 216개 표시)까지 남았습니다. 별도 수집 로그 `collection_remaining_v5.log`는 412개를 수집했습니다. 실패 표시 위치 101~104, 오류 표시 위치 192~194를 수집 순서에 대조했습니다.

| 표시 위치 | 시험 | v6 결과 |
|---|---|---|
| 101 | active_prompts: no_active_prompt_outside_the_allowlist | 통과 |
| 102 | active_prompts: exactly_one_active_version[response.generate] | 통과 |
| 103 | active_prompts: exactly_one_active_version[response.review_tone] | 통과 |
| 104 | active_prompts: deactivating_does_not_erase_history | 통과 |
| 192 | consumer_idempotency: duplicate_dedupe_key_has_one_side_effect | 통과 |
| 193 | consumer_idempotency: concurrent_claims_have_one_side_effect | 통과 |
| 194 | consumer_idempotency: timeout_is_unknown_and_not_automatically_retried | 통과 |

이 7개 시험은 소스상 DB 연결 경로가 있으나, v5의 실패 traceback과 완성된 XML은 확인되지 않았으므로 실패 원인을 DB로 확정하지 않습니다. v5는 중단되었으며 동일 범위의 v6에서 전부 통과했습니다. 이번 이동 코드의 신규 결함으로 분류할 근거는 확인되지 않았습니다.

진행 로그가 마지막으로 보여 준 것은 216개 표시입니다. PowerShell 출력 리디렉션이 불완전한 다음 행을 버퍼링할 수 있어 217번 시험 자체가 멈췄다고 단정할 수 없습니다. 다음 출력 행에 해당하는 217~288번 중 261번과 262번은 FastAPI TestClient를 실제로 구동합니다. 표준 socketpair의 샌드박스 정체는 다른 작업자가 재현했고, 이 검토는 그 재현을 독립적으로 수행하지 않았습니다.

## 경계와 남은 경고

- 코드 수정 0개, 추가 시험 실행 0개, 외부/API 호출 0회, 사용자 개인자료 접근 0회입니다.
- 실제 서비스 환경 배포·응답 확인은 이 검토 범위 밖입니다.
- 경고 3개는 `mobility/devtools/judgment_log.py:352`의 문자열 역슬래시 해석 SyntaxWarning이 반복 보고된 것입니다. 시험 실패와 구분합니다.
- 새 이름으로 만든 검토 기록이므로 기존 산출물 덮어쓰기·백업 대상은 없습니다. 이전 v5 로그와 v6 XML·로그를 보존합니다.
