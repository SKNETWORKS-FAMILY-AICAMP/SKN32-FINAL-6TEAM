# 구현 지시 — DoD 재측정 원문 수집 (수정된 항목들)

## 0. 역할 — ★사실만 모은다. 판정하지 않는다

`RULE.md` §3.6-5 — 계약 테스트를 구현 담당이 스스로 통과시키지 않는다.
**"통과/미통과" 판단은 검수 담당이 한다.** 당신은 **명령을 돌리고 출력을 그대로 옮긴다.**

★`wiki/records/evidence/DoD-NN_*.md` (판정 파일)를 **절대 만들거나 고치지 마라.**
당신이 쓰는 것은 `wiki/records/evidence/_raw/DoD-NN_v2.md` 뿐이다.

## 1. 왜 재측정하나

아래 항목들은 **판정 문서가 작성된 뒤에 실제로 고쳐졌다.** 문서가 낡았다.

| DoD | 판정 당시 상태 | 그 뒤 무슨 일이 있었나 |
|---|---|---|
| 07 | PII redaction 미검증 | **PII 마스킹 구현됨** — `tests/security/test_pii_redaction_runtime.py` 통과 |
| 09 | 분류기가 API 에 미연결 → 전 Case `escalated` | **배선 수정됨** — `create_app()` 이 분류기 주입 |
| 05 | 절삭 동작 관측 없음 | **`tests/unit/core/test_context_budget.py` 추가됨** — 전역 제거 순서 구현 |
| 10 | 실데이터 급증 alert 미관측 | **`tests/unit/voc/test_feedback_runtime.py` 추가됨** |
| 04 | `agent_runs` 가 비어 실행 관측 없음 | Controller 통합테스트는 통과 중. **`demo` tenant 에 남는 run 이 있는지 재확인 필요** |

현재 상태: **123 passed, 0 failed, skipped 0**.

## 2. 소유 범위

```
wiki/records/evidence/_raw/**      ← 이번 산출물 (v2 파일만)
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **전부 금지**: `app/**`, `tests/**`, `eval/**`(★평가 실행 중), `knowledge/**`,
`scripts/**`, `config/**`, `wiki/records/handoff/**`, `wiki/records/submission/**`,
그리고 `wiki/records/evidence/` 의 `_raw/` 밖 파일.

## 3. 수집할 것 — 5개 파일

`wiki/records/evidence/_raw/DoD-04_v2.md`, `DoD-05_v2.md`, `DoD-07_v2.md`,
`DoD-09_v2.md`, `DoD-10_v2.md`

**형식은 전부 동일하다:**

```markdown
# DoD-NN 재측정 원문 (수집: 구현 담당, 판정 없음)

## 재현 명령
```powershell
<그대로 붙여 돌릴 수 있는 명령>
```

## 실제 출력
```
<원문 그대로. 길면 자르되 "…N줄 생략" 이라고 적는다>
```

## 관측 사실
- <숫자·파일경로·테스트명 등 사실만>
- <"통과했다" 같은 판단 문장을 쓰지 마라>

## 확인하지 못한 것
- <돌려보지 못했거나 관측 불가한 것>
```

### 항목별 무엇을 실측하나

| DoD | 실측 대상 |
|---|---|
| **04** | `agent_runs` 에 행이 있는지 · `graph_revision` 값이 채워졌는지 (`demo` tenant 기준). checkpoint 에 담기는 키 목록 |
| **05** | `tests/unit/core/test_context_budget.py` 실행 결과 + `ContextBroker.build()` 를 큰 입력으로 돌려 `estimated_input_tokens` 와 `omissions` **실제 출력**. omissions 의 **순서**를 그대로 옮겨라 |
| **07** | `tests/security` 실행 결과 + ★**PII 를 넣은 Case 를 만들어 `customer_cases`·`case_events` 에 원문이 남는지 DB 직접 조회** |
| **09** | ★`POST /v1/cases` 후 `customer_cases` 의 `intent`/`issue_code`/`sentiment` **값**과 `status`. `case_events` 에 `classified` 가 있는지 |
| **10** | `python -m scripts.run_daily_feedback --date <오늘>` 출력 + `tests/unit/voc` 실행 결과 + `feedback_analytics_reports` 건수 |

★**분류기·LLM 실호출이 필요한 경우 fake 를 주입**하라. 이 환경은 외부 네트워크가 막혀 있다
(`APIConnectionError`). 실호출이 필요해 못 돌린 항목은 **"확인하지 못한 것"** 에 적어라.

## 4. 규칙

- ★**명령을 실제로 돌려라.** 안 돌린 것은 "확인하지 못한 것" 에 적는다
- ★**"통과", "정상 동작", "문제 없음" 같은 판단어를 쓰지 마라.** 숫자와 출력만
- ★**출력을 다듬지 마라.** 실패하면 실패 출력을 그대로 붙인다
- ★**`demo` tenant 를 오염시키지 마라.** 테스트용 데이터를 만들면 지운다

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 5. 완료 조건

```powershell
Get-ChildItem docs\evidence\_raw\*_v2.md | Measure-Object    # 5개
python -m pytest tests -q                                    # 123 passed 유지
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```
기대: 5개 파일, **123 passed**, `tenants=1`.

## 6. 리포트

`wiki/records/reports/2026-08-13_S-REMEASURE_리포트.md` — 수집한 5항목,
**돌리지 못한 명령과 그 이유**.

## 7. 하지 말 것
- ❌ `wiki/records/evidence/DoD-NN_*.md` (판정 파일) 생성·수정
- ❌ 판단어 사용 / 출력 각색
- ❌ 안 돌린 명령의 출력을 지어내기
- ❌ `eval/**` 열기 (평가 실행 중)
- ❌ `demo` tenant 오염
