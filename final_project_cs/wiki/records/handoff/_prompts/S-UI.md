# Codex — 스트림 S-UI (운영 화면: Case · Trace · Approval · VOC)

## 0. 먼저 읽을 것
1. `RULE.md` §3.1(하드코딩 금지) §3.2(폴백 금지) §3.4
2. `CLAUDE.md` ★§0.1(근거 없이 확정하지 않는다) ★§0.2(승인 없이 실행하지 않는다) §4(실제로 열어서 확인)
3. `wiki/records/handoff/03_REST_MCP_인터페이스.md` — 쓸 수 있는 API 는 **이 5개뿐**
4. 구현돼 있는 것: `app/presentation/api/app.py`(FastAPI), `app/presentation/security.py`,
   `app/infrastructure/db/repository.py`, `app/core/settings.py`
5. `../A-COP_구현계획서_v5.md` §3(In: 최소 Case/Trace/Approval/VOC UI) — 읽기 전용, **수정 금지**

## 1. 소유 범위
```
app/presentation/ui/**
tests/e2e/**
wiki/records/reports/ , wiki/records/history/ , wiki/records/screenshots/
```
★그 밖 **전부 금지**. `app/presentation/api/**` 와 `security.py` 는 **수정하지 마라**
(이미 인수됨). 라우터 등록이 필요하면 **리포트에 요청**하고, UI 는 자체 라우터로 마운트하라.
`app/core/**`, `app/modules/**`, `app/application/**`, `eval/**`, `knowledge/**` 는 **다른 세션 작업 중**이다.

## 2. 만들 것 — 화면 4개 (v5 §3 In)

### 2-1. Case 목록 / 상세
- 목록: status·intent·issue_code·sentiment·owner_team·version·updated_at
- 상세: 현재 상태, `state_json`, **evidence 목록(source_type·source_id·claim)**

### 2-2. Trace (이벤트 타임라인)
- `case_events` 를 `aggregate_version` 순으로: event_type · actor · created_at · payload 요약
- ★append-only 임이 화면에서 드러나야 한다 (수정/삭제 버튼을 만들지 마라)

### 2-3. Approval ★가장 중요
- pending `action_requests` 목록 → 상세에 **ActionProposal 과 rationale evidence 를 반드시 함께** 표시
- ★**근거 없이 승인 버튼을 누를 수 있게 만들지 마라.** evidence 가 비면 승인 버튼을 비활성화한다
- 승인/거절은 `POST /v1/cases/{case_id}/actions/{action_id}/approve` 를 호출한다
  (직접 DB 를 쓰지 마라)
- 표시할 것: action_type, arguments, risk_level, idempotency_key(마스킹), 근거 evidence

### 2-4. VOC 일일 리포트
- `feedback_analytics_reports` 의 최신 report: intent/issue count, negative ratio, unresolved ratio, **급증 alert**
- ★리포트가 아직 없으면 **"없음"을 명확히 표시**한다. 가짜 숫자를 만들지 마라

## 3. 구현 지침
- **서버 사이드 렌더링(Jinja2) 또는 정적 HTML+fetch** 중 단순한 쪽. SPA 프레임워크 금지(YAGNI)
- 포트·API base URL·키를 **하드코딩하지 마라** → `app.core.settings.get_settings()`
  ★`os.getenv` 를 쓰면 `.env` 값이 안 보인다 (S-API 가 이걸로 전면 장애를 냈다:
  `wiki/records/reports/debugs/2026-08-12_1830_S-API가_실행되지_않는다.md`)
- ★**PII 를 화면에 원문으로 띄우지 마라.** masked 값만
- 데이터가 없으면 **빈 상태를 정직하게 표시**한다. 더미 데이터 금지

## 4. 테스트 (`tests/e2e/`)
Playwright 가 없으면 **FastAPI TestClient + HTML 파싱**으로도 된다. 반드시 검증할 것:
1. Case 목록/상세가 **실제 seed 데이터**를 렌더링한다
2. Trace 가 이벤트를 version 순으로 보여준다
3. ★**evidence 없는 proposal 은 승인 버튼이 비활성**이다
4. 승인 클릭이 **REST approve endpoint 를 호출**한다 (DB 직접 쓰기 아님)
5. VOC 리포트가 없을 때 **"없음"** 을 표시한다 (0 이나 가짜 값이 아니라)
- ★`pytest.skip` 금지. 데이터 없으면 **fail**
- ★테스트 전용 tenant, teardown 에서 삭제. `demo` 를 지우지 마라

## 5. 완료 조건 (실제로 띄워서 확인한다)
```powershell
python -m pytest tests -q          # 기존 테스트가 계속 통과 + skip 0
Start-Process -NoNewWindow python -ArgumentList "-m","uvicorn","app.presentation.api.app:app","--port","8010"
Start-Sleep 4
curl.exe -s -o NUL -w "cases=%{http_code}\n"    http://127.0.0.1:8010/ui/cases
curl.exe -s -o NUL -w "approvals=%{http_code}\n" http://127.0.0.1:8010/ui/approvals
curl.exe -s -o NUL -w "voc=%{http_code}\n"       http://127.0.0.1:8010/ui/voc
```
★`CLAUDE.md` §4 — **백엔드 테스트 통과만으로 "구현 완료"라 하지 않는다. 실제로 열어서 확인한다.**
가능하면 화면 캡처를 `wiki/records/screenshots/` 에 남겨라.

## 6. 리포트
`wiki/records/reports/2026-08-12_S-UI_리포트.md` — §5 **실제 출력 원문**, 화면 4개의 경로,
`api/` 에 요청할 것(라우터 등록 등). `wiki/records/history/2026-08-12_S-UI.md` 이력 추가.

## 7. 하지 말 것
- ❌ `app/presentation/api/**`, `security.py` 수정
- ❌ 승인 화면에서 근거 없이 승인 가능하게 만들기
- ❌ UI 가 DB 에 직접 쓰기 (읽기는 허용, 쓰기는 REST 경유)
- ❌ 더미/가짜 데이터 표시
- ❌ PII 원문 노출
- ❌ `os.getenv` / 포트·URL 하드코딩
- ❌ `pytest.skip`
- ❌ 서버를 안 띄워보고 "동작함"
