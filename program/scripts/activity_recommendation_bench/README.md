# 서울 활동 대체 추천 비교 실행기

> **2026-10-10 재검토:** 이 실행기는 기존 유료 예비 연구의 보존본입니다. 기존24문제의 ID·정답 상관관계 때문에 추천 품질 채택 근거로 사용하지 않습니다. 누적380/380회로 호출 슬롯은0개이며 금액 잔여분만 보고 새 유료 실행을 하지 않습니다. 여러 프로세스의 비용 예약을 보호하지 못하므로 차기 유료 실행에 그대로 재사용하지 않습니다. [정정과 후속 계획](../../research/activity_recommendation_20261009/followup-plan-20261010.md), [비용 없는 개발 모듈](../activity_recommendation_followup/README.md)을 확인하십시오. 아래 명령은 기존 실행 방법을 기록한 것입니다.


필수 조건을 코드로 확인한 뒤 취향 추천의 품질·비용·지연을 비교하는 독립 연구 도구입니다. 운영 앱을 가져오거나 수정하지 않습니다.

## 재현 조건

- 자료: `datasets/travel/activity_recommendation_bench_20261009/raw/scenarios-v2.jsonl`의 24개 문제, 각각 14개 후보 중 필수 조건 통과 9개.
- 예비 자료 2개는 본 점수에서 제외합니다. 본 비교는 3회 반복이며 첫 두 회는 동일 후보 순서, 셋째는 순서 변형입니다.
- 규칙, GPT-5.4 nano 직접, GPT-6 Luna 직접, Jev API(유료)+코드, Jev API(유료) 선별+nano, Jev API(유료) 선별+Luna를 비교합니다.
- Jev API(유료)는 후보별 성격 제공 여부를 Noul로 평가하고 가중합은 코드가 계산합니다. 이번 추가 학습·보정은 수행하지 않습니다. Jev 계열 Winnow 모델 실행 결과가 아닙니다.
- 고객·후보 속성·가중치·출력 계약을 공통으로 고정하며 정답 전용 속성은 입력에서 재귀 제거합니다.
- OpenAI API용으로 지정된 환경변수만 읽고 개인용 키로 대체하지 않습니다. 키는 출력하지 않습니다.
- 전체 시험 비용 상한 US$0.50, 최대 유료 요청 380회입니다. 예비·본 비교·출력 한도 진단이 같은 비용 기록을 공유합니다. 기존 기록을 지우면 지출 누적 보호가 사라지므로 지우지 않습니다.
- 단가는 [OpenAI 가격표](https://developers.openai.com/api/docs/pricing)와 [TypeSafe 공식 가격 소개](https://typesafe.ai/blog/introducing-system-one-models-and-jev)에서 2026-10-09 확인했습니다. API 사용량으로 환산한 예상 과금이며 결제 명세서 값은 아닙니다.

## 실행

다음 명령은 작업 폴더 루트에서 실행합니다. 새 유료 시험은 남은 비용 범위에서만 가능합니다. 같은 실행 이름을 다시 쓰면 원본 덮어쓰기를 거부합니다.

```powershell
python program/scripts/activity_recommendation_bench/review_fixtures.py
python -m pytest -q -p no:cacheprovider --basetemp .tmp/activity-recommendation-tests-new program/scripts/activity_recommendation_bench/tests
python program/scripts/activity_recommendation_bench/bench.py --run-id new-smoke-name --smoke
python program/scripts/activity_recommendation_bench/bench.py --run-id new-main-name
python program/scripts/activity_recommendation_bench/analyze.py --run-id new-main-name --output-dir datasets/travel/activity_recommendation_bench_20261009/analysis/new-main-name
```

분석 명령은 유료 요청을 보내지 않습니다. 사전 검수 파일이 이미 있으면 원본 검수 기록을 보존하도록 먼저 백업해야 합니다. pytest의 임시 폴더도 매번 새 이름을 쓰십시오.

## 해석

정답은 작성된 성격 표기와 사전 가중합으로 만든 합성 정답입니다. 사람의 고객 만족을 재는 정답표가 아닙니다. 동일 설명 틀을 공유하므로 24개를 독립적인 실제 고객 표본이라고 주장하지 않습니다. 후보 검색, 여행 전체 균형, 실제 운영시간 조회, 추천 이유의 사실성은 이번 자동 채점에 포함하지 않습니다.

[분석 사전 기준](analysis-plan.md)과 [출력 한도 추가 진단](diagnostic-plan.md)을 함께 읽으십시오. 출력 한도 진단의 5개 문제·1회 결과는 본 비교와 합치지 않습니다.

모델 응답 대역 단위 시험과 실제 API 비교는 별도입니다. 이 도구는 mock 서버를 실행하지 않으며 운영 앱의 화면·DB·배포 경로도 검증하지 않습니다.
