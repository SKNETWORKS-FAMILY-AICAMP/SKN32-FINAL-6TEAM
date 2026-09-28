# DoD-29 Response Generation & Review Team 이식 리포트

## 구현 내용

- `app/modules/customer_ops/response_review_policy.py`를 추가했다.
- `FORBIDDEN_WORDS`, `PII_PATTERNS`, `TONE_PROFILES`, `DEFAULT_TONE_PROFILE`, `decide_tone()`을 이식했다.
- 검증 정책은 새 객체를 만들지 않고 기존 `CUSTOMER_OPS_POLICY`를 그대로 import해 재사용했다.
- `app/modules/customer_ops/response_review.py`를 `app.core.*` 계약·검증 엔진과 커머스 도메인 필드(`order_id`, `refund_amount`, `return_quantity`)에 맞춰 추가했다.
- `tests/unit/teams/test_response_review_team.py`에 sample 구조의 10개 테스트와 `return_quantity` 상한 검증 테스트 1개를 추가했다.
- 기존 `tests/unit/teams/test_response_review.py`의 오래된 `RESPONSE_VERIFICATION_POLICY` import/assert만 `CUSTOMER_OPS_POLICY`로 정렬했다. 새 `RESPONSE_VERIFICATION_POLICY` 객체는 만들지 않았다.

## 검증 출력

요청된 단위 테스트:

```text
python -m pytest tests/unit/teams/test_response_review_team.py -q
...........                                                              [100%]
11 passed, 1 warning in 1.03s
```

요청된 전체 테스트 명령의 출력 요약:

```text
python -m pytest tests -q
300 passed, 3 deselected, 3 failed, 10 errors in 24.23s
```

실패 3건은 RAG 통합 테스트의 OpenAI embedding 네트워크 연결 실패였고, 오류 10건은 기존 e2e 테스트의 pytest 임시 디렉터리 권한 오류였다. 새 response review 테스트 및 관련 기존 테스트는 통과했다.

## 범위 확인

- `app/core/**`는 수정하지 않았다.
- `config/project.yaml`에 팀을 등록하지 않았다.
- `final_project_sample`에는 쓰기 작업을 하지 않았다.
- Controller 자동배선 대상이 되지 않도록 `accepted_case_types=[]`를 유지했다.

## sample과 다른 부분

- 이 저장소의 기존 `CUSTOMER_OPS_POLICY`를 재사용하므로 sample의 `RESPONSE_VERIFICATION_POLICY`는 생성하지 않았다.
- fact claim은 `payment_id` 대신 `order_id`를 사용하고, `refund_amount` 및 `return_quantity`를 `orders.total_cents`·`orders.item_count`와 대조한다.
- 기존 저장소 테스트가 존재하지 않는 sample 정책명을 import하고 있어, 그 테스트의 참조명만 기존 정책명으로 수정했다.
