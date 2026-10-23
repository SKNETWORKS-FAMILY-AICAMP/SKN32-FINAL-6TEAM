# 활동 추천 개발 계약 검증

추천에 필요한 사실과 조건이 준비됐는지 확인하고, 없는 후보나 잘못된 근거를 정상 추천으로 처리하지 않는 개발 모듈입니다. **유료 호출 0회, 사람 판정 0건**입니다. 이미 정해진 합성 취향·유사도 숫자로 계산하는 코드이며 의미 이해 모델의 성능 시험은 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 계약 단위 시험 | 통과 | 72/72 = 100% |
| 개발 경계·규모 문제 | 통과 | 8/8 = 100% |
| 후보 규모별 코드 실행 | 완료 | 33/33 = 100% |
| 사람 판정 | 미수행 | 분모 미정 |

## 재현 명령

작업 폴더는 `C:\Users\playdata2\Documents\final_workspace`입니다. Python과 pytest가 준비된 환경에서 실행합니다. 모듈 자체는 Python 표준 라이브러리만 사용합니다. 계정·키·외부 연결을 준비할 필요가 없습니다. 작은 단위 시험과 개발 실행은 각각 수 초 안팎에 끝나지만 PC 상태에 따라 달라집니다.

루트 검수용 새 결과 폴더를 사용합니다. 이 경로가 이미 있으면 마지막 이름을 새 이름으로 바꿉니다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python program/scripts/activity_recommendation_followup/dev_suite.py --output-dir datasets/travel/activity_recommendation_bench_20261009/followup-20261010/dev-root-v2 --timing-repeats 11
```

완료하면 `passed_cases: 8`, `development_cases: 8`, `human_review_count: 0`, `paid_api_calls: 0`이 표시됩니다. 지정한 폴더에 `fixtures.jsonl`, `outcomes.json`, `timings.json`, `summary.json`이 새로 생깁니다. 이미 있는 폴더는 덮어쓰지 않습니다.

단위 시험은 작업 폴더 안의 **새 임시 경로**를 지정합니다. 아래 임시 경로는 실행 전에 없는 경로를 고르세요. pytest의 임시 폴더 정리 동작을 기존 결과 경로에 적용하지 않습니다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider --tb=line --basetemp datasets/travel/activity_recommendation_bench_20261009/followup-20261010/unit-temp-root-v2 program/scripts/activity_recommendation_followup/tests/test_contract.py
```

완료하면 `72 passed`가 표시됩니다. 모듈 작성자의 실행 로그는 [unit-test-20261010-v3.log](tests/unit-test-20261010-v3.log)입니다. 실행 환경의 `pyreadline3` 종료 과정에서 표시되는 Windows 콘솔 핸들 오류가 기록됐지만 pytest 본체는 종료 코드 0과 72개 통과를 반환했습니다.

## 입력과 함수

`prepare(payload)`는 Python 사전 하나를 받습니다. JSON으로 표현 가능한 값만 사용하는 계약입니다.

| 입력 | 의미와 조건 |
|---|---|
| `as_of` | 최신성 판단 기준. 시간대가 있는 ISO 시각 |
| `max_age_seconds` | 허용된 사실의 나이. 0보다 큰 유한한 숫자 |
| `customer` | 비용·이동 포함 시간 상한, 무단차 필수, 비, 야외 허용 |
| `weights` | 취향·이동·유사도 중요도. 각 0~1, 합계 1 |
| `candidates` | 고유한 불투명 ID, 설명, 분류, 합성 취향·유사도 점수, 사실 목록 |
| 각 사실 | `value`, `observed_at`, `evidence_id` |

사실은 영업 여부·위험·비용·이동시간·체류시간·무단차 여부·야외 여부를 각각 보관합니다. 숫자는 음수·NaN·무한대·bool·표현 범위를 넘는 큰 정수를 거부합니다. 알 수 없는 필드와 중복 후보 ID도 거부합니다.

입력 예시는 생성 결과의 `fixtures.jsonl`에 있습니다. 개발 자료의 후보 ID는 별도 난수 시드에서 만든 96비트 값이며, 속성과 점수를 만드는 난수 시드와 분리했습니다. 두 시드와 전체 자료 해시를 함께 기록합니다.

## 반환 상태

| 상태 | 의미 | 요청할 추천 수 |
|---|---|---:|
| `ready` | 사실이 준비됐고 방문 가능한 후보가 있음 | 후보 수와 3 중 작은 값 |
| `no_feasible_candidates` | 사실은 준비됐으나 필수 조건을 통과한 후보가 없음 | 0 |
| `facts_unresolved` | 사실 값·시각·근거 ID 누락, 오래된 값, 미래 시각이 있음 | 0 |
| `invalid_input` | 구조·형식·수치·ID 계약 위반 | 0 |

한 후보에라도 해결되지 않은 필수 사실이 있으면 전체 요청을 `facts_unresolved`로 반환합니다. 일부 후보의 정보만 보고 정상 추천으로 바꾸는 대체 처리를 하지 않습니다. 이 상태 정의는 연구 모듈 안의 계약이며 운영 앱의 고객 안내 정책을 바꾸지 않습니다.

방문 가능 여부는 영업·위험·예산·이동+체류 시간·무단차·비와 야외 허용 조건으로 계산합니다. 취향은 점수에만 반영하며 필수 제약과 구분합니다. 최종 합성 점수는 다음과 같습니다.

```text
taste_weight * taste
+ travel_weight * max(0, 1 - travel_min / 60)
+ similarity_weight * similarity
```

`gold_score_groups`는 같은 점수의 후보들을 묶습니다. 동점인 후보를 여러 방식으로 정렬해도 정답으로 인정합니다. 후보 ID의 문자열 순서는 표시 순서만 정하며 더 좋은 후보의 근거가 아닙니다.

## 출력 검증

`validate_output(prepared, response)`는 추천 ID 목록 `ranking`과 후보별 설명 `reasons`를 검사합니다. 설명에는 `candidate_id`, 하나 이상의 `evidence_ids`, 비어 있지 않은 `text`가 필요합니다.

- 후보 ID가 실제 가능한 후보인지, 중복이 없는지, 정확히 요청된 수인지 검사합니다.
- 설명마다 해당 후보에 등록된 근거 ID가 있는지 검사합니다. 다른 후보의 근거를 가져오면 거부합니다.
- 계약 형식이 맞는지와 합성 정답 순위가 맞는지는 `valid`, `ranking_matches_gold`로 따로 반환합니다.
- 근거 ID가 존재해도 설명문이 사실인지까지 검증한 것은 아닙니다. `semantic_factuality_verified`는 항상 false, `human_review_count`는 항상 0입니다.

## 실행한 검증과 측정 범위

72개 단위 시험은 후보 0·1·2개, 신선도 경계, 오래됨·미래·누락, 필수 조건별 제외, 수치·구조 오류, 출력 ID·근거 오류, 동점 복수 정답, 후보 순열, 전단사 ID 변경, 이동시간 증가·예산 축소·중요도 반전의 변화 관계를 포함합니다. 추가한 회귀 시험은 실제 저장 파일의 바이트 해시와 결과에 기록된 해시가 일치하는지 확인합니다.

별도 개발 실행은 후보 수 16·64·256의 세 문제와 누락·오래됨·미래·음수·가능 후보 없음의 다섯 문제로 구성했습니다. 규모별 준비·필터·정렬·출력 검증 코드를 한 번 준비 실행하고 각각 11회 측정했습니다.

| 후보 수 | 반복 | 코드 시간 p50 | 코드 시간 p95 | 범위 |
|---|---:|---:|---:|---|
| 16 | 11회 | 0.4075ms | 0.4413ms | 준비·필터·정렬·ID·근거 검사 |
| 64 | 11회 | 1.7018ms | 2.2538ms | 동일 |
| 256 | 11회 | 6.4891ms | 7.9237ms | 동일 |

위 값은 이 PC에서 새 `dev-agent-v2` 실행으로 측정한 코드 연산 시간입니다. 원시 반복 값·최솟값·최댓값은 결과의 `timings.json`에 있습니다. 이전 실행과 PC 상태를 고정한 교대 비교가 아니므로 실행 간 속도 개선으로 해석하지 않습니다. 실제 장소 검색, 모델 응답, 네트워크와 서비스 전체 지연을 측정하지 않았습니다.

## 보존과 남은 검증

모듈 작성자의 현재 결과는 [dev-agent-v2](../../../datasets/travel/activity_recommendation_bench_20261009/followup-20261010/dev-agent-v2/)에 있습니다. 이전 [dev-agent-v1](../../../datasets/travel/activity_recommendation_bench_20261009/followup-20261010/dev-agent-v1/)과 루트 검수자의 `dev-root-v1` 출력 파일 8개는 수정하지 않고 실제 바이트 해시로 보존을 확인했습니다.

**v1 해시의 의미에는 오류가 있었습니다.** v1의 `fixture_sha256`는 저장 직전 UTF-8·LF 문자열의 해시였지만 Windows가 파일을 저장하며 줄바꿈을 CRLF로 바꿨습니다. 따라서 v1 기록 값을 실제 파일 바이트 해시로 사용할 수 없습니다. 이전 결과를 고쳐 쓰지 않고 이 설명으로 구분합니다.

v2는 `fixtures.jsonl`을 UTF-8·LF 바이트로 직접 저장합니다. `fixture_sha256`는 실제 저장 바이트의 SHA-256이며 `fixture_sha256_scope`에 그 범위를 기록합니다. v2 자료의 실제 바이트 해시와 기록 값은 `9da1a5343eadd999a9c309a48dd4d0e48f27fba10fb1a36cbed3547fc0f24e47`로 일치합니다.

해시 수정 직전 생성기·README·단위 시험은 [_backup/2026-10-10_fixture_byte_hash](../activity_recommendation_followup/_backup/2026-10-10_fixture_byte_hash/)에 복사했습니다. 큰 정수 오류 수정 직전 원본도 [_backup/2026-10-10_numeric_overflow](../activity_recommendation_followup/_backup/2026-10-10_numeric_overflow/)에 보존했습니다.

사람 정답 검수, 별도로 보류한 고객 문제에서의 모델 비교, 모델별 설정, 캐시 조건, 큰 후보 목록에서의 모델 순위 품질, 설명 근거의 의미 사실성, 실제 장소 자료의 신뢰도·최신성은 검증하지 않았습니다. 개발 계약 통과만으로 실제 서비스 채택을 결정할 수 없습니다.
