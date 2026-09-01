# S-CASE-IDEMPOTENCY-FIX — Case 생성 멱등성 구멍 (1)·(2) 수정

원본 결함: [`2026-09-01_Case생성_멱등성_세_구멍.md`](debugs/2026-09-01_Case생성_멱등성_세_구멍.md)

## 재현부터 — 보고된 "500"이 아니라 더 조용한 실패였다

원본 리포트의 실측(§2)을 먼저 `tests/integration/api/test_api_runtime.py`의
`api_fixture`를 그대로 쓰는 임시 스크립트로 재현했다. 결과는 리포트와
일치했다 — **500이 아니라 두 요청 모두 201로 성공하면서 서로 다른
case_id를 반환**했다(`customer_cases` 2행, `action_requests` 1행).
`create_action_request`의 `ON CONFLICT (tenant_id, idempotency_key) DO
UPDATE`가 충돌을 예외 없이 삼켜서, 나중 요청의 Case는 감사 기록 없이
고아로 남는다. 500보다 나쁘다 — 클라이언트도 서버도 실패를 모른다.

## 수정한 것

### 구멍 (1) — 동시 요청 race

원본 리포트가 제시한 세 옵션 중 **C(advisory lock)**를 택했다 — 이
저장소가 이미 같은 패턴을 두 곳에 쓰고 있어서다(`register_prompt_files()`,
`case_service.start_run()`). `create()`·`approve()`·`_mcp_open()` 세
군데 전부 SELECT 직전에 `pg_advisory_xact_lock(hashtext(tenant:idem))`을
건다 — 트랜잭션이 끝나면 자동 해제되고, 두 번째 요청은 첫 번째가
커밋할 때까지 블록됐다가 "이미 있다"를 정확히 본다.

### 구멍 (2) — 죽은 필드

원본 리포트의 **옵션 B**(낫다고 판단한 쪽)를 그대로 택했다:
- `CreateCase.idempotency_key` — 이제 존중한다. 클라이언트가 보내면
  그 값을, 안 보내면 기존처럼 `request_id`로 서버가 계산한다.
- `CreateCase.tenant_id` — 삭제했다. `extra="forbid"`라 보내던 클라이언트는
  즉시 422로 안다. 인증(`principal.tenant_id`)이 테넌트의 유일한
  출처라는 원칙과 상충하는 필드라 "존중하게 고치기"가 아니라 "지우기"다.
- 리포트가 지적한 후속 요구("같은 키에 다른 몸통이 오면 409")도 함께
  넣었다 — `action_requests.arguments_json`에 `body_sha256`(customer_id·
  message·channel 해시)을 같이 저장하고, 재사용된 키의 저장된 해시가
  다르면 `409 idempotency_key_reused`를 던진다.

### 구멍 (3) — 손대지 않음

"같은 뜻, 다른 문장"(반품 문의를 세 번 다르게 표현)을 하나의 Case로
묶을지는 CS 도메인 정책 결정이다. 원본 리포트도 판단을 유보했고, 이
세션에서도 코드를 건드리지 않았다 — 열린 Case에 이어붙이는 로직 자체가
없다는 사실만 재확인했다.

## 검증

1. **재현 스크립트로 수정 전/후 대조** — 수정 전: `[201, 201]`, 서로
   다른 case_id, `customer_cases=2`. 수정 후: `[201, 201]`, **같은**
   case_id, `customer_cases=1`, `action_requests=1`.
2. 클라이언트 지정 `idempotency_key` + 같은 몸통 → 같은 case_id로 수렴 확인.
3. 같은 `idempotency_key` + 다른 몸통 → `409 idempotency_key_reused` 확인.
4. 회귀 테스트 4건 신규(`tests/integration/api/test_api_runtime.py`):
   - `test_concurrent_identical_create_requests_produce_one_case`
   - `test_concurrent_identical_mcp_open_requests_produce_one_case`
   - `test_client_supplied_idempotency_key_is_respected`
   - `test_reusing_idempotency_key_with_a_different_body_is_409`
   - (approve 경로는 기존 승인 재검증 테스트로 간접 커버, 별도 동시성
     테스트는 이번엔 추가하지 않음 — approve는 `expected_version` 낙관적
     잠금으로 상태전이 자체가 이미 두 번째 요청을 걸러내는 구조라 위험도가
     create/mcp_open보다 낮다고 판단)
5. `python -m pytest -q -m "not live"` → 490 passed(기존 486 + 신규 4,
   xfail 1건은 무관한 별개 결함 `2026-09-01_분류_빈라벨_통과.md`).

## 학습 자료 정정

`program/onboarding/trace/steps.py:63` — "고객이 취소 버튼을 두 번
눌러도 Case가 두 개 생기지 않는다"는 조건부 문장이었다(순차 재시도에서만
참, 동시 요청은 검증 안 됨)을 "같은 idempotency_key로 순차·동시 모두
한 번만 처리되며, REST는 클라이언트가 같은 키를 보낼 때만·MCP는
서버가 항상 계산하므로 무조건 그렇다"로 정정 — **이번 수정이 실제로
이 문장을 참으로 만든 뒤에** 고쳤다(수정 전에 문구만 먼저 바꾸지 않았다).

## 산출물

- `app/presentation/api/cases.py` — advisory lock 3곳, `CreateCase`
  필드 정리, body-fingerprint 409 체크
- `tests/integration/api/test_api_runtime.py` — 신규 회귀 테스트 4건
- `program/onboarding/trace/steps.py` — 학습 자료 문구 정정
- `docs/reports/debugs/2026-09-01_Case생성_멱등성_세_구멍.md` — 상태 갱신
