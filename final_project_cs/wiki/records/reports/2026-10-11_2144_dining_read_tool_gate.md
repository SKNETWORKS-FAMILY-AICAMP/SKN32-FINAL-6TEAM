---
type: report
title: 요식 읽기 도구의 실행 관문 우회 차단
status: verified
domain: travel
---

# 요식 읽기 도구의 실행 관문 우회 차단

다른 담당이 읽기 도구로 꺼진 요식 계산을 직접 부르던 경로를 차단했습니다. 거절은 DB 연결을 열기 전에 이뤄집니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 수정 전·후 같은 호출 재현 | 확인 | 2/2 = 100% |
| 새 경계 회귀 | 통과 | 16/16 = 100% |
| 관련 단위 회귀 전체 | 통과 | 55/55 = 100% |
| 원장 SQL 통합 회귀 | 통과 | 3/3 = 100% |
| 기존 여행 요식 E2E | 조건으로 건너뜀 | 0/5 = 0% |

## 결함과 수정

[ReadToolbox](../../../app/tools/read_tools.py)의 `dining_state`·`dining_states`는 Team 구현을 직접 import하고 `dining_ledger` bool만 검사했습니다. Dining을 disabled로 선언한 고정 조립 판에서 Activity 문맥으로 허용된 도구를 호출해도 DB 연결과 원장 SQL이 각각 실행됐습니다. 실제 고객·DB에 연결하지 않고 합성 메모리 cursor를 사용한 실제 `.call` 경로 재현입니다.

이제 고정된 판에서 Dining 실행 관문과 state/states 제공자를 먼저 검사하고, 도메인의 team_hooks 호출로 계산합니다. 비활성·부재·적재 실패와 계산 제공자 누락은 연결 전에 거절합니다. `dining_ledger=False`도 bound 판의 비활성 담당을 우회하지 못합니다. 활성 판은 원래 인자·주문 여유를 같은 판의 제공자에게 전달합니다. standalone은 기존 명시적 경계를 유지합니다.

## 실행 근거와 한계

- [수정 전 재현](../evidence/2026-10-11_1936_team_plugin_implementation/readtool-disabled-dining-repro-v2.log): 두 도구 모두 `TeamUnavailable`을 거절하지 않고 연결·SQL 이벤트 2개씩 발생.
- [수정 후 같은 재현](../evidence/2026-10-11_1936_team_plugin_implementation/readtool-disabled-dining-after-fix.log): 두 도구 모두 disabled, 연결·SQL 이벤트 0개.
- [55건 단위 회귀 로그](../evidence/2026-10-11_1936_team_plugin_implementation/dining-read-tool-gate-v1.log): 55/55, 5.84초. ruff·공백 검사 통과.
- [원장 DB 검증 로그](../evidence/2026-10-11_1936_team_plugin_implementation/dining-read-tool-db-v1.log): 원장 SQL 3/3 통과. 기존 요식 E2E 5건은 시험이 만든 가게만 있는 DB를 요구하므로 현재 로컬 개발 DB에서 skip. 통과로 세지 않았습니다.
- mock 서버 시험: 사용하지 않았습니다. 메모리 SQL cursor 합성 시험과 로컬 개발 DB 통합 시험을 구분했습니다.
- 실서버 확인(서버 응답): 로컬 개발 DB의 합성 원장 SQL 경로 확인. x600 서버의 cs 프로젝트 API·DB는 확인·변경하지 않았습니다.

## 복구 자료

- [도구 코드 수정 전 백업](../../../app/tools/_backup/2026-10-11_2143_read_tool_gate/read_tools.py)
- [계약 수정 전 백업](../../teams/team-contract/_backup/2026-10-11_2143_read_tool_gate/plugin-availability.md)
- [수정 코드·시험 해시](../evidence/2026-10-11_1936_team_plugin_implementation/readtool-gate-sha256-2144.json)

커밋·푸시·배포는 하지 않았습니다. 최종 Claude Sonnet 5.5 독립 재감사 결과는 별도 보고합니다.
