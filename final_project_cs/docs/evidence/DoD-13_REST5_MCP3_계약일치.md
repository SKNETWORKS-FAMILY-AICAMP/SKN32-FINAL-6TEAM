# DoD-13 — REST 5개 endpoint 와 MCP read-only 3개 tool 이 문서·contract 와 일치

- v5 §20 항목 13 / 검증 방법: OpenAPI/MCP test
- 실행: 2026-08-12 23:20 · 실측 원문 `docs/evidence/_raw/DoD-13.md`
- 판정: 통과

## ★2026-09-06 갱신 — 판정은 유효하고, 낡은 이름·수치·경로만 현행으로 고쳤다


| 낡았던 것 | 지금 (실측 2026-09-06) |
|---|---|
| "경로 4개 위 operation 5개, `/v1/` 아래 6번째가 생기면 위반" | 규칙이 v7 에서 바뀌었다 — **5는 상한이 아니다** |
| — | `CONTRACT_V1_PATHS` 는 **경로 5개**(outbox resolve 포함) |
| 재현 출력 | **17 passed** |

```
/v1/cases
/v1/cases/{case_id}
/v1/cases/{case_id}/messages
/v1/cases/{case_id}/actions/{action_id}/approve
/v1/outbox/{message_id}/resolve
```

★**판정이 재는 것은 개수가 아니라 「선언한 집합과 실제 표면이 같은가」다.**
`test_openapi_surface.py` 가 양방향으로 본다 — 선언했는데 없으면 실패
(`missing`), 선언 안 했는데 있으면 실패(`extra`). 그래서 경로가 늘어도
**계약에 적기만 하면** 통과하고, 몰래 늘면 잡힌다. 개수를 상한으로 읽던
옛 서술이 틀렸던 것이다.


## 재현 명령

```powershell
python -m pytest tests/integration/api/test_openapi_surface.py tests/security -q
python  # create_app().openapi()["paths"] 와 MCP tool 이름 출력
```

## 실제 출력

```
{"paths": ["/v1/cases", "/v1/cases/{case_id}",
           "/v1/cases/{case_id}/actions/{action_id}/approve",
           "/v1/cases/{case_id}/messages"],
 "mcp_tools": ["get_my_cases", "get_case_detail", "open_support_case"]}
```

## 판정 근거

- `/v1/` 경로 **4개** 위에 method **5개** — `POST /v1/cases` 와 `GET /v1/cases` 가 같은 경로를 공유한다.
  `tests/integration/api/test_openapi_surface.py::test_five_rest_endpoints_by_method` 가
  operation 수를 세어 **정확히 5** 임을 단언한다.
- 경로 집합이 `docs/handoff/03_REST_MCP_인터페이스.md` §1 표와 일치한다
  (테스트가 계약 표를 상수로 들고 대조한다).
- MCP tool 이 **정확히 3개**이고 이름이 v5 §13-2 와 같다.
  `tests/security/test_scope_contract.py` 가 세 tool 의 `required_scope` 가
  전부 `mcp:read` 임을 단언한다.
- `test_mcp_open_support_case_changes_only_case_state` 가
  `open_support_case` 실행 전후로 `action_requests`·`payments`·`subscriptions` 가
  **변하지 않음**을 DB 로 확인한다 — MCP 가 쓰기를 하지 않는다는 동작 근거다.

## 계약 개정 이력

최초 계약은 "path 집합 == 5개 + `/health`" 였고, 운영 UI(`/ui/*`)를 등록하자 깨졌다.
`RULE.md` §3.5(contract-first)대로 **계약을 먼저 고쳐** 세는 대상을 `/v1/*` 로 명확히 했다
(`docs/handoff/03` §1-0). `/v1/` 아래 6번째 경로가 생기면 여전히 위반이다.

## 한계

- 문서 원문과 OpenAPI 출력의 **자동 텍스트 비교**는 하지 않았다.
  테스트가 들고 있는 상수 표와 계약 문서 표가 어긋나면 잡히지 않는다 — 사람이 대조해야 한다.
- MCP 는 in-process 로 검증했다. 실제 MCP 클라이언트(개인 AI) 접속 시연은 하지 않았다.
