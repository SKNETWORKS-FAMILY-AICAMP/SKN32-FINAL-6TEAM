---
type: report
title: EKS v0.9.3 정책판 전체 이동 재검증
status: draft
domain: travel
---

# 격리 정책판 재검증·PR110 HOLD

2026-10-29T21:37:01.420371 KST. 기존 `1ab3f0d882bc80d0ea437116d6301d0760084f68` + 미커밋 v0.9.3 패치를 재사용했습니다. 이번 실행 전체 이동 **223/223 = 100.00%**, 집중 호환성 **73/73 = 100.00%**, 추가 과거/캐시 문맥 탐침 **11/11 = 100.00%**입니다. 층 사이 중복이 있어 합산하지 않습니다. 전체 실패 0·오류 0·skip 0, 실행 424.03초입니다. 이전 223/223을 이번 결과로 재사용하지 않았습니다. [실제 집계](../evidence/2026-10-29_eks-route-policy-full-recheck/summary.json).

## 정본·수정 범위

루트/하위 AGENTS·RULE, wiki·개발 역할·코드 경로·Mobility 및 저장/소비 계약, datasets README/REPORT와 실제 coord NOTICE 15개를 읽었습니다. 최신 통합·담당자 승인·운영 반영은 주장하지 않습니다. 이 세션은 이전 P2 수정의 후속 자체 검증이며 별도 제3자 승인으로 표시하지 않습니다.

설정 정본은 격리 후보의 `engine/rules/rules_v0.3.json`입니다. `rules_version=v0.9.3`, `source_id=mobility_rules@v0.9.3`, `effective_date=2026-10-29`; history의 supersedes v0.9.2 및 changelog를 대조했습니다. Runtime과 Verifier Evidence는 기존 설정을 읽고, 파일명/문맥 schema_version/실행 코드에 판 분기를 추가하지 않습니다. 현재 wiki의 첫차 모델·미상·적용 제외 계약은 후보에만 추가된 상태입니다. [기존 수정 패치](../evidence/2026-10-29_eks-route-policy-full-recheck/candidate.patch), [이전 계약 검토](2026-10-29_eks-route-policy-version-followup.md). 원본 제품 코드·기존 골든·현재 정책 값은 이번에 고치지 않았습니다.

## 역사적 문맥·캐시 호환성

v0.9.1/v0.9.2/판 정보 누락 × transit/direct_walk/direct_taxi 9조합과 실제 과거 JSON snapshot은 조회/검증 콜백 전에 `needs_replan/basis_changed`를 반환하며 원 basis·legs·선택 ID·문맥을 보존했습니다. 수단별 행은 오래된 basis가 분기 전에 거절되는지의 탐침이며 유효한 새 도보/택시 전체 통합 시험을 대신하지 않습니다. 이전 판 안에서 이미 충돌한 결과를 소급 구별하거나 v0.9.3으로 재명명하지 않습니다.

캐시 키는 runtime 객체·시간표 판·규칙 판을 포함합니다. 서로 다른 runtime뿐 아니라 같은 객체의 rules_version이 달라도 키가 달라지고, 새 키로 옛 답을 읽지 않으며 옛 답의 복사본 변경도 원 캐시를 바꾸지 않았습니다. 런타임은 변경된 입력 파일을 감지해 재적재하지만 이미 실행 중인 계산기는 그 계산에 적재한 판을 유지합니다. 판 교체·인플라이트 요청·DB 이력의 전체 운영 전환을 이번 탐침만으로 검증했다고 하지 않습니다.

소비부 `trip_reminders`는 `needs_replan`을 `held`로 처리합니다. **자동 재계획·고정 항목 변경·고객 승인 완료가 아닙니다.** 관련 저장·고정 항목 기존 회귀를 이번 집중층에 포함했고 실제 DB 이관·고객 일정 수락·알림 발송은 0건입니다. [실제 탐침](../evidence/2026-10-29_eks-route-policy-full-recheck/migration-matrix.json).

## 첫차 추정 출처

기존 공개 입력을 다시 읽어 717노선·41,103구간을 확인했습니다. 301 seq53 best/worst 05:22/05:39, 710 seq20 04:21/04:27 재생이며 표본 **4/4 = 100% 추정**입니다. policy Evidence **18/18 = 100%**가 현재 설정의 source_id와 effective_date에 일치합니다. 공표 기점 시각의 `seoul_bus_route@2026-09-10`, 누적 프로파일의 `seoul_OA-21217`(2026-09-13), 정책 시행일 2026-10-29를 구분합니다. [실제 공개자료 재생](../evidence/2026-10-29_eks-route-policy-full-recheck/public-data-recheck.json), [출처 검사](../evidence/2026-10-29_eks-route-policy-full-recheck/provenance-check.json).

첫 통과는 best p50·worst max(p90,p50), 부족 구간 거리/속도 모델이며 정류장 최초 도착 실측/물리적 하한 보장이 아닙니다. 실제 정류장 첫 도착 관측 확보 0건, 정확도 검증 분모 모름입니다. 과거 여행일 재생은 현재 정책의 재생이며 당시 정책/관측의 소급 증거가 아닙니다. 유효 관측 우선·미래 환승에 현재 도착 전용 금지·미상 경고·첫차/막차 모순·운행일 경계는 집중층에서 확인했습니다.

## 자원·보존·재현

새 clone/전체 데이터 복사/GB 산출물/삭제 0건. 기존 WSL 사본과 Python3.12를 재사용했습니다. 실행 전 호스트 CPU 2~4%, WSL 가용 약14GB를 확인했고 pytest는 `nice -n 19 taskset -c 2,3`, BLAS/OMP 1스레드로 제한했습니다. 전체층·집중층·추가 탐침은 순차 실행했습니다. 관측 시 다른 장기 CPU 작업이 WSL 목록에 없었고 호스트 부하는 낮았으나 기존 작업의 지연을 직접 측정한 무영향 보증은 아닙니다. 운영/외부/유료 호출은 offline socket guard·mock LLM·연결 불가 DB로 차단했습니다. 시간은 성능 개선 또는 운영 지연 인과의 증거가 아닙니다.

명령은 `/root/eksstruct1029-py312/bin/python /mnt/c/_proj/eks-independent-1029/policy-recheck.py`, 완료 후 `policy-postcheck.py`이며 [전체 실제 인자](../evidence/2026-10-29_eks-route-policy-full-recheck/full-exit.json)·[집중 인자](../evidence/2026-10-29_eks-route-policy-full-recheck/compatibility-exit.json)·XML을 보존했습니다. 첫차 재생과 새 migration 탐침은 기존 시험 뒤 실행했습니다. 코드/규칙/시험/입력 해시 **300/300 = 100%**, 별도 골든 포함 시험 자산 **168/168 = 100%** 보존입니다. 자산 before 해시는 전체 시험 진행 도중 추가로 수집했으며 코드/입력 before는 실행 전입니다. 전체 입력 114파일(실자료113+빈 marker1) 289,950,471바이트를 복제하지 않았습니다.

disk_guard inventory와 세션 신규 크기는 evidence에 있습니다. 등록 사본 생성이 없어 release 대상이 없고, inventory 등록0이 WSL 전체를 추적한다는 뜻은 아닙니다. 모든 기존 자료·과거 보고서는 보존했습니다.

## 남은 일

최신 통합판 적용과 필수 관문, 담당자 정책·성능 수락, 실제 정류장 첫차 정확도, 운영 reader fatal 원인·해소는 별도입니다. 이번에 통합·필수3관문·운영 검증을 완료하지 않았습니다. **PR110 draft/HOLD 유지, production writes/push/merge/deploy 0건.** 운영 완료 분모 모름. [후속 인계](../../handoff/2026-10-29_eks-route-policy-full-recheck.md).


산출물 크기(최종 검증 직전): scratch 331,923바이트, 새 실행 스크립트 26,287바이트, bytecode 18,614바이트, evidence 260,693바이트. 전체층 temp 미생성, 집중층 temp du 10,035바이트. 기존 사본·자료는 보존했고 새 clone 0바이트입니다. [크기·inventory](../evidence/2026-10-29_eks-route-policy-full-recheck/artifact-sizes.json).
