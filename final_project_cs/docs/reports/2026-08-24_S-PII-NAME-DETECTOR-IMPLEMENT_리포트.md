# S-PII-NAME-DETECTOR-IMPLEMENT 구현 리포트

## 결론

검증된 성씨 사전과 호칭·자기소개 문맥을 결합한 안 C를 구현하고 프로덕션 REV에 반영했다. 기존 이메일·전화·카드번호 패턴은 수정하지 않았다.

## 사전 근거와 탐지 규칙

- 통계청 2015 인구주택총조사 성씨 표의 상위 50개 성씨를 사용했다. 상위 20개가 인구 94.2%를 차지하는 공식 표를 근거로, 관찰된 NIKL 첫 음절 518개를 전부 쓰지 않고 상위 50개로 제한했다. [통계청 공식 성씨 표](https://sri.kostat.go.kr/boardDownload.es?bid=203&list_no=356061&seq=8)
- 성씨만 있으면 검출하지 않는다.
- 이름 뒤 `님`·`씨`·`고객님` 또는 `성함은`·`이름은`·`저는`·`제가` 뒤의 `입니다`·`이에요`·`예요` 문맥에서만 검출한다.

## 동일 표본 측정

측정 스크립트에 새 방법을 추가했으며 새 스크립트는 만들지 않았다. seed `20260824`, M/S/N 각각 500개, 기존 span 기반 recall·오탐 정의를 그대로 사용했다.

| 방법 | M recall / 오탐 | S recall / 오탐 | N recall / 오탐 |
|---|---:|---:|---:|
| 안 A | 59.8% / 684 | 60.0% / 717 | 73.4% / 5,161 |
| 안 B | 2.2% / 8 | 0.4% / 5 | 0.0% / 8 |
| 안 C | 2.4% / 2 | 3.4% / 5 | 0.4% / 2 |

안 C의 오탐은 안 A보다 각각 342배, 143.4배, 2,580.5배 적고 모두 두 자릿수 이하다. recall도 세 도메인 모두 안 B보다 높아 판정 기준을 충족했다. 측정 스크립트 2회 실행 결과는 완전히 동일했다.

## 변경 파일

- `datasets/voc/nikl_ne_2022/processed/measure_pii_recall.py`: 안 C 추가
- `datasets/voc/nikl_ne_2022/processed/pii_name_gap_measurement.md`: 근거·결과·판정·검증 결과 갱신
- `app/modules/customer_ops/response_review_policy.py`: `detect_person_name_pii()` 및 문맥 패턴 추가
- `app/modules/customer_ops/response_review.py`: 기존 결정 단계에서 이름 탐지 호출
- `tests/unit/teams/test_response_review.py`: 양성/문맥 없는 음성 테스트 추가

## 테스트

지정 단위 테스트:

```text
8 passed, 1 warning in 3.44s
```

요청한 전체 명령 `python -m pytest -q -m "not live"`:

```text
3 failed, 345 passed, 3 deselected, 2 warnings, 11 errors in 139.52s (0:02:19)
```

기준으로 제시된 354 passed와 달리 전체 실행은 환경 제약으로 완료되지 않았다. 실패 3건은 기존 RAG 테스트의 OpenAI API 네트워크 차단, 에러 11건은 기존 e2e/fixture 단계의 임시 디렉터리 권한 거부였다. 새 이름 탐지 단위 테스트와 기존 response review 단위 테스트는 통과했다.
