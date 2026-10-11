# DoD-08 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
python -m pytest tests/contract/test_team_contract.py tests/contract/test_core_isolation.py -q
```

## 실제 출력
```
... [100%]
3 passed, 1 warning in 1.15s
EXIT=0
```

## 관측 사실
- 실행 파일은 `tests/contract/test_team_contract.py`, `tests/contract/test_core_isolation.py`이다.
- 출력의 테스트 수는 3개이다.
- 테스트 소스에 `BillingSubscriptionTeam`, `TechnicalEntitlementTeam`, `TeamModule`, `TeamManifest`가 나타난다.

## 확인하지 못한 것
- 외부 프로세스에서 manifest 호환성을 확인하는 명령은 실행하지 않았다.
