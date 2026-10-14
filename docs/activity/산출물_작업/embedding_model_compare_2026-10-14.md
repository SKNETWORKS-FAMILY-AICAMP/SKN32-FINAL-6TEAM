# 임베딩 모델 비교 (오프라인, DB·코어 무변경) — 2026-10-14

활동 4개 scope 100청크 · 질문 30개(20문항 + 새 10문항)를 메모리에서만 비교했다. DB 에 쓰지 않았다.

| 모델 | 20문항 Hit@3 / Hit@1 | 새 10문항 Hit@3 / Hit@1 | 전체 Hit@3 |
|---|---|---|---|
| text-embedding-3-small (1536, 현재) | 13/20 / 9 | 8/10 / 4 | 21/30 |
| text-embedding-3-large (dimensions=1536) | 17/20 / 13 | 9/10 / 6 | 26/30 |
| text-embedding-3-large (3072) | 17/20 / 13 | 9/10 / 6 | 26/30 |

- 메모리 계산이라 DB 시험(12/20)과 1건 차이가 난다(청크 전체 본문 임베딩 vs 적재본, 동점 처리).
- 적용하려면: 코어 `app/infrastructure/rag/retriever.py:38` 이 `dimensions` 를 넘기지 않아 large 는 3072 차원이 나와 `vector(1536)` 과 어긋난다. 코어 수정 + 전 문서 재임베딩 필요 → 코어 협의 사항.
- 재현: `cd final_project_cs && PYTHONPATH=. python ../docs/activity/산출물_작업/embedding_model_compare.py` (OpenAI 임베딩 약 5만 토큰)
