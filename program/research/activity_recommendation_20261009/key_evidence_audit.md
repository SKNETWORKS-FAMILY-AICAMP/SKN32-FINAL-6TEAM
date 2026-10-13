# 추천 연구 핵심 근거 심화 검수

**핵심 설계 방향은 본문 근거로 유지되지만, 순서 편향의 원인 분리·후보 회수의 평가 범위·전용 추천 모델의 서빙 방식을 더 좁혀 적었습니다.** 검수 경계는 2026-10-09 KST이며 추가 유료 호출은 하지 않았습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 핵심 자료 본문 대조 | 완료 | 7/7 = 100% |
| 날짜·확인 범위 보완 | 완료 | 7/7 = 100% |
| 보고서 한계 보완 | 완료 | 4/4 = 100% |

아래의 ‘확인’은 작성자의 실험을 독립 재현했다는 뜻이 아닙니다. 해당 주장과 방법이 원문에 적혀 있는지 대조했습니다. 각 기관의 성과 수치를 triPilot의 예상 성능으로 옮기지 않습니다.

| 자료 | 확인한 본문 | 유지할 주장 | 제한하거나 바로잡은 부분 |
|---|---|---|---|
| [2026 위치 편향](https://arxiv.org/html/2608.03091v1) | §3 지표, §4 실험, §5 결과, §6 결론 | 관련도와 순열 일관성은 다른 축 | 20개 순열과 결정적 순위 추출을 사용. API 반복의 생성 변동과 순열 효과를 분리해야 함 |
| [COMPASS v2](https://arxiv.org/html/2510.07043v2) | §3.1·§3.4 정답 계산, §4.1 결과, §5.2 분석 | 실행 가능성과 효용 최적화의 분리 | 초판 2025-10-08, 개정 2026-04-16. Apple 소개 시점 2025년 12월을 최초 발표일로 쓰지 않음 |
| [TREK v2](https://arxiv.org/html/2607.26977v2) | §3.1·§3.5, §4.1–4.4, Appendix A.2·F | 달성 가능한 정답과 결정적 조건 검증 | 사람 검수는 정답 계획의 현실성·실행 가능성. 생성된 모델 답의 사람 만족·실플랫폼 전이는 별도 과제 |
| [LinkedIn follows](https://www.linkedin.com/blog/engineering/ai/rebuilding-linkedins-follows-recommendations-with-llm-based-semantic-retrieval-and-ranking) | Semantic Encoding, Supervised Fine-tuning, EBR, L2 Integration | 같은 취향 임베딩을 회수와 순위에 재사용 | Follow 자료로 학습한 모델과 DNN 순위. 추가 학습 없는 대화 API의 성능 증거가 아님 |
| [LinkedIn 검색](https://www.linkedin.com/blog/engineering/search/reimagining-linkedins-search-stack) | Infrastructure, Golden Grades, Judge Training, Retrieval, SLM Ranking | 회수 뒤 작은 순위 모델, 점수 캐시, 평가 깊이 제어 | 사람 정책 정답과 일치하도록 채점 모델을 맞춤. 여행 취향 정답이나 우리 모델 보정 상태를 대신하지 않음 |
| [Spotify NEO·GLIDE](https://research.atspotify.com/2026/8/from-models-to-products-llms-for-recommendation-at-spotify-scale) | Catalog Grounding, NEO Training, GLIDE, Deploying, Results | 실제 항목 ID 연결, 장단기 취향, 생성 회수와 기존 순위 결합 | 도메인 학습과 Semantic ID 매핑을 사용. 회수 지표만으로 취향 정합을 증명하지 않음. 연결 논문은 저자 초록만 확인 |
| [Netflix GenRec v2](https://arxiv.org/html/2608.10257v2) | §4.5 점수 출력부, §4.6 학습 목표, §4.7 서빙, §5.1–5.2, §7 | 입력 압축·추천 후학습·목록 점수 출력으로 비용 제어 | prefill-only는 전용 점수 출력부의 방식. A/B 대상은 batch-compute surfaces. 범용 API 옵션·실시간 여행 지연 증거로 확대하지 않음 |

이번 보고서에 추가한 한계는 네 가지입니다. 고정 후보 시험은 회수 품질을 재지 못합니다. 순서를 바꾸는 API 반복은 순서 민감도와 생성 변동을 함께 측정합니다. 합성 정답의 객관성은 실제 고객 만족을 보증하지 않습니다. 전용 추천 모델의 실행 방식은 범용 API에서 그대로 사용할 수 있는 설정이 아닙니다.

출처 수는 그대로 **43개(논문 17·공식 문서 15·직접 기술 블로그 11)**입니다. 이번 검수에서 자료 수를 늘리지 않았습니다. 문헌 목록의 `read_depth`를 실제 대조한 절과 범위로 구체화했습니다. 초록만 확인한 다른 논문은 그대로 초록 확인으로 남겨 세부 실험을 확인한 것처럼 표시하지 않았습니다.

수정 전 판은 [_backup/2026-10-09_claim_audit/](./_backup/2026-10-09_claim_audit/)에 보존했습니다. 자료 목록 재생성은 생성기가 기존 파일을 백업한 뒤 수행합니다.
