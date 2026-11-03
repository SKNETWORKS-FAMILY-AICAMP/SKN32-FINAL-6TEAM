---
type: report
title: ST4F-718 IDB 대기 후속 수정과 구형 탭 차단 경계
status: draft
domain: travel
---

# ST4F-718 저장 후보 후속

2026-10-29 격리 후보의 queued IDB open 무응답을 수정했습니다. **통합 HOLD 유지**입니다. 담당은 이번 Codex 세션이며 독립 검토자·정책 승인자는 미확보입니다. 루트/CS 지침·RULE·wiki 입구·역할·코드 경로·문서 표준과 실제 coord NOTICE 61개를 읽었습니다. 원본 제품·운영·트래커 변경, commit/push/배포/삭제는 각각 0건입니다.

수정은 `scratch/st4f718-storage-fix-20261029/r`의 일반 파일 snapshot에만 있습니다. 이전 검토 snapshot의 src/tests/설정을 복사하고 기존 의존성을 junction으로 읽었습니다. 최신 통합 tip 검증이 아닙니다. 기존 사본은 수정하지 않았습니다. 후보 계약을 먼저 추가한 뒤 helper를 수정했습니다.

open 요청은 활성 이벤트 루프 기준 1,500ms 뒤 `HistoryOpenTimeout`으로 실패합니다. 요청 자체의 blocked 이벤트도 즉시 실패합니다. 취소 불가능한 요청은 늦은 upgrade 때 abort, 늦은 success 때 연결을 닫으며 key/claim/이관을 시작하지 않습니다. 자동 재시도·메모리/서버/다른 저장소 폴백은 없습니다. 차단 해제 뒤 별도 명시적 호출은 재시도할 수 있습니다. transaction도 1,500ms 후 abort를 시도하고 실제 complete/abort 결과로 끝납니다. 이미 완료된 commit을 timeout 성공으로 추정하거나 취소됐다고 거짓 보고하지 않습니다. crypto 실행·메인 스레드 정지·백그라운드 타이머 throttling까지 포함하는 전체 호출의 절대 wall-clock 보장은 아닙니다. timeout UI는 기존 blocked Toast/SignOut 경고를 사용하며 새 진행 UI는 추가하지 않았습니다.

| 직접 재실행 | 결과 |
|---|---|
| Vitest 전체 | 1,241/1,241 = 100%, 실패/skip 0 |
| tsc --noEmit --incremental false | 1/1 = 100%, exit 0 |
| 기존 실제 Edge runner | 22/22 = 100% |
| 추가 실제 Edge 관측 | 9/9 = 100%, 결함 재현 포함; 수락률 아님 |
| 새 실제 Edge pending 시험 | 4/4 = 100% |
| 원본 scanner/XML SHA256 | 2/2 = 100% 보존 |

`setup.json`의 Node로 `browser.cjs`, `adversarial.cjs`, `pending.cjs`를 실행했습니다. 웹 cwd에서 Vitest `run --config review.vitest.config.ts --reporter=json --outputFile=.../web.json`, tsc를 실행했습니다. 로그·프로필·초기 준비 자료는 scratch에 보존했습니다. 기존 bundling use-client 경고가 있었으며 오류로 숨기지 않았습니다. npm 설치·전체 Next build·PG/필수 관문 재실행은 하지 않았습니다. 선행 보안 124/125 = 99.2%, 필수 2/3 = 66.7% HOLD는 과거 수치이며 이번 결과로 승격하지 않습니다.

실제 Edge 두 탭에서 blocked upgrade 뒤 queued claim이 제한 시간 후 명시적 실패하고 blocker 해제 뒤에도 같은 결과를 유지했습니다. 삭제 요청 뒤에 줄 선 신규 open은 만료 후 upgrade를 abort하여 DB/표식을 만들지 않았고, 명시적 재호출은 한 번 성공했습니다. 실제 SignOut 함수 본문을 추출해 stubbed logout/cache와 실제 IDB migration을 연결한 시험에서 계정 정리가 먼저 끝나고 busy/finally가 종료되며 timeout 코드·원문 잔존 경고가 표시됐습니다. 늦은 open은 원문을 삭제하지 않았습니다. 전체 TripScreen/SignOut React mount·접근성·실서버 수락은 아닙니다. 기존 runner의 quota commit abort는 주입 오류이며 native IDB quota 발생 증거가 아닙니다.

**구형 탭 P1은 미해결입니다.** 구형 코드는 새 프로토콜·IDB·배포 플래그를 읽지 않으므로 새 탭에서 이를 원자적으로 막을 수 없습니다. 새 이관 뒤 옛 v1 알고리즘의 중복 허용·raw ID 재생성은 이번에도 재현됐습니다. 재이관·storage listener·polling 삭제·raw tombstone으로 해결됐다고 주장하지 않습니다. old→new/new→old/동시 쓰기/정지 후 복귀를 포함해 구형 쓰기 탭이 종료됐음을 보장하는 배포 절차가 아직 없습니다. 이 절차의 실제 검증 전에는 후보를 활성화하거나 통합하지 않습니다. 기존 전체 구형 앱 mount도 검증하지 않았습니다.

**영속 HMAC 식별자 정책은 승인하지 않았습니다.** 비추출 키도 동일 origin membership oracle을 막지 못합니다. helper의 “never customer data” 설명은 삭제했습니다. 로그아웃 뒤 재식별 가능한 표식 보존, 회원/게스트 사전 안내, 철회·삭제·여행/계정 삭제 연계·보존 종료는 매니저·웹/인증·개인정보 담당의 확정 사양이 필요합니다. 키만 남고 표식이 논리적으로 삭제된 경우 재생을 재허용하는 탐지 한계도 그대로입니다. 익명화·전체 손상 차단·법적 적합성은 주장하지 않습니다.

후속은 정책 확정, 구형 쓰기 탭 퇴역 절차와 실제 다중 탭/복원 수락, 최신 통합 tip에서 최소 patch 재검증, 실제 컴포넌트 mount/회원·게스트/계정 전환, native quota·다른 지원 브라우저·축출 검증입니다. 운영 완료 분모 모름입니다. scanner/기존 XML/허용 목록/판정 규칙 변경·예외는 0건이며 이전 보안 HOLD를 유지합니다.

이 patch는 **이전 storage-policy 후보에 대한 helper 1파일 추가 델타**입니다. 이전 bundle 전체를 통합하지 마십시오. [후속 델타](../evidence/2026-10-29_st4f718-storage-wait-continuation/continuation.patch) · [실행 집계](../evidence/2026-10-29_st4f718-storage-wait-continuation/summary.json) · [pending 재현](../evidence/2026-10-29_st4f718-storage-wait-continuation/pending.cjs) · [관측](../evidence/2026-10-29_st4f718-storage-wait-continuation/pending.json) · [후보 정책](../evidence/2026-10-29_st4f718-storage-wait-continuation/credits-device-history.md).
