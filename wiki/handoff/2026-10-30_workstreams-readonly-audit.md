---
type: handoff
title: NPU TeamFlow EKS LLM 서빙 디스크 작업 현황과 안전한 인계
status: draft
domain: travel
---

# 2026년 10월 30일 작업 흐름 감사와 오케스트레이션 인계

> 2026-10-31 ??? ?? ??? ?? **#6/#7 ?? ?? ??**: `C:/_proj/eksfatal1029`? ???????? `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-folder-retire-20261031/eksfatal1029/files/`?? ?????. ?? Git? HEAD?refs?status?dirty.patch?unpushed.bundle??? ?? ??? `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/backups/proj-checkout-archive-20261029c/eksfatal1029__repo/`? ??? bundle verify 1/1 ?????. ?? #6/#7? HOLD?????? ??? ?????. ?? ??? ?? ?? ??? **?? ??**?? ???? ?????. WSL `/root/eks*` ??? ??????? ?????. ?? ?????? ? ?? ??? `followup-boundaries.json`, `wsl-followup.json`, `bundle-verification.json`? ?????. ?? ?? 10-30 ?? ??? ??? ?????.

작성: Codex, 00:10~00:14 KST. 수신: 후속 오케스트레이터. 요청한 작업 흐름 **5/5 = 100%**를 규칙·wiki·coord 및 로컬 프로세스 관측과 대조했습니다. 이는 감사 범위의 확인율입니다. 제품 전체 완료율과 각 작업 전체 완료율은 **분모 모름**입니다. 프로세스 종료·코드 컴파일·시험 통과·운영 수락을 서로 바꾸어 해석하지 않습니다.

## 실제 실행 상태

[00:13 KST 관측 증거](../records/evidence/2026-10-30_workstreams-readonly-audit/snapshot.json)는 원시 명령행 없이 PID·부모 PID·생성 시각·스크립트 이름·선택한 리스너와 disk inventory만 보존합니다. Windows 프로세스 조회는 시작과 후속 시점에 반복했습니다. 현재 로컬에서 안 보인다고 원격 작업 종료로 판정하지 않았습니다.

| 작업 | 관측 및 마지막 확인 기록 | 현재 판정과 차단 요인 |
|---|---|---|
| NPU | 감사 중 `build_wave_sdk_bounded.py` PID 21964, 이후 20940이 관찰됐고 00:13 스냅샷에는 없습니다. 별도 NPU 관련 Claude/Codex 세션도 있습니다. 최신 CPU 시도 두 개의 build.json은 모두 `not_started_supported_toolchain_missing`, device_started=false, cpu_harness_executed=false입니다. | 이전 작업은 중단/보류됐지만 **현재 재개 활동 있음**. CPU 빌드와 디바이스 검증은 미완료입니다. 이전 RAM 거부가 최신 시도의 직접 원인은 아닙니다. 지원 MSVC ARM64·native CUDA 헤더 환경이 최신 차단 요인이며, 디바이스 실행은 별도 자원·유휴 확인 필요입니다. |
| TeamFlow | 이번 Windows 조회에서 TeamFlow 작업 스크립트는 식별되지 않았습니다. 최신 actionable NOTICE는 격리 후보 COMPLETE·scope released라고 적습니다. 마지막 저장된 전체 집계는 미완료 **109/695 = 15.7%**, done586/review57/todo36/inprogress16입니다. | **격리 작업 종료와 백로그 종결은 다릅니다.** 이번 API 조회는 하지 않아 현재 집계는 미확정입니다. 보안 원본 관문·운영 화면 수락·최신 통합본 검증이 남습니다. |
| EKS | 이번 로컬 조회에서 EKS 명시 스크립트는 식별되지 않았고, `wsl --list --running --quiet`는 배포판 이름 없이 반환했습니다. 최신 wiki는 전체 이동 **223/223 = 100%**, PR110 draft/HOLD, reader fatal 미해결입니다. | **로컬 진단 종료/보류, 운영 원인 미확정**입니다. 기존의 좁은 비민감 런타임 오류 분류 경로가 확보되지 않았습니다. 과거 CI/CD 성공은 reader 정상 동작이나 PR110 반영 증거가 아닙니다. 원격 프로세스·PR 현재 상태는 재조회하지 않았습니다. |
| LLM 서빙 | llama-server PID28436, 포트18434 리스너가 존재합니다. launch-serving/launch-normal 자식 PID23968/2200/23120도 리스너를 보유합니다. 포트만으로 각각의 모델·역할을 확정하지 않습니다. | **로컬 서빙 프로세스 존재**, 건강 상태·고객 경로 수락은 미확인입니다. 설명 작성·대화 출처 후보는 서비스/보안 HOLD입니다. 기존 DoD 프로세스 종료는 DoD 성공이 아닙니다. |
| 디스크 | inventory 여유 182,387,269,632바이트(182.387GB), 최소32,212,254,720바이트, 목표400,000,000,000바이트. entries=[]·unregistered_dirs=[]입니다. | **목표 미달**, 목표까지 217,612,730,368바이트 부족입니다. 빈 목록은 관리 루트 밖 scratch·NPU·WSL까지 빈 것이라는 뜻이 아닙니다. 이번 정리/삭제는 없습니다. |

NPU의 최신 결과 위치는 `C:/Users/kcxsz/frog-npu-dev/experiments/npu-full/argen3/wave-cpu-build-20261029T151147564952Z/build.json` 및 `wave-cpu-build-20261029T151249176497Z/build.json`입니다. 둘 모두 직접 확인했습니다. 00:12 생성된 `resume-20261030T0012KST/`도 있어, 오케스트레이터는 기존 작업자와 중복 실행하지 않아야 합니다. 해당 기록은 감사 중 바뀌는 자료입니다.

## 남은 작업과 인계 조건

아래 **10개 후속 항목**은 이번 감사에서 정리한 인계 목록이며 프로젝트 전체 백로그의 분모가 아닙니다. 실행 배정·외부 통지·권한 변경·운영 쓰기는 수행하지 않았습니다.

| 번호 | 인계 대상과 재개 위치 | 다음 안전한 행동 | 완료 증거와 중지 조건 |
|---|---|---|---|
| 1 | NPU 기존 작업자, frog-npu-dev/experiments/npu-full/argen3 | 현재 재개 작업의 소유·결과 파일을 먼저 재확인하고, 기존 MSVC ARM64 및 native Windows CUDA 헤더의 존재·타깃을 읽기 전용으로 확인합니다. | 기존 도구가 없으면 정확한 누락 항목을 인계합니다. 설치·다운로드·시스템 변경은 이번 범위에 없습니다. CPU harness 수락은 compile.log·AA64 PE·run.log·실제 종료 코드까지 필요합니다. |
| 2 | NPU 자원/정확도 담당, 같은 기존 실험 | 기존 엔진·기준 로그를 재사용해 지원 ABI·모듈/로더 메모리 예산·NPU 유휴 여부를 먼저 정리합니다. | 자원 허가 전 디바이스 실행 금지. reps=1/reps>1 및 sequential/wave/sequential 장치 비교는 후속 허용 범위에서만 실행합니다. R2·FFN/G6 실패는 유지하며 CPU mock 통과를 NPU 정확도·속도로 쓰지 않습니다. |
| 3 | TeamFlow role-manager 담당 | 민감 원문을 열지 않는 이번 감사 결과를 바탕으로, 후속 허용 범위에서 상태별 조회를 새로 수행하고 소유 없는 작업만 선택합니다. 최신 NOTICE의 scope release와 실제 미커밋 후보를 함께 확인합니다. | 새 이슈를 쓰도록 별도 지시받으면 assignee=3rd_team_4_be. 기존 미배정25건 일괄 변경 금지. 109/695는 10-29 기록이지 현재 값이 아닙니다. |
| 4 | TeamFlow 보안 관문 담당, scratch/st4f719-blocker-independent-20261029/repo 및 ST4F746 관련 기존 후보 | 보존 XML와 scanner는 유지한 채 격리된 새 작업 버전에서 fixture 의미 보존 설계를 검토합니다. 기존 사본을 우선 사용합니다. | 719 웹 **1463/1463 = 100%**, 필수 **2/3 = 66.7% HOLD**. 746의 후보 scanner 성공은 원본 detector 성공이 아닙니다. DNS fixture 전체를 TEST-NET으로 치환하면 **110/114 = 96.5%**로 의미가 깨집니다. 예외/관문 약화로 닫지 않습니다. |
| 5 | TeamFlow 운영 수락 담당 | 저장된 번들 대조 증거와 실제 화면 수락의 차이를 정리하고, 읽기 전용으로 가능한 수락 항목만 분리합니다. | 8건의 번들 문구 대조는 화면 수락·done이 아닙니다. 게스트 세션 POST·운영 로그인·시험 여행 생성/삭제는 이번 범위에서 실행하지 않습니다. |
| 6 | EKS 관측 담당, C:/_proj/eksfatal1029 | 기존 synthetic 진단 시각 2026-10-28 22:09:29~22:12:00 UTC의 reader_structured_stream 오류 범주를 기존 승인된 비민감 로그 경로에서 확보할 수 있는지 확인합니다. | 해당 경로·권한이 없으면 그 항목을 정확한 blocker로 남깁니다. 자격정보 검색·추가 권한·CI 권한 전용·고객 로그/DB export 금지. 오프라인 **7/7 = 100%** 재현은 원인 판정이 아닙니다. |
| 7 | EKS 통합 담당, 기존 /root/eksremain3r_1029/wt-bisect 및 C:/_proj/eksfatal1029 | 저장된 v0.9.3 후보 patch와 portable 시험을 검토하고, 다음 허용된 세션에서 최신 통합본 관문과 담당 수락을 확인합니다. 이 감사는 WSL을 시작하지 않습니다. | reader fatal 해소·첫차 근거·정책 수락과 PR110 상태를 별개로 확인합니다. 첫차 4표본은 추정이며 실제 첫차 관측0입니다. 현재 감사에서는 merge/push/CD/배포하지 않습니다. |
| 8 | 설명 작성기 기존 담당, Hermes scratch/schedule-explain-impl-20261029/wt | r8 및 resume-fixes-final.patch/manifest-final과 기존 반례를 함께 검토하고, 독립 재검토 범위와 격리 DB/자식 프로세스 차단 준비를 정리합니다. | 관련 **226/226**, 넘김 **91/91 = 100%**는 전체 서비스 수락이 아닙니다. 유료 저장 답 **8/10 = 80%**, DoD 미완료·의미검사 한계·설명 예산 공유가 남습니다. 새 유료 호출·서빙 교체는 수행하지 않습니다. |
| 9 | 대화 출처 담당, 같은 기존 wt와 review7 | 저장된 공식 스키마와 후보의 JSON wrapper/필수 신원 필드 차이를 검토하고, 공식 JSON 봉투 문서 또는 이미 승인된 비민감 응답으로 검증할 계획을 인계합니다. | HTTP **4/4**, 문서/strict **4/4 = 100%**는 실제 제공처 전체 wire 수락이 아닙니다. 실제 제공처·실모델·DB/브라우저·전체 DoD 미확인 상태와 서비스/보안 HOLD 유지입니다. |
| 10 | 디스크 담당 | 기존 inventory와 NPU 소유 NOTICE를 대조해 관리 밖 경로·소유·산출물 재사용 여부를 확인합니다. 후속 수 GB 쓰기 전 tools/disk_guard.py check --path <위치> --need-bytes <예상량>을 적용합니다. | 종료 코드3/2면 쓰지 않습니다. 지울 후보는 정확한 절대경로·파일 목록·보존 증거와 그 대상의 사용자 삭제 승인이 있어야 합니다. 과거 정리 NOTICE는 새 삭제 승인이 아닙니다. |

NPU argen2의 단일 프로세스 실행·17/17 토큰 일치와 argen3의 CPU 빌드/장치 미수락은 다른 범위입니다. stream16의 17:50 idle 기록도 argen3 현재 실행 상태를 대신하지 않습니다. H1 실측·레이어 합산·투영 속도·저메모리 스트리밍 속도를 섞어 최종 성능으로 보고하지 않습니다.

## 근거와 우선순위

- 루트 AGENTS 및 사용자 제공 규칙, cs AGENTS/RULE, wiki 색인·handoff를 확인했습니다. 원본 Git 조회/변경은 필요 없어 실행하지 않았습니다. 오래된 coord의 cleanup 권고보다 현재의 대상별 삭제 승인 규칙을 우선합니다.
- coord 위치: `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/_coord/`. TeamFlow manager1915/actionable, EKS fatal/release, explain-writer paid serving 및 disk round4/growth NOTICE를 직접 대조했습니다. NOTICE는 소유 기록이며 지금 살아 있는 실행 보증이 아닙니다. 현재 예약은 재확인해야 합니다.
- NPU 근거: `C:/Users/kcxsz/frog-npu-dev/HANDOFF-20261029-npu-full-resumed.md`, `experiments/npu-full/argen3/REPORT.md`, `REQUEST_WAVES.md`, 위 최신 build.json 두 개, `_coord/NOTICE-npu-stream16-20261029.md`. 소유 NOTICE의 weights·references·활성 엔진 보존 경계를 유지합니다.
- [719 최신 독립 검토](2026-10-29_st4f719-auth-generation-independent-review.md), [746 보안 관문](2026-10-29_st4f746-security-gate.md), [746 fixture 검토](2026-10-29_st4f746-fixture-replacement-review.md), [마지막 TeamFlow 집계](2026-10-29_teamflow-actionable-746.md), [운영 번들 수락 한계](2026-10-29_teamflow-manager-bundle-markers.md).
- [EKS 최신 전체층](2026-10-29_eks-route-policy-full-recheck.md), [reader fatal 오프라인 원인 분리](../records/reports/2026-10-29_eks-reading-fatal-offline-discrimination.md). 일부 과거 인계의 한글은 이미 `?`로 손상돼 있어 손상 문장을 복원·추정하지 않고 구조화 증거 및 읽을 수 있는 NOTICE와 대조했습니다.
- [설명 서빙 재개](2026-10-29_explain-writer-serving-resume.md), [출처 스키마 후속](2026-10-29_conversation-source-schema-continuation.md), [디스크 가드](../records/reports/2026-10-29_disk-growth-guard.md).

## 이번 한 일과 안전 경계

규칙·wiki·coord·기존 NPU 결과 대조, 반복 Windows 프로세스 조회, 리스너 조회, 실행 중 WSL 목록 조회, disk inventory 실행, 민감 필드 없는 증거 저장, 이 인계 작성 및 handoff 색인에 링크 추가를 수행했습니다. 외부 오케스트레이터 전송·새 작업자 실행은 하지 않았으며 위 목록을 검토 가능한 인계물로 남깁니다.

고객 자료·키·토큰·환경파일·DB·원시 TeamFlow 이슈·대화 transcript는 열지 않았습니다. Hermes process registry는 실행 메타데이터의 구조 및 선별 PID/작업 태그만 추출했고 원시 명령행·사용자 식별 필드는 출력/저장하지 않았습니다. 인터넷/운영 API 호출·프로세스 중지·설치·새 clone·산출물 복제·설정 변경·삭제·push는 모두 0건입니다. 쓰기는 이 감사의 wiki 기록 및 색인 추가에 한정했습니다.

새 모델/엔진/DB/clone 크기는 0바이트입니다. 감사 증거·인계문·색인 추가의 바이트 수는 같은 evidence 폴더의 `artifacts.json`에 기록합니다. 가드 목록이 비어도 기존 사본을 임의 release/정리하지 않았습니다. 전체 디스크 보호나 모든 프로세스의 무부수효과를 보장한다고 주장하지 않습니다.


## 2026-10-30 후속 확인 링크

이후 TeamFlow 실제 GET 재집계는 미완료109/695=15.7%, 최근741~746 매니저 담당6/6=100%입니다. 구구루트 아침 이동 복구는 기존 격리 사본에서 재현2/2·최종시험41/41=100%, 보안 HOLD 유지입니다. 이 감사 당시 기록을 오늘 결과로 덮지 않고 [후속 인계](2026-10-30_teamflow-guguroute-morning-recovery.md)로 이어갑니다.
