# 구현 지시 — 발표 시나리오 Case 를 화면에 남기는 스크립트

## 0. 무엇이 미검증인가

`wiki/records/evidence/DoD-18_UI_시나리오_종단표시.md`:

| 항목 | 상태 |
|---|---|
| ★**시나리오 1·2 의 Case 가 화면에 실제로 보이는가** | **미검증** — Case 목록이 비어 있다 |
| ★**Trace 가 7단계 전이를 화면에 보여주는가** | **미검증** |
| ★**Approval 화면에서 실제 proposal 을 승인해 종단 완료** | **미검증** |

원인은 명확하다. Controller 통합테스트가 두 시나리오를 코드로 끝까지 통과시키지만
**그 Case 들은 teardown 에서 삭제된다.** 화면에는 아무것도 안 남는다.

DoD-18 이 요구하는 것은 화면이 200 을 내는 것이 아니라
**"발표 시나리오를 끝까지 보여주는 것"** 이다.

현재 기준선: **153 passed, 0 failed, skipped 0**.

## 1. 소유 범위

```
scripts/seed_demo_cases.py     ← 새로 만든다
tests/**
wiki/records/reports/ , wiki/records/evidence/_raw/
```
★금지: `app/**`(결함을 찾으면 리포트에 쓰고 고치지 마라 — 별도 발주한다),
`config/**`, `eval/**`, `knowledge/**`, `wiki/records/handoff/**`, `wiki/records/evidence/DoD-*.md`.

## 2. 만들 것 — `python -m scripts.seed_demo_cases`

demo tenant 에 **발표용 Case 2건을 남긴다.** 실행 후 삭제하지 않는다.

- **시나리오 1** (해지 후 결제 → 환불 제안 → 승인 → 종단):
  `classifying(1)→routing(2)→running(3)→waiting_approval(4)` **까지만** 만든다.
  ★**승인은 하지 마라.** 발표에서 사람이 `/ui/approvals` 에서 직접 누를 것이다.
- **시나리오 2** (Pro/Free 권한 불일치): `→resolved(4)` 까지 종단 완료.

★**반드시 `transition_case()` 를 통해서만** 상태를 만들어라 (`CLAUDE.md` §0.3).
`customer_cases` 직접 `UPDATE` 금지. `case_events` 가 append-only 로 쌓여야
trace 화면이 7단계를 보여줄 수 있다.

★**재실행 안전해야 한다.** 두 번 돌려도 Case 가 4건이 되지 않는다.
기존 demo Case 를 지우고 다시 만들든, 이미 있으면 건너뛰든 — 방식은 네가 정하고 리포트에 써라.

★LLM 을 호출하지 마라. 분류 결과·proposal 은 고정값으로 주입하되
**어디서 온 값인지 Case 에 남겨라** (`CLAUDE.md` §1 — 지어내지 않는다. 근거를 필드에 남긴다).
seed 로 만든 Case 임이 데이터에서 구분돼야 한다.

## 3. 확인 — ★띄워서 HTTP 로 본다

```powershell
Start-Process -NoNewWindow python -ArgumentList "-m","uvicorn","app.presentation.api.app:app","--port","8041"
Start-Sleep 8
curl.exe -s http://127.0.0.1:8041/ui/cases       # ★Case 2건이 본문에 보이는가
curl.exe -s http://127.0.0.1:8041/ui/approvals   # ★시나리오1 proposal 이 보이는가
curl.exe -s http://127.0.0.1:8041/ui/cases/<시나리오1 id>   # ★trace 4단계
curl.exe -s http://127.0.0.1:8041/ui/cases/<시나리오2 id>   # ★trace 4단계 + resolved
```

★**HTTP 200 만 확인하고 끝내지 마라.** 이 프로젝트에서 그 검증이 이미 한 번 통과됐고
그래도 화면은 비어 있었다. **응답 본문에 Case id·상태·전이 단계가 실제로 들어 있는지**
grep 해서 리포트에 원문으로 붙여라.

★확인 후 서버를 종료하라.

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **153건 이상, 0 failed, skipped 0**.
★`pytest.skip` 금지.

## 5. 리포트

- `wiki/records/evidence/_raw/DoD-18_seed.md` — ★**실측 원문만.** 판정 문장 쓰지 마라.
  - 생성된 Case id 2건 + 최종 상태·version
  - `case_events` 행 (aggregate_version 순서)
  - §3 의 **응답 본문 grep 원문** (Case id 가 보이는 줄)
  - 재실행 후 Case 수 (전/후)
- `wiki/records/reports/2026-08-14_S-DEMO-SEED_리포트.md` — 재실행 안전 방식, 발견한 결함(고치지 말고 기록)

## 6. 하지 말 것
- ❌ `customer_cases` 직접 UPDATE
- ❌ 시나리오 1 을 승인까지 끝내기 (발표에서 누를 것이 없어진다)
- ❌ HTTP 200 만 보고 "화면에 보인다" 고 하기
- ❌ 재실행하면 Case 가 늘어나는 스크립트
- ❌ 판정 문장을 `_raw/` 에 쓰기
- ❌ `app/**` 수정
