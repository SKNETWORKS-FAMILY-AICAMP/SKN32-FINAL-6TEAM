# 2026-10-26 팀 develop 전체 시험 복구 확인

- 문제: develop→main PR 의 `CI (main)` 「전체 시험 (live 제외)」가 7c326cbb 에서 실패(384 failed · 95 errors, run 40224187039). 실패 메시지 608곳이 `all_dates_in_past` — 고정 날짜 fixture 가 전부-과거 가드에 걸림.
- 수정: 팀 develop f57be9970a7d583f9a3cb4f11638439cffb5b594 (tests/conftest.py 가드 시계 고정 + dining 시험 주입점, 제품 코드 변경 0). 개인 develop 22ea65c7, 팀·개인 role-manager 376f2a67 동일 수정.
- 확인: f57be997 에서 `CI (main)` 수동 실행(workflow_dispatch, run 40227135126) → **success**. 「전체 시험」 11902 passed · 466 skipped · 0 failed, 아키텍처 168 passed, ruff·Docker 빌드 success. `CI (develop)` run 40226609671 success.
- 날짜와 무관해 보였던 실패(desk_gate 4 · lock_needs_confirmed_item 4 · KeyError density 등)도 이번 실행에서 0 — 같은 원인(등록 거절 연쇄)이었다.
