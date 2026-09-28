# 구현 지시 — 옛 도메인 scope 이름 정리 (`subscription:read`/`technical:read`)

## 0. 배경

`config/guardrails.yaml` 의 `security.scopes` 목록에 `subscription:read`·
`technical:read` 가 남아 있다. 실제로 이 두 scope 를 요구하는
`require_scope(...)` 호출은 코드 어디에도 없다(REST 라우터는
`case:read`/`case:write`/`action:approve`/`mcp:read` 만 실제로 검사한다) —
**기능적으로 깨진 건 아니다.** 다만 이름이 옛 구독·청구 도메인을 가리키고 있어
쇼핑몰 도메인과 안 맞는다. 심각도는 낮지만(이 세션에서 고친 다른 결함과 달리
운영 경로에 영향 없음), 이름을 도메인에 맞게 정리한다.

## 1. 소유 범위

```
config/guardrails.yaml
tests/security/test_scope_contract.py
tests/integration/api/test_api_runtime.py
```

★금지: 그 외 모든 파일. `app/presentation/security.py`·`require_scope` 구현
자체는 건드리지 않는다 — 이 두 scope 이름은 실제로 강제되지 않으므로 로직
변경이 필요 없다.

## 2. 새 값 (그대로 쓴다)

```
subscription:read  →  order:read
technical:read     →  return:read
```

`order_shipping`/`return_exchange` 두 Team 이름과 짝을 맞춘 것이다.

## 3. 무엇을 바꾸는가

- `config/guardrails.yaml` 의 `security.scopes` 목록에서 두 값을 교체
- `tests/security/test_scope_contract.py` 의
  `test_six_scopes_are_guardrail_owned` 단언 집합을 새 값으로 교체
- `tests/integration/api/test_api_runtime.py` 의
  `test_unauthorized_matrix_for_each_scope_and_rest_endpoint` 의
  `@pytest.mark.parametrize("scope", [...])` 목록도 새 값으로 교체.
  이 테스트의 `expected` 딕셔너리는 `scope == "case:write"`/`"case:read"`/
  `"action:approve"`/`"mcp:read"` 여부로만 분기하므로(정확한 scope 이름과 무관하게
  나머지는 전부 403 기대) **로직 변경은 필요 없고 parametrize 목록 문자열만**
  바꾸면 된다.

## 4. 검증

```powershell
python -m pytest tests/security/test_scope_contract.py -q
python -m pytest tests/integration/api/test_api_runtime.py -q
python -m pytest -q
```

전부 실패 0건이어야 한다(회귀 없음, deselected 수는 그대로).

## 5. 완료 조건

- [ ] `subscription:read`·`technical:read` 문자열이 이 3개 파일 어디에도 남지 않는다
- [ ] `pytest -q` 전체 통과, 실패 0건
- [ ] `wiki/records/reports/2026-08-17_S-SCOPE-RENAME_리포트.md` 제출
