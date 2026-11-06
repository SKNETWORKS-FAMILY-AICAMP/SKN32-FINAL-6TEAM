---

- [재난 수신 기록 계약](operations/receipt-history.md) · [구현 보고](records/reports/2026-10-17_1530_receipt-history-and-targets.md) · [매니저 독립 검토](records/reports/2026-10-17_receipt-history-manager-review.md)
type: guide
title: cs 프로젝트 구현 wiki
description: 여행 CS guguroute의 현재 계약·구현 안내입니다
status: draft
domain: travel
---

2026-10-29 ST4F-719 인증 세대 독립검토: 웹1463/1463·PG/Edge64/64=100%, 필수2/3=66.7% 보존 XML HOLD. [보고](records/reports/2026-10-29_st4f719-auth-generation-independent-review.md).

2026-10-29 ST4F-746 보안 추적: 최초4파일10건 시험값 오탐·원본 detector 실패/HOLD, 기능20/20=100%. [보고](records/reports/2026-10-29_st4f746-security-gate.md).

2026-10-29 ST4F-719 미리보기 P1 격리후보 수정: PG·Edge26/26·웹1321/1321=100%, 단위변이7/7·Edge변이3/3 검출, 필수2/3=66.7% scanner/XML HOLD·push0. [보고](records/reports/2026-10-29_st4f719-preview-privacy-fix.md).

2026-10-29 ST4F-746 아침 읽기 복구 독립검토: 단위20/20·시간대2/2·PG2/2·두여행1/1=100%, 원본 detector 4파일/HOLD·push0. [보고](records/reports/2026-10-29_st4f746-morning-independent-review.md).

2026-10-29 ST4F-746 ?? ?? ?? ??: ??56/56??PG2/2???2/2=100%, ?? ??HOLD?push0. [??](records/reports/2026-10-29_st4f746-morning-read-recovery.md).


2026-10-29 ST4F-719 재개: id mutation4/4 격리수정·Edge8/8·실PG전환4/4·개인정보10/10=100%, 필수1/3=33.3%(Git 환경 오류)·scanner/XML HOLD·push0. [보고](records/reports/2026-10-29_st4f719-late-id-mutations-resumed.md).

2026-10-29 A11 실DB 기준대조: 계약367/367·DoD26/26=100%, 회귀1505/1505=100%, 보안124/125=99.2%·필수2/3=66.67% HOLD·push0. [보고·인계](records/reports/2026-10-29_routing-a11-real-db.md).

2026-10-29 중단 S6 A11 재개: 숙박16/16=100%·XML118/118=100% 보존, 필수0/3=0%·통합HOLD·push0. [인계](../../wiki/handoff/2026-10-29_routing-a11-resumed.md).


2026-10-29 ST4F-719 개인정보·인증 복구 후보: Edge10/10·웹1282/1282·변이4/4=100%, 필수2/3=66.7% 보안 HOLD·push/배포0. [보고·인계](records/reports/2026-10-29_st4f719-privacy-auth-recovery.md).

2026-10-29 ST4F-719 identity-bound 독립검토: Edge4/8=50%·개인정보/401/옛 키 3경계 재현, 필수2/3=66.7% HOLD. [보고](records/reports/2026-10-29_st4f719-identity-independent.md).

2026-10-29 ST4F-719 세션 소유권 격리수정: 웹1268/1268·실인증 Edge3/3·변이4/4=100%, 필수2/3=66.7% HOLD. [보고](records/reports/2026-10-29_st4f719-identity-bound.md).

2026-10-29 새벽 첫차 원인추적: 첫차시험군2/3=66.67%·추가해소0/5=0%, 정류장 첫차 근거 미확보·PR110 HOLD. [보고·인계](../../wiki/records/reports/2026-10-29_eks-dawn-first-vehicle-causality.md).

2026-10-29 ST4F-719 수정 후보 독립 재검토: 웹1257/1257·변이3/3=100%, Edge5/6=83.3%, 계정 경계 잔존/이력 삭제 재현, 필수2/3=66.7% HOLD. [보고·인계](records/reports/2026-10-29_st4f719-fixes-independent-review.md).


2026-10-29 ST4F-719 검토실패3건 격리수정: 새사본 웹1257/1257·Edge9/9=100%, 필수2/3=66.7% HOLD. [보고·인계](records/reports/2026-10-29_st4f719-review-fixes.md).


2026-10-29 ST4F-719 독립검토 HOLD: 웹1231/1231·변이4/4=100%, 정보누락2·로그아웃잔존1·필수2/3=66.7%. [보고](records/reports/2026-10-29_st4f719-independent-review.md).


2026-10-29 ST4F-732 단계 시계 독립검토: 목표12→0초 확인·Edge15/19=78.9%, 기존경계4건·필수2/3=66.7% HOLD. [보고·인계](records/reports/2026-10-29_st4f732-clock-independent-review.md).



2026-10-29 ST4F-718 저장 정책 독립검토: 웹1241/1241·Edge22/22=100%; 구버전 중복/raw ID 재생성·queued open 무응답 재현, 기존 필수2/3=66.7% HOLD 유지. [보고·인계](records/reports/2026-10-29_st4f718-storage-policy-review.md).
# cs 프로젝트 구현 wiki

2026-10-29 ST4F-728 늦은 게스트 응답 차단: 웹1227/1227·모방화면11/11·필수3/3=100%,운영수락남음. [보고](records/reports/2026-10-29_st4f728-guest-logout.md).

2026-10-29 ST4F-597 메뉴 선택 고침 독립 검토·양원격 반영 `07e79f1987`: Dining258/258·판정39/39·필수3/3=100%,운영 종결 보류. [보고](records/reports/2026-10-29_st4f597-independent-review.md).

[2026-10-28 서빙 속도] 먼저 채우기가 빈칸 일정만 추천 계산(후보 `06b75e491`, 격리 합성 받기→채우기 끝 p50 9.03→4.12초). 독립 검토: 이웃한 두 빈칸 시각 기준은 새 회귀가 아닌 기존 결함 — 장소만 저장하는 기준(`keep_times`)으로 고쳐 같은 식당 연속 대체를 없앰(adjacent 합성 6.69→4.80초), push · 배포 0. [후보](records/reports/2026-10-28_먼저채우기_빈칸만_계산_서빙속도.md) · [독립 검토 · 고침](records/reports/2026-10-28_먼저채우기_이웃빈칸_독립검토.md)

[2026-10-27 서빙 속도] x600 채팅 접수 157건: 「읽는 중」 p50 20.4초 · p95 62.3초 — 모델 읽기 p50 7.9초, 위험 점검+먼저 채우기 p50 10.1초. 후보 2건(위험 점검 동시 `4f8453ae` · 대안 준비 앞단 양보 `665e17c5`), push · 배포 안 함. [측정 · 병목 순위 · 남은 결정](records/reports/2026-10-27_계획서빙_속도_병목측정.md).

[2026-10-26 수정] 계획 읽기가 실패(`fatal` · x600 `reading_model_failed`, 막대 8/9줄)인데 질문 붙잡기 때문에 「계획을 다 읽었어요」·「읽어 온 계획 확인하기」가 뜨던 결함 — 실패면 붙잡지 않고 실패 화면으로. vitest 1205/1205=100%(rebase 뒤), Playwright 36/36=100%(mock). [원인·근거·시험](records/reports/2026-10-26_계획읽기_실패인데_다읽었어요_수정.md).

2026-10-25 [전체 과거 normal confirm HTTP 증명·35개 회귀·전체관문 대조](records/reports/2026-10-25_allpast-normal-confirm-proof.md) — 추가 제품 수정 없음, 원격 반영 전.

2026-10-27 전수검사 A~J 후보 통합(F · C · B · G · A · D · E · H · J 9/9, I 제외) — 빠른 관문 10,530/10,530 · vitest 1,217/1,217 · DB core 89/89 · 수용 49 엄격 39/49, role-manager 반영 [보고서](records/reports/2026-10-27_K_전수검사후보_통합_role-manager.md)

2026-10-27 미통합 후보 통합(T04 범위 경계 되묻기 · 「일정 수정」 완료 저장 실패 503 save_failed + 웹 문구표 짝) — role-manager 064208bd 위 통합 후보 `integ/F-20261027`, 빠른 관문 10345/10345 · DB 67/67 · vitest 1206/1206, 실 E4B T04 · X02 · F03 2/3(T04 는 저장 없이 되묻기 — 모델 과제), push 대기: [보고서](records/reports/2026-10-27_F_후보통합_T04_저장실패503_064208bd.md)

2026-10-27 TeamFlow(팀플로) 버그 수집 189건(전체 688건 중 미해결 ∪ 최근 30일 버그) — 결함 111건 중 해결 표시 93건 · 미해결 18건, 숙소 고를 때 상한 넘는 재확인 가격 적용(ST4F-709) · 「수 있음」을 수요일 휴무로 읽던 것(ST4F-685)을 격리 후보에서 고침(단위 시험까지, 푸시 전): [보고서](records/reports/2026-10-27_teamflow_버그수집_J.md)

2026-10-26 계획 접수 호텔 줄 — 후보 하나로 먼저 채우던 것 · 활동으로 잡히던 것 · 체크인 없으면 숙박이 안 되던 것을 고쳐 종류(숙박·활동·식사) 확인 질문과 후보 고르기로(로컬 관문 0 실패, role-manager 까지): [기록](records/reports/2026-10-26_호텔_종류확인_후보선택.md)

2026-10-26 수용 49 모델 해석 실패 5행 원인 분류 — 코드 결함 1(T04: 범위 경계 시각을 한 일정 새 시작으로 쓰던 것, 되묻기로 고침 · 후보 145367ee5, push 전) · 모델 과제 4(I05 · I07 · T15 · F02) · 하네스 결함 0: [보고서](records/reports/2026-10-26_fix5_수용5행_원인분류_T04.md)
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
2026-10-29 A11 ready 독립 재검토: 실DB 9/9·웹 69/69 통과, 권한·미답·미검사·판 충돌 우회 새 결함 없음. XML 336/336 불변, 보안 124/125 HOLD 유지·운영 변경0. [검토 보고](records/reports/2026-10-29_a11-ready-independent-resume.md).

2026-10-29 Linux 기대13/18=72.22% 추가정정·전체층218/223=97.76%/5실패,기본전체RAG16미준비·운영HOLD. [보고](../../wiki/records/reports/2026-10-29_eks-linux-remaining18.md).

2026-10-29 ST4F-718 저장/quota/privacy 후보: 웹1241/1241·Edge22/22·변이4/4=100%, 필수2/3=66.7% HOLD·정책/운영수락 미완. [보고·인계](records/reports/2026-10-29_st4f718-storage-policy.md).

2026-10-29 ST4F-718 독립검토: 웹1255/1255·변이4/4·Edge12/12=100%, 무제한 증가·quota/탭 한계 확인, 필수2/3=66.7% HOLD. [보고·인계](records/reports/2026-10-29_st4f718-independent-review.md).


ST4F-740 다음 미배정 항목으로 718의 자동 재생 이력 유실을 찾고 격리 수정했습니다. **필수 2/3 = 66.7% HOLD**, 종결·push·배포 0건입니다. [보고서](records/reports/2026-10-29_st4f718-credits-retention.md).


2026-10-29 EKS Linux 기대값 정정:198/216=91.67%·기존18/36=50%해소,필수3/3=100%·운영HOLD. [보고](../../wiki/records/reports/2026-10-29_eks-linux-precision-expectations.md).


2026-10-29 보안 원본2/2=100% 보존·과거XML 탐지5건/HOLD. 새727 브라우저16/16,739 운영읽기5/5=100%;운영종결보류. [보고](records/reports/2026-10-29_systemic-scanner-and-backlog.md).

2026-10-29 EKS 전체원본113/113=100%·Linux180/216=83.33%, 기존36실패/새실패0·PR110 draft/HOLD. [보고](../../wiki/records/reports/2026-10-29_eks-linux-full-original-reliability.md).

2026-10-29 734/724 독립검토: 실API·PG·Edge 전이확인, 변이3/3=100%;724 필수2/3=66.7% HOLD·보호18/18=100%.739 추가검증20/20=100%,운영종결보류. [보고](records/reports/2026-10-29_st4f734-724-independent-review.md).

2026-10-29 ST4F734 slack2 도착 질문 실API/Edge 수정확인·웹1232/1232=100%;724 최신tip검증·기존XML 필수2/3=66.7% HOLD. [보고](records/reports/2026-10-29_st4f734-tight-question-and724-validation.md).

2026-10-29 EKS reader 관측 후속: workflow5/5·격리31/31=100%, 기존 읽기 실행 경로 미확보·원인 미확정/HOLD. [보고](../../wiki/records/reports/2026-10-29_eks-reader-observability-boundary.md).

2026-10-29 EKS fatal 후속: reader215/215·원인분리7/7=100%, 운영원인 미확정·배포HOLD. [보고](../../wiki/records/reports/2026-10-29_eks-reading-fatal-offline-discrimination.md).

2026-10-29 EKS checking AMD6451/51·PR CI3/3=100%, 운영 기준2/3=66.67%·fatal1건으로 배포HOLD. [보고·인계](../../wiki/records/reports/2026-10-29_eks-checking-amd64-validation-and-baseline-fatal.md).

2026-10-29 EKS 후속: 기존37실패 전부기준대조, 실제checking SQL절감후보·필수3/3=100%·통합HOLD. [근거](../../wiki/records/reports/2026-10-29_eks-linux37-and-checking-duplication.md).

2026-10-29 [734 읽기 전용 실서버 확인·733 격리 회귀](records/reports/2026-10-29_734-readonly-and733.md): 소스4/4·실PG7/7·웹39/39=100%,전체화면 수락 남음·731 HOLD 유지.

2026-10-29 ST4F-731 후보 문서 정정·잠금 시험8/8, 독립734 DB2/2·웹14/14=100%; 필수2/3=66.7% HOLD. [보고](records/reports/2026-10-29_lock-lifetime-and734.md).

2026-10-29 EKS ????: ?????? ????0.632?0.521?, ??24/24=100%; EKS?? ??????HOLD. [??](../../wiki/records/reports/2026-10-29_eks-full-data-latitude-pruning.md).

2026-10-29 EKS 서빙 후속 격리후보: 이동1488/1614=92.19%(skip126), 경계1500/1500=100%; 합성87.904→84.428μs·운영통합HOLD. [근거](../../wiki/records/reports/2026-10-29_eks-serving-bottleneck-partition.md).


2026-10-29 추가ST4F727:실제Leaflet/Edge 취약2/2→현재차단2/2=100%,운영수락보류. [보고](records/reports/2026-10-29_teamflow714-acceptance-and589-boundary.md).

2026-10-29 ST4F-714 종결1건·전체미완료102/688=14.8%.서버due자동추가를 영수증에 기록. [보고](records/reports/2026-10-29_teamflow714-acceptance-and589-boundary.md).

2026-10-29 ST4F-714 기존수정 수락:12/12=100%·x600 설정해시 일치.589 운영상한 읽기관측·종결보류. [보고](records/reports/2026-10-29_teamflow714-acceptance-and589-boundary.md).

2026-10-29 x600006268853c/908실함수 확인·ST4F-504역사재현→현행보호검증/종결. 새30/30·원반복30/30=100%,597메뉴근거부재348곳은남음. [보고](records/reports/2026-10-29_x600-acceptance-and-st4f504-causal-review.md).


2026-10-29 ST4F-597: 메뉴 원문이 있어도 누락하던 SQL 선택을 격리 수정·재현4→0, 새회귀6/6. 운영 메뉴 미적재 문제·이슈종결은 남음. [검증·인계](records/reports/2026-10-29_teamflow-st4f597-menu-source.md).

[현재3100 실측] 호텔조식 예시 실제교체 2/2=100% 완료: localhost93tSFrxar_RqgguLjsbwY / LANp4N2ThMaXaAI8RY4eWrbC, fresh guest 예시버튼·전체 textarea 확인, 제출/등록0·선택동의거부. old pin+검증delta이며 최신12커밋전체통합 아님. API/DB/Dining·기존고객계획 불변. [핸들/PID·사진·rollback·인계](records/reports/2026-10-25_hotel-example-live3100.md).

[현재 실측 2026-10-25 12:56] DB6536/API22260·기존웹27124/16432 연결복구. 새DB/API handed_off, HTTP/CORS12/12·실guest GET2/2·확정여행version1/items2 readback. test1 질문·대안선택은 미완료, 사용자원고 쓰기0. [긴급복구 근거·현재handoff](records/reports/2026-10-25_service-emergency-recovery.md).

2026-10-25 관리자: 지정 DB identity/app-role read-only 일치·3300/8070 준비. 예약 false/default revision0, 정식 로그인 비밀 전달 후 명시OFF 저장 필요. [근거](records/reports/2026-10-25_admin-db-handoff-connection.md).

2026-10-25: 승인된 V10+좌표 guard 로컬·LAN 실서비스 반영. proc_194b6e03a438 handed_off/PID27500, E4B/native tokenizer 실제로딩, 필수API·브라우저·비교DB2case stop/저장 확인. shared schema905/archives·의미 품질은 별도 남음. [최종 근거·rollback·한계](records/reports/2026-10-25_v10-local-service-release.md).

여행 CS triPilot의 현재 계약·구현 안내입니다. 제품 사양은 [상위 wiki](../../wiki/index.md)의 후속 확정 결정과 대조하며, 이력 문서는 당시 상태를 확인할 때만 엽니다.

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

## 고객 응대 라이팅 현재 상태

[E4B tokenizer 실제 복구·후속 재생 인계](records/reports/2026-10-25_e4b-tokenizer-recovery-v6.md): 공식 loader SHA256 일치 설치 자산으로 새 고유 cache를 복구, 원래 두 입력 양쪽 offline token-count/encode/decode 4/4=100% 통과했습니다. 기존 배치3/6 stage·채팅35/476 snapshot은 계속 실행 중입니다. 기존6stage와 PID 종료 후에만 실API·실E4B 양쪽4행을 순차 재생하는 continuation `proc_227989a6c1f3`는 부모 handed_off 확인, 결과 아직 대기·의미 unknown입니다.

[E4B v5 실재생 관찰·부모 인계](records/reports/2026-10-25_e4b-v5-observation-handoff.md): 2026-10-25 06:10 KST snapshot은 원계획8/8 review·reload, field baseline18/23·나머지 미진행, 단계2/6 exit0입니다. 실제 HTTP500 2행의 tokenizer 캐시 부재를 offline probe로 분리했으며 기존 parent-owned `proc_f11a51b230be`는 계속 실행 중입니다. 582행 비교 snapshot과 완료 후 정확 마감 명령을 남겼고 의미 개선/운영 성공은 미판정입니다.

고객 웹은 문의·알림·계획 검토/등록 응대 상태를 최소 표시하도록 연결했습니다. 기존 trip-home 타입 오류 2건을 계약에 맞게 최소 수정한 뒤 Vitest 770/770 = 100%, 깨끗한 격리 tsc·Next webpack production build가 통과했습니다. 원본 tsc는 0바이트 `.next-live/types/routes.d.ts`의 generated 오류 1건으로 계속 실패하며 화면은 미확인입니다. [웹 소비 계약](external/web-response-status.md) · [응대 소비 검증](records/reports/2026-10-24_web-response-status-consumption.md) · [타입 수정·전체 빌드 증거와 한계](records/reports/2026-10-25_web-trip-home-type-repair.md).

[독립 P2 늦은 등록 응답 세션 귀속 수정](records/reports/2026-10-25_web-registration-session-fence.md): 실제 발신 세션/세대를 결과까지 보존하고 교체 후 저장·성공 반환을 거부합니다. 정확 반례 RED 3건 → GREEN, 최종 Vitest 798/798 = 100%·92/92 파일, 격리 tsc·Next webpack production build exit 0입니다. 원본 generated TS2306·실화면/실환경 수락은 계속 열려 있습니다.

[HTTP4 승인 범위 실검증](records/reports/2026-10-25_http4-approved-155006.md): 원본 임시 loopback HTTP4 **4/4 = 100%**, 기존 57파일·964 nodeid 단일 재실행 **959/964 = 99.4813%·DB setup 오류 5·실패/skip 0**입니다. 전후 backend 1,297파일 hash 동일·임시 listener/thread 정리를 검산했으며 실DB/실모델/서비스/배포 수락은 아닙니다.

[계획서·문의·모니터링 구현/검증 현황](../../wiki/delivery/travel-response-current.md)에서 최신 결과·독립 검토 결함·승인 경계를 확인합니다. 개별 단위 통과와 실제 DB·모델·화면·운영 완료를 구분합니다.

## 2026-10-24 이관·과거 자료 참고

[복사 검증과 D 인계자료 요약](../../wiki/records/reports/2026-10-24_workspace-migration-and-history.md)에서 제한 시간 해시·readcheck 미완료와 10월 10~18일 자료의 시점·충돌을 확인합니다. 과거 기록을 현재 코드·배포 사실로 사용하지 않습니다.

## 2026-10-24 보조 자료 선별 보존

[실험 원본·결과 및 설명 그림 보존 안내](records/reports/2026-10-24_langgraph-comparison-preservation.md)를 추가했습니다. 과거 보고서는 동결 유지하며 원래 루트 폴더 삭제는 보류했습니다.

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

2026-10-25 — 잔여 비DB3후보 최소 통합·원본 독립probe RED→GREEN. 회귀327/331, 소켓차단4를 유지하며 DB/서비스/운영은 미변경. [최종 기록](records/reports/2026-10-25_remaining-non-db-integration.md).

2026-10-25 — F3 새 격리 수정은 원문 probe3실패로 **수락 미해결**입니다. 단일955개948통과/원문3실패/기존4bind차단. [타임라인·실패 경로·남은 계약](records/reports/2026-10-25_remaining-non-db-f3-unresolved.md).

2026-10-25 — F3 독립 검토와 동등 스케줄 회귀: 원문3실패를 시험 모순으로 분리하며 제품 logical-dispatch 경계만 수락 검토합니다. [정확 실행 결과·남은 범위](records/reports/2026-10-25_remaining-non-db-f3-acceptance.md).


## 현재 누적 릴리스 준비 — 2026-10-25

정확 history-preserving 비DB 누적 후보 준비 완료 / 릴리스 HOLD. 원문3실패·bind4차단·strict-budget 미수락 유지; admin/예약OFF는 wiki3경로 clean 병합 가능성만 확인(미적용). [최종 현황](records/reports/2026-10-25_remaining-non-db-release-preparation.md).


2026-10-25 — 관리자 예약 OFF/로컬 실행기 누적 격리 통합, 실제 실행·OFF 저장은 DB 대기. [최신 인계](records/reports/2026-10-25_final-admin-non-db-integration.md).


2026-10-24 한 구간의 택시 이동이 전체로 확대되지 않도록 읽기·구간 생성·성향 전달을 통일했습니다. 매니저 통합·검증과 운영 확인은 [결함 기록](records/reports/debugs/2026-10-24_택시구간_범위수정_매니저반영.md)에서 구분합니다.
2026-10-27 G 모델 품질 — 해석 문법이 쓸모없는 기준 칸 · 날짜 인용을 비워 두지 못하게(F02 통과 · I05 날짜 해소, 수용 49 엄격 38→39/49 = 77.6→79.6%, 회귀 0) · 속도 병목은 GPU 경합 · num_ctx 재적재(33 s+31 s)가 주원인 · 후보 00aca1041→a7e6da518(push 전) · W1~W6 공개 response 계약 초안: [보고서](records/reports/2026-10-27_G_모델품질_해석문법_속도_설계.md)
## 원본 최소 통합 현재 상태

[2026-10-25 launcher 독립분 반영·나머지 HOLD](records/reports/2026-10-25_original-minimal-integration.md). 기존 고객 응대 기록을 보존하며 backend/admin/auth 원본 수용 및 실제 예약 OFF 저장은 미확인입니다.


## 2026-10-25 관리자 OFF 수락 보충

[실측] 이전 인증 대기·OFF 미확인은 후속 정식 저장 및 독립DB 확인으로 해소됐습니다(false/override revision1, audit1). backend/admin/auth 원본 통합 완료를 뜻하지 않습니다. 현재 PC native5433/이전 WSL 요구 차이는 [완료 보충](records/reports/2026-10-25_admin-db-handoff-connection.md)에 명시했습니다.


## 공유 9구간 원본 적용 현재 결론 — 2026-10-25

[실측] 신규 reader/F3 7 + 기존 Diagnostics 보존2 = **9/9 = 100%** 원본 완료. 5필수파일 CAS·원본208/212(bind차단4·제품실패0)·관리자진단2/2·기존변경/index/refs/flags/백업 검산. 이전 shared HOLD 해소, 서비스/DB/OFF/모델/배포 변경0. [변경·검증·복원·인계](records/reports/2026-10-25_shared-original-safe-application.md).

## F3 원문 probe 3건 정식 해소 — 2026-10-25

[실측] 서로 모순되는 원문 probe 3건(81행 유료 호출 필요 vs 90행 `paid == []`)을 사용자 지시로 동등 시험 `test_llm_f3_acceptance.py`로 대체. 원문 바이트·실패 근거 보존, 같은 시험 바이트 수정 전 RED 3/3·수정 후 GREEN 3/3, 회귀 208/212(bind 차단4·제품실패0)로 이전과 동일. 제품 코드·DB·서비스·모델·배포 변경0. [보고](records/reports/2026-10-25_f3-contradictory-probe-resolution.md).

## I01~I08 로컬 전용 공개 문구 재대조 — 2026-10-26

[실측] 계획 writer 문구 6개 모두 role-manager 계약에 없는 공개 `response` 키를 새로 만드는 (b) 6/6=100% → 이식·커밋 0, 6행 N/A 유지. 16d6b00a 빠른 관문 10,219 통과·실패0·건너뜀173. [보고](records/reports/2026-10-26_I행_로컬전용문구_role-manager_계약재대조.md).

## 원본 직접 통합 A(날짜 위험·고객시간·최신팀 후보) — 2026-10-28

[실측] 원본 47경로 적용·커밋0, 고객시간 P1 4동작 원본구조 이식 RED12→GREEN12, 날짜 위험 HOLD. 백엔드 7,633/7,672·신규 회귀0, 관리자 6/6. [보고](records/reports/2026-10-28_original-final-integration.md).

## 원본 ops 8070·관리자 3300 직접 실행 — 2026-10-28

[실측] 원본 cwd에서 ops(리스너 PID 26564)·관리자(32620) 기동, 운영자 admin 로그인 200, 프록시·직접 GET·읽기 전용 DB 모두 `travel.booking.enabled=false`(override, admin, revision 2) 일치, 로그인 전 401. 소스 변경0·커밋0. [보고](records/reports/2026-10-28_original-runtime-ops-admin-switch.md).

2026-10-29 ST4F-711: 실제 백엔드 필수3/3=100%·동시성41/41=100%, 최신 양쪽 role-manager 소스217da9ad0 반영; 운영/LB-09 원인 확인 별도. [검증·한계·인계](records/reports/2026-10-29_st4f711-backend-gates.md).



[2026-10-29 버스 scalar 독립 검토](../../wiki/records/reports/2026-10-29_bus-scalar-independent-continuation.md): 필수3/3=100%, 기존 min_cell 보존·한 표현식 후보; 제외·운영 미검증·원격결과는 보고서 참조.
2026-10-29 EKS 후속: 버스 프로파일 단일값 검사 로컬 합성 개선 후보·독립 7,528/7,528 = 100%, 원본 제품 코드 변경·운영 배포 0. [측정과 한계](../../wiki/records/reports/2026-10-29_eks-bus-profile-scalar-performance.md).






2026-10-29 EKS 후속: main 위 scalar·CD 진단 후보 회귀, contract368/security125/DoD26 통과. 운영 접수속도 미입증·push/배포0. [측정·전제·인계](../../wiki/records/reports/2026-10-29_eks-operational-performance-continuation.md).

2026-10-29 ST4F-728 x600 소스2/2일치·공개403/운영수락 미완, 다음729 관리자46/46=100%;종결0·미완료102/688=14.8%. [근거](records/reports/2026-10-29_st4f728-production-and729-followup.md).

2026-10-29 ST4F-729 실제로딩 잔여결함 격리수정·화면2/2/회귀1/1/관리자46/46=100%,통합HOLD·종결0.공개403은Cloudflare1010,x600공개GET2/2통과. [근거](records/reports/2026-10-29_st4f729-loading-and-public403.md).


2026-10-29 ST4F-729 독립검토: 필수2/3=66.7%, 기존728증거XML 보안실패로 통합HOLD. Next합성2/2·웹세션11/11=100%, push/배포0. [보고·인계](records/reports/2026-10-29_st4f729-independent-review.md).

2026-10-29 ST4F-729 후속: 기본 build4/4·화면14/14=100%, 보안124/125=99.2%·필수2/3=66.7% HOLD. 기존 XML 불변·표본 id 생성 원인 수정 후보, push/배포0. [검증·실패·인계](records/reports/2026-10-29_st4f729-source-followup.md).

2026-10-29 ST4F-729: 기존 필수2/3=66.7% HOLD·오탐 분류 제안 보안143/143=100%, XML 불변·정책 승인 전 미통합. [보고](records/reports/2026-10-29_st4f729-security-resolution.md).

2026-10-29 ST4F-729 SHA 예외 미채택·보존 규칙 아래HOLD, 미배정708 독립 검증. [보고](records/reports/2026-10-29_st4f729-policy-review-and708.md).


2026-10-29 ST4F-731 빈 추천의 판 변경 경합 격리 수정: 접수단위1063/1063·DB10/10=100%, 필수2/3=66.7% HOLD·729 증거 불변. [보고](records/reports/2026-10-29_st4f731-empty-recommendation-race.md).


2026-10-29 ST4F-731 독립검토 REQUEST_CHANGES: 실제 edit 후 revision1/view2 두모드 재현2/2=100%, 필수2/3=66.7% 보안 HOLD 유지·push0. [보고](records/reports/2026-10-29_st4f731-independent-review.md).


2026-10-29 Mobility 위도 가지치기 독립 검토: 필수3/3=100%, 로컬 실익 확인·EKS 성능 미측정·배포HOLD. [보고 및 인계](../../wiki/records/reports/2026-10-29_eks-latitude-independent-review.md).


2026-10-29 ST4F-731 응답 경합 격리수정: 실DB29/29·단위1063/1063=100%, 보안124/125·필수2/3=66.7% HOLD. [검증·인계](records/reports/2026-10-29_st4f731-response-fence.md).


2026-10-29 ST4F-731 corrected fence 독립검토: 실DB45/45·변이3/3=100%, 보안124/125·필수2/3=66.7% HOLD 유지. [검토·인계](records/reports/2026-10-29_st4f731-response-fence-independent-review.md).


2026-10-29 EKS 반경 구조 검증: Linux 전체층216건 실행·37실패, 오류정책 반례로 미통합. 공개 자료 보완·그래프 적재 후속. [보고](../../wiki/records/reports/2026-10-29_eks-structural-radius-and-graph-load.md).

2026-10-29 [ST4F732 독립 진행 검증](records/reports/2026-10-29_st4f732-independent-progress.md):실PG13/13·위험22/22·웹45/45=100%,새 결함 없음·화면 수락 남음·731 HOLD 유지.

2026-10-29 ST4F-733 거절 일정 이름 누락 격리수정:단위39/39·실DB집중6/6=100%,확장15/16=93.8%,보안124/125·필수2/3=66.7% HOLD,설명만 정확재조회·종결0. [근거·인계](records/reports/2026-10-29_st4f733-named-refusal.md).


2026-10-29 733+731 독립검토: PG43/43·실제runner6/6·변이5/5=100%, 필수2/3=66.7% HOLD·734 후속. [보고](records/reports/2026-10-29_st4f733-731-second-independent-review.md).


2026-10-29 ST4F-734 실API 연결 격리화면3/3=100%·tight잔여,724 후보audit3/3=100%;운영수락·통합HOLD. [보고](records/reports/2026-10-29_st4f734-staged-browser-and724.md).


2026-10-29 ST4F-740 윤일·불가능한 날짜 정합성 격리 수정: 단위1073/1073·API/PG3/3=100%, 보안124/125 HOLD·원본2/2 보존·종결0. [보고](records/reports/2026-10-29_intake-calendar-integrity.md).

2026-10-29 ST4F-740 independent review: intake1142/1142, corrected31/31, mutation2/2=100%; security124/125=99.2%, HOLD. [Report](records/reports/2026-10-29_st4f740-independent-review.md).


2026-10-29 ST4F-718 대기 후속: 웹1241/1241·Edge pending4/4=100%; 구형 탭/영속 HMAC 정책 미해결·통합HOLD. [검증·인계](records/reports/2026-10-29_st4f718-storage-wait-continuation.md).


2026-10-29 ST4F-732 단계 대기 시계 격리수정: 웹1230/1230·Edge5/5 = 100%, 보호XML 탐지5건·통합HOLD, 718미해결 유지. [보고·인계](records/reports/2026-10-29_st4f732-step-clock.md).

2026-10-29 ST4F-732 경계후속: Edge21/21·웹1232/1232=100%, 음성5/5=100%; scanner/XML·통합/운영 HOLD. [근거](records/reports/2026-10-29_st4f732-edge-followup.md).

2026-10-29 ST4F-732 경계후속 독립검토: 기존4실패4/4 재현, Edge21/21·실제 로컬SSE10/10·웹1232/1232=100%, 변이1/1=100%; 동일입력 실행경계·전체앱 수락 미확인, 필수/scanner/XML/통합/운영 HOLD. [보고·인계](records/reports/2026-10-29_st4f732-edge-independent-review.md).

2026-10-29 ST4F-719 동시 시각·장소 변경 카드 격리수정: 웹1231/1231·Edge5/5=100%, 보안124/125·필수2/3=66.7% HOLD·종결0. [보고·인계](records/reports/2026-10-29_st4f719-combined-change-card.md).


2026-10-29 EKS 혼합 선택: 전체6/8=75%·동률 변이1/1=100%, 추가해소0/5=0%·PR110 HOLD. [보고](../../wiki/records/reports/2026-10-29_eks-mixed-selection-causality.md).


2026-10-29 ST4F-746 ???? ?? ??? ?? ??:29/29???335/335=100%, ??HOLD. [??](records/reports/2026-10-29_st4f746-checkout-route-match.md).


2026-10-29 ST4F-746 독립검토: 실제DB1/1·계약367/367=100%, 관련49/51=96.1%·기존 아침읽기2실패/보안HOLD. [보고](records/reports/2026-10-29_st4f746-independent-review.md).


2026-10-29 ST4F-746 fixture 치환 검토: 기준·7곳치환114/114=100%, DNS포함110/114=96.5%·HOLD. [보고](records/reports/2026-10-29_st4f746-fixture-replacement-review.md).

2026-10-29 ST4F-719 미리보기 독립검증: Edge21/24=87.5%, 비인증 늦은 성공·실패 재시도 결함, 변이8/8=100%, 릴리스 HOLD. [보고](records/reports/2026-10-29_st4f719-preview-independent.md).

2026-10-29 ST4F-719 ??? ?? ?? ?? ??: Edge28/28=100%, scanner/XML HOLD ??. [??](records/reports/2026-10-29_st4f719-authorization-lifetime.md).


2026-10-29 ST4F-719 auth lifetime independent review: unit32/40=80%, Edge28/28 + identity10/10 + UI1/1=100%; endpoint/race defects, security HOLD. [Review](records/reports/2026-10-29_st4f719-auth-lifetime-independent-review.md).

2026-10-29 ST4F-719 ?? ???watcher 401 ?? ??: ? 1,438/1,438?PG/Edge 58/58 = 100%, Git ?? ??? ?? 1/3 = 33.3% HOLD. [??](records/reports/2026-10-29_st4f719-auth-generation-race-fix.md).

2026-10-25 v2 — 독립검토 P1/P2와 추가 cmd 실패코드 누락을 새 격리 후보에서 수정했습니다. 최종 launcher 18/18·admin 41/41·8개 개별 관문 통과, 이전 wrapper 실패 기록은 별도 보존했습니다. 이전 7개 시험은 전체 배치를 검증하지 않았습니다. 실제 3300·예약 OFF 저장은 미검증입니다. [수정·실패 이력·결과](records/reports/2026-10-25_local-admin-3300-v2.md).

2026-10-25 — 로컬 일괄 실행의 개인 스크립트 필수 의존을 해소해 고객 API·운영 API·제품 관리자 3300 구성을 준비했습니다. 서비스·실DB·모델·배포는 실행하지 않았습니다. [실행 계약](operations/local-app-bundle.md) · [검증 기록](records/reports/2026-10-25_local-admin-3300.md).

2026-10-24 — 예약 마스터 기본 OFF를 제품 관리자 운영 설정에 연결한 격리 v2 후보입니다. 실DB·운영 OFF 적용·독립 검토는 미완료이며 [계약](operations/booking-master-switch.md)과 [실행 근거·한계](records/reports/2026-10-24_booking-admin-off-v2.md)를 구분해 확인합니다.

2026-10-24 — 고객 운영시간 P1 두 건의 격리 후속 수정: 완료·재연결 SSE 보존 및 고객 휴무의 공용 제외집합 전파 차단. 독립 재검토·운영 반영 전이며 [실행 결과와 한계](records/reports/2026-10-24_customer-hours-p1.md)를 확인합니다.

2026-10-24 — 최신 팀 develop 위 격리 날짜 위험 2차 보완: deferred·기간 겹침·재사용 시간경계·risk_panel 보존. 원본/운영 변경 없이 TDD와 실제 Python·웹·모형 부품 브라우저 검증을 수행했습니다. 전체 관문은 기준본과 같은 Git 실행 권한 실패 3건이 남으며, 최종 수치·실패/한계·인계는 [검증 기록](records/reports/2026-10-24_date-risk-second-pass.md)을 봅니다.

