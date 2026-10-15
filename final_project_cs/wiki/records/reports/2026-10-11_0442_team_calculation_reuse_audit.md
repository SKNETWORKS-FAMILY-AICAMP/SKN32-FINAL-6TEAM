# 담당 Team의 기존 계산 승계 대조

핵심 계산은 기존 함수 재사용으로 연결돼 있고 관련 시험 90/90건이 통과했다. 그러나 전체 기능의 우월성은 입증되지 않았다. 다시 적용 안내 문구 결함 1건을 실행으로 재현했고, 변경 후 추가 후보를 별도 보류 제안으로 여는 동작은 승계 확인이 남았다. 제품 코드는 수정하지 않았다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 요식·활동·이동 호출 대조 | 확인 | 3/3 = 100% |
| 관련 시험 | 통과 | 90/90 = 100% |
| 다시 적용 문구 결함 | 재현 | 1/1 = 100% |

## 범위와 판단

비교 대상은 현재 로컬 작업 트리의 TripDesk 직접 계산·적용 경로와 등록 Team 실행 경로다. 제품 전체 기능을 전수 평가한 분모는 아니다. LLM 추천 정확도, 실제 외부 지도 경로 오차, 운영 배포 성능을 이 시험으로 주장하지 않는다.

| 기능 | 기존 경로 | 현재 담당 Team 경로 | 판정 |
|---|---|---|---|
| 식사 지연·휴무 | TripDesk → plan_delay / plan_closed | DiningTeam.handle_report → 같은 함수 | 계산 재사용, 가격 조회 입력 추가 |
| 활동 품절 매장 안내 | TripDesk.ask_nearby_store → plan_nearby_store | ActivityTeam.handle_report → 같은 함수 | 계산 재사용 |
| 새 대안 계산 | TripDesk._fresh_plan → plan_fresh_alternate | conversation_work._fresh_plan → 같은 함수 | Activity·Dining 공통 경로 재사용 |
| 기존 대안 선택 | TripDesk.swap_alternate → plan_swap | ItineraryWork._change → 같은 함수 | 계산 재사용 |
| 이전 일정 복원 | TripDesk.rollback → plan_rollback | ItineraryWork._rollback → 같은 함수 | 복원 계산 재사용, 다시 적용 문구 차이 있음 |
| 이동 사건·출발 재계산 | 공유된 이동 계획 함수 | MobilityTeam.handle_trigger → plan_mobility_trigger → plan_route_adjustment / plan_departure_adjustment | 팀 실행 연결 확인 |
| 구조화 구간 계산 | 이동 엔진 | MobilityTeam.execute → _from_engine → wiring.team_result | 엔진 연결 시험 통과 |

현재 구조의 개선은 계산 정확도 향상과 구분한다. Team은 제안만 반환하고 Controller가 적용하며, 입력 대기·같은 Case 재개·중복 적용 방지·적용 기록을 공통 경로로 처리한다. 이 동작은 아래 로컬 개발 DB 시험에서 확인했다.

후보 확보는 case_dispatch._prepare_candidates에서 TripDesk._widen_activities / _add_nearby를 호출한 뒤 Team에 넘긴다. 따라서 후보 확보까지 전부 각 Team 내부로 옮겨졌다고 말할 수 없다. 이 처리는 여행 장소 후보 사본을 준비하며 일정 버전을 직접 변경하는 경로는 아니다.

## 확인한 차이

1. **실행 재현된 결함:** conversation_work는 redo를 _rollback으로 전달하지만 ItineraryWork._rollback은 plan_rollback의 redo=True 인자를 전달하지 않는다. 기존 TripDesk는 변경 이력으로 다시 적용 여부를 구해 전달한다. 현재 Team 결과는 다시 적용할 일정을 제안하면서 안내에 '되돌렸어요'를 쓴다. [결함 기록](debugs/2026-10-11_0442_team_redo_wording.md).
2. **정적 대조상 승계 확인이 남은 동작:** TripDesk.fresh_alternate는 변경 뒤 more_options를 _ask_options로 별도 pending_changes 제안에 등록했다. 현재 _fresh_change → settle → itinerary.apply 경로에서는 같은 추가 등록 호출을 확인하지 못했다. 다른 후보 자체는 변경 항목의 alternates와 summary에 보존된다. 후보 계산 유실과 별도 선택 목록 등록 차이를 구분한다. 브라우저 표시와 pending 목록의 대응 실행은 이번에 하지 않았다.

## 실제 실행

Python 3.12.7, 기존 임시 PYTHONPATH=.tmp/conversation-python(tiktoken 0.12.0), 자동 플러그인 로딩 비활성, pytest_asyncio.plugin 명시. 비동기 실행기의 로컬 socketpair가 제한 환경에서 정지해 중단했으며, 동일 시험을 제한 밖에서 실행했다. 전역 패키지나 제품 의존성은 변경하지 않았다. 출력은 UTF-8로 기록했다.

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONPATH='.tmp/conversation-python'
python -m pytest -p pytest_asyncio.plugin tests/unit/travel/test_conversation_work.py tests/unit/travel/test_fresh_alternate.py tests/unit/travel/test_dining_review_fixes.py tests/unit/travel/mobility/test_review_fixes_wiring.py -q
python -m pytest -p pytest_asyncio.plugin tests/scenario/test_case_version_day.py tests/e2e/test_web_conversation_resume.py -q
```

| 시험 파일 범위 | 통과/실행 |
|---|---|
| 팀 대화·대안·요식 회귀·이동 엔진 연결 | 73/73 = 100% |
| 기존 직접 경로와 Case 경로 비교·웹 대기 재개 | 17/17 = 100% |

단위 시험 분모는 45+10+10+8=73, 통합 시험 분모는 8+9=17이다. 합계 90건이다. 대표 하루 비교 시험은 일정 버전·최종 항목·통지 문구 일치와 Case/적용 기록을 검사한다. 외부 공급자와 해석 모델은 시험용 입력이다. 운영 데이터를 사용하지 않는 시험용 테넌트를 로컬 개발 DB에 만들고 정리했다.

mock 서버 시험(화면 반응): 이번 범위에서 미실시.

실서버 확인(cs 프로젝트 서버 응답): 안 했음. 로컬 API 시험 클라이언트·등록 Team·Controller·적용기·로컬 개발 DB를 실행했다. 실제 브라우저와 운영 배포는 확인하지 않았다.

근거: [단위 로그](../evidence/2026-10-11_team_calculation_audit/unit.log), [단위 JUnit](../evidence/2026-10-11_team_calculation_audit/unit.junit.xml), [통합 로그](../evidence/2026-10-11_team_calculation_audit/integration.log), [통합 JUnit](../evidence/2026-10-11_team_calculation_audit/integration.junit.xml), [문구 재현 결과](../evidence/2026-10-11_team_calculation_audit/redo.log), [재현 스크립트](../evidence/2026-10-11_team_calculation_audit/reproduce_redo.py).

## 참조·다음 검증

- app/domains/travel_ops/components/conversation/trip_desk.py:123,169,180,270
- app/domains/travel_ops/components/conversation/case_dispatch.py:201
- app/domains/travel_ops/instances/dining/team.py:107
- app/domains/travel_ops/instances/activity/team.py:160
- app/domains/travel_ops/instances/mobility/team.py:74,151
- app/domains/travel_ops/instances/_shared/conversation_work.py:168,200,258
- app/domains/travel_ops/instances/_shared/itinerary_team.py:197,304

다음 검증은 redo 문구 수정·회귀 시험, 변경 후 추가 후보의 pending 목록·브라우저 표시 대조다. 이번 작업은 제품 코드 수정·커밋·푸시·배포를 하지 않았다. 새 기록 파일을 만들었으며 기존 제품 산출물을 교체하지 않았다.
