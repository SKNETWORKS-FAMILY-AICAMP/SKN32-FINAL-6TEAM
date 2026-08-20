# S-DOD17-AUTOMATED-GATE 리포트

## 변경

- `scripts/check_release_gate.py`를 추가했다.
- DoD-17의 재현 명령을 `python -m scripts.check_release_gate`로 갱신했다.
- 게이트는 순서대로 비-live pytest, 기존 `scripts.verify_dod`, 동결 대상 diff를 검사하고 단계별 pass/fail과 실패 항목을 stdout에 출력한다.
- DoD-17 및 `RULE.md`의 계약·기능 동결 규칙에 따라 `app/core/contracts.py`와 `docs/handoff/01_계약_Pydantic.md`를 동결 대상으로 삼았다. 두 파일 모두 최근 커밋 `HEAD` 이후 변경이 없어야 통과한다.

## 검증

### 현재 상태 실행

실행 명령:

```powershell
python -m scripts.check_release_gate
```

결과: **실패(exit code 1)**.

- pytest: `311 passed, 3 failed, 10 errors, 3 deselected` (게이트 요약 기준)
- `python -m scripts.verify_dod`: pytest 및 DoD evidence 판정 조건 미충족으로 실패
- 기능 동결: 통과 — 동결 대상 2개 파일의 HEAD 이후 변경 없음

따라서 현재 작업 트리에서 게이트가 성공하는 성공 케이스는 재현되지 않았다. 게이트는 기존 실패를 통과로 위장하지 않고 non-zero를 반환한다.

### 임시 실패 주입 검증

게이트의 실패 전파를 확인하기 위해 `tests/unit/test_composition_root.py`에 임시 `assert False` 테스트를 추가한 뒤 `python -m scripts.check_release_gate`를 실행했다. pytest 요약의 실패 수가 `3 failed`에서 `4 failed`로 증가하고 게이트가 non-zero로 종료되는 것을 확인한 후, 해당 테스트를 즉시 제거하여 파일을 원상복구했다.

테스트 코드와 계약 자체에는 영구 변경을 남기지 않았다.
