# Codex — DoD 실측 원문 수집 (`wiki/records/evidence/_raw/`)

## 0. 역할 분담 (★중요)

**당신은 사실을 모은다. 판정은 하지 않는다.**

`RULE.md` §3.6-5 — 계약 테스트를 Codex 가 쓴 코드로 Codex 가 통과시키지 않는다.
그래서 **"통과/미통과" 판단은 Claude 가 한다.** 당신은 **명령을 돌리고 출력을 그대로 옮긴다.**

★`wiki/records/evidence/DoD-NN_*.md` 는 **절대 만들거나 고치지 마라.** 그건 Claude 소유다.
당신이 쓰는 것은 `wiki/records/evidence/_raw/DoD-NN.md` 뿐이다.

## 1. 소유 범위

```
wiki/records/evidence/_raw/**       ← 이번 산출물
wiki/records/reports/ , wiki/records/history/
```
★그 밖 **전부 금지**. `app/**`, `tests/**`, `eval/**`, `knowledge/**`, `scripts/**`,
그리고 `wiki/records/evidence/` 의 `_raw/` 밖 파일.

## 2. 만들 것 — 항목별 실측 파일

아래 12개 각각에 대해 `wiki/records/evidence/_raw/DoD-NN.md` 를 만든다.
**형식은 전부 동일**하다:

```markdown
# DoD-NN 실측 원문 (수집: Codex, 판정 없음)

## 재현 명령
```powershell
<그대로 붙여 돌릴 수 있는 명령>
```

## 실제 출력
```
<원문 그대로. 길면 앞뒤를 자르되 "…N줄 생략" 이라고 적는다>
```

## 관측 사실
- <숫자·파일경로·테스트명 등 사실만>
- <"통과했다" 같은 판단 문장을 쓰지 마라>

## 확인하지 못한 것
- <돌려보지 못했거나 관측 불가한 것>
```

### 수집 대상 12항목

| # | 무엇을 실측하나 | 힌트 |
|---:|---|---|
| 04 | LangGraph checkpoint 와 `customer_cases` projection 분리 | `agent_runs.graph_revision` 저장 여부, checkpoint 에 무엇이 들어가는지, checkpoint 로 업무 상태를 되돌리는 코드가 있는지 |
| 05 | ContextPack ≤ 12,000 token + omissions | `tests/contract/test_contracts.py` 의 예산 테스트, 실제 `ContextBroker.build()` 를 큰 입력으로 돌려 `estimated_input_tokens`·`omissions` 출력 |
| 07 | tenant/customer scope + PII redaction | `tests/security` 실행, `tenant_id` 없는 조회 쿼리 검색, PII 마스킹 코드 위치 |
| 08 | TeamModule Protocol·manifest 호환 | `tests/contract/test_team_contract.py`, `test_core_isolation.py` 실행 |
| 09 | 인라인 분류가 **모든** Case 생성에서 실행 | `POST /v1/cases` 후 `customer_cases.intent/issue_code/sentiment` 채워짐, 실패 시 `classification_failed` 이벤트 |
| 10 | 일일 배치 report | `python -m scripts.run_daily_feedback --date ...` 출력, `feedback_analytics_reports` 건수, 급증 경계값 테스트 |
| 13 | REST 5 + MCP 3 이 문서와 일치 | `/openapi.json` 의 `/v1/*` 경로, MCP tool 3개 이름·scope |
| 14 | API key scope 구분 | `tests/security` 의 unauthorized matrix 결과 (scope × endpoint 표) |
| 15 | A/B/Proposed 60×3 + holdout 20 | golden/holdout 건수, runner 파일 존재, **전량 실행 여부** — ★안 돌렸으면 "안 돌렸다"고 적어라 |
| 16 | bootstrap CI · McNemar · 한계 서술 | `python -m eval.stats.bootstrap --input eval/reports/sample_raw.jsonl --n 10000` 출력, `mcnemar` 출력, 리포트 템플릿에 한계 절이 있는지 |
| 17 | 마일스톤 gate | `git log --oneline` 전문, 각 커밋이 어느 Phase 인지 |
| 18 | UI 4화면 | uvicorn 띄우고 `/ui/cases` `/ui/approvals` `/ui/voc` `/ui/cases/{id}` HTTP 코드 + 렌더 본문 일부 |

## 3. 규칙

- ★**명령을 실제로 돌려라.** 안 돌린 것은 "확인하지 못한 것"에 적는다
- ★**"통과", "정상 동작", "문제 없음" 같은 판단어를 쓰지 마라.** 숫자와 출력만
- ★**출력을 다듬지 마라.** 실패하면 실패 출력을 그대로 붙인다
- ★UI 확인 후 **띄운 서버를 반드시 종료**하라
- ★테스트를 새로 만들거나 고치지 마라

## 4. 완료 조건

```powershell
Get-ChildItem docs\evidence\_raw\*.md | Measure-Object    # 12개
python -m scripts.verify_dod                              # 참고용 (여전히 MISSING 이 정상)
```

★`verify_dod` 결과가 좋아지지 않아도 정상이다 — 판정 파일은 Claude 가 쓴다.

## 5. 리포트

`wiki/records/reports/2026-08-12_S-EVIDENCE_실측수집_리포트.md` — 수집한 12항목 목록,
**돌리지 못한 명령과 그 이유**. `wiki/records/history/2026-08-12_S-EVIDENCE.md` 이력 추가.

## 6. 하지 말 것

- ❌ `wiki/records/evidence/DoD-NN_*.md` (판정 파일) 생성·수정
- ❌ 판단어 사용 / 출력 각색
- ❌ 안 돌린 명령의 출력을 지어내기
- ❌ 소유 범위 밖 수정
