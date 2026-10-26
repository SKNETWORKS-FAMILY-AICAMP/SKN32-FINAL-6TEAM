---

- [재난 수신 기록 계약](operations/receipt-history.md) · [구현 보고](records/reports/2026-10-17_1530_receipt-history-and-targets.md) · [매니저 독립 검토](records/reports/2026-10-17_receipt-history-manager-review.md)
type: guide
title: cs 프로젝트 구현 wiki
description: 여행 CS guguroute의 현재 계약·구현 안내입니다
status: draft
domain: travel
---

# cs 프로젝트 구현 wiki

2026-10-25 [전체 과거 normal confirm HTTP 증명·35개 회귀·전체관문 대조](records/reports/2026-10-25_allpast-normal-confirm-proof.md) — 추가 제품 수정 없음, 원격 반영 전.

2026-10-26 채팅 「실내를 야외로 바꿔줘」 첫 답이 식사 낀 대체 목록이던 결함 — 기준 일정 재확인이 활동 되묻기 선택지를 지운 것, 격리 후보에서 고침(로컬 시험·실 E4B까지, 푸시·배포 전): [보고서](records/reports/2026-10-26_chat-outdoor-anchor-guard-fallback.md)
2026-10-26 채팅 「실내를 야외로 바꿔줘」가 53c3c273 뒤에도 식사 낀 대체 목록이던 결함 — x600 유료 대체 의심과 남은 빈 선택지 길, 실내·야외 되묻기는 활동 후보로(로컬 시험·실 E4B까지, 푸시·배포 전): [보고서](records/reports/2026-10-26_chat-outdoor-setting-clarify-candidates.md)
2026-10-26 채팅 실내·야외 바꾸기 da4ccd97 재시험 — 되묻기 선택지에 식사가 남던 것 · 이미 야외인 일정을 또 바꾸던 것 고침, 되돌린 뒤 박물관 운영시간 「모름」은 되돌리기 결함이 아님(로컬 시험·실 E4B까지, 푸시·배포 전): [보고서](records/reports/2026-10-26_chat-outdoor-setting-swap-targets.md)
2026-10-26 채팅 실내·야외 바꾸기 c34bd376 x600 — 선택 없이 「실내를 야외로 바꿔줘」가 식사 포함 대체 목록으로 되묻던 경로 확정(해석 `place_setting.want=any`) · 조건이 있으면 어느 되묻기든 조건 선택지(로컬 시험·실 E4B까지, 푸시·배포 전): [보고서](records/reports/2026-10-26_chat-outdoor-setting-clarify-paths.md)

2026-10-25 채팅에서 화면으로 고른 일정에 묻는 말이 「어느 일정」 되묻기 · 앞 일정 답으로 끝나던 결함을 격리 후보에서 고쳤습니다(로컬 시험까지, 반영 전): [원인 · 수정 · 실모델 한계](records/reports/2026-10-25_chat-selected-stop-subject.md).

2026-10-25 [전체 과거 normal confirm HTTP 증명·role-manager 21개 회귀](records/reports/2026-10-25_allpast-normal-confirm-proof.md) — role-manager 원기능 보존 이식, 격리 21/21 통과; 원격·운영 상태는 연결 기록 참조.

2026-10-25 전체 과거 날짜 신규 등록 가드 독립 후보: [날짜 기준·공통 검사·검증 및 미반영 경계](records/reports/2026-10-25_all-past-calendar-hotfix.md). 기존 확정 재시도/reopen 정책과 다른 정상 검사는 보존합니다.

2026-10-25 웹 화면 고침: 계획 확인 · 여행 화면 지도 오른쪽 아래(시트 모서리)에 비치던 흰 바탕은 시트 밑 Leaflet 저작권 줄의 배경이라 투명하게 했고, 계획 입력 아래 고정 단추 줄은 화면 양옆 · 맨 아래까지 덮으며, 보내는 중 잠긴 입력칸은 회색으로 보입니다. 「예시 불러오기」는 내일부터 이틀 · 하루 세 곳(요일 휴무 없는 곳)으로 바꿔 로컬 계획 확인 6/6 통과. 계획 확인 시트 손잡이는 검사 단계부터 보이고, 확인 화면에서 장소가 바뀐 일정(「바꾸기」 · 검색 · 「맞아요」 · 「전체 자동 추천」)은 처음 등록 때도 그 장소 이름이 일정 이름입니다(수정 모드 완료와 같음 · 지역만 적어 서버가 채운 곳은 적힌 이름 · 직접 고친 제목이 먼저 · 그 옆 이동도 남음), 첫 여행이면 「예시 불러오기」 → 「계획 확인하기」를 비추는 첫 안내(A안)가 뜹니다. ST4F-735 ~ 738 · 푸시 전 · [작업 기록](records/reports/2026-10-25_웹_지도모서리_계획입력_예시일정.md).

2026-10-24 계획 확인 진행 표시 ③ · 멈춘 질문 후보 대기(ST4F-731 · 732): 서버가 위험 점검 · 먼저 채우기 · 해석 반영 진행 알림을 보내고 화면은 서버 단계마다 한 칸으로 보입니다. 검사를 읽는 길은 접수 행을 잠그지 않고(쓰기는 그대로), 대안 미리 준비가 요식 판정보다 먼저 돌며, 「전체 자동 추천」 미리 보기는 첫 검사 · 멈춘 질문이 끝난 뒤 나갑니다 — 로컬 같은 계획 재측정에서 「후보를 찾는 중」 22.5초 → 0.9초. 실서버 확인 전 · [작업 기록](records/reports/2026-10-24_계획확인_진행표시_후보대기_ST4F-731-732.md).

2026-10-23 Next.js 보안 갱신(ST4F-724): 02시 리뷰 뒤 공개된 Next.js 권고(16.0.0~16.4.0)로 web 16.4.0 도 critical 이 되어 web · admin · dev-console 을 16.4.2 로 올렸습니다. 운영 의존성 audit 3/3 앱 0건 · check 12/12 · 단위 1,198/1,198 통과, 개발 서버 보안 경고 사라짐. 배포 전입니다. [작업 기록](records/reports/2026-10-23_Next보안갱신_16.4.2_ST4F-724.md).

2026-10-23 프론트엔드 리뷰: role-eval-ui 기준 격리 브랜치에서 P1 4건·P2 15건을 확인했습니다. 세 앱 check 12/12·단위 1,158/1,158 통과, 제품 수정·운영 반영 전입니다. [전체 보고서](records/reports/2026-10-23_frontend-audit.md).

2026-10-23 프론트엔드 독립 리뷰·Codex 대조(Claude): 리뷰어 6명 독립 검토로 통합 결함 43건(P1 5·P2 38)·P3 약 86건을 정리했고, Codex 19건은 19/19 코드 일치. 새 P1은 git에 추적된 Chromium 프로필(History·Login Data·Cookies 127파일)입니다. 단위 1,158/1,158 재확인, 수정 0/43. [대조 보고서](records/reports/2026-10-23_frontend-audit-claude-crosscheck.md).

2026-10-18 추가 확인: 공개 식당 자료를 넣어 지역 검색·실제 도착 기준을 보완했습니다. 로컬 확장 100/100, 새 실서버 검증은 WSL 시작 오류로 대기 중이며 배포 전입니다. [최신 결과와 실패 범위](records/reports/2026-10-18_nambu-field-fixes.md).

2026-10-18 남부터미널 실사용 네 분야를 격리 사본에서 수정했습니다. 관련 회귀 6315건 통과, 운영 배포 전입니다. [변경·원인·시험 한계](records/reports/2026-10-18_nambu-field-fixes.md) · [진행·목적지·조회 상태 계약](actions/journey-progress.md).

2026-10-18 관리자 여행 상세: 여행을 눌러 저장 대화·최초/현재 계획을 조회합니다. 양쪽 매니저 코드 반영·운영 자동배포 완료, 지정 다섯 여행의 세 탭 15/15을 실제 화면과 DB로 대조했습니다. [운영 확인·시험 한계](records/reports/2026-10-17_admin-trip-release.md) · [초기 구현 기록](records/reports/2026-10-17_admin-trip-detail.md).

여행 CS guguroute의 현재 계약·구현 안내입니다. 제품 사양은 [상위 wiki](../../wiki/index.md)의 후속 확정 결정과 대조하며, 이력 문서는 당시 상태를 확인할 때만 엽니다.

세션을 이어받는 경우 [인계 안내 목차](../../wiki/handoff/index.md)에서 가장 최근 인계부터 읽습니다.

**지금 상태를 볼 곳**: 환경별 가동 상태는 [운영 현황](operations/current-state.md), 날짜별 변경은 [변경 기록](log.md), 이 저장소만의 결정은 [결정 목록](decisions/index.md), 시험은 [시험 지도](quality/test-map.md).

| 영역 | 읽을 문서 |
|---|---|
| 개발 책임·실제 경로 | [코드·시험 경로](teams/code-layout.md)·[개발 역할](../../wiki/delivery/roles.md) |
| 에이전트 팀 선택·실행 | [에이전트 팀](teams/index.md)·[Registry](teams/team-registry.md)·[Controller](runtime/agentic-controller.md)·[플러그인 가용성·교체](teams/team-plugin-lifecycle.md) |
| 입력·결과 계약 | [Team 계약](teams/team-contract/index.md)·[Context](context/index.md) |
| 고객 접속·인증 | [외부 접속](external/index.md)·[현재 MCP](external/mcp-tools.md) |
| 변경·승인·중복 방지 | [ActionProposal](actions/action-proposal.md)·[멱등성](actions/idempotency.md) |
| 데이터·SQL | [데이터](data/index.md)·[SQL 적용](data/migrations.md) |
| 시험·평가·실행 | [시험 지도](quality/test-map.md)·[실행](operations/run.md)·[불변식](quality/invariants.md) |
| 운영 현황·변경 기록 | [운영 현황](operations/current-state.md)·[운영 목차](operations/index.md)·[변경 기록](log.md) |
| 흐름·상태 | [실행 흐름 목차](runtime/index.md)·[품질 목차](quality/index.md)·[결정 목록](decisions/index.md) |

`TeamRegistry`는 에이전트 팀을 선택하는 장치이고 `Controller`는 처리 흐름을 진행합니다. 감시 작업과 모니터링 도구의 구분은 해당 아키텍처 계약에서 확인합니다. 개발자·QA의 사후 결함 분석과 고객 요청 처리의 자동화를 혼동하지 않습니다.

## 2026-10-12 작업 기록 요약

각 줄은 그날의 기록이다. 현재 상태는 위 「지금 상태를 볼 곳」에서 다시 확인한다.

2026-10-12 12:55 운영 확인: WSL 기동 복구 뒤 공개 첫 화면·상태 주소 HTTP 200과 실제 Chrome 화면을 재확인했습니다. 추가 용량 관리는 별도 세션에 인계했습니다. 이후 매니저 배포에서 빠진 플러그인 수정의 복구 후보는 아직 검증 중이며 새벽 반영 기록을 현재 완료 상태로 재사용하지 않습니다. [복구 근거·검사 범위](records/reports/2026-10-12_1255_public_screen_recovery.md).

2026-10-12 UI/UX 검사: 실제 Claude Sonnet 5.5 코드 검토 2/2, 고정 검증 사본 단위 686/686, 최종 관련 Chrome 52/52와 문의 후속 7/7을 확인했습니다. 로딩 중 전체 접힌 일정·이전 먼 마커 유지·팝업 넘침을 수정했습니다. 최초 전체 실행 745건과 후속 검사·다른 작업의 동시 변경은 구분하며 공개 배포하지 않았습니다. [최종 결과·검사 범위·원본 증거](records/reports/2026-10-12_UIUX전수검사_최종결과.md).

`[2026-10-12]` 실행·대기·재개 복구와 되돌리기 버튼의 검증·공개 반영 상태는 [최종 자동 반영 보고서](records/reports/2026-10-12_manager_recovery_release_followup.md)에서 확인합니다. 현재 제품 사양은 후속 wiki 결정·계약을 따르며 과거 계획 상태표를 오늘 배포 상태로 재사용하지 않습니다.

2026-10-12 설계 초안: 여행 관련 잡담과 다섯 입력 경로를 고객별 취향으로 연결하는 [통합 구현 계획](records/plans/2026-10-12_여행대화와_고객취향_통합_구현계획.md)을 작성했습니다. 취향 기억과 일정 변경 허가를 분리하며 구현·운영 반영은 하지 않았습니다.

2026-10-12 구현: 일정 밖 장소의 역사 질문을 검색 근거 경로로 보내고, 일반 추천 답변의 근거 범위를 제한했습니다. 관련 로컬 시험 41/41 통과; 실제 모델 응답과 운영 반영은 미확인입니다. [검토·변경·검증 기록](records/reports/2026-10-12_1105_여행대화_역사질문과_추천근거.md).

2026-10-12 구현: 일정 입력의 “지금”을 접수 시각 기준 날짜·시각으로 해석하고, 시간·날짜 변경 요청이 장소 교체 경로로 들어가지 않도록 막았습니다. 관련 로컬 단위 시험 54/54 통과; 사용자가 겪은 대화 기록과 운영 반영은 미확인입니다. [원인·수정·검증 기록](records/reports/2026-10-12_여행_날짜시각_오인과_장소교체_보호.md).

## 과거 기록

[수정 전 문서](records/commerce_2026-10-11/wiki--index.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](../../wiki/index.md) — 현재 정본을 찾는 입구

## 이전 절 링크

<a id="final_project_cs-지식-지도"></a>
<a id="말-네-개를-먼저-나눈다"></a>
<a id="영역"></a>
<a id="runtime--case가-흘러가는-곳"></a>
<a id="teams--업무-책임-단위"></a>
<a id="context--읽기-경로"></a>
<a id="actions--쓰기-경로"></a>
<a id="external--바깥과-만나는-면"></a>
<a id="data--저장"></a>
<a id="quality--무엇으로-보증하는가"></a>
<a id="operations--돌리는-법"></a>
<a id="decisions--이-저장소에만-영향을-주는-결정"></a>
<a id="흐름으로-보기"></a>
<a id="이-저장소의-불변식"></a>
<a id="sample과의-관계"></a>
<a id="-2026-09-03-계약은-이식하고-파일은-복사하지-않는다"></a>
<a id="이-참조는-낡았다"></a>
<a id="중앙-허브"></a>
<a id="최근-변경"></a>
<a id="기록-구역-records-2026-09-08"></a>

- 숙소 재검토 후속 배포 뒤 새 예시 양일 같은 호텔·조식·숙박 아이콘과 지도, 375/1280px 즉시 수정·취소의 실제 확인을 완료했다. [최종 기록](records/reports/2026-10-17_lodging-edit-live-verification.md). 수동 호텔 저장 문제는 별도 추적 범위다.


- 재난 수신 기록의 영향 카드·다중 필터는 양쪽 매니저 반영·운영 배포 완료. 로그인 화면의 실제 확인은 남았다. [확인 범위와 남은 일](records/reports/2026-10-17_receipt-impact.md).

- 재난 영향 필터 통합판은 전체 시험·관리자 기본 빌드·양쪽 매니저 반영·운영 배포 완료. 실제 관리자 화면의 체크박스·조회는 확인. 안전 단계 참고 문자의 영향 표시 보정은 남았다. [통합 검토](records/reports/2026-10-17_receipt-impact-manager-integration.md).

- 관리자 여행 상세 매니저 통합·자동배포 검증은 [후속 기록](records/reports/2026-10-17_admin-trip-release.md)에 이어 남깁니다.

- 2026-10-18 후속: 고객 입력 초안 원문 탭·철회 시계 차이 결함 수정·양쪽 매니저·운영 배포·지정 5여행 20/20 DB 대조를 완료했습니다. 미완료 19/19와 운영 환경 전체 DoD 26/26, 로컬 추가 오류의 후속 2/2 및 최초 실패는 [날짜별 결과](records/reports/2026-10-18_trip-draft-and-full-gates.md)에 구분해 보존했습니다.

- 2026-10-18: 재난문자 내용·지역 관련성 v2. 담당 격리842/842·완료관문26/26·mock 서버 화면8/8; 통합·운영 상태는 [검증 기록](records/reports/2026-10-18_receipt-message-relevance.md)에 구분.

- 2026-10-18: 재난문자 지역·내용 v2는 양쪽 매니저와 운영 api·worker·admin 반영 및 실제 동일 시각 문제 카드 확인 완료. [운영 응답·화면·시험 한계](records/reports/2026-10-18_receipt-message-relevance-live.md).

2026-10-18: develop 웹앱 보존 병합의 로컬 검증을 완료했다. 게시·운영 상태와 분리한 [검증 기록](records/reports/2026-10-18_develop-web-merge-review.md).

2026-10-18: develop CI 실패 원인을 보완하고 독립 전체 검증을 완료했다. 게시 후 CI·운영 확인은 별도다. [기록](records/reports/2026-10-18_develop-ci-repair.md).


2026-10-24 한 구간의 택시 이동이 전체로 확대되지 않도록 읽기·구간 생성·성향 전달을 통일했습니다. 매니저 통합·검증과 운영 확인은 [결함 기록](records/reports/debugs/2026-10-24_택시구간_범위수정_매니저반영.md)에서 구분합니다.
