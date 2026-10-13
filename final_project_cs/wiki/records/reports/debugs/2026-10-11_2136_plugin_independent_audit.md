# 플러그인 독립 감사 후속 결함

작성: 2026-10-11 21:36 KST. 범위: 로컬 작업 트리. 운영 반영 전입니다.

Claude Opus 5.5가 기존 회귀 93건 통과 뒤 코드 검토와 추가 실행에서 여섯 결함을 확인했습니다. 기존 시험 통과만으로 완료를 선언하지 않고 수정·추가 재현을 진행합니다.

| 결함 | 원인 | 보완·검증 상태 |
|---|---|---|
| 담당 미정 문의가 실행 불가로 고정 | 모든 제공자 0개를 TeamUnavailable로 바꿈 | 도메인 주입 담당 메타데이터로 구분, 실제 Controller 포함 190/190 통과 |
| 원격 deadline에서 취소 호출 누락 | Controller와 A2A의 같은 바깥 제한시간 경합 | 실행 deadline과 유한 정리 예산 분리, 실제 Controller 재현 6/6 통과 |
| 비활성 Team 코드 import | 도메인 __init__의 즉시 재수출 | 지연 export, 새 프로세스에서 여섯 비활성 구현 import 시도 0회 확인 |
| 이동 읽기 도구의 우회 어림값 | TeamUnavailable을 일반 엔진 예외로 삼킴 | 조립 판 안에서 원인 보존·503, 필수 엔진 실패 추정 성공 차단 |
| 등록 전 식당 판정의 직접 SQL | place_id 유무에 따라 서로 다른 실행 관문 | catalog_state hook으로 위임, DB 읽기 전 담당 관문; 실제 SQL 추가 검증 진행 |
| 회차 조립 실패로 독립 작업 중단 | 회차 전체가 단일 조립·예외에 묶임 | Team 의존 작업 격리·독립 정리와 재난 점검 유지, 회귀 32/32 통과 |

근거: [Opus 원문](../../evidence/2026-10-11_1936_team_plugin_implementation/opus-final-review.jsonl), [import·읽기 경계 회귀 81/81](../../evidence/2026-10-11_1936_team_plugin_implementation/opus-read-boundary-v2.log), [미분류 회귀](../../evidence/2026-10-11_1936_team_plugin_implementation/unknown-route-regression-v3.log), [worker 회귀](../../evidence/2026-10-11_1936_team_plugin_implementation/worker-audit-regression-v2.log).

기존 전체 e2e 1차는 99건 통과·12건 실패에서 중단됐습니다. 미실행 888건을 통과로 세지 않습니다. 후속 전체 실행과 최종 독립 감사가 끝나기 전까지 본 결함 묶음을 완료로 닫지 않습니다. 구현 이전 원본은 [백업](../../../../legacy/team_plugin_lifecycle/)에 보존했습니다.
