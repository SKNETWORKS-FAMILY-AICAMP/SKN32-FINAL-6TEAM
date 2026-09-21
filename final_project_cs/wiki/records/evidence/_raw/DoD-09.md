# DoD-09 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
python  # FastAPI TestClient로 POST /v1/cases 후 customer_cases와 case_events 조회
```

## 실제 출력
```
customer_id= 57f45d44-0123-4120-ba54-0ada460d7c40
status= 201
body= {"case_id":"8c0e0426-d676-43bc-b106-dfea4f5f287d","status":"escalated","version":2,"intent":null,"issue_code":null,"sentiment":null,"links":{"self":"/v1/cases/8c0e0426-d676-43bc-b106-dfea4f5f287d"}}
customer_cases= (None, None, None)
EXIT=0
events= [('created', {'channel': 'test', 'message': 'classification measurement'}), ('classification_failed', {'failure_code': 'classification_failed'})]
EXIT=0
```

## 관측 사실
- POST 경로는 `/v1/cases`이고 응답 상태 코드는 201이다.
- 응답의 `intent`, `issue_code`, `sentiment` 값은 모두 `null`이다.
- `customer_cases` 조회 튜플은 `(None, None, None)`이다.
- case_events에는 `created`, `classification_failed` 두 행이 조회되었다.
- 실패 이벤트 payload의 `failure_code`는 `classification_failed`이다.

## 확인하지 못한 것
- 별도 분류기 구현을 사용한 성공 분류 POST 결과는 확인하지 못했다.
