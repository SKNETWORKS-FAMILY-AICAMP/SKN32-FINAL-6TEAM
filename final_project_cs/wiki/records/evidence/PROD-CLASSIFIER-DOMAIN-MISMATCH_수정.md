# evidence — 운영 REST API 기본 classifier 가 쇼핑몰 Case 를 분류하지 못하던 결함 수정

- 실행: 2026-08-17
- 판정: 통과
- ★심각도: 이 세션에서 발견한 것 중 **가장 심각한 결함이다** — 운영 경로에 영향을 줬다

## 문제

`app/modules/customer_ops/feedback.py` 의 `INTENTS = frozenset({"billing",
"technical", "other"})` 는 VOC 분석 전용 상수가 아니다. 호출 경로:

```
app/presentation/api/app.py::create_app()
  → composition.build_classifier()          (classifier 인자가 없으면 기본값)
    → app/composition.py::build_classifier()
      → feedback.classify(masked(message))   ← 여기
```

`build_router(classifier, ...)` 가 이 classifier 를 `/v1/cases` Case 생성 라우터에
꽂는다. 즉 **이것이 운영 REST API 로 들어오는 모든 신규 Case 의 실제 분류 경로다.**

쇼핑몰 메시지를 정직하게 분류하면 LLM 은 `intent="shipping"` 또는 `"order"` 등을
반환한다. 그 값이 옛 `INTENTS={"billing","technical","other"}` 밖이므로
`classify()` 의 검증(`app/modules/customer_ops/feedback.py:100`,
`if result.intent not in INTENTS: raise ClassificationFailed(...)`)에 걸려
**모든 신규 쇼핑몰 Case 가 분류 실패로 떨어졌을 것이다.** (`classification_failed`
+ `escalated` 로 안전하게 처리되긴 하지만 — 정상 분류·라우팅이 전혀 안 된다는
뜻이다.)

## 재현 (수정 전 실패 확인 — 코드 검사로 대체)

수정 전 `INTENTS`/`ISSUE_CODES` 값은 `git diff` 로 확인 가능:
`app/modules/customer_ops/feedback.py`(git HEAD 버전)의
`INTENTS = frozenset({"billing", "technical", "other"})`.
LLM 이 `intent="shipping"` 을 반환하면 `feedback.py:100` 의
`if result.intent not in INTENTS: raise ClassificationFailed(...)` 이 즉시 걸린다 —
코드 경로상 자명하므로 별도의 "실패 재현 실행"은 생략한다(수정 자체가 이미
`intent="shipping"` 이 통과하는 것으로 결과를 낸다 — 아래).

## 수정

`INTENTS`·`ISSUE_CODES`·시스템 프롬프트 텍스트를 쇼핑몰 도메인으로 교체.
새 `INTENTS = {"order", "shipping", "return", "exchange", "other"}` 는
`app/modules/customer_ops/order_shipping.py`·`return_exchange.py` 의
`TeamManifest.accepted_case_types` 와 정확히 일치한다(라우팅에 그대로 쓰이므로
반드시 일치해야 한다 — `app/application/controller.py` 의
`registry.resolve(case_type=intent)`).

## 검증 (Claude 가 독립적으로 재실행 — RULE.md §3.6-3)

```powershell
python -m pytest tests/unit/voc -q                 # 8 passed
python -m pytest -q                                 # 294 passed, 1 deselected
```

### ★실 LLM 스모크 — 실제 운영 경로 그대로

```python
from app import composition
classifier = composition.build_classifier()   # 이것이 API 의 기본 classifier 다
result = classifier('배송완료로 떴는데 상품을 못 받았습니다.')
```

```
{'intent': 'shipping', 'issue_code': 'shipping_delivered_not_received', 'sentiment': 'negative'}
```

`composition.build_classifier()` 를 직접 호출해 `app/presentation/api/app.py` 가
실제로 주입하는 것과 **동일한 함수**로 확인했다. 실 OpenAI 호출로 반환된
`intent='shipping'` 값이 새 `INTENTS` 를 통과했다 — 수정 전이었다면 이 값 자체가
`ClassificationFailed` 를 냈을 것이다.

## Codex 산출물 검수 중 있었던 소동 (기록으로 남긴다)

이 작업(S-VOC-CLASSIFIER)의 소유 범위 확인 중 `git status --short` 에
`tests/unit/test_project_composition.py` 가 함께 변경된 것으로 나타나 **처음엔
Codex 가 소유 범위 밖 파일을 건드린 것으로 의심했다.** 확인 결과 이 파일은 이번
세션 훨씬 이전(다른 작업, 커밋되지 않은 상태)에 이미 옛 team_id 참조를 고쳐 둔
것이었고 — `git diff` 는 세션 시작 시점의 단일 커밋(HEAD) 대비 보여주므로, **이번
Codex 실행과 무관한 기존 변경까지 함께 나타난 것**이었다. 이 파일을 임시로
HEAD 로 되돌려 실행해 보니 실제로 4건이 실패하는 것을 확인했다(→ **이 세션의
반복된 `294 passed` 관측이 실제로 결함을 잡아낼 수 있다는 것도 함께 증명됐다**).
확인 후 즉시 원상 복구했다. Codex 는 실제로는 계약이 지정한 두 파일
(`feedback.py`·`tests/unit/voc/test_feedback.py`)만 변경했다 — `git diff --stat` 로
확인.

## 남은 위험

- 이 결함이 **얼마나 오래 있었는지**(이번 세션의 도메인 마이그레이션 때부터인지,
  더 이전인지)는 커밋 이력만으로는 특정하지 못한다 — `git log` 상 이 파일을 건드린
  커밋은 최초 도메인 전환 커밋 하나뿐이고, 그 뒤로 한 번도 커밋되지 않았다.
- REST API 를 통한 실제 Case 생성 e2e 테스트(진짜 메시지 → 진짜 분류 → 진짜 라우팅)가
  스위트에 없다. `tests/unit/voc/test_feedback.py` 는 injected LLM 스텁을 쓰고,
  `eval/runners/common.py` 의 `_team_context()` 는 `expected_intent` 를 그대로
  주입해 분류 자체를 우회한다. **이런 종류의 "값 집합이 실제 도메인과 안 맞는" 결함을
  구조적으로 잡는 테스트가 없다** — `INTENTS` 와 `TeamManifest.accepted_case_types`
  가 항상 일치해야 한다는 불변조건을 검사하는 단위테스트를 추가하면 재발을 막을 수
  있다. 이번 작업 범위 밖이라 만들지 않았다.
