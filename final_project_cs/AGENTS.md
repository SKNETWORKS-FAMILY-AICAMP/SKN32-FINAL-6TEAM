# triPilot — 현재 작업 규칙

현재 제품은 **여행 CS triPilot**, 개발 팀은 **A-COPilot**입니다. Activity·Dining·Mobility는 요청을 처리하는 에이전트 팀입니다. 개발 담당자와 혼동하지 않습니다.

## 정본과 적용 범위

- 현재 제품 사양은 [wiki](wiki/index.md)와 [상위 wiki](../wiki/index.md)의 후속 확정 결정·계약을 따릅니다. 구현·배포 상태는 코드와 해당 환경의 실행 기록으로 확인합니다.
- v11은 2026-09-10 당시 계획 기록입니다. v12는 wiki 기반 안내서로 작성할 예정이며 완료본이 아닙니다. 동결된 handoff·과거 계획·성과표는 현재 계약을 덮어쓰지 않습니다.
- 쇼핑몰 시절 자료·코드·데이터는 [D-023](../wiki/decisions/D-023-no-commerce-assets-in-use.md)에 따라 현재 판단·시험·평가·시연·화면·관문에서 사용하지 않습니다. records·legacy·백업은 이력 보존용입니다. 재유입 방지 검사의 금지 목록과 여행지 쇼핑 활동은 구분합니다.
- `final_project_sample`은 별도의 참고 구현체입니다. 그 도메인 자료나 완료 상태를 이 제품의 검증에 가져오지 않습니다.

## 작업 시작과 책임

[RULE.md](RULE.md)를 읽고 관련 현재 wiki 계약·실제 호출 경로·영향받는 시험을 확인합니다. 담당과 공유 계약 변경 순서는 [개발 역할](../wiki/delivery/roles.md), 실제 파일 위치는 [코드·시험 안내](wiki/teams/code-layout.md)를 따릅니다. 고객 대신 문제를 직접 고치는 상주 상담원·운영 관리자 역할은 만들지 않습니다. 개발자·QA는 축적된 결함을 사후 분석합니다.

## 유지해야 할 안전 경계

- 핵심 주장에는 출처·확인 시각을 붙입니다. 근거·값을 지어내지 않습니다. 축소된 Context Pack은 `degraded`·`omissions`, 분류 실패는 `classification_failed`로 드러냅니다. 무음 폴백·오류 삼키기를 금지합니다. 실패 처리·대체 소스 정책은 해당 현재 계약을 따릅니다.
- Team은 `ActionProposal`을 반환하며 외부 부수효과를 직접 실행하지 않습니다. 업체 예약·결제·환급의 고객 승인·권한 경계를 우회하지 않습니다. 항로 지킴이의 일정 변경 조건과 업체 거래 승인을 구분합니다.
- MCP는 [현재 여행 도구 계약](wiki/external/mcp-tools.md)을 따릅니다. 사용자 키 또는 개인 AI OAuth 토큰([D-CS-012](wiki/decisions/D-CS-012-agent-auth-claude-style.md) · [개인 AI OAuth](wiki/external/personal-ai-oauth.md) — 고객이 허용한 권한 범위 안)으로 본인 여행만 열고, 쓰기 등록은 `travel.mcp.write_enabled` 기본 꺼짐을 지킵니다. 도구 인자로 호출 고객을 바꾸지 않습니다.
- Case 상태 변경은 `transition_case()`를 거칩니다. `case_events`는 추가만 합니다. CAS·멱등 키·outbox 중복 방지와 provider 결과 `unknown` 처리 규칙을 유지합니다. timeout을 성공으로 추정하거나 자동 재실행하지 않습니다.
- tenant·customer 격리, PII 마스킹, 키·접속 정보 비공개, 프롬프트 버전·해시·호출 기록을 유지합니다. 미등록 프롬프트를 조용히 대체하지 않습니다.
- Core는 Team 구현을 직접 import하지 않습니다. `TeamRegistry`는 선언으로 에이전트 팀을 선택하고 `Controller`가 흐름을 진행합니다. `allowed_tools`·도구 예산·`extra='forbid'` 계약 경계를 유지합니다. 가드레일 값은 공통 설정에서 읽습니다.

## 검증과 보고

- 검증 없이 완료·운영 반영을 선언하지 않습니다. 화면 변경은 실제 화면을 확인합니다. mock 서버 시험과 실서버 확인은 구분합니다.
- 평가의 데이터·모델·프롬프트·seed·반복·실패·표본 크기를 남깁니다. holdout으로 프롬프트를 고치지 않습니다. 표본 결과를 실제 서비스 전체 성능으로 일반화하지 않습니다.
- 작업 보고는 한국어 존댓말과 `n/m = %` 진행 표를 사용합니다. 파일은 링크로 줍니다. 기존 산출물을 덮기 전에 백업하고, 관련 시험·남은 한계·백업 경로를 기록합니다.
- dated 보고서를 [records/reports](wiki/records/reports/)에 추가하고 wiki에는 결론 한 줄과 링크를 남깁니다. 기존 과거 기록을 오늘 상태로 다시 쓰지 않습니다.

## 이전 규칙

[2026-10-11 정리 전 원문](wiki/records/commerce_2026-10-11/AGENTS.md) — 당시 규칙·상태표의 보존본입니다. 현재 작업 지시로 사용하지 않습니다.
