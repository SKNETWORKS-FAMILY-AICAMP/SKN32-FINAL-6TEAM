# Team 플러그인 설계 — Claude Opus 5.5 논의 완료

작성: 2026-10-11. 19:14 KST 백업·개정 회차의 후속 보고입니다. 사용자 승인 후 모델 검토와 반론을 완료했고, 합의한 방향을 계획·현재 계약 문서에 반영했습니다. 제품 구현 완료 보고가 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| Claude 독립 검토·반론 재논의 | 완료 | 2/2 = 100% |
| 계획 개정·후속 결과 기록 | 완료 | 2/2 = 100% |
| 제품 코드 구현 | 미착수 | 0/6 = 0% |
| 계획한 인수 시나리오 실행 | 미실행 | 0/24 = 0% |

## 요청 모델과 실제 실행

Claude Code 2.1.287에서 `--model claude-opus-5-5`를 명시했습니다. 두 응답 모두 `modelUsage`의 `canonicalModel=claude-opus-5-5`, `provider=firstParty`, `is_error=false`, `terminal_reason=completed`를 확인했습니다. 모델을 임의 대체하지 않았습니다. 자료 전달은 사용자의 “진행 하라고” 지시 후 수행했습니다.

- 1차: [프롬프트](../evidence/2026-10-11_1826_team_plugin_review/review-prompt.txt), [CLI 원문](../evidence/2026-10-11_1826_team_plugin_review/attempt-2.json), [읽기용 의견](../evidence/2026-10-11_1826_team_plugin_review/opus-review-round1.md).
- 2차: [Codex 반론](../evidence/2026-10-11_1826_team_plugin_review/discussion-prompt.txt), [CLI 원문](../evidence/2026-10-11_1826_team_plugin_review/attempt-3-discussion.json), [읽기용 의견](../evidence/2026-10-11_1826_team_plugin_review/opus-discussion-round2.md).

CLI는 safe-mode·strict MCP config·plan 권한 모드·Read/Glob/Grep 도구만으로 실행했습니다. 두 결과의 permission_denials는 빈 목록이며 하위 에이전트 실행은 0입니다. 비밀정보·고객 데이터 제외를 지시했고 제품 파일 수정 도구를 허용하지 않았습니다. CLI 의견은 실행 시험이나 구현 검증을 대신하지 않습니다.

## 합의와 수정

| 쟁점 | 최종 계획 | 이유 |
|---|---|---|
| Team 부재 | 해당 업무·필수 계산 불가, 독립 기능 유지 | 꺼진 Team의 일을 이전 경로로 대신 성공시키지 않음 |
| 계산 재사용 경계 | team_hooks 유지·계산별 필수/선택 구분 | 계산까지 모두 Team.execute로 몰 필요 없음 |
| 실행 중 교체 | Controller·Registry·Executor·계산 표·endpoint·revision을 요청별로 고정 | 설정 검사 뒤 전역 계산 함수가 바뀌는 혼합 방지 |
| 재개·담당 지정 | ROUTED와 토큰·답변 반영 전에 가용성 검사 | 거절된 요청이 업무 상태나 토큰을 소비하지 않음 |
| 로딩 | disabled import 0회, 명시적 optional 실패만 격리 | 필수 코어·계약 결함·결정 15의 데이터 장애를 숨기지 않음 |
| Local/A2A | Controller 공통 관문+실행기 방어, 원격 식별자 대조 | 원격 실행 우회와 다른 task 결과 수용 방지 |

Codex가 1차 의견의 “전역 clear/register 뒤 Controller swap”을 반박했습니다. Claude는 2차에서 해당 방안을 철회하고 전체 묶음 게시에 동의했습니다. 후보 조립이 이동 엔진 등 전역 설정을 바꾸면 여전히 위험하므로 그 부작용 제거도 계획에 넣었습니다.

초안의 mutable disable·참조 카운트·강제 drain 확대는 이번 범위에서 뺐습니다. 기존 관리용 reload로 새 판을 게시하고 이전 요청은 이전 판으로 종료합니다. 즉시 강제 취소를 보장하는 기능과 구분합니다. 자원 해제를 GC만으로 보장한다는 주장도 채택하지 않았습니다.

모든 resolver 예외를 unavailable로 합치는 제안은 그대로 받지 않았습니다. 실제 부재와 잘못된 구성·구현 결함의 원인은 보존합니다. capability 제공자 1:1·중복 거부·계약 버전 검사는 유지합니다.

## 남은 질문의 처리

사용자 방향에서 정할 수 있는 사항은 계획에 구체화했습니다. 이동 계산이 필요한 새 계획·변경은 Mobility 부재 시 이용 불가, 기존 계획서 읽기는 유지합니다. 엔진 off는 Team disabled와 구분하며 검증된 대체 소스가 없으면 추정값 성공으로 바꾸지 않습니다. 감시 종류가 빠지면 그 종류의 미실행 사유를 남기고 독립 감시를 유지합니다. 식당 상태가 필수인 요청은 Dining 부재 시 실행하지 않습니다.

새 상태·수신자 없는 사람 인계 큐는 추가하지 않습니다. 외부 `team_unavailable`/503과 내부 원인 구분을 목표로 정했고 근거 없는 Retry-After는 만들지 않습니다. 선언 스키마 필드, revision 저장 필드, MCP 오류 봉투, threadpool/백그라운드 판 전달은 구현 첫 단계와 시험에서 호환성을 확정해야 합니다. 남은 구현 세부를 확인 완료로 표시하지 않습니다.

## 검증 범위

기존 결함 재현 4/4 관측은 그대로이며 목표 시험 통과가 아닙니다. [소스 해시 후속 확인](../evidence/2026-10-11_1826_team_plugin_review/source-hash-followup.json)에서 재현 때 확인한 코드 8/8개가 동일했습니다. 원격 결과 식별자 문제는 A2A 코드 검토로 추가한 항목이며 원격 호출 실측이 아닙니다.

제품 시험은 이 문서 변경에서 실행하지 않았습니다. mock 서버 시험: 미실행(화면 반응). 실서버 확인(서버 응답): 안 했음. 문서 링크·코드 울타리·시나리오 수·공백 검사의 결과는 [후속 문서 검사](../evidence/2026-10-11_1826_team_plugin_review/document-check-followup.json)에 별도로 남깁니다. Mermaid 화면 렌더링 확인과는 구분합니다.

## 변경과 백업

현재 계획은 [Team 로딩·실행·교체](../../teams/team-plugin-lifecycle.md)입니다. [구성 계약](../../teams/composition.md), [폴더·계산 경계 결정](../../decisions/D-CS-013-domain-folder-layout.md), [Registry](../../teams/team-registry.md), [변경 이력](../../log.md)에 현재 구현과 목표 정책의 차이·후속 링크를 반영했습니다. 이전 차단 보고는 당시 기록으로 보존했습니다. 상위 v11·동결 plans/handoff는 수정하지 않았습니다.

기존 문서 다섯 개는 덮어쓰기 전에 [19:14 백업](../../_backup/2026-10-11_1914_team_plugin_consensus/)에 상대 경로를 유지해 복사했습니다. 코드·커밋·푸시·배포는 수행하지 않았습니다. 다음 구현은 계획의 여섯 코드 단위와 24개 인수 시나리오를 기준으로 진행할 수 있습니다.
