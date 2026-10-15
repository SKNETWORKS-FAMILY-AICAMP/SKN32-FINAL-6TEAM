# ID 전용 선택 진단 실행

인용 생성 없이 후보 ID만 고르는 진단입니다. 실제 CLI 실행은 유료이며 기존 재시험의 공유 US$0.50/600호출 안에서만 진행합니다. 추가 예산은 없습니다. Choice 예상29회, Rank20회입니다. 완료 시간은 미측정이며 실제 사람 검수는0건입니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 진단 단계 준비 | 완료 | 2/2 = 100% |
| 실제 API 진단 | 미실시 | 0/49 = 0% |

먼저 기존 본 평가가 종료되어 실행 잠금이 해제되어야 합니다. Choice 응답의 반올림 검증은 루트가 기존 평가 종료 후 수정합니다. 이 실행기는 그 검증을 그대로 사용합니다. 기존 원본24/48개와 진행 중인 실험 코드는 변경하지 않습니다.

## 비용 없는 계획 확인

작업 폴더에서 실행합니다. 모델 호출과 환경 파일 읽기는0입니다. 대상 문제 ID와 예상 호출 수가 출력됩니다.

```powershell
python -B program/scripts/activity_recommendation_id_diagnostic_20261010/runner.py --stage choice --plan-only
python -B program/scripts/activity_recommendation_id_diagnostic_20261010/runner.py --stage rank --plan-only
```

Choice는48행·예상29호출, Rank는10문제×2모델=20행·20호출이 나와야 합니다. Rank 대상은 방문 가능 후보2개 이상 문제를 case_id 순으로 고른 첫10개이며, 결과를 보고 고르지 않습니다.

## 실제 실행

아래 두 명령은 루트만 실제 호출에 사용합니다. 같은 비용 장부의 실행 잠금을 사용하므로 본 실험이 아직 실행 중이면 거부합니다. 지정 출력 폴더가 이미 있어도 거부합니다. 새 실행 ID를 임의로 만들어 같은 문제를 자동 재시도하지 않습니다.

```powershell
python -B program/scripts/activity_recommendation_id_diagnostic_20261010/runner.py --stage choice --run-id id-choice-eval-v1
python -B program/scripts/activity_recommendation_id_diagnostic_20261010/runner.py --stage rank --run-id id-rank-diag-v1
```

자료 폴더의 `runs/id-choice-eval-v1/`와 `runs/id-rank-diag-v1/`에 새 결과가 생깁니다. `metadata.json`은 동결 해시·사전 대상, `schedule.json`은 순서, `results.jsonl`은 원래 응답 정보·지표, `responses/`는 호출별 원시 응답, `finish.json`은 완료 수·공유 지출·해시 보존 여부입니다. 지출·호출 한도에 닿으면 부분 결과를 남기고 중단합니다.

Rank는 두 모델 모두 none·최대512출력토큰·동일 ranking-only 스키마이며 문제마다 모델 순서를 교대합니다. enum·개수는 요청 스키마와 parser에서, 중복·추가 필드는 parser에서 엄격하게 검사합니다. 인용·이유 생성은 없습니다. 실패를 고치거나 재호출하지 않습니다.

## 결과 해석

Choice는 상위1 지표, Rank는 상위3 지표입니다. 코드 상태·단일 후보의 무호출 결과를 모델 우열로 사용하지 않습니다. 동점은 기존 root_metrics 계약을 따릅니다. 계층 Choice는 `raw_call_records`가 참조하는 모든 응답 사용량을 확인하며 마지막 응답만 전체 비용으로 세지 않습니다.

인용까지 요구한 본 Top3는 전체 경로 결과이고, 이 ID 전용10문제는 같은 선택 계약의 진단입니다. 새 독립 표본·최종 미사용 평가가 아니며 기존 표본수에 더하지 않습니다. 실제 고객 만족, 근거 회수, 사람 의미 검수는 이번 진단이 확인하지 않습니다.

오류 `existing_shared_ledger_required`는 공유 장부가 없다는 뜻입니다. 새 장부를 만들지 말고 기존 재시험 자료 위치를 확인합니다. `run_locked`는 다른 실행이 진행 중이라는 뜻이므로 종료 후 다시 시작합니다. `budget_stop` 또는 `insufficient_shared_call_slots`면 예산·호출 상한에 도달한 것이므로 추가 실행하지 않습니다.
