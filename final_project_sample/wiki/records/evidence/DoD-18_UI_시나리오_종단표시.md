# DoD-18 — Case UI · trace · approval · VOC report 가 발표 시나리오를 끝까지 보여준다

- v5 §20 항목 18 / 검증 방법: e2e smoke
- 최초 판정: 2026-08-12 23:20 **부분 통과** (화면이 비어 있었다) · 실측 원문 `wiki/records/evidence/_raw/DoD-18.md`
- 재측정: 2026-08-14
- 판정: 통과

## 재현 명령

```powershell
Start-Process python -ArgumentList '-m','uvicorn','app.presentation.api.app:app','--port','8765'
curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8765/ui/cases
# /ui/approvals, /ui/voc, /ui/cases/{id} 동일
```

## 실제 출력

```
PATH=/ui/cases      STATUS=200   <title>Case 목록</title>
PATH=/ui/approvals  STATUS=200   <title>Approval</title>
PATH=/ui/voc        STATUS=200   <title>VOC 일일 리포트</title>
PATH=/ui/cases/{id} STATUS=200   <title>Case 상세</title>
```

Claude 독립 확인(포트 8012)에서도 4경로 전부 **200**, VOC 화면이
빈 report 와 `급증 alert 없음` 을 표시했다 — **데이터가 없을 때 가짜 숫자를 만들지 않는다.**

## 통과한 것

- 화면 4종이 실제로 뜬다 (`CLAUDE.md` §4 — 백엔드 테스트 통과만으로 완료라 하지 않는다)
- 승인 화면이 `ActionProposal` 과 rationale evidence 를 함께 표시하도록 구현됐고,
  승인은 DB 직접 쓰기가 아니라 `POST /v1/cases/.../approve` 를 호출한다
- VOC 데이터 부재 시 정직한 빈 상태 표시

## ★미통과 — 왜 "부분"인가

DoD 18 이 요구하는 것은 화면이 뜨는 것이 아니라 **"발표 시나리오를 끝까지 보여주는 것"** 이다.

| 항목 | 상태 |
|---|---|
| 4개 화면 HTTP 200 | 통과 |
| 빈 상태 정직 표시 | 통과 |
| ★**시나리오 1·2 의 Case 가 화면에 실제로 보이는가** | **통과** (2026-08-14 재측정) |
| ★**Trace 가 전이 단계를 화면에 보여주는가** | **통과** |
| ★**Approval 화면에서 실제 proposal 을 승인해 종단 완료** | **통과** — `waiting_approval(4)→resuming(5)` |
| 브라우저에서 CSS·상호작용 시각 확인 | **통과** |

## ★재측정 (2026-08-14)

```powershell
python -m scripts.seed_demo_cases     # 발표 Case 2건을 남긴다 (삭제하지 않는다)
python -m uvicorn app.presentation.api.app:app --port 8041
```

`scripts/seed_demo_cases.py` 를 만들었다. 기존에 화면이 비어 있던 이유는
**Controller 통합테스트가 두 시나리오를 코드로 통과시킨 뒤 teardown 에서 지웠기 때문**이다.
상태는 `transition_case()` 로만 만들고 `customer_cases` 를 직접 UPDATE 하지 않는다.

### 실측 — `/ui/cases`

★case_id 는 시나리오 이름에서 `uuid5` 로 만든다. **몇 번을 돌려도 같은 값**이므로
발표 자료의 URL 과 이 문서의 실측값이 매 실행마다 죽지 않는다.

```
49986645-f233-523d-9f96-58e33853892d  waiting_approval  billing_refund
                                      charged_after_cancellation  negative
                                      billing_subscription  v4
2c6f960e-043b-51e5-b1cf-fb6fee4543f8  resolved  technical_entitlement
                                      entitlement_mismatch  neutral
                                      technical_entitlement  v4
```

재실행 안전: 두 번 돌려도 `cases_in_tenant = 6` 으로 같고 case_id 도 같다.

### 실측 — `/ui/approvals` 에서 승인 → 종단

```
POST /ui/approvals/<case>/<action>  ->  303
GET  /ui/cases/<case>               ->  <span class='badge'>resuming</span> version 5
```

`waiting_approval(4) → resuming(5)`. **화면에서 누른 승인이 실제 상태를 바꿨다.**
승인은 DB 직접 쓰기가 아니라 `POST /v1/cases/.../actions/.../approve` 를 거친다.

### ★브라우저로 열어 확인한 것 — 가드레일이 옳게 동작했다

승인 화면을 실제로 열었더니 **환불 제안의 승인 버튼이 `disabled`** 였다.
처음엔 UI 결함으로 의심했으나, `app/presentation/ui/routes.py:191` 이 원인이었다:

```python
disabled = " disabled" if not evidence else ""
```

★**근거 없는 제안은 승인할 수 없다** (`CLAUDE.md` §0.1). 가드레일이 옳았고
**seed 스크립트가 evidence 를 안 넣은 것이 잘못**이었다. seed 에 근거 3건
(policy_chunk `doc_06#c3` · payment `seed-pay-0001` · subscription `seed-sub-0001`)을
넣자 버튼이 열렸고, 근거가 없는 옛 Case 는 **여전히 disabled 로 남았다** — 구분되고 있다.

## ★같은 확인에서 결함 하나를 새로 찾았다

`approve()` 의 두 분기가 **같은 응답**을 냈다:

```python
if response.is_error:
    return RedirectResponse("/ui/approvals", status_code=303)
return RedirectResponse("/ui/approvals", status_code=303)
```

승인이 실패해도 운영자는 목록으로 돌아올 뿐 **무엇이 잘못됐는지 알 수 없었다.**
승인은 되돌릴 수 없는 행위인데 실패를 삼키면 "눌렀으니 됐겠지" 로 넘어간다
(`CLAUDE.md` §3 — 조용한 스킵을 만들지 않는다).
실패 사유를 화면에 띄우도록 고치고 `tests/integration/api/test_ui_approval_failure_is_visible.py` 로 고정했다.

★**HTTP 200 만 봤다면 못 찾았다.** 최초 판정에서 4화면 200 을 확인하고도
화면이 비어 있었던 것과 같은 종류의 누락이다.

## 남은 한계

- 시나리오 1 은 `resuming(5)` 까지 관측했다. `→running(6)→resolved(7)` 은
  Controller 를 붙여야 하고, 화면에서 그 두 단계를 이어 본 적은 없다
- 발표용 seed 는 **LLM 을 부르지 않는다.** 분류·proposal 이 고정값이고
  `state_json.seeded_by = "scripts.seed_demo_cases"` 로 구분된다.
  **실제 분류기가 만든 Case 로 같은 화면 흐름을 본 것은 아니다**
- 스크린샷을 `wiki/records/screenshots/` 에 남기지 않았다 (텍스트 실측만 있다)

Controller 통합 테스트는 두 시나리오를 **코드로** 끝까지 통과시켰지만
(`classifying(1)→…→resolved(7)`), 그 Case 들은 테스트 teardown 에서 삭제된다.
**화면에서 같은 흐름을 보여준 적이 없다.**

또한 DoD-09(분류기 미연결)가 막혀 있어 API 로 만든 Case 는 전부 `escalated` 가 된다 —
발표 시나리오를 화면으로 재현하려면 그것부터 풀려야 한다.

## 재측정 조건 — 2026-08-14 에 1·2 를 충족했다

1. ~~DoD-09 배선 수정 후~~ → 완료 (`wiki/records/evidence/DoD-09_인라인분류_전건실행.md`)
2. ~~seed 기반으로 시나리오 1·2 Case 를 **삭제하지 않고** 만들어 두고~~ → `scripts/seed_demo_cases.py`
3. 화면 캡처를 `wiki/records/screenshots/` 에 남긴다 → **미수행**. 텍스트 실측으로 대체했다
