# A2A 동기 호출의 제한시간 우회 수정

동기 endpoint 조회가 이벤트 루프를 막던 결함을 수정하고, 동기 transport는 원격 제출 전에 거절합니다. 기존 비동기 HTTP 왕복과 함께 검증했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 제한시간 우회 원인 재현 | 확인 | 2/2 = 100% |
| 수정 관련 회귀 시험 | 통과 | 52/52 = 100% |
| 운영 환경 반영 | 이 스트림에서 미실행 | 0/1 = 0% |

## 원인과 계약

기존 실행기는 `asyncio.wait_for` 안에서도 동기 resolver와 submit을 같은 이벤트 루프에서 직접 호출했습니다. 네트워크 없는 0.15초 sleep 재현에서 두 호출 모두 0.03초 제한을 넘겨 약 0.157초 뒤 정상 반환했고 다른 작업도 약 0.172초 지연됐습니다. [수정 전 실측](../evidence/2026-10-11_1936_team_plugin_implementation/sync-a2a-loop-block-audit-v2.json).

[가용성 계약](../../teams/team-contract/plugin-availability.md)에 먼저 동기/비동기 경계를 적었습니다. resolver는 외부 제출·상태 변경이 없는 순수 조회여야 합니다. transport의 존재하는 submit/send·poll/get_status·cancel은 async 함수여야 하며, 동기 factory가 awaitable을 반환하는 transport도 허용하지 않습니다. 동기 제출을 thread로 옮기면 기한 뒤 늦은 POST가 발생할 수 있으므로 그 방식은 사용하지 않습니다.

## 구현과 확인

- [A2A 실행기](../../../app/core/remote_team/a2a_executor.py)는 동기 resolver를 `asyncio.to_thread`로 호출하여 ContextVar의 조립 판을 전달합니다. awaitable 반환이면 요청 이벤트 루프에서 이어서 기다립니다. 비동기 resolver는 그대로 지원합니다.
- 기한이 지난 조회 결과는 원격에 제출하지 않습니다. 늦게 반환된 coroutine은 실행 없이 닫고, 늦게 실패한 조회 예외는 종류만 운영 로그로 소비합니다. 이미 시작한 thread를 강제로 취소한다고 보장하지 않습니다.
- transport 메서드는 제출 전 async 계약을 확인하고 동기 메서드는 실행 0회로 거절합니다. poll·cancel이 제공되는 경우도 같은 계약을 적용하며, 취소는 기존 제한시간 안의 best effort입니다.
- [회귀 시험](../../../tests/unit/core/test_plugin_availability.py)은 동기 조회 중 이벤트 루프 응답·기한 뒤 제출 0회·ContextVar thread 전파·awaitable 반환·동기 transport 세 종류 실행 0회·늦은 coroutine 정리를 확인합니다. 기존 비동기 Port와 ASGI HTTP 왕복도 함께 통과했습니다.

```powershell
python -m pytest tests/unit/core/test_plugin_availability.py tests/unit/ports/test_team_ports.py tests/integration/a2a/test_travel_remote_round_trip.py -q
```

실제 결과: **52 passed in 3.63s**. [시험 로그](../evidence/2026-10-11_1936_team_plugin_implementation/a2a-sync-contract-round9.log). 해당 코드 ruff와 git diff --check도 통과했습니다. [최종 파일 SHA256](../evidence/2026-10-11_1936_team_plugin_implementation/a2a-sync-sha256-2121.json).

초기 취소 시험은 30ms 안에 resolver thread를 처음 시작하는 조건까지 포함해 원격 제출 전 기한이 끝날 수 있었습니다. 취소 동작 시험은 비동기 resolver로 분리하고, thread 제한시간은 별도 시험으로 확인했습니다. 이 과정의 실패 로그도 보존했습니다.

수정 전 코드·시험은 각 파일 옆 `_backup/2026-10-11_2116_sync_a2a_timeout/`에, 계약은 같은 이름의 계약 폴더 백업에 보존했습니다. [실행기 백업](../../../app/core/remote_team/_backup/2026-10-11_2116_sync_a2a_timeout/), [시험 백업](../../../tests/unit/core/_backup/2026-10-11_2116_sync_a2a_timeout/), [계약 백업](../../teams/team-contract/_backup/2026-10-11_2116_sync_a2a_timeout/).

## 범위와 남은 확인

이 결과는 로컬 코드·단위 시험·in-process HTTP 통합입니다. x600 서버의 cs 프로젝트 서버에 배포하거나 외부 A2A 기계를 호출하지 않았습니다. async 함수 내부에서 동기 I/O를 강제로 수행하는 잘못된 외부 어댑터까지 안전하게 중단하는 기능은 없으므로, 어댑터 구현도 해당 계약을 따라야 합니다. Python thread 강제 중단이나 임의 네이티브 코드 격리를 보장하지 않습니다. 커밋·푸시·배포는 하지 않았습니다.
