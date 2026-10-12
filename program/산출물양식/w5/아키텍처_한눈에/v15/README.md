# v15 — v14 + 제품 결함 수정 반영 (2026-10-03)

v14 는 그대로 두고 새 판으로 만들었다. 다시 만들기: `src/build_v15.py`.

## v14 에서 바뀐 것 (그림 2 · 문서)

| 자리 | v14 | v15 | 근거(제품 코드) |
|---|---|---|---|
| 활동 담당 반복 | 도구 12번 안에서 | 후보는 위 6곳까지 · 도구 한도에 걸린 후보는 「못 봤다」로 빼고 결과 | `itinerary_changes.py` ACTIVITY_RECHECK_LIMIT=6 · `itinerary_team.py` safe_recheck |
| 오류 끝 | 실행 멈춤 · 이번 점검의 남은 일도 멈춤 | 이 건만 멈춤 · 다른 일정은 계속 · 5분 뒤 다시 최대 3번 | `trip_watch_cases.py` · `config/guardrails.yaml` retry_max 3 · retry_cooldown_seconds 300 |
| 대안 못 찾음 | 고객 알림 없음(한계) | 고객에게 원인 알림 · **변경안 확인 실패는 아직 알림 없음** | `trip_watch_cases.py` _after_run(itinerary_unresolved 만) · `controller.py` _reject_unverified(degraded_context_blocks_action) |
| 답 없는 요청 | 열린 채(한계) | 그 일정이 끝나면 닫힘 | `trip_watch_cases.py` PendingStore.expire · `pending.py` choose |
| 번역 숫자 검사(부록) | 집합 포함 | 개수까지 맞춤 | `notify/translate.py` Counter |

고친 것은 제품 저장소의 로컬 커밋 `82aff095` · `06c3cb16` — 2026-10-03 기준 원격에 안 올라갔다.
코덱스 확인은 이번 판에서 다시 돌리지 않았다(바뀐 글을 코드와 직접 대조함).
