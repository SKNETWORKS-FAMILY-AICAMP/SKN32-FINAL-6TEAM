# 구현 지시 — Basement 관리자 화면 (`/ui/admin`)

## 0. 왜 만드나

이 프로젝트의 주장은 **"모듈형 Basement"** 다. 그런데 그 모듈 구조가
**코드 안에만 있고 눈에 보이지 않는다.** Registry·manifest·Port·가드레일이
실제로 어떻게 조립돼 있는지 화면에서 확인할 수 없다.

관리자 화면은 두 가지를 해결한다:
1. **운영** — 어떤 Team 이 무슨 capability 로 등록됐고 어떤 tool 을 쓸 수 있는지
2. **발표·심사** — "모듈형" 주장을 말이 아니라 화면으로 보여준다

★**이번 범위는 읽기 전용(read-only)** 이다. 켜고 끄는 쓰기 기능은 다음 단계다
(운영 중 Team 을 끄는 것은 실행 중 Case 에 영향을 준다 — 별도 설계가 필요하다).

## 1. 소유 범위

```
app/presentation/ui/**        (admin 화면 추가)
tests/e2e/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/**`, `app/domain/**`, `app/modules/**`, `app/application/**`,
`app/infrastructure/**`, `app/composition.py`, `app/presentation/api/**`,
`eval/**`, `knowledge/**`, `config/**`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

★필요한 정보는 **기존 구조에서 읽는다.** 새 저장소나 테이블을 만들지 마라.

## 2. 만들 것 — `/ui/admin` (4개 섹션, 한 화면)

### 2-1. Agent Team Modules
`app/composition.py:build_registry()` 로 Registry 를 만들어 등록된 Team 을 보여준다.
각 Team 의 `TeamManifest` 에서:

| 표시 항목 | 출처 |
|---|---|
| `team_id` · `display_name` | manifest |
| `capabilities` | manifest |
| `accepted_case_types` | manifest |
| `allowed_tools` | manifest |
| `knowledge_scope` | manifest |
| `max_steps` · `active` | manifest |
| `supported_contract_versions` | manifest |
| `implementation_revision` | manifest |

★**Team 을 추가하면 이 화면에 자동으로 나타나야 한다** — 하드코딩하지 마라.

### 2-2. Ports & Adapters
현재 조립된 Port 와 그 구현체를 보여준다:

| Port | 현재 구현 |
|---|---|
| `TeamExecutorPort` | `LocalTeamExecutor` (A2A 가능) |
| `MessageBrokerPort` | `OutboxBrokerAdapter` |
| `GraphStorePort` | `SqlGraphAdapter` |
| Vector 검색 | pgvector retriever |
| LLM | provider·model (키는 **마스킹**) |

★**클래스 이름을 런타임에서 읽어라**(`type(obj).__name__`). 문자열로 적지 마라 —
구현이 바뀌면 화면도 바뀌어야 한다.

### 2-3. Guardrails
`config/guardrails.yaml` 의 주요 수치를 섹션별로:
토큰 예산(12,000 + 섹션별) · 신뢰성(timeout·retry·loop guard) ·
RAG(top-k·차원·문서/청크 수) · VOC 급증식 · scope 6종 · 평가 설정

★`app.core.settings.get_guardrails()` 로 읽는다. 값을 화면에 다시 쓰지 마라.

### 2-4. 시스템 현황
- 등록 Team 수 · 적재 문서/청크 수(`knowledge_documents`/`knowledge_chunks`)
- Case 상태별 건수 (`customer_cases` group by status)
- 최근 outbox 상태 (pending/dead-letter 건수)

★모든 조회에 **`tenant_id` 조건**을 넣는다.

## 3. 구현 지침

- 기존 `/ui/*` 와 같은 방식(서버 사이드 렌더링). SPA 프레임워크 금지
- ★**PII·API 키·비밀을 화면에 노출하지 마라.** LLM 키는 `sk-****` 형태로
- ★데이터가 없으면 **"없음"을 정직하게 표시**한다. 더미 값 금지
- 기존 UI 네비게이션에 `admin` 링크를 추가한다
- ★**쓰기 기능을 만들지 마라** (Team 활성/비활성 토글 등). 읽기 전용이다

## 4. 테스트 (`tests/e2e/`)

1. `/ui/admin` 이 **200** 이다
2. ★등록된 두 Team(`billing_subscription`·`technical_entitlement`)이 **화면에 나타난다**
3. ★**fake Team 을 하나 더 등록하면 그것도 나타난다** (하드코딩이 아님을 증명)
4. guardrails 의 `token_budget=12000` 이 화면에 표시된다
5. ★API 키 원문이 화면에 **없다**

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지. 테스트 전용 tenant, teardown 삭제, `demo` 보존.

## 5. 완료 조건

```powershell
python -m pytest tests -q
Start-Process -NoNewWindow python -ArgumentList "-m","uvicorn","app.presentation.api.app:app","--port","8020"
Start-Sleep 5
curl.exe -s -o NUL -w "admin=%{http_code}\n" http://127.0.0.1:8020/ui/admin
```
기대: **128건 이상, 0 failed, skipped 0**, `admin=200`.
★확인 후 **서버를 종료**하라.

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 6. 리포트

`wiki/records/reports/2026-08-14_S-ADMINUI_리포트.md` — 화면 구성, 각 정보의 출처(런타임 조회 vs 설정),
§5 출력 원문, 노출하지 않기로 한 항목.

## 7. 하지 말 것
- ❌ Team 목록·Port 이름 하드코딩
- ❌ 쓰기 기능 (활성/비활성 토글)
- ❌ API 키·PII 노출
- ❌ 더미 데이터
- ❌ `tenant_id` 없는 조회
- ❌ 소유 범위 밖 수정
- ❌ 서버를 안 띄워보고 "동작함"
