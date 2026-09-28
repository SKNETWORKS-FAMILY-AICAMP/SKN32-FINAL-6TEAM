# DoD-14 — API key scope 가 read/write/MCP 를 구분한다

- v5 §20 항목 14 / 검증 방법: unauthorized matrix
- 실행: 2026-08-12 23:20 · 실측 원문 `wiki/records/evidence/_raw/DoD-14.md`
- 판정: 통과

## 재현 명령

```powershell
python -m pytest tests/integration/api/test_api_runtime.py -q
python -m pytest tests/security -q
```

## 실제 출력

```
14 passed, 1 warning in 5.08s
2 passed, 1 warning in 0.74s
```

## 판정 근거

- `test_unauthorized_matrix_for_each_scope_and_rest_endpoint` 가 scope **6종**
  (`case:read`, `case:write`, `subscription:read`, `technical:read`, `action:approve`, `mcp:read`)
  에 대해 parametrize 되어 REST endpoint 를 전수 호출하고 기대 status 를 단언한다.
- `test_mcp_read_scope_tools_execute_only_with_mcp_principal` 이 MCP tool 3종을
  각각 parametrize 하여 `mcp:read` principal 로만 실행됨을 확인한다.
- scope 목록은 `config/guardrails.yaml` 의 `security.scopes` 에서 읽는다
  (`test_six_scopes_are_guardrail_owned` 가 하드코딩이 아님을 단언).
- ★`test_case_from_other_customer_is_not_found` — 남의 Case 는 **404** 다.
  403 이면 존재 사실을 알리는 것이라 실패로 판정한다(`wiki/records/handoff/03` §2).

## ★이 항목은 한 번 전면 실패했었다

1차 산출물은 `security.py` 가 `os.getenv` 로 설정을 읽어 **인증이 필요한 모든 요청이 500** 이었다.
그때 테스트는 정적 단언 3건뿐이라 초록이었다.
→ `wiki/records/reports/debugs/2026-08-12_1830_S-API가_실행되지_않는다.md`

★**route 가 등록됐다는 사실과 scope 가 강제된다는 사실은 다르다.**
지금 통과는 실제 HTTP 호출 14건에 근거한다.

## 한계

- 표 형태의 scope × endpoint 전수 매트릭스 **출력물**은 생성하지 않았다
  (테스트 parametrize 안에만 있다). 발표용으로 뽑으려면 별도 작업이 필요하다.
- API key **회전·만료** 정책은 구현·검증 범위 밖이다(v5 MVP 경계).
- OAuth2/OIDC 는 v5 §3 Phase 2 로 **의도적으로 구현하지 않았다.**
