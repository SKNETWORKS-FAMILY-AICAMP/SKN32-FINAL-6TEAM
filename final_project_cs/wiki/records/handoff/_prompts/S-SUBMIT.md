# 구현 지시 — 제출 산출물 작성 (wiki/records/submission/)

## 0. ★가장 중요한 규칙 — 수치를 지어내지 마라

이 문서들은 심사에 나간다. **모든 수치는 저장소에 실재하는 근거에서 가져온다.**

- 근거 위치: `wiki/records/evidence/DoD-*.md`, `wiki/records/reports/`, `wiki/records/reports/debugs/`
- ★**모르는 값은 "미측정" 이라고 쓴다.** 추정치를 숫자처럼 쓰지 마라
- ★**아직 통과하지 않은 것을 통과했다고 쓰지 마라.**
  `wiki/records/evidence/` 의 `판정:` 줄이 기준이다 (`통과` / `부분 통과` / `미통과`)
- 수치에는 **분모를 함께** 적는다 (예: `0.85 (51/60)`)

현재 실측 상태 (2026-08-13):
```
테스트: 116 passed, 0 failed, skipped 0
DB: tenants=1, demo_customers=10, knowledge_documents=25, knowledge_chunks=300 (1536d)
검색: '해지했는데 결제가 됐어요' → doc_06 이 1·2위 (0.52)
      'Pro로 바꿨는데 기능이 안 보여요' → doc_14 가 1·2위
마일스톤: M1 도달, M2 도달, M3 미도달(평가 전량 실행 진행 중)
평가: 하네스 완성·인용 검증 적용. 전량 실행 결과는 아직 없다 → "진행 중" 으로 쓴다
```

## 1. 소유 범위

```
wiki/records/submission/**
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **전부 금지**. 특히 `app/**` 는 **지금 다른 세션이 구조를 옮기는 중이다. 절대 열지 마라.**
`eval/**`, `tests/**`, `knowledge/**`, `wiki/records/evidence/**`, `wiki/records/handoff/**` 도 금지.

## 2. 만들 문서

`wiki/records/submission/` 에 아래를 만든다. 파일명 앞에 번호를 붙인다.

### `00_제출산출물_인덱스.md`
각 문서가 무엇을 담는지, 어떤 근거 파일에서 왔는지 한 줄씩.

### `01_수집데이터_및_전처리.md`
- 정책/FAQ 코퍼스 25문서 300청크의 **구성과 작성 기준**
- scope 배분표 (billing 5 / refund 4 / subscription 4 / entitlement 5 / incident 3 / technical 2 / support 2)
- 청킹 방식(`##` 소제목 단위), 임베딩(1536차원), 적재 결과
- ★**코퍼스 품질 게이트**(`scripts/check_corpus.py`)가 무엇을 검사하는지 —
  이건 이 프로젝트의 차별점이다. 근거: `wiki/records/evidence/DoD-06_*.md`

### `02_시스템_아키텍처.md`
- 계층 구조 (External Access / Core Basement / Domain / Adapters)
- ★**Case 생명주기 12상태와 전이표** — `transition_case()` 단일 진입점
- optimistic concurrency · append-only event · projection replay
- Context Broker 12,000 토큰 예산과 제거 순서
- outbox = Message Broker 재정의
- 근거: `wiki/records/evidence/DoD-02_*.md`, `DoD-03_*.md`, `DoD-12_*.md`

### `03_RAG_LLM_벡터DB_구현.md`
- pgvector 적재·검색, top-k=8, scope 필터, tenant 격리
- 시나리오 질의별 실제 top-8 결과 (근거: `DoD-06_*.md`)
- Context Broker 가 근거를 어떻게 조합하는가

### `04_테스트_계획_및_결과.md`
- 테스트 분류(계약/단위/통합/보안/e2e)와 **실제 건수**
- ★**결함을 숨기지 마라.** `wiki/records/reports/debugs/` 의 결함들을 그대로 싣는다:
  RAG 검색 100% 실패, API 전 요청 500, PII 평문 저장, 평가가 환각 인용에 점수,
  Controller 가 `resuming` 에서 `resumed` 를 건너뜀
  **각각 어떻게 발견하고 무엇으로 고쳤는지** 적는다 — 이게 가장 설득력 있는 부분이다

### `05A_DB_스키마.md`
- v5 §8 테이블 14개 + mock 4개
- ★정합성의 실체인 **UNIQUE 제약 3종**이 무엇을 막는지

### `05B_보안_경계.md`
- API key + scope 6종, MCP read-only 3 tool
- 남의 Case → 404(403 아님)인 이유
- PII 마스킹, audit 금지 항목

### `06_시연_시나리오.md`
- 시나리오 1: 해지 후 추가 결제 → 환불 승인 대기
  실제 관측된 전이: `classifying(1)→routing(2)→running(3)→waiting_approval(4)→resuming(5)→running(6)→resolved(7)`
- 시나리오 2: Free/Pro 권한 불일치 → `→resolved(4)`
- 시나리오 3: 반복 VOC 급증
- 각 단계에서 **어느 화면을 보여줄지** (`/ui/cases`, `/ui/approvals`, `/ui/voc`)

### `07_한계와_다음_단계.md`
★**이 문서가 가장 중요하다.** 심사에서 신뢰를 만드는 건 여기다.
- `wiki/records/evidence/` 에서 **부분 통과·미통과 항목을 전부** 모아 정직하게 나열
- 60건×3회가 증명하지 **않는** 것 (v5 §15-8): 모집단 일반화·장기 drift·실제 손실률·SLA
- Phase 2 로 미룬 것: OAuth2, 실결제 provider, Redis Streams, hybrid BM25+rerank,
  Graph 저장소 본체(신 계획서 §9-D 가 "현재 규모에서는 JOIN 이 맞다"고 거부)

## 3. 형식

- Markdown. 표를 적극 쓴다
- 각 문서 하단에 **"근거"** 절 — 어느 evidence/report 파일에서 가져왔는지
- 발표자가 그대로 읽어도 되게 문장을 완결한다

## 4. 완료 조건

```powershell
Get-ChildItem docs\submission\*.md | Measure-Object
```
9개 문서. 그리고 **각 문서의 수치가 근거 파일과 일치하는지 스스로 대조**하고
대조 결과를 리포트에 적어라.

## 5. 리포트

`wiki/records/reports/2026-08-13_S-SUBMIT_리포트.md` — 만든 문서 목록,
★**근거를 찾지 못해 "미측정" 으로 남긴 항목 목록**.

## 6. 하지 말 것
- ❌ `app/**` 열기 (다른 세션이 구조 이동 중)
- ❌ 수치 추정·창작
- ❌ 미통과 항목을 통과로 쓰기
- ❌ 결함 이력 숨기기
- ❌ 평가 전량 실행 결과를 있는 것처럼 쓰기 (아직 없다)
