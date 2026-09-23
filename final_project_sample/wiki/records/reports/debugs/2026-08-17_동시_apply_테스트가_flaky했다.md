# 동시 apply 테스트가 flaky 했다

## 위치
`tests/e2e/test_composer_write_channel.py::test_concurrent_apply_one_wins_one_gets_409`

## 재현
```powershell
python -m pytest tests -q
```
전체 스위트(`tests` 디렉터리를 명시해 collect)로 돌리면 간헐적으로 실패한다.
같은 테스트만 단독으로 돌리면(`pytest tests/e2e/test_composer_write_channel.py::...`)
3회 연속 통과해서 처음엔 "격리해서 도니까 문제없다"로 보였다 — **이게 함정이었다.**
전체 스위트 안에서는 스레드 스케줄링에 더 많은 경합이 걸려 문제가 노출된다.

## 실측
```
FAILED tests/e2e/test_composer_write_channel.py::test_concurrent_apply_one_wins_one_gets_409
assert [200, 200] == [200, 409]
  At index 1 diff: 200 != 409
1 failed, 313 passed, 1 deselected in 19.81s
```
(재현 명령: `python -m pytest tests -q`, 2026-08-17, 커밋 `48ebaa3` 위)

## 원인
`apply_candidate()` 의 낙관적 동시성은 **`revision`(내용 해시)이 실제로 바뀌었는지**로
충돌을 감지한다 — `revision = sha256(config 의 canonical JSON)`. 테스트가 두 번째
스레드에 보낸 payload 가 **원본 `current["config"]` 를 그대로(수정 없이)** 다시 보냈다:

```python
t2 = threading.Thread(target=_apply, args=(1, current["config"]))  # 수정 없음!
```

이 payload 를 쓰면 파일 내용이 바뀌지 않으므로 **revision 도 바뀌지 않는다.**
그래서 스레드 스케줄링 순서에 따라:
- 무수정 payload 가 **먼저** 쓰이면: 파일 내용·revision 이 그대로다 → **뒤에 오는
  실제 수정 payload 도 여전히 원래 revision 과 일치**해서 통과해 버린다 → `[200, 200]`
- 실제 수정 payload 가 먼저 쓰이면: revision 이 바뀐다 → 무수정 payload 는 stale
  revision 으로 막힌다 → `[200, 409]` (테스트가 기대한 결과)

**운영 코드(`composer_service.apply_candidate`)의 낙관적 동시성 자체는 정상이다.**
결함은 테스트가 "내용이 바뀌지 않는 쓰기"를 동시성 케이스로 잘못 구성한 것이다 —
`RULE.md` §4.1 이 요구하는 것처럼 고쳤는지와 무관하게 기록한다.

## 위험도
운영 영향 없음(테스트 전용 결함). 다만 이걸 놓쳤으면 "동시 apply 검증됨"이라고
잘못 보고할 뻔했다 — CLAUDE.md 가 반복 경고하는 "검사하는 척하는 검사" 패턴이다.

## 정정
두 payload 모두 원본과 다르게(그리고 서로 다르게) 만들어 어느 순서로 실행되든
반드시 revision 이 바뀌게 고쳤다 — `tests/e2e/test_composer_write_channel.py` 의
`payload_a`/`payload_b` 를 각각 다른 team 의 `active` 를 토글하도록 수정.

## 부가 발견 — `scripts/verify_dod.py` 가 `eval/tests/` 를 건너뛰고 있었다

이 결함을 조사하다가 별개의 결함을 하나 더 찾았다: `scripts/verify_dod.py` 가
`pytest tests -q` 로 **`tests/` 디렉터리만** 돈다. 그런데 `eval/tests/test_stats_and_datasets.py`
에 7건이 `eval/tests/` 아래 있어서, **병합 게이트(`RULE.md` §5)가 이 7건을 전혀
검사하지 않고 있었다.** 그래서 verify_dod 의 테스트 수도 314(전체 315-1)로,
전체 스위트(321 passed/322)보다 7건 적게 나왔다 — flaky 진단 초기에 두 숫자가
안 맞아 헷갈렸던 원인이다.

```powershell
python -m pytest -q --collect-only                 # 322개 (eval/tests 포함)
python -m pytest tests -q --collect-only            # 315개 (eval/tests 제외)
```

`scripts/verify_dod.py::_run_tests()` 의 pytest 호출에서 `"tests"` 경로 인자를
제거해 `pytest.ini` 의 rootdir 발견 규칙을 그대로 따르게 고쳤다 — 이제 전체를 돈다.
