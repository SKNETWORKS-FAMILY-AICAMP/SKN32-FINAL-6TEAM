---
type: handoff
title: EKS 릴리스 2026-10-28 독립 검증 · 병목 프로파일링 인계
description: 배포 성공 · 실측 재현 확인, CD 1차 실패 시각 분해, 로컬 복제 프로파일링, 측정 접수 26건 처리 경로. CD 진단 후보 72ba5ff48 미반영
status: draft
domain: travel
impl_scope: cs — 검증 · 진단. 운영 · 원격 변경 0
---

# 인계 — EKS 릴리스 독립 검증 (V, 2026-10-28 23:15 ~ 10-29 00:20)

## 현재 상태

- EKS = main `20c296e77` 확인(CD `40699378486` success · digest 4 · 공개 200). R 의 전후 수치는 원본 26행으로 재현됨. [보고서](../records/reports/2026-10-28_eks-release-independent-verification-and-bottlenecks.md)
- CD 1차 실패: 첫 공개 확인의 연결 단계 `URLError`(이유 미기록). verify 153초 중 ~130초는 되돌리기.
- 운영 확인 단계 최소 19.3초 — 로컬 CPU 몫은 1.3~2.8초. 나머지 귀속은 AWS 로그 없이는 미확정.

## 한 일 목록

- gh run 기록 · CD 결과 파일 · `aws_cd.py` 대조, 통계 재계산.
- scratch `eks-verify-20261028/`: main 새 clone, 자체 PG16(55591) 클러스터 · 이주 · 시드 · 장소 목록, 같은 측정 스크립트로 로컬 9회 + cProfile 3회, 연결 수 · 스레드 표본 기록. PG 는 멈춤.
- 후보 커밋 `72ba5ff48`(scratch clone 만): CD 공개 확인 연결 단계 실패 3회 재시도 · 실패 기록에 `URLError(이유형식)` · `recovery` 시간 분리. 80/80 · ruff 통과. **push 0.**
- 쓴 파일: 검증 보고서, 이 인계, 인계 목차 한 줄, R 보고서 머리 한 줄, `_coord/V-eks-verify-perf-NOTICE.md`.

## 남은 일

1. `72ba5ff48` 반영 여부 결정(재시도가 일시 장애를 가릴 수 있음) — 반영하면 S2 role-manager 통합 뒤 develop → main PR.
2. AWS 읽기 자격증명이 생기면: pod 로그 `intake stage timing` · `intake prefill timing`(10-28 21:23~23:09 KST)로 확인 단계 19초 귀속, RDS 연결 지표, api replicas · readinessProbe · 전략 확인.
3. 측정 접수 26건: 자동 정리(약 11-04 21시 이후) 뒤 `intake_backups` 에 남는 26건을 지울지 · 골든셋 추출에서 제외할지 사용자 결정.
4. 성능 후보(연결 풀 · 데우기 뒤 준비 · 공개 뒤 작업 분리)는 운영 근거 확보 뒤.
