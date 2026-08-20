# 구현 지시 — Response Generation & Review Team 이식 (DoD-29)

## 0. 작업 대상

★**`C:\Users\playdata2\Documents\final_workspace\final_project_cs` 안에서만 작업한다.**
`final_project_sample`은 **읽기만** 한다 — 절대 쓰지 않는다.

## 1. ★먼저 읽을 파일 (이것만)

원본(참고용, 읽기만):
```
C:\Users\playdata2\Documents\final_workspace\final_project_sample\app\modules\customer_ops\response_review.py
C:\Users\playdata2\Documents\final_workspace\final_project_sample\app\modules\customer_ops\response_review_policy.py
C:\Users\playdata2\Documents\final_workspace\final_project_sample\tests\unit\teams\test_response_review_team.py
```

이식 대상(이 저장소):
```
app/modules/customer_ops/verification_policy.py   ← 이미 있는 도메인 대조 선언, 그대로 재사용한다
app/modules/customer_ops/feedback.py               ← SENTIMENTS 상수 확인용
app/core/verification.py                           ← 엔진(수정 금지, sample과 동일해야 함)
app/core/contracts.py
CLAUDE.md                                           ← 지금 상태표, §5
```

## 2. 왜 이걸 하나

v8 §8-B에 신설된 DoD-29(Response Generation & Review 검증)가 이 저장소에서
아직 구현되지 않았다. `final_project_sample`엔 이미 있고(2026-08-18 완료,
`CLAUDE.md` 참고), **basement 엔진(`app/core/verification.py`)은 한 줄도 안
바뀐 채** 도메인 어휘 파일만 다르다 — 정확히 `verification_policy.py`가 이미
증명한 패턴이다("basement는 규칙 엔진, 이 파일이 어휘다").

★**`app/core/verification.py`를 고치지 않는다.** sample과 동일해야 한다.
고치고 싶어지면 그건 이 작업의 범위가 아니다 — 멈추고 보고하라.

## 3. 도메인 매핑 — 이미 `verification_policy.py`에 정답이 있다

| sample(구독·결제) | 이 저장소(커머스) |
|---|---|
| `payment_id` → `payments` | `order_id` → `orders`(이미 선언됨) |
| `amount`/`refund_amount`(payment_id 대조, amount 상한) | `refund_amount`(`order_id` 대조, `total_cents` 상한) — 이미 선언됨 |
| (없음) | `return_quantity`(`order_id` 대조, `item_count` 상한) — 이미 선언됨, sample에는 없던 이 저장소만의 필드 |

`CUSTOMER_OPS_POLICY`(`app/modules/customer_ops/verification_policy.py`)를
**새로 만들지 말고 그대로 가져다 쓴다** — sample의 `RESPONSE_VERIFICATION_POLICY`를
흉내내 새 policy 객체를 또 만들지 마라. 이미 있는 `CUSTOMER_OPS_POLICY`가
`refund_amount`·`order_id`·`return_quantity`를 전부 커버한다.

## 4. 만들 것

### 4-1. `app/modules/customer_ops/response_review_policy.py`

sample의 `response_review_policy.py`를 참고해 이 저장소용으로 새로 쓴다:
- `FORBIDDEN_WORDS`·`PII_PATTERNS`·`TONE_PROFILES`·`DEFAULT_TONE_PROFILE`·`decide_tone()`
  — 도메인 무관이므로 거의 그대로(단, import는 `app.core.verification`이지
  `acop_basement.core.verification`이 아니다 — **이 저장소는 리네임 안 됐다**)
- `decide_tone(sentiment)`은 sample과 동일 로직(negative → empathetic,
  그 외/None → professional). `app/modules/customer_ops/feedback.py`의
  `SENTIMENTS = frozenset({"positive", "neutral", "negative"})`와 값이 일치하는지
  먼저 확인하고 써라(확인했다 — 일치한다, 그래도 스스로 다시 확인해라)
- `RESPONSE_VERIFICATION_POLICY`라는 이름으로 새 객체를 만들지 마라 —
  §3에서 말한 대로 `app.modules.customer_ops.verification_policy.CUSTOMER_OPS_POLICY`를
  **import해서 그대로 쓴다**

### 4-2. `app/modules/customer_ops/response_review.py`

sample 파일을 거의 그대로 옮기되:
- import를 `app.core.contracts`·`app.core.verification`으로 바꾼다(`acop_basement.*` 아님)
- `RESPONSE_VERIFICATION_POLICY` 대신 `CUSTOMER_OPS_POLICY`를 쓴다(§3·4-1)
- `manifest.team_id = "response_generation_review"`, `capabilities = ["response.generate_review"]`,
  `accepted_case_types = []`(sample과 동일 — **Controller 자동배선 범위 밖에 그대로 둔다.
  config/project.yaml에 등록하지 마라** — sample도 미등록 상태이고, 이건 사용자
  판단이 남은 부분이다. 등록하면 이 작업 범위를 넘는 것이다)
- 로직(재시도 4회, PII 즉시 escalate, deterministic review 우선, tone LLM은
  deterministic 통과 후에만)은 sample과 동일하게 유지한다

### 4-3. `tests/unit/teams/test_response_review_team.py`

sample의 10개 테스트를 이 저장소 도메인으로 옮긴다:
- `refund_amount`/`order_id` 관련 fact-mismatch 테스트는 `orders` 테이블 fixture로
  (sample은 `payments`였다)
- ★**새 테스트 최소 1개 추가**: `return_quantity`가 `order_id`의 `item_count`를
  초과하면 fact_mismatch로 잡히는지 — 이건 sample에 없던 이 저장소만의 필드라
  sample 테스트를 그대로 옮기는 것만으로는 커버 안 된다
- 나머지 9개(manifest·정상 흐름·톤 결정·forbidden word·PII·tone-only 실패·
  escalation 매핑 등)는 구조 그대로, 도메인 값만 바꿔서 이식

## 5. ★지킬 것

| 규칙 | 이유 |
|---|---|
| `app/core/**` 수정 금지 | basement는 엔진, 여기는 어휘만 |
| `final_project_sample` 쓰기 금지 | 읽기만 — 다른 저장소다 |
| `config/project.yaml`에 새 Team 등록 금지 | sample도 미등록, 사용자 판단 영역 |
| 새 `RESPONSE_VERIFICATION_POLICY` 객체 금지 | 이미 있는 `CUSTOMER_OPS_POLICY` 재사용 |
| import는 `app.core.*`(이 저장소는 acop_basement 리네임 안 됨) | 실측 확인함 |

## 6. 완료 조건 — ★출력으로 증명하라

```powershell
cd C:\Users\playdata2\Documents\final_workspace\final_project_cs
python -m pytest tests -q
```
★기대: 지금 **302 passed, 3 deselected**에서 **최소 11개 늘어난다**(10개 이식 +
`return_quantity` 신규 1개 이상). 그 출력을 리포트에 그대로 붙여라.

## 7. 리포트

`docs/reports/2026-08-19_S-RESPONSE-REVIEW-PORT_리포트.md`
— 만든 파일, §6 출력 원문, sample과 다르게 처리한 부분(있다면).

## 8. 하지 말 것
- ❌ `app/core/verification.py` 등 basement 엔진 수정
- ❌ `final_project_sample` 파일 쓰기
- ❌ `config/project.yaml`에 Team 등록(자동 배선)
- ❌ 새 도메인 policy 객체 중복 생성
- ❌ 테스트 수가 그대로인 채 "완료"
