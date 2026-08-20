# S-DOD17-AUTOMATED-GATE — 마일스톤 게이트를 사람이 손으로 재현하는 절차에서 자동 스크립트로

## 0. 배경

- `docs/evidence/DoD-17_마일스톤_게이트.md` — 지금 "재현 명령"이 `git log
  --oneline` + `python -m pytest tests -q` 를 **사람이 손으로** 실행하는
  절차다. CI gate 라고 부를 만한 프로그래밍적 단일 명령/스크립트가 없다.
- `scripts/verify_dod.py`(있다면, 정확한 경로 직접 확인) 처럼 이 저장소엔
  이미 "한 방에 검사하고 pass/fail exit code 를 내는" 스크립트 패턴이
  있다 — 그 패턴을 따라라, 새 프레임워크를 들여오지 마라.

## 1. 할 일

`scripts/check_release_gate.py`(또는 기존 `scripts/verify_dod.py` 가 있다면
그 옆에 붙는 자연스러운 이름으로) 를 만들어 다음을 **한 명령으로** 순서대로
검사하고, 하나라도 실패하면 non-zero exit code 로 끝나게 해라:

1. `python -m pytest tests -q -m "not live"` 실행 — 0 failed 인지 확인
2. `python -m scripts.verify_dod`(있다면) 실행 — evidence 파일 전부 존재하는지
3. **기능 동결(feature freeze) 위반 검사** — `git diff` 로 다음 파일들이
   최근 커밋 이후 무단 변경되지 않았는지 확인: `app/core/contracts.py`
   의 전이표 관련 정의, `docs/handoff/01_계약_Pydantic.md`. (정확히 어떤
   파일을 "동결 대상"으로 볼지는 `docs/evidence/DoD-17_마일스톤_게이트.md`
   와 `RULE.md` 를 읽고 판단해라 — 근거 없이 임의로 정하지 마라.)
4. 각 단계의 결과를 사람이 읽을 수 있는 요약으로 stdout 에 출력한다
   (몇 개 통과, 몇 개 실패, 실패한 항목 이름).

이 스크립트가 곧 "게이트"다 — 실행해서 exit code 0 이 나오면 게이트
통과, 아니면 실패다. 이게 지금까지 없던 "재현 가능한 단일 명령"이다.

## 2. 검증

- 스크립트를 실제로 실행해서 성공 케이스(현재 상태에서 pass)를 리포트에
  붙여라.
- 일부러 하나를 깨뜨려서(예: 테스트 파일에 임시로 `assert False` 하나
  추가) 스크립트가 실제로 non-zero exit code 로 실패를 잡아내는지 확인한
  뒤, **반드시 원상복구**하고 그 과정도 리포트에 적어라.

## 3. 쓰기 대상

- `scripts/check_release_gate.py` (신규)
- `docs/evidence/DoD-17_마일스톤_게이트.md` — "재현 명령" 섹션을 새 스크립트
  실행 명령으로 갱신(판정 자체는 건드리지 마라, Claude 가 한다)
- `docs/reports/2026-08-20_S-DOD17-AUTOMATED-GATE_리포트.md` (신규)

## 4. 하지 말 것

- 실제 CI(GitHub Actions 등) 워크플로 파일을 새로 만들지 않는다 — 로컬
  스크립트까지만이다(이 프로젝트엔 아직 CI 인프라가 없다)
- 테스트 코드나 계약 자체를 수정하지 않는다
