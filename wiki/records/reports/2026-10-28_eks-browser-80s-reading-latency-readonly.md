---
type: report
title: EKS 실제 브라우저 시험 80.7초 「읽는 중」 · 58초 연결 끊김 — 서버 경로 읽기 전용 추적과 개선 후보
description: guguroute.devroro.click(EKS, main e88e01925) 손님 예시 6일정 시험의 병목과 연결 끊김 원인을 서버 판별 · 코드 경로 · 공개 경로 측정으로 좁히고, x600 기준선과 과장 없이 비교한 기록
status: draft
domain: travel
impl_scope: cs — 진단만(코드 · 설정 · DB · 서비스 변경 0)
---

# EKS 브라우저 시험 80.7초 · 연결 끊김 — 읽기 전용 추적 (2026-10-28 00:05~00:40 KST)

## 결론

| 항목 | 결과 | 근거 수준 |
|---|---|---|
| 시험 서버 | **AWS EKS**(ap-northeast-2, namespace `tripilot`), 팀 **main `e88e01925`** — CD (AWS) run `40488146501` 이 10-27 19:42 KST 에 api · worker · web · admin 이미지 digest 와 공개 `/health` · `/` 200 을 확인한 판. 속도 후보 A(`3ea98bc48`) · B(`b0c334285`) 포함 | 확인(DNS · 응답 헤더 · x600 DB · CD 기록) |
| x600 이 아님 | x600 DB 에 이 접수 0행, 최근 2시간 접수 0건. guguroute 응답에는 x600 의 `via: 1.1 Caddy` 가 없고 x600 Caddy 설정에도 guguroute 이름 0건 | 확인 |
| EKS 서버 쪽 시각(DB · 로그 · pod 지표) | **못 읽음** — x600 의 AWS 자격증명 `InvalidClientTokenId`(00:10), 이 PC 에 aws CLI · kubectl · `~/.aws` 없음. 이 접수의 단계 시각 · 동시 접수 · CPU 제한(throttling) · 재시작은 **미확인** | 막힘 |
| 80.7초의 정체 | 웹 「완료」 = 서버가 `status=review, stage=review` 로 넘긴 뒤(먼저 채우기 · 해석 답 반영까지 끝) + 웹 표시 속도 조절(줄 읽기 ≤5초 · 단계당 ≥0.9초). 그 뒤 **5초 자동 넘김은 설계된 대기**(도움말 「5초 뒤 계획 확인 화면」)라 처리 시간이 아니다 | 코드 확인, 서버/웹 분할은 미측정 |
| 58초 연결 끊김 | 웹은 **7초 동안 SSE 이벤트가 없으면** 「연결이 끊겼어요」로 바꾸고 다시 붙는다(`STREAM_TIMING.watchdogMs=7000`). 서버의 접수 SSE(`op_stream.watch`)는 beat 를 **DB 읽기(`read`) + 내용 계산(`content`) 이 끝난 다음에만** 낸다 → 한 회차가 7초 넘게 막히면 서버가 살아 있어도 끊김으로 보인다 | 코드 확인 · 가장 유력한 기전. 무엇이 막았는지는 미측정 |
| 막힘 후보(미측정) | ① 접수 읽기 전체가 **API pod 안 BackgroundTasks** 로 돈다(`trip_api.web_intake` → `pipeline.process`) — 같은 프로세스 · GIL · CPU 를 SSE 와 나눈다. ② 배포 스크립트 주석 「A single small node cannot fit two API pods plus the worker」 — 작은 노드 1대에 api · worker · web · admin. ③ 이동 계산기는 AWS t3.medium 측정에서 **구간당 약 2.2초**(24구간 53.7~56.5초), 뒤에서 이동 계산이 돌면 다른 요청 1.7~2.2배 느려짐(10-20 자유 스레드 보고서, 측정 기계는 EKS 노드와 별개) | 정황 |
| 공개 경로 상태(시험 뒤, 한가할 때) | `/health` 200 20/20 · p50 0.067초 · 최대 0.326초, `/events` 미인증 401 5/5 · p50 0.085초, 접수 GET 미인증 401 5/5 · p50 0.096초 — 경로는 조립돼 있고 한가할 때 연결 지연은 작다. ★401 지연은 고객 폴링 지연이 아니다 | 측정 |
| x600 기준선과 비교 | x600(채팅 접수, 10-20~10-26) 「읽는 중」 p50 21.8 · p95 64.1초(152건, 오늘 재현). 이번 80.7초는 **한 건 · 다른 서버 · 다른 끝점(브라우저 완료 vs DB 채우기 끝)** 이라 p95 보다 크다는 것 외에 개선/악화를 말할 수 없다. x600 의 A·B 반영 뒤 접수는 아직 0건(17:23 이후) | 측정 · 비교 한계 명시 |

## 1. 서버 판별

- DNS: Cloudflare 프록시 IP(104.21.x · 172.67.x). `tripilot.devroro.click` 은 응답에 `via: 1.1 Caddy`(x600 Caddy), `guguroute.devroro.click` 은 없음.
- x600: `docker ps` 에 tripilot 4 + db, jikimi 4. Caddy 설정의 이름은 jikimi · tripilot 뿐. x600 DB(`acop_cs`)를 `BEGIN READ ONLY` 로 조회 — 이 접수 0행.
- GitHub: `CD (AWS)` 마지막 성공 = `e88e01925`(run `40488146501`, 배포 기록 `checked_at 10:42:29Z`, migration Job 이름 · digest 4개 · 공개 health 200). 그 뒤 main 커밋 없음(fetch 00:1x 기준). 수동 변경 여부는 자격증명이 없어 확인 못 함.

## 2. 요청 경로(main `e88e01925`)와 시험 관측의 대응

| 브라우저 관측 | 서버 코드 구간 | 비고 |
|---|---|---|
| 0초 제출 | `POST /v1/web/trip-intakes` → `BackgroundTasks(process)` (API pod 안) | worker pod 가 아니다 |
| (일정이 보이기 시작) | `read_source` — 모델 읽기(`reader_structured_stream`, 넘김 장치) | EKS 의 읽기 모델 · 넘김 설정은 미확인 |
| 날씨 등 점검 ~17–27초 | `review.ensure(force)` → `risks.decorate(fresh)` — 첫 일정 혼자, 나머지 3개 동시(후보 A). 외부 소스 1회 상한 8초 | 10초 창은 x600 위험 점검 p50 4.2초보다 길다(한 건이라 비교만) |
| 먼저 채우기 ~32–48초 | `_prefill` → `prefill.run`(autofix 계획 · 담당 제안 · `pipeline.edit` 재검사 = 이동 다시 계산) | 이동 계산은 CPU 일 |
| ~58초 「연결이 끊겼어요」 | 48초 뒤: `_apply_interpretations`(답이 있으면 `pipeline.edit` 재검사) → `stage=review` | 이 구간에서 SSE 회차가 7초 넘게 막힌 것으로 보이나 **서버 시각 없이 단정 못 함** |
| 80.7초 완료 | `public_status` 가 `reading` 을 벗어남 → SSE `result` 또는 끊긴 동안의 1.5초 GET 폴링으로 확인 | 웹 표시 속도 조절 포함 |
| +5초 자동 넘김 | 웹 완료 막대(설계) | 처리 시간 아님 |
| (화면 뒤) | `_prepare_alternatives(not_meals)` → `_dining_judge` → `_prepare_alternatives(meals)` — 같은 API 프로세스에서 8스레드 풀 | 계획 확인 화면의 반응도 같은 CPU 를 나눔 |

웹 쪽 「끊김」은 서버 쪽 「실패」와 다르다: 끊긴 뒤 웹은 1·2·4…초로 다시 붙고, 그동안 1.5초마다 GET 으로 끝까지 따라간다(통합 K `followAfter`). 그래서 접수는 정상 완료됐다.

## 3. 개선 후보(우선순위 · 근거 · 위험)

| # | 후보 | 기대 효과 | 근거 | 위험 · 결정 |
|---:|---|---|---|---|
| 0 | **EKS 읽기 전용 측정부터** — 유효 자격증명으로 `q_eks_intake_40c50259.sql`(이 접수의 단계 시각만) + api pod 의 CPU throttling · 재시작 · 노드 종류/크레딧 확인 | 80.7초를 읽기 · 점검 · 채우기 · 답 반영 · 웹 표시로 나눔 | 지금은 서버 시각 0 | 사용자가 x600(또는 이 PC)에 AWS 키/SSO 를 직접 설정해야 함 |
| 1 | **SSE beat 를 DB 회차와 분리** — `watch` 가 `read`/`content` 를 `asyncio.wait_for` 로 감싸거나 beat 를 별도 타이머 작업으로 내고, 느리면 `slow=true` beat 를 보낸다(채팅 `op_stream.run` 처럼 「생존 신호는 이벤트 루프」) | 서버가 살아 있는 동안의 거짓 「연결이 끊겼어요」 제거 · 재연결/폴링 GET 폭주 감소 | `watch` 구조(코드) · 웹 watchdog 7초 | 작음 — 시험: 가짜 `read` 가 8초 막힐 때 beat 가 3초마다 나오는지 RED/GREEN. 이벤트 루프 자체가 굶으면 효과 제한 |
| 2 | **접수 읽기를 API 프로세스 밖으로** — worker(큐) 또는 이동 계산을 프로세스 풀로 | SSE · GET 응답이 CPU 일에 안 밀림 | `BackgroundTasks(process)` · 작은 단일 노드 · 이동 계산 구간당 ≈2.2초(t3.medium) | 중간 — 실행 위치 변경. 진행 보관소(`progress.py`)가 프로세스 메모리라 SSE 내용 이벤트 경로도 같이 바꿔야 함 |
| 3 | **EKS 용량 확인/조정** — api pod CPU request/limit, 노드 종류 · T 계열이면 CPU 크레딧 잔량/unlimited | 같은 코드로 전 구간 단축 가능 | 배포 주석(작은 노드 1대) | 비용 — 사용자 결정 |
| 4 | 10-27 보고서의 순위 1·2·5(먼저 보여 주고 채우기는 뒤에서 · 읽기 출력 줄이기 · 확정 일정 대안 지연 계산) | x600 추정 「읽는 중」 p50 −50% 등 | 팀 보고서 `2026-10-27_계획서빙_속도_병목측정` | 사용자 계약 변경 · 재학습 — 결정 필요 |
| 5 | 위험 점검 외부 소스별 지연을 남기기(소스 · 소요 · 시간 초과 enum) | AWS 에서 특정 소스가 8초 상한에 걸리는지 판별 | 이번 점검 창 ~10초 | 작음 — 로그/지표 추가만 |

★후보 A·B 는 이미 EKS 판에 들어 있다. 이번 한 건이 그 효과를 보여 주지도, 부정하지도 않는다.

## 4. 하지 않은 것 · 지킨 것

- 고객 DB 쓰기 · 접수 재생 · 인증된 접수 GET(`reap_stalled` · 질문 계획 저장 부작용) · 손님 가입 0. 비밀값 · 원문 · 계정 식별자 출력 0.
- x600 SQL 3회 모두 `BEGIN READ ONLY` · `statement_timeout` · `lock_timeout` · `ROLLBACK`(집계 · 존재 여부 · 열 이름만).
- 공개 GET 30회(미인증 · 0.5초 간격). 원본 작업 트리 변경 0(`tools/safe_git.py fetch team` 만).

## 5. 증거(Hermes profile scratch `cache/scratch/speed-80s-20261028/`)

- `cd.log`(CD run 로그, 시크릿은 GitHub 가 `***` 처리) · `probe.py` / `probe_result.json` · `q_eks_intake_40c50259.sql`(x600 에서 문법만 확인 — 0행) · `pipeline_e88.py`(main 코드 사본).
- x600 기준선 재현: `serving-latency-after-20261027/q_after.sql`(00:3x 재실행, 결과 같음 · after 0건).

## 6. 남은 일

1. 유효한 AWS 자격증명(사용자 직접 설정) → 위 SQL + api pod 지표/로그(시험 시각 ±5분)로 80.7초 분할 · 58초 막힘 원인 확정.
2. 후보 1(SSE beat 분리)을 격리 clone 에서 TDD — 부모 승인 뒤.
3. 후보 2·3·4 는 사용자 결정.
4. x600 A·B 효과는 반영 뒤 채팅 접수가 쌓이면 같은 SQL 로.
