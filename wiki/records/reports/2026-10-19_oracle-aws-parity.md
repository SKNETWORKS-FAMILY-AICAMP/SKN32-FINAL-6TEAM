---
type: report
title: 오라클 ARM · AWS(EKS) 운영 코드 ↔ role-manager 차이 표 (2026-10-19)
status: active
domain: travel
impl_scope: cs — 오라클 ARM · AWS(EKS) 의 cs 프로젝트 서버(api · worker · web · 관리자)와 role-manager
---

# 오라클 ARM · AWS(EKS) 운영 코드 ↔ role-manager 차이 표

확인 시각: 2026-10-19 18:40~20:30 KST. 이 세션(「오라클·AWS 앞선 수정 매니저·x600 반영」)이 읽기 전용으로 확인했다. 운영 설정 · 컨테이너는 바꾸지 않았다.

## 한 줄 결론

운영에만 있는 앞선 수정은 **넷**(배달 독립 반복 · R13 · R14 · 웹 직접 검색)이고 넷 다 role-manager 최신판 위로 다시 맞춘 수정본을 만들었다. 나머지 차이는 role-manager 가 더 새 판이거나, 팀 develop 에만 있는 코드이거나, 운영 전용 설정이다. 위험 안내 알림 dead_letter 수정은 이미 `505ca969` 로 들어갔다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 운영 파일 지문 받기(오라클 5 컨테이너 · AWS 3 파드 + 웹 빌드 입력) | 끝 | 9/9 = 100% |
| 다른 파일 가르기 | 끝 | 운영 판에만 있던 줄이 든 파일 전부 사람이 읽음 |
| (가) 수정본 만들기 · 시험 | 끝 | 4/4 = 100% |
| commit 세션 반영 · 두 원격 푸시 | 넘김 | 아래 「반영 상태」 |
| x600 서버 반영 확인 | 푸시 뒤 | 아래 「반영 상태」 |

## 어떻게 대조했나

1. 오라클 ARM 은 ssh 로 컨테이너 안 `/srv`(api · worker · 후보 r14 · 관리자) · `/app`(웹)을, AWS 는 kubectl 로 파드 안 `/srv`(api · worker · 관리자)를 읽어 파일마다 git blob 지문을 냈다. 줄 끝(CRLF)은 LF 로 맞춰 셌다 — 운영 이미지가 Windows 작업 폴더에서 빌드돼 줄 끝만 다른 파일이 760개쯤 있었다.
2. AWS 웹 파드에는 소스가 없다(빌드 결과만). 그 이미지를 만든 빌드 입력 `scratch/aws-location-consent-20261018/web-build-context.tar.gz`(지문 `d244c4f0…`, 이미지 증명 `image-proof.json` 과 같음)를 대신 대조했다.
3. 기준은 role-manager `eaa9a9c6`(두 원격 같음, 18:4x). 다른 파일마다 「운영 판에만 있는 줄 가운데 **git 이력 어디에도(모든 브랜치) 더해진 적 없는 줄**」을 셌다. 그런 줄이 있는 파일만 사람이 차이를 읽었다. 이진 파일(.gz · .png)은 원래 바이트로 다시 비교했다 — 모두 같음.
4. 이 방법이 놓칠 수 있는 것: 운영이 **줄을 지우기만 한** 수정. 그래서 「기준판(405f9706 · develop)과 role-manager 에 다 있는데 운영에만 없는 줄」도 따로 셌다 — 나온 것은 모두 role-manager 가 뒤에 더한 줄(운영이 더 옛 판)이었다.

도구 · 원자료: `scratch/oracle-aws-parity-20261019/`(remote_hash.py · compare.py · novelty.py · ops_removed.py · develop_only.py, 결과 `live/`).

## 숫자

| 곳 | 대조한 파일 | 다른 파일 | 그중 develop 판과 같음 | git 에 없는 줄이 든 파일 |
|---|---|---|---|---|
| 오라클 api(=worker 같은 이미지 r8) | 825 | 125 | 92 | 22 |
| 오라클 후보 r14(고객 경로 아님) | 825 | api 와 다른 5 | – | 5 |
| 오라클 관리자 r8 | 876 | 11 | 6 | 2 |
| 오라클 웹 r12 | 334 | 31 | 17 | 7 |
| AWS api(=worker) | 842 | 126 | 83 | 25 |
| AWS 관리자 | 807 | 51 | 25 | 16 |
| AWS 웹(빌드 입력) | 412 | 37 | 29 | 8 |

「다른 파일」의 대부분은 운영 이미지가 팀 develop(405f9706 이후)을 바탕으로 빌드됐기 때문이다 — role-manager 는 그 뒤 develop 을 다 받지 않았다. 「git 에 없는 줄이 든 파일」도 대부분 이름 바꾸기 전 문구(triPilot) · 줄 모양 차이였다.

## 가른 결과

### (가) 운영에만 있는 앞선 수정 — 수정본 만듦

| 무엇 | 운영 위치 | 수정본 | 맞춘 방법 | 시험(이 PC, 격리 사본) |
|---|---|---|---|---|
| 알림 배달 독립 반복(`deploy/worker.sh`) | 오라클 api · worker(r8) | `scratch/worker-delivery-loop-20261019/` | 오라클 판은 쓰지 않고 v2(98a868a7) 위에 다시 만듦 — 오라클 판은 v2 종료 시험 13/14 실패. 배달 간격 2초 → 10초(`WORKER_DELIVERY_SLEEP`, 오라클 worker CPU 30% · 10분 81회 실측) | worker 시험 40/40 두 번(Bash · dash 각 20, 새 시험 6종 포함) |
| R13 이동 자료 늦게 불러오기(되잡기만) | 없음(오라클 후보, 활성화 안 됨) | `scratch/r13-worker-lazy-20261019/` | baseline → candidate 를 role-manager 에 3방향, 충돌 0 | 68/68 |
| R14 출발 시각 시간대 · 출발 실패 사유 · 직접 이름 검색 종류 | 오라클 후보 컨테이너 r14(고객 경로 아님) | `scratch/r14-departure-search-20261019/` | r8 → r14 를 role-manager 에 3방향, 5파일 충돌 0 + 시험 4 · 계약 2 · 기록 3 | 191/191 |
| 웹 직접 검색 결과 상태 표시(`place-search-status.ts`) | 없음(배포 안 됨) | `scratch/explicit-search-web-20261019/` | 기준 파일이 role-manager 판과 같아 그대로 | vitest plan-check 253/253 · tsc · eslint 통과 |

합친 판 전체(unit · architecture · contract, DB 없는 것) 비교는 이 PC 부하로 13분에 15%만 진행돼 중단했다 — commit 세션의 반영 전 전체 시험으로 판정한다. 격리 사본에서는 시험 4개(`test_car_fare` · `test_check_scripts` · `test_judgment_log` · `test_declared_refs_are_savable`)가 저장소 루트 자료가 없어 수집 단계에서 오류였고, 기준판 `eaa9a9c6` 에서도 같았다. worker 시험은 Git Bash 에서 묶음 15회 중 1회 1개 실패가 남았다(원인 미확인, README).

### (나) role-manager 가 더 새 판 — 넣을 것 없음

오라클 · AWS 공통: `decision_unit.py` · `trip_messages.py`(pick) · `places.py`(시장은 구역으로) · `risks.py` · `itinerary.py`(완료 항목 제외) · `departure_revalidation.py` · `place_status.py` · `trip_watch_cases.py`(미룸 열쇠) · `wiring.py` · `notice_routing.py` · `llm_failover.py`(json_stream) · 이동 시각화 스크립트(이름만), 오라클 · AWS 웹(위험 패널 · 직접 고르기 · 채팅 알림), 관리자(사용자 목록 경로 · 운영 설정 · 시험 화면). 모두 운영 판이 앞선 git 판이거나 그 조각이다.

### (다) 운영 전용 — 넣지 않음

`migration-safety.json`(빌드 때 생성) · `next-env.d.ts` · 관리자 `test-results/` · AWS `deploy/aws-recovery-history/*.sql`(AWS DB 복구 계획) · AWS 웹 `traffic-renderer-live-evidence.test.ts`(로컬 증거 파일 경로를 읽는 시험) · 운영 환경 파일 · 키 · 프록시(이번에 읽지 않음).

### (라) 팀 develop 에만 있는 코드 — 이 작업 범위 밖

SNS 맛집 링크 · 요식 판정 에이전트 · 쇼핑 지점 운영시간(`social_dining*.py` · `dining/judge.py` · `sibling_hours.py` · 마이그레이션 232 · 905 등)과 develop 판으로 바뀐 파일 92개(오라클)/83개(AWS). git(develop)에는 이미 있다. role-manager 로 들이는 것은 develop 병합 결정이라 따로 둔다. ★주의: 오라클 · AWS DB 에는 마이그레이션 232 · 905 가 이미 적용돼 있다.

### 넣지 않은 것 · 이유

| 무엇 | 이유 |
|---|---|
| AWS `itinerary.py` 의 `with_told_hours` · `customer_hours`(고객이 알려 준 운영시간, 22줄) | AWS 파드 안 어디서도 부르지 않는 조각(파드 안 grep 1곳 = 정의만), git 이력 · 이 PC 기록에도 없음. 부르는 쪽 없이 넣으면 죽은 코드 — 기능 출처 확인이 먼저 |
| AWS ⑧ ITS 예비 키 | 사용자 보류 |
| AWS 웹 위치 동의(⑦) | 이미 `961856da` |
| 위험 안내 알림 dead_letter(`notice_routing.py`) | 이미 `505ca969`(0a761e95 판에 포함) |

## 반영 상태

- **반영**: commit 세션이 4묶음 + 이 표를 `380e3909`(부모 `0a761e95`, 29파일, 두 원격 role-manager 같음)로 넣었다. commit 세션 시험: ruff F · E9, unit + architecture + contract 8,222 통과(새 실패 0), 웹 vitest 934/934 · tsc · eslint, worker 종료 시험 39/40(아래 후속).
- **x600 서버**: 자동 배포가 21:03:38 `반영 완료 90d553923a (이전 0a761e950d)`(380e3909 포함). 21:05~21:15 읽기 확인 — worker 컨테이너 안 worker.sh 지문 `40e70fd4`(= 380e3909 판), R13(`preload_mobility=False`) · R14(`_DEPARTURE_INFEASIBLE_CODES`) 코드 들어감, 프로세스 구조 = 본 셸(PID1, `sleep 60`) + 배달 서브셸(`sleep 10`), 배달 1분에 5~6회, `{"job":…}` 실패 줄 0, worker · api 최근 15분 Traceback 0, 재시작 0, worker 메모리 7MiB(대기 중), 남은 발송 대기(pending · locked) 0, 공개 주소 `/` · `/health` 200.
- **실서버 확인 범위**: 배포 뒤 새 고객 알림이 0건(마지막 `trip.notice` 는 19:01 건너뜀 2건)이라 **실제 고객 알림 발송 · 위험 안내 경로는 확인 안 함**. 16:38~16:52 dead_letter 3건은 수정(`505ca969`) 전 것이고 다시 보내지 않았다. 종료(TERM) 때의 회수는 다음 배포 교체 때 worker 로그로 본다.
- **후속 v2**: commit 세션이 본 worker 시험 흔들림(`stop_at_job_completion[bash]`)은 배달 반복이 첫 신호 뒤 다음 신호를 무시해 생긴 것 — `scratch/worker-delivery-loop-20261019/followup-v2/`(worker.sh `643f8d6c` · 시험 대기 시한 10초 · 계약 한 줄)로 고쳐 commit 세션에 넘김→ commit 세션이 `9931b1ec`(부모 `90d55392`, 두 원격 같음)로 반영. x600 서버 21:21:33 `반영 완료 9931b1ecd7 (이전 90d553923a)`. 21:23 읽기 확인 — worker.sh `643f8d6c`, 본 셸 + 배달 서브셸 구조 그대로, 배달 1분 5회, 실패 줄 0, Traceback 0, 재시작 0, 발송 대기 0. 옛 worker 의 종료 회수 과정은 로그가 컨테이너와 함께 교체돼 확인 못 함(배포 시작 21:20:16 → 새 worker 기동 21:20:57).
- 매니저가 이 대조 뒤 `0a761e95` 로 움직였다(로딩 설문 · 이름 등 24커밋). 수정본 파일과 겹치는 변경은 없다(이름 대조 0건).
- mock 서버 시험: 없음(이 작업은 화면 반응 시험을 돌리지 않음). 실서버 확인(서버 응답): 아직 안 함 — 푸시 뒤 x600 배포 기록 · worker 로그로 확인한다.

## 남은 일

- (라) develop 코드를 role-manager 에 들일지 — 사용자 결정.
- `with_told_hours` 기능 출처 확인(10-13 「고객이 알려 준 운영시간」 결정의 구현이 어디 있는지).
- 오라클 · AWS 를 role-manager 판으로 다시 배포하는 것은 이 작업 범위 밖(읽기만 함).
