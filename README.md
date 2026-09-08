# A-COP

A-COP(AI 연동형 모듈형 에이전틱 고객운영 플랫폼)은 부트캠프 최종 프로젝트로 진행하는 6명·10주 프로젝트다. 주제는 다중 에이전트 서빙 기반 고객 피드백 분석 및 맞춤형 응대 자동화 시스템이다. 고객 메시지를 업무 Case로 만들고, 전문 Agent Team이 상태·정책·이력·피드백 분류를 바탕으로 판단·응대·후속 작업 제안을 수행하도록 한다.

A-COP의 기준선은 하나의 Runtime 위에 CS Pack과 Commerce Ops Pack을 교체·확장하는 구조다. 10주 범위에서는 자동화 CS와 제한된 Commerce 검증 사이트를 구현하며, 운영자는 Case·Action·승인·근거·평가를 감독한다. 이후 구현·평가·심사의 기준선은 v8이다.

## 저장소 구조

| 폴더 | 역할 |
|---|---|
| [`final_project_cs/`](final_project_cs/) | 릴리스 대상 제품 코드베이스다. 실제 CS Pack·Commerce Ops Team(Order/Shipping·Return/Exchange)을 구현하며, 현재 상태표 기준으로 Core 런타임, REST/MCP, 쇼핑몰 도메인 RAG·Feedback Analytics·Controller·운영 UI·A2A/Graph·ActionProposal 방어·프롬프트 감사추적이 구현·검증돼 있다. DoD는 evidence 28/28, 통과 24, 부분통과 4이며 29번(Response Generation & Review)은 아직 평가되지 않았다. RC는 아니다. |
| [`final_project_sample/`](final_project_sample/) | 참고 구현체다. Core/Team 계약과 Composer 쓰기채널·개발 콘솔 연동 인프라를 여기서 먼저 만들고 검증한 뒤 `final_project_cs`로 이식한다. [`examples/`](final_project_sample/examples/)에는 착수 목록에서 빠진 옛 Billing/Technical 예시 Team이 별도 보존돼 있으며, 릴리스 때 제거할 수 있는 형태로 분리돼 있다. Composer 인프라의 계약은 [`docs/handoff/13_Composer_쓰기채널_계약.md`](final_project_sample/wiki/records/handoff/13_Composer_쓰기채널_계약.md)에 있다. |
| [`final_project_ui/`](final_project_ui/) | 세 프로젝트 어디에도 없는 읽기 전용 개발 콘솔이다. 대상 프로젝트의 파일·DB·introspection 데이터를 읽기만 하며, 유일한 예외로 대상이 제공하는 인증된 Composer 쓰기 API(`/composer/current`, `/composer/validate`, `/composer/apply`)만 호출한다. 대상 파일·DB·Python 모듈을 직접 수정하거나 import하지 않는다. |
| [`program/`](program/) | 코드가 아닌 기획·근거 자료 모음이다. `program/plan/`은 구현계획서, `program/research/`는 조사·근거 자료, `program/briefing/`은 발표 문서, `program/personal/`은 팀원 개인 작업물(git 비추적)을 담는다. |
| `team_branch/` | 팀 공유 원본 자료(git 비추적)다. |

## 어디서부터 읽을까

- 기준선: [`program/plan/A-COP_구현계획서_v8.md`](program/plan/A-COP_구현계획서_v8.md)
- 현재 근거 색인: [`program/research/index.md`](program/research/index.md)

## 작업 규칙

각 코드 프로젝트의 세부 작업 규칙은 해당 폴더의 `CLAUDE.md`와 `RULE.md`에 있다.

- [`final_project_cs/CLAUDE.md`](final_project_cs/CLAUDE.md) · [`final_project_cs/RULE.md`](final_project_cs/RULE.md)
- [`final_project_sample/CLAUDE.md`](final_project_sample/CLAUDE.md) · [`final_project_sample/RULE.md`](final_project_sample/RULE.md)
- [`final_project_ui/CLAUDE.md`](final_project_ui/CLAUDE.md) (이 프로젝트에는 별도 `RULE.md`가 없다)
