# DoD-09 — 인라인 감성·의도·이슈 분류가 모든 Case 생성에서 실행된다

- v5 §20 항목 9 / 검증 방법: classification fixture
- 최초 판정: 2026-08-12 23:20 **미통과** (분류기 미연결)
- 재측정: 2026-08-13 · 실측 원문 `wiki/records/evidence/_raw/DoD-09_v2.md`
- 판정: 통과

## 재현 명령

```powershell
python  # TestClient 로 POST /v1/cases (fake classifier 주입) 후 DB 조회
```

## 실제 출력 (재측정)

```
POST 응답 status = 201
응답: intent=billing, issue_code=payment_failed, sentiment=negative, status=routing
customer_cases 조회 = ('billing', 'payment_failed', 'negative', 'routing')
case_events = ['created', 'classified']
```

## 판정 근거

| 요구 | 결과 |
|---|---|
| 분류가 **실행**된다 | **통과** — 세 라벨이 모두 채워졌다 |
| 상태가 `escalated` 가 아니다 | **통과** — `routing` 까지 진행 |
| `classified` 이벤트가 남는다 | **통과** — `['created', 'classified']` |
| 분류 실패 시 `classification_failed` + `escalated` | **통과** (유지) — 실패 fake 주입 테스트가 별도로 있다 |

## 최초 판정에서 무엇이 바뀌었나

2026-08-12 실측에서는 이랬다:

```
status= 201, intent=null, issue_code=null, sentiment=null, status=escalated
customer_cases= (None, None, None)
events= ['created', 'classification_failed']
```

★원인은 **배선 누락**이었다 — `feedback.classify()` 는 구현돼 있고 단위 테스트도 통과했는데
`create_app()` 이 그것을 주입하지 않아 분류기가 항상 `None` 이었다.
S-API 는 주입 지점을, S-VOC 는 함수를 만들었고 **둘을 잇는 일을 아무에게도 주지 않은 것**이
원인이었다(내 계약의 구멍). → `wiki/records/reports/debugs/2026-08-12_2320_*`

`create_app()` 이 분류기를 주입하도록 고친 뒤 재측정해 위 결과를 얻었다.

## 한계

- 측정에 **fake classifier 를 주입**했다. 실제 LLM 분류기의 정확도는 이 항목이 아니라
  DoD-15/16(평가)에서 측정한다
- 외부 분류기 실호출 결과는 확인하지 못했다 (이 환경은 외부 네트워크가 막혀 있다)
- 분류 **품질**(intent accuracy, issue macro-F1)은 여기서 다루지 않는다.
  이 항목은 "**실행되는가**" 만 본다
