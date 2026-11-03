# 2026-10-28 인계 — C12 독립 리뷰 수정 반영 · 최신 팀 role-manager 위 통합 후보 재검증

## 한 일
| 작업 | 바뀐 곳 | 상태 | 근거 |
|---|---|---|---|
| C12 후보 `7f670774f` 위에 리뷰 수정 `C12-review-followup.patch`(sha256 `b594f1e4…a64a`) 적용 — 여행 소유 확인 전 실패는 다시 읽지 않고 원래 예외(남의 여행 · 열린 제안에 503 내던 것, 평소 404) · 잠그기 전 실패의 503 본문 `proposal_status` = `open` | cs `entry/trip_api.py` · `tests/unit/travel/test_choose_storage_failure.py`(+2) · 계약 `trips.md` 한 문장 · 리뷰 보고서(새) | **검증 끝 · push 안 함** | [리뷰 보고서](../../final_project_cs/wiki/records/reports/2026-10-28_C12_리뷰_제안고르기_저장실패.md) |

- 기준: 팀 `role-manager` = `ffb5fb1b5`(`git ls-remote team`, 2026-10-28 00:29 · 00:40 KST 두 번 같음) → 후보는 fast-forward. 개인 원격(`origin`)은 자격 도우미 오류(`cannot spawn bash: Permission denied`)로 **확인 못 함**.
- 후보: `ffb5fb1b5` → `7f670774f` → **`129741ec3`**(tree `534f7eb8`), 로컬 브랜치 `scratch/c12-integ-20261028`(push 안 함), worktree `Hermes scratch/c12-integ-20261028`(전체 checkout · `.git` 있음).
- 적용 바이트: 3파일 sha256 이 리뷰 검증 사본(`c12-review-20261028/pb`)과 같음. `git diff --cached --check` · `apply --whitespace=error` · ruff 통과.

## 검증 (모두 같은 커밋 바이트)
| 검사 | 결과 |
|---|---|
| 단위 RED(`7f670774f` 의 trip_api) | 새 2건 실패 · 2/14 |
| 단위 GREEN | 14/14 = 100% |
| 실 PostgreSQL RED(scratch 클러스터 55491, 리뷰 탐침 8 + 단위 14) | 4 실패 / 22 — 리뷰와 같은 4건 |
| 실 PostgreSQL 이웃(후보 e2e 3 · 탐침 8 · web_api · watch_failures · watch_relaxed · desk_gate · chat_lodging_web · web_auth_guest_transfer · 단위 choose 3파일, `booking_full` 포함) | 122/122 = 100%, 가드 차단 0 |
| 빠른 관문(architecture · contract · unit · security · eval, not live/db/slow, 네트워크 · DB 차단 실행기) | 10,549 통과 / 0 실패 / 173 건너뜀 = 100%. 리뷰 때 archive 사본의 환경 실패 9건(`.git` · frontend 없음)은 전체 worktree 에서 0 |

- 탐침 `test_c12_review_probe.py` 는 후보에 넣지 않았다(시간 기반 0.6s 대기) — 실행 때만 임시 복사 후 지움, 최종 관문은 깨끗한 tree 에서 다시 돌림.
- 외부 쓰기 0: push · x600 · 공유 DB(5433) · 모델 호출 없음. PG 클러스터는 끝나고 중지.

## 증거 · 보존
- `Hermes scratch/c12-integ-ev/`: `ev/{unit-red,unit-green,gate-final,gate-clean}.{log,xml}` · `ev/{db-nbr,db-red}/` · `patches/0001,0002` · `c12-integ.bundle`(`ffb5fb1b5..129741ec3`, verify ok) · 실행 스크립트(`gate.sh` · `dbrun.sh` · `env.sh` 시험용 가짜 값).

## 남은 일 (부모)
1. push 직전 두 원격 `ls-remote` — 팀 `role-manager` 가 아직 `ffb5fb1b5` 인지, 개인 원격 상태.
2. `129741ec3` 를 role-manager 에 fast-forward push → x600 배포 로그에서 SHA 확인 · `/health` · 정상 고르기 200.
3. 리뷰 P3 잔여 3건(`_stay_recheck` try 밖 · 서버 lock_timeout 설정 시 경합 · expired/superseded 닫기 커밋 실패 안내)은 고치지 않음.
4. 정리: 통합 뒤 worktree `c12-integ-20261028` 와 이전 `routing-p1-choose-20261027` · `c12-review-20261028/src.tar`(235MB) 삭제 가능 — 증거 폴더는 보존.
