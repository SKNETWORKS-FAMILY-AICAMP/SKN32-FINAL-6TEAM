# sample 대비 cs 격차 조사 리포트

- 조사일: 2026-08-18
- 범위: `../final_project_sample` 전체(산출물·`.git` 제외), cs의 `app/`·`docs/` 읽기 비교
- 원칙: 이번 세션에서는 아래 리포트만 생성했다. sample과 cs의 코드·설정·스키마는 수정하지 않았다.
- 주의: sample 일부 파일은 터미널 인코딩이 깨져 보였으므로, 판정은 식별 가능한 코드·심볼·SQL·테스트·문서 구조를 교차 확인해 작성했다.

## 1. 요약 표

| 발견 항목 | sample의 무엇 | cs에 있는가 | 공통/특화 | 포팅 우선순위와 근거 |
|---|---|---|---|---|
| issue_code별 Customer Ops 분기 | `app/modules/customer_ops/feedback_team.py`, `response_review.py` | 기존 `order_shipping.py`, `return_exchange.py`만 있음 | VOC 배치는 공통, response review 엔진은 공통, 업무 필드·정책은 billing 특화 | 높음: cs의 여러 issue_code가 전용 판단 없이 LLM으로 떨어짐. 단, commerce 시나리오를 새로 설계해야 함 |
| Response Generation & Review Team | GEN → 결정론적 REV → tone REV → `TeamResult` | 없음 | 엔진은 공통, `payment_id`·`refund_amount` 검증은 billing 특화 | 높음: DoD-29 미구현 항목이며 안전·근거 검증에 직접 영향 |
| `team_modules/` 구조 | 실제 파일/디렉터리는 발견되지 않음. 대신 `TeamModule` Protocol과 Team 구현이 있음 | 없음 | 구조명 자체는 공통 개념이나 현재 sample에는 미사용 골격도 없음 | 낮음: 복사할 디렉터리 구조가 아니라 실제 계약·배선 여부를 재설계해야 함 |
| VOC/Feedback Analytics Team | 일일 집계·alert·`feedback_analytics_reports` 적재 | 없음 | 집계 런타임은 공통, VOC 스키마·alert 기준은 도메인 특화 | 중간: 운영 분석 기능으로 유용하지만 commerce VOC vocabulary/schema 번역 필요 |
| active run 경합 방지 | `004_agent_runs_active_uniqueness.sql` partial unique index | 없음 | 완전 공통 | 높음: cs `start_run()`의 SELECT-후-INSERT는 최초 활성 행이 없을 때 동시 경합에 취약 |
| tenant-scoped outbox dedupe | `005_outbox_dedupe_key_tenant_scoped.sql` | 없음 | 완전 공통 | 높음: cs 스키마·INSERT가 전역 `(topic,dedupe_key)`라 tenant 간 메시지 손실 가능 |
| outbox payload tenant 검증 | sample `outbox.py`의 case tenant 조회 및 불일치 거부 | 없음 | 완전 공통 | 높음: cs는 payload tenant를 case 소유 tenant와 대조하지 않음 |
| Composer JWT write channel | `app/presentation/composer_auth.py` 및 composer API/service/audit | 없음 | 공통 보안·운영 채널 | 중간~높음: cs에 Composer 기능 자체가 대응되는지 계약 확인 후 별도 포팅 필요 |
| S-BUGHUNT 계약·검증 흐름 | `wiki/records/handoff/_prompts/S-BUGHUNT-01..08` | 동일 시리즈 없음 | 대부분 공통, Teams/VOC만 도메인 특화 | 중간: 코드 복사보다 버그헌트 계약과 commerce 대응 테스트를 먼저 이식 |
| sample 전용 평가·분석 보강 | `eval/stats/bootstrap.py`, `mcnemar.py`, `agreement.py` 및 관련 테스트 | 대응 파일 없음 | 통계 하네스는 공통, 데이터셋·라벨은 특화 | 낮음~중간: 운영 안정성보다 DoD-29/동시성 이후 진행 |

## 2. Customer Ops 격차

### 2.1 cs의 현재 상태

`cs/app/modules/customer_ops/order_shipping.py`는 주문·배송·정책을 읽은 뒤 배송 상태가 `delivered`이고 주문이 있으면 `refund.request` 제안을 만든다. 그 밖의 문의는 `_llm_answer()`로 보낸다. `cs/app/modules/customer_ops/return_exchange.py`도 반품 요청(`status == "requested"`)이 있으면 `return.accept` 제안을 만들고, 그 밖에는 LLM 답변으로 떨어진다.

`cs/app/modules/customer_ops/feedback.py`에는 다음 issue code가 선언되어 있지만, 두 Team의 `execute()`에서 issue code별 전용 분기 대상으로 사용되지 않는다.

- `order_payment_failed`, `order_duplicate_charge`, `order_change_or_cancel`, `order_other`
- `shipping_delayed`, `shipping_delivered_not_received`, `shipping_other`
- 반품/교환 관련 quantity·fee/period 계열 코드

따라서 사용자가 지적한 대로 현재 결정론적 업무 시나리오는 Team당 사실상 하나이고, 나머지는 tool 결과를 근거로 한 자유 응답이다. `verification_policy.py`의 상단 대응표(`payment_id`→commerce의 `order_id` 등)는 향후 번역 시 참고할 수 있지만, 이름만 바꾸면 되는 기계적 포팅은 아니다. 결제 금액 검증은 주문 총액·주문 항목·배송/반품 상태 검증으로 바뀌어야 한다.

### 2.2 sample의 Team 수와 성격

sample의 `app/modules/customer_ops/feedback_team.py`는 고객 문의 처리 Team이 아니라 일일 VOC 집계 Team이다. `run_daily_feedback()`를 실행하고, alert가 있으면 `escalated`, 없으면 `completed`를 반환하며 `feedback_analytics_reports`에 근거를 남긴다. 즉 issue_code별 상담 분기를 늘리는 구현은 아니지만, cs에는 없는 실행 가능한 Team 종류다.

`sample/app/modules/customer_ops/response_review.py`의 `ResponseGenerationReviewTeam`은 업무 문의를 조사하는 Team과 별개인 cross-cutting 응답 생성·검토 Team이다. 주요 실행은 다음과 같다.

1. context/evidence와 DB 사실을 정규화한다.
2. `response_review_policy.py:decide_tone()`이 sentiment를 보고 tone을 규칙으로 결정한다. negative면 `empathetic`, 그 밖에는 `professional`이다.
3. GEN LLM으로 응답 초안을 만든다.
4. 금칙어·PII·사실/정책 불일치를 결정론적으로 검토한다. 실패하면 최대 3회 재생성한다(코드상 총 4회 시도).
5. PII면 재시도 없이 즉시 `escalated`; 반복 실패면 `review_retries_exhausted`; LLM의 명시적 escalation도 계약 결과로 변환한다.
6. 결정론 검토를 통과한 뒤 tone LLM 검토를 수행한다. tone만 실패하면 재시도하지 않고 `warnings=["tone_review_failed"]`로 완료한다.

따라서 `response_review.py`는 단순 prompt helper가 아니라 `TeamManifest`, `TeamTask`, `TeamResult`, `TeamModule` 계약을 구현한 세 번째 종류의 Team/모듈이다. 다만 sample의 `config/project.yaml`에는 `feedback_analytics`가 `app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam`으로 배선되어 있고, `response_generation_review`는 config에 선언되어 있지 않다. `tests/unit/teams/test_response_review_team.py`와 contract 테스트로 검증되지만, 현재 기본 composition의 운영 Team으로 자동 실행되는 상태는 아니다.

### 2.3 `team_modules/` 확인 결과

sample과 cs 양쪽에서 실제 `app/modules/customer_ops/team_modules/` 디렉터리는 발견되지 않았다. sample은 `app/core/contracts.py`의 `TeamModule` Protocol, `TeamManifest`, `TeamResult`를 사용하고, 구현은 개별 `.py` 파일에 있다. `composition.py`는 `config/project.yaml`의 `implementation_ref`를 동적으로 import하여 registry에 넣는다.

그러므로 `team_modules/`를 “sample에서 cs로 그대로 가져올 구조”로 판단하면 안 된다. 실제 실행 경로에 배선된 것은 `FeedbackAnalyticsTeam`이며, Response Review는 테스트 가능한 독립 구현이지만 기본 config에 연결되지 않은 상태다. 포팅 시에는 디렉터리 생성 여부보다 manifest/contract, registry 등록, routing/capability 정책, 테스트를 하나의 계약으로 결정해야 한다.

## 3. DoD-29 — Response Generation & Review

### 3.1 요구사항

`sample/docs/evidence/DoD-29_ResponseGenerationReview.md`는 v8 §27의 DoD-29를 `TeamModule` Protocol·Core 계약 검증과 GEN/REV 시나리오의 unit test로 확인한다. 문서에 기록된 요구는 다음과 같이 요약된다.

- TeamModule Protocol 및 `TeamResult` 계약 준수
- 응답 초안 GEN 후 검토 REV가 완료되는 실행 흐름
- 금칙어/안전 규칙 위반은 최대 3회 재시도 후 escalation
- `refund_amount` 등 생성 응답의 claim이 DB 사실·정책과 불일치하면 재시도하고 검토 이력을 기록
- PII는 재시도 없이 즉시 escalation
- 결정론적 검토가 tone 검토 LLM보다 먼저 실행
- tone만 실패한 경우 응답 전체를 버리지 않고 warning으로 표시
- sentiment에 따른 tone 결정이 GEN과 tone REV 양쪽에 동일하게 전달

v8 §27 원문 전체를 이 리포트에 복제하지 않고, evidence에 명시된 v8 §8-B 흐름을 인용하면 핵심 순서는 “규칙 결정 → GEN 초안 → REV 검증 → 완료”이다. 이는 고객 원문 자체를 선제적으로 거부하는 preflight가 아니라, 생성된 답변을 검토하는 계약이어야 한다. sample의 2026-08-18 검수 문서도 이 경계를 확인하고 초기 preflight 결함을 수정한 것으로 기록한다.

### 3.2 sample 구현 파일

- `sample/app/modules/customer_ops/response_review.py`: Team manifest, evidence/facts 정규화, GEN 호출, 결정론 검토, retry/escalation, tone review, `TeamResult` 변환
- `sample/app/modules/customer_ops/response_review_policy.py`: 금칙어, PII regex, tone profile, sentiment→tone 규칙, 검증 policy
- `sample/app/core/verification.py`: claim과 사실·정책의 불일치 검증 primitive
- `sample/tests/unit/teams/test_response_review_team.py`: 정상 완료, tone 선택, 금칙어 retry, fact mismatch retry, PII 즉시 escalation, 검토 순서, warning을 검증
- `sample/docs/evidence/DoD-29_ResponseGenerationReview.md`: DoD 증거와 실행 결과
- `sample/docs/handoff/_prompts/S-RESPONSE-REVIEW-TEAM.md`: 구현 계약/요구의 handoff 문서

기본 운영 배선은 제한적이다. `sample/config/project.yaml`에는 VOC Team이 등록되어 있지만 Response Review Team은 등록되어 있지 않다. 따라서 포팅 시 “파일 복사 완료 = DoD-29 운영 완료”로 간주할 수 없다.

### 3.3 도메인 번역 경계

도메인 무관으로 재사용 가능한 부분은 GEN/REV 상태 흐름, retry 상한, PII 탐지, 금칙어 검토 인터페이스, evidence/decision/warning 기록, tone 결정과 검토 순서, `TeamResult` 계약이다.

도메인 특화 부분은 `RESPONSE_VERIFICATION_POLICY`의 `payment_id`→`payments`, `policy_ref`→`policies` reference, `refund_amount`→`amount_cents` 수량 규칙, billing 문맥의 금칙어와 prompt 내용이다. commerce에서는 예를 들어 `order_id`→`orders`, `order_item_id`→`order_items`, `return_quantity`→주문 item quantity, `shipping_status`→`shipments` 같은 검증 schema를 새로 정해야 한다. `payment_id`를 단순히 `order_id`로 치환하면 주문 총액과 결제 승인 금액의 의미 차이를 숨길 수 있다.

## 4. 동시성·보안·메시징 격차

### 4.1 active agent run

sample의 `app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql`은 `(tenant_id, case_id)`에 대해 status가 `active/running/resuming`인 행을 하나만 허용하는 partial unique index를 추가한다. 기존 `CaseService.start_run()`의 `SELECT ... FOR UPDATE`는 이미 활성 행이 있을 때는 유효하지만, 활성 행이 0개인 최초 동시 실행에서는 잠글 행이 없어 두 INSERT가 모두 통과할 수 있다는 결함을 DB 제약으로 막는다.

cs의 `app/application/case_service.py:start_run()`은 동일한 SELECT-후-INSERT 패턴이고, cs에는 004 대응 migration이 없다. 따라서 동일 결함 가능성이 확인된다. 포팅은 도메인 번역이 없는 공통 DB migration + 동시 최초 실행 통합 테스트로 진행해야 한다.

### 4.2 tenant-scoped outbox dedupe

sample의 `005_outbox_dedupe_key_tenant_scoped.sql`은 기존 `UNIQUE(topic, dedupe_key)`를 제거하고 `UNIQUE(tenant_id, topic, dedupe_key)`로 바꾼다. 같은 dedupe key를 서로 다른 tenant가 사용할 수 있어야 하는데 전역 unique이면 한 tenant의 메시지가 다른 tenant의 동일 키와 충돌하여 `ON CONFLICT DO NOTHING`으로 유실될 수 있기 때문이다.

cs의 `001_schema.sql`은 여전히 `UNIQUE(topic, dedupe_key)`이고 005가 없다. `cs/app/infrastructure/messaging/outbox.py`의 INSERT도 `ON CONFLICT(topic,dedupe_key)`를 사용한다. 이 격차는 commerce 데이터와 무관한 tenant isolation 결함이다.

### 4.3 outbox payload tenant 혼합

sample의 최신 `outbox.py`는 `case_id`로 `customer_cases.tenant_id`를 조회하고, payload가 주장하는 tenant가 실제 case tenant와 다르면 `ValueError`를 발생시킨다. tenant가 없으면 거부하며, insert conflict도 tenant-scoped key를 사용한다.

cs의 대응 `outbox.py`는 case tenant를 조회해 payload tenant가 없을 때 기본값으로 쓰지만, payload에 tenant가 있을 때 case 소유 tenant와 다른지 검사하지 않는다. 따라서 payload tenant와 case_id의 tenant를 혼합하는 격리 결함이 남아 있다. 공통 수정 후보지만 실제 구현은 별도 계약으로 발주해야 한다.

### 4.4 Composer 인증

sample의 `app/presentation/composer_auth.py`는 issuer Bearer 검증, configured scope 검증, 15~60분 TTL guardrail, HS256 JWT의 `sub/aud/scope/iat/exp/jti` 필수 claim 검증, scope별 dependency를 제공한다. cs에는 해당 파일이 없고 대응 Composer write channel도 확인되지 않았다. 이것은 billing 특화가 아닌 공통 운영 보안 기능이지만, cs에 Composer 기능을 가져올 범위·API·감사 로그 계약을 먼저 정해야 한다. 즉 당장 인증 파일만 복사할 항목은 아니다.

## 5. S-BUGHUNT 계약과 cs 적용성

sample의 `wiki/records/handoff/_prompts/S-BUGHUNT-01..08`은 코드 자체가 아니라 최근 결함을 찾기 위한 조사 계약이다. 제목과 내용의 핵심은 다음과 같다.

| 계약 | sample에서 조사한 축 | cs 적용성 |
|---|---|---|
| 01 CORE-SAFETY | tenant 조건 누락, 예외 삼키기, lock 없는 read-then-write, 계약-구현 불일치 | 높음. order/shipping/return 데이터에도 tenant 경계와 동시성이 동일하게 존재 |
| 02 CONTEXT-RAG-A2A | ContextPack, RAG 근거, A2A, resume의 경계·실행 여부 | 높음. 도메인과 무관한 runtime 계약 |
| 03 TEAMS-VOC | Team 응답/분류기/VOC의 실제 동작과 mock·계약 누락 | 중간~높음. Team 구조는 공통이나 billing vocabulary는 commerce로 번역 |
| 04 MCP-IDEMPOTENCY-RESUME | MCP 중복 실행, idempotency, resume token 재사용·TTL | 높음. cs의 action/order 처리에도 동일 안전성 필요 |
| 05 GRAPHSTORE-REST | GraphStore와 REST 경계, 실제 endpoint/adapter 계약 | 높음. 그래프 질의의 도메인 데이터만 교체 |
| 06 CONTROLLER-TRANSITION | 상태 전이·동시 실행·outbox 원자성·재현성 | 매우 높음. cs에서 004/005와 함께 우선 실행할 후보 |
| 07 COMPOSER-EVAL | Composer validate/apply 동시성, 임시 파일, bootstrap·McNemar·agreement 통계 | 중간. Composer/eval 기능을 cs가 채택할 때 적용 |
| 08 전체점검 | 01~07 후속 재점검, Response Review·Composer·examples 분리·미완성 배선 점검 | 높음. 포팅 후 최종 회귀 감사 계약으로 사용 |

cs에는 이 동일한 S-BUGHUNT prompt 시리즈가 대응 파일로 확인되지 않았다. 포팅할 때 sample의 결함 사례를 그대로 가정하지 말고, 각 계약의 시나리오를 `order_id`, `shipment_id`, `return_id`, commerce tenant fixture로 번역해 재검증해야 한다.

## 6. 그 밖의 sample-only 발견

전체 파일 목록과 참조를 훑은 결과, 이번 작업의 포팅 후보로 의미 있는 sample-only 묶음은 다음과 같다.

- `app/presentation/composer_auth.py`, `app/presentation/api/composer.py`, `app/application/composer_service.py`: 구성기 write channel, JWT/scope/audit/allowlist 검증. 기능 단위로는 공통이지만 cs의 현재 운영 범위와 먼저 대조해야 한다.
- `eval/stats/bootstrap.py`, `eval/stats/mcnemar.py`, `eval/stats/agreement.py` 및 테스트: bootstrap/McNemar/Cohen kappa 기반 평가 보강. 통계 알고리즘은 공통이나 sample 라벨·holdout 데이터는 도메인 특화다.
- `app/modules/customer_ops/feedback_team.py`, `app/application/feedback_job.py`, feedback analytics schema/테스트: 일일 VOC 집계·alert·tenant별 report. commerce에서는 order/shipping/return issue code와 alert threshold를 다시 정의해야 한다.
- `wiki/records/evidence/DoD-29_ResponseGenerationReview.md`와 관련 테스트/계약: cs의 CLAUDE.md가 미평가로 명시한 항목. 단순 문서 복사보다 commerce 검증 policy와 테스트를 새로 작성해야 한다.
- sample의 `examples/` 분리와 관련 audit 문서: 구독·청구 Team을 production customer_ops와 분리한 경계 작업. cs에는 billing/technical 구현을 그대로 가져올 이유가 없고, commerce Team도 examples와 production 경계를 유지해야 한다.

## 7. 포팅 계획 초안

실행은 하지 않으며, 다음 계약 순서를 권장한다.

1. **P0 — 공통 안전성 계약**: 004 partial unique index, 005 tenant-scoped unique, outbox payload tenant 일치 검사를 먼저 별도 계약으로 작성한다. cs의 `start_run()`과 `outbox.py`에 대한 동시성·tenant isolation 통합 테스트를 먼저 추가할 대상이다.
2. **P0 — DoD-29 공통 엔진 계약**: `TeamModule`/`TeamResult` 적합성, GEN→결정론 REV→tone REV 순서, PII 즉시 escalation, 금칙어/fact mismatch retry, warning semantics를 commerce-neutral 테스트로 고정한다.
3. **P0 — commerce Response Review policy**: sample의 `payment_id`, `refund_amount`, `payments` 검증을 복사하지 말고, `order_id`, `order_items`, `shipments`, `returns`, `order_total`에 대한 claim/reference/quantity 규칙을 `cs/app/modules/customer_ops/verification_policy.py`와 합의한다.
4. **P1 — issue_code 전용 판단**: `order_payment_failed`, duplicate charge, change/cancel, delayed/other shipping 등 우선순위와 출력 계약을 정한다. 각 분기는 읽기 근거·escalation·ActionProposal 여부를 명시하고, 현재 두 Team의 `_llm_answer()` fallback과 충돌하지 않게 routing 계약을 먼저 고친다.
5. **P1 — Response Review 배선**: `config/project.yaml`의 Team 선언, `composition.py` registry, capability resolver/controller routing, prompt key와 테스트를 함께 결정한다. sample처럼 구현만 있고 기본 config에 없는 상태를 피한다.
6. **P1/P2 — VOC Team**: commerce VOC 집계의 기간·issue code·alert 기준과 report schema를 정한 후 `feedback_team.py` 패턴을 번역한다. 운영 분석 가치가 확인될 때 진행한다.
7. **P2 — Composer/eval 및 전체 버그헌트**: cs가 Composer write channel과 평가 하네스를 채택할 경우 JWT/scope/audit부터, 이후 통계 도구를 도메인 데이터셋에 맞춰 포팅한다. 마지막으로 S-BUGHUNT-08을 commerce fixture로 재실행한다.

## 8. 조사 제한 및 결론

sample의 `app/modules/customer_ops/team_modules/`는 실제로 존재하지 않아 미사용 골격으로 판정할 파일 자체가 없었다. 또한 이번 작업은 실행·수정이 아닌 정적 비교이므로 sample의 테스트 결과는 문서에 기록된 결과를 인용한 것이며, cs에 대한 신규 테스트 실행 결과가 아니다.

결론적으로 가장 먼저 가져올 “버전 상승분”은 도메인 업무 코드의 복사가 아니라 (1) active run/outbox tenant 안전성, (2) DoD-29의 응답 검토 계약과 결정론적 안전장치, (3) 그 뒤 commerce issue_code별 전용 판단을 추가하는 순서다. Billing-specific identifier와 policy는 반드시 commerce 계약으로 번역한 뒤에만 포팅해야 한다.

## 9. 작업 후 cs git status

아래는 리포트 저장 후 실행한 명령의 결과다.

```text
 M ../.gitignore
 M CLAUDE.md
 M RULE.md
 M app/composition.py
 M app/infrastructure/llm/openai.py
 M app/modules/customer_ops/order_shipping.py
 M app/modules/customer_ops/return_exchange.py
 M app/presentation/ui/__init__.py
 D app/presentation/ui/composer.py
 M app/presentation/ui/routes.py
 M app/presentation/ui/theme.py
 M app/tools/read_tools.py
 M config/project.yaml
 M wiki/records/release_checklist.md
 ... (상위 작업트리의 기존 변경 다수; sample·ui·research 경로 포함)
?? wiki/records/reports/2026-08-18_S-SAMPLE-DIFF-DISCOVERY_리포트.md
?? eval/stats/agreement.py
?? eval/label_holdout_template.py
?? prompts/order_shipping/
?? prompts/return_exchange/
?? scripts/register_prompts.py
?? tests/integration/llm/
?? tests/unit/tools/
?? ../final_project_sample/app/infrastructure/db/migrations/004_agent_runs_active_uniqueness.sql
?? ../final_project_sample/app/infrastructure/db/migrations/005_outbox_dedupe_key_tenant_scoped.sql
?? ../final_project_sample/app/modules/customer_ops/response_review.py
?? ../final_project_sample/app/modules/customer_ops/response_review_policy.py
?? ../final_project_sample/app/presentation/composer_auth.py
?? ../final_project_sample/docs/evidence/DoD-29_ResponseGenerationReview.md
?? ../final_project_sample/tests/unit/teams/test_response_review_team.py
warning: could not open directory 'final_project_ui/.pytest-tmp2/': Permission denied
```

해석: 위 결과에는 조사 전부터 존재하던 cs·sample·형제 프로젝트 변경이 함께 포함되어 있다. 이 세션에서 의도적으로 생성한 것은 `wiki/records/reports/2026-08-18_S-SAMPLE-DIFF-DISCOVERY_리포트.md` 하나이며, sample 파일은 읽기만 했다. sample에 표시된 변경은 사용자 지시상 `git status/diff`를 sample 저장소에서 별도로 실행하지 않았고, 상위 작업트리 상태에서 우연히 함께 표시된 기존 상태다.
