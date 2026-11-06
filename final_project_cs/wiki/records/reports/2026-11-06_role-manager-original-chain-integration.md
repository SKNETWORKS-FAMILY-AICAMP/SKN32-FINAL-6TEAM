---
type: report
title: 원본 통합 체인 d0cc4f3 의 role-manager 반영 (PC 이전 전)
status: verified
domain: travel
---

# 원본 통합 체인 d0cc4f3 의 role-manager 반영 — 2026-11-06

사용자 지시(2026-11-06): 「커밋푸시 다 하라」 → 정정 「매니저 브랜치(role-manager)까지만 커밋푸시」. develop·main 은 건드리지 않는다. 강제 푸시 없음.

## 무엇을 넣었나

- 원본 PC 에만 있던 검토 완료 통합 체인 `d0cc4f375`(팀 develop `325ba25d8` 기반 7커밋 — 날짜 위험 2차 · 고객 운영시간 · 관리자 예약 OFF · 로컬 실행기 · 기록 문서)를 role-manager `1cf4542a1` 위에 **병합 커밋**으로 넣었다(체인 이력 보존, role-manager 의 빨리감기).
- 충돌 21파일은 role-manager 의 변경(rollback_hold · plan_input_extras · `_kept_ends` · 병렬 위험 점검 · LocalSlots)을 유지하고 체인의 의도만 덧붙였다. 줄끝은 저장소 기준 LF.
- 시험 보정 1건: `tests/unit/travel/test_booking_master_api.py` 가 `ACOP_TENANT_ID` 환경값에 기대어 `demo` 에서 실패하던 것을, 픽스처에서 공개 기능 읽기의 테넌트를 시험 테넌트로 고정했다(제품 코드 변경 없음).

## 넣지 않은 것(HOLD)과 이유

- LLM 넘침(overflow · hedge, 체인의 `c32348d42` · `eff496edc`): role-manager 의 로컬 동시 자리 설계(`LocalSlots`, 2026-10-28)와 같은 자리(`llm_failover.py` 호출 고리)를 서로 다르게 고쳐 단순 병합이 안 된다. role-manager 판을 유지했고 overflow 설정 2칸 · 시험 5파일(`test_llm_overflow_*` · `test_llm_f3_acceptance`) · `test_llm_failover.py` 변경은 넣지 않았다. 체인은 원격 `backup/guguroute-date-risk-integration-20261106` 에 그대로 있다.
- 원본 작업 트리의 그 밖의 미커밋 변경(추적 변경 116 · 미추적 코드 등): 원본 HEAD `efeb873a8` 가 role-manager 보다 1,108커밋 뒤라 대부분 role-manager 가 같은 파일을 더 고쳤다. 원본에서 더한 줄이 병합 결과에 있는 비율을 세면 코드 350경로 중 90% 이상 67 · 50~90% 20 · 50% 미만 29 · 파일 없음 234(옛 구조 `app/modules` 등 176 포함)다. 기능 단위 이식 · 시험이 필요해 이번에 넣지 않았고, 원격 `backup/guguroute-original-worktree-20261106` 에 보관했다.

## 검증 (로컬 · DB · 외부 API · 모델 없음)

| 항목 | 병합본 | 기준 role-manager |
|---|---|---|
| 관리자 lint · tsc · vitest | 0 · 0 · 48/48 | — |
| 웹 lint · tsc · vitest | 0 · 0 · 1237/1237 | — |
| Python 빠른 단계(architecture · contract · unit · security, `not live and not db and not slow`) | 10,831 통과 · 3 실패 · 173 건너뜀 / 11,007 | 10,727 통과 · 3 실패 · 173 건너뜀 / 10,903 |
| tools 시험(실행기 · 디스크 가드 · codex 충돌) | 40/40 | — |

- 실패 3건은 기준과 같은 이름이다(`test_no_tracked_text_file_leaks_infrastructure` · `test_api_key_file` 2건 — 이 PC 의 Git/무시 규칙 환경). 새 실패 0.
- 한 샤드는 파일 순서에 따라 `test_disaster_msg`(건당 약 130초) 뒤 `test_rate_limit` 근처에서 멈추듯 느려졌다. 같은 순서로 기준 role-manager 도 같은 지점에서 느려졌고, 해당 파일들은 따로 돌리면 병합본 233/233 통과다.
- 실제 서비스 기동 · 실DB · 예약 OFF 저장 확인 · x600 배포는 하지 않았다.

## 재병합 — push 직전 원격 이동

push 직전 원격 role-manager 가 `1cf4542a1` → `5a17e1f53`(과거 날짜 가드 확장)로 움직여 그 위에 다시 합쳤다(충돌 3: `plan-check/model.ts` 의 `draftProblem` 은 "hours" · "past" 둘 다 유지, `result-parts.tsx` import 합침, `wiki/index.md`). 재검증: 관리자 lint 0 · tsc 0 · vitest 48/48, 웹 lint 0 · tsc 0 · vitest 1245/1245, Python 빠른 단계 10,893 통과 · 3 실패(기준 `5a17e1f53` 와 같은 3건, 새 실패 0) · 173 건너뜀 / 11,069. 느린 샤드는 파일마다 따로 돌려 채웠다(시간 초과 0).
