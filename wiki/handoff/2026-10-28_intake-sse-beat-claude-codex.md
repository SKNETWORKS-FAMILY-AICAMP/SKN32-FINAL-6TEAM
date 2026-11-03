---
type: handoff
title: 접수 SSE beat 분리 후보(EKS 80.7초 · 거짓 끊김) — Claude·Codex 논의 · 격리 구현 인계
description: 팀 main e88e01925 위 후보 커밋 35e1b0259(push 0). 실제 처리 시간은 EKS 자격 무효로 분리 못 함, SSE 거짓 끊김 기전만 고침
status: draft
domain: travel
impl_scope: cs — final_project_cs/app/domains/travel_ops/modules/live_progress/op_stream.py 후보
---

# 접수 SSE beat 분리 후보 인계 — 2026-10-28 01:20 KST

## 한 일

| 작업 | 상태 | 근거 |
|---|---|---|
| EKS 80.7초를 「실제 처리 시간」과 「SSE 거짓 끊김 표시」로 분리 | 처리 시간 분할은 **불가**(EKS 단계 시각 0 · 자격 무효) · 거짓 끊김 기전은 코드 + 합성 재현으로 확인(EKS 에서 그 기전이었는지는 미확정) | [보고서](../../final_project_cs/wiki/records/reports/2026-10-28_접수SSE_beat_분리_후보.md) · 원 [EKS 보고서](../records/reports/2026-10-28_eks-browser-80s-reading-latency-readonly.md) |
| Claude CLI(`claude-opus-5-5`) ↔ Codex CLI(`gpt-6.1-sol`) 실제 논의 4회차 | 끝 — 독립 분석 → 교차 비판 → 실제 회귀 판정 → 실제 diff 검토. 각 회차 session id · 시각 · 비용/토큰은 보고서 §1 | scratch `speed-cc-codex-20261028/ev/` |
| 후보 구현(`op_stream.watch`) | 끝 · **push 0** — 커밋 `35e1b0259ef73bb4187a15f1ef607c633633799f`(tree `df08e929`, 부모 팀 main `e88e01925`), patch `ev/0001-intake-sse-beat-split.patch` sha256 `976c4fbb0407538f…02f9`. role-manager `ffb5fb1b5` 에도 `apply --check` 통과 | `ev/candidate.txt` |
| 시험 | 새 단위 RED 6 → **11/11 × 3** · 격리 PG(scratch 55473) 관련 **74/74** · 넓은 묶음(intake_review · trip_events · web_guard) **69/69** · security+contract+architecture **325/325** · ruff 통과 · 합성 간격(운영 값) 조회 8초 막힘 **10.032 → 3.016초**, 내용 4초 막힘 5.015 → 3.016초 | `ev/*.xml` · `measure_gap_final.json` |

바뀐 경로(한 묶음): `final_project_cs/app/domains/travel_ops/modules/live_progress/op_stream.py` · `tests/unit/travel/test_intake_watch_beat_gap.py`(새) · `tests/e2e/test_op_stream.py`(contract_correction 1) · `wiki/external/rest-endpoints/web-intakes.md` · `wiki/records/reports/2026-10-28_접수SSE_beat_분리_후보.md`(새). 원본 작업 폴더에는 보고서와 이 인계만 복사했다(코드 변경 0).

## 남은 일

1. 부모: 어느 줄기(main=EKS · role-manager=x600)에 올릴지 결정 → 최신 팁에서 `git -c core.autocrlf=false apply -3 --index` → CI 전체.
2. 유효 AWS 자격 뒤: 같은 예시 브라우저 재시험에서 SSE 수신 시각(최대 이벤트 간격, `pending` beat)과 EKS 단계 시각으로 80.7초 분할 · 58초 원인 확정.
3. 막지 못하는 것: 첫 조회(`accepted` 전) 구간, 이벤트 루프 굶주림(같은 API 프로세스 BackgroundTasks · 작은 노드 — 원 보고서 후보 2·3, 사용자 결정).
4. 격리 PG(55473, scratch `pgdata` — c1 클러스터 사본)는 작업 끝에 멈췄다. 다시 쓰려면 `postgres.exe -D <pgdata> -p 55473` 를 백그라운드로.

다시 확인하는 명령: `git -C <clone> show --stat 35e1b0259` · `sha256sum ev/0001-intake-sse-beat-split.patch`.
