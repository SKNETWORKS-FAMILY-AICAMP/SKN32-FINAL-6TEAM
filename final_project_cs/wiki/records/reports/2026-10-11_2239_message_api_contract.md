# 메시지 API 문서를 Controller·Team 대기·재개 계약에 맞춤

2026-10-11 22:39 KST. 문서 2개를 현재 로컬 코드와 대조하여 정정했다. 제품 소스·시험·운영 배포는 이 작업에서 변경하지 않았다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 대상 문서 전체 읽기·정정 | 끝 | 2/2 = 100% |
| 제품 코드 해시 유지 | 확인 | 4/4 = 100% |
| 내부 파일 링크 | 통과 | 15/15 = 100% |

## 바뀐 설명

- [웹 API](../../external/rest-endpoints/web-access.md)의 메시지 행에서 시나리오용 별도 경로·향후 Case 통합 설명을 현재 Controller → 담당 Team → 공통 적용 경로로 교체했다. 요청 필드·응답 필드·오류·중복·SSE를 코드와 대조했다.
- [계획 읽기 API](../../external/rest-endpoints/web-intakes.md)의 채팅 결정 단위를 해석과 업무 실행으로 구분했다. `case_status=waiting_input`, 선택적 `case_id/resume_token/expected_version`, 답변 본문 전달과 재개를 명시했다. `version`은 Case 버전, 적용 결과의 `outcome.version`은 여행 버전이다. `report`는 공통 필수 응답이 아니며 기존 품절 상품 추천 전용 칸은 유지한다.
- 해석 응답의 `decision`과 재개 응답의 `reason=team_conversation`을 구분했다. 웹 개발 모드 공개 칸과 `decision.record()`의 실제 `raw` 칸, 대화 조회의 `trip_id`를 반영했다. 당시 모델 172문장 측정은 과거 품질 기록이며 이번 Team 검증 수치가 아님을 적었다.

## 근거와 확인 범위

확인한 제품 경로는 `MessageIn`, 에이전트·웹 메시지 handlers, `trip_messages.handle_trip_message`, `case_dispatch.execute/resume_pending/response`, `conversation_work`, `Controller.resume/resume_customer_input`, `decision_unit.record`다. worker 담당자가 UI의 `report` 필수 소비를 찾지 못했고 부모가 생산 코드를 바꾸지 않고 새 Team 응답 계약으로 시험을 보강하도록 승인한 상태와도 대조했다.

[최종 Sonnet 감사 기록](2026-10-11_2233_team_plugin_final_delta.md)의 193/193 합성 시험과 추가 읽기 감사 결과는 별도 근거다. 문서 작업은 새 제품 시험을 실행하지 않았으며, 실제 고객·외부 DB·실제 모델의 일반 성능·운영 배포를 검증하지 않았다. `503 team_unavailable`은 해당 업무를 막는다는 뜻이고 저장된 독립 조회를 모두 중단한다는 뜻이 아니다.

[문서 확인 로그](../evidence/2026-10-11_1936_team_plugin_implementation/api-docs-verification-v1.json) · [제품 소스 해시](../evidence/2026-10-11_1936_team_plugin_implementation/api-docs-source-sha256-v1.json) · [백업 대조 diff](../evidence/2026-10-11_1936_team_plugin_implementation/api-docs-diff-v1.patch).

두 대상 문서는 현재 git untracked여서 일반 `git diff`가 변경을 보여 주지 않는다. 따라서 백업 원본과 최종 문서의 unified diff를 별도 저장하고 UTF-8·후행 공백·내부 파일 링크를 확인했다. 과거 records 문서를 오늘 상태로 다시 쓰지 않았다.

## 백업

[수정 직전 원본 2개](../../external/rest-endpoints/_backup/2026-10-11_223742_controller_team_contract/)를 복사했다. 세부 문구를 마지막으로 다듬기 전 첫 편집본도 같은 폴더의 `first_edit/`에 보존했다. 커밋·푸시·운영 배포는 하지 않았다.
