# VISION-05. 메시징과 내구 실행 확장

| 항목 | 내용 |
|---|---|
| 상태 | 보류 |
| MVP 포함 | 아니오 |
| 최종 갱신 | 2026-08-13 |

## 1. 무엇인가

Redis Streams/RabbitMQ 어댑터를 실증하고, 필요하면 Kafka와 Temporal 식 외부 durable execution으로 확장한다. 현재는 `MessageBusPort`+outbox 테이블+background worker를 사용한다.

## 2. 지금 하지 않는 이유

- 현재 실행 경로는 한 프로세스 경계의 outbox와 worker로 Case 실행·재시도를 관측할 수 있다.
- 외부 broker와 durable execution을 추가하면 전달 순서·중복·consumer group·운영 복구를 별도로 검증해야 한다.
- 동시성·장기 실행 수치가 확인되지 않은 상태에서 broker를 바꾸면 장애 원인과 성능 기준선이 섞인다.

## 3. 도입 트리거 (이 조건이 만족되면 재검토한다)

- active Case 동시성이 20건을 초과하는 상태가 7일 지속되면 메시지 계층을 검토한다.
- worker를 2개 이상으로 수평 확장해야 하는 시점이 오면 Redis Streams/RabbitMQ 실증을 시작한다.
- 최근 100건에서 재시도·순서 보장 요구가 5건 이상이면 broker 요구사항을 확정한다.
- 프로세스 경계를 넘는 10분 초과 장기 실행이 주 10건 이상이면 durable execution을 검토한다.

## 4. 도입 시 예상 비용

전제: 6인 팀이 AI 코딩 도구를 상시 사용한다. 아래는 인·일이 아니라 실소요 일수(wall-clock)다.
단축률은 이 저장소 실측(2026-08-12, 2시간 21분에 18,390줄·테스트 107건)에 근거한 추정이며 정밀한 값이 아니다.

### Redis Streams/RabbitMQ 어댑터만 도입

| 구분 | 내용 | 실소요 | AI 단축 정도 |
|---|---|---:|---|
| 생성 | `MessageBusPort` 어댑터, outbox·dedupe·retry·consumer 설정과 테스트 생성. 병목은 없다. | 0.5~1일 | 큼 |
| 검증·통합 | 순서·idempotency·재전달·dead-letter, worker claim과 장애 주입을 검증. 병목은 중복 side effect와 복구 결과 판정이다. | 1.5~2일 | 작음 — 사람이 판단한다 |
| 대기 | 없음. 병목은 없다. | 없음 | 없음 |
| **합계** | | **2~3일** | |

### Temporal 포함

| 구분 | 내용 | 실소요 | AI 단축 정도 |
|---|---|---:|---|
| 생성 | Temporal workflow·activity, 재시도·타임아웃·검색·운영 설정과 테스트 생성. 병목은 런타임 모델에 맞춘 배선이다. | 1.5~2일 | 큼 |
| 검증·통합 | 중단·재기동·중복·버전 변경, broker와 workflow 경계, 장기 실행 복구와 운영 지표를 검증. 병목은 런타임 운영 판단이다. | 4~6일 | 작음 — 사람이 판단한다 |
| 대기 | Temporal 인프라 프로비저닝과 운영 권한을 기다린다. 병목은 인프라 일정이다. | 1.5~2일 | 없음 |
| **합계** | | **7~10일** | |

병목: 어댑터만 도입할 때는 장애·중복 검증, Temporal 포함 시에는 런타임 운영과 복구 검증이 지배적이다.

## 5. 선행 조건 (이게 먼저 있어야 도입 가능)

- outbox dedupe·재전달·dead-letter 계약 테스트
- 메시지 순서의 업무 정의와 idempotency 기준
- worker claim, retry, timeout, trace를 분리한 지표
- 프로세스 중단·broker 장애·재기동 failure injection 절차

## 6. 폐기 조건 (이 조건이면 이 비전을 버린다)

- 6개월 동안 active Case p95 동시성이 10건 이하이고 worker 1개로 SLA를 충족하면 외부 broker 도입을 폐기한다.
- 최근 500건에서 순서 위반 0건, 중복 side effect 0건, 재시도 요구 1% 이하이면 메시징 확장을 폐기한다.
- 6개월 동안 10분 초과 프로세스 경계 실행이 주 2건 이하이면 durable execution을 폐기한다.

## 7. 참고

- `wiki/records/handoff/02_DB_스키마.md`
- `wiki/records/handoff/06_가드레일_수치.md`
- `CLAUDE.md` §0.3 상태·이벤트 원칙

## 개정 이력

- 2026-08-13 최초 작성.
- 2026-08-13 비용 산정 방식을 실소요 일수로 변경(실측 근거). 실측 커밋 구간은 2026-08-12 15:14~17:35다.
