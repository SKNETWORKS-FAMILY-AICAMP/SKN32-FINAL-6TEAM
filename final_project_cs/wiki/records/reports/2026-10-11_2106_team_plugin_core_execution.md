# Team 실행 관문·A2A 검증 구현 결과

비활성·부재·선택 적재 실패 Team의 실행 우회를 막고, A2A 업무 결과의 식별자 검사를 전송·원격 응답까지 연결했습니다. 로컬 코드 검증 결과이며 운영 반영 완료 보고가 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 코어·A2A 실행 경계 구현 | 완료 | 1/1 = 100% |
| 해당 경계 회귀 시험 | 통과 | 61/61 = 100% |
| 운영 배포·실기계 확인 | 이 스트림에서 미실행 | 0/1 = 0% |

## 계약과 변경

[실행 가용성 계약](../../teams/team-contract/plugin-availability.md)을 적용했습니다. Controller·조립·hook·외부 오류 연결은 다른 스트림이 맡으며 이 결과만으로 전체 기능 완료를 선언하지 않습니다.

- Registry는 `require_runnable(team_id, capability=None)`에서 disabled·not_installed·load_failed를 운영 실패로 구분합니다. 메타데이터 `get`은 유지합니다. `declare_unavailable`은 구현 없는 선언과 이미 적재된 Team의 hook 적재 실패를 지원하고, `availability()`는 원본을 변경할 수 없는 복사 상태표를 반환합니다.
- zero-provider의 비어 있지 않은 case_type은 `TeamUnavailable(..., not_installed)`로 거절합니다. 빈 case_type·모호한 제공자·capability 중복·계약 major 불일치는 선언/계약 오류로 유지합니다. 다른 Team에 조용히 재배정하여 업무를 대행하지 않게 하는 정책입니다.
- TeamConfig에 `required=True`, `capabilities=None`, `hooks=None` 호환 필드를 추가했습니다. 정적 선언 검증에서는 구현 import를 하지 않습니다. 실제 로딩과 선언/manifest 대조는 조립 스트림의 책임입니다.
- Local/A2A 실행기는 동일한 등록표 관문과 tool scope를 검사합니다. ToolScopeViolation은 RuntimeError 계열로 분리했습니다. A2A는 registry 없이 실행할 수 없으며 조립에서 명시적으로 주입해야 합니다.
- A2A artifact의 team/task/run 식별자 누락·불일치와 알 수 없는 완료 상태를 거절합니다. unavailable은 별도 운영 실패로 보존하고 resolver 구현 예외를 unavailable로 숨기지 않습니다. 비동기 resolver 대기는 deadline에 포함됩니다.
- HTTP 제출은 기존 식별자 세 개를 전달하며 여행 원격 simulator는 artifact에 그대로 돌려줍니다. 원격 상태 조회용 id와 업무 task id를 혼동하지 않습니다. HTTP 통합의 입력→재개 완료 artifact를 실행기 매핑으로 검증합니다.
- 취소의 추가 대기는 `reliability.a2a_cancel_timeout_seconds=1`로 제한합니다. 이 값은 실측 SLA가 아닌 운영 한도입니다. 취소 시간 초과는 고객 문장 없이 예외 종류·team/task/run만 운영 로그에 남기며 원래 deadline 실패를 보존합니다.

## 검증

실행 명령:

```powershell
python -m pytest tests/unit/core/test_plugin_availability.py tests/unit/ports/test_team_ports.py tests/integration/a2a/test_travel_remote_round_trip.py tests/unit/core/test_registry_capability_default.py tests/unit/core/test_case_subject_routing.py -q
```

실제 결과: **61 passed in 3.60s**. [원문 로그](../evidence/2026-10-11_1936_team_plugin_implementation/core-ports-http-round6.log). 코드 린트와 해당 파일 `git diff --check`도 통과했습니다. Windows 제한 환경의 asyncio socketpair 정지 문제로 로컬 단위 시험은 승인된 제한 외 실행으로 확인했습니다.

이번 시험은 등록표·실행기 직접 시험과 in-process ASGI HTTP 통합입니다. x600 서버의 cs 프로젝트 서버는 호출·배포하지 않았고, 실제 외부 A2A 기계와 네트워크 단절·부분 응답까지 검증한 결과가 아닙니다. 네이티브 프로세스 중단이나 취소를 무시하는 외부 구현까지 완전 격리한다고 보장하지 않습니다.

초기 고정 fixture의 answer/evidence 계약 누락을 수정했고, 이전 2실패/50통과 로그와 후속 통과 로그를 함께 보존했습니다. 이는 제품이 실패를 통과로 바꾼 것이 아니라 검증용 입력을 기존 TeamResult 계약에 맞춘 수정입니다.

## 변경 파일과 보존

원본: [구현 전 백업](../../../legacy/team_plugin_lifecycle/2026-10-11_1936/). 계약은 수정 전 같은 폴더의 `_backup`에 별도 보존했습니다. 파일별 최종 내용은 [SHA256](../evidence/2026-10-11_1936_team_plugin_implementation/core-source-sha256-2106.json)으로 확인할 수 있습니다.

변경 파일: `app/core/team_availability.py`, `app/core/registry.py`, `app/core/project_config.py`, `app/core/remote_team/executor.py`, `app/core/remote_team/a2a_executor.py`, `app/infrastructure/a2a/http_transport.py`, `app/presentation/a2a/travel_remote_agent.py`, `config/guardrails.yaml`, `tests/unit/core/test_plugin_availability.py`, `tests/unit/ports/test_team_ports.py`, `tests/integration/a2a/test_travel_remote_round_trip.py`.

다음 확인은 전체 조립 판 고정·Controller 상태 저장 전 거절·JSON/SSE/MCP 오류 정합과 운영 환경 검증입니다. 이 스트림은 커밋·푸시·배포를 하지 않았습니다.
