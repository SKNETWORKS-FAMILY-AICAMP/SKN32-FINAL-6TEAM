# S-BASEMENT-02-VERIFICATION-CRASH — 할루시네이션 방어 코드의 NaN/Infinity 크래시 수정

## 0. 배경

`final_project_sample/acop_basement/core/verification.py` (참고용, **절대
수정 금지**) 와 `app/core/verification.py` 를 대조해 발견됨. sample 의
`_to_decimal()` 은 `Decimal("NaN")`/`Decimal("Infinity")` 를
`.is_finite()` 로 걸러내는데, cs 는 이 검사가 없다. 그 결과 비정상적인
금액 값이 파싱 단계는 통과했다가 이후 비교 연산(`>`, `int()` 등)에서
`InvalidOperation`/`OverflowError` 로 **500 에러**를 낸다.

이 파일은 **할루시네이션 방어의 핵심**이다 — "거부해야 할 제안"이
"서버 에러"가 되면 안 된다. `CLAUDE.md` §0.1 원칙 그대로: 근거를 못
대면(또는 값이 이상하면) 확정하지 않고 안전하게 거부해야지, 죽으면 안
된다.

## 1. 할 일

1. `app/core/verification.py` 의 `_to_decimal()`(또는 동등 함수 —
   정확한 함수명을 코드에서 확인해라)에 `Decimal` 값이 유한한지
   확인하는 검사를 추가해라. 유한하지 않으면(NaN, ±Infinity) **크래시
   대신 검증 실패로 안전하게 처리**해라(이 함수가 반환하는 실패 형태를
   그대로 따라라 — 새 예외 타입을 만들지 마라).
2. sample 의 정확한 구현 방식을 참고하되, cs 의 함수 시그니처·호출부와
   맞게 다시 작성해라(복사-붙여넣기 하지 마라).

## 2. 검증

- 재현 테스트를 먼저 추가해서 **수정 전에는 실패/크래시**하는 걸
  확인하고, 수정 후 통과하는 걸 확인해라. `Decimal("NaN")` 과
  `Decimal("Infinity")`(및 `-Infinity`) 둘 다 테스트해라.
- 기존 정상 금액 비교 테스트가 여전히 통과하는지 확인해라(회귀 없음).
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 붙여라
  (현재 359 passed 기준 변화 명시).

## 3. 쓰기 대상

- `app/core/verification.py`
- 관련 테스트 파일(정확한 위치는 `tests/` 안에서 verification 관련
  기존 테스트 파일을 찾아 그 옆에 추가해라)
- `docs/reports/2026-08-24_S-BASEMENT-02-VERIFICATION-CRASH_리포트.md` (신규)

## 4. 하지 말 것

- `final_project_sample/` 수정 금지 — 읽기만
- `verify_proposal`/`Facts` 의 다른 검증 로직 변경 금지 — 이 버그만
  고쳐라
