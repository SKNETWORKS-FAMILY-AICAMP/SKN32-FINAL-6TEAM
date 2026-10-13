# Noul 특성 판정과 코드 순위 추가 실행기

Jev API(유료)에 후보가 특정 성격을 제공하는지만 묻고 최종 추천 점수는 코드가 계산합니다. **단위 시험은 무료, 실제 실행은 유료**이며 기존 재시험의 신규$0.50·600호출 상한을 공유합니다. 현재 코드 시험43/43을 통과했고, 이 추가 방법의 실제 모델 호출은 아직 수행하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 비용 없는 단위 시험 | 통과 | 43/43 = 100% |
| 추가 평가·안정성 실행 | 미실행 | 0/64 관측 = 0% |
| 사람 검수 | 미수행 | 0건 |

이 방법은 본 eval-v1 진행 중 추가한 탐색입니다. [고정한 추가 기준](C:/Users/playdata2/Documents/final_workspace/program/research/activity_recommendation_20261009/retest-feature-addon-20261010.md)을 먼저 읽습니다. 본 평가 시작 전 사전등록이나 본 모델 설정 선택의 일부라고 부르지 않습니다.

## 비용 없는 재현

작업 폴더는 `C:\Users\playdata2\Documents\final_workspace`입니다. 기존 Python과 pytest를 사용합니다. 아래 명령은 실제 API나 키를 읽지 않습니다. pytest 임시 경로는 아직 없는 새 이름을 사용합니다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider --tb=short --basetemp .tmp/activity-retest-20261010/features-unit-root-v1 program/scripts/activity_recommendation_features_20261010/tests/test_runner.py
```

완료하면 `43 passed`가 표시됩니다. 모듈 작성자의 재실행은43개 통과·종료 코드0입니다. pytest가 끝난 뒤 환경의 `pyreadline3` 콘솔 핸들 종료 경고가 발생했으며 시험 실패는 아니었습니다.

시험은 독립 특성 질문, 숨겨진 정답 차단,0.5 임계값, 기피 감점·제한·반올림, 가중치와 이동 변화, ID 변경·순서 변경,64질문 묶음, 실패 후 묶음 중단, 이미 쓴 비용 보존, 예산 거절과0·1후보 우회를 검사합니다. 실제 평가48문제에 완벽한 특성 판정 대역을 주어 계산 연결도 검사합니다. 이 대역의 정답 일치는 모델 성능이 아닙니다.

## 실제 실행

실제 호출은 루트 담당자가 기존 지정 키와 환경에서 실행합니다. 실행기는 동결된 `Providers.call`, `Budget`, `prepare_case`, `public_case`, `root_metrics`, `variant`를 재사용합니다. 기존 동결 파일은 수정하지 않습니다.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python program/scripts/activity_recommendation_features_20261010/runner.py --stage eval --run-id features-eval-v1
python program/scripts/activity_recommendation_features_20261010/runner.py --stage stability --run-id features-stability-v1
```

평가는48관측·최대37호출, 안정성은16관측·최대16호출입니다. 합계53호출·1892질문이며 실패·예산 중단 시 줄어듭니다. 두 단계는 같은 SQLite 비용 장부와 실행 잠금을 공유하므로 동시에 실행하지 않습니다. 기존 활동 추천 재시험이 실행 중이면 즉시 잠금 오류를 냅니다.

결과는 기존 재시험 자료의 [runs 폴더](C:/Users/playdata2/Documents/final_workspace/datasets/travel/activity_recommendation_bench_20261009/retest-20261010/runs/) 아래 각 `--run-id` 이름으로 저장합니다. 이름은 `features-`로 시작하는 단일 폴더명이어야 합니다. 이미 있으면 거부합니다. 완료하면 해당 폴더에 `metadata.json`, `schedule.json`, `results.jsonl`, `finish.json`, 실제 `responses/`가 생깁니다.

예산이 부족하면 새로 올리지 않고 중단합니다. `finish.json`의 `completed/planned`, `stop`, 공유 장부 스냅샷을 먼저 확인합니다. 종료됐다는 사실만으로 모든 예정 문제를 완료한 것은 아닙니다.

## 동작과 기록

`rank_features(public, provider, model)`는 공개 입력과 기존 호출 객체를 받습니다. 모델에는 trait와 해당 후보 description만 전달합니다. `state={}`이며 후보 ID·이름·다른 후보·고객 중요도·거리·정답은 특성 질문에 넣지 않습니다. 같은 trait가 여러 선호 항목에 있어도 질문은 후보당 한 번만 합니다.

Noul≥0.5는true, 미만은false로 바꾸고 코드가 선호 중요도 합−기피 벌점 합을0~1로 제한합니다. 이후 `floor(x*4+.5)/4`, 이동 점수, 분류 유사도, 기존 가중합을 적용합니다. 확률0.51과0.99를 서로 다른 취향 강도로 사용하지 않습니다.

반환 값에는 순위, 실제 모델, 특성별 확률·판정, 코드 점수, 모든 서브콜·사용량·비용·지연·요청 ID가 있습니다. 파싱·타임아웃 실패는 해당 문제의 남은 묶음을 중단하고 비용을 보존합니다. 중간 예약 거절도 앞선 비용을 보존합니다. 자동 Luna 대체나 재시도는 없습니다.

0후보·해결되지 않은 사실·잘못된 입력은 실행기의 상태 관문에서 처리합니다.1후보는 코드가 골라 유료 요청하지 않습니다. 이 코드 우회를 실제 모델 요청의 정확도와 분리해 집계해야 합니다. 이유 문장이나 근거 인용을 새로 생성하지 않으며 `semantic_factuality_verified=false`, 사람 검수0건을 유지합니다.

기존 Choice 반올림 수정 재시험은 별도입니다. 이 추가 결과만으로 Score·Noul의 최적성, 실제 고객 만족, 운영 앱 채택을 확정하지 않습니다. 실제 장소 검색이나 정보원의 진실성·최신성을 검증한 시험도 아닙니다.

수정 전 원본은 [구현 보완 전 백업](C:/Users/playdata2/Documents/final_workspace/program/scripts/activity_recommendation_features_20261010/_backup/2026-10-10_pre_integration/)에 있습니다. 기존 최상위 재시험 파일과 원래 결과는 변경하지 않았습니다.
