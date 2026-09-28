# 구현 지시 — trace 화면 결함 + ablation 5종 실행 준비 + DoD-05/10 실측

세 가지를 한 번에 한다. 서로 소유 범위가 겹치지 않는다.

## A. trace 화면에 Case 가 나타나지 않는다 (DoD-18)

### 실측
```
/ui/cases        case_id_exact = True
/ui/cases/{id}   case_id_exact = True
/ui/approvals    case_id_exact = True
trace            case_id_exact = False, case_id_prefix = False   ← ★
trace version 검색 위치 = [1396, 1609, 1880, 2124]   (이벤트 4건은 렌더링됨)
Case 상태 = ('waiting_approval', 4)
events = created/1, classified/2, routed/3, approval_required/4
```

이벤트 4건은 화면에 있는데 **`case_id` 문자열이 본문에 없다.**
DoD-18 은 "Case UI·trace·approval·VOC 가 **시나리오를 끝까지 보여준다**" 를 요구한다.
trace 가 어느 Case 의 것인지 화면에서 알 수 없으면 그 요구를 못 채운다.

### 고칠 것
- trace 화면에 **어느 Case 의 이력인지** 표시한다 (case_id, subject, 현재 status·version)
- 이벤트를 `aggregate_version` 순으로 보여주는 기존 동작은 유지
- ★append-only 임이 드러나야 한다 — 수정/삭제 버튼을 만들지 마라

### 소유 범위 (A)
```
app/presentation/ui/**
tests/e2e/**
```

---

## B. ablation 5종 실행 준비 (DoD-15)

v5 §15-6 이 요구하는 5종: `no_context_broker` · `no_team_split` · `no_approval` ·
`no_rag` · `no_feedback_inline`.

`--ablation` 옵션은 이미 있다(`eval/runners/common.py`). ★**실제로 각 flag 가
그 기능을 끄는지** 확인하고, 안 끄면 고쳐라.

### 확인·수정할 것
| flag | 무엇이 꺼져야 하나 |
|---|---|
| `no_rag` | 정책 검색을 하지 않는다 → `policy_evidence` 가 비고 `degraded` 표시 |
| `no_context_broker` | ContextPack 조립 없이 원문만 넘긴다 |
| `no_team_split` | 두 Team 을 나누지 않고 하나로 처리 |
| `no_approval` | 승인 대기 없이 바로 응답 |
| `no_feedback_inline` | 인라인 분류를 건너뛴다 |

★각 flag 가 **결과 행의 `config.ablations` 에 기록**되는지 확인하라.
★**전량 실행은 하지 마라** — 외부망이 막혀 있다. `--dry-run` 으로 호출 수만 확인하고,
실행은 검수 담당이 한다.

### 소유 범위 (B)
```
eval/runners/**
eval/tests/**
```
★`eval/reports/*.jsonl` 을 **지우지 마라** — 평가 결과 원본이다.

---

## C. DoD-05 · DoD-10 실측 원문 (판정하지 마라)

★`wiki/records/evidence/DoD-NN_*.md`(판정 파일)를 **만들거나 고치지 마라.**
`wiki/records/evidence/_raw/DoD-05_v4.md`, `DoD-10_v4.md` 만 쓴다.
★**"통과" 같은 판단어 금지.** 숫자와 출력만.

### DoD-05 — ContextPack 절삭
```powershell
python -m pytest tests/unit/core/test_context_budget.py -v
```
그리고 ★`ContextBroker.build()` 를 **예산 초과 입력**으로 직접 돌려
`estimated_input_tokens` 와 `omissions` **전체를 순서대로** 출력하라.

### DoD-10 — VOC 급증
```powershell
python -m pytest tests/unit/voc -v
python -m scripts.run_daily_feedback --date <오늘>
```
그리고 ★테스트 tenant 에 **실제 Case 를 임계 이상 만들어** alert 가 나오는지.
끝나면 그 데이터를 지워라. `demo` 는 건드리지 마라.

### 소유 범위 (C)
```
wiki/records/evidence/_raw/**   (v4 파일만)
```

---

## 공통 금지

★위 A·B·C 소유 범위 **밖 전부 금지**: `app/core/**`, `app/domain/**`,
`app/modules/**`, `app/application/**`, `app/composition.py`,
`app/presentation/api/**`, `knowledge/**`, `config/**`, `scripts/**`,
`wiki/records/handoff/**`, `wiki/records/submission/**`, `wiki/records/evidence/` 의 `_raw/` 밖.

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지(fake 주입).
테스트 전용 tenant, teardown 삭제, `demo` 보존.

## 완료 조건

```powershell
python -m pytest tests -q
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 1 --seed 7 --provider openai --limit 2 --ablation no_rag --dry-run
Get-ChildItem docs\evidence\_raw\*_v4.md | Measure-Object
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```
기대: **130건 이상, 0 failed, skipped 0**, ablation dry-run 정상, `_v4.md` 2개, `tenants=1`.

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 리포트

`wiki/records/reports/2026-08-14_S-TRACE-ABL_리포트.md` — A·B·C 각각의 변경/관측,
★**ablation flag 중 실제로 기능을 끄지 않던 것이 있었다면 그게 핵심 산출물이다.**

## 하지 말 것
- ❌ trace 에 수정/삭제 기능 추가
- ❌ ablation 전량 실행
- ❌ 평가 결과 원본 삭제
- ❌ 판정 파일 생성·수정 / 판단어 사용
- ❌ 소유 범위 밖 수정
- ❌ 돌려보지 않고 "완료"
