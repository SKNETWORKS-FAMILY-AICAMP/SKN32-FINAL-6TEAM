# Codex 작업 지시 — S-RAG 2단계: pgvector 적재와 검색

코퍼스 원문 25건/300섹션은 **인수 완료**됐다(`wiki/records/evidence/DoD-06_정책FAQ_25건_300청크.md`).
이번 작업은 **적재(ingest)와 검색(retriever)** 이다.

## 0. 먼저 읽을 것

1. `RULE.md` §3.1(하드코딩 금지) · §3.2(폴백 금지) · §3.4(리포트 의무)
2. `CLAUDE.md` §0.1(근거 없으면 답하지 않는다) · §1(tenant 격리)
3. `wiki/records/handoff/02_DB_스키마.md` §1(`knowledge_documents`·`knowledge_chunks` DDL) · §3(RAG 검색 SQL)
4. `wiki/records/handoff/06_가드레일_수치.md` §3 — top-k 8 · 1536차원 · hnsw
5. `app/core/context.py` — ★**이미 구현된 Context Broker**. `PolicyChunk` 를 받는다. **읽어라. 고치지 마라**
6. `app/core/settings.py` — `get_settings()`, `get_guardrails()`

## 1. 소유 범위

```
knowledge/ingest.py
app/infrastructure/rag/**
tests/integration/rag/**
wiki/records/reports/ , wiki/records/history/
```

★`app/core/**`, `app/presentation/**`, `app/infrastructure/db/**`, `scripts/**`, `knowledge/documents/*.md` **금지**.
코퍼스 원문은 인수된 상태다. **고치지 마라.**

## 2. 만들 것

### 2-1. `knowledge/ingest.py`

```powershell
python -m knowledge.ingest          # 적재
python -m knowledge.ingest --dry-run
```

- `knowledge/manifest.json` 을 읽어 25개 문서를 `knowledge_documents` 에 넣는다
  (`tenant_id='demo'`, `title`/`source_uri`/`scope`/`version`/`pii_class` 는 frontmatter 에서)
- 각 문서를 **`##` 소제목 단위로 청킹**한다 → `knowledge_chunks` **300행**
- `metadata_json` 필수 키: `tenant_id`, `scope`, `document_id`, `version`, `pii_class`, `effective_from`,
  `section_title` (인용 표시 `doc_06#c04` 를 만들 수 있어야 한다)
- 임베딩: `get_settings().embedding_model` (`text-embedding-3-small`, **1536차원**).
  ★모델명·차원을 하드코딩하지 마라 — `guardrails.get("rag.embedding_dim")` 로 검증하라
- ★**재실행해도 중복이 쌓이면 안 된다.** `UNIQUE(document_id, chunk_no)` 가 있다
- ★**API 키가 없으면 예외를 던지고 멈춰라.** 랜덤 벡터·0벡터로 대체하지 마라(폴백 금지)
- 진행 상황과 **실제 적재 건수**를 출력한다

★비용 주의: 300 청크 × ~300자 = 소액이지만, `--dry-run` 으로 먼저 건수를 확인하고 돌려라.

### 2-2. `app/infrastructure/rag/retriever.py`

```python
def search_policy(tenant_id: str, query: str, allowed_scopes: list[str], top_k: int | None = None) -> list[PolicyChunk]
```

- `wiki/records/handoff/02` §3 의 SQL 그대로 (cosine, `ORDER BY embedding <=> :q`)
- `top_k` 기본값은 `guardrails.get("rag.top_k")` (=8). ★하드코딩 금지
- ★**`tenant_id` 와 `scope` 필터를 반드시 건다.** 조건 없는 조회는 보안 결함이다
- 반환 타입은 `app.core.context.PolicyChunk` — **Context Broker 가 그대로 받는다**
  (`document_id`, `chunk_no`, `content`, `score`, `scope`)
- ★검색 실패(DB 오류 등)를 빈 리스트로 삼키지 마라. 예외를 올려서
  호출자가 `ContextInputs(retrieval_failed=True)` 로 판단하게 한다

### 2-3. `tests/integration/rag/`

1. **적재 건수** — `knowledge_documents` 25행, `knowledge_chunks` **300행** (DoD 6)
2. **차원** — 임베딩이 1536차원인지 확인
3. ★**검색 적합성** — 시나리오 질의를 넣고 **기대 문서가 top-k 안에** 오는지:
   - `"해지했는데 결제가 됐어요"` → `doc_06`(해지 후 발생한 청구의 환불)이 top-8 안
   - `"Pro로 바꿨는데 기능이 안 보여요"` → entitlement scope 문서가 top-8 안
4. ★**tenant 격리** — 다른 tenant_id 로 조회하면 **0건**
5. ★**scope 필터** — `allowed_scopes=['billing']` 이면 refund/entitlement 청크가 안 나온다
6. **멱등성** — ingest 두 번 돌려도 `knowledge_chunks` 가 300행

★테스트가 임베딩 API 를 매번 호출하지 않게 하라 (적재된 것을 조회만 하거나, 질의 임베딩을 캐시).
비용과 속도 둘 다 문제가 된다.

★테스트 전용 tenant 를 쓰고 teardown 에서 지운다. **`demo` tenant 데이터를 지우지 마라.**

## 3. 환경

- PostgreSQL 16.14 `127.0.0.1:5433` DB `acop`, `vector 0.8.3` 설치됨
- `pgvector` 파이썬 패키지 설치됨. OpenAI 키는 `.env` 의 `ACOP_OPENAI_API_KEY`
- ★설정은 **`app.core.settings.get_settings()`** 로만 읽는다.
  `os.getenv` 를 쓰면 `.env` 값이 안 보인다 — S-API 가 이걸로 전면 장애를 냈다
  (`wiki/records/reports/debugs/2026-08-12_1830_S-API가_실행되지_않는다.md`)

## 4. 완료 조건 — 실제로 실행하고 출력을 붙인다

```powershell
python -m knowledge.ingest --dry-run
python -m knowledge.ingest
python -m knowledge.ingest              # 재실행 — 건수가 늘면 안 된다
python -m pytest tests -q               # 기존 74건이 계속 통과해야 한다
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'documents='||count(*) from knowledge_documents"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'chunks='||count(*) from knowledge_chunks"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

기대: `documents=25`, `chunks=300`, `tenants=1`.

## 5. 리포트

`wiki/records/reports/2026-08-12_S-RAG_적재_검색_리포트.md` — §4 명령의 **실제 출력 원문**,
검색 적합성 테스트의 질의별 top-8 결과(문서 id 와 점수), 임베딩 호출 횟수와 대략 비용.
`wiki/records/history/2026-08-12_S-RAG_ingest.md` 이력 추가.

## 6. 하지 말 것

- ❌ 코퍼스 원문(`knowledge/documents/*.md`) 수정
- ❌ 소유 범위 밖 파일 수정
- ❌ 모델명·차원·top-k 하드코딩
- ❌ API 키 없을 때 랜덤/0 벡터로 대체
- ❌ 검색 실패를 빈 리스트로 삼키기
- ❌ `tenant_id`·`scope` 조건 없는 조회
- ❌ 테스트가 `demo` tenant 오염·삭제
- ❌ 적재를 돌리지 않고 건수를 추정해서 쓰기
