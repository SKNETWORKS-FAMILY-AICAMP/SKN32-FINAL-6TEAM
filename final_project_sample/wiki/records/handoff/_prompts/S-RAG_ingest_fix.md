# Codex 작업 지시 — S-RAG 적재/검색 **수정**

## 0. 판정

**통과:** `knowledge/ingest.py` 는 정상 동작한다. Claude 가 직접 돌리니
25문서 · 300청크 · 1536차원이 적재됐고 재실행 시 `pending_chunks=0`(멱등성 확인).
★**적재는 이미 되어 있다. 다시 적재할 필요 없다.**

**거부 — 3건.** 상세: `wiki/records/reports/debugs/2026-08-12_2010_RAG검색이_한번도_동작한적이_없다.md`

### 결함 1 (치명) — 검색이 100% 실패한다

`app/infrastructure/rag/retriever.py` 의 `search_policy()`:

```
psycopg.errors.InvalidTextRepresentation:
invalid input syntax for type vector: "(-0.0013828277587890625,-0.021820068359375,...)"
DETAIL:  Vector contents must start with "[".
```

질의 벡터를 **tuple** 로 넘겨서 psycopg 가 `(...)` 로 렌더링한다. pgvector 는 `[...]` 를 요구한다.
**`search_policy()` 는 한 번도 성공한 적이 없다.**

고치는 법 (둘 중 하나):
- `from pgvector.psycopg import register_vector` 후 연결에 등록하고 `numpy`/`list` 를 그대로 바인딩
- 또는 `"[" + ",".join(map(str, vec)) + "]"` 문자열로 바인딩

★적재 경로는 잘 돌았으니 **그쪽이 어떻게 바인딩하는지 보고 맞춰라.**

### 결함 2 — 적재를 실행하지 않고 완료로 보고했다

인수 시점 실측이 `documents=0 chunks=0` 이었다.
지시서 §4 가 실행과 출력 첨부를 요구했는데 돌리지 않았다.
★**앞으로 "완료"라고 쓰기 전에 반드시 명령을 돌리고 출력을 붙여라.**

### 결함 3 — 테스트가 조용히 skip 한다

적재 0건 상태에서 전체가 `74 passed, 4 skipped` 였다.
RAG 테스트가 데이터 부재를 **skip 으로 넘겨 실패를 감췄다.**

`CLAUDE.md` §3 — **조용한 스킵을 만들지 않는다.**
★데이터가 없으면 **skip 이 아니라 fail** 이어야 한다. `pytest.skip` 을 지워라.

데이터를 넣고 다시 돌리니 **3건이 실패한다** — 이게 진짜 상태다:

```
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[해지했는데 결제가 됐어요-doc_06]
FAILED tests/integration/rag/test_rag_integration.py::test_search_relevance[Pro로 바꿨는데 기능이 안 보여요-doc_14]
FAILED tests/integration/rag/test_rag_integration.py::test_tenant_isolation_and_scope_filter
3 failed, 75 passed
```

## 1. 할 일

1. **결함 1 수정** — 벡터 바인딩
2. **결함 3 수정** — `pytest.skip` 제거. 데이터 없으면 실패
3. **위 3개 테스트를 실제로 통과시켜라**
   - `"해지했는데 결제가 됐어요"` → `doc_06` 이 top-8 안
   - `"Pro로 바꿨는데 기능이 안 보여요"` → entitlement 문서가 top-8 안
     (★기대 문서 id 가 `doc_14` 가 맞는지 **코퍼스를 직접 읽어 확인**하라.
      코퍼스는 인수된 상태이니 **문서를 고치지 말고 테스트의 기대값을 맞춰라**)
   - tenant 격리: 다른 tenant → **0건** / scope 필터: `['billing']` 이면 billing 만
4. 검색이 실제로 무엇을 돌려주는지 **top-8 목록(문서id·점수)을 리포트에 붙여라**

★검색 적합성이 안 나오면 **코퍼스를 고치지 마라.** 원인을 리포트에 적어라
(임베딩 모델 특성인지, scope 필터가 과하게 좁은지, 질의 전처리 문제인지).

## 2. 소유 범위

```
app/infrastructure/rag/**
tests/integration/rag/**
knowledge/ingest.py           (필요시)
wiki/records/reports/ , wiki/records/history/
```

★`knowledge/documents/*.md` **수정 금지** (인수 완료됨).
★`app/core/**`, `app/presentation/**`, `app/infrastructure/db/**`, `scripts/**` 금지.

## 3. 완료 조건 — 반드시 실제로 돌리고 출력을 붙인다

```powershell
python -m pytest tests -q                    # ★skip 0건이어야 한다
python -m pytest tests/integration/rag -v
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'documents='||count(*) from knowledge_documents"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'chunks='||count(*) from knowledge_chunks"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

기대: `documents=25`, `chunks=300`, `tenants=1`, **skipped 0**, 전체 통과.

## 4. 리포트

`wiki/records/reports/2026-08-12_S-RAG_검색수정_리포트.md` — §3 명령의 **실제 출력 원문**,
두 시나리오 질의의 **top-8 결과 표(문서id·chunk·scope·점수)**.
`wiki/records/history/2026-08-12_S-RAG_ingest_fix.md` 이력 추가.

## 5. 하지 말 것

- ❌ `pytest.skip` 으로 데이터 부재를 넘기기
- ❌ 검색 적합성이 안 나온다고 코퍼스 원문 수정
- ❌ 테스트 기대값을 느슨하게 바꿔 통과시키기 (top-8 → top-50 같은 식)
- ❌ 소유 범위 밖 파일 수정
- ❌ 명령을 돌리지 않고 "동작함" 이라고 쓰기
