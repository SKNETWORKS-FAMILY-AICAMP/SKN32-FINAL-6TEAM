---
type: handoff
title: ST4F-719 세션 소유권 격리 수정 — HOLD
status: draft
domain: travel
---

# 한 일 목록

- 이전 후보의 계정 경계 실패를 새 baseline에서 1/3 = 33.3%로 재현했습니다.
- 새 격리 사본에 서버 HMAC `privacy_scope`, scope별 diff 보관, 다른 탭 종료 전달, 늦은 logout·UI 정리 소유권 검사, 새 쿠키를 지우지 않는 서버 응답을 구현했습니다.
- 전달 patch만 적용한 새 사본의 웹 1268/1268·타입/diff 2/2, 서버 쿠키 28/28, 실제 Edge+로컬 인증 API 3/3, 일반 카드 Edge 5/5, 변이 검출 4/4 = 100%입니다.
- 필수는 계약 367/367·DoD 26/26, 보안 124/125로 **2/3 = 66.7% HOLD**입니다. 기존 XML/scanner 해시 740/740 = 100% 동일입니다. 운영 쓰기·트래커 쓰기·커밋·push·배포·파일 삭제는 0건입니다.

# 이어받을 곳

[보고·범위·실패 기록](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-identity-bound.md) · [전달 patch/증거](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-identity-bound/).

사본은 `scratch/st4f719-identity-20261029/`의 repo(수정/브라우저), baseline-repo(이전 실패), delivery-repo(전달 patch만 적용), mutation-web(독립 단위 변이)입니다. 기준은 `656579fe37d613a64caeb96cdb344958890a1c4d`; 최신 원격이나 718/731/732를 통합하지 않았습니다. 전용 PG는 종료·접속 거부 확인했고 원자료를 남겼습니다. 원본 제품 코드에 역복사하지 마세요.

공유 인증 계약과 쿠키 폐기 정책을 독립 검토한 뒤 최신 통합 사본에서 3관문·브라우저 수락이 필요합니다. 삭제 Set-Cookie 제거와 옛 키+무효 쿠키 adoption 호환성도 확인해야 합니다. 실제 외부 OAuth·운영 여행 API 전체 흐름·차단/동결 탭 즉시 전달·실기기 수락은 분모 모름입니다. 기존 XML/scanner/HOLD를 우회하지 않고, 이 인계는 배포·push 승인이 아닙니다.
