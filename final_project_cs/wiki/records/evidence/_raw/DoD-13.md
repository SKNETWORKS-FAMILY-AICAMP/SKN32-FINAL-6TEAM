# DoD-13 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
python  # create_app().openapi() paths와 MCP tool 이름 출력
```

## 실제 출력
```
{"paths": ["/v1/cases", "/v1/cases/{case_id}", "/v1/cases/{case_id}/actions/{action_id}/approve", "/v1/cases/{case_id}/messages"], "mcp_tools": ["get_my_cases", "get_case_detail", "open_support_case"]}
EXIT=0
```

## 관측 사실
- OpenAPI `/v1/` 경로 문자열은 4개이다.
- `/v1/cases`에는 POST와 GET 경로가 코드에 있다.
- MCP tool 이름 출력은 `get_my_cases`, `get_case_detail`, `open_support_case`이다.

## 확인하지 못한 것
- 문서 원문과 OpenAPI/MCP 출력의 자동 비교 결과는 확인하지 못했다.
