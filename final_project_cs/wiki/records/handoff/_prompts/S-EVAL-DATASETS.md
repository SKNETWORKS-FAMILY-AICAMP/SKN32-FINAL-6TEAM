# 구현 지시 — golden/holdout 평가 데이터셋을 쇼핑몰 도메인으로 재작성

## 0. 배경 — 왜 이 작업이 필요한가

`eval/datasets/golden.jsonl`(60건)과 `eval/datasets/holdout.jsonl`(20건)은 아직
**옛 구독·결제 도메인**(영어 메시지, `billing`/`technical` intent, `doc_01`·`doc_02`·
`doc_05`·`doc_06`·`doc_24` 등 존재하지 않는 문서를 인용)이다.

`knowledge/documents/` 는 이미 쇼핑몰 도메인 25문서로 전면 교체됐다
(`wiki/records/plans/2026-08-17_코퍼스_25문서_배분안.md`). 옛 golden/holdout 이 인용하는
문서는 전부 삭제됐다 — 지금 이 데이터셋으로 평가를 돌리면 존재하지 않는 근거를
"정답"으로 채점하게 된다.

`eval/datasets/attack_fixtures.jsonl` 은 **이미 쇼핑몰 도메인으로 마이그레이션됐다**
(order_id·refund_amount·return_quantity 어휘, 17건). 이 파일은 건드리지 않는다 — 참고만 한다.

## 1. 소유 범위

```
eval/datasets/golden.jsonl     ← 전체 재작성 (60건)
eval/datasets/holdout.jsonl    ← 전체 재작성 (20건)
wiki/records/reports/                  ← 작업 리포트 제출 (RULE.md §3.4 필수)
```

★금지 — 다음은 절대 건드리지 않는다:
`eval/datasets/attack_fixtures.jsonl`, `eval/runners/**`, `eval/stats/**`,
`eval/defense_metrics.py`, `app/**`, `knowledge/**`, `config/**`, `tests/**`,
`prompts/**`, `scripts/**`. 이 스트림의 소유 디렉터리 밖이다(RULE.md §3.6-2).

## 2. 도메인 사실 — 지어내지 않는다

### 2-1. 라우팅 가능한 intent 는 4종뿐이다

Team 이 두 개만 있고 각각 이 `case_type` 만 받는다(`app/modules/customer_ops/*.py`):

| Team | accepted_case_types |
|---|---|
| `OrderShippingTeam` | `order`, `shipping` |
| `ReturnExchangeTeam` | `return`, `exchange` |

`expected_intent` 는 **반드시 이 4개 문자열 중 하나**여야 한다:
`order` · `shipping` · `return` · `exchange`.
`billing`·`technical`·`refund`·`support`·`incident` 는 **쓰지 않는다** — 이 값으로는
Case 가 어느 Team 으로도 라우팅되지 않는다(그 스코프의 문서는 RAG 근거로만 쓰인다).

### 2-2. 문서 색인 — 인용은 이 파일에 있는 것만

`wiki/records/handoff/_prompts/_doc_index.json` 에 25문서의 `document_id`·`scope`·`title`·
`sections`(섹션 제목 전체)가 정확히 들어 있다. **이 JSON 에 없는 문서 ID·섹션 제목을
지어내지 않는다.** 각 케이스의 `doc_ref` 필드는 반드시 이 JSON 에 실제로 존재하는
`document_id`와 그 문서의 `sections` 배열에 있는 문자열 그대로여야 한다(공백 하나도
다르면 안 된다 — 검증 스크립트가 문자열 완전일치로 대조한다).

scope→intent 매핑 (문서를 고를 때 이 표를 따른다):

| scope | 쓸 수 있는 intent | 문서 |
|---|---|---|
| `shipping` | `shipping` (배송지 변경은 `order`도 가능 — 아래 참고) | doc_01~05 |
| `order` | `order` | doc_06~10 |
| `return` | `return` | doc_11~14 |
| `exchange` | `exchange` | doc_15~17 |

`refund`·`support`·`incident` scope 문서(doc_18~25)는 **케이스의 `doc_ref` 로 쓰지 않는다**
— 어느 intent 로도 라우팅되지 않으므로 golden/holdout 케이스의 근거가 될 수 없다.

### 2-3. 정책 사실을 지어내지 않는다

케이스 문구(특히 `notes`)에 구체적인 정책 수치(기한·비율·금액)를 넣을 때는
`_doc_index.json` 이 가리키는 실제 문서 파일(`knowledge/documents/<file>.md`)을 열어
**그 문서에 실제로 적힌 수치**를 쓴다. 특히 이 프로젝트에서 실제로 틀렸던 것들:

- 청약철회(단순변심) 기한은 **7일** (40%가 아니다, 15일도 아니다)
- 환불 지연이자는 **연 15%** (연 40%는 법률상 상한일 뿐 실제 요율이 아니다)
- 대금 환급은 **3영업일 이내** (반품은 재화를 반환받은 날 기산)

모르는 수치는 케이스에 넣지 않는다 — 수치 없이 시나리오만 써도 된다.

## 3. 스키마 — 필드 이름·타입을 정확히 지킨다

JSONL, 한 줄에 한 케이스. 필드는 정확히 이 8개, 순서는 상관없다:

```json
{
  "case_id": "g-order-01",
  "message": "실제 고객이 보낼 법한 한국어 문의 (1~3문장, 반말/존댓말 자연스럽게)",
  "channel": "web",
  "expected_intent": "order",
  "expected_issue_code": "duplicate_charge_after_cancel",
  "expected_sentiment": "negative",
  "expected_next_action": "wait_for_approval",
  "doc_ref": "doc_08#판매자 귀책에 의한 취소",
  "notes": "normal; 실제 결제 취소 이력이 있음에도 이중 청구된 사례"
}
```

| 필드 | 규칙 |
|---|---|
| `case_id` | golden `g-<intent>-NN`, holdout `h-<intent>-NN`. `NN`은 그 intent 그룹 안에서 01부터. 전체 80건에서 **중복 금지** |
| `message` | **한국어만.** 영어 금지(옛 데이터셋의 실패를 반복하지 않는다). 실제 CS 채널에 올 법한 자연스러운 문장 |
| `channel` | `web` \| `chat` \| `email` \| `phone` 중 하나 |
| `expected_intent` | §2-1 의 4개 값 중 하나만 |
| `expected_issue_code` | 영문 snake_case. 같은 시나리오 계열이면 같은 코드를 재사용해도 됨(단, golden·holdout 이 완전히 같은 코드+같은 메시지 조합이면 안 됨) |
| `expected_sentiment` | `positive` \| `neutral` \| `negative` \| `frustrated` \| `worried` \| `confused` 중 하나 |
| `expected_next_action` | `continue` \| `wait_for_input` \| `wait_for_approval` \| `call_tool` \| `handoff` \| `respond` \| `escalate` 중 하나(`app/core/contracts.py` `NextAction`) |
| `doc_ref` | `"doc_NN#정확한 섹션 제목"` — §2-2 규칙 |
| `notes` | 자유 서술. golden 은 `"normal; ..."`, holdout 은 `"holdout; ...; frozen and not used for prompt tuning"` 로 시작 |

## 4. 케이스 배분

### golden.jsonl — 60건

| intent | 건수 | case_id 범위 |
|---|---|---|
| `order` | 15 | g-order-01 ~ g-order-15 |
| `shipping` | 15 | g-shipping-01 ~ g-shipping-15 |
| `return` | 15 | g-return-01 ~ g-return-15 |
| `exchange` | 15 | g-exchange-01 ~ g-exchange-15 |

### holdout.jsonl — 20건

| intent | 건수 | case_id 범위 |
|---|---|---|
| `order` | 5 | h-order-01 ~ h-order-05 |
| `shipping` | 5 | h-shipping-01 ~ h-shipping-05 |
| `return` | 5 | h-return-01 ~ h-return-05 |
| `exchange` | 5 | h-exchange-01 ~ h-exchange-05 |

★holdout 은 golden 과 **다른 구체 시나리오**를 쓴다(같은 문서·섹션을 다시 인용해도
되지만, `message` 문장을 golden 케이스와 실질적으로 같게 쓰지 않는다). holdout 은
"보존"이 원칙이다 — 이번에 한 번만 쓰고 이후 프롬프트 튜닝에 다시 손대지 않는다
(`RULE.md` 는 아니지만 `eval/datasets/` 의 기존 관례).

### 각 intent(order/shipping/return/exchange) 안에서 문서 커버리지

그 intent 에 해당하는 scope 의 모든 문서(예: `order`→doc_06~10 다섯 개)가
golden 15건 안에서 **최소 2번 이상씩** `doc_ref` 로 등장해야 한다. 특정 문서 하나에
쏠리지 않게 한다.

### 시나리오 다양성 — 최소 요구

- 최소 3건은 `expected_next_action: "wait_for_approval"` 이며, 그 문서 근거가
  실제로 승인 흐름이 있는 섹션이어야 한다(doc_01 배송완료-미수령 계열,
  doc_08 판매자 귀책 취소, doc_14 반품 수량 초과 계열 등 — `_doc_index.json` 에서
  "승인" 이 들어간 섹션 제목을 찾아 그 문서로 연결한다).
- 최소 3건은 `notes` 에 `degraded` 또는 `expected_issue_code` 에 `unavailable` 포함
  — RAG 조회 실패·근거 부족 상황을 나타낸다(실제로 그런 근거가 부족한 척하는
  케이스이며, 근거 문서 자체는 정상적으로 존재해도 된다).
- 최소 5건은 `expected_sentiment` 가 `negative` 또는 `frustrated` — 불만 섞인 문의도
  섞는다(전부 중립적인 문의만 있으면 감성 분류를 평가할 수 없다).

## 5. 검증 — Claude 가 이렇게 확인한다(참고용, 네가 직접 돌릴 필요는 없다)

```
python -m scripts.verify_eval_datasets   # (Claude 가 작성해 검증한다)
```

다음을 기계적으로 대조한다: 건수(60/20), `case_id` 형식과 중복 여부,
`expected_intent`/`expected_next_action`/`expected_sentiment` 값이 허용 집합 안에
있는지, `doc_ref` 가 `_doc_index.json` 과 완전일치하는지, 문서 커버리지(§4),
한국어 여부(ASCII 알파벳 비중이 비정상적으로 높은 `message` 를 잡아낸다).

★네 산출물은 **그대로 신뢰되지 않는다.** 이 검사를 통과하지 못하면 반려하고
다시 요청한다 — 결과를 리포트에 남긴다(RULE.md §3.6-3·§3.6-4).

## 6. 완료 조건

- [ ] `eval/datasets/golden.jsonl` 정확히 60줄, `eval/datasets/holdout.jsonl` 정확히 20줄
- [ ] 모든 줄이 유효한 JSON, 스키마 8필드 정확
- [ ] `expected_intent` 가 4값 중 하나뿐, `billing`/`technical`/`refund`/`support`/`incident` 없음
- [ ] `doc_ref` 전부 `_doc_index.json` 과 문자열 완전일치
- [ ] `message` 전부 한국어
- [ ] `case_id` 80건 전체 중복 없음
- [ ] §4 커버리지·다양성 요구 충족
- [ ] `wiki/records/reports/2026-08-17_S-EVAL-DATASETS_리포트.md` 제출 — 무엇을 몇 건 어떻게 배분했는지,
      어느 문서·섹션을 근거로 썼는지 요약 표 포함
