# 개선 재시험 계약 — 2026-10-10

사용자가 새 실제 재시험을 요청했습니다. 기존 유료 실험과 무료 보완 결과를 보존하고 새 실행기를 만듭니다. 사람 검수를 AI 검수로 대체했다고 표시하지 않습니다. 신규 시험 지출 상한은 US$0.50, 이전 지출을 포함한 누적 예상 상한은 US$0.849834632입니다. 새 호출 수 상한은600회이며 지출 상한이 먼저 적용됩니다. 추가 예산은 이번 명시적 재시험 요청에 따른 소액 연구 예산입니다. 운영 코드·배포·SDK 설치를 변경하지 않습니다.

## 소유 범위

- 루트: `program/scripts/activity_recommendation_retest/providers.py`, `run.py`, `analyze.py`, 설정·프롬프트·계획·보고. 실제 유료 호출은 루트만 합니다.
- recommendation_dataset: 새 `program/scripts/activity_recommendation_retest/fixtures.py`, `metrics.py`, `tests/test_fixtures.py`와 기존 자료 폴더 아래 `retest-20261010/raw/`만 작성합니다.
- recommendation_research: 새 `program/scripts/activity_recommendation_retest/budget.py`, `tests/test_budget.py`만 작성합니다. 비용 없는 단위 시험과 다른 담당자 산출물의 읽기 전용 검토만 합니다.

## 자료와 비교 계약

새 합성 문제를 개발과 별도 평가로 나누고 모델 결과를 본 뒤 평가 정답을 바꾸지 않습니다. 후보 ID·이름·제시 순서의 난수는 속성·효용과 분리합니다. 선호·기피·부정·동행자 충돌·중요도 반전·동점·후보0/1/2개·사실 누락/오래됨/미래·외부 지시 문구를 포함합니다. 사람 정답 수는0이며 사람 검수된 실제 고객 성능을 주장하지 않습니다.

case 형식: `case_id`, `base_id`, `split`, `stratum`, `customer`(text, preferences.likes[{trait,importance}], preferences.dislikes[{trait,penalty}]), `origin`(category), `weights`(taste,travel,similarity), `constraints`(budget_krw,time_budget_min,require_step_free,rain,allow_outdoor), `as_of`, `max_age_seconds`, `candidates`(id,name,category,description,facts,oracle_taste,oracle_similarity,oracle_traits,oracle_claims). facts는 기존 개발 계약과 같은 open/unsafe/cost_krw/travel_min/visit_min/step_free/outdoor의 {value,observed_at,evidence_id}입니다. oracle 전용 자료는 모델 입력에서 재귀 제거합니다.

fixtures.py: `generate(output_dir)`는 새 디렉터리에 dev.jsonl/eval.jsonl/manifest.json을 생성하고 덮어쓰기를 거부합니다. dev24개, eval48개를 기본으로 하며 후보16·64·256개 규모 문제도 각각 포함합니다. `prepare_case(case)`는 기존 순수 개발 contract.prepare에 필요한 변환만 하여 상태를 반환합니다. `public_case(case,pool_ids=None)`는 사실과 고객 의미만 포함하며 oracle·정답 점수·순위를 포함하지 않습니다. `rule_rank(case)`는 별도 키워드 기준으로 feasible ID를 반환합니다.

metrics.py: `evaluate(case,ranking)`는 상태·출력 개수·중복·필수 제약·동점 허용 top1/nDCG@3/recall@3/regret를 계산합니다. 후보 없는 경우 유효한 상태 응답과 순위 정확도를 분리합니다. `expected_ranking(case)`와 `gold_groups(case)`는 정답 계산 전용입니다. 필요시 인터페이스 변경을 먼저 루트에 알립니다.

비교: 규칙; Jev API(유료) Choice 직접 1위 선택; Jev API(유료) Score 의미 등급+코드 순위; nano/Luna none·low 통제; 개선 선별+Luna. Choice 확률은 순위 효용이 아니므로 Choice 1위와 Score 상위3을 분리합니다. Score는0~4의 명시적 취향 적합 등급으로 질문합니다. 설명은 근거 ID와 원문 인용의 기계적 일치를 확인하고 의미 사실성 사람 검수는 미수행으로 표시합니다.

## 공유 비용 보호 인터페이스

`Budget(path,cap_usd,max_calls,baseline_usd=0.0)`는 SQLite 장부를 생성합니다. `reserve(lane,upper_usd,metadata=None)` -> call_id 문자열, `finish(call_id,actual_usd=None,usage_known=False)` -> 기록비용. `snapshot()` -> reserved_calls,finished_calls,known_usd,unknown_reserved_usd,committed_usd,cap_usd,baseline_usd,cumulative_usd. 예약·완료는 BEGIN IMMEDIATE 트랜잭션으로 보호하며 식별자는 UUID. 사용량 누락·프로세스 종료는 예약액을 계속 비용으로 잡습니다. 예상액 초과 실제 사용량은 실제액을 기록하고 차기 예약을 잠급니다. 재시작과 다중 프로세스 경쟁·중복 완료·경계·비정상 종료를 시험합니다. 별도 `run_lock()` context manager는 SQLite 장부와 연동된 프로세스 독점 실행 잠금이며 충돌 시 즉시 오류를 냅니다. 잠금 보유 프로세스 종료 시 운영체제가 해제합니다. 로그·metadata에 키 값을 저장하지 않습니다.
