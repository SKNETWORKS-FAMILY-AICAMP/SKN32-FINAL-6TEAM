# 구현 지시 — provider timeout 이 `unknown` 으로 남고 자동 재실행되지 않는지 증명

## 0. 무엇이 미검증인가

`wiki/records/evidence/DoD-11_action_idempotency_승인.md` 의 미통과 2줄:

| 항목 | 상태 |
|---|---|
| ★**provider timeout → `unknown` 종단 동작** | **미검증** — 코드 경로는 있으나 실제로 timeout 을 주입해 `unknown` 으로 남는지 확인하지 않았다 |
| ★`unknown` 자동 재실행 금지 | **미검증** |

★**"코드에 경로가 있다" 와 "그 경로가 실제로 밟힌다" 는 다른 주장이다.**
이 프로젝트에서 그 차이로 6번 당했다 (분류기 미연결·RAG 검색 전건 실패·Team LLM 미호출 등).
`git grep` 으로 `status='unknown'` 을 찾은 것은 증거가 아니다.

`CLAUDE.md` §0.2 가 정한 규칙이 이것이다:
> provider timeout 을 **성공으로 추정하지 않는다.** `unknown` 으로 남기고 자동 재실행하지 않는다.

현재 기준선: **153 passed, 0 failed, skipped 0**.

## 1. 소유 범위

```
tests/**
app/application/**        ← 필요 최소한만. 결함이 있으면 고쳐라
app/infrastructure/**     ← 동
wiki/records/reports/ , wiki/records/evidence/_raw/
```
★금지: `app/core/**`, `app/domain/**`, `config/guardrails.yaml`, `config/project.yaml`,
`eval/**`, `knowledge/**`, `wiki/records/handoff/**`, `wiki/records/evidence/DoD-*.md`(판정은 Claude 가 쓴다).

## 2. 증명할 것

**실제로 timeout 을 주입해서** 다음 셋을 관측하라. 세 개 전부 DB 조회로 확인한다.

1. ★provider 호출이 timeout 하면 `action_requests.status` 가 **`unknown`** 이 된다
   — `success` 도 `failed` 도 아니다. **실패로 단정하는 것도 오답이다** (돈이 이미 나갔을 수 있다)
2. ★`unknown` 인 행이 **자동으로 재실행되지 않는다** — worker/controller 를 다시 돌려도
   provider 를 다시 호출하지 않고 `action_requests` 행이 늘지 않는다
3. ★Case 가 timeout 을 **성공으로 전이시키지 않는다** — `resolved` 로 가지 않는다

주입 방법은 네가 정해라. 단 ★**실제 실행 경로를 타야 한다.**
`unknown` 을 테스트가 직접 DB 에 써넣고 "관측했다" 고 하면 그건 증명이 아니다.
provider 어댑터 경계에서 `TimeoutError`(혹은 실제 사용하는 예외)를 내고,
그 위의 **애플리케이션 코드가 스스로 `unknown` 을 기록**해야 한다.

★**만약 실제로 해 보니 `unknown` 이 안 되거나 자동 재실행이 일어난다면
그것이 결함이다. 감추지 말고 고치고, 무엇이 틀렸는지 리포트에 써라.**
(이 프로젝트는 결함 발견을 성과로 친다 — `wiki/records/reports/debugs/` 13건)

## 3. 테스트

`tests/integration/` 에 추가. ★`pytest.skip` 금지. 실제 LLM·외부 네트워크 호출 금지.
기존 153건이 그대로 통과해야 한다.

각 테스트는 **DB 를 조회해 단언**하라 — 모킹한 반환값을 단언하는 것은 증명이 아니다.

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **153건 이상, 0 failed, skipped 0**.

## 5. 리포트

- `wiki/records/evidence/_raw/DoD-11_timeout.md` — ★**실측 원문만.** 판정 문장 쓰지 마라.
  - timeout 주입 지점(파일:줄)
  - 주입 후 `action_requests` 행 원문 (status·attempts·idempotency_key)
  - 재실행 후 행 수 **전/후 비교**
  - Case 상태·version
- `wiki/records/reports/2026-08-14_S-TIMEOUT_리포트.md` — 주입 방법, 고친 결함(있다면), §4 출력 원문

## 6. 하지 말 것
- ❌ `unknown` 을 테스트가 DB 에 직접 써넣고 "관측"이라 하기
- ❌ timeout 을 `failed` 로 처리하고 통과라 하기
- ❌ `git grep` 결과를 증거로 제출하기
- ❌ 결함을 찾고 감추기
- ❌ 판정 문장(`통과`/`미통과`)을 `_raw/` 에 쓰기
