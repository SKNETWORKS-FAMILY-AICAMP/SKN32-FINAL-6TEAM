---
type: handoff
title: ST4F-719 독립 검토 차단 결함 격리 수정 — 독립 재검토 인계, 보안 HOLD 유지
status: draft
domain: travel
---

# 진행 표 (구역별 갱신)

| 구역 | 상태 | 근거 |
|---|---|---|
| 1. 사본·재현 | 완료 | 새 격리 사본 `scratch/st4f719-blocker-fix-20261029/`(`--no-hardlinks --no-checkout`, 기준 `656579fe3`, `candidate.patch` SHA-256 `52bbc414…e68b`). manifest 18/18 내용 일치(manifest는 CRLF 작업본 기준, 사본은 LF blob — 줄끝 정규화 비교). 기존 화면 6파일 기준 60/61, 후보 53/61(새 실패 7) 재현. focus 재조회 채팅 답 유실·로그아웃 경합 재현 |
| 2. 수정 | 완료 | 아래 「수정 내용」. Vitest 1290/1290(후보 1260 + 복원 22 + 새 8), tsc 1/1 |
| 3. 관문·전체 회귀 | 완료(자체) | 실제 PG: 계약 367/367, DoD 26/26, 쿠키 e2e 37/37(+2 새), 보안 124/125(기존 `st4f728-guest-logout/security-ready.xml`과 같은 실패, HOLD). 실제 인증 Edge 수락 10/10, 독립 탐침 3/3, 새 경합 spec 4/4, `session.spec` 11/11. API 탐침: 엄격 비교 23/24(옛 adopt 201 vs 표 200, 둘 다 허용 — 503 해소), 차단 계정 교환 403·발급 없음. 전체 화면: 기준 910/954, 후보 919/958. 단독 재실행 후보·기준 각 36/37이며 **새 회귀 0**. 변이: Py 2/2·Vitest 3/3·Edge 4/4 검출, 복구 hash 일치 |
| 4. 독립 재검토 인계 | 인계 | 아래 「독립 재검토자에게」 |

[보고서](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-blocker-fix.md) · [증거](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-blocker-fix/)(`full-candidate.patch`: 기준 위 29파일, 적용 사전검사·blob 29/29. `blocker-fix-on-candidate.patch`: 후보 위 증분).

# 수정 내용(사본에서만, 원본 제품 코드 수정 0)

1. `Providers`의 `Fragment key`·`OnboardingProvider`의 `key` 재마운트 제거. 온보딩은 렌더 중 소유자 조정으로 A→B·A→없음일 때만 메모리를 비우고, 첫 세션(없음→게스트)은 직전 초안을 유지합니다. 화면 캐시는 다른 계정이 들어오거나(A→B) 로그아웃·다른 탭 종료(`retired`)일 때만 비웁니다. 401은 오류 화면을 유지합니다.
2. 같은 세션 판정을 객체 비교에서 `sameSession`(같은 객체 또는 같은 인증 privacy scope)으로 바꿨습니다(`trip-chat` onSuccess, `stream` 재연결, `sessionChecked`, `logout`). 강제 재조회가 같은 세션·같은 세부값을 받으면 객체를 그대로 둡니다.
3. `logout`은 다른 계정이 들어온 경우에만 null입니다. `SignOut`은 await 전에 동의 사본·온보딩을 지웁니다.
4. `adopt-ticket`을 `_admin_access` 점검 예외에 추가(옛 `adopt`와 같음). `adopt-cookie`는 표 발급 뒤 차단된 계정을 403으로 거절하고 표 사용을 되돌립니다.
5. 확정 응답 뒤 다른 scope의 `onboarding.v3:*`를 정리합니다(브라우저 재시작·서버 종료로 주인 잃은 설문).
6. mock stub에 두 단계 이관과 「401·로그아웃은 삭제 Set-Cookie 없음」을 반영했습니다. 새 계약을 모르는 기존 시험 여섯 곳과 `helpers.forgetStartScreen`은 `contract_correction` 주석을 달고 의도를 유지한 기대값으로 바꿨습니다. 후보 patch에서 빠진 시험 3파일(22건)을 다시 넣었습니다.

원본 제품 코드·보안 scanner·보호 XML·기존 실패 원문은 수정하지 않았습니다. 커밋·push·배포·병합·삭제는 0건입니다. 보안 HOLD는 유지합니다. 반영은 사용자 지시(2026-10-29)에 따라 매니저 브랜치(`role-manager`) 담당이 맡고, HOLD가 정식으로 풀린 뒤에만 합니다. 공개 증거·보고·인계에서 비공개 fixture 값 51개와 겹치는 값을 찾았고 0건이었습니다.

# 독립 재검토자에게

1. `full-candidate.patch`를 `656579fe3`의 새 사본에 적용하고 `candidate-manifest.json`(29건)을 대조합니다. 분모는 그 사본에서 직접 셉니다.
2. 기존 `tests/live` 전체를 기준과 후보에서 비교합니다. 공통 실패 36건은 영상·촬영·지도 SDK 등 환경 문제입니다. 동시 부하에서만 실패한 시험 3건(`login-consent-flow`:32, `preferences` 영어·키보드, `trip-list` 최근 여행 카드)은 단독으로 다시 돌립니다.
3. 판단할 것:
   - stub 삭제 Set-Cookie 제거와 `contract_correction`이 약화가 아닌지
   - guest→member 로그인 때 설문 메모리를 비우는 정책
   - 표 TTL 안의 폐기 키 교환과 이관 한 번에 rate 2단위를 쓰는 한계
4. 남은 것:
   - `preferences.spec.ts`:451은 기준에서도 실패하며 원인은 아직 모릅니다.
   - identity-test fixture에서는 동의 gate 때문에 로그아웃 확인 문구를 셀 수 없습니다. 실제 계정 화면 spec으로 대신 확인했습니다.
   - API 탐침은 새 DB에서 실행합니다. 같은 DB를 다시 쓰면 이미 있는 `admin_records` 행 때문에 중단됩니다.
   - production build는 다시 실행하지 않았습니다(`node_modules` junction).
