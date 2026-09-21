# DoD-05 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
python -m pytest tests/contract/test_contracts.py -q
@' ... ContextBroker().build(...) ... '@ | python
```

## 실제 출력
```
21 passed, 1 warning in 0.06s
EXIT=0
```
```
EXIT=1
Traceback ...
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='openaipublic.blob.core.windows.net', port=443): Max retries exceeded with url: /encodings/cl100k_base.tiktoken (Caused by NewConnectionError(... [WinError 10013] ...))
```

## 관측 사실
- 계약 테스트 출력의 테스트 수는 `21 passed`이다.
- 계약 테스트에는 `estimated_input_tokens=12001` 입력과 `estimated_input_tokens=12000` 입력 사례가 있다.
- ContextBroker 실측 명령은 `tiktoken` 인코딩 파일 URL 연결 오류로 종료 코드 1을 출력했다.

## 확인하지 못한 것
- 큰 입력의 `estimated_input_tokens`와 `omissions` 출력은 확인하지 못했다.
