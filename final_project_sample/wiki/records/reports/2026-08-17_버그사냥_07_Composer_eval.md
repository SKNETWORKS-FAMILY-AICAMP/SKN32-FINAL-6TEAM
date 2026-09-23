# 버그사냥 07 — Composer 쓰기채널·eval/stats

범위: `app/application/composer_service.py`, `app/presentation/api/composer.py`, `eval/stats/bootstrap.py`, `eval/stats/mcnemar.py`, `eval/stats/agreement.py`.
코드 수정은 하지 않았다.

### app/application/composer_service.py:107-113 — `os.replace()` 실패 시 staged 임시 파일이 남는다
- 시나리오: 유효한 후보를 `apply_candidate()`에 전달하고 `staged.write_text()`까지 성공한 뒤 `os.replace(staged, target)`가 `OSError`를 던지면, `finally`는 `candidate_path`만 삭제한다. `.write.<uuid>.yaml` staged 파일은 작업 디렉터리에 남는다. 반복되는 디스크 오류나 권한 문제에서 임시 파일이 누적된다.
- 왜 기존 테스트가 못 잡는가: 기존 apply 테스트는 정상 저장과 검증 실패만 다루며, `os.replace()` 실패를 주입하지 않는다. 예외 경로의 디렉터리 잔여 파일도 검사하지 않는다.
- 재현 시도: 실제로 `os.replace`를 `OSError`를 던지도록 주입해 재현했다. 후보 파일은 없어졌지만 `.project.write.<uuid>.yaml` 파일이 남았다.
- 위험도: 보통

### app/application/composer_service.py:38, 91-113 — revision 검사 락이 프로세스 로컬이라 다중 워커에서 낙관적 동시성이 원자적이지 않다
- 시나리오: 두 API 요청이 서로 다른 프로세스/서버 워커에서 같은 `base_revision`으로 동시에 들어오면, 각 프로세스의 `_WRITE_LOCK`은 서로 다른 객체다. 두 요청 모두 같은 현재 revision을 읽고 검사를 통과한 뒤 각각 `os.replace()`를 수행할 수 있다. 둘 다 200이 되고 마지막 replace가 먼저 저장된 변경을 덮어쓴다. 단일 프로세스의 스레드 경합만 막는다.
- 왜 기존 테스트가 못 잡는가: `tests/e2e/test_composer_write_channel.py`의 동시성 테스트는 같은 프로세스 안의 두 스레드만 사용한다. 이 경우에는 공유 `threading.Lock` 때문에 [200, 409]가 나온다.
- 재현 시도: 재현 안 해봄, 코드 읽기로만 판단. `threading.Lock`이 프로세스 간 공유되지 않는 구조와 `base_revision` 검사·replace 사이에 파일/DB 수준의 공유 잠금 또는 조건부 쓰기가 없는 것을 확인했다.
- 위험도: 높음

### eval/stats/bootstrap.py:23-30 — 확인 결과 버그 아님: 재표본추출과 seed 재현성
- 시나리오: `[1.0, 2.0, 5.0]`에 같은 `n`과 `seed`를 두 번 적용하면 각 bootstrap draw가 같은 순서로 생성되어 mean과 CI가 동일하다. `random.Random(seed)`가 함수 내부에서 새로 생성되므로 전역 RNG 상태에도 의존하지 않는다.
- 왜 기존 테스트가 못 잡는가: 기존 테스트는 알려진 입력의 한 번의 CI만 확인하고, 같은 seed를 두 번 호출한 결과의 동일성은 직접 확인하지 않는다.
- 재현 시도: 실제로 같은 입력에 `seed=7`을 두 번 적용했고 결과가 동일했다. `choice()`를 사용한 재표본추출도 입력 길이만큼 반복되어 무작위 재표본을 수행한다.
- 위험도: 낮음

### eval/stats/mcnemar.py:11-50 — 확인 결과 버그 아님: exact/chi-square 경계와 코너 케이스
- 시나리오: discordant pair가 0개이면 exact p=1.0으로 종료하고, `(0, 1)` 및 전부 한 방향인 `(0, 24)`는 exact 분기로 계산한다. threshold가 25일 때 `(0, 25)`는 chi-square continuity-corrected 분기로 전환한다. 분기 조건 `< threshold`는 guardrail의 “25 미만 exact” 정의와 일치한다.
- 왜 기존 테스트가 못 잡는가: 기존 테스트는 `(3, 1)`, `(3, 5)`, `(0, 40)`만 확인하며 0건과 정확히 25건 경계를 확인하지 않는다.
- 재현 시도: 실제 실행에서 `(0,0)→(0.0, 1.0, exact)`, `(0,24)→exact`, `(0,25)→chi-square`, `(3,5)→exact`를 확인했다. 잘못된 값이나 예외는 재현되지 않았다.
- 위험도: 낮음

### eval/stats/agreement.py:54-63 — 확인 결과 버그 아님: Cohen's kappa 상수 라벨 분기
- 시나리오: 표준식 `κ=(P_o-P_e)/(1-P_e)`을 사용하며, 두 평가자가 같은 하나의 카테고리만 사용하면 `expected==1.0`이고 완전 일치이므로 1.0을 반환한다. 한쪽만 상수이거나 서로 다른 상수이면 expected가 1.0이 아니므로 표준식의 결과 0.0을 반환한다.
- 왜 기존 테스트가 못 잡는가: 기존 agreement 테스트에는 일반적인 완전 일치/불일치와 다중 카테고리만 있고, 단일 카테고리 및 서로 다른 상수 카테고리 경계가 없다.
- 재현 시도: 실제로 `['a'],['a']→1.0`, `['a'],['b']→0.0`, 반복된 동일 상수 라벨→1.0을 확인했다. 표준식과 불일치하지 않는다.
- 위험도: 낮음

## 검증

```powershell
python -m pytest -q
```

실행 결과: `346 passed, 3 failed, 1 deselected`.

실패한 3건은 모두 `tests/integration/rag/test_rag_integration.py`에서
OpenAI Embeddings API(`api.openai.com`) 연결을 시도하다가 네트워크 권한
오류(`WinError 10013`)로 실패했다. 이번 검토 대상 코드의 테스트 실패는
확인되지 않았다.
