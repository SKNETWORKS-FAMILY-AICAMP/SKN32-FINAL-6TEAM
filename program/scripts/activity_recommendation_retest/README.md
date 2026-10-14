# Activity 개선 유료 재시험

정해진 서울 활동 후보에서 한 곳을 고르는 작업과 상위3개를 정렬하는 작업을 구분합니다. 운영 앱·DB·고객 추천은 변경하지 않습니다. 원본은 AI 합성이고 실제 사람 검수는0건입니다.

## 실행 전 기준

[사전 기준](../../research/activity_recommendation_20261009/retest-preregistered-20261010.md)과 [작업 계약](../../research/activity_recommendation_20261009/retest-contract-20261010.md)을 먼저 읽습니다. 새 시험은 기존$0.349834632와 별도로 최대$0.50·600호출입니다. 모든 단계·실패·별도 특성판정 시험이 같은 SQLite 예산을 공유합니다. 자동 재시도는 없습니다. 실제 사용량이 없으면 예약 상한을 지출로 남깁니다. 청구 명세서를 조회한 확정액과 사용량×공개단가 추정은 다릅니다.

지정된 로컬 개발용 환경 파일의 cs 프로젝트 API용 OpenAI 키와 TypeSafe 키만 읽습니다. 키를 터미널이나 결과에 출력하지 않습니다. SDK2.44.0을 유지합니다.

## 무료 확인

백업 폴더의 옛 시험을 수집하지 않도록 현재 시험 파일을 명시합니다.

```powershell
python -m pytest -q -p no:cacheprovider --basetemp .tmp/activity-retest-check program/scripts/activity_recommendation_retest/tests/test_fixtures.py program/scripts/activity_recommendation_retest/tests/test_providers.py program/scripts/activity_recommendation_retest/tests/test_budget.py program/scripts/activity_recommendation_retest/tests/test_run.py
```

## 실제 유료 실행

이미 있는 실행 폴더 이름을 재사용하지 않습니다. 같은 장부를 사용하므로 새 폴더 이름이 비용 상한을 초기화하지 않습니다. 다음은 당시 최초 실행 명령이며 다시 실행하려면 **새 실행 이름**이 필요합니다. 중단된 실행도 덮어쓰지 않습니다.

```powershell
python program/scripts/activity_recommendation_retest/run.py --stage smoke --run-id smoke-v1
python program/scripts/activity_recommendation_retest/run.py --stage dev --run-id dev-v1
python program/scripts/activity_recommendation_retest/run.py --stage eval --run-id eval-v1 --dev-run dev-v1
python program/scripts/activity_recommendation_retest/run.py --stage stability --run-id stability-v1 --dev-run dev-v1
python program/scripts/activity_recommendation_retest/analyze.py --eval-run eval-v1 --stability-run stability-v1 --output-id final-v1
```

개발24문제에서 nano/Luna의 none/low 설정을 각각 선택하고 평가48문제에 고정합니다. 품질·비용의 주 비교는 실제로2개 이상 가능한 후보가 있는 문제만 사용합니다. 후보0개·사실 누락/오류·후보1개는 코드 처리이며 모델 이해 능력으로 세지 않습니다. 같은 입력8개와 ID·순서 변경8개는 독립 표본이 추가된 것이 아닙니다. 각 문제 안에서 모델 실행 순서를 고정 난수로 섞고 호출은 순차 실행합니다.

## 보완 이력

첫 실제 예비 시험의 Score 확률은 각 항목이 소수2자리로 표시됩니다. 점수와 표시 확률의 가중합을0.003 이내로 요구하던 검증식이 정상 응답을 거부했습니다. 표시 확률5개와 점수 각각의 반올림 상한으로 허용오차를 계산했습니다. 원래 Score 값은 바꾸지 않고 이론 상한보다 큰 불일치는 계속 실패시킵니다. 원본 예비 응답과 실패 비용은 보존합니다.

동점 경계의 낮은 후보를 여러 개 넣어 더 높은 필수 후보 누락까지 만회하던 회수율 계산도 고쳤습니다. 별도 채점기와 실제72문제의 정순·역순 및 한 곳 선택 결과를 대조하는 회귀 시험을 포함합니다.

변경 전 실행기·검증 코드 보존: [_backup](./_backup/). 실제 원본·응답·장부는 git 밖 [retest-20261010](../../../datasets/travel/activity_recommendation_bench_20261009/retest-20261010/)에 있습니다.
