---
type: report
title: ST4F-732 경계 후속 후보 독립 검토
status: draft
domain: travel
---

# ST4F-732 경계 후속 독립 검토

2026-10-29 KST. 사용자 요청으로 별도 Codex 세션이 `2026-10-29_st4f732-edge-followup.md`와 보존된 후속 후보를 검토했습니다. **좁은 시계 수정은 재현 검증을 통과했으며 통합·운영은 HOLD입니다.** 사람의 독립 승인이나 최신 원격 통합 승인을 뜻하지 않습니다. 원본 제품 코드·Git 설정·트래커·운영 쓰기·커밋·푸시·배포·삭제는 하지 않았습니다. ST4F-718·731 HOLD와 필수 관문 HOLD를 유지합니다.

## 범위와 근거

루트/CS AGENTS, CS RULE, 양쪽 wiki 입구, 개발 역할·코드 경로, `web-intakes.md`, 기존 독립 검토·후속 보고와 인계를 읽었습니다. 로컬 coord NOTICE 62개를 읽고 비공개 scratch에 보존했습니다. 732 담당의 범위 해제와 통합 HOLD를 확인했으며 조정 메시지는 보내지 않았습니다. 규칙 변경은 없습니다.

새 작업 사본은 `scratch/st4f732-edge-independent-20261029/repo`입니다. 후속 후보의 웹 소스를 파일 복사했으며 Git 사본이나 최신 원격 tip이라고 주장하지 않습니다. 의존성 junction은 기존 설치본을 읽습니다. 이전 검토 사본과 원본 제품 코드는 수정하지 않았습니다. 실행 중 변이는 이번 사본의 hook에만 적용하고 `finally`로 바이트를 복구했습니다. 사본·하네스·로그를 모두 보존합니다.

`server-steps.ts`는 reading/reading_api를 같은 표시 칸으로 묶고 reading_api를 우선합니다. 그 뒤 places → hours → moves → risks → prefill → answers 순서로 가장 먼 단계를 표시합니다. 읽기는 m/m이어도 정리 중일 수 있고, prefill recheck도 단순 완료 카운트와 구별됩니다. `reduceStream`은 같은 총수의 역순 카운트를 무시하고 다른 총수는 새 카운트로 보존합니다. 재연결은 상태 복사본 재생입니다. 따라서 동일 패킷 재생과 앞 단계의 늦은 패킷은 현재 단계의 새 소식이 아닙니다. 현재 칸의 내용·총수·recheck 변경 또는 실제 표시 단계 변경은 시계 기준점을 바꿉니다. 후속 후보의 선택은 이 코드 계약과 일치합니다.

`useServerSteps`의 경계 객체는 A→null→A와 A→B→A에서 문자열이 다시 같아져도 새 객체입니다. 이전 interval의 tick은 새 경계에 표시되지 않고 effect cleanup으로 해제됩니다. `performance.now()`를 써서 벽시계 변경과 분리합니다. 기존 표시 기준 8초, 전송 watchdog 7초, 재연결 지연 등 제품 수치는 바꾸지 않았습니다. 새 시간 임계값이나 임의 timeout 성공 판정도 추가하지 않았습니다. Playwright의 상태 대기 제한은 테스트 실행 한도이며 제품 수락 기준이 아닙니다.

## 실행 결과

| 실행 | 이번 실측 |
|---|---|
| 후속 후보, 기존 확장 Edge 하네스 재실행 | 21/21 = 100%, pageerror 0 |
| 이전 후보 재삽입 | 16/21 = 76.2%, 실패 5건 |
| 원래 hook 재삽입 | 15/21 = 71.4%, 실패 6건 |
| 이전 검토의 네 경계 실패 재현 | 4/4 = 100% 탐지 |
| 새 독립 HTTP SSE 하네스 | 10/10 = 100%, pageerror 0 |
| 새 SSE 하네스의 표적 변이 | 1/1 = 100% 탐지 |
| 전체 웹 Vitest | 1232/1232 = 100%, 실패·skip 0 |
| TypeScript | 1/1 = 100%, exit 0 |

기존 네 실패는 앞 단계 지연 패킷의 현재 시계 초기화, ended 뒤 같은 단계 재시작의 옛 tick, received 공백 뒤 옛 tick, 빠른 A→B→A의 옛 tick입니다. 확장 하네스에서는 reading_api 뒤 지연 reading도 추가로 실패합니다. 원래 hook에는 기존 reading→checking 12초 잔류도 있습니다. 기존 보고서의 19개 결과와 이번 21개 결과는 분모가 다릅니다. 재사용 하네스 결과와 새로 작성한 독립 SSE 시험을 구분했습니다.

새 `sse.cjs`는 loopback HTTP 서버에서 `text/event-stream`을 실제 Edge fetch로 받습니다. 분할된 CRLF 이벤트 블록 → 제품 `stream.ts/watchIntake` → `useIntakeEvents` → `toIntakeEvent` → `reduceStream` → 실제 `serverProgressOf` → `useServerSteps`를 React StrictMode에서 실행합니다. fetch나 제품 파서를 대역으로 교체하지 않았습니다. 인증 응답·내용·서버 일정은 통제된 로컬 fixture이고 `onChange`는 재조회 요청을 기록합니다. 전체 IntakeReview/Next 라우트·실제 백엔드·DB는 실행하지 않았습니다.

실제 연결에서 단계 순서, 동일 replay·역순 카운트·늦은 앞 단계, title/total/recheck, 연결 종료 뒤 제품 hook의 재연결·재생, 관측된 종료 경계, 접수 전환 재마운트, 벽시계 전후 이동, CDP frozen/active, unmount의 실제 연결 abort를 확인했습니다. 서버는 3초 간격 beat와 같은 줄의 replay를 보냅니다. 둘 다 현재 단계 패킷을 바꾸지 않아 시계를 초기화하지 않습니다. 시계는 Playwright 가상 단조 시계입니다. CDP 전환 사이에 실제 OS 절전 시간을 재현한 것은 아닙니다.

표적 변이는 `news`를 현재 단계 패킷 대신 모든 `serverPhases`로 계산하게 했습니다. 새 SSE 시험이 지연 앞 단계 초기화를 탐지하고 종료 경계도 실패했습니다(8/10 = 80%). 변이 제거 뒤 같은 하네스를 다시 실행해 10/10 = 100%를 확인했습니다. 단순히 초록 결과만 확인한 것이 아닙니다.

하네스 준비 중 두 문제도 구분합니다. 최초 세션 fixture의 필드 이름과 브라우저 `process` shim 누락을 바로잡았습니다. 이어 heartbeat 없는 하네스에서 기존 7초 watchdog이 연결을 끊어 6/10 = 60%였으며 서버의 정상 heartbeat를 추가했습니다. 제품 watchdog을 늦추거나 끄지 않았습니다. 이 준비 실패를 제품 회귀나 최종 통과로 섞지 않았습니다. 마지막 로그·변이 로그·runner를 보존합니다.

## 실행 식별자와 남은 수락

실제 앱 `src/app/intakes/[intakeId]/page.tsx`는 `<IntakeReview key={intakeId}>`를 사용합니다. 서로 다른 접수는 stream과 시계가 새로 만들어지는 코드 경계이며 새 하네스에서도 같은 입력으로 ID를 바꿔 재마운트할 때 0초·빈 phases를 확인했습니다. Reading↔Checking은 서로 다른 컴포넌트이며 `PlanCheck`의 읽기 질문 유지 경로는 Reading을 계속 유지할 수 있습니다. 후속 후보의 관측 경계 처리는 이 지속 렌더 경로에서도 필요합니다.

**같은 접수·같은 단계·같은 패킷·종료 공백 없음**에서 외부 `run_id`/revision만 바꾸면 hook은 이를 읽지 않으므로 9초를 그대로 표시합니다. 이 불구별성을 독립 시험으로 확인했습니다. 임의로 실행 경계를 추정하지 않았습니다. 실제 같은 접수 재검사/취소/재시작이 해당 조건으로 도달하는지는 전체 앱과 백엔드 실행 증거가 필요합니다. 도달한다면 실행 ID 전달 또는 재마운트 계약을 담당자와 먼저 검토해야 합니다. 이를 해결 완료나 새 확정 결함으로 단정하지 않습니다. `withAnswers`도 마운트 안에서 유지되는 상태이므로 실행 ID 도입 시 함께 검토해야 합니다.

전체 앱의 재조회·pacer·질문 유지와 실제 서버 재시작, OS 절전, 최신 원격 통합 및 배포 수락은 미확인입니다(운영 수락 분모 모름). 후속 보고서의 이 한계를 닫지 않습니다. 프런트 격리 검토이며 병합하지 않았으므로 백엔드 필수 3관문은 이번에 재실행하지 않았습니다. 이전 2/3 = 66.7% HOLD를 새 통과율로 재사용하지 않습니다. scanner/XML·기존 5탐지를 고치거나 예외·이동·삭제하지 않았습니다.

[실행 집계·보호 확인](../evidence/2026-10-29_st4f732-edge-independent-review/summary.json) · [기존 경계 재현](../evidence/2026-10-29_st4f732-edge-independent-review/checks.json) · [독립 SSE 결과](../evidence/2026-10-29_st4f732-edge-independent-review/sse.json) · [SSE runner](../evidence/2026-10-29_st4f732-edge-independent-review/sse.cjs) · [변이](../evidence/2026-10-29_st4f732-edge-independent-review/sse-mutation.json) · [인계](../../../../wiki/handoff/2026-10-29_st4f732-edge-independent-review.md).
