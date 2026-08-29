# S-PII-NAME-GAP-MEASURE 리포트

## 결론

현재 REV `PII_PATTERNS`에는 사람 이름 정규식이 없으며, NIKL NE 2022의 실제 `PS_NAME` 표본 1,500건을 실행한 결과 M(메신저)·S(SNS)·N(뉴스) 모두 이름 recall 0.0%였다.

안 A(관찰 성씨 첫 음절 기반)는 M 59.8%, S 60.0%, N 73.4%로 recall을 개선했지만, 오탐 span이 각각 684, 717, 5,161건이었다. 안 B(님/씨 호칭 기반)는 오탐이 상대적으로 적었으나 M 2.2%, S 0.4%, N 0.0%로 실용적인 단독 탐지기가 되지 못했다.

따라서 이번 작업의 권고는 코드 즉시 반영이 아니다. 다음 검증에서는 안 A를 검토된 성씨 사전과 강한 호칭·직함 문맥으로 제한하고, 안 B는 보조 신호로만 결합하는 것이 적절하다.

## 측정 근거

- 원본 ZIP: `datasets/voc/nikl_ne_2022/raw/NIKL_NE_2022_CSV.zip`; 압축 해제 없이 `zipfile` 스트리밍 파싱
- 실제 사람 이름 라벨: `PS_NAME` 55,755건
- 보조 PS 라벨 관찰: `PS_CHARACTER` 1,743건, `PS_PET` 693건
- 표본: seed `20260824`, M/S/N 각 500건, 총 1,500건
- 비교 방법: 현재 패턴 3개, 안 A 성씨 후보 + 1~2음절, 안 B 호칭 앞 2~4음절
- 오탐 정의: 표본 문장 내 전체 PS_NAME gold span과 겹치지 않는 predicted span
- 형태소 분석기 확인: `konlpy=True`, `fugashi=True`; 새 패키지는 설치하지 않음

## 결과표

| 방법 | M recall | S recall | N recall | M 오탐 | S 오탐 | N 오탐 |
|---|---:|---:|---:|---:|---:|---:|
| 현재 | 0.0% | 0.0% | 0.0% | 0 | 0 | 2 |
| 안 A | 59.8% | 60.0% | 73.4% | 684 | 717 | 5,161 |
| 안 B | 2.2% | 0.4% | 0.0% | 8 | 5 | 8 |

고객 메시지에 가까운 M/S만 보면 A가 recall 측면에서 우세하지만, 안전 관련 즉시 escalate에 필요한 오탐 통제에는 부족하다. N은 뉴스 문장 구조가 달라 A의 오탐이 특히 커서 서비스 대표값으로 사용하지 않았다.

## 변경 범위와 재현성

변경한 것은 측정 스크립트와 문서뿐이다. `final_project_cs/app/modules/customer_ops/response_review_policy.py` 및 기타 REV 코드는 수정하지 않았다. 스크립트는 [measure_pii_recall.py](../../../../datasets/voc/nikl_ne_2022/processed/measure_pii_recall.py)이며, 동일 명령을 두 번 실행해 동일한 행 수·표본 수·recall·오탐 수치를 확인했다.

실행 명령:

```powershell
python datasets/voc/nikl_ne_2022/processed/measure_pii_recall.py
```

상세 측정 정의와 두 실행의 터미널 출력 전문은 [pii_name_gap_measurement.md](../../../datasets/voc/nikl_ne_2022/processed/pii_name_gap_measurement.md)에 기록했다.
