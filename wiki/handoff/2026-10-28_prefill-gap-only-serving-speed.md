---
type: handoff
title: 먼저 채우기 빈칸만 계산(확인 화면 공개 전 실제 처리 시간 단축) — Claude·Codex 3회차 · 격리 짝 측정 인계
description: 팀 role-manager ffb5fb1b5 위 후보 커밋 06b75e491(push 0). SSE 표시가 아니라 stage=review 공개 전 서버 처리 시간을 줄이는 변경 1건과 단계 시각 로그
status: draft
domain: travel
impl_scope: cs — final_project_cs/app/domains/travel_ops/components/intake/{autofix,prefill,pipeline}.py 후보
---

# 먼저 채우기 빈칸만 계산 인계 — 2026-10-28 02:50 KST

## 한 일

| 작업 | 상태 | 근거 |
|---|---|---|
| 기회 비교(10-27 병목 보고서 순위 1~6 · EKS 보고서 후보 · 코드 추적) | 끝 — 계약 변경(먼저 보여 주기) · 재학습 · 용량 · 대안 지연은 범위 밖. 남은 안전한 것 중 **먼저 채우기의 버려지는 추천 계산**이 가장 큼 | [보고서](../../final_project_cs/wiki/records/reports/2026-10-28_먼저채우기_빈칸만_계산_서빙속도.md) §결론 |
| Claude CLI(`claude-opus-5-5`) ↔ Codex CLI(`gpt-6.1-sol`) 실제 논의 3회차 | 끝 — 독립 분석 · 기회 비교 → 실제 diff 교차 검토(고친 것 5) → 실측 · 최종 판정(둘 다 approve) | 보고서 §1 · scratch `speed-real-20261028/ev/` |
| 후보 구현 | 끝 · **push 0** — 커밋 `06b75e491d8bf1e124d85cb45562fbd0c06c6413`(tree `6186358e`, 부모 팀 role-manager `ffb5fb1b5`), patch `ev/0001-prefill-plan-gap-only.patch` sha256 `f8f69975…eea5`. 팀 main `e88e01925` 와 바꾼 3파일이 같아 `merge-tree` 충돌 0 | `git show --stat 06b75e491` |
| 격리 짝 측정(합성, 10쌍 × 2 프로필, 호출당 0.3초) | 받기 → 먼저 채우기 끝 p50 **9.55 → 4.42초(−54%)** · 계산기 호출 20 → 4 · 결과 모양 20/20 같음 | `ev/paired.jsonl` · `paired_summary.json` |
| 느린 계산기(2.2초/호출, 3쌍) | 32.4 → 19.3초(−40%) · 고치기 전은 한도 25초 소진으로 빈칸을 못 채움 → 후보는 채움(결과가 바뀌는 경우 — 팀에 알릴 것) | `ev/paired_slow.jsonl` |
| 시험 | 새 14 HEAD RED 11 → 14/14 · 넓은 묶음 격리 PG 8,756 통과 · 실패 0(건너뜀 128 = 이동 자료 없는 환경) · security+contract+architecture 662/662 · ruff 통과 · `diff --check` 깨끗 | `ev/red5.xml` · `green5.xml` · `union_cand.xml` · `gate_cand3.xml` |

바뀐 경로(한 묶음): `final_project_cs/app/domains/travel_ops/components/intake/{autofix,prefill,pipeline}.py` · `tests/unit/travel/test_intake_prefill_plan_scope.py`(새) · `tests/e2e/test_intake_prefill_scope.py`(새) · `wiki/records/reports/2026-10-28_먼저채우기_빈칸만_계산_서빙속도.md`(새). 원본 작업 폴더에는 보고서와 이 인계만 복사했다(코드 변경 0).

## 남은 일

1. 부모: 줄기 결정(main=EKS · role-manager=x600) → 최신 팁에서 `git -c core.autocrlf=false apply -3 --index` → CI 전체. 앞 회차 SSE 후보 `35e1b0259` 와 파일이 겹치지 않는다.
2. 운영 효과 미측정 — 배포 뒤 새 로그 `intake prefill timing` · `intake stage timing`(EKS 는 유효 AWS 자격 뒤 pod 로그)과 x600 같은 SQL(받기 → `reading.prefill`)로 전후 비교. 그 전에는 운영 수치를 말하지 않는다.
3. 기존 위험(이번 범위 밖): 이웃한 두 빈칸의 시각 기준(먼저 채우기가 저장하지 않는 앞 빈칸의 시각 바꿈) · 공통 숙소 묶음 펼침 — 별도 후속.
4. 격리 PG(55491, scratch `speed-real-20261028/pgdata`)는 작업 끝에 멈췄다. 검증 worktree `speed-real-20261028/tree` 는 후보 커밋을 담고 있어 부모가 반영할 때까지 남긴다.

다시 확인하는 명령: `git -C <scratch>/speed-real-20261028/tree show --stat 06b75e491` · `sha256sum ev/0001-prefill-plan-gap-only.patch`.
