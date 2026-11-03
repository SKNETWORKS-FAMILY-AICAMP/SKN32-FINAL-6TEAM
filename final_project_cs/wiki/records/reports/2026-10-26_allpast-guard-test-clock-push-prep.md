---
type: report
title: 전부-과거 가드 시험 시계 고정 — 원격 3갈래 최신 HEAD 기준 로컬 커밋 준비
status: verified
domain: travel
---

# 전부-과거 가드 시험 시계 고정 커밋 준비 (2026-10-26 KST)

push는 하지 않았다. live·원본 코드·제품 코드 변경 0. 작업 폴더 `cache/scratch/clockfix-push-20261026-025217/`.

## 결론

| 대상 | 원격 HEAD(마지막 ls-remote) | 로컬 커밋 | 변경 | 빠른 관문 | 모의 시계 10-27·12-01 | DB 관문 가드 422 |
|---|---|---|---|---|---|---|
| 팀 SKN develop | 7c326cbb | f57be997 (작업트리 `team-dev2`) | conftest +25, dining 시험 ±3 | 9380/9380 = 100% (skip 173) | 날짜 차이 0 | 0 (509/509 = 100%, skip 23) |
| 개인 A-COP develop | d8366bbf | 22ea65c7 (`personal-dev`) | conftest +25 | 9112/9112 = 100% | 날짜 차이 0 | 0 (507/507, patch 전 167건 실패 중 가드 137건 메시지) |
| 팀·개인 role-manager | da4ccd97 | 376f2a67 (`rm3`) | conftest +25 | 9311/9311 = 100% | 날짜 차이 0 | 0 (507/507, skip 23) |

- 팀 develop: 처음 d2ab93a6 위 f506c463 으로 만든 뒤 원격이 7c326cbb(frontend·wiki 만)로 진행돼 cherry-pick. `final_project_cs/app`·`tests` 트리 해시가 검증 커밋과 같다(DB 시험 파일은 frontend 를 읽지 않음). 빠른 관문은 새 트리에서 다시 돌렸다.
- role-manager: 2ce73990 → 53c3c273(096a672a, 검증 완료) → da4ccd97 로 두 번 재기준. 최종 376f2a67.
- 개인 develop 은 팀과 다른 줄기(5d52dfbf 기준). dining 시험 파일이 없고, patch 전에도 빠른 관문 날짜 민감 시험 0건. DB 관문만 가드에 걸린다 → conftest 고정만 넣었다.

## 검증 방법

- 빠른 관문: `tests/architecture tests/contract tests/unit tests/security -m 'not live and not db and not slow'`, DB·네트워크 차단 runner(`run_clkp.py`).
  - git 없는 PATH 에서는 패치 전후 모두 같은 3건(test_api_key_file 2, test_no_infra_in_tracked_files 1, Python subprocess 의 WindowsApps git WinError 5)이 실패했다. scratch 의 portable git 을 PATH 앞에 두니 0건.
- 모의 시계: `FCLK_SHIFT_TO` 로 가드 모듈 시계를 옮겼다. 패치 전 팀 develop 은 10-27·12-01 에서 dining 6건 실패, 패치 후 0건.
  - 고정 시계를 우회하는 probe(`CLKP_BYPASS_PIN`)로도 dining·가드 43/43.
- 가드 RED: 가드를 끄는 plugin(`CLKP_GUARD_OFF`, 파일 무수정)으로 test_all_past_dates·test_all_past_confirm_api 13건 중 6건 실패, 켜면 13/13. 모든 트리 동일.
- DB 관문: 비교 DB `gugu_replay_improved_20261025` 만 사용, 새 `clkp_*` tenant. 이전 보고서의 38/37 파일 목록(전역 표·DDL 파일 제외: dining 원장·safety·web_api·activity_catalog_pool·watch_failures/relaxed·simulation_guest_catalogue·watch_simulation·watch_monitoring).
  - 실행 전후 행 수 변화는 다른 작업자 tenant(acceptance_matrix_*, integ_v9_chat_*)뿐. 내 tenant 잔여 0.
  - rm 53c3c273 트리: 부하 중 timing 시험 1건(test_plugin_unavailable deadline) 실패 → 단독 재실행 33/33.
- ruff 0.16.8 `ruff check .` (CI 와 같은 판): 모든 트리 0.

## 한계

- DB 관문은 CI 전체가 아니라 안전한 파일 목록만 돌렸다. 제외 파일은 빈 DB CI 에서 확인 필요.
- 분류기의 `B_future_break` 는 고정 전 시계 기준 예측값이다. 고정 후 가드의 오늘은 2026-08-01 로 일정해 해당되지 않는다.
- push·x600·로컬 서빙 모두 반영 안 함.
