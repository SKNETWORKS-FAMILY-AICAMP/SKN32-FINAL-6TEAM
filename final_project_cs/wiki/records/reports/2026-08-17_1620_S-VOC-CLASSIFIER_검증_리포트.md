# 2026-08-17 16:20 — VOC/운영 classifier 도메인 어휘 수정 검증 리포트

## 1. 작업 목표

`app/modules/customer_ops/feedback.py` 의 `INTENTS = {"billing","technical","other"}`
가 **운영 REST API 의 기본 classifier** 로 꽂혀 있다는 것을 발견했다
(`app/composition.py::build_classifier()` → `app/presentation/api/app.py`).
쇼핑몰 메시지를 정직하게 분류하면 `intent="order"/"shipping"` 등이 나오는데 그
값이 옛 `INTENTS` 밖이라 **분류가 계속 실패했을 것**이다 — 이 세션에서 발견한 것
중 가장 심각한 결함이다(운영 경로 영향).

## 2. 수행 내용

새 어휘는 Claude 가 직접 설계(Team 라우팅 계약과 정확히 맞아야 하는 핵심 결정이라
Codex 의 재량에 맡기지 않았다):

```
INTENTS = {"order", "shipping", "return", "exchange", "other"}
ISSUE_CODES = 13종 (order/shipping/return/exchange 각 전용 코드 + other)
```

`wiki/records/handoff/_prompts/S-VOC-CLASSIFIER.md` 계약으로 이 정확한 값을 명시하고
Codex 에 기계적 전파(상수 교체·프롬프트 문구 교체·테스트 fixture 교체)만 위임.

## 3. 검증 (Claude 가 독립적으로 재실행)

| 검사 | 결과 |
|---|---|
| 소유 범위 | `git diff --stat` — `feedback.py`·`tests/unit/voc/test_feedback.py` 2개 파일, 15줄 변경. 계약과 정확히 일치 |
| `pytest tests/unit/voc -q` | 8 passed |
| `pytest -q`(전체) | 294 passed → (아래 §4 신규 테스트 추가 후) 295 passed |
| ★실 운영 경로 스모크 | `composition.build_classifier()`(API 가 실제 주입하는 그 함수)를 직접 호출, 실 LLM 으로 `'배송완료로 떴는데 상품을 못 받았습니다.'` 분류 → `{'intent': 'shipping', 'issue_code': 'shipping_delivered_not_received', ...}` — 수정 전이었다면 이 값 자체가 `ClassificationFailed` 를 냈을 것 |

### ★검수 중 소동 — 잘못된 의심, 조사 후 해소

소유 범위 확인 중 `git status` 에 `tests/unit/test_project_composition.py` 도
변경된 것으로 나타나 Codex 가 범위를 넘었다고 처음 의심했다. 확인 결과 이 파일은
이번 세션 훨씬 이전(다른 작업)에 이미 고쳐져 있었고, `git diff` 가 단일 초기 커밋
대비 보여주는 것이라 이번 Codex 실행과 무관하게 나타난 것이었다. 이 파일을 임시로
`git checkout HEAD --`로 되돌려 실행해 보니 **실제로 4건이 실패**했다 — 이는
동시에 **이 세션 내내 반복해 온 `pytest -q` 전체 실행이 실제 결함을 놓치지 않고
잡아낼 수 있다**는 것도 증명했다(그 4건이 항상 존재했다면 "294 passed" 로
나오지 않았을 것이다). 확인 즉시 원상 복구했다. Codex 의 실제 변경 범위는
계약대로 2개 파일뿐이었다.

## 4. 재발 방지 — 구조적 불변조건 테스트 추가

`wiki/records/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md` 의 "남은 위험" 절에서
지적한 대로, **이 결함 종류(classifier 어휘가 실제 라우팅 가능한 case_type 과
어긋남)를 구조적으로 잡는 테스트가 없었다.** Codex 위임 없이 직접 작성:

`tests/unit/voc/test_feedback_intent_alignment.py` —
`OrderShippingTeam.manifest.accepted_case_types ∪ ReturnExchangeTeam.manifest
.accepted_case_types ⊆ feedback.INTENTS` 를 검사한다. 이 테스트를 옛 `INTENTS`
값으로 몽키패치해 실행 → 정확히 `{'order','shipping','return','exchange'}` 누락을
검출함을 확인(테스트가 실제로 이 버그 클래스를 잡는다는 것을 증명).

## 5. 산출물

```
app/modules/customer_ops/feedback.py                       수정 (Codex, 검수됨)
tests/unit/voc/test_feedback.py                             수정 (Codex, 검수됨)
tests/unit/voc/test_feedback_intent_alignment.py            신규 (Claude 직접 작성)
wiki/records/handoff/_prompts/S-VOC-CLASSIFIER.md                    신규 (Codex 계약)
wiki/records/reports/2026-08-17_S-VOC-CLASSIFIER_리포트.md            신규 (Codex 자체 보고)
wiki/records/evidence/PROD-CLASSIFIER-DOMAIN-MISMATCH_수정.md         신규
```

## 6. 미해결 이슈

- 이 결함이 **얼마나 오래 있었는지**는 커밋 이력만으로 특정 못 한다(이 파일을 건드린
  커밋이 최초 도메인 전환 커밋 하나뿐이고 그 뒤로 커밋된 적이 없다).
- REST API 를 통한 진짜 Case 생성 end-to-end 테스트(실 메시지 → 실 분류 → 실
  라우팅)가 스위트에 여전히 없다. 이번에 추가한 것은 "어휘 집합이 일치하는가"라는
  **정적 불변조건**이지, "실제로 그 경로가 끝까지 동작하는가"의 **동적 e2e 증거**는
  아니다. `tests/unit/voc/test_feedback.py` 는 injected 스텁을 쓰고,
  `eval/runners/common.py::_team_context()` 는 `expected_intent` 를 직접 주입해
  분류 단계 자체를 건너뛴다. 실 REST API(`/v1/cases`)에 실 메시지를 보내 실
  LLM 분류로 Case 가 만들어지고 라우팅까지 되는 e2e 테스트는 이번 범위 밖이라
  만들지 않았다 — 다음 작업 후보로 남긴다.
