"""Build the dated primary-source bibliography; no model or network calls."""
import json
import shutil
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent

def write_with_backup(name, content):
    target = ROOT / name
    if target.exists():
        stamp = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d_%H%M%S_%f')
        backup = ROOT / '_backup' / (stamp + '_catalog')
        backup.mkdir(parents=True, exist_ok=False)
        shutil.copy2(target, backup / target.name)
    target.write_text(content, encoding='utf-8')

ROWS = [
('official_docs','Recommendation systems overview','https://developers.google.com/machine-learning/recommendation/overview/types',None,'2025-08-25','본문','후보 생성·점수·재정렬의 단계 구분','규칙/회수와 고비용 재정렬을 분리한다'),
('official_docs','Retrieve and Re-Rank','https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html',None,None,'본문','빠른 회수 뒤 CrossEncoder로 소수 후보를 평가','다수 후보를 생성형 모델에 모두 보내는 방식의 대조군'),
('paper','Is ChatGPT Good at Search? Investigating Large Language Models as Re-Ranking Agents','https://arxiv.org/abs/2304.09542','2023-04-19','2024-12-28','저자 초록','RankGPT와 NovelEval의 오염 통제','후보 ID만 반환하고 새 장소를 지어내지 않도록 한다'),
('paper','Enhancing Reranking for Recommendation with LLMs through User Preference Retrieval','https://aclanthology.org/2025.coling-main.45/','2025-01',None,'초록 및 PDF 본문','후보에 필요한 사용자 선호를 골라 LLM에 전달하는 UR4Rec','전체 대화와 정리된 취향 전달의 효과를 별도 시험한다'),
('paper','Beyond Utility: Evaluating LLM as Recommender','https://arxiv.org/abs/2411.00331','2024-11-01','2026-09-07','v2 HTML 본문','입력 이력 길이·후보 위치·프로필 생성·허구 항목 평가','순위 정확도 외 순서 민감도와 후보 유효성을 측정한다'),
('paper','Evaluating Position Bias in Large Language Model Recommendations','https://arxiv.org/abs/2508.02020','2025-08-04',None,'저자 초록','후보 위치 편향 및 RISE 반복 선택','같은 후보의 순열을 바꿔 순위를 비교한다'),
('paper','Position Bias Undermines Preference Consistency in Listwise LLM-Based Reranking','https://arxiv.org/abs/2608.03091','2026-08-04',None,'v1 HTML §3–§6: 지표·실험 조건·결과·결론','효과성과 순열 일관성은 다른 평가 축; 고정 입력 결정적 순위 추출 및 20개 순열','nDCG 외 출력 안정성을 확인하되 순열 변화와 생성 변동을 구분한다'),
('paper','TravelPlanner: A Benchmark for Real-World Planning with Language Agents','https://arxiv.org/abs/2402.01622','2024-02-02','2024-10-23','저자 초록','여행 도구 환경과 복합 조건 계획 평가','단일 장소 추천과 전체 계획 생성의 평가 범위를 구별한다'),
('paper','ChinaTravel: An Open-Ended Travel Planning Benchmark with Compositional Constraint Validation for Language Agents','https://arxiv.org/abs/2412.13682','2024-12-18','2026-04-29','v5 HTML 본문','사람의 열린 요구·암묵적 의도와 기호적 조건 검증','합성 시험 뒤 실제 고객 표현의 의미 정합성을 확인한다'),
('paper','Flex-TravelPlanner: A Benchmark for Flexible Planning with Language Agents','https://arxiv.org/abs/2506.04649','2025-06-05',None,'HTML 본문','여러 턴에서 새 조건과 기존 우선순위 충돌','뒤늦게 추가한 낮은 중요도 때문에 필수 조건을 깨는지 시험한다'),
('paper','Beyond Itinerary Planning A Real-World Benchmark for Multi-Turn and Tool-Using Travel Tasks','https://arxiv.org/abs/2512.22673','2025-12-27','2026-04-21','v3 HTML 본문','TravelBench: 한 턴·여러 턴·해결 불가 과제와 고정 도구 응답','후보가 하나도 가능한 경우와 시간에 따라 달라진 자료를 별도 시험한다'),
('paper','COMPASS: Benchmarking Constrained Optimization in LLM Agents','https://arxiv.org/abs/2510.07043','2025-10-08','2026-04-16','v2 HTML §3.1–§3.5·§4.1·§5.1–§5.2; Apple 소개와 대조','규칙 필터·전수 조합으로 실행 가능 집합과 효용 정답을 구함; 회수 부족과 정보 처리 실패 구분','방문 가능성과 효용 최적화를 독립 측정; 고정 후보 재정렬만으로 전체 회수 품질을 주장하지 않는다'),
('paper','TREK: A Travel Reasoning and Evaluation Kit for LLM Agents in Complex Trip Planning','https://arxiv.org/abs/2607.26977','2026-07-29','2026-08-10','v2 HTML §3.1–§3.6·§4.1–§4.4·Appendix A.2 및 F 한계','결정적 합성 조건·사람 검수 정답; 모델 답의 사람 평가와 실플랫폼 전이는 후속 과제','정답 가능성을 먼저 검증하고 실행 가능성과 비용을 독립 채점; 실제 고객 만족 증명으로 확대하지 않는다'),
('paper','FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance','https://arxiv.org/abs/2305.05176','2023-05-09',None,'저자 초록','측정 자료로 학습하는 비용 제한 모델 연쇄','단계 추가 자체가 절감이라는 가정 없이 총비용을 비교한다'),
('paper','RouteLLM: Learning to Route LLMs with Preference Data','https://arxiv.org/abs/2406.18665','2024-06-26','2025-02-23','v4 HTML 본문','선호 자료로 학습한 강·약 모델 선택','라우팅과 항상 두 모델을 호출하는 연쇄를 구분한다'),
('paper','On Calibration of Modern Neural Networks','https://arxiv.org/abs/1706.04599','2017-06-14','2017-08-03','저자 초록','높은 예측 확률과 실제 정답률의 불일치 및 temperature scaling','confidence 임계값은 별도 검증 자료로 보정한다'),
('paper','Lost in the Middle: How Language Models Use Long Contexts','https://arxiv.org/abs/2307.03172','2023-07-06','2023-11-20','저자 초록','긴 입력에서 근거 위치에 따른 성능 변동','같은 중요 정보를 앞·중간·끝에 배치한 조건을 추가한다'),
('paper','Beyond Utility Evaluation for LLM-Based and Generative Recommender Systems: A Focused Survey of Offline Protocols','https://www.preprints.org/manuscript/202609.1653','2026-09-20',None,'본문; 심사 전; AI 추출 및 독립 사람 코딩 미확보 명시','후보 접근·항목 식별·채점 단위가 비교 결론을 바꿈','최신 보조 조사로만 사용하고 원 연구를 독립 근거로 삼는다'),
('official_docs','ndcg_score','https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html',None,None,'본문','로그 할인·이상 순위 정규화·동점 처리','이득 함수와 tie 규칙을 시험 전에 고정한다'),
('official_docs','TypeSafe Introduction','https://docs.typesafe.ai/introduction',None,None,'본문','원자적 질문 분리 뒤 계수 조합은 코드로 수행','취향·유사도 의미 점수와 거리 계산을 분리한다'),
('official_docs','TypeSafe Confidence','https://docs.typesafe.ai/confidence',None,None,'본문','confidence는 출력 확률 분포에서 계산되는 통계','0.9 confidence를 우리 시험 정답률 90%로 해석하지 않는다'),
('official_docs','TypeSafe Primitives Questions','https://docs.typesafe.ai/primitives',None,None,'본문','Choice·Score·Noul의 의미와 서로 독립인 질문','중간 취향 강도는 yes 확률 대신 정의한 등급 Score로 평가한다'),
('official_docs','TypeSafe Quick start','https://docs.typesafe.ai/introduction/quickstart',None,None,'본문','공식 Jev API 호출·키·타입 계약','공식 TypeSafe API와 호환 구현을 구분한다'),
('official_docs','Winnow API and runtime behavior','https://github.com/EldanRing/winnow-inference/blob/main/docs/API.md',None,None,'본문','확률은 제한 선택지 softmax; confidence는 정규화 엔트로피; Jev 서비스 복제 아님','Winnow-E4B의 정답률·calibration·GPU 비용은 따로 측정한다'),
('first_party_blog','Introducing System One Models and Jev','https://typesafe.ai/blog/introducing-system-one-models-and-jev','2026-09-15',None,'본문','TypeSafe 제공자의 구조화 판단 모델 소개와 자체 비교','제공자 속도·비용 주장을 우리 workload 실측으로 대체한다'),
('first_party_blog','Open-Sourcing Reranker v2','https://contextual.ai/blog/rerank-v2','2025-08-27',None,'본문','지시·다국어 재정렬 모델과 공급자 benchmark','독립 cross-encoder 대조군을 후속 비교 후보로 둔다'),
('first_party_blog','Introducing zerank-2 The Most Accurate Multilingual Instruction-Following Reranker','https://www.zeroentropy.dev/articles/zerank-2-advanced-instruction-following-multilingual-reranker','2025-11-18',None,'본문','다국어·지시·보정 점수에 관한 공급자 실험','한국어 여행에서 이점은 직접 시험하며 공급자 최고 성능을 보장으로 쓰지 않는다'),
('official_docs','OpenAI Evaluation best practices','https://developers.openai.com/api/docs/guides/evaluation-best-practices',None,None,'공식 문서 본문','업무 대표 자료·경계 조건·사람 피드백과 단계별 평가','합성 문제를 사람 검수나 실서비스 대표 자료라고 부르지 않는다'),
('official_docs','OpenAI Latency optimization','https://developers.openai.com/api/docs/guides/latency-optimization',None,None,'공식 문서 본문','출력 축소·호출 축소·병렬화·계산 가능한 일의 비모델 처리','연쇄 p95와 짧은 ID 출력 비용을 측정한다'),
('official_docs','OpenAI Prompt caching','https://developers.openai.com/api/docs/guides/prompt-caching',None,None,'공식 문서 본문','동일 접두어 재사용; 캐시 쓰기는 추가 요금 아닌 해당 입력 단가','캐시 사용량을 기록하고 첫 호출과 재사용 호출을 구분한다'),
('official_docs','OpenAI Structured model outputs','https://developers.openai.com/api/docs/guides/structured-outputs',None,None,'공식 문서 본문','JSON Schema 준수·거절·잘림 처리가 내용 정답을 보장하지 않음','형식 실패와 추천 오답을 독립 채점한다'),
('official_docs','OpenAI Pricing','https://developers.openai.com/api/docs/pricing',None,None,'공식 문서 표준 요금표','nano와 Luna의 입력·캐시·출력 단가 및 도구 단가','같은 티어·사용량 기준으로 계산; 결제 확정액과 추정 분리'),
('official_docs','SciPy bootstrap','https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html',None,None,'본문','paired=True이면 동일 표본 인덱스로 여러 배열 재표집','같은 문제의 모델 점수 차이로 문제 단위 신뢰구간 계산'),
('official_docs','statsmodels McNemar','https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html',None,None,'본문','paired binary 결과의 2x2 표·소표본 exact binomial','반복을 독립 표본으로 늘리지 않고 문제당 성공 정의 고정'),
('first_party_blog','Smarter Context Compression for LLM Pipelines zerank-2 as a Calibrated Classifier','https://www.zeroentropy.dev/articles/smarter-context-compression-for-llm-pipelines-zerank-2-as-a-calibrated-classifier/','2026-04-02',None,'본문','선별 recall와 입력 길이의 절충·검증 자료 임계값 선택','선별 비용과 최상위 보존율을 함께 기록; 블로그 예제 threshold 코드는 그대로 채택하지 않음'),
('first_party_blog','Prompting Best Practices For Instruction-Following Rerankers','https://www.zeroentropy.dev/articles/prompting-best-practices-for-instruction-following-rerankers/','2026-01-22',None,'본문','사용자·업무 맥락 및 충돌 우선순위를 명시; 회수 실패는 재정렬로 복구 불가','필수 조건과 선호 계수를 구분해 모델에 전달한다'),
('first_party_blog','Should You Use LLMs for Reranking A Deep Dive into Pointwise Listwise and Cross-Encoders','https://www.zeroentropy.dev/articles/should-you-use-llms-for-reranking-a-deep-dive-into-pointwise-listwise-and-cross-encoders/','2025-09-05',None,'본문','17개 benchmark의 공급자 직접 비교; 전문 reranker 후 선택적 LLM','Jev+nano/Luna가 항상 최선이라고 가정하지 않고 단일 모델·규칙 대조군 포함'),
('first_party_blog','Rebuilding LinkedIn’s follows recommendations with LLM-based semantic retrieval and ranking','https://www.linkedin.com/blog/engineering/ai/rebuilding-linkedins-follows-recommendations-with-llm-based-semantic-retrieval-and-ranking','2026-08-24',None,'본문: semantic encoding·supervised fine-tuning·offline/online EBR·L2 ranking integration','내러티브 프로필·학습한 bi-encoder 회수·L2 재정렬의 임베딩 재사용','회수와 최종 순위의 의미 특징을 맞춘다; 별도 학습 없는 범용 모델 성능 증거로 쓰지 않는다'),
('first_party_blog','Engineering the next generation of LinkedIn’s Feed','https://www.linkedin.com/blog/engineering/feed/engineering-the-next-generation-of-linkedins-feed','2026-03-12',None,'본문','학습한 LLM 기반 의미 회수와 행동 순서 모델을 결합','고객 취향의 의미와 현재 요청 맥락을 함께 전달한다; 클릭 최적화 목표는 여행 효용으로 바꾼다'),
('first_party_blog','Reimagining LinkedIn’s search tech stack','https://www.linkedin.com/blog/engineering/search/reimagining-linkedins-search-stack','2026-01-21',None,'본문: infrastructure·golden grades·judge training·retrieval·SLM ranking','임베딩 회수·작은 CrossEncoder 순위·점수 캐시·사람 golden set','모델 판정 전에 정답 검수와 일치도를 확인하고 재정렬 깊이·캐시를 제어한다'),
('first_party_blog','From Models to Products: LLMs for Recommendation at Spotify Scale','https://research.atspotify.com/2026/8/from-models-to-products-llms-for-recommendation-at-spotify-scale','2026-08-03',None,'본문: catalog grounding·NEO training·GLIDE·deployment·results; 연결 논문은 저자 초록만','Semantic ID의 실제 항목 연결·장단기 취향 결합·생성 회수 후 기존 순위·사람 검수','후보 ID와 현재 이용 가능성을 검증하고 익숙함·새로움을 고객 목표에 맞춘다; 관련 논문을 중복 집계하지 않는다'),
('first_party_blog','SilverTorch: Index-as-Model, a new retrieval paradigm for recommendation systems','https://engineering.fb.com/2026/05/26/ml-applications/silvertorch-index-as-model-new-retrieval-paradigm-recommendation-systems/','2026-05-26',None,'본문','회수·자격 필터·신경 순위·합성 점수의 실행 경로를 같은 배포 산출물로 관리','단계 경계의 버전 불일치와 왕복 지연을 줄인다; 거대 목록의 GPU 이득을 소규모 후보에 옮기지 않는다'),
('paper','GenRec: An LLM-Backed Recommendation Ranker at Netflix','https://arxiv.org/abs/2608.10257','2026-08-10','2026-08-21','v2 HTML §4.5–§4.7·§5.1·§5.2·§7','추천 후학습·전용 catalog scoring head·prefill-only 실행; batch-compute surfaces A/B','입력 압축과 짧은 출력부터 비교; 전용 ranking head의 prefill-only를 범용 API 옵션으로 취급하지 않는다'),
]
sources = []
for i, (kind, title, url, published, updated, depth, finding, application) in enumerate(ROWS, 1):
    sources.append(dict(id=f'S{i:02d}',kind=kind,title=title,url=url,first_published=published,last_updated=updated,checked_on='2026-10-09',timezone='Asia/Seoul',verification='primary_page_opened',read_depth=depth,finding=finding,application=application,date_status='publication_or_update_verified' if published or updated else 'publication_date_not_shown'))
catalog=dict(boundary_date='2026-10-09',timezone='Asia/Seoul',selection='목적별 1차 출처 조사; 전수 문헌 조사 아님. 날짜 없는 공식 문서는 확인일을 발표일로 쓰지 않음.',counts=dict(Counter(s['kind'] for s in sources)),total_sources=len(sources),sources=sources)
write_with_backup('sources.json', json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
lines=['# 활동 추천 연구 출처 목록','',f"확인 경계는 2026-10-09 KST입니다. 검증 출처 {len(sources)}개이며 유형별 개수는 {catalog['counts']}입니다. 같은 논문의 판·프로젝트 소개는 한 자료로 셌습니다. 날짜가 표시되지 않은 공식 문서는 오늘 발표된 자료라는 뜻이 아닙니다.",'','| 자료 | 발표일 · 갱신일 | 확인 범위 | 우리 시험에 반영할 점 |','|---|---|---|---|']
for s in sources:
    date=s['first_published'] or '발표일 미표시'
    if s['last_updated']: date += ' · 갱신 '+s['last_updated']
    lines.append(f"| [{s['title']}]({s['url']}) | {date} | {s['read_depth']} | {s['application']} |")
write_with_backup('source_catalog.md', '\n'.join(lines)+'\n')
print(json.dumps({'sources':len(sources),'counts':catalog['counts']},ensure_ascii=False))
