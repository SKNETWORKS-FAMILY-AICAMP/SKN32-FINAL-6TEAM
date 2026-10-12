# 구현 지시 — `idempotency_key` 를 v5 §10-1 산식으로 (안전 규약)

## 0. 결함

`app/modules/customer_ops/billing.py`:
```python
idempotency_key = uuid5(NAMESPACE_URL, str(task.task_id) + ":refund").hex
```

**v5 §10-1 이 정한 산식:**
```
idempotency_key = sha256(tenant_id + request_id + action_type + business_subject)
```

★키가 **`task_id`** 에 걸려 있어 run 이 바뀌면 키가 달라진다.
실측(`wiki/records/evidence/DoD-11_action_idempotency_승인.md`):
승인 후 Controller 를 재실행하자 **같은 업무 행위(환불 제안)에 새 행이 하나 더 생겼다.**

**생성 경로의 중복은 막지만, run 을 가로지르는 중복은 막지 못한다.**
v5 산식이면 `UNIQUE(tenant_id, idempotency_key)` 가 막았을 것이다.

★이건 **환불·결제 중복 방지의 실체**다. `설계 원칙 §0.2`(승인 없이 실행하지 않는다)와
같은 급의 안전 규약이다.

`technical.py` 도 같은 구조인지 확인하고 함께 고쳐라.

## 1. 소유 범위

```
app/modules/customer_ops/billing.py
app/modules/customer_ops/technical.py
app/core/                       (키 계산 유틸이 필요하면 여기. Core 격리 유지)
app/presentation/api/**         (서버 재계산이 필요하면)
tests/**
wiki/records/reports/ , wiki/records/history/
```
★금지: `app/core/contracts.py`(계약 모델), `app/domain/**`, `eval/**`,
`knowledge/**`, `config/**`, `scripts/**`, `wiki/records/handoff/**`, `wiki/records/evidence/**`, `wiki/records/submission/**`.

## 2. 고칠 것

### 2-1. 산식을 v5 §10-1 로

```
idempotency_key = sha256(tenant_id + request_id + action_type + business_subject)
```

- `business_subject` 는 **그 행위의 대상**이다 (예: 환불이면 `case_id` 또는 결제 식별자).
  ★무엇을 골랐는지 **리포트에 근거와 함께** 적어라
- `request_id` 는 요청 단위 식별자다. **`task_id` 를 쓰지 마라** — run 마다 바뀐다
- 길이 제약 유지: `Field(min_length=8, max_length=128)` (`app/core/contracts.py`)

### 2-2. ★서버가 재계산한다

계약 문서(`wiki/records/handoff/01_계약_Pydantic.md` §5)가 이미 정하고 있다:
> `idempotency_key` 는 Team 이 제안한 값이 아니라 **서버가 재계산한 값이 최종**이다.

- Team 이 낸 값을 그대로 믿지 말고, **action 을 기록하는 지점에서 재계산**한다
- ★키 계산 함수를 **한 곳**에 두고 Team·서버가 같은 함수를 쓰게 한다
- Core 격리 유지 — `app/core/**` 가 `app.modules`/`app.presentation` 을 import 하면 안 된다
  (`tests/contract/test_core_isolation.py` 가 검사한다)

## 3. 테스트

1. ★**run 을 가로지르는 중복 차단** — 승인 후 Controller 재실행 시
   `action_requests` 가 **늘지 않는다** (지금은 는다)
2. 기존 통과 유지: 동일 생성요청 10회 → `action_requests` **1행**
3. ★**다른 Case·다른 action_type 은 서로 다른 키**를 갖는다 (과도한 병합 방지)
4. 키가 계약 길이 제약(8~128) 안이다

★`pytest.skip` 금지. 실제 LLM·네트워크 호출 금지(fake 주입).
테스트 전용 tenant, teardown 삭제, `demo` 보존.

## 4. 완료 조건

```powershell
python -m pytest tests -q
```
기대: **130건 이상, 0 failed, skipped 0** (live 는 deselected).

PG 가 죽어 있으면:
```powershell
$data="C:\Users\playdata2\Documents\llm_workspace\_unified_mall_3\data\pgdata"
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\pg_ctl.exe" -D $data -o "-p 5433" -l "$data\server_5433.log" start
```

## 5. 리포트

`wiki/records/reports/2026-08-14_S-IDEMKEY_리포트.md` — 새 산식, `business_subject` 로 무엇을 골랐고 왜,
서버 재계산 지점, §3 테스트 결과 원문.

## 6. 하지 말 것
- ❌ `task_id` 기반 키 유지
- ❌ Team 이 낸 키를 그대로 사용
- ❌ 키 계산 로직을 두 곳에 두기
- ❌ Core 격리 위반
- ❌ 기존 테스트 단언 약화
- ❌ 돌려보지 않고 "완료"
