---
type: contract
title: Team 실행 가용성과 조립 판
status: draft
domain: neutral
---

# Team 실행 가용성과 조립 판

`TeamRegistry.require_runnable(team_id, capability=None)`이 실행 객체를 얻는 관문입니다. `get`은 메타데이터 조회입니다. 비활성·부재·선택 로딩 실패를 `disabled`, `not_installed`, `load_failed`로 구분하고 `TeamUnavailable`로 거절합니다. HTTP는 `team_unavailable` 503이며 SSE·MCP도 같은 실패 의미를 유지합니다. 원격 일시 불가만 재시도 가능으로 표시합니다.

Team 선언의 `required`는 활성 구현의 로딩 실패 정책입니다. 비활성 구현은 required여도 import하지 않습니다. capability 중복·manifest 계약 major 불일치는 후보 조립 오류이며 조용히 격리하지 않습니다. TeamTask/TeamResult 전송 필드 계약은 이 내부 변경으로 판올림하지 않습니다.

Controller는 담당·capability를 task 생성과 답변·토큰 반영 전에 확인합니다. 실행 도중 필요해진 다른 Team의 필수 계산은 그 계산 관문에서 별도로 확인합니다. Core에 여행별 의존 관계를 하드코딩하지 않습니다. Local/A2A 모두 관문을 거치고 A2A 결과의 team_id/task_id/run_id를 대조합니다.

Registry·Executor·계산 hook·Controller·revision을 같은 조립 판에 고정합니다. 준비 실패한 판은 게시하지 않습니다. 기존 요청은 이전 판으로 끝나며 새 요청은 새 판을 사용합니다. 담당 부재나 활성 엔진 미준비를 직선거리 추정·빈 결과·완료 상태로 바꾸지 않습니다.

Dining의 이름·메뉴·방문구간·식당 UID 연결은 고정된 Dining hook을 사용합니다. 관광 콘텐츠 번호가 없고 정확히 일치하는 내부 가게 번호만 있는 개선도 Dining 구현 안에 유지합니다. 접수 컴포넌트가 직접 원장 SQL로 실행 관문을 우회하지 않습니다. Mobility 경로선 계산도 필수 hook을 사용하며 저장된 계획서 자체의 읽기와 구분합니다.

제품 판 밖에서 독립 계산을 시험하려면 명시적 `standalone_services`를 사용합니다. 시나리오 재생용 `service_overrides`는 꺼진 Team을 활성화하지 않습니다. 기록되지 않은 경로를 임의의 시간으로 성공시키지 않습니다.

같은 답변의 동시 재개에서 다른 요청이 실행권을 먼저 얻으면 현재 상태를 멱등 응답합니다. 실제 복구 실행권을 얻은 요청은 실행 결과를 그대로 반환합니다. 활성 실행의 복구·만료는 기존 Case 실행 계약을 따릅니다.

[수명주기](../team-plugin-lifecycle.md), [가용성 회귀](../../../tests/integration/controller/test_plugin_unavailable.py), [조립 판 시험](../../../tests/unit/test_plugin_composition_runtime.py).
