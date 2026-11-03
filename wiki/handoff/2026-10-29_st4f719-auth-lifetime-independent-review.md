---
type: handoff
title: ST4F-719 인증 수명 독립 검토 — 수락 보류
status: draft
domain: travel
---

기존 인증 수명 후보를 독립 검토했습니다. **HOLD 유지**입니다. 집중 시험 32/40 = 80%, 실패 8개입니다. 세 인증 watcher의 401 무효화 누락, 늦은 401이 전환 복귀/로그아웃 후 같은 계정 새 로그인을 지우는 경합, 늦은 로그아웃의 같은 계정 재로그인 취소를 재현했습니다. 공개 API 401과 본문 없는 HTTP 401도 무효화 범위 밖입니다.

실제 PG 인증·Edge 미리보기 28/28, 기존 실제 인증/로그아웃 Edge 10/10 = 100%가 통과했습니다. 업무 응답은 stub이며 실제 PG 업무 쓰기 전수 검증은 아닙니다. 제품 소스·보안 파일 508/508, 보호 scanner/XML 2/2 = 100% SHA256 일치입니다. 이전 필수 2/3 = 66.7% 보안 HOLD를 유지하고, 전체 관문 재실행 완료로 간주하지 않습니다.

한 일 목록: 규칙·wiki·coord snapshot 읽기, 기존 격리 후보 fetch 경로 감사, 독립 401/경합 시험, 실제 PG 인증 Edge, 오류 화면 검증, 해시 확인, 보고서·인계 작성입니다. 후보는 `scratch/st4f719-blocker-independent-20261029/repo`, 새 증거는 같은 상위 폴더의 `auth-lifetime-independent/`와 `browser-auth-lifetime*-independent*` 로그입니다. 제품 수정·clone·운영/사용자 데이터 접근·push·배포·삭제는 0건입니다.

다음 담당자는 요청 시작 인증 세대가 401/로그아웃 완료까지 전달되도록 수정하고, 같은 세션 refresh는 유지하면서 새 로그인은 보호해야 합니다. 세 watcher도 함께 검토해야 합니다. 최신 coord·통합 tip은 미확보이며 예약은 없습니다. 기존 손상 문서를 덮어쓰지 않았습니다.

상세 근거·시험 명령·한계는 [독립 검토 보고서](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-auth-lifetime-independent-review.md)를 봅니다.

종료 보충: 실제 여행 목록의 401 오류 유지 시험 1/1 = 100%, 스크린샷 직접 확인했습니다. 최초 한글 기대 문자열 손상 실패는 별도 보존했고 수정된 시험을 고유 이름으로 재실행했습니다. app/stub/api/PG 4/4 = 100% 포트 종료를 확인했습니다. 새 증거·시험·browser 로그의 명시 측정 범위 40파일 357,182 bytes이며 기존 PG/Next 순증은 분모 모름입니다. 최종 inventory·결과 JSON은 `auth-lifetime-independent/`에 있습니다. 이 세션의 로컬 검증 사용은 끝났으며 예약·운영 수락은 없습니다.
