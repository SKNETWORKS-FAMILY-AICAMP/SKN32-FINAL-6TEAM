# 구현 지시 — Core 격리 위반 + 계약 테스트가 그것을 못 잡는다

## 0. 결함 2건

### 결함 1 — `app/core/` 가 `app/presentation/` 을 import 한다

```
app/core/transition.py:32
    from app.presentation.security import mask_json
```

★**Core 는 바깥 계층을 import 하지 않는다.** v5 §7-5 와
`wiki/records/handoff/07_모듈화_구조.md` §1(Core Runtime 축)의 전제다.
Basement 주장("무엇이든 올릴 수 있다")을 정면으로 깬다 —
Core 를 떼어 쓰려면 `presentation` 을 통째로 끌고 와야 한다.

PII 마스킹 작업 때 들어온 것으로 보인다.

### 결함 2 — ★계약 테스트가 `app.modules` 만 본다

`tests/contract/test_core_isolation.py:5`
```python
def test_core_does_not_import_modules():
    assert not any(name == "app.modules" or name.startswith("app.modules.") ...)
```

`app.presentation` · `app.infrastructure` 는 **검사하지 않는다.**
그래서 결함 1 이 통과했다. **검사하지 않는 규칙은 지켜지지 않는다.**

## 1. 소유 범위

```
app/core/**
app/presentation/security.py     (함수 이동 시 원위치에 re-export)
tests/contract/test_core_isolation.py
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/modules/**`, `eval/**`(★평가 실행 중), `knowledge/**`,
`config/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 2. 고칠 것

### 2-1. `mask_json` 을 Core 안으로 옮긴다

마스킹은 **도메인 규칙**이지 표현 계층 관심사가 아니다
(설계 원칙 §1 — "PII 는 저장 시 masking"). 예: `app/core/redaction.py`.

- `app/core/transition.py` 가 **Core 내부 모듈**을 import 하게 한다
- ★`app/presentation/security.py` 는 **기존 이름을 re-export** 로 남긴다
  (`from app.core.redaction import mask_json`) — 호출부가 깨지지 않게
- ★**re-export 방향은 옛 경로 → 새 경로 단방향**이다.
  새 위치(`app/core/redaction.py`)가 `app.presentation` 을 참조하면 순환이 된다.
  지난번 모듈화가 이걸로 실패했다
  (`wiki/records/reports/debugs/2026-08-13_1400_모듈화가_순환import로_실패했다.md`)

### 2-2. ★계약 테스트를 실제 규칙에 맞게 넓힌다

`tests/contract/test_core_isolation.py` 가 `app/core/**` 의 모든 `.py` 를 AST 로 파싱해
아래를 **전부** 금지하게 한다:

```
app.modules        (기존)
app.presentation   ← 신규
app.infrastructure ← 신규
app.application    ← 신규
```

★**위반 파일과 import 이름을 메시지에 담아라.** 어디가 문제인지 즉시 보이게.
★`app.core.*` 내부 import 와 표준 라이브러리·서드파티는 허용한다.

★단 **`psycopg` 직접 import 는 지금 허용**한다 — `transition.py` 가 psycopg 연결을 받는 것은
의도된 설계다(S-DB 스트림 구현 세부에 묶이지 않기 위해). 이건 별도 판단 사항으로 남긴다.

## 3. 완료 조건

```powershell
python -m pytest tests -q
python -m pytest tests/contract/test_core_isolation.py -v
```

기대: **126건 이상, 0 failed, skipped 0** (live 는 deselected).
★그리고 **넓힌 테스트가 실제로 위반을 잡는지** 증명하라 —
일부러 `app/core/` 어딘가에 `from app.presentation... ` 를 넣어 테스트가 실패하는지 확인하고,
**되돌린 뒤** 결과를 리포트에 적어라.

## 4. 리포트

`wiki/records/reports/2026-08-13_S-ISOLATION_리포트.md` — 옮긴 함수, re-export 위치,
넓힌 검사 범위, **일부러 위반을 넣었을 때 테스트가 잡았는지**.

## 5. 하지 말 것
- ❌ Core 가 바깥 계층을 import 하는 상태 유지
- ❌ 새 위치가 `app.presentation` 을 역참조 (순환)
- ❌ 기존 호출부 깨기 (re-export 유지)
- ❌ 검사 범위를 넓히지 않고 위반만 고치기 — **둘 다 해야 한다**
- ❌ `eval/**` 열기
- ❌ 돌려보지 않고 "완료"
