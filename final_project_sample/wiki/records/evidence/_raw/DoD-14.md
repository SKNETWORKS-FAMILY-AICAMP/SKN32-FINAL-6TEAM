# DoD-14 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
python -m pytest tests/integration/api/test_api_runtime.py -q
python -m pytest tests/security -q
```

## 실제 출력
```
.............. [100%]
14 passed, 1 warning in 5.08s
EXIT=0
.. [100%]
2 passed, 1 warning in 0.74s
EXIT=0
```

## 관측 사실
- API runtime 테스트 출력의 테스트 수는 14개이다.
- security 테스트 출력의 테스트 수는 2개이다.
- API runtime 테스트 소스의 scope 목록은 6개이며 `case:read`, `case:write`, `subscription:read`, `technical:read`, `action:approve`, `mcp:read`이다.

## 확인하지 못한 것
- 별도 표 형태의 scope × endpoint 출력은 생성하지 않았다.
