너는 「[모델배포] 시스템 구성도」 여행판 본문(`시스템구성도_코덱스_3차.md`, 아래 전문)을 쓴 **작성자**다. 합의된 본문에서 **코드와 다른 곳이 새로 드러났다.** 반박만 고친다.

## 반박

| # | 자리 | 무엇 | 근거 | 고칠 방향 |
|---|---|---|---|---|
| **U1** | 146행 「운영 접점」 행 | 운영 UI 경로를 접두 없이 `/admin`, `/cases` … 로 적었다. **실제로는 모두 `/ui` 접두가 붙는다** | `final_project_cs/app/presentation/ui/routes.py:23` `router = APIRouter(prefix="/ui", ...)`, 경로 `:187` `/admin` · `:260` `/cases` · `:303` `/cases/{case_id}` · `:338` `/cases/{case_id}/trace` · `:361` `/approvals` · `:409` POST `/approvals/{case_id}/{action_id}` · `:430` `/ops/outbox`. 정정 사실표 29행도 고쳤다. **Claude 의 사실표가 틀렸고 네 본문이 그것을 옮긴 것이다** | 운영 UI 경로를 `/ui/admin`, `/ui/cases`, `/ui/cases/{id}`, `/ui/cases/{id}/trace`, `/ui/approvals`, `/ui/ops/outbox` 로 고친다. REST 경로(`/v1/...`·`/health`·`/admin/reload`·`/introspection`)는 접두가 없으니 그대로 둔다 |
| **U2** | 본문 전체 | 같은 운영 UI 경로가 146행 말고도 나오면 같이 고친다 | 위와 같다 | 없으면 U2 항목을 넣지 않아도 된다 |

- 반박에 없는 곳은 고치지 않는다. 새 글자에 한자·가나·「。」「、」 를 넣지 않는다.

## 답 형식

**파일을 만들지 마라.** 최종 메시지에 ```json 코드블록 **하나**만 담는다.

```json
[
  {"id": "U1", "old": "<본문에 정확히 한 번 나오는 글자>", "new": "<바꿀 글자>"}
]
```

- `old` 가 정확히 한 번 나오지 않으면 Claude 는 **아무것도 적용하지 않는다.** U1 은 반드시 있어야 한다.

## 본문 전문
