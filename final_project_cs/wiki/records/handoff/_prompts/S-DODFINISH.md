# 구현 지시 — 부분통과 DoD 5건의 재측정 원문 수집

## 0. 역할 — ★사실만 모은다. 판정하지 않는다

`RULE.md` §3.6-5 — **"통과/미통과" 판단은 검수 담당이 한다.**
★`wiki/records/evidence/DoD-NN_*.md`(판정 파일)를 **절대 만들거나 고치지 마라.**
당신이 쓰는 것은 `wiki/records/evidence/_raw/DoD-NN_v3.md` 뿐이다.
★**"통과", "정상 동작" 같은 판단어를 쓰지 마라.** 숫자와 출력만.

## 1. 왜 재측정하나

아래 5건은 **부분통과** 인데, 그 뒤에 구조가 바뀌었다.

| DoD | 부분통과 사유 | 그 뒤 무슨 일이 있었나 |
|---|---|---|
| 04 | `agent_runs` 가 비어 실행 관측 없음 | ★**composition root 조립됨** — REST 요청이 Controller 를 탄다 |
| 05 | 절삭 동작 관측 없음 | `tests/unit/core/test_context_budget.py` 추가, 전역 제거순서 구현 |
| 10 | 실데이터 급증 alert 미관측 | `tests/unit/voc/test_feedback_runtime.py` 추가 |
| 11 | 승인 종단·`unknown` 미검증 | Controller/Executor 조립 완료 |
| 18 | 시나리오가 화면에 안 보임 | composition root + 분류기 배선 완료 |

현재: **128 passed, 0 failed, skipped 0**.

## 2. 소유 범위

```
wiki/records/evidence/_raw/**       ← v3 파일만
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/**`, `tests/**`, `eval/**`, `knowledge/**`, `scripts/**`, `config/**`,
`wiki/records/handoff/**`, `wiki/records/submission/**`, `wiki/records/evidence/` 의 `_raw/` 밖 파일.

## 3. 수집할 것 — `wiki/records/evidence/_raw/DoD-NN_v3.md` 5개

형식은 이전 v2 파일과 동일하다:
`## 재현 명령` / `## 실제 출력` / `## 관측 사실` / `## 확인하지 못한 것`

### DoD-04 — checkpoint / projection 분리
★**REST 로 Case 를 만든 뒤** `agent_runs` 를 조회하라 (composition root 가 붙었으니 행이 생겨야 한다).
- `select run_id, graph_revision, status from agent_runs where tenant_id=...`
- 한 run 안에서 `graph_revision` 이 **변하지 않는지**
- checkpoint 에 담기는 키 목록

### DoD-05 — ContextPack 절삭
- `python -m pytest tests/unit/core/test_context_budget.py -v` 출력
- ★`ContextBroker.build()` 를 **예산 초과 입력**으로 직접 돌려
  `estimated_input_tokens` 와 `omissions` **전체를 순서대로** 출력

### DoD-10 — VOC 급증
- `python -m pytest tests/unit/voc -v` 출력
- `python -m scripts.run_daily_feedback --date <오늘>` 출력
- ★**실제 Case 를 임계 이상 만들어** alert 가 나오는지 (테스트 tenant 사용, 끝나면 삭제)

### DoD-11 — 승인 · idempotency · unknown
- `python -m pytest tests/integration/api tests/integration/controller -v` 출력
- ★**동일 요청 10회 → `action_requests` 몇 행인지** DB 직접 조회
- ★승인 종단: `waiting_approval` → approve → `resolved` 까지의 **status·version 순서**
- provider timeout → `unknown` 경로가 코드에 있는지 (`git grep`)

### DoD-18 — UI 종단
- ★시나리오 Case 를 **`waiting_approval` 까지 만들고 삭제하지 않은 채**
  `/ui/cases`·`/ui/cases/{id}`·`/ui/approvals` 를 호출해
  **그 Case 가 화면 본문에 나타나는지** (HTML 에서 case_id 문자열 검색)
- trace 화면에 이벤트가 **version 순으로** 나오는지
- 끝나면 테스트 데이터를 정리하라

## 4. 규칙

- ★**명령을 실제로 돌려라.** 안 돌린 것은 "확인하지 못한 것" 에 적는다
- ★실제 LLM 호출이 필요하면 **fake 주입**. 이 환경은 외부망이 막혀 있다
  (`APIConnectionError`) — 못 돌린 것은 그대로 적어라
- ★**`demo` tenant 를 오염시키지 마라.** 만든 데이터는 지운다
- 테스트를 새로 만들거나 고치지 마라

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 5. 완료 조건

```powershell
Get-ChildItem docs\evidence\_raw\*_v3.md | Measure-Object     # 5개
python -m pytest tests -q                                     # 128 passed 유지
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```
기대: 5개 파일, **128 passed**, `tenants=1`.

## 6. 리포트

`wiki/records/reports/2026-08-14_S-DODFINISH_리포트.md` — 수집 5항목,
**돌리지 못한 명령과 이유**.

## 7. 하지 말 것
- ❌ 판정 파일 생성·수정 / 판단어 사용
- ❌ 안 돌린 명령의 출력을 지어내기
- ❌ `demo` tenant 오염
- ❌ 테스트 수정
