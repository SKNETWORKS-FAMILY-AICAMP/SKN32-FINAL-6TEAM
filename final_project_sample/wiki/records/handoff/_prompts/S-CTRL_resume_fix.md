# Codex — S-CTRL 수정 1건: `resuming` 에서 `resumed` 를 건너뛴다

## 0. 잘한 것 (그대로 유지)

지난 작업에서 테스트 8종을 전부 작성했고 **7건 통과**, 1건이 **진짜 제품 결함**을 잡았다.
★**제품 코드를 고치지 않고 정확히 보고했다.** 그게 맞는 행동이었다.

## 1. 고칠 것 — 딱 이거 하나

```
InvalidTransition: 허용되지 않은 전이:
  resuming --completed--> ?  (가능한 이벤트: ['resumed', 'resume_failed'])
```

**원인** (당신 리포트가 정확했다):
REST approve 가 `APPROVED` 로 `waiting_approval → resuming`(version 5)까지 만든다.
그 뒤 Controller 가 Team 결과를 **`COMPLETED` 로 곧장 적용**하는데,
v5 §5-1 상 `resuming` 의 다음은 `running`(`resumed`) 또는 `escalated`(`resume_failed`) 뿐이다.

`controller.resume()` (controller.py:169)은 `RESUMED` 를 올바르게 발행한다.
**승인 경로가 그 함수를 타지 않는 것**이 문제다.

**고치는 법**: Controller 메인 루프가 Team 결과를 적용하기 **전에** Case 상태를 확인해,
`CaseStatus.RESUMING` 이면 먼저 `EventType.RESUMED` 를 발행해 `running` 으로 옮긴다.
`resume_node` 는 `RESUME_NODE_FOR_WAIT[wait_reason]` 로 정한다 (이미 import 돼 있다).

상세: `wiki/records/reports/debugs/2026-08-12_2230_Controller가_resuming에서_resumed를_건너뛴다.md`

## 2. 소유 범위

```
app/application/controller.py          ← 수정 대상
app/application/case_service.py        ← 필요하면
wiki/records/reports/ , wiki/records/history/
```

★그 밖 **전부 금지**. 특히:
- `app/core/**`, `app/domain/**` — ★**전이표를 고쳐서 통과시키지 마라.**
  `resuming --completed` 를 전이표에 추가하는 것은 **v5 §5-1 위반**이다
- `tests/**` — ★**테스트를 느슨하게 고쳐서 통과시키지 마라.**
  기대 전이 순서 단언을 지우거나 완화하는 것은 결함 은폐다
- `app/presentation/**`, `app/modules/**`, `knowledge/**`, `eval/**`

## 3. 완료 조건

```powershell
python -m pytest tests -q                        # ★107 passed, skipped 0, failed 0
python -m pytest tests/integration/controller -v
python -m scripts.run_outbox_worker --once
$psql="$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe"
& $psql -h 127.0.0.1 -p 5433 -U postgres -d acop -tAc "select 'tenants='||count(*) from tenants"
```

★시나리오 1의 전이 순서가 아래로 관측돼야 한다:
```
classifying(1) → routing(2) → running(3) → waiting_approval(4) → resuming(5) → running(6) → resolved(7)
```
`tenants=1`, **skipped 0**.

## 4. 리포트

`wiki/records/reports/2026-08-12_S-CTRL_resume수정_리포트.md` — 변경 내용(diff 요약),
§3 명령의 **실제 출력 원문**, 시나리오 1·2 의 전이 순서.
`wiki/records/history/2026-08-12_S-CTRL_resume_fix.md` 이력 추가.

## 5. 하지 말 것

- ❌ `app/domain/events.py` 전이표에 `resuming --completed` 추가
- ❌ 테스트의 전이 순서 단언 삭제·완화
- ❌ 소유 범위 밖 수정
- ❌ 다른 기능 추가 (이번엔 이 결함 하나만)
- ❌ 명령을 돌리지 않고 "동작함"
