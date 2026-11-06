---
type: guide
title: guguroute wiki
description: 현재 제품 사양은 확정 결정·현재 계약, 구현·배포 상태는 코드·환경별 실행 기록으로 확인합니다
status: draft
domain: travel
---

# guguroute wiki

2026-10-25 v2 — 독립검토 P1/P2와 추가 cmd 실패코드 누락을 새 격리 후보에서 수정했습니다. 최종 launcher 18/18·admin 41/41·8개 개별 관문 통과, 이전 wrapper 실패 기록은 별도 보존했습니다. 이전 7개 시험은 전체 배치를 검증하지 않았습니다. 실제 3300·예약 OFF 저장은 미검증입니다. [수정·실패 이력·결과](../final_project_cs/wiki/records/reports/2026-10-25_local-admin-3300-v2.md).

2026-10-25 — 로컬 일괄 실행의 개인 스크립트 필수 의존을 해소해 고객 API·운영 API·제품 관리자 3300 구성을 준비했습니다. 서비스·실DB·모델·배포는 실행하지 않았습니다. [실행 계약](../final_project_cs/wiki/operations/local-app-bundle.md) · [검증 기록](../final_project_cs/wiki/records/reports/2026-10-25_local-admin-3300.md).

2026-10-24 — 최신 팀 develop 위 격리 날짜 위험 2차 보완: deferred·기간 겹침·재사용 시간경계·risk_panel 보존. 원본/운영 변경 없이 TDD와 실제 Python·웹·모형 부품 브라우저 검증을 수행했습니다. 전체 관문은 기준본과 같은 Git 실행 권한 실패 3건이 남으며, 최종 수치·실패/한계·인계는 [검증 기록](../final_project_cs/wiki/records/reports/2026-10-24_date-risk-second-pass.md)을 봅니다.

2026-10-29 ST4F-728 로그아웃 경합 재현·차단: 웹1227/1227·화면11/11·필수3/3=100%,트래커종결0. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f728-guest-logout.md).

2026-10-25 [전체 과거 normal confirm HTTP 증명·role-manager 21개 회귀](handoff/2026-10-25_allpast-normal-confirm-proof.md) — role-manager 원기능 보존 이식, 격리 21/21 통과; 원격·운영 상태는 연결 기록 참조.

2026-10-25 신규 계획의 전체 과거 날짜만 거절하는 독립 hotfix 후보: [계약·검증·role-manager 인계](handoff/2026-10-25_all-past-calendar-hotfix.md). 일부 과거 + 오늘/미래는 이 가드로 차단하지 않으며 운영 반영 완료는 아닙니다.
2026-11-03 C: 정리 승인 삭제: scratch·clones 65/65 루트 93.27GB 삭제(오류0, 끊긴 링크는 보존본 안 worktree gitdir 3개 외 0), final_workspace 54.68GB(17:1x), C: 여유 349.02GB(17:06, 이후 343~351GB 변동, 400GB까지 50.98GB 부족), `_unified_mall_3`·`test_workspace` 보존 준비 완료·승인 대기. [보고](records/reports/2026-11-03_scratch-approved-deletion-and-project-prep.md) · [인계](handoff/2026-11-03_scratch-approved-deletion-handoff.md) · [독립 재검증·정정](records/reports/2026-11-03_scratch-approved-deletion-independent-verification.md) · [백업 푸시 교차검증](records/reports/2026-11-03_backup-push-independent-crosscheck.md)

2026-11-03 Telegram 총괄 세션 5fbd35ab 위키화: 지시134/134·답변366/366 대조, 인사동·일정 설명 원인 보존, 설명 작성기 후보 backups 보존, 삭제 전 비밀 교체·삭제 방식 결정 필요. [보고](records/reports/2026-11-03_telegram-orchestrator-5fbd35ab-session-wiki.md) · [인계](handoff/2026-11-03_telegram-orchestrator-5fbd35ab-close-handoff.md).

2026-10-30 아침 이동 복구 독립검토: 단위59/59·웹54/54·실PG/API 최종 개별9/9·Edge6/6=100%, 필수 실행3/3·원본 인정2/3=66.7% 보안 HOLD, 보호503/503·제품수정/push0. [인계](handoff/2026-10-30_morning-recovery-independent-review.md).

2026-10-29 ST4F-719 인증 세대 독립검토: 웹1463/1463·PG/Edge64/64=100%, 필수2/3=66.7% 보존 XML HOLD. [인계](handoff/2026-10-29_st4f719-auth-generation-independent-review.md).

출처 후속 검토: HTTP4/4·문서/strict4/4 = 100%, 서비스·보안 HOLD 유지. [인계](handoff/2026-10-29_conversation-source-schema-continuation.md).


2026-10-29 대화 출처 신원 수정 독립검토: 집중142/142·추가 strict/경계31/31·실행회귀565/565=100%(4제외), 문서손상1·공식 wire schema/실제 제공처 수락 미확인, 서비스·보안 HOLD 유지. [보고·인계](handoff/2026-10-29_conversation-source-identity-independent-review.md).


2026-10-29 ST4F-719 미리보기 P1 격리후보 수정: PG·Edge26/26·웹1321/1321=100%, 단위변이7/7·Edge변이3/3 검출, 필수2/3=66.7% scanner/XML HOLD·push0. [인계](handoff/2026-10-29_st4f719-preview-privacy-fix.md).

2026-10-29 ST4F-746 보안 추적: 최초4파일10건 시험값 오탐·원본 detector 실패/HOLD, 기능20/20=100%. [인계](handoff/2026-10-29_st4f746-security-gate.md).

2026-10-29 EKS v0.9.3 재검증: 전체223/223 = 100.00%·집중73/73 = 100.00%·과거/캐시11/11=100%, PR110 HOLD·운영쓰기0. [인계](handoff/2026-10-29_eks-route-policy-full-recheck.md).

2026-10-29 ST4F-719 late-id 독립검토: PG·Edge 미리보기 소유권 누락1건 재현/수락보류, 네경합8/8·변이4/4·웹1304/1304=100%, 필수2/3=66.7% 보안 HOLD·push0. [인계](handoff/2026-10-29_st4f719-late-id-independent.md).


2026-10-29 ST4F-746 아침 복구 독립검토: 단위20/20·시간대2/2·실DB2/2·여행격리1/1=100%, 원본 detector 4파일/HOLD·push0. [인계](handoff/2026-10-29_st4f746-morning-independent-review.md).

2026-10-29 ST4F-746 ?? ?? ?? ??: ??56/56??PG2/2???2/2=100%, ?? ??HOLD?push0. [?????](handoff/2026-10-29_st4f746-morning-read-recovery.md).


2026-10-29 ST4F-719 재개: id mutation4/4 격리수정·Edge8/8·실PG전환4/4·개인정보10/10=100%, 필수1/3=33.3%(Git 환경 오류)·scanner/XML HOLD·push0. [인계](handoff/2026-10-29_st4f719-late-id-mutations-resumed.md).

2026-10-29 A11 실DB 기준대조: 계약367/367·DoD26/26=100%, 회귀1505/1505=100%, 보안124/125=99.2%·필수2/3=66.67% HOLD·push0. [보고·인계](handoff/2026-10-29_routing-a11-real-db.md).

2026-10-29 중단 S6 A11 재개: 숙박16/16=100%·XML118/118=100% 보존, 필수0/3=0%·통합HOLD·push0. [인계](handoff/2026-10-29_routing-a11-resumed.md).


2026-10-29 ST4F-719 개인정보·인증 복구 후보: Edge10/10·웹1282/1282·변이4/4=100%, 필수2/3=66.7% 보안 HOLD·push/배포0. [보고·인계](handoff/2026-10-29_st4f719-privacy-auth-recovery.md).

2026-10-29 ST4F-719 identity-bound 독립검토: Edge4/8=50%·개인정보/401/옛 키 3경계 재현, 필수2/3=66.7% HOLD. [보고·인계](handoff/2026-10-29_st4f719-identity-independent.md).

2026-10-29 EKS golden2 도보·출발문맥: 해소1/5=20%(bike golden v2 독립도출=실제), 5파일21/24·새실패0, 가려진 자전거 more_option 담당결정·PR110 HOLD. [보고](records/reports/2026-10-29_eks-golden-walk-context-causality.md).

2026-10-29 ST4F-719 세션 소유권 격리수정: 웹1268/1268·실인증 Edge3/3·변이4/4=100%, 필수2/3=66.7% HOLD. [보고·인계](handoff/2026-10-29_st4f719-identity-bound.md).

2026-10-29 새벽 첫차 원인추적: 첫차시험군2/3=66.67%·추가해소0/5=0%, 정류장 첫차 근거 미확보·PR110 HOLD. [보고·인계](records/reports/2026-10-29_eks-dawn-first-vehicle-causality.md).

2026-10-29 ST4F-719 수정 후보 독립 재검토: 웹1257/1257·변이3/3=100%, Edge5/6=83.3%, 계정 경계 잔존/이력 삭제 재현, 필수2/3=66.7% HOLD. [보고·인계](handoff/2026-10-29_st4f719-fixes-independent-review.md).


2026-10-29 ST4F-719 검토실패3건 격리수정: 새사본 웹1257/1257·Edge9/9=100%, 필수2/3=66.7% HOLD. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f719-review-fixes.md).


2026-10-29 ST4F-719 독립검토 HOLD: 정보누락2·로그아웃잔존1 재현, 필수2/3=66.7%. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f719-independent-review.md).


2026-10-29 ST4F-732 단계 시계 독립검토: 목표12→0초 확인·Edge15/19=78.9%, 기존경계4건·필수2/3=66.7% HOLD. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f732-clock-independent-review.md).



2026-10-29 ST4F-718 저장 정책 독립검토: 웹1241/1241·Edge22/22=100%; 구버전 중복/raw ID 재생성·queued open 무응답 재현, 기존 필수2/3=66.7% HOLD 유지. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f718-storage-policy-review.md).
# triPilot wiki

2026-10-29 원래실패13/18=72.22% 추가해소·전체층211/216=97.69%/5실패,기본전체RAG16미준비·PR110 HOLD. [보고](records/reports/2026-10-29_eks-linux-remaining18.md).

2026-10-29 ST4F-718 저장/quota/privacy 후보: 웹1241/1241·Edge22/22·변이4/4=100%, 필수2/3=66.7% HOLD·정책/운영수락 미완. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f718-storage-policy.md).

2026-10-29 ST4F-718 독립검토: 웹1255/1255·변이4/4·Edge12/12=100%, 무제한 증가·quota/탭 한계 확인, 필수2/3=66.7% HOLD. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f718-independent-review.md).


ST4F-740 다음 미배정 항목으로 718의 자동 재생 이력 유실을 찾고 격리 수정했습니다. **필수 2/3 = 66.7% HOLD**, 종결·push·배포 0건입니다. [보고서](../final_project_cs/wiki/records/reports/2026-10-29_st4f718-credits-retention.md).


2026-10-29 EKS Linux 정밀 기대18/36=50% 정정·전체198/216=91.67%, 필수3/3=100%·잔여18/운영HOLD. [보고](records/reports/2026-10-29_eks-linux-precision-expectations.md).


2026-10-29 보안 원본2/2=100% 보존·과거XML 탐지5건/HOLD. 새727 브라우저16/16,739 운영읽기5/5=100%;운영종결보류. [보고](../final_project_cs/wiki/records/reports/2026-10-29_systemic-scanner-and-backlog.md).

2026-10-29 EKS 전체원본113/113=100%·Linux180/216=83.33%, 기존36실패/새실패0·PR110 draft/HOLD. [보고](records/reports/2026-10-29_eks-linux-full-original-reliability.md).

2026-10-29 734/724 독립검토: 실API·PG·Edge 전이확인, 변이3/3=100%;724 필수2/3=66.7% HOLD·보호18/18=100%.739 추가검증20/20=100%,운영종결보류. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f734-724-independent-review.md).

2026-10-29 ST4F734 실제tight 질문 격리수정·웹1232/1232·변이3/3=100%;724 새설치/audit/check3/3,필수2/3=66.7% HOLD. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f734-tight-question-and724-validation.md).

2026-10-29 EKS reader 관측 후속: workflow5/5·격리31/31=100%, 기존 읽기 실행 경로 미확보·원인 미확정/HOLD. [보고](records/reports/2026-10-29_eks-reader-observability-boundary.md).

2026-10-29 EKS fatal 후속: reader215/215·원인분리7/7=100%, 운영원인 로그 미확보·PR110 draft/배포HOLD. [보고](records/reports/2026-10-29_eks-reading-fatal-offline-discrimination.md).

2026-10-29 EKS checking: AMD64 이미지51/51·CI3/3=100%, 전체층 비회귀216/216. 운영42항목 기준2/3=66.67%·fatal1건으로 PR110 draft/배포HOLD. [보고](records/reports/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal.md).

2026-10-29 checking 독립검토: 실PG14/14·필수3/3=100%, Linux잔여16실패 재현·EKS후보전후 미확보·통합HOLD. [근거](records/reports/2026-10-29_eks-checking-independent-review.md).

2026-10-29 EKS 후속: Linux37/37 기준대조(1통과36기준실패), checking실제SQL169→133·후보HOLD·운영변경0. [근거](records/reports/2026-10-29_eks-linux37-and-checking-duplication.md).

2026-10-29 EKS ?????? ??: ???? ???0.632?0.521?(17.60%), ??24/24=100%; ????/???? ??????HOLD. [??](records/reports/2026-10-29_eks-full-data-latitude-pruning.md).

2026-10-29 EKS 서빙 후속: 가장 큰 관측구간181.60/319.43초=56.85%; 격리 중복검사 제거는 합성87.904→84.428μs, 전체 개선 미입증·운영통합HOLD. [근거](records/reports/2026-10-29_eks-serving-bottleneck-partition.md).

2026-10-29 ST4F-728 로그아웃 경합 재현·차단: 웹1227/1227·화면11/11·필수3/3=100%,트래커종결0. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f728-guest-logout.md).

2026-10-29 추가727:실제Leaflet/Edge HTML주입2/2재현·현재helper차단2/2=100%,전체앱/운영수락남음·열림. [보고](../final_project_cs/wiki/records/reports/2026-10-29_teamflow714-acceptance-and589-boundary.md).

2026-10-29 후속 영수증:ST4F-714만 종결·전체586/688=85.2%,남음102/688=14.8%.589 지정담당·소진원인/실조회 수락 남음. [보고](../final_project_cs/wiki/records/reports/2026-10-29_teamflow714-acceptance-and589-boundary.md).

2026-10-29 TeamFlow714 기존 수정: 과거RED→현행12/12=100%·x600 설정해시 일치.589 지정담당·현재일73.1%/월80.3% 관측,종결보류. [보고](../final_project_cs/wiki/records/reports/2026-10-29_teamflow714-acceptance-and589-boundary.md).

2026-10-29 x600읽기수락·ST4F-504종결1건,현재시험30/30·원반복30/30=100%.TeamFlow잔여103/688=15.0%,597/711수락남음. [보고](../final_project_cs/wiki/records/reports/2026-10-29_x600-acceptance-and-st4f504-causal-review.md).

[현재3100 실측] 호텔조식 예시 실제교체 2/2=100% 완료: localhost93tSFrxar_RqgguLjsbwY / LANp4N2ThMaXaAI8RY4eWrbC, fresh guest 예시버튼·전체 textarea 확인, 제출/등록0·선택동의거부. old pin+검증delta이며 최신12커밋전체통합 아님. API/DB/Dining·기존고객계획 불변. [핸들/PID·사진·rollback·인계](../final_project_cs/wiki/records/reports/2026-10-25_hotel-example-live3100.md).

[현재 실측 2026-10-25 12:56] DB6536/API22260·기존웹27124/16432 연결복구. 새DB/API handed_off, HTTP/CORS12/12·실guest GET2/2·확정여행version1/items2 readback. test1 질문·대안선택은 미완료, 사용자원고 쓰기0. [긴급복구 근거·현재handoff](../final_project_cs/wiki/records/reports/2026-10-25_service-emergency-recovery.md).

2026-10-25 관리자: 지정 native DB 연결·3300/8070 재기동·direct 설정200 확인. false/default revision0이며 기존 admin 비밀 전달 부족으로 명시OFF PATCH/영속 수락 미완료. [현재 보고](records/reports/2026-10-25_admin-db-handoff-connection.md).

현재 제품 사양은 **확정 결정·현재 계약**, 구현·배포 상태는 **코드·환경별 실행 기록**으로 확인합니다. 과거 계획·보고서를 현재 사실로 사용하지 않습니다.

세션을 이어받는 경우(Codex↔Claude) [인계 안내 목차](handoff/index.md)에서 가장 최근 인계부터 읽습니다. **커밋되지 않은 작업이 많아 git 이력만으로는 최근 상태가 보이지 않습니다** — 인계의 「한 일 목록」과 [변경 기록](log.md)을 함께 봅니다.

## 2026-10-24 복사 검증·자료 조사

문서 변경 전 상대경로·크기 비교는 일치했습니다. 전체 해시·읽기 검증 완료와는 구분하며, [복사 검증 한계·과거 자료 선별 요약](records/reports/2026-10-24_workspace-migration-and-history.md)에 확인 범위와 후속 결과를 남깁니다.

## 2026-10-24 루트 보조 자료 보관

[보관 경로 manifest와 정리 보류 상태](records/reports/2026-10-24_root-aux-cleanup.md)를 확인합니다. 선별 증거는 보존했으며 루트 규칙 수정 승인 차단으로 세 폴더 삭제는 하지 않았습니다.

## 고객 응대 라이팅 현재 상태

[E4B tokenizer 실제 복구·후속 재생 인계](../final_project_cs/wiki/records/reports/2026-10-25_e4b-tokenizer-recovery-v6.md): 공식 loader SHA256 일치 설치 자산을 새 고유 cache로 복사했고 원래 두 입력의 양쪽 offline token-count/encode/decode 4/4=100% 통과했습니다. 기존 배치3/6 stage·채팅35/476 snapshot은 계속 실행 중이며, 실API·실E4B 양쪽4행은 기존 종료 후에만 실행하는 continuation `proc_227989a6c1f3`를 부모에게 handed_off했습니다. 실재생/의미 완료 아님.

[E4B v5 실재생 관찰·부모 인계](../final_project_cs/wiki/records/reports/2026-10-25_e4b-v5-observation-handoff.md): 2026-10-25 06:10 KST snapshot은 원계획8/8 review·reload, field baseline18/23·나머지 미진행, 단계2/6 exit0입니다. 실제 HTTP500 2행의 tokenizer 캐시 부재를 별도 offline probe로 확인했으며 배치는 기존 parent-owned `proc_f11a51b230be`에서 계속 실행 중입니다. 완결·개선·운영품질 성공 아님.

[계획서·문의·모니터링 구현/검증 현황](delivery/travel-response-current.md)에서 최신 결과·독립 검토 결함·승인 경계를 확인합니다. 개별 단위 통과와 실제 DB·모델·화면·운영 완료를 구분합니다.

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

2026-10-25 — 잔여 비DB3후보 새 격리 통합3/3, F1/F2수정2/2. 현재baseline과 같은 소켓차단4건 및 새 독립검토는 남았습니다. [결과](../final_project_cs/wiki/records/reports/2026-10-25_remaining-non-db-integration.md) · [인계](handoff/2026-10-25_remaining-non-db-integration.md).

2026-10-25 — F3 새 격리 수정은 원문 probe3실패로 **수락 미해결**입니다. 단일955개948통과/원문3실패/기존4bind차단. [타임라인·실패 경로](records/reports/2026-10-25_remaining-non-db-f3-unresolved.md) · [새 설계 검토 인계](handoff/2026-10-25_remaining-non-db-f3-unresolved.md).

2026-10-25 — F3 독립 설계 검토: 원문 paid-called 장벽의 인과 모순과 제품 결함을 분리하고 동등 스케줄 old RED/new GREEN을 검증했습니다. 원문 실패와 bind 차단은 보존합니다. [최신 근거](records/reports/2026-10-25_remaining-non-db-f3-acceptance.md).


## 현재 누적 릴리스 준비 — 2026-10-25

정확 history-preserving 관리자 예약OFF/로컬실행기까지 누적 통합 / 릴리스 HOLD. 원문3실패·bind4차단·strict-budget 미수락 유지, 실제 실행·OFF 저장은 DB 대기. [최신 현황](handoff/2026-10-25_final-admin-non-db-integration.md) · [직전 준비 기록](handoff/2026-10-25_remaining-non-db-release-preparation.md).


2026-10-25 — 관리자 예약 OFF/로컬 실행기 누적 격리 통합, 실제 실행·OFF 저장은 DB 대기. [최신 인계](records/reports/2026-10-25_final-admin-non-db-integration.md).


[2026-10-29 버스 scalar 독립 검토](records/reports/2026-10-29_bus-scalar-independent-continuation.md): 필수3/3=100%, 실제공공자료·최신코드 동등 확인, local 혼합walk 평균8.65% 감소; EKS 전체성능 미검증.
## 원본 최소 통합 현재 상태

[2026-10-25 launcher 독립분 반영·나머지 HOLD](records/reports/2026-10-25_original-minimal-integration.md). 최신팀 fetch 성공, 원본 전체 최신화·admin/core 통합·DB 인계 완료 아님.


## 2026-10-25 관리자 OFF 수락 보충

[실측] 이전 미완료 이후 정식 로그인·OFF 실저장 및 proxy/direct/독립DB 확인 완료(false/override revision1, audit1). 현재 PC native5433이며 이전 WSL 요구와 환경이 다릅니다. [완료 보충·경계](records/reports/2026-10-25_admin-db-handoff-connection.md).


## 공유 9구간 원본 적용 현재 결론 — 2026-10-25

[실측] 신규 reader/F3 7 + 기존 Diagnostics 보존2 = **9/9 = 100%** 원본 완료. 5필수파일 CAS·원본208/212(bind차단4·제품실패0)·관리자진단2/2·기존변경/index/refs/flags/백업 검산. 이전 shared HOLD 해소, 서비스/DB/OFF/모델/배포 변경0. [변경·검증·복원·인계](records/reports/2026-10-25_shared-original-safe-application.md).

## F3 원문 probe 3건 정식 해소 — 2026-10-25

[실측] 서로 모순되는 원문 probe 3건(81행 유료 호출 필요 vs 90행 `paid == []`)을 사용자 지시로 동등 시험 `test_llm_f3_acceptance.py`로 대체. 원문 바이트·실패 근거 보존, 같은 시험 바이트 수정 전 RED 3/3·수정 후 GREEN 3/3, 회귀 208/212(bind 차단4·제품실패0)로 이전과 동일. 제품 코드·DB·서비스·모델·배포 변경0. [보고](records/reports/2026-10-25_f3-contradictory-probe-resolution.md).


2026-10-29 EKS 후속: 버스 프로파일 단일값 검사 로컬 합성 개선 후보·독립 7,528/7,528 = 100%, 운영 속도 미검증·배포 0. [측정과 인계](records/reports/2026-10-29_eks-bus-profile-scalar-performance.md).




2026-10-29 EKS 후속: x600 scalar hash·공개 GET 확인, main 위 필수3/3=100%, 실패·복구 시간 진단 후보 검증. EKS 접수속도 미입증·push/배포0. [근거·통합 전제](records/reports/2026-10-29_eks-operational-performance-continuation.md).


2026-10-29 [EKS CD 진단 독립 후속 검토](records/reports/2026-10-29_eks-cd-diagnostics-independent-review.md): 로컬 필수3/3=100%, CLI 비밀본문 노출 보완·PR108 Linux CI 진행. EKS 성능 개선 미입증.

2026-10-29 ST4F-728 x600 소스2/2일치·공개403/운영수락 미완, 다음729 관리자46/46=100%;종결0·미완료102/688=14.8%. [근거](../final_project_cs/wiki/records/reports/2026-10-29_st4f728-production-and729-followup.md).

2026-10-29 ST4F-729 실제로딩 잔여결함 격리수정·화면2/2/회귀1/1/관리자46/46=100%,통합HOLD·종결0.공개403은Cloudflare1010,x600공개GET2/2통과. [근거](../final_project_cs/wiki/records/reports/2026-10-29_st4f729-loading-and-public403.md).


2026-10-29 EKS 진단 후속 최종: main5041362ba6·CD40747516232 성공, 새 산출물 앱4/4=100%. 직접 EKS 읽기·접수 성능 개선 실측 없음. [보고](records/reports/2026-10-29_eks-cd-diagnostics-independent-review.md).


2026-10-29 ST4F-729 독립검토: 필수2/3=66.7%, 기존728증거XML 보안실패로 통합HOLD. Next합성2/2·웹세션11/11=100%, push/배포0. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f729-independent-review.md).

2026-10-29 EKS scalar: main ?1?????? ??3/3=100%, PR109 Linux ?? ?; ???3/3 ????? ?? ???. [??](records/reports/2026-10-29_eks-scalar-release-and-measurement.md).

2026-10-29 ST4F-729 후속: 기본 build4/4·화면14/14=100%, 보안124/125=99.2%·필수2/3=66.7% HOLD. 기존 XML 불변·표본 id 생성 원인 수정 후보, push/배포0. [검증·실패·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f729-source-followup.md).

2026-10-29 ST4F-729: 기존 필수2/3=66.7% HOLD·오탐 분류 제안 보안143/143=100%, XML 불변·정책 승인 전 미통합. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f729-security-resolution.md).

2026-10-29 EKS scalar 최종: PR109→main57f3d2f004d0·CI/CD 성공·4앱4/4=100%, 실제전후각3/3 완료. 운영속도 인과개선 미입증·합성6건 보존. [보고](records/reports/2026-10-29_eks-scalar-release-and-measurement.md).

2026-10-29 ST4F-729 보존 경계 검토·HOLD 유지, 미배정708 독립 검증. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f729-policy-review-and708.md).


2026-10-29 위도 가지치기 독립 검토: 필수3/3=100%, 실제경로12/12 일치·로컬16.63% 감소. 전체층 기존실패/미실행·Linux/EKS 측정 남음, 배포HOLD. [보고](records/reports/2026-10-29_eks-latitude-independent-review.md).


2026-10-29 ST4F-731 독립검토: 새PG45/45=100%·추가 차단 결함 미발견, 필수2/3=66.7% security HOLD. [근거](../final_project_cs/wiki/records/reports/2026-10-29_st4f731-response-fence-independent-review.md).


2026-10-29 EKS 구조 후보 기각: 예외 동작 차이·전체층179/216=82.87%, 필수3/3=100%. 그래프 적재 대안 조사·통합0. [보고](records/reports/2026-10-29_eks-structural-radius-and-graph-load.md).

2026-10-29 ST4F-733 거절 일정 이름 누락 격리수정:단위39/39·실DB집중6/6=100%,확장15/16=93.8%,보안124/125·필수2/3=66.7% HOLD,설명만 정확재조회·종결0. [근거·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f733-named-refusal.md).


2026-10-29 733+731 두 번째 독립검토: PG43/43·실제runner6/6·변이5/5=100%, 보안HOLD 유지·미배정734 추가검증. [보고](../final_project_cs/wiki/records/reports/2026-10-29_st4f733-731-second-independent-review.md).


2026-10-29 ST4F-734 격리브라우저 저장3/3=100%·2분질문0 잔여,724 후보audit3/3=100%·보안HOLD 유지. [근거](../final_project_cs/wiki/records/reports/2026-10-29_st4f734-staged-browser-and724.md).


2026-10-29 ST4F-740 날짜 변조·잘못된 날짜 접수 실패 격리 수정: 접수1073/1073·실API/PG3/3=100%, 필수 DoD 26/26·보안124/125 HOLD. 원본2/2 보존·새 티켓25/25 재조회, 통합/운영종결0. [보고](../final_project_cs/wiki/records/reports/2026-10-29_intake-calendar-integrity.md).

2026-10-29 ST4F-740 independent review: intake1142/1142, corrected31/31, mutation2/2=100%; security124/125=99.2%, HOLD. [Report](../final_project_cs/wiki/records/reports/2026-10-29_st4f740-independent-review.md).


2026-10-29 ST4F-718 대기 후속: 웹1241/1241·Edge pending4/4=100%; 구형 탭/영속 HMAC 정책 미해결·통합HOLD. [검증·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f718-storage-wait-continuation.md).


2026-10-29 ST4F-732 단계 대기 시계 격리수정: 웹1230/1230·Edge5/5 = 100%, 보호XML 탐지5건·통합HOLD, 718미해결 유지. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f732-step-clock.md).

2026-10-29 ST4F-732 경계후속: Edge21/21·웹1232/1232=100%, 음성5/5=100%; scanner/XML·통합/운영 HOLD. [근거](../final_project_cs/wiki/records/reports/2026-10-29_st4f732-edge-followup.md).

2026-10-29 ST4F-732 경계후속 독립검토: 기존4실패4/4 재현, Edge21/21·실제 로컬SSE10/10·웹1232/1232=100%, 변이1/1=100%; 동일입력 실행경계·전체앱 수락 미확인, 필수/scanner/XML/통합/운영 HOLD. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f732-edge-independent-review.md).

2026-10-29 ST4F-719 동시 시각·장소 변경 카드 격리수정: 웹1231/1231·Edge5/5=100%, 보안124/125·필수2/3=66.7% HOLD·종결0. [보고·인계](../final_project_cs/wiki/records/reports/2026-10-29_st4f719-combined-change-card.md).

2026-10-29 EKS Linux 잔여5 원본 재현: 추가해소0/5=0%·실패5/5=100%, rail+bus 성립/선택·첫차 근거·golden 차이 분리, PR110 HOLD. [보고](records/reports/2026-10-29_eks-linux-remaining5-investigation.md).


2026-10-29 혼합 선택 추적: 기본39/39·전체6/8=75%, 동률 변이1/1=100%, 추가해소0/5=0%·PR110 HOLD. [보고](records/reports/2026-10-29_eks-mixed-selection-causality.md).

2026-10-29 C 드라이브 안전 정리: npm·pip 캐시 2,393/2,393=100% 삭제·실측 +1.111GB, NPU 실험 +25.278GB·WSL +6.349GB 확인, Git 권한 오류로 프로젝트 캐시 보존. [조사·삭제·인계](records/reports/2026-10-29_c-drive-safe-cache-audit.md).

2026-10-29 디스크 증가 예방 가드: 설정 기반 여유 검사·사본 재사용 장부 `tools/disk_guard.py` 구현, 시험 18/18=100%×3회, C: 여유 78.499GB(목표 400GB 부족 321.5GB), NPU FP16 이중 저장·엔진 ONNX+DLA·작업 사본 누적 원인 실측, 삭제 0건. [원인·사용법·한계](records/reports/2026-10-29_disk-growth-guard.md).

2026-10-29 C: 400GB 3차 정리: NPU 무효 엔진 17.72GB·끝난 `C:/_proj/*1029` 체크아웃 15개 36.23GB(번들·패치·미추적 sha256 보존)·Temp 5.33GB 삭제, 여유 119.73→175.24GB, 부족 224.76GB는 AGENTS.md 승인·다른 프로필·모델·WSL·시스템 설정으로 차단. [실행·차단 범위](records/reports/2026-10-29_c-drive-400gb-cleanup-round3.md).

2026-10-29 C: 400GB 4차 정리: guguroute scratch 남은 후보 6/6=100% 삭제(논리 17.91GB, 미푸시 HEAD 5개 bundle·고유 파일 5,785개 sha256 보존), 여유 170.55→188.03GB, 부족 211.97GB는 3차와 같은 승인·소유·실행 중 제약. [삭제 범위·보존·차단](records/reports/2026-10-29_c-drive-400gb-cleanup-round4.md).

2026-10-29 guguroute scratch 사본 정리: 끝난 체크아웃 19개·10-24~26 스냅숏 트리 18개를 커밋·고유 파일 보존 확인 뒤 삭제(논리 57.07GB, 고유 2.87GB는 backups 보존), C: 여유 최저 76.27GB→126.50GB, 같은 시간 NPU 실험 +33GB·WSL +3.7GB, 400GB 목표 미달. [삭제 범위·보존·증가 원인](records/reports/2026-10-29_guguroute-scratch-copy-cleanup.md).

2026-10-29 TeamFlow 재개: 미완료108/694=15.6%, 705·737 단위59/59=100%·증거 재조회2/2, 종결0·보안 HOLD. [인계](handoff/2026-10-29_teamflow-manager-resume-705-737.md).


2026-10-29 ST4F-746 ?? ?? ?? ?? ????: ??29/29???335/335=100%, ??0/3=0%???HOLD ??. [??](handoff/2026-10-29_teamflow-actionable-746.md).

2026-10-29 일정 설명 서빙 재개: 226/226·넘김91/91=100%, 신규 유료 호출0·보안/서비스 HOLD. [인계](handoff/2026-10-29_explain-writer-serving-resume.md).

2026-10-29 EKS 경로 독립검토: 전체223/223=100.00%, 빠른층1629/1630=99.94%·skip1, 경계89/89·번호보존4/4=100%. 정책판충돌 P2·첫차는 추정·성능비용 확인, PR110 HOLD·push0. [보고·인계](handoff/2026-10-29_eks-route-fix-independent-review.md).


2026-10-29 ST4F-746 독립검토: 실제PG/API 날짜변경1/1·계약367/367=100%, 관련49/51=96.1%·기존 아침읽기2실패, 보안HOLD·push0. [보고·인계](handoff/2026-10-29_st4f746-independent-review.md).


2026-10-29 EKS 정책판 P2 후속: 집중71/71·portable2/2=100%, 10구간 ABBA 17.473→15.531초. PR110/운영 fatal HOLD. [인계](handoff/2026-10-29_eks-route-policy-version-followup.md).


2026-10-29 ST4F-746 fixture 치환 검토: DNS 예약값 치환 의미손상, 보존파일 수정0·HOLD. [인계](handoff/2026-10-29_st4f746-fixture-replacement-review.md).

2026-10-29 ST4F-719 미리보기 독립검증: Edge21/24=87.5%, 비인증 늦은 응답·재시도 결함3건, 변이8/8=100%, 릴리스 HOLD. [인계](handoff/2026-10-29_st4f719-preview-independent.md).

2026-10-30 TeamFlow 미완료109/695=15.7%·매니저72/109=66.1%, 아침 이동 복구 격리시험41/41=100%, HOLD 유지. [인계](handoff/2026-10-30_teamflow-guguroute-morning-recovery.md).
