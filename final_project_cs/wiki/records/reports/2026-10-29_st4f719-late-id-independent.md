---
type: report
title: ST4F-719 late id mutation 독립 검토 — 미리보기 소유권 누락으로 수락 보류
status: draft
domain: travel
---

2026-10-29 KST. [재개 후보](../../../../wiki/handoff/2026-10-29_st4f719-late-id-mutations-resumed.md)를 기존 `scratch/st4f719-blocker-independent-20261029/repo`에서 독립 검토했습니다. **후보 수락 불가·보안 HOLD 유지**입니다. 원본 제품 코드 반영·커밋·push·배포·다른 프로필 수정·자료 삭제는 하지 않았습니다. 새 checkout·의존성 설치·DB 전체 사본·production build도 만들지 않았습니다.

## 발견한 결함

**[P1] `useServerReview.previewRecommendAll()`의 늦은 A 응답이 계정 전환 뒤 마운트된 화면의 미리보기 상태에 들어갑니다.** `frontend/apps/web/src/features/plan-check/use-server-review.ts:471`의 `await` 다음 `setPreviewed`에는 `active()` 검사가 없습니다. 같은 파일의 변경 저장·되돌리기·재검증 응답에는 검사가 있습니다. `Providers`는 계정 전환 때 query 캐시를 비우지만 화면 트리는 마운트한 채 유지합니다. 따라서 query 객체 경계만으로 React 상태까지 보호되지 않습니다. 미리보기 반환 조건도 intake id와 revision만 비교하며 계정 scope는 보지 않습니다.

독립 Edge 탐침은 A의 autofix dry-run 응답을 보류하고 실제 PG 쿠키를 B로 교체한 뒤 `/auth/me` 재조회로 B의 privacy scope를 확인합니다. 이후 응답을 풀면 캐시에는 표식이 없지만 마운트된 `IntakeReview`의 preview state에는 A 응답 전용 표식이 남습니다. 실제 PG 인증 실행 **0/1 = 0% 통과**, 실패 **1/1 = 100% 재현**입니다. 같은 시험의 캐시 전환 대조도 0/1 통과입니다. 이는 실제 여행 API 쓰기나 운영 개인정보 노출의 재현이 아니라 합성 여행 응답을 이용한 화면 상태 격리 실패입니다.

원인 대조로 `setPreviewed` 직전 `if (!active()) throw gone();` 한 줄만 임시 삽입한 실제 PG 실행은 **1/1 = 100%** 통과했습니다. 진단 뒤 후보 파일을 바이트 단위 복구했습니다. 이 한 줄을 완성된 수정안으로 승인하지 않습니다. 재시도·사전 조회·추천 결과 반환과 취소 경로를 포함해 소유권을 검토한 후 별도 수정·재검토가 필요합니다.

## 네 경로와 취소·테넌트 경계

| 경로 | 확인 결과 |
|---|---|
| IntakeReview edit | onMutate에서 query 객체를 고정하고 성공과 stale_revision 오류에 적용합니다 |
| TripEdit reopen | 결과 intake가 아직 없으므로 출발 trip query 객체로 성공·오류·로컬 intake id 설정을 제한합니다 |
| TripScreen resumed | 보관된 완료 콜백과 SafetyPanel의 onMutate/onSuccess/onSettled가 trip query 소유권을 확인합니다 |
| useServerReview apply | 저장·되돌리기·재검증의 주요 적용 경로는 마운트 생명주기와 query 소유권을 함께 확인합니다. 위 미리보기 분기는 누락입니다 |

실제 PG 인증·Edge에서 네 경합 차단과 네 정상 대조 **8/8 = 100%**, 기존 개인정보·세션 시험 **10/10 = 100%**입니다. mutation 응답은 합성 stub이며 resumed는 실제 화면에 전달된 완료 콜백 경합을 검사합니다. 운영 재난 해제나 실제 여행 mutation 종단 시험으로 확대하지 않습니다.

계정 전환은 `client.clear()`를 동기적으로 호출합니다. 설치된 TanStack 구현에서 query 제거는 destroy → cancel로 연결됩니다. 추가 시험은 A query의 AbortSignal 즉시 취소와, 취소를 무시하고 완료되는 promise가 같은 키의 B 데이터를 덮지 못함을 확인했습니다(**1/1 = 100%**). mutation HTTP 요청 자체가 계정 전환으로 전부 취소된다는 뜻은 아닙니다. 응답 적용 거부가 별도로 필요합니다.

실제 PG의 별도 테넌트 probe는 자기 테넌트 쿠키 조회 성공·다른 테넌트 조회 거절·동일 세션 해시의 tenant-bound privacy scope 차이를 **3/3 = 100%** 확인했습니다. 브라우저 A/B fixture는 같은 테넌트의 서로 다른 고객이며, 다른 테넌트 간 여행 쓰기 브라우저 시험을 했다고 주장하지 않습니다.

## 관문과 Git 실행 환경

실제 PG 인증·Edge 변이에서 `queryOwner`를 항상 true로 바꾸면 네 경합 시험이 모두 실패했습니다. 목표 검출 **4/4 = 100%**입니다. 해당 실행의 등록 8건은 실패 4·정상 대조 선택 제외 4로, 전체 등록 기준 실행은 **4/8 = 50%**입니다. 정상 대조는 앞선 8/8 실행에서 별도로 통과했습니다. finally 복구 후 후보 소스 **12/12 = 100%**, scanner/XML **2/2 = 100%** 시작 해시 일치를 확인했습니다.

| 검사 | 직접 실행 결과 |
|---|---|
| Vitest | 1304/1304 = 100%, 기존 1303 + 독립 취소 시험 1, 실패·건너뜀 0 |
| TypeScript | exit 0 |
| PG 계약 | 367/367 = 100% |
| PG DoD | 26/26 = 100% |
| PG 쿠키 e2e | 38/38 = 100% |
| 보안 | 124/125 = 99.2%, 기존 보호 XML 검출로 실패 1 |
| 필수 관문 | 2/3 = 66.7%, 보안 HOLD |

기존 보관 `git-tool/cmd/git.exe`를 재사용했습니다. Authenticode는 **Valid**, 서명자는 Johannes Schindelin, 실행 버전은 `2.56.0.windows.4`입니다. 위치는 `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/scratch-candidates-20261029d/files/tf106-20261029/continue-711-20261029/git-tool/cmd/git.exe`입니다. 시험 전용 `setup.json`을 백업한 뒤 이 경로만 임시 지정하여 기존 `run_pg.py`가 PATH 앞에 넣게 했습니다. finally에서 setup 원래 바이트를 복구했습니다. 시스템·사용자 프로필·다른 서비스 설정은 바꾸지 않았습니다. 모든 Git 실행에는 `GIT_OPTIONAL_LOCKS=0`을 유지했습니다.

Git PermissionError는 해소되어 실제 보안 scanner가 실행됐고 기존 XML이 검출됐습니다. scanner·XML 내용/예외/추적 범위는 고치지 않았습니다. 기존 러너는 자식 실패에도 외부 종료 0을 내는 경우가 있어 **러너 exit 0을 통과 근거로 쓰지 않았습니다**. pytest XML과 Playwright JSON의 실패·건너뜀을 직접 셌습니다. 독립 재현 driver에는 결과 집계 검사를 추가했습니다. 원시 실패 로그는 공개 복사 없이 격리 사본에 보존했습니다.

## 보존·인계

이번 실행 이름의 로그·JSON·XML·브라우저 출력·독립검토 폴더·재현 스크립트 89파일은 집계 시 1,012,223바이트입니다. 기존 PG·Next 캐시·공개 evidence·추가 probe 소스·wiki 문서는 이 집계와 별도입니다.

종료 확인에서 앱·stub·API·PG **4/4 = 100%** 포트 연결 거부, setup 복구, 공개 12파일과 실제 fixture 문자열 119개의 대조 일치 0·인프라 검출 0을 확인했습니다. 공개 evidence는 집계 시 20,180바이트입니다. `disk_guard inventory`는 entries 0·unregistered_dirs 0, 여유 182,893,592,576바이트·최소 32,212,254,720바이트·목표 400,000,000,000바이트였습니다. Next 캐시는 재사용했으며 작업 전 실측이 없어 순증 분모 모름입니다. 디스크 목표 미달을 이유로 자료를 정리하지 않았습니다. 목차 수정 전 백업은 `independent-late-review/index-before-wiki.md`, `index-before-handoff.md`입니다.

루트/격리 사본/CS AGENTS·RULE·wiki 입구·개발 역할·코드 경로·웹 인증/격리 계약을 읽었습니다. 현재 `wiki/coord`와 루트 `_coord`는 디스크에 없었습니다. 기존 coord snapshot(`scratch/st4f719-review-20261029/coord-read.json`, 62개 중 관련 본문; identity 검토의 63개 이름 집계)을 참고했으며 최신 조정 상태를 확인했다고 주장하지 않습니다. 외부 메시지나 트래커 수정은 하지 않았습니다.

후보 소스 manifest 12개와 scanner/XML 2개는 검토 시작·종료 해시로 확인합니다. 임시 진단과 변이의 원본도 `independent-late-review/`에 보존합니다. 새 독립 시험만 격리 사본에 추가했습니다. 기존 인계·보고서의 과거 결과는 덮어쓰지 않았습니다.

[집계·재현 코드·해시](../evidence/2026-10-29_st4f719-late-id-independent/) · [인계](../../../../wiki/handoff/2026-10-29_st4f719-late-id-independent.md). 보안 HOLD와 미리보기 P1이 모두 남으므로 병합·push·배포 승인은 없습니다.
