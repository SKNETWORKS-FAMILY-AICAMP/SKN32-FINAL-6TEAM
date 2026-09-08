# 구현 지시 — Controller 가 capability 를 하드코딩해 새 Team 이 라우팅되지 않는다

## 0. 결함 (Basement 구조검사 결과)

`wiki/records/reports/2026-08-13_Basement_구조검사.md` 의 결론:

> 이 저장소는 Team 계약과 Local/A2A 실행 계약의 뼈대는 있으나,
> **"무엇이든 올릴 수 있는 Basement" 주장은 부분적으로만 성립**한다.

> ★**가장 먼저 부러질 곳**: Controller 의 `_capability()` 가
> **두 capability 만 알고 있다** (`app/application/controller.py`)

★`TeamModule` Protocol 은 열려 있는데 **라우팅이 닫혀 있다.**
새 Team 을 등록해도 Controller 가 그 capability 를 모르면 선택되지 않는다.
4축 판정이 전부 "부분" 인 **유일한 공통 원인**이다.

## 1. 소유 범위

```
app/application/controller.py
app/core/registry.py
tests/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/contracts.py`, `app/domain/**`, `app/modules/**`,
`app/presentation/**`, `eval/**`(★평가 실행 중), `knowledge/**`,
`config/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 2. 고칠 것

### 2-1. capability 해석을 Registry 조회로 바꾼다

지금 `Controller._capability()` 는 capability 를 **하드코딩**한다.
이것을 **Registry 에 물어보는 방식**으로 바꾼다.

`TeamManifest` 에는 이미 필요한 정보가 있다:
- `capabilities: list[str]`
- `accepted_case_types: list[str]`
- `active: bool`

Registry 가 `intent`/`case_type` → **등록된 Team 중 처리 가능한 것**을 찾아 주게 한다.
Controller 는 **어떤 Team 이 있는지 몰라야 한다.**

```python
# 예시 시그니처 (실제 코드에 맞춰 조정)
def resolve(self, *, case_type: str, intent: str | None = None) -> TeamManifest | None: ...
```

### 2-2. 지켜야 할 것

- ★**Core 격리 유지**: `app/core/registry.py` 가 `app.modules` 를 import 하면 안 된다.
  Team 은 **주입**받아 등록한다. `tests/contract/test_core_isolation.py` 가 검사한다
- ★`supported_contract_versions` 확인은 유지한다 (v5 §7-4)
- ★해석 실패 시 **조용히 기본값으로 넘어가지 마라** — `escalated` 로 보낸다
  (`app/domain/events.py` 의 `ROUTING_FAILED`)
- ★기존 두 Team 의 라우팅 동작이 **그대로여야 한다**

## 3. 테스트

1. ★**새 Team 을 하나 더 등록하면 라우팅된다** — 기존 두 Team 을 건드리지 않고
   fake Team(capability `demo.investigate`, case_type `demo`)을 등록해
   Controller 가 그것을 선택하는지 확인
2. 처리 가능한 Team 이 없으면 `ROUTING_FAILED` → `escalated`
3. `active=False` 인 Team 은 선택되지 않는다
4. 기존 Billing/Technical 라우팅이 그대로 동작한다

★**1번이 이 작업의 핵심이다.** "새 Team 을 코드 수정 없이 올릴 수 있다" 를 증명한다.

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **123건 이상, 0 failed, skipped 0** (live 는 deselected).

★그리고 리포트에 **"새 Team 추가 시 고쳐야 할 파일 수"** 를 다시 세어 적어라.
구조검사가 "최소 2개(Team 모듈 + composition root)" 라고 했다.
이 수정 후 그 숫자가 어떻게 되는지가 성과 지표다.

## 5. 리포트

`wiki/records/reports/2026-08-13_S-CAPABILITY_리포트.md` — 변경 전후 `_capability()` 비교,
새 Team 추가 시 고칠 파일 수, §3 테스트 결과 원문.

## 6. 하지 말 것
- ❌ Registry 가 `app.modules` 를 import (격리 위반)
- ❌ 해석 실패를 기본 Team 으로 폴백
- ❌ 기존 두 Team 라우팅 동작 변경
- ❌ `eval/**` 열기 (평가 실행 중)
- ❌ 테스트 단언 약화
- ❌ 돌려보지 않고 "완료"
