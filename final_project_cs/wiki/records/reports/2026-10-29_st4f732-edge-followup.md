---
type: report
title: ST4F-732 시계 경계 후속 수정과 브라우저 검증
status: draft
domain: travel
---

# ST4F-732 시계 경계 후속

2026-10-29 KST. 담당·자체 검토: 이번 Codex 세션. 독립 사람 승인이나 통합 완료를 뜻하지 않습니다. 원본 제품 쓰기·운영 쓰기·트래커 쓰기·commit/push/배포·삭제 0건. scanner/XML 및 ST4F-718·731 HOLD를 유지합니다.

루트/CS AGENTS·RULE, wiki 입구·역할, `web-intakes.md` 진행 계약과 실제 `planSteps`, hook, `reduceStream`, Reading/Checking 호출 경로를 확인했습니다. Hermes 로컬 `_coord/*NOTICE.md` 62개를 읽어 비공개 사본에 보존했습니다. 732 담당의 범위 해제·통합 HOLD를 확인했습니다. 처음 도구 검색에는 coord 커넥터가 없었지만 실제 로컬 coord 경로를 찾아 읽었습니다. 조정 메시지 전송은 하지 않았습니다.

## 계약 판단

`wiki/external/rest-endpoints/web-intakes.md`의 단계 순서와 재연결 재생 계약, `intake-events.ts`의 furthest 선택·같은 총수 역순 카운트 무시, `server-steps.ts`의 “one step has had no news” 정의가 근거입니다. 현재 표시 단계가 그대로인 앞 단계의 지연 패킷은 현재 단계의 소식이 아닙니다. 동일 값 replay도 새 진행이 아닙니다. 현재 단계의 packet 내용(총수·상세·recheck 포함)이 바뀌거나 단계가 바뀌면 새 기준점을 만듭니다. reading_api가 있으면 reading보다 우선하는 기존 규칙을 유지합니다. 서버 필드·SSE 계약 변경은 없습니다.

재시작은 관측한 current→null→current 경계(ended/received) 또는 A→B→A 단계 경계를 포함합니다. 같은 문자열 키가 재등장해도 이전 tick을 재사용하지 않도록 경계마다 별도 객체를 둡니다. 조건부 자기 state 갱신으로 첫 렌더부터 이전 tick을 배제하며, interval은 해당 경계 객체에 귀속됩니다. StrictMode에서 interval 1개·cleanup을 실제 React로 확인했습니다. 임의 시간 임계값·타임아웃 추측·무음 폴백을 추가하지 않았습니다. 기존 표시 기준 8초는 그대로입니다.

## 실행 증거

| 검증 | 결과 |
|---|---|
| 원래 hook Edge 재현 | 14/19 = 73.7%, 목표+기존4경계 실패 |
| 이전 후보 Edge 재현 | 15/19 = 78.9%, 기존4경계 실패 |
| 새 수정 확장 Edge | 21/21 = 100%, pageerror0 |
| 이전 후보 재삽입 음성 대조 | 결함 탐지5/5 = 100%, 전체16/21 = 76.2% |
| 전체 웹 Vitest | 1232/1232 = 100%, 실패·skip0 |
| TypeScript | 1/1 = 100%, exit0 |
| 원본 보호 해시 | 18/18 = 100%, XML 탐지5건 유지 |

격리 사본은 `scratch/st4f732-edge-followup-20261029/repo`이며 이전 독립검토 archive의 웹 소스를 새 디렉터리로 복사했습니다. 원본 Git 명령·설정 변경은 없습니다. 의존성 junction은 이전 검토와 같은 설치본을 읽습니다. 실행 명령은 setup의 node로 `browser.cjs`, `negative.py`, 웹 cwd에서 `node_modules/vitest/vitest.mjs run --reporter=json --outputFile=.../web.json`, `node_modules/typescript/bin/tsc --noEmit`입니다. runner·패치·집계는 아래 evidence에 있습니다. PowerShell이 Rolldown stderr 경고를 native error로 표시한 호출은 shell exit1이었으나 브라우저 JSON은 21/21·pageerror0입니다. Python 음성 대조의 subprocess exit0도 확인했습니다. 음성 대조 첫 실행은 예상 실패 수를 6으로 잘못 적어 하네스 단언이 실패했고 실제 5로 정정해 재실행했습니다. 제품 실패로 세지 않았습니다.

검증은 실제 React StrictMode·실제 reducer를 bundle한 독립 Edge 문서입니다. 기존 19경계에 현재 상세/총수/recheck·동일 replay 구분, reading_api 이후 지연 reading을 추가했습니다. 전체 앱·실제 SSE 서버 수락으로 일반화하지 않습니다. wall clock, 가상 timer catchup, CDP frozen/active는 OS 절전 수락과 구분합니다.

## 미해결·보류

경계 없이 동일 props로 실행 식별자만 바뀌면 이 hook 입력에는 그 사실이 없습니다. 실제 다른 접수 전환이 동일 컴포넌트·동일 props로 이어지는지 전체 앱에서 확인하고, 필요하면 실행 ID 전달 계약을 별도로 검토해야 합니다. 화면상 관측하지 못한 중간 상태도 추정하지 않습니다. 재시작의 실제 전체 앱 도달성·실서버 재연결·OS 절전·최신 원격 tip 통합 수락은 남으며 운영 수락은 분모 모름입니다.

이번 변경은 프런트 내부 시계만이며 통합하지 않았으므로 백엔드 필수3관문은 재실행하지 않았습니다. 이전 실행의 2/3 = 66.7% HOLD는 현재 통과율로 승격하지 않습니다. scanner·XML·기존 탐지5건을 수정/예외/이동하지 않았습니다. 새 공개 텍스트는 변경 없는 find_leaks로 검사했습니다. 모든 scratch·로그를 보존합니다.

[집계](../evidence/2026-10-29_st4f732-edge-followup/summary.json) · [수정 패치](../evidence/2026-10-29_st4f732-edge-followup/followup.patch) · [브라우저 runner](../evidence/2026-10-29_st4f732-edge-followup/browser.cjs) · [음성 대조](../evidence/2026-10-29_st4f732-edge-followup/browser-negative.json) · [보호 해시](../evidence/2026-10-29_st4f732-edge-followup/preservation-end.json).
