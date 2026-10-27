# 2026-10-27 전수검사 A~J 후보 통합 · role-manager 반영 (세션 K)

- 작성: 2026-10-27 17:0x KST, Claude(K). 사용자 지시: 「전수검사 후보 모두 반영」, 시연(14:00) 뒤 push 금지 해제.
- 기준: 팀 · 개인 `role-manager` = `064208bdd453b0ee7322439b1db728fec6d4d506`(16:08 · 17:05 `git ls-remote` 두 번 확인, 바뀜 없음). develop(`9c4a018f`) · main(`b4c2847e`)은 건드리지 않았다.
- 트리: `cache/scratch/integ-K-allaudit-20261027`(sparse: final_project_cs · final_project_sample · .github · program/scripts/rag_gate · wiki/handoff), 브랜치 `integ/K-allaudit-20261027`. 원본 작업트리 미변경. 증거 `cache/scratch/integ-K-ev/`.

## 1. 후보별 통합 결과 (9/9 = 100% 통합, 제외 0 · I 는 원래 범위 밖)

| 순서 | 후보 | 원 tip | 커밋 | 충돌 · 처리 | 단계 빠른 관문 |
|---|---|---|---|---|---|
| 1 | F 통합(T04 되묻기 · 일정 수정 완료 503 save_failed) | 7ba115305 | 5 (fast-forward) | 없음 | (F 자체 10,345 통과) |
| 2 | C 컨트롤러 · 감시 · 실패조치 | eaa649f40 | 7 cherry-pick | 코드 충돌 없음. 계약 단락 정합 커밋 1개(아래 2-1) | 10,402 통과 · 실패 0 |
| 3 | B 채팅 경로 | ba1a42860 | 3 | 없음 | 10,423 · 0 |
| 4 | G 모델 품질(해석 문법) | 9281a2df2 | 4 | `trip-chat-context.md` 문서 충돌 — B 세 줄 + G 절 둘 다 보존 | 10,448 · 0 |
| 5 | A 접수 · 읽기 | a0c677181 | 8 | 없음 | 10,466 · 0 |
| 6 | D 웹 읽기 막대 · 폴링 | 10b537cdc | 2 | 없음(프론트만) | (아래 E·H 와 함께) |
| 7 | E 장소 · 운영시간 · 검색 | f5edf4784 | 7 | `wiki/log.md` — C · E 두 줄 모두 보존 | (H 와 함께) |
| 8 | H 서빙 속도 | a29e2d8eb | 3 | `pipeline.py`(A) · `guardrails.yaml`(C) 자동 병합 | 10,519 · 0 (D+E+H 누적) |
| 9 | J TeamFlow | 4cbfe2a01(별도 clone 에서 fetch) | 4 | `wiki/index.md` — F · J 두 줄 모두 보존 | 10,530 · 0 |
| + | 통합 수정(K) | — | 2 | 아래 2-1 · 2-2 | — |

제외: **I(EKS, 1b38aa7ef)** — main 기반 · aws_cd/cd-aws/ci-web 변경이라 별도 PR 대상(지시대로 손대지 않음). 분석만 §4.

### 2-1. 같은 일을 두 세션이 한 곳 — 저장 실패 다시 읽기 (F 7f19fe4cd ↔ C)
- 코드: C 의 `conversation/storage_failure.guarded` 는 `chat_edit._unchanged_after_failure` 를 부르고, F 뒤 이 함수는 공용 `intake/reopen_commit.version_unchanged_after_failure` 로 넘긴다 → 다시 읽기 구현은 **하나**. 중복 · 상충 없음(빠른 관문 · DB 시험 근거).
- 계약: `web-intakes.md` 의 F 문장 「승인 경로(`_apply_approved`) 저장 실패는 아직 계약 밖」이 C 가 같은 날 닫은 사실과 어긋나 → C 단락을 가리키게 고치고, C 단락에 다시 읽기 공용 함수 하나임을 적었다(커밋 `ad4aa4c30`).

### 2-2. 새 거절 코드의 웹 문구표 짝 (스킬 규칙: 새 서버 거절 코드 = error-text.ts 한 줄)
- `409 intake_not_ready`(A 의 등록 준비 거절 · 기존 registration) · `409 over_price_limit`(J ST4F-709, `detail.price_limit`)가 `REFUSAL_TEXT` 에 없어 영어 화면이 「The request could not be completed … (code)」로 떴다.
- 시험 먼저: `error-text.test.ts` 2건 RED(2 failed) → 문구 추가 → 9/9 GREEN(커밋 `c91289b16`). 한국어 화면은 서버의 해요체 문장을 그대로 쓴다(기존 규칙). E 의 `outside_service_area` 는 거절 코드가 아니라 검색 `notes` 이고 E 가 `place-search-status.ts` 에 이미 처리.

### 2-3. 알려 둘 정책 변화 (사용자 「모두 반영」 지시로 포함)
- C 가 재난문자 훈련 판정 제외 낱말을 넓혔다(`가상 상황` · `시험 발송` 등 + 실제 사건 표지 · 조건 꼬리). 이전 운영 메모는 「낱말 변경은 사용자 결정」이었다 — 이번 반영은 사용자 지시 「전수검사 후보 모두 반영」에 따른 것이며, 근거는 C 보고서의 전국 50,070건 실측(판정 갈림 2건 · 새로 버림 0).

## 3. 최종 tip 검증 (`c91289b16` 기준, 보고서 커밋 전 코드 트리)

| 검사 | 결과 |
|---|---|
| 빠른 관문(architecture · contract · unit · security · eval, not live/db/slow, 격리 러너) | 10,530 통과 / 10,530 실행 = **100%** (건너뜀 178 · 선택 제외 680, 실패 0) |
| vitest 전체(web) | 1,217 / 1,217 = **100%** (135 파일) |
| tsc `--noEmit -p tsconfig.json`(web) | 오류 0 |
| ruff 0.16.8 `check .`(CI 와 같은 명령, sparse 트리) | 통과 |
| DB 시험 core(비교 DB `gugu_replay_improved_20261025` · 새 tenant · 격리 러너): test_chat_edit_web · test_trip_reopen · test_chat_add_lodging_kind_web(B 신규) · 승인경로 통합 test_travel_approval_proposal_reaches_waiting(C) · test_auto_apply_proposals | 89 / 89 = **100%** (11분 47초) |
| DB 시험 intake: tests/e2e/test_intake_*.py 36 파일(같은 비교 DB · 새 tenant) | 332 / 332 = **100%** (37분 51초) |
| 실 E4B 수용 49(G 와 같은 하네스 복사본, `--local-runtime-stream` 라벨 · live runtime v10c · num_ctx 12288 · lease owner K-allaudit) | 엄격 **39/49 = 79.6%** (이전 기준 38/49, G 후보 39/49 — 줄지 않음, 회귀 0) |

수용 49 행 비교(기준 G-real-base → G-real-cand → K 통합):
- F02: fail → pass → **pass** (G 의 anchor_kind 갈래).
- 실패 10행은 G 후보와 같은 행: I01~I08(`public_not_registered_reply` — 로컬 전용 L02 계획 작성기 기대값, 낡은 기대 · I05 는 날짜 칸 모두 통과하고 이 검사만 남음, I01 은 모델 정지), T04(`public_status: clarify` — F 의 범위 경계 되묻기가 의도한 답, 행 기대값은 「바로 적용」이라 계약 갱신 필요), T15(공개 상태 기대 — 이전과 같음).
- X02 · F03 은 통과 유지.

DB 시험 사후 대조(`cmp.txt`): 바뀐 행은 새 tenant 뿐이다(기존 tenant 행 변경 0).

## 4. C `migrate.py lock_policy` ↔ I `aws_cd.py` 잠금 제한 — 분석만(I 미통합)
- C: `apply_all` 맨 바깥 호출에서 시도마다 `SET LOCAL lock_timeout = <migration-plan.json lock_policy.lock_timeout_ms=5000>ms`, 교착(40P01) · 잠금 초과(55P03)만 3회(대기 3 · 10초) 재시도, 실패 한 줄 JSON. 중첩 호출(트랜잭션 안)은 재시도하지 않는다.
- I: EKS 마이그레이션 Job 스크립트가 `set_config('lock_timeout','5s',false)` · `statement_timeout 5min` 을 먼저 걸고 확인한 뒤 `apply_all(conn)`.
- **상충**: psycopg 기본 autocommit 꺼짐이라 I 의 `SELECT set_config…` 뒤 연결이 트랜잭션 안(INTRANS) → C 의 `apply_all` 은 중첩 경로로 가서 **재시도가 꺼진다**. 값도 두 곳(I 상수 `"5s"` · C json 5000ms)이다.
- 권고(I 를 main 에 낼 때): set_config 확인 뒤 `conn.commit()`(세션 설정은 유지) 하고 `apply_all` 을 맨 바깥으로 부르게, lock_timeout 은 `migration_plan.lock_policy` 한 곳에서 읽고 I 상수는 statement_timeout 만 남긴다. I 의 종료 기록은 `MigrationLockFailed.sqlstate` 를 그대로 싣는다(호환).

## 5. push · 배포
- push 대상 = 이 보고서를 담은 커밋(`integ/K-allaudit-20261027` tip). 직전 `git ls-remote` 로 두 원격이 064208bdd 그대로일 때만 fast-forward(force 없음). 원격 SHA · CI(main) 수동 실행 · x600 deploy.log 결과는 push 뒤 세션 K 최종 보고와 `cache/scratch/_coord/K-allaudit-integration-NOTICE.md` 에 적고, 다음 기록 커밋에 옮긴다(문서만 다시 push 하면 x600 배포가 한 번 더 돈다).

## 5-1. 추가 기록 — 첫 push(9a15223e0) 뒤 결과 · CI 고침 (17:16~17:4x)
- push: 17:16:08 팀 · 개인 role-manager `064208bdd → 9a15223e0`(fast-forward, 직전 ls-remote 두 원격 064208bdd 확인).
- x600: `deploy.log` 17:20:10 시작 → `Deployment safety migrate: passed`(재시도 줄 없음 · 교착 재현 안 됨) → 17:23:26 「반영 완료 9a15223e0c (이전 064208bdd4)」, 공지판 `deploy:9a15223e0c` done, `/health` 200.
- CI (main) [40472347206](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40472347206): 13,041 통과 · **2 실패** · 466 건너뜀(ruff · Docker 통과). 실패 2건은 `tests/integration/db/test_migrations_rerun.py` 의 임시 plan(`lock_policy` 없음)이 C 의 「lock_policy 없으면 시작 안 함」 계약에 걸린 **시험 낡음** — 운영 plan 에는 정책이 있고 x600 마이그레이션도 통과. 고침: 임시 plan 에 실제 plan 의 `lock_policy` 를 그대로 싣는다(단언 그대로, 값 새로 만들지 않음). 로컬 격리 러너는 임시 DB 생성을 막아 이 파일이 건너뜀 → 판정은 CI 재실행.
- CI (web) [40472351405](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN32-FINAL-6TEAM/actions/runs/40472351405): check 통과, live 238 통과 · **1 실패** — `server-review.spec.ts:51` 「실시간 진행이 열렸다가 아무 소식도 없으면 「연결이 끊겼어요」를 알리고 폴링으로 끝까지 따라간다」. **제품 회귀(D)**: D 가 「끊긴 동안만 폴링」으로 바꾼 뒤, 죽은 줄에 다시 붙어 인사(`accepted`)만 받아도 `live` 로 돌아가 폴링을 멈춰 읽기가 화면에서 끝나지 않았다(10-03 규칙 「고객이 멈춘 화면에 앉아 있지 않게」 위반). 고침: `follow.followAfter` — `lost` 뒤 인사만으로는 `live` 가 아니고 단계 · 박동 · 끝이 와야 폴링을 멈춘다(D 의 「살아 있는 줄 옆 타이머 없음」은 유지). 단위 시험 RED 1 → GREEN, vitest 1,218/1,218 · tsc 0 · eslint 0. Playwright 는 이 PC 에 브라우저가 없어 CI (web) 재실행으로 판정.

## 6. 디스크
- 시작 16:06 C: 여유 998M. `modelq-G-20261027/base`(064208bdd 깨끗한 비교 트리, 변경 0) worktree 제거로 2.6G. 통합 트리 sparse(약 0.4G) 뒤 2.1~2.2G.
- web node_modules 는 `integ-F-20261027` 것을 junction(package-lock md5 `fbf752db…` 같음).

## 남은 일
- T04 수용 행 기대값을 F 의 되묻기 계약에 맞출지(행 갱신) — 계약 · 시험 근거로 별도.
- I05 의 W2 검사 · I0x `public_not_registered_reply` 낡은 기대 정리.
- I(EKS) PR 때 §4 권고 반영.
- `trip_api._choose` · `_create_trip` 저장 실패(C 보고서 남은 일).
