# 활동 추천 연구 출처 목록

확인 경계는 2026-10-09 KST입니다. 검증 출처 43개이며 유형별 개수는 {'official_docs': 15, 'paper': 17, 'first_party_blog': 11}입니다. 같은 논문의 판·프로젝트 소개는 한 자료로 셌습니다. 날짜가 표시되지 않은 공식 문서는 오늘 발표된 자료라는 뜻이 아닙니다.

| 자료 | 발표일 · 갱신일 | 확인 범위 | 우리 시험에 반영할 점 |
|---|---|---|---|
| [Recommendation systems overview](https://developers.google.com/machine-learning/recommendation/overview/types) | 발표일 미표시 · 갱신 2025-08-25 | 본문 | 규칙/회수와 고비용 재정렬을 분리한다 |
| [Retrieve and Re-Rank](https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) | 발표일 미표시 | 본문 | 다수 후보를 생성형 모델에 모두 보내는 방식의 대조군 |
| [Is ChatGPT Good at Search? Investigating Large Language Models as Re-Ranking Agents](https://arxiv.org/abs/2304.09542) | 2023-04-19 · 갱신 2024-12-28 | 저자 초록 | 후보 ID만 반환하고 새 장소를 지어내지 않도록 한다 |
| [Enhancing Reranking for Recommendation with LLMs through User Preference Retrieval](https://aclanthology.org/2025.coling-main.45/) | 2025-01 | 초록 및 PDF 본문 | 전체 대화와 정리된 취향 전달의 효과를 별도 시험한다 |
| [Beyond Utility: Evaluating LLM as Recommender](https://arxiv.org/abs/2411.00331) | 2024-11-01 · 갱신 2026-09-07 | v2 HTML 본문 | 순위 정확도 외 순서 민감도와 후보 유효성을 측정한다 |
| [Evaluating Position Bias in Large Language Model Recommendations](https://arxiv.org/abs/2508.02020) | 2025-08-04 | 저자 초록 | 같은 후보의 순열을 바꿔 순위를 비교한다 |
| [Position Bias Undermines Preference Consistency in Listwise LLM-Based Reranking](https://arxiv.org/abs/2608.03091) | 2026-08-04 | v1 HTML §3–§6: 지표·실험 조건·결과·결론 | nDCG 외 출력 안정성을 확인하되 순열 변화와 생성 변동을 구분한다 |
| [TravelPlanner: A Benchmark for Real-World Planning with Language Agents](https://arxiv.org/abs/2402.01622) | 2024-02-02 · 갱신 2024-10-23 | 저자 초록 | 단일 장소 추천과 전체 계획 생성의 평가 범위를 구별한다 |
| [ChinaTravel: An Open-Ended Travel Planning Benchmark with Compositional Constraint Validation for Language Agents](https://arxiv.org/abs/2412.13682) | 2024-12-18 · 갱신 2026-04-29 | v5 HTML 본문 | 합성 시험 뒤 실제 고객 표현의 의미 정합성을 확인한다 |
| [Flex-TravelPlanner: A Benchmark for Flexible Planning with Language Agents](https://arxiv.org/abs/2506.04649) | 2025-06-05 | HTML 본문 | 뒤늦게 추가한 낮은 중요도 때문에 필수 조건을 깨는지 시험한다 |
| [Beyond Itinerary Planning A Real-World Benchmark for Multi-Turn and Tool-Using Travel Tasks](https://arxiv.org/abs/2512.22673) | 2025-12-27 · 갱신 2026-04-21 | v3 HTML 본문 | 후보가 하나도 가능한 경우와 시간에 따라 달라진 자료를 별도 시험한다 |
| [COMPASS: Benchmarking Constrained Optimization in LLM Agents](https://arxiv.org/abs/2510.07043) | 2025-10-08 · 갱신 2026-04-16 | v2 HTML §3.1–§3.5·§4.1·§5.1–§5.2; Apple 소개와 대조 | 방문 가능성과 효용 최적화를 독립 측정; 고정 후보 재정렬만으로 전체 회수 품질을 주장하지 않는다 |
| [TREK: A Travel Reasoning and Evaluation Kit for LLM Agents in Complex Trip Planning](https://arxiv.org/abs/2607.26977) | 2026-07-29 · 갱신 2026-08-10 | v2 HTML §3.1–§3.6·§4.1–§4.4·Appendix A.2 및 F 한계 | 정답 가능성을 먼저 검증하고 실행 가능성과 비용을 독립 채점; 실제 고객 만족 증명으로 확대하지 않는다 |
| [FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance](https://arxiv.org/abs/2305.05176) | 2023-05-09 | 저자 초록 | 단계 추가 자체가 절감이라는 가정 없이 총비용을 비교한다 |
| [RouteLLM: Learning to Route LLMs with Preference Data](https://arxiv.org/abs/2406.18665) | 2024-06-26 · 갱신 2025-02-23 | v4 HTML 본문 | 라우팅과 항상 두 모델을 호출하는 연쇄를 구분한다 |
| [On Calibration of Modern Neural Networks](https://arxiv.org/abs/1706.04599) | 2017-06-14 · 갱신 2017-08-03 | 저자 초록 | confidence 임계값은 별도 검증 자료로 보정한다 |
| [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) | 2023-07-06 · 갱신 2023-11-20 | 저자 초록 | 같은 중요 정보를 앞·중간·끝에 배치한 조건을 추가한다 |
| [Beyond Utility Evaluation for LLM-Based and Generative Recommender Systems: A Focused Survey of Offline Protocols](https://www.preprints.org/manuscript/202609.1653) | 2026-09-20 | 본문; 심사 전; AI 추출 및 독립 사람 코딩 미확보 명시 | 최신 보조 조사로만 사용하고 원 연구를 독립 근거로 삼는다 |
| [ndcg_score](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html) | 발표일 미표시 | 본문 | 이득 함수와 tie 규칙을 시험 전에 고정한다 |
| [TypeSafe Introduction](https://docs.typesafe.ai/introduction) | 발표일 미표시 | 본문 | 취향·유사도 의미 점수와 거리 계산을 분리한다 |
| [TypeSafe Confidence](https://docs.typesafe.ai/confidence) | 발표일 미표시 | 본문 | 0.9 confidence를 우리 시험 정답률 90%로 해석하지 않는다 |
| [TypeSafe Primitives Questions](https://docs.typesafe.ai/primitives) | 발표일 미표시 | 본문 | 중간 취향 강도는 yes 확률 대신 정의한 등급 Score로 평가한다 |
| [TypeSafe Quick start](https://docs.typesafe.ai/introduction/quickstart) | 발표일 미표시 | 본문 | 공식 TypeSafe API와 호환 구현을 구분한다 |
| [Winnow API and runtime behavior](https://github.com/EldanRing/winnow-inference/blob/main/docs/API.md) | 발표일 미표시 | 본문 | Winnow-E4B의 정답률·calibration·GPU 비용은 따로 측정한다 |
| [Introducing System One Models and Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) | 2026-09-15 | 본문 | 제공자 속도·비용 주장을 우리 workload 실측으로 대체한다 |
| [Open-Sourcing Reranker v2](https://contextual.ai/blog/rerank-v2) | 2025-08-27 | 본문 | 독립 cross-encoder 대조군을 후속 비교 후보로 둔다 |
| [Introducing zerank-2 The Most Accurate Multilingual Instruction-Following Reranker](https://www.zeroentropy.dev/articles/zerank-2-advanced-instruction-following-multilingual-reranker) | 2025-11-18 | 본문 | 한국어 여행에서 이점은 직접 시험하며 공급자 최고 성능을 보장으로 쓰지 않는다 |
| [OpenAI Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | 발표일 미표시 | 공식 문서 본문 | 합성 문제를 사람 검수나 실서비스 대표 자료라고 부르지 않는다 |
| [OpenAI Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization) | 발표일 미표시 | 공식 문서 본문 | 연쇄 p95와 짧은 ID 출력 비용을 측정한다 |
| [OpenAI Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | 발표일 미표시 | 공식 문서 본문 | 캐시 사용량을 기록하고 첫 호출과 재사용 호출을 구분한다 |
| [OpenAI Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 발표일 미표시 | 공식 문서 본문 | 형식 실패와 추천 오답을 독립 채점한다 |
| [OpenAI Pricing](https://developers.openai.com/api/docs/pricing) | 발표일 미표시 | 공식 문서 표준 요금표 | 같은 티어·사용량 기준으로 계산; 결제 확정액과 추정 분리 |
| [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html) | 발표일 미표시 | 본문 | 같은 문제의 모델 점수 차이로 문제 단위 신뢰구간 계산 |
| [statsmodels McNemar](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html) | 발표일 미표시 | 본문 | 반복을 독립 표본으로 늘리지 않고 문제당 성공 정의 고정 |
| [Smarter Context Compression for LLM Pipelines zerank-2 as a Calibrated Classifier](https://www.zeroentropy.dev/articles/smarter-context-compression-for-llm-pipelines-zerank-2-as-a-calibrated-classifier/) | 2026-04-02 | 본문 | 선별 비용과 최상위 보존율을 함께 기록; 블로그 예제 threshold 코드는 그대로 채택하지 않음 |
| [Prompting Best Practices For Instruction-Following Rerankers](https://www.zeroentropy.dev/articles/prompting-best-practices-for-instruction-following-rerankers/) | 2026-01-22 | 본문 | 필수 조건과 선호 계수를 구분해 모델에 전달한다 |
| [Should You Use LLMs for Reranking A Deep Dive into Pointwise Listwise and Cross-Encoders](https://www.zeroentropy.dev/articles/should-you-use-llms-for-reranking-a-deep-dive-into-pointwise-listwise-and-cross-encoders/) | 2025-09-05 | 본문 | Jev+nano/Luna가 항상 최선이라고 가정하지 않고 단일 모델·규칙 대조군 포함 |
| [Rebuilding LinkedIn’s follows recommendations with LLM-based semantic retrieval and ranking](https://www.linkedin.com/blog/engineering/ai/rebuilding-linkedins-follows-recommendations-with-llm-based-semantic-retrieval-and-ranking) | 2026-08-24 | 본문: semantic encoding·supervised fine-tuning·offline/online EBR·L2 ranking integration | 회수와 최종 순위의 의미 특징을 맞춘다; 별도 학습 없는 범용 모델 성능 증거로 쓰지 않는다 |
| [Engineering the next generation of LinkedIn’s Feed](https://www.linkedin.com/blog/engineering/feed/engineering-the-next-generation-of-linkedins-feed) | 2026-03-12 | 본문 | 고객 취향의 의미와 현재 요청 맥락을 함께 전달한다; 클릭 최적화 목표는 여행 효용으로 바꾼다 |
| [Reimagining LinkedIn’s search tech stack](https://www.linkedin.com/blog/engineering/search/reimagining-linkedins-search-stack) | 2026-01-21 | 본문: infrastructure·golden grades·judge training·retrieval·SLM ranking | 모델 판정 전에 정답 검수와 일치도를 확인하고 재정렬 깊이·캐시를 제어한다 |
| [From Models to Products: LLMs for Recommendation at Spotify Scale](https://research.atspotify.com/2026/8/from-models-to-products-llms-for-recommendation-at-spotify-scale) | 2026-08-03 | 본문: catalog grounding·NEO training·GLIDE·deployment·results; 연결 논문은 저자 초록만 | 후보 ID와 현재 이용 가능성을 검증하고 익숙함·새로움을 고객 목표에 맞춘다; 관련 논문을 중복 집계하지 않는다 |
| [SilverTorch: Index-as-Model, a new retrieval paradigm for recommendation systems](https://engineering.fb.com/2026/05/26/ml-applications/silvertorch-index-as-model-new-retrieval-paradigm-recommendation-systems/) | 2026-05-26 | 본문 | 단계 경계의 버전 불일치와 왕복 지연을 줄인다; 거대 목록의 GPU 이득을 소규모 후보에 옮기지 않는다 |
| [GenRec: An LLM-Backed Recommendation Ranker at Netflix](https://arxiv.org/abs/2608.10257) | 2026-08-10 · 갱신 2026-08-21 | v2 HTML §4.5–§4.7·§5.1·§5.2·§7 | 입력 압축과 짧은 출력부터 비교; 전용 ranking head의 prefill-only를 범용 API 옵션으로 취급하지 않는다 |
