# S-DOD29-COMPLETE — Response Generation & Review Team 를 실행 가능하게 배선하고 golden/holdout 커버리지를 채운다

## 0. 배경 (읽기만, 수정 금지)

- `docs/evidence/DoD-29_ResponseGenerationReview.md` — 현재 판정 "부분 통과".
  남은 이유 둘: ① `config/project.yaml` `teams:` 에 미등록 — Registry 에
  없어서 자동으로도 수동으로도 실행된 적이 없다. ② golden/holdout 데이터셋에
  이 Team 대상 case 가 0건 (v8 §1031 배분: 12건).
- `app/modules/customer_ops/response_review.py`, `response_review_policy.py`
  — 이미 구현·검증됨(`tests/unit/teams/test_response_review.py` 6건 통과,
  `tests/live/test_response_review_live_smoke.py` 실 LLM 통과 확인됨). 이
  파일들의 로직은 건드리지 않는다 — 배선(wiring)과 데이터만 작업 범위다.
- `ResponseGenerationReviewTeam.accepted_case_types == []` 다 — 이건 v8
  원문이 의도한 설계다("Controller 자동배선 범위 밖", 다른 Team 의 응답을
  사후 검증하는 2차 파이프라인 단계라는 의미). **그래서 `TeamRegistry.resolve()`
  의 일반 case_type 라우팅으로는 절대 이 Team 이 안 걸린다** — 이걸 다른
  case_type 을 억지로 채워서 우회하지 않는다. 대신 아래 §1 의 설계를 따른다.
- `app/core/registry.py`, `app/core/controller.py`(또는 동등한 실행 오케스트레이션
  모듈 — 정확한 파일명은 직접 찾아라)를 먼저 읽고 현재 Team 실행 흐름을
  파악한 뒤 시작해라.

## 1. 배선 설계 (구현 전에 결정하고 리포트에 근거를 남긴다)

목표: 어떤 Team 이 `TeamResult.answer`(응답 텍스트)를 만들면, **설정으로
켜져 있을 때만** `ResponseGenerationReviewTeam` 이 그 응답을 검증하는
2차 단계로 이어지게 한다. 기본값은 꺼짐(disabled) — 기존 동작을 절대
바꾸지 않는다. 이 원칙 안에서 가장 최소침습적인 구현 방법을 네가 골라라.
후보(예시일 뿐, 다른 안이 더 낫다고 판단되면 그걸 써도 된다 — 단 왜
골랐는지 리포트에 반드시 남겨라):

- (안 A) Controller 의 Team 실행 직후 지점에 "review pass" 훅을 추가하고,
  `config/project.yaml` 에 `response_review: {enabled: false, owner_team_id: response_generation_review}`
  같은 최상위 설정 블록을 하나 추가해 켜고 끌 수 있게 한다.
- (안 B) 별도의 명시적 REST 엔드포인트나 CLI 명령으로 "이 case_id 의
  응답을 검증해줘"를 호출하게 만든다(자동배선 없이 수동 트리거만).

어느 쪽이든:
- **Core 는 Team 내부를 import 하지 않는다** 원칙(`CLAUDE.md` §2)을 지켜라 —
  Controller 가 `TeamManifest` 와 `execute()` 만으로 이 Team 을 다뤄야 한다.
- 계약 모델(`app/core/contracts.py`) 을 변경해야 한다면 `docs/handoff/01_계약_Pydantic.md`
  와 반드시 함께 갱신해라. 둘이 어긋나면 결함이다.
- `config/project.yaml` 에 새 필드를 추가한다면 `app/core/project_config.py`
  의 Pydantic 모델도 같이 갱신해야 검증을 통과한다.

## 2. golden/holdout 데이터셋 12건 추가

- `eval/datasets/golden.jsonl`, `eval/datasets/holdout.jsonl` (정확한 경로는
  직접 확인해라)의 기존 스키마를 그대로 따라 이 Team 을 대상으로 한 case
  를 추가한다. v8 §1031 배분은 golden 12건이다(holdout 별도 배분이 있다면
  같이 맞춰라 — v8 원문에서 직접 확인).
- 시나리오는 실제 쇼핑몰 CS 맥락(주문/배송/반품/교환 응답에 대한 검증)으로
  작성한다 — 옛 구독/청구 도메인 어휘를 쓰지 않는다.
- 데이터를 지어내지 말고, 스키마의 각 필드가 무엇을 요구하는지 기존 다른
  Team 의 case 예시를 참고해서 형식을 맞춰라.

## 3. 검증

- 새로 만든 배선 경로에 대한 통합 테스트를 최소 2건 작성한다: (1) 설정이
  꺼져있을 때 기존 동작이 전혀 안 바뀐다는 회귀 테스트, (2) 설정이 켜져있을
  때 실제로 2차 검증이 실행돼 `outcome` 이 반영된다는 테스트.
- `python -m pytest -q -m "not live"` 전체 실행 결과를 리포트에 실제
  터미널 출력 그대로 붙여라(요약하지 말 것). 실행 전후 pass 수 변화를
  명시해라(현재 327 passed, 3 deselected).
- eval 데이터셋에 추가한 12건이 실제로 파싱되는지 확인하는 스모크 체크가
  있다면 그것도 실행해라(예: `eval/check_judge.py` 류가 있다면).

## 4. 쓰기 대상 (이 목록 밖의 파일은 만들거나 고치지 않는다)

- `app/core/controller.py`(또는 실제 오케스트레이션 파일 — 정확한 이름
  확인 후 기록)
- `config/project.yaml`
- `app/core/project_config.py` (새 설정 필드 추가 시)
- `app/core/contracts.py`, `docs/handoff/01_계약_Pydantic.md` (계약 변경 시,
  변경한다면 둘 다 반드시 같이)
- `eval/datasets/golden.jsonl`, `eval/datasets/holdout.jsonl`
- `tests/` 아래 신규 테스트 파일(정확한 위치는 기존 통합테스트 배치 규칙을
  따라라)
- `docs/reports/2026-08-20_S-DOD29-COMPLETE_리포트.md` (신규 작성)

## 5. 하지 말 것

- `response_review.py`/`response_review_policy.py` 내부 로직 수정
- 기존에 등록된 `voc_store_manager` Team 의 동작 변경
- 기본값을 켜짐(enabled: true)으로 하는 것 — 반드시 꺼짐이 기본이어야 한다
- `docs/evidence/DoD-29_ResponseGenerationReview.md` 자체를 직접 수정
  (판정 갱신은 Claude 가 한다 — 대신 리포트에 실행 근거를 남겨라)
