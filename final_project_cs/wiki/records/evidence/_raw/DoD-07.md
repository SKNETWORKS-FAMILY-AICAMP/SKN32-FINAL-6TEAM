# DoD-07 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
python -m pytest tests/security -q
rg -n "tenant_id|masked|WHERE tenant_id" app tests
```

## 실제 출력
```
.. [100%]
2 passed, 1 warning in 0.74s
EXIT=0
```
```
app\tools\read_tools.py:54:            "WHERE tenant_id=%s AND customer_id=%s ..."
app\presentation\ui\routes.py:27: ... masked(...)
app\presentation\security.py:50:def masked(value: object) -> str:
```

## 관측 사실
- `tests/security` 출력의 테스트 수는 2개이다.
- security scope 집합 문자열에는 `case:read`, `case:write`, `subscription:read`, `technical:read`, `action:approve`, `mcp:read`가 있다.
- 조회 SQL 출력에 `WHERE tenant_id=%s AND customer_id=%s`가 포함되어 있다.
- `app/presentation/security.py`에 `masked` 함수가 있다.

## 확인하지 못한 것
- 모든 보안 테스트의 tenant/customer unauthorized matrix 전체 출력은 확인하지 못했다.
