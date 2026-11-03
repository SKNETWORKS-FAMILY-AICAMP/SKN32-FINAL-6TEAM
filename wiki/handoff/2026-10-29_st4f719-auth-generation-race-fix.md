---
type: handoff
title: ST4F-719 인증 세대 경합·watcher 401 수정 인계
status: draft
domain: travel
---

지정한 독립 검토의 실패 8건을 기존 후보 `scratch/st4f719-blocker-independent-20261029/repo`에서 재현하고 수정했습니다. 늦은 401·로그아웃은 요청 시작 세대를 확인하며, 같은 세션 refresh와 기존 401 오류 화면은 유지합니다. 세 watcher·빈 HTTP 401·쿠키 동반 공개 API와 쿠키 없는 공지 경계·스트림 재전송도 검증했습니다.

최종 웹 **1,438/1,438 = 100%**, 기존 독립 집중 **40/40 = 100%**, 추가 경계 **101/101 = 100%**, PG 인증·Edge **58/58 = 100%**, PG 쿠키 e2e **38/38 = 100%**, 단위 변이 **8/8**, Edge 변이 **1/1 = 100%**입니다. 보호 scanner/XML **2/2 = 100%** 해시 일치, 소유한 검증 포트 **4/4 = 100%** 종료를 확인했습니다.

**통합·릴리스 HOLD**입니다. 이번 DoD **26/26 = 100%**이나, Git 실행 불가로 계약 **365/367 = 99.5%**, 보안 **124/125 = 99.2%**입니다. 필수 관문은 이번 실행 **1/3 = 33.3%**이며, scanner는 tracked 파일 열거 전 실패했습니다. 이를 과거 XML 탐지 실패와 같은 원인으로 설명하지 않으며, 기존 보안 HOLD도 유지합니다. 시험·scanner·XML·Git 설정을 바꿔 우회하지 않았습니다.

증거·백업·최소 패치는 기존 후보 상위의 `generation-race-fix/`에 있습니다. `candidate-change.patch`에는 transport 4개·새 단위 시험·인증 wiki만 담았습니다. identity-test 페이지 export와 Edge spec·PG G2 생성은 로컬 검증 fixture이므로 배포물에 넣지 않습니다. 최초 결과·변이 실패·기존 자료를 보존했습니다.

한 일 목록과 실행 명령·검증 범위·환경 실패·보존 영수증은 [상세 보고](../../final_project_cs/wiki/records/reports/2026-10-29_st4f719-auth-generation-race-fix.md)에 있습니다. 담당·자체 검토는 이번 Codex 세션이며 새 독립 승인·최신 coord 예약·통합 tip 확인을 주장하지 않습니다. 새 clone·원본 코드 역복사·push·운영 접속·배포·삭제는 0건입니다. 전체 DB와 Next 캐시는 재사용했고 inventory lease entries는 0입니다. 새 증거 크기는 `generation-race-fix/artifact-size.json`, 기존 PG/Next 순증은 분모 모름입니다.

다음 담당은 동작하는 승인된 Git 환경에서 계약·보안 관문을 재실행하고 최신 tip·별도 검토를 확인해 주세요. 로컬 인증 수정 완료와 제품 전체·운영 완료를 구분합니다.
