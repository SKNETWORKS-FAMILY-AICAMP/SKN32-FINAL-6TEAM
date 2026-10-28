---
type: guide
title: guguroute wiki
description: 현재 제품 사양은 확정 결정·현재 계약, 구현·배포 상태는 코드·환경별 실행 기록으로 확인합니다
status: draft
domain: travel
---

# guguroute wiki

2026-10-29 ST4F-728 로그아웃 경합 재현·차단: 웹1227/1227·화면11/11·필수3/3=100%,트래커종결0. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f728-guest-logout.md).

2026-10-25 [전체 과거 normal confirm HTTP 증명·role-manager 21개 회귀](handoff/2026-10-25_allpast-normal-confirm-proof.md) — role-manager 원기능 보존 이식, 격리 21/21 통과; 원격·운영 상태는 연결 기록 참조.

2026-10-25 신규 계획의 전체 과거 날짜만 거절하는 독립 hotfix 후보: [계약·검증·role-manager 인계](handoff/2026-10-25_all-past-calendar-hotfix.md). 일부 과거 + 오늘/미래는 이 가드로 차단하지 않으며 운영 반영 완료는 아닙니다.

현재 제품 사양은 **확정 결정·현재 계약**, 구현·배포 상태는 **코드·환경별 실행 기록**으로 확인합니다. 과거 계획·보고서를 현재 사실로 사용하지 않습니다.

세션을 이어받는 경우(Codex↔Claude) [인계 안내 목차](handoff/index.md)에서 가장 최근 인계부터 읽습니다. **커밋되지 않은 작업이 많아 git 이력만으로는 최근 상태가 보이지 않습니다** — 인계의 「한 일 목록」과 [변경 기록](log.md)을 함께 봅니다.

## 읽기 순서

1. [빠른 시작](quickstart.md) — 문서별 책임과 읽는 순서
2. [제품 범위](product/scope.md)·[결정 목록](decisions/index.md) — 현재 제품과 후속 결정
3. [아키텍처](architecture/index.md)·[cs 구현 wiki](../final_project_cs/wiki/index.md) — 구조·계약·실행 경로
4. [개발 역할](delivery/roles.md)·[작성 표준](governance/document-standard.md) — 담당·검토·문서 작성

## 영역 지도

| 영역 | 무엇 | 목차 |
|---|---|---|
| 제품 | 무엇을 만드는가 | [product/](product/index.md) |
| 사업 | 가격·비용 | [business/](business/index.md) |
| 아키텍처 | 어떻게 나뉘는가 | [architecture/](architecture/index.md) |
| 진행 | 언제·누가 | [delivery/](delivery/index.md) |
| 평가 | 무엇으로 증명하는가 | [evaluation/](evaluation/index.md) |
| 조사 | 무엇을 알아봤는가 | [research/](research/index.md) |
| 결정 | 왜 그렇게 했는가 | [decisions/](decisions/index.md) |
| 작성 표준 | 어떻게 쓰는가 · 검사기 | [governance/](governance/index.md) |
| 변경 기록 | 날짜별로 무엇이 바뀌었나 | [log.md](log.md) |
| 인계 | 세션 간 이어받기 | [handoff/](handoff/index.md) |

## 현재 자료와 이력

- [D-023](decisions/D-023-no-commerce-assets-in-use.md): 쇼핑몰 자산은 현재 판단·시험·평가·시연·관문에 사용하지 않습니다.
- [평가 안내](evaluation/index.md)와 [현재 여행 코퍼스](../final_project_cs/wiki/context/travel-corpus.md)에서 여행 자료를 찾습니다.
- [데이터 안내](../datasets/README.md)는 실제 데이터 폴더·사용 상태의 정본입니다.
- v11은 2026-09-10 당시 계획 기록이며 v12 안내서는 작성 전입니다. 과거 결정은 날짜·적용 범위를 확인합니다.

## 과거 기록

[수정 전 문서](records/commerce_2026-10-11/wiki--index.md)는 당시 기록입니다. 현재 여행 제품의 사양·평가·시연·완료 증거로 사용하지 않습니다. 원문 바이트는 같은 폴더의 백업에도 보존했습니다.

## 관계

- [여행 사양 허브](index.md) — 현재 정본을 찾는 입구


## 이전 절 링크

<a id="tripilot-지식-허브"></a>
<a id="-2026-09-08-여행-판올림--이-wiki의-절반이-아직-쇼핑몰이다"></a>
<a id="영역"></a>
<a id="product--무엇을-만드는가"></a>
<a id="business--얼마짜리인가"></a>
<a id="architecture--어떻게-나뉘는가"></a>
<a id="delivery--언제-무엇을-내는가"></a>
<a id="evaluation--무엇으로-증명하는가"></a>
<a id="research--무엇을-알아봤는가"></a>
<a id="decisions--왜-그렇게-했는가"></a>
<a id="governance--어떻게-쓰는가"></a>
<a id="코드-저장소"></a>
<a id="미결정"></a>
<a id="최근-변경"></a>
<a id="작업-기록은-각-저장소의-wikirecords에-있다-2026-09-08"></a>

## 별도 참고 구현

[참고 sample wiki](../final_project_sample/wiki/index.md)는 계약 인프라를 검증하는 별도 구현입니다. 그 업무 자료·완료 결과를 여행 릴리스 증거로 쓰지 않습니다.


2026-10-17 수동 숙소 저장 보완: 격리 HTTP40/40 통과, 운영 반영 확인 전. [독립 통합 기록](../final_project_cs/wiki/records/reports/2026-10-17_manual-stay-manager-review.md)


2026-10-17 수동 저장 API·worker 배포 안정성 확인. 공개 계획서의 선택 장소 표시 보완은 격리36/36 통과, 운영 반영 확인 전. [통합 기록](../final_project_cs/wiki/records/reports/2026-10-17_public-plan-manager-review.md)


2026-10-17 공개 계획서 선택 장소 표시9ebf1aec의 API·worker 배포30초 안정성 확인. 실제 내부HTTP에서3응답200·장소4/4표시·첨부헤더 확인. 공개 브라우저·수동 저장 최종 화면은 미확인. [최종 확인 기록](../final_project_cs/wiki/records/reports/2026-10-17_public-plan-manager-review.md)

- 2026-10-18 관리자 여행 상세 운영 반영·실제 5여행 검증 완료: [인계·확인 한계](handoff/2026-10-18_admin-trip-release.md).


[2026-10-29 버스 scalar 독립 검토](records/reports/2026-10-29_bus-scalar-independent-continuation.md): 필수3/3=100%, 실제공공자료·최신코드 동등 확인, local 혼합walk 평균8.65% 감소; EKS 전체성능 미검증.
