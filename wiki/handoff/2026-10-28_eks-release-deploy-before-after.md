---
type: handoff
title: EKS 릴리스 2026-10-28 배포 · 전후 실측 인계
description: main 20c296e77 EKS 반영, CD 1차 실패 뒤 재실행 성공, 같은 입력 13/13 전후 측정
status: draft
domain: travel
impl_scope: cs — 팀 원격 push · EKS 배포 완료. 원본 작업 폴더 코드 변경 0
---

# 인계 — 2026-10-28 EKS 릴리스

## 현재 상태

- EKS = main `20c296e77`(CD run `40699378486`, 22:54 KST digest · 공개 200 확인). role-manager `c52fb5c69`, develop `3463b30c6`.
- 배포 전후 같은 입력 13/13: SSE 최대 간격 p50 4.05 → 3.01초, 7초 넘는 간격 1/13 → 0/13(확인). 끝까지 걸린 시간 p50 45.6 → 32.1초는 변동이 커서 미확정(p≈0.2). [보고서](../records/reports/2026-10-28_eks-release-deploy-and-before-after-latency.md)

## 한 일 목록

- sa-0 시험 3커밋 Codex 독립 검토 후 통합(mobility 단언 약화는 후속).
- role-manager → develop → PR #107 → main. PR CI 1 실패(`test_chat_lodging_web` 만료 시계, `4fee819ca` 부터) 시험만 고쳐 재실행 통과.
- CD 1차 verify URLError → 자동 복구, 2차 성공. 마이그레이션 Job 실측 30.5 · 17.4초.
- 쓴 파일: 이 인계, 보고서, 인계 목차 한 줄. `_coord/R-eks-release-NOTICE.md`.

## 남은 일

1. x600 523 · SSH 타임아웃 — 복구 뒤 role-manager `c52fb5c69` 자동 배포 확인(사람/현장).
2. mobility `test_contract_keys` 추가 후보를 `more_options` 와 대조하도록 강화.
3. 운영 DB 측정용 손님 접수 26건(id 앞자리 scratch `summary.json`) — 정리 여부 사용자 판단.
4. 서버 쪽 단계 시각 분해는 유효한 AWS 읽기 자격증명이 생기면.
5. 개인 원격 develop(`da35486cb`)은 팀 develop 과 갈라져 있어 갱신 안 함.
