# MCP 버전 회귀의 계산 제공자와 Team 비활성 조회 검증

MCP 버전 변경·되돌림 시험은 계산 부재를 우회하는 대신 명시적인 시험 계산 제공자를 조립하도록 수정했습니다. 모든 Team을 꺼도 저장된 여행을 조회하는 제품 경로가 유지됨을 로컬 앱·DB에서 확인했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 변경·추가 시나리오 | 통과 | 2/2 = 100% |
| 수정한 MCP 파일 전체 회귀 | 통과 | 16/16 = 100% |
| 정적 검사 | 통과 | 1/1 파일 = 100% |

두 시나리오는 전체 16항목에 포함되므로 합쳐 18항목이라고 세지 않습니다. 전체 Team 인수 시나리오 24개나 운영 완료율이 아닙니다.

## 변경

[MCP 종단 시험](../../../tests/e2e/test_mcp_server.py)의 기존 `_leg_engine=None` monkeypatch를 제거했습니다. 판 교체 시험은 이전 계산 표를 보존한 별도 Controller 사본에 시험용 구간 계산·도보 정책·출처를 명시하고, 같은 Registry와 revision으로 새 BindingTable을 게시합니다. 제품의 계산기 부재 거절을 복원하거나 해제하지 않았습니다.

시험 제공자는 고정 5분 구간을 만들며 각 호출에서 좌표 입력·출발 하한·도착 목표와 시작/종료·경로 형식을 확인합니다. 호출 이력이 실제로 존재하고 5분 일치인지 시험이 단언합니다. 이 값은 버전 처리 회귀를 고정하기 위한 시험 자료이며 실제 서울 경로 정확도나 운영 이동시간 근거가 아닙니다.

신규 시나리오는 여행을 먼저 저장한 뒤 여섯 Team 모두를 비활성으로 조립해 게시합니다. 등록표의 실행 가능 값 전부 false와 빈 계산 표를 확인한 상태에서 다음을 실행합니다.

- 실제 제품 입구 `GET /v1/web/trips/{id}`가 200이며 기존 version·item id를 유지합니다.
- `/health`가 200이고 다른 이용자의 키는 기존 여행에 404를 받습니다.
- MCP 프로토콜의 `tripilot_get_trip`도 같은 여행·판을 읽습니다.

수정 전 파일은 [원본 보존 폴더](../../../legacy/team_plugin_mcp/2026-10-11_2115/tests/e2e/)에 복사했습니다. 변경은 시험 파일 하나로 한정했습니다.

## 검증과 한계

```powershell
python -m pytest tests/e2e/test_mcp_server.py::test_swap_and_rollback_use_the_current_version_and_a_stranger_gets_404 tests/e2e/test_mcp_server.py::test_saved_trip_remains_readable_with_every_team_disabled -q --tb=short
python -m pytest tests/e2e/test_mcp_server.py -q --tb=short
python -m ruff check tests/e2e/test_mcp_server.py
```

[대상 시나리오 원문 로그](../evidence/2026-10-11_1936_team_plugin_implementation/mcp-product-regression.log)는 2항목 통과, [파일 전체 원문 로그](../evidence/2026-10-11_1936_team_plugin_implementation/mcp-file-regression.log)는 16항목 통과입니다. 기존 MCP SDK의 `streamablehttp_client` 이름 변경 권고 경고가 있었고 실패는 없습니다. [정적 검사](../evidence/2026-10-11_1936_team_plugin_implementation/mcp-product-lint.log)와 [시험 파일 해시](../evidence/2026-10-11_1936_team_plugin_implementation/mcp-product-source-hash.json)도 보존했습니다.

mock 서버 시험: 해당 없음(화면 반응을 검증하지 않았습니다).

실서버 확인(서버 응답): 로컬 개발 서버의 실제 앱 처리 코드와 PostgreSQL을 SDK·ASGI 내부 전송으로 실행했습니다. 운영 중인 cs 프로젝트 서버의 네트워크·배포 응답은 확인하지 않았습니다. 시험 계산 제공자는 시험에서만 사용하며 지도·교통 제공자 API를 호출하지 않았습니다.

관련 계약: [Team 수명 관리](../../teams/team-plugin-lifecycle.md), [실행 가용성](../../teams/team-contract/plugin-availability.md). 운영 배포와 Claude 독립 검토는 상위 통합 기록에서 별도 판정합니다.
