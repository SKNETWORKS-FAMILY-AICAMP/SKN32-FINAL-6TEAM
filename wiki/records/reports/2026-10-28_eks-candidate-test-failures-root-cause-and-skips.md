---
type: report
title: EKS 후보 전체 시험 실패 5건 · 요식 판정 1건 · 이동 계약 1건 원인 수정과 건너뜀 506건 분류 · 해소
description: ca879220b 전체 시험의 실패 2건(test_intake_read_lock · test_trip_events)과 dining 재실패(test_dining_agent_judge), 재검증 중 드러난 SSE 시험 3건과 자료 기기 전용 이동 시험 1건의 원인을 실측으로 규명해 시험만 고쳤다(앱 코드 0). 건너뜀 506건을 사유별로 나눠 485건을 격리 환경에서 실제로 돌렸다
status: draft
domain: travel
impl_scope: cs — final_project_cs/tests 6파일(e2e 4 · integration/dining 1 · unit/travel/mobility 1). 앱 · 배포 · 워크플로 0 (push 0 · PR 0 · 배포 0)
---

# EKS 후보 시험 실패 원인 수정 · 건너뜀 해소 — 2026-10-28

선행: [최종 통합 검증](2026-10-28_eks-migration-job-final-integration-check.md)(실패 2 · 건너뜀 506 / 13,583, dining 248/249)

## 결론

| 항목 | 결과 |
|---|---|
| 기준 | 팀 `main` `e88e01925` · `develop` `36ba4c2fc` — 10:3x · 21:37 `ls-remote`, 움직이지 않음. EKS 후보 `ca879220b` 위 **3커밋**(시험만): `ee606a5ef` · `1826f5f42` · `1dbef9e6d` = 브랜치 `fix/eks-candidate-test-determinism-20261028`(scratch clone `eks-fix-20261028/repo3`) |
| 앱 코드 변경 | **0** (`git diff e88e01925..HEAD -- final_project_cs/app` = 후보의 `migrate.py` 1개뿐) |
| 최종 전체 시험(CI main 재현) | 새 initdb PG 16.15(127.0.0.1:55541) · 새 DB, TZ → migrate → prompts → seed 모두 rc 0, 아키텍처 **170/170**, 전체 `-n 8 --dist loadfile --ignore=tests/integration/rag` **13,376 통과 · 실패 0 · 건너뜀 207 / 13,583 = 통과 98.5%**(건너뜀 포함 분모), rc 0, 1:20:51. 기존 대비 실패 2 → 0, 건너뜀 506 → 207 |
| 따로 돌린 건너뜀 해소 관문(같은 HEAD) | 합성 전용 DB **14/14** · WSL Linux bash · dash **40/40** · 공개 이동 자료 읽기 사본 **226 통과 · 건너뜀 1 / 227**(외부 연결 차단 기록 0) |
| 건너뜀 506 처리 | 전체 시험 안에서 실행 **299** + 별도 관문 실행 **186** = **485/506 = 95.8%** 실제 실행 · 통과. 남은 **21/506 = 4.2%**는 정책 차단 14 · 이 PC 에 자료 없음 7(아래 표) |
| 패치 | `ev/patches/0001~0003`. `e88e01925` · `36ba4c2fc` · `efc6fca47` 색인에 각각 `apply --cached --check` 통과, `ca879220b` 에 적용한 tree = HEAD tree `fd6b39cc7` |

## 원인과 수정 (실패 7건, 모두 시험 쪽)

| 시험 | 원인(실측) | 수정 | RED / GREEN |
|---|---|---|---|
| e2e `test_intake_read_lock::…does_not_wait_for_a_write` | 잠금이 아니라 **읽기 계산 시간**. `pg_stat_activity` 잠금 대기 표본 **0**인데 두 GET 이 각각 약 0.95 · 1.05초 → 합 2.0초로 `< HOLD_S−1(2초)` 판정 실패(단독 3회 중 1회). 기준 main 도 같은 원인 | 읽기가 끝날 때까지 잠금을 쥐고, **쥔 채로 끝났는지**로 판정(읽기가 잠그면 30초 상한까지 막혀 실패). 쓰기 대기 시험은 그대로 | 변이(읽기 길이 접수 행 잠금): 새 시험 실패(31.3초) · 원본도 실패. 원본 단독 1/3 실패 재현. 새 파일 3회 4/4 |
| e2e `test_trip_events::…signal_with_no_content` | 1.6초 연결 안에 두 변경 + 0.3초 조용한 틈이 다 들어가야 했다. CPU 부하(26 프로세스)에서 원본 **3/3 실패**(ping 없음 · itinerary 미관찰) | 스트림이 실제로 낸 글을 기록해 두 변경 신호와 그 뒤 ping 을 본 다음 틱에 닫는다(안전 상한 20초). 단언 그대로 | 부하 새 시험 3/3 통과. 변이(ping 제거): 새 시험 실패 |
| dining `test_dining_agent_judge::…dining_table` | `82eecd6b2`(10-20)가 옛 독립 호출도 `intake_state` 잠금 **뒤에** 읽게 바꿨는데 시험은 `load` 만 대역 → 요식 시험 DB 에 없는 `trip_intakes` 로 UndefinedTable. CI 는 dining 을 늘 건너뛰어 드러나지 않았다 | 접수 경계(`intake_state` · `load` · `store`)만 대역. 기존 행 단언 그대로 + `stale 0` · 합쳐 저장(`agent_judged`) 확인 추가 | 원본 1 실패(UndefinedTable) → 2/2 |
| e2e `test_op_stream` `fast_stream` 픽스처(…`marked_duplicate` · …`same_answer_as_json`) | 마감까지 FAST **5초**. 8일꾼 부하에서 채팅이 5초를 넘겨 `error{code: timeout, elapsed: 5.0}`(1차 · 2차 전체 시험에서 번갈아 실패, 부하 원본 2/2 실패) | 픽스처의 생존 신호는 빠른 값 그대로, **마감만 운영 값**(`travel.op_stream.max_seconds.<op>`). 시간 초과 동작은 `_run(cfg=…)` 시험이 따로 본다. 실패 메시지에 마지막 이벤트 | 부하에서 같은 마감 처리(당시 시험 단위)로 5/5, 픽스처로 옮긴 최종판은 최종 전체 시험(8일꾼) 통과 |
| e2e `test_intake_prepared_alternatives::…takes_its_result` | 준비를 「1초 뒤」 끝내 부하에서 요청보다 먼저 저장(`['accepted','result']`), 또 계산이 `beat_seconds` 를 넘으면 어림 카드 앞에 `beat` 가 끼었다(`['accepted','beat']`) | 「바꾸기」가 준비 중임을 실제로 본 뒤(`_claim` → None) 끝낸다. 순서 판정에서 생존 신호(`beat`)만 뺀다 | 부하 원본 2/2 실패 → 최종판 부하 3/3(`beat` 거르기 전 판 2/2). 변이(기다리지 않고 다시 계산): 실패. 두 파일 단독 34/34 |
| unit `mobility/test_plan_v1::test_contract_keys`(자료 기기 전용) | `2b22b09ff`(10-23)가 `departure_context` 에 계획 후보 + 「더 보기」 후보를 함께 담게 했는데(고객이 고르면 `selected_context` 가 꺼낸다) 기대 `== options` 가 갱신되지 않았다. 자료가 없는 CI · 일반 PC 에서는 건너뛰어 숨어 있었다 | 계획 후보는 모두 포함 · 나머지는 `MORE_MAX` 안의 온전한 후보. 기존 값 대조 그대로 | `{'subway_1','subway_2'} == {'subway_1'}` 실패 → 파일 56/56 |

★ 「단독은 통과」를 환경 탓으로 남기지 않았다. 7건 모두 벽시계 창 · 고정 대기 · 갱신 안 된 대역/기대값이 원인이었고, 제품 결함은 찾지 못했다(잠금 · ping · 준비 기다리기 동작은 변이로 시험이 잡는 것을 확인).

## 건너뜀 506건 — 사유별 처리 (분모 = 기존 전체 시험의 건너뜀 nodeid 506)

| 사유 | 건수 | 처리 | 결과 |
|---|---|---|---|
| dining 통합 — 기본 포트 5433(공유 로컬 DB `C:\_proj\postgresql\data\guguroute-16`, scram)에 비밀번호 없이 접속 시도 | 246 | `DINING_PG_PORT=55541`(격리) 를 주고 전체 시험 안에서 | 246/246 |
| PGlite 필요(`OPS_PGLITE_MODULE`) | 37 | scratch 에 `@electric-sql/pglite@0.3.14`, 전체 시험 안에서 | 37/37 |
| task-owned PostgreSQL(`integration_test` 전용 DB) | 8 | 격리 클러스터에 `integration_test` 역할 · DB | 8/8 |
| 독립 OAuth DB 실행기(`ACOP_OAUTH_TEST_ISOLATED=1`) | 8 | 격리 DB 에서 | 8/8 |
| 합성 전용 DB(`semantic_synthetic` · 127.0.0.1:15544 · 가드 표) | 14 | 두 번째 새 클러스터, migrate · seed 뒤 별도 관문 | 14/14 |
| 실제 Linux bash(POSIX) · dash | 40 | WSL Ubuntu(Linux 6.18, `/bin/sh`→dash) 에서 별도 관문 | 40/40 |
| 이동 공개 자료(시간표 · 그래프 · 수집 스크립트 등, git 밖) | 133 | 원본 `datasets/mobility/{processed,scripts}` 를 scratch clone 으로 **읽기 복사**(원본 쓰기 0), 외부 연결 차단 plugin | 132 통과 · 1 건너뜀(아래) |
| **남은 21** | | | |
| 정책 차단 — 실제 요식 원장 · 실제 공개 사실 식당 · TourAPI 원장 적재 · 미쉐린(제3자 자료, 로컬에 있으나 미실행) · 실모델 재생 · 외부 API · 실제 보행망 live | 5+2+1+2+2+1+1 = **14** | 합성 아님 · 제3자 · 실호출이라 실행하지 않음 | 미실행 |
| 이 PC 에 자료 없음 — 학습 산출물(감성 모델) 4 · H 원본(`datasets/core/pointing`) 2 · 서울 보행 그래프 · 건물 출입구 1 | **7** | 원본 작업 폴더에도 없음 | 미실행 |

- 485 + 21 = 506. 최종 전체 시험의 건너뜀 207 = 별도 관문 186 + 남은 21.
- **공유 DB 접속 시도**: 기존 전체 시험의 dining 246건이 `tests/integration/dining/conftest.py` 기본값(`localhost:5433`, user postgres, 비밀번호 없음)으로 공유 로컬 DB 에 접속을 시도했다. 인증 단계에서 끊겨 세션 · 쓰기는 없었다. 시험 코드에서 5433 을 기본으로 쓰는 곳은 이 conftest 하나다(`grep`). 이번 실행은 모두 격리 포트를 명시해 공유 DB 시도 0. 이 기본값은 팀 dining 개발 DB 관례(`scripts/dining/dev_up.py` 도 5433)라 바꾸지 않았다 — 접속이 열리면 그 클러스터에 `dining_test_<pid>` DB 를 만들고 지운다는 점은 남는 위험이다.
- **CI 공백**: CI (main) 는 `DINING_PG_PORT` 가 없어 dining 249건 중 DB 246건을 늘 건너뛴다(`test_dining_agent_judge` 결함이 숨은 이유). 워크플로는 이번 범위에서 고치지 않았다.

## 격리 · 안전

- DB: scratch 새 initdb 클러스터 2개(55541 · 15544, trust · 127.0.0.1)만 사용, 끝난 뒤 `pg_ctl stop`(LISTEN 0) 하고 지웠다. 합성 자료만 썼다(실고객 0). 외부 연결 차단 plugin 기록 0.
- 원본 작업 폴더: `safe_git.py ls-remote` · 읽기만. 원본 `datasets/mobility` 실행 뒤 새 파일 0(`find -newer`).
- push · PR · 배포 0. AWS · x600 접속 0.
- 지운 것(다시 만들 수 있는 것): `eks-fix-20261028/{pgdata,pgdata2,tmp,repo,pglite}`, repo3 의 이동 자료 읽기 사본, WSL `~/.cache/eksfix-*`. 남긴 것: `repo3`(브랜치) · `ev/` · 실행 스크립트.

## 증거 (Hermes profile scratch `eks-fix-20261028/`)

- 최종: `ev/full_fix3/`(0~5 log · rc · `4_arch.xml` · `5_full.xml` · `head.txt`=`1dbef9e6d`) · `ev/gate3_{semantic,wsl,mobility}/`
- 중간 전체 시험(보존): `ev/full_fix/`(실패 2 — op_stream 중복 · 준비 대안) · `ev/full_fix2/`(실패 1 — op_stream JSON 같음)
- RED/GREEN: `ev/probe_lock/`(요청별 시간 · 잠금 대기 표본) · `ev/stress_events/` · `ev/mutants/` · `ev/stress2/` · `ev/stress3/` · `ev/dining_redgreen/` · `ev/gate_mobility/`(최초 실패) · `ev/gate_mobility_fix/`
- `ev/patches/0001~0003-*.patch` · `ev/hashes.txt`(바뀐 시험 6파일 sha256) · `ev/final_remaining_skips.json`(남은 21 nodeid)

## 다음 일 (부모 · 사용자)

1. 이 3커밋을 EKS PR 에 함께 올릴지 별도 PR 로 낼지 정한다(시험만, `main` · `develop` · `role-manager` 모두 그대로 적용됨).
2. CI (main) 에 dining DB 시험을 넣을지(`DINING_PG_PORT` · 비밀번호) 팀이 정한다 — 지금은 246건이 CI 에서 늘 건너뛴다.
3. 정책 차단 14건(실데이터 · 실모델 · 외부 API)은 별도 승인 없이 돌리지 않는다.
