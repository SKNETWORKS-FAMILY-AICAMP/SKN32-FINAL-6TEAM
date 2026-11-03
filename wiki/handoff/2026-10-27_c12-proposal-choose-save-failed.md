# 2026-10-27 인계 — C 전수검사 결함 12(제안 고르기 저장 실패 500 → 503 save_failed)

## 한 일
| 작업 | 바뀐 곳 | 상태 | 근거 |
|---|---|---|---|
| 제안 고르기(`trip_api._choose` → `pending.choose`) 저장소 운영 실패를 잠근 제안 행 다시 읽기로 503 `save_failed` | cs `planning/pending.py` · `entry/trip_api.py` · 시험 2파일(새) · 계약 `trips.md` · `web-intakes.md` · 보고서 | **검증만 끝 · push 안 함** | [보고서](../../final_project_cs/wiki/records/reports/2026-10-27_C12_제안고르기_저장실패_503.md) |

- 후보 커밋 `7f670774f`(부모 role-manager `ffb5fb1b`, tree `3ca58e82`), worktree `Hermes scratch/routing-p1-choose-20261027`, patch `routing-p1-choose-ev/C12.patch`.
- 검증: 빠른 관문 10,547/0 · 단위 RED 5 → 12/12 · 실 PostgreSQL(scratch 클러스터 55491, 끝나고 중지) RED 3 → 3/3, 이웃 e2e 88/88 · ruff 통과 · Codex 텍스트 검토 P0/P1 0(P2 1건 반영).
- 남은 일: 부모가 두 원격 `ls-remote`(개인 원격은 이 세션 끝에 자격 도우미 오류로 재확인 못 함) 뒤 role-manager fast-forward push → x600 배포 `/health` · 정상 고르기 200 확인. develop · main 은 그 뒤 순서대로.
