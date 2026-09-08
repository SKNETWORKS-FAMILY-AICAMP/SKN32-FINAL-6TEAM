# S-EVAL-RUNNER-TEAM-AGNOSTIC 보고서

작성일: 2026-08-20

## 결론

`eval/runners/common.py`의 `_team_context()`에서 `OrderShippingTeam`과
`ReturnExchangeTeam` 직접 import 및 intent별 분기를 제거했다. 이제
`app.composition.build_registry()`가 `config/project.yaml`을 읽어 구성한
Registry에 `TeamRegistry.resolve(case_type=..., intent=...)`를 호출한다.
Team 인스턴스의 생성자 형태는 composition root의 기존 `_instantiate_team()`을
통해 처리된다.

라우팅 실패는 조용히 버려지지 않는다. Registry가 해석하지 못하면
`RuntimeError` 메시지에 `routing_failed`와 `case_type`/`intent`가 포함되어
상위 runner 결과의 error 필드로 남는다.

## 변경 사항

- 라우팅 필드: golden/holdout 스키마의 `expected_intent`를 사용했다.
  `expected_case_type`가 존재하는 스키마도 수용하도록 case type은
  `expected_case_type` 우선, 없으면 `expected_intent`로 읽는다.
- Registry의 resolved entry에서 module을 얻고,
  `TeamRegistry.capability_for()`로 intent에 맞는 capability를 선택한다.
- `no_team_split`: Registry가 선언한 Team 경계를 runner가 임의로 합칠 수
  없으므로, 현재 구조에서는 기존의 “두 Team을 하나로 합쳐 처리” 실험을
  재현할 수 없다. 플래그는 호환성을 위해 받되 Registry 라우팅을 그대로
  수행하는 no-op으로 두었다. 즉, 이 ablation 결과를 과거 의미의
  no-team-split 결과로 해석하면 안 된다.

수정 파일은 다음 두 개뿐이다.

- `eval/runners/common.py`
- 본 보고서

`golden.jsonl`, `holdout.jsonl`, `config/project.yaml`,
`app/composition.py`, `app/core/registry.py`는 수정하지 않았다.

## 현재 Registry 기준 라우팅 점검

현재 `config/project.yaml`에 등록된 active Team은 다음과 같다.

| team_id | accepted_case_types | capabilities |
|---|---|---|
| `voc_store_manager` | `other` | `voc.aggregate`, `voc.escalate` |
| `response_generation_review` | `[]` | `response.generate_review` |

Registry를 실제로 구성한 뒤 각 데이터셋의 모든 case에 대해
`resolve(case_type=expected_intent, intent=expected_intent)`를 실행했다.

| dataset | 전체 | 라우팅 성공 | `routing_failed` |
|---|---:|---:|---:|
| golden | 72 | 0 | 72 |
| holdout | 24 | 0 | 24 |

legacy intent별 집계는 golden이 order/shipping/return/exchange 각 15건 모두
실패하고, holdout은 각 5건 모두 실패했다. 데이터셋에는 별도로
response-review 보조 케이스 golden 12건/holdout 4건이 있으며 이들도 모두
실패했다. 실패 case ID는 다음과 같다.

- golden order: `g-order-01`–`g-order-15`
- golden shipping: `g-shipping-01`–`g-shipping-15`
- golden return: `g-return-01`–`g-return-15`
- golden exchange: `g-exchange-01`–`g-exchange-15`
- golden response-review 보조 케이스: `g-response-review-01`–`g-response-review-12`
- holdout order: `h-order-01`–`h-order-05`
- holdout shipping: `h-shipping-01`–`h-shipping-05`
- holdout return: `h-return-01`–`h-return-05`
- holdout exchange: `h-exchange-01`–`h-exchange-05`
- holdout response-review 보조 케이스: `h-response-review-01`–`h-response-review-06`

이 점검은 Team 실행이나 LLM 호출 없이 Registry resolve 단계만 수행했다.
현재 등록된 Team에 해당 case type이 없으므로 실제 Team 실행까지 진행할 수
없었다. 이는 데이터셋의 옛 2-Team 매핑을 새 Team으로 임의 보정한 결과가
아니다.

## 데이터셋 매핑 갭에 대한 제안

golden/holdout을 직접 수정하지 않고, 다음 결정을 데이터셋 소유자와 설계자가
먼저 확정해야 한다.

1. 각 case에 `expected_case_type` 또는 별도의 routing label을 추가해
   `expected_intent=order`가 Procurement+Order&Payment인지
   Catalog&Verification(A2A)인지 표현한다.
2. shipping은 Fulfillment&Logistics, return/exchange는 Return&Refund로
   연결하는 새 routing label을 명시한다.
3. Registry가 활성화된 뒤에는 데이터셋 검증 단계에서 각 case가 정확히 한
   active Team으로 resolve되는지 검사하고, 0개 또는 2개 이상이면
   `routing_failed`로 집계한다.
4. 과거 두 Team 분할과 새 분할의 비교가 필요하면 데이터셋 버전 또는 별도
   라우팅 매핑 fixture를 두고, 현재 `no_team_split` 플래그를 과거 실험의
   동일 조건이라고 간주하지 않는다.

## 검증

- `python -c "import eval.runners.common"`: 성공 (`import ok`)
- `python -m pytest -q -m "not live"`: `324 passed, 3 failed, 11 errors,
  3 deselected`

요청 배경에 제시된 기준 `338 passed`와 비교하면 이 실행에서는 14건이
통과하지 않았다. 실패 원인은 변경한 runner가 아니라 실행 환경 제약으로
확인됐다. RAG 통합 테스트 3건은 OpenAI API 네트워크 접근 차단으로 실패했고,
e2e/fixture 11건은 `C:\Users\playdata2\AppData\Local\Temp\pytest-of-playdata2`
접근 권한 오류로 setup 단계에서 실패했다. 따라서 이 환경에서는 전체 테스트가
기준 상태와 동일하다고 주장할 수 없다.
