# 통합 검증에서 발견한 도메인 경계 의존성 보완

Team 수명 관리 통합의 구조 검사에서 발견한 두 역방향 의존성을 기존 연결 방식으로 분리했습니다. 기존 시험 입력과 개인정보 처리 조건은 유지했으며 로컬 실행으로 검증했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 단위·기존 개인정보·구조 검사 | 통과 | 146/146 = 100% |
| 로컬 PostgreSQL 통합 검사 | 통과 | 88/88 = 100% |
| 수정 파일 정적 검사 | 통과 | 5/5 = 100% |

분모는 아래 명령에서 실행한 pytest 항목 및 ruff 대상 파일입니다. 운영 배포 완료율이 아닙니다.

## 변경

- [서비스 개선 추출](../../../app/domains/travel_ops/components/customer/service_improvement.py)은 선택 웹 모듈을 직접 불러오던 의존성을 기존 `settings_hook.operator_setting` 연결로 바꿨습니다. 운영 조정값이 없으면 기존 `web_guard.guest_idle_hours` 가드레일 기본값을 쓰고, 회원 보유기간과 비교해 더 짧은 기간만 추출합니다. SQL의 현재 선택 동의·사용자당 최신 여행 한 개 조건은 바꾸지 않았습니다.
- [점검 Port](../../../app/domains/travel_ops/ports/data_sources/disruptions.py)는 상위 감시 컴포넌트 직접 import 대신 새 [시험 입력 연결](../../../app/domains/travel_ops/ports/data_sources/simulation_hook.py)을 호출합니다. `register(provider)`로 `resolve`, `inputs`, `record_result`를 공급합니다. 실제 인증·범위 검증·입력 생성·실행 기록은 기존 simulation 컴포넌트가 그대로 수행합니다. 기본 소스와 기존 6종 조합을 끄거나 검사 상한을 높이지 않았습니다.
- [독립 시뮬레이션 통합 시험](../../../tests/integration/test_watch_simulation.py)은 앱 조립을 거치지 않는 fixture이므로 공급자 연결을 명시했습니다. 운영 조립의 `wire_optional_features()` 연결은 상위 통합 작업에 전달했습니다.

기존 파일 세 개는 [원본 보존 폴더](../../../legacy/team_plugin_boundary/2026-10-11_2106/)에 경로 그대로 복사했습니다. 새 연결 파일과 새 시험은 원본을 덮어쓰지 않았습니다.

## 검증 명령과 근거

```powershell
python -m pytest tests/unit/travel/test_boundary_simulation_and_improvement.py tests/unit/test_service_improvement.py tests/architecture/test_travel_ops_cells.py -q --tb=short
python -m pytest tests/integration/test_watch_simulation.py tests/integration/db/test_service_improvement.py -q --tb=short
python -m ruff check app/domains/travel_ops/components/customer/service_improvement.py app/domains/travel_ops/ports/data_sources/disruptions.py app/domains/travel_ops/ports/data_sources/simulation_hook.py tests/unit/travel/test_boundary_simulation_and_improvement.py tests/integration/test_watch_simulation.py
```

[단위·구조 원문 로그](../evidence/2026-10-11_1936_team_plugin_implementation/boundary-regression.log)는 146항목 통과입니다. 신규 68항목은 64개 시험 입력 조합의 소스 교체·전체/안전 점검 기록, 미등록·불완전 공급자 거절, 운영 조정값·기본값·더 짧은 회원기간 3조건을 검증합니다. 기존 개인정보 단위 76항목과 구조 검사 2항목도 통과했습니다. 구조 검사에서 기존 다른 소스의 문자열 escape 관련 경고 1건이 있었으며 오류는 아닙니다.

[로컬 DB 통합 원문 로그](../evidence/2026-10-11_1936_team_plugin_implementation/boundary-db-regression.log)는 88항목 통과입니다. 기존 시험 그대로 여행·이용자 범위, 서명 변조·만료·중지, 안전정지와 결과·알림 표지, 선택 동의·추출 기한·검토·내보내기 조건을 확인했습니다. 실제 이용자 자료를 추출하거나 운영 자료를 변경하지 않았습니다.

[정적 검사 최종 로그](../evidence/2026-10-11_1936_team_plugin_implementation/boundary-lint-v2.log)는 통과입니다. 초기 검사에서 기존 통합 시험의 미사용 `UUID` import 한 개가 발견되어 제거했습니다.

mock 서버 시험: 해당 없음(화면 반응은 검증하지 않았습니다).

실서버 확인(서버 응답): 안 했음. 이번 범위는 로컬 PostgreSQL과 소스 계약 검사이며, 운영 중인 cs 프로젝트 서버의 HTTP 응답·배포는 별도입니다.

## 연결 문서

[서비스 개선 운영 계약](../../operations/service-improvement.md), [Team 수명 관리 계획](../../teams/team-plugin-lifecycle.md)의 통합 경계 보완입니다. Claude 독립 검토와 전체 운영 호환성 판정은 상위 통합 리포트에서 별도 기록합니다.
