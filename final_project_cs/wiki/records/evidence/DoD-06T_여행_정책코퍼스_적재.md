# DoD-06T — 여행 정책 코퍼스 작성·적재 (2026-09-22)

★**DoD-06 의 여행판이다.** [DoD-06_정책FAQ_25건_300청크.md](DoD-06_정책FAQ_25건_300청크.md) 는
**쇼핑몰 코퍼스**의 기록이고 그 수(25문서·306청크)는 2026-08-17 에 그 코퍼스가 받은 판정이라
그대로 둔다. 이 문서는 **함께 공존하는** 여행 코퍼스의 수를 남긴다.

- 판정: **통과** (작성·게이트·적재·검색까지. 단 1536칸은 비어 있다 — 아래 §5)
- 커밋 hash: 미커밋(작업 트리). 이 세션은 커밋하지 않는다
- DB: `acop_cs` @ 127.0.0.1:5433 · tenant `demo`

---

## 1. 재현 명령

```powershell
python -m scripts.check_corpus
python -m scripts.ingest_corpus_local --manifest knowledge/travel/manifest.json --dry-run
python -m scripts.ingest_corpus_local --manifest knowledge/travel/manifest.json
python -m pytest tests/integration/rag -q
```

적재 전에 스키마 변경이 필요하다(재실행 안전):

```powershell
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop_cs `
  -v ON_ERROR_STOP=1 -f app/infrastructure/db/migrations/022_knowledge_chunk_openai_embedding_nullable.sql
```

## 2. 게이트 출력 (원문, 여행 부분만 발췌 — 쇼핑몰 줄은 잘랐다)

```
  · [여행] 문서 12 / 총 섹션 130
  · [여행] scope 배분 일치: {'travel_access': 1, 'travel_activity': 3, 'travel_cancellation': 1,
                             'travel_dining': 2, 'travel_mobility': 3, 'travel_weather': 2}
  · [여행] 문서 내 최대 문장 반복: 1 (상한 1)
  · [여행] 최다 공유 섹션 제목: '인원이 정원을 넘을 때' 1/12문서
  · [여행] 전체 청크 쌍 유사도: 평균 0.001 / 중앙 0.000
  · [여행] 청크 절반 이상에 공통인 6-gram 종류: 0
  · [여행] 청크 길이(공백 제외): 평균 258 최소 200 최대 342
  · [여행] 구체 수치 포함: 문서 100% / 섹션 45%
  · [여행] 청크 30% 초과에 공통인 8-gram: 0종 (상한 0)
  · [여행] 조사 오류: 0건 (상한 0)
  · [공통] scope 겹침 0건 (쇼핑몰 7종 · 여행 6종)
------------------------------------------------------------------------------
  전 항목 통과 — 인수 가능
```

★**쇼핑몰 코퍼스의 판정이 그대로다** — 같은 실행에서 `[쇼핑몰] 문서 25 / 총 섹션 306`,
`청크 길이 평균 232`, `조사 오류 0`, `구체 수치 문서 100% / 섹션 40%` 가 함께 나온다.
검사는 **컬렉션마다 따로** 돌기 때문에 여행 문서가 늘어도 쇼핑몰 수치가 흔들리지 않는다.

## 3. 적재 출력 (원문)

```
코퍼스 knowledge\travel\manifest.json — 문서 12 · 절 130
임베딩 모델 bge-m3:latest · 1024차원 · 칸 embedding_1024
  t_doc_01 (travel_activity) — 넣음 11 · 건너뜀 0 · 실패 0
  ...
  t_doc_12 (travel_access) — 넣음 130 · 건너뜀 0 · 실패 0
지금 이 코퍼스 상태: 문서 12 · 청크 130 · embedding_1024 채워짐 130
```

## 4. DB 직접 조회 (문서가 아니라 DB 를 세었다)

```sql
SELECT kd.scope, count(DISTINCT kd.document_id) docs, count(*) chunks,
       count(kc.embedding) dim1536, count(kc.embedding_1024) dim1024
  FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id)
 WHERE kd.tenant_id='demo' GROUP BY ROLLUP(kd.scope) ORDER BY 1;
```

```
        scope        | docs | chunks | dim1536 | dim1024
---------------------+------+--------+---------+---------
 exchange            |    3 |     36 |      36 |      36
 incident            |    2 |     24 |      24 |      24
 order               |    5 |     60 |      60 |      60
 refund              |    4 |     48 |      48 |      48
 return              |    4 |     52 |      52 |      52
 shipping            |    5 |     62 |      62 |      62
 support             |    2 |     24 |      24 |      24
 travel_access       |    1 |     11 |       0 |      11
 travel_activity     |    3 |     31 |       0 |      31
 travel_cancellation |    1 |     13 |       0 |      13
 travel_dining       |    2 |     21 |       0 |      21
 travel_mobility     |    3 |     31 |       0 |      31
 travel_weather      |    2 |     23 |       0 |      23
                     |   37 |    436 |     306 |     436
```

| | 쇼핑몰 | 여행 | 합 |
|---|---:|---:|---:|
| 문서 | 25 | **12** | 37 |
| 청크 | 306 | **130** | 436 |
| 1536칸(OpenAI) | 306 | **0** | 306 |
| 1024칸(bge-m3) | 306 | **130** | 436 |

## 5. ★ 1536칸이 비어 있다 — 숨기지 않는다

여행 130청크에는 OpenAI 임베딩이 **없다.** 크레딧이 없어 로컬 `bge-m3` 로만 넣었다.
따라서 `ACOP_EMBEDDING_PROVIDER=openai` 로 되돌리면 여행 scope 검색이 **예외로 죽는다** —
조용히 0건이 되지 않게 `app/infrastructure/rag/retriever.py::search_policy` 가 그 상태를
직접 검사한다. 회귀 시험:
`tests/integration/rag/test_rag_integration.py::test_the_travel_corpus_is_local_only_and_that_is_visible`

되메우려면 크레딧이 생긴 뒤 `python -m scripts.embed_chunks_local` 의 반대 방향(OpenAI 적재)이
필요하다 — 지금은 그 스크립트가 없다. **안 해 본 것 목록에 남긴다.**

## 6. 검색 실측

```
Q: 비가 와서 야외 활동을 못 하게 됐다            → t_doc_04#c3 (travel_weather) 0.561
Q: 예약을 이틀 전에 취소하면 위약금이 있나요      → t_doc_01#c1 (travel_activity) 0.636
Q: 지하철이 멈춰서 다음 일정에 못 갈 것 같아요    → t_doc_08#c10 (travel_mobility) 0.590
Q: 휠체어로 갈 수 있는 곳인가요                  → t_doc_12#c2 (travel_access) 0.647
Q: 배송완료로 떴는데 못 받았어요 (쇼핑몰 scope)   → doc_03·doc_01·doc_05 (shipping)  ← 여행 문서 0건
Q: 비가 와서 … (쇼핑몰 scope 로 검색)             → doc_05·doc_04 (shipping)          ← 여행 문서 0건
tenant='tenant-that-does-not-exist'               → []
```

시험 18건: `python -m pytest tests/integration/rag -q` → `18 passed`.

## 7. 일부러 깨뜨려 본 것 (게이트가 실제로 우는지)

| 무엇을 깨뜨렸나 | 무엇이 울었나 | 원복 |
|---|---|---|
| `t04` 문서의 `scope: travel_weather` → `refund` | `[FAIL] [여행] scope 배분 불일치: 실측 {'refund': 1, …}` | 했다. 다시 「전 항목 통과」 |
| Activity `knowledge_scope` 에 `refund` 를 되돌림 | `FAILED … test_registered_teams_never_search_commerce_scopes`. 그때 실제 검색: top-8 중 **7건이 쇼핑몰 환불 문서**(`doc_18`·`doc_19`·`doc_21`) | 했다. 18 passed |
| 세 Team 의 `policy_optional_capabilities` 삭제 | `tests/scenario` **8 failed** — 일정 관리 Case 가 `escalated` 로 떨어진다 | 했다. 29 passed |

## 8. 남은 것

- 법령·고시(소비자분쟁해결기준 등) **원문 조회 안 했다.** 그래서 업종별 위약금율은 코퍼스에 없다
- `_policy_hours`·`_penalty_rate` 가 산문에서 수치를 못 꺼낸다 →
  [../reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md](../reports/debugs/2026-09-22_정책청크에서_수치를_못_꺼낸다.md)
- 여행 코퍼스의 1536칸(위 §5)
