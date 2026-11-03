---
type: report
title: ST4F-719 미리보기 계정 격리 P1 수정 후보
status: draft
domain: travel
---

2026-10-29 KST. [독립검토의 P1](2026-10-29_st4f719-late-id-independent.md)을 기존 격리 후보 `scratch/st4f719-blocker-independent-20261029/repo`에서 수정했습니다. 원본 제품 코드·운영 DB·트래커·원격에는 반영하지 않았습니다. 새 clone·DB 전체 사본·의존성 설치·production build·커밋·push·배포·삭제는 0건입니다. 기존 scanner/XML 보안 HOLD를 유지합니다. 변경 담당·시험·자체 검토는 이 Codex 세션이며 독립 승인으로 표시하지 않습니다.

## 수정 범위

제품 변경은 `final_project_cs/frontend/apps/web/src/features/plan-check/use-server-review.ts` 한 파일입니다. API·권한·DB 계약은 변경하지 않습니다.

- 사전 dry-run 요청과 저장된 미리보기에 출발 query의 소유권 검사 함수를 붙였습니다. 같은 intake id·revision이어도 다른 query 수명의 응답은 재사용하거나 표시하지 않습니다.
- `previewRecommendAll`은 성공 반환·로컬 상태 저장·실패 후 재시도·최종 오류 처리 전에 요청 소유권을 검사합니다. 소유권이 끝난 응답은 자료를 반환하지 않고 일반 `item_gone` 오류로 종료하며 이전 오류의 값이나 메시지를 옮기지 않습니다. 이전 계정의 실패 때문에 새 계정으로 재시도하지 않습니다.
- `hasRecommendation`은 시작과 완료 때 소유권을 확인하고 끝난 소유권에는 `null`을 반환합니다. 실패한 사전 요청을 지울 때 기존 promise 일치 검사를 유지합니다.
- 취소와 실제 계획 적용은 요청 세대를 끝냅니다. 취소 뒤 늦은 성공이나 앞선 요청의 역순 완료가 미리보기를 다시 열지 못합니다. 이전 계정의 보관된 취소 콜백은 새 계정 미리보기를 지우지 못합니다.

HTTP 전송이 모두 취소된다고 주장하지 않습니다. 이미 진행 중인 요청의 **응답 적용·반환과 후속 재시도**를 차단하는 수정입니다.

## 직접 검증

| 검사 | 결과 |
|---|---|
| 신규 hook 경계 시험 | 17/17 = 100% |
| 전체 웹 Vitest | 1321/1321 = 100%, 실패·건너뜀 0 |
| TypeScript | exit 0 |
| 실제 PG 인증·Edge 미리보기 | 8/8 = 100%, 실패·건너뜀·flaky 0 |
| 실제 PG 인증·Edge 기존 네 변경 경로 | 8/8 = 100% |
| 실제 PG 인증·Edge 개인정보·세션 | 10/10 = 100% |
| 단위 변이 | 7/7 = 100% 검출 |
| 실제 PG 인증·Edge 소유권 변이 | 목표 3/3 = 100% 검출, 등록 8건 중 실패 3·정상 5·건너뜀 0 |
| 변이 복구 후 신규 hook | 17/17 = 100%, 후보 manifest 3/3 = 100% 일치 |
| PG 계약 | 367/367 = 100% |
| PG DoD | 26/26 = 100% |
| PG 쿠키 e2e | 38/38 = 100% |
| 보안 | 124/125 = 99.2%, 기존 보호 XML 검출 1건 |
| 필수 관문 | 2/3 = 66.7%, 보안 HOLD |

신규 단위 시험은 직접/사전 요청의 늦은 성공·실패, 재시도 도중 전환, 동일 id·revision의 사전 응답 재사용 거절, 이미 저장된 미리보기 표시 격리, 이전 취소 콜백, 진행 중 취소, 역순 완료, unmount, 추천 여부의 성공·실패와 정상 재시도·최종 stale 오류를 검사합니다. 변이는 요청 소유권·재시도 전 검사·사전 요청 소유권·표시 검사·취소 소유권·요청 세대·추천 여부 반환 검사를 각각 제거했으며 17건 중 각각 6·2·1·1·1·2·1건이 실패했습니다. 변이 후 소스를 바이트 단위 복구했습니다.

Edge의 8건은 성공·실패·재시도·취소 각각에 A→B 전환과 동일 계정 대조를 둡니다. 실제 PG 쿠키로 `/auth/me`의 B privacy scope를 확인한 뒤 보류 응답을 해제하며, 캐시·마운트된 React hook 상태·호출 결과를 검사합니다. 계정은 합성 fixture이고 여행 응답은 stub입니다. 운영 여행 mutation 종단 검증이나 실제 고객 자료 노출의 재현으로 확대하지 않습니다. 기존 네 변경 경로 8건과 개인정보·세션 10건도 함께 재실행했습니다.

첫 Edge 실행은 6/8 = 75%였습니다. 시험에서 B의 정상 warm-up을 A의 재시도로 함께 센 오류와 전환 뒤 사라진 PlanCheck에서 취소 콜백을 찾는 오류를 수정했습니다. A 쿠키에 속하는 요청만 값 출력 없이 세고 원래 보관된 콜백으로 검사합니다. 첫 실패 JSON·로그·브라우저 출력은 보존했습니다. 첫 1318건 단위 집계 후 경계 3건을 추가한 최종 집계는 1321건입니다.

## 실행·보존 경계

기존 PG 클러스터와 Next 캐시를 재사용하고, PG를 쓰는 실행은 순차로 진행했습니다. 기존 서명된 Git helper의 Authenticode Valid와 서명자를 확인하여 시험 전용 `setup.json`에만 임시 지정했습니다. `GIT_OPTIONAL_LOCKS=0`을 유지하고 finally에서 설정을 원래 바이트로 복구합니다. 기존 러너는 자식 실패에도 exit 0을 내므로 JSON/XML의 실패·오류·건너뜀을 직접 집계했습니다.

재현 명령은 작업 폴더의 `preview_fix_web_final.py`, `preview_fix_mutants.py`, `preview_fix_gates.py`, `preview_fix_browser_mutant.py`입니다. 정상 브라우저 실행은 `BROWSER_SPECS=preview-owner-fix,late-id-mutations,identity`, `API_PROBES=0`, `INDEP_PROBES=0`, `LATE_REAL=1`로 `run_late_gates.py browser-preview-owner-final`을 실행합니다. 이름이 이미 사용된 실행·문서는 덮어쓰지 말고 새 이름을 사용합니다. 변이 러너는 후보를 일시 수정하므로 다른 검증과 동시에 실행하지 않습니다.

기존 source manifest 12개 중 의도한 hook 한 파일만 변경했고 나머지 11/11 = 100%, 보호 scanner/XML 2/2 = 100% 해시 일치를 확인했습니다. XML 내용·scanner·예외·추적 범위를 고치지 않았습니다. 실패 원시 로그와 fixture/cookie는 공개 복사하지 않습니다. 공개 evidence에는 코드·패치·집계·해시만 남기며 fixture 값 대조와 기존 scanner 함수 검사를 별도로 수행합니다.

루트·후보 AGENTS, CS RULE, wiki 입구·개발 역할·코드 경로·웹 인증/격리 계약을 확인했습니다. 현재 `wiki/coord`와 `_coord`는 없으므로 기존 `scratch/st4f719-review-20261029/coord-read.json`을 참고했습니다. 최신 조정 상태·다른 담당자의 승인·통합 예약을 확보했다고 주장하지 않습니다. 외부 메시지는 보내지 않았습니다.

Edge 소유권 변이는 실제 PG 인증 전환의 늦은 성공·재시도 성공·보관 취소 경로에서 3/3 = 100% 검출했습니다. 등록 8건의 나머지 5건은 통과하고 건너뜀은 0건입니다. 원본 수정안으로 복구 후 신규 hook 17/17 = 100%와 후보 manifest 3/3 = 100% 일치를 다시 확인했습니다.

종료 포트·공개 자료 검사·디스크 실측은 [집계](../evidence/2026-10-29_st4f719-preview-privacy-fix/summary.json)와 [인계](../../../../wiki/handoff/2026-10-29_st4f719-preview-privacy-fix.md)에 기록합니다. 필수 관문의 보안 HOLD가 남으므로 병합·push·운영 반영 승인은 없습니다.

최종 포트 4/4 = 100% 종료, setup 복구, 공개 10파일·fixture 문자열 119개 대조 일치 0·인프라 검출 0입니다. 공개 검사 준비는 기본 Python의 pytest 부재로 2회 실패했고 기존 시험 Python에서 통과했습니다. 공개 evidence 32,878바이트, 이번 실행 관련 측정 97파일 1,012,774바이트이며 기존 PG·Next 캐시와 이후 문서·측정 파일 추가분은 별도입니다. inventory entries 0·unregistered_dirs 0·여유 182,654,906,368바이트, 최소 32,212,254,720바이트·목표 400,000,000,000바이트입니다. Next 캐시 순증은 사전 측정이 없어 분모 모름입니다. [공개 검사 영수증](../evidence/2026-10-29_st4f719-preview-privacy-fix/privacy-receipt.json).
