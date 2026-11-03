---
type: handoff
title: ST4F-719 개인정보·인증 복구 후보 — 실제 Edge 10/10, 보안 HOLD
status: draft
domain: travel
---

# 한 일 목록

- 기존 독립 검토의 계정/다중 탭 온보딩 잔존, 같은 scope 실제 401 무시, 무효 쿠키+옛 키 이관 실패를 새 사본에서 재현했습니다. 기존 Edge 4/8 = 50%였습니다.
- 온보딩의 인증 scope 소유권·확정 종료 정리와 같은 scope 401 처리를 수정했습니다. 옛 키 복구는 cookie-free 표 발급과 cookie-only 교환으로 명시하고 혼합 자격 거절을 유지했습니다.
- 최종 Edge 10/10·웹 1282/1282·변이 4/4·쿠키/API 35/35 = 100%입니다. TypeScript·production build도 통과했습니다.
- 계약 367/367·DoD 26/26 = 100%, 보안 124/125 = 99.2%로 **필수 2/3 = 66.7%, HOLD 유지**입니다. 선정 원본 740/740 = 100% hash 일치입니다.
- 후보와 후속 patch, 명령·실패·보정·정제 근거를 보존했습니다. 전용 PG 종료·접속 거부를 확인했습니다. 원본 제품 코드·scanner·보호 XML 수정, 삭제, 커밋·push·배포·고객/트래커 쓰기는 0건입니다.

[보고서](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-privacy-auth-recovery.md) · [증거·후속 patch](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-privacy-auth-recovery/).

사본/runner는 `scratch/st4f719-privacy-fix-20261029/`입니다. 기준은 `656579fe37d613a64caeb96cdb344958890a1c4d`와 이전 검토 후보이며 최신 원격 통합본이 아닙니다. `followup.patch`는 이전 독립 사본에 적용 사전검사했습니다. `candidate.patch`는 기준 위의 제품/계약/시험 후보입니다. 브라우저 fixture route는 제품 patch에 포함하지 않습니다.

이번 세션은 구현·자체 검증이며 독립 승인으로 표시하지 않습니다. 다음 담당은 공유 인증 계약과 패치의 독립 검토, 별도 보안 HOLD 해결을 맡아야 합니다. 외부 OAuth·다른 브라우저·운영 여행 API·최신 통합·운영 수락의 분모는 모릅니다. 보호 자료 삭제·scanner 완화·혼합 자격 허용·무조건 쿠키 삭제로 해결하지 않습니다. push·배포 승인은 없습니다.
