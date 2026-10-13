# 일반 Case 재개의 교차 Team 필수 계산 사전검증 범위

2026-10-11 부모의 추가 감사 질문에 대한 Codex 원문 대조 메모다. 실행 중인 Opus 호출에는 이 질문을 추가 주입하지 못했으므로 Opus의 판정으로 인용하지 않는다. 시험·제품 수정은 하지 않았다.

대상은 `legacy/deployment_candidates/2026-10-11_222547_plugin_v5` 후보뿐이다.

## 코드 순서

- `app/presentation/api/cases.py`의 `message`는 Controller의 `resume`/`resume_customer_input`에 message·expected_version·event_id를 전달하며 `resume_prepare` callback은 넘기지 않는다.
- `app/application/controller.py:872`의 기존 owner, `902~907`의 최종 owner/capability 관문 후 `908~909`는 callback이 있는 경우에만 실행한다. `911~924`는 VALID_INPUT·가린 답변·토큰 소비·요청 해시를 저장하고 commit한다. `931`이 run_case다.
- cross-Team 계산은 해당 도구가 쓰일 때 `app/core/service_bindings.py`의 `read_binding(required_team=...)`에서 현재 고정된 Registry를 검사한다. Mobility의 `legs.leg_planner` 등도 이 관문을 사용한다.
- 실행 중 TeamUnavailable은 Controller `466~476`에서 run을 실패로 닫고 예외를 다시 올린다. 이미 저장한 고객 답변/토큰을 되돌리지는 않는다. `830~850`의 동일 event 멱등 재시도는 running이고 활성 run이 없으면 원래 답변으로 run_case를 다시 실행할 수 있다.

## 판단과 한계

Dining owner는 활성이고 실제 계산에 필요한 Mobility hook만 disabled인 조건에서는 generic Case 재개가 owner/capability 관문을 통과할 수 있다. 이후 실제 Mobility 계산이 호출되면 성공으로 우회하지 않고 실패한다. 반면 교차 계산의 가용성을 VALID_INPUT 전에 모두 확인한다고 보장하지는 않는다.

현재 계약의 명시적 owner→최종 owner/capability→선택 resume_prepare→VALID_INPUT 순서는 충족한다. '업무 시작 전 확인 가능한 불가는 답변/토큰 미소비' 문장을 모든 교차 Team 필수 계산까지 일반화하면 코드보다 강한 문구다. 확정된 설명 차이/사전검증 공백과 실제 답변 손실을 구분한다. runtime 재현은 하지 않았고 모든 Dining 행동이 실제 Mobility를 호출한다고 주장하지 않는다.

strict Team 가용성 우회로 분류하지 않는다. 모든 Dining 업무를 Mobility 활성 조건으로 묶으면 독립 업무도 막는다. 모든 필수 의존성에 대한 비소비 사전보장이 필요하면 도메인이 request/action에 필요한 읽기 전용 사전검증 callback을 중립 조립 경계에 명시해야 한다. Core에 여행 Team 이름을 추가하는 방식은 부적합하다. 지금 임의 수정하지 않았다.
