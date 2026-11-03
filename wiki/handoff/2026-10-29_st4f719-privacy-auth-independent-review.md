---
type: handoff
title: ST4F-719 개인정보·인증 복구 후보 독립 검토 — 기존 화면 회귀 7건, 수락 불가
status: draft
domain: travel
---

# 한 일 목록

- 후보 patch를 새 격리 사본에 적용했고 manifest 18/18 일치를 확인했습니다. 계약 367/367, DoD 26/26, 쿠키 e2e 35/35, Edge 수락 10/10, Vitest 1260/1260, tsc를 재현했습니다. 보안은 124/125로 기존 XML 실패이며 **필수 2/3 = 66.7% HOLD**입니다.
- 실제 PG 인증 라우터에 독립 API 탐침 24건을 실행했습니다. 23/24이며, 점검 중 `adopt-ticket` 503 회귀가 있습니다. 권한 상승·혼합 자격·표 교차 사용은 찾지 못했습니다.
- 기존 화면 시험 6개 파일은 기준 60/61에서 **후보 53/61로 떨어졌고 새 실패는 7건**입니다. 이 중 4건은 scope key 재마운트가 원인임을 변이로 확인했습니다. 1건은 mock stub 계약 누락이고, 2건은 원인을 확인하지 못했습니다.
- 실제 Edge 재현: focus 재조회 때 처리 중인 채팅 답변이 유실됩니다(객체 비교). 로그아웃 경합 때 동의 사본이 남습니다. 끝난 scope의 설문이 localStorage에 남습니다.
- 보고 분모 1282에 후보에 없는 시험 22건이 들어 있음을 확인했습니다.
- 원본 제품 코드·scanner·보호 XML 수정, 커밋·push·배포·삭제는 0건입니다.

[보고서](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-privacy-auth-independent-review.md) · [증거](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-privacy-auth-independent-review/).

# 다음 담당

1. `Providers` boundary와 `OnboardingProvider`의 key 재마운트를 없애거나 범위를 좁힙니다. 기존 live 시험 6파일을 기준 60/61 이상으로 되돌립니다.
2. `trip-chat` onSuccess와 `SignOut`의 ended 검사를 객체 비교에서 scope 비교로 바꿉니다. focus 재조회 경합 시험을 추가합니다.
3. `adopt-ticket`을 점검 예외 목록(`_admin_access`)에 넣을지 결정하고, mock stub에 두 단계 이관을 반영합니다.
4. 주인 없는 `onboarding.v3:*` 정리 정책을 정하고, 분모는 실제 후보 파일 기준으로 다시 셉니다.

보안 HOLD는 별도 정식 해결 대상이며 push·배포 승인은 없습니다. 사본은 `scratch/st4f719-privacy-independent-20261029/`이고, 비공개 fixture 자격은 그 안의 `actors-private.json`에만 있습니다.
