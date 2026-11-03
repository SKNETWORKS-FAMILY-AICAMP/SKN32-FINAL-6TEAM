---
type: handoff
title: ST4F-719 identity-bound 독립 검토 — 3개 경계 재현, HOLD
status: draft
domain: travel
---

# 한 일 목록

- 루트/CS 지침·wiki·인계·현재 coord NOTICE 63/63 = 100%를 읽고 이전 전달 patch를 새 no-hardlinks 사본에서 검토했습니다.
- 실제 Edge+새 PG 인증 API에서 계정 변경/다른 탭 로그아웃의 온보딩 잔존(P1), 같은 scope 재조회 뒤 실제 폐기 401 무시(P2), 무효 쿠키+유효 옛 키 이관 실패(P2)를 재현했습니다.
- 최종 브라우저 4/8 = 50%, 변이 검출 4/4 = 100%, 기존 웹 1268/1268·추가 거절 9/9·쿠키 e2e 28/28 = 100%입니다.
- 계약 367/367·DoD 26/26 = 100%, 보안 124/125 = 99.2%이므로 **필수 2/3 = 66.7%, 보안 HOLD 유지**입니다. 선정 보호 파일 740/740 = 100% 동일입니다.
- 공개 evidence에 실제 쿠키·옛 키·CSRF가 없는지 검사했습니다. 전용 PG 정상 종료·접속 거부를 확인했고 사본·데이터·실패 로그를 보존했습니다.

[독립 보고](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-identity-independent.md) · [정제 증거](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-identity-independent/) · [검토 대상 인계](2026-10-29_st4f719-identity-bound.md).

작업 사본·재현 runner는 `scratch/st4f719-independent-20261029/`입니다. 기준 `656579fe37d613a64caeb96cdb344958890a1c4d`+이전 `candidate.patch`이며 최신 원격 통합본이 아닙니다. 제품 코드 원본으로 복사하지 않았습니다. 구현 수정·운영/고객/트래커 쓰기·커밋·push·배포·삭제는 하지 않았습니다.

다음 담당자는 보고서의 P1/P2 세 경계를 고치고 동일 scope/다른 B scope, 두 탭, 옛 키의 무효 쿠키 유무를 함께 재검증해야 합니다. 혼합 자격 거절이나 보호된 XML/scanner를 약화하지 않습니다. 외부 OAuth·다른 브라우저·운영 여행 API·동결 탭·최신 통합의 수락 분모는 모릅니다. 독립 검토 수행은 확인했으나 수락·릴리스 승인은 보류합니다.
