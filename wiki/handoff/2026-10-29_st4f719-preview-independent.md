---
type: handoff
title: ST4F-719 미리보기 개인정보 독립검증 — 릴리스 HOLD
status: draft
domain: travel
---

**릴리스 HOLD를 유지합니다.** 기존 후보를 실제 PG 인증·Edge로 독립 검증한 최종 결과는 21/24 = 87.5%입니다. A→B·A→B→A·같은 계정·취소·unmount는 통과했지만, 비인증 전환 뒤 늦은 성공·재시도 성공의 반환/미리보기 상태 저장, 늦은 실패의 후속 요청·stub 세션 생성 3건이 남았습니다. 기존 scanner/XML 보안 HOLD도 해소되지 않았습니다.

한 일 목록: 규칙·wiki·coord snapshot 확인, 기존 격리 후보 재사용, 6경계×4모드 Edge 시험, 비인증 P1 재현, 소유권 변이 검출과 바이트 복구, hook·PG 필수 관문·쿠키 회귀, 포트 종료·해시·공개 개인정보 검사, 인계·목차 작성입니다. 제품 수정·새 clone·운영/트래커 쓰기·commit·push·배포·삭제·scanner 예외는 0건입니다.

변이 1종은 정상 교차 계정 시험 8/8 = 100%에서 검출됐습니다. 복구 hook 17/17, PG 계약 367/367·DoD 26/26·쿠키 38/38 = 100%, 보안 124/125 = 99.2%, 필수 관문 2/3 = 66.7%입니다. 후보 3/3·상속 source 11/11·scanner/XML 2/2·종료 포트 4/4 = 100% 보존/종료 확인입니다.

실제 PG는 쿠키 인증 검증이고 여행 응답·새 세션 응답은 로컬 stub입니다. hook 상태·반환 경계 재현을 운영 mutation 또는 DOM 노출 증거로 넓히지 않습니다. 현재 query 소유권은 401에서 유지되므로, 오류 화면을 보존하면서 요청의 인증 수명은 별도로 끝내는 수정과 재검증이 필요합니다. 상세 원인·시험 준비 오류·명령·자료 위치는 [보고](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-preview-independent.md), 안전한 결과는 [공개 evidence](../../final_project_cs/wiki/records/evidence/2026-10-29_st4f719-preview-independent/)에 있습니다. 계정 값·cookie·원시 실패 로그는 공개 복사하지 않았습니다.

기존 후보와 로그는 `scratch/st4f719-blocker-independent-20261029/`에 보존했습니다. 이 세션의 로컬 검증 사용 범위는 반환했으며 통합 예약·릴리스 승인은 없습니다. 현재 coord 디렉터리가 없어 snapshot만 확인했고 최신 조정 상태·통합 tip은 미확보입니다. 기존 scratch 후보는 disk ledger lease가 없어 새 등록이나 타 소유권 release를 하지 않았습니다. inventory·생성 파일 크기는 공개 영수증에 있고 PG·Next 캐시 순증은 사전 측정이 없어 분모 모름입니다.

?? ??: PG ???Edge28/28=100%, ??2/2=100%, ?? ?? HOLD ??. [? ??](2026-10-29_st4f719-authorization-lifetime.md).
