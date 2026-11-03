---
type: report
title: Activity 서울 장소 원장 보강 계획과 비교 DB 리허설
date: 2026-10-26
status: plan-verified-not-applied
---

> 작업 폴더(증거 원본): `C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/activity-seoul-place-20261026-011437-9255`

# Activity 서울 장소 원장 보강 계획 · 비교 DB 리허설 — 2026-10-26 01:31 KST

## 결론

- **live `acop_cs` 의 `activity.ac_place` 는 시험 1행(`T05c98c6740be` 시험궁)뿐이고 서울 장소는 0/6,333 = 0% 입니다.** 그래서 지금 live 의 Activity 장소 찾기·운영 판정은 경복궁·남산서울타워·북촌한옥마을·국립중앙박물관 4/4 모두 `not_found`·판정 `None`(모름)입니다(읽기 전용 실측).
- 반면 코어 `place_catalog`(tenant `demo`, 서울 area 1)는 8,425행이 있고 대표 4곳도 있습니다. 하지만 **2026-10-16 사용자 결정으로 활동 팀은 `place_catalog` 를 읽지 않고 `activity.ac_place` 만 읽습니다**(`place_by_name.py`·`place_candidates.py`). catalog 에 있어도 Activity 경로는 그 자료를 쓰지 않습니다.
- 채울 자료는 **로컬에 있습니다. x600 에만 있는 자료가 아닙니다.** 팀 develop `d2ab93a6` 은 원격 `origin/develop` 과 같고(ls-remote로 확인), 거기에 git 으로 추적되는 `activity_total_data.csv` 가 있습니다(6,333행·서울 6,333·sha256 `283869ae…`). live API(v7a) 의 source-v7a 사본과도 바이트가 같습니다. 별칭 시드 `place_aliases.csv` 131행(`9081e834…`)도 같습니다.
- **비교 DB `gugu_replay_improved_20261025` 리허설: 21/21 = 100% 통과, 롤백 후 영구 변경 0** (조건: `read_hours` 생략). `read_hours` 를 포함한 1차 실행은 20/21 = 95.2% 였습니다. 실패 1건은 `read_hours` 가 원래 있던 시험행의 `hours_read` 를 바꾼 것입니다. 이 단계를 빼도 판정 결과는 12/12 = 100% 같았습니다.
- live 적용 스크립트(`live_apply.py`)는 준비만 했고 **실행하지 않았습니다.** 읽기 전용 dry-run 과 비교 DB 롤백 리허설에서는 검증 14/14 = 100% 가 나왔습니다. 실행 경로는 부모 승인 전까지 코드에서 거부합니다.

## ① 현황 집계(읽기 전용 · 2026-10-26 01:15~01:30)

| 표 | live acop_cs | 비교 baseline | 비교 improved |
|---|---:|---:|---:|
| `activity.ac_place` | **1** (시험궁, 서울 0) | 1 | 1 |
| `activity.ac_load_meta` | 1 (`source_file='t'`, sha 0…) | 1 | 1 |
| `activity.ac_indoor` | 0 | 0 | 0 |
| `activity.ac_live_status` (304) | **표 없음** | 0 | 0 |
| `activity.ac_place_alias` (306) | **표 없음** | 0 | 0 |
| `activity.ac_place_web_info` (307) | **표 없음** | 0 | 0 |
| `public.activity_judge_shadow` (305) | 있음 | 있음 | 있음 |
| `place_catalog` | 8,435 (demo 서울 8,425: tour_api 8,061·daiso 233·musinsa 49·oliveyoung 47·artbox 35) | 8,435 | 8,435 |
| `catalog_hours` | 1,615 | 1,615 | 1,615 |
| `places` | 3,136 | 7,826 | 8,785→8,805* |

\* improved 의 `places` +20 은 조사 중 다른 작업자가 쓴 것입니다. 제 tenant(`actseed_*`) 행은 0이고, 제 트랜잭션은 모두 롤백했습니다.

- 대표 장소: catalog 에는 4/4(126508·126535·126537·129703) 있고, ac_place 에는 0/4 입니다.
- live 스키마는 300~303·305 까지만 적용돼 있고 **304/306/307 이 빠져 있습니다.** live 코드(source-v7a)는 이 표들을 읽습니다. 표가 없으면 세이브포인트 안에서 실패하고 「모름」·시드 별칭만 쓰는 쪽으로 처리됩니다(코드 주석 `ledger._in_savepoint` 와 같습니다).

## ② 자료 출처·정본 대조

| 사본 | sha256(앞 16) | 행 | develop 대비 |
|---|---|---:|---|
| **팀 develop d2ab93a6 `data_processing/activity_total_data.csv` (정본)** | `283869aec62506f3` | 6,333 | — |
| live source-v7a 같은 경로 | `283869aec62506f3` | 6,333 | 동일 |
| 원본 저장소 HEAD(10-13) 같은 경로 | `f8ce15c640818d29` | 6,334 | 공유 6,333. 원본에만 있는 1건 `3458416` 은 develop 커밋 `a63256580` 에서 **의도적으로 삭제**됨. 운영시간 4,398·휴무 3,286 칸이 옛 값 |
| `datasets/travel/activity_total_data/*_1005.csv` | `b011cfb73a6eb0dc` | 6,338 | 이 사본에만 있는 5건(삭제됨·옛 자료), 16열 옛 형식 |
| `datasets/activity/processed/activity_total_data.csv` | `fdc87da5780aacd0` | 1,507 | PR#6 옛 자료, `firstimage` 열 있음 |

- 「없는 것만 보충」 판정: live ac_place 와 정본의 같은 id 겹침은 **0건**입니다. 정본 6,333건은 모두 새 행이고, 같은 id 로 내용이 충돌하는 행은 없습니다. 원래 있던 시험행은 정본에 없으므로 `--prune` 없이 보존합니다.
- 옛 사본에만 있는 id(1~27건)는 develop 이 삭제했거나 옛 자료라서 **가져오지 않습니다.**
- **정본 CSV 와 `place_catalog` 의 같은 id 충돌**(공유 6,003건, 서로 다른 표라 덮지 않고 보존): 좌표 50m 넘게 차이 33·주소 13·제목 13·유형 1. 예: 2997813·2611568 은 catalog 좌표가 (19.69, 117.99)로 오류값, 2828431 은 catalog 주소가 강남구인데 CSV 는 마포구, 1604652 는 「건청궁」 vs 「경복궁 건청궁」. 상세는 `compare_acop_cs.json` 에 있습니다. catalog 정정은 이 작업 범위 밖입니다.
- 정본에 없는 catalog 서울 tour_api 2,422건과 catalog 에 없는 정본 330건은 각자의 수집 범위 차이이며, 이번에 보충하지 않습니다.
- 별칭 시드 131행: 정본 제목과 불일치 0, 정본에 없는 id 0입니다.
- **x600 에만 있을 수 있는 것**(이번 보충에 필수는 아님): 모델로 편 `hours_week`(read_hours `--model`), `ac_indoor`·`ac_live_status`·`ac_place_web_info` 의 운영 중 누적 행, `customer` 별칭. 가져오려면 x600 접근(서버 지문·인증), 읽기 전용 덤프 범위 승인, canonical id/hash 대조가 필요합니다.

## ③ 비교 DB 리허설(정본 스크립트, 롤백)

- 실행 root: `…/activity-seoul-place-20261026-011437-9255/src/final_project_cs` (develop d2ab93a6 을 `git -c core.autocrlf=false archive` 로 받음. CSV·별칭 바이트는 blob 과 같음). 시작할 때 root 를 출력했고, 환경변수는 이 작업 전용 `ACTSEED_SOURCE_ROOT` 를 썼습니다.
- `ac_place` 는 tenant 칸이 없는 공용 표입니다. 그래서 **영구 적재 대신 외부 트랜잭션 한 개 안에서 실행하고 ROLLBACK 했습니다.** 다른 작업자의 비교 재생 결과를 바꾸지 않기 위해서입니다. 장소 행(`places`)은 새 tenant `actseed_<rand>` 에만 넣었고, 이것도 롤백했습니다.
- Python socket 은 전면 차단했습니다(DB 는 libpq). 모델·E4B·외부 호출은 0회입니다.
- 실행 순서: `load_places.rows/load(prune=False)` → `load_place_aliases.check/load(prune=False)` → (1차만) `read_hours.run(chat=None)` → 조회·판정.

| 검사 | 2차(read_hours 생략) |
|---|---|
| 같은 id 겹침 0 / 적재 6,333 / 원래 있던 행 보존(stale 1·pruned 0) | 통과 |
| 별칭 131/131, 문제 0 | 통과 |
| 시험행 불변 · place_catalog 불변 | 통과 |
| `find_place_by_name` 경복궁→126508, 남산서울타워·남산타워·N서울타워→126535(별칭 2건 `match=alias`), 북촌한옥마을→126537, 국립중앙박물관→129703 | 6/6 |
| 「다이소」 → ambiguous(195곳, 한 곳으로 찍지 않음) | 통과 |
| `alias_target(남산타워)` → 126535 + 좌표 + 서울 주소 | 통과 |
| `ledger.state_by_content` 4/4 행 반환(원장 사용). 경복궁 화 11:00 = `closed=True`(정기휴무), 수 = 공휴일 이월 미확인으로 `None` | 4/4 |
| `ledger.state`(새 tenant places 행 → 126535) | 통과 |
| `find_place_candidates(126508)` origin 경복궁 + 후보 4,796, source `activity.ac_place:…` | 통과 |
| ROLLBACK 후 지문 9종 동일(영구 쓰기 0) | 통과 |
| **합계** | **21/21 = 100%** |

- 대조군(적재 전, 읽기 전용): 비교 DB·live 모두 5개 이름 `not_found`, `state_by_content(126535)=None` 이었습니다. 위 결과가 적재한 자료에서 나온 것임을 확인했습니다.
- 한계 ①: 대표 4곳 모두 운영시간이 규칙으로 펴지지 않아 `known=False` 입니다. 규칙으로 펴지는 곳은 1,531/6,333 = 24.2% 입니다. 나머지를 펴려면 `read_hours --model`(유료 API, 또는 `--local` E4B)이 필요하며, 이번에는 호출하지 않았습니다. 판정은 지어내지 않고 「모름」으로 남습니다.
- 한계 ②: 비교 DB 에는 304/306/307 표가 이미 있습니다. 그래서 「표가 없는 상태에서 CREATE」는 같은 SQL 파일을 실행하는 no-op 으로만 확인했습니다. 다른 작업자가 쓰는 표를 DROP 해서 재현하는 방식은 잠금 위험 때문에 하지 않았습니다.

## ④ live acop_cs 적용 절차(부모 승인 후 · 미실행)

1. **live 쓰기 승인을 받습니다.** 그다음 `live_apply.py` 의 거부 줄(`refused in this worker build…`)을 지우고, 실행자는 부모가 맡습니다. live API·프런트 재시작은 필요 없습니다(DB 만 바꾸며, 별칭 DB 사본은 TTL 60초).
2. **백업**(읽기 전용):
   `pg_dump -h 127.0.0.1 -p 5433 -U <admin> -d acop_cs -Fc -n activity -f <backup>/acop_cs_activity_<ts>.dump`
   이 명령은 이번에 실제로 시험했습니다(13,487B, sha `e3b5e0b9…`, `backup_test_readonly/`). 지문 JSON 도 함께 남깁니다.
3. `python live_apply.py`(dry-run) 로 precheck 를 다시 확인합니다. 기대값: `csv_rows 6333 · existing 1 · overlap_same_id 0 · expected_total_after 6334`. 겹침이 0이 아니면 멈춥니다.
4. `python live_apply.py --execute --i-have-parent-approval` 를 실행합니다. 한 트랜잭션에서 다음을 하고, 검증 14/14 를 통과할 때만 COMMIT 합니다(실패 시 ROLLBACK).
   - 304/306/307 SQL 원문 적용. 305 는 이미 있습니다.
   - 새 3표에 `GRANT SELECT, INSERT, UPDATE, DELETE … TO guguroute_app`. 기존 activity 표 권한과 같습니다.
   - `load_places`(prune 없음)
   - `load_place_aliases`(prune 없음)
5. **예상 행수**:

   | 항목 | 예상 |
   |---|---|
   | `ac_place` | 1 → **6,334**(서울 주소 6,333, 좌표 6,333, 운영시간 원문 6,212, 휴무 원문 4,956) |
   | `ac_load_meta` | 1 → 2 |
   | `ac_place_alias` | 표 생성 + **131** |
   | `ac_live_status`·`ac_place_web_info` | 표 생성, 0행 |
   | 변경 없음 | `place_catalog` 8,435 / `catalog_hours` 1,615 / `places` / `place_aliases` 1 / `ac_indoor` 0, 시험행 md5 |

6. **사후 검증**: 대조군 스크립트 `control.py acop_cs`(읽기 전용)를 다시 실행합니다. 5개 이름이 `found`, `state_by_content(126535)` 가 행을 반환해야 합니다. 이어서 실제 API 에서 남산타워 확인 화면 검색을 한 번 확인합니다(부모).
7. **되돌리기**: `DELETE FROM activity.ac_place_alias; DELETE FROM activity.ac_place WHERE load_id=<새 load_id>; DELETE FROM activity.ac_load_meta WHERE load_id=<새>;`. 표 생성까지 되돌려야 하면 백업 dump 로 `pg_restore --clean -n activity` 를 씁니다.
8. **선택 후속**(별도 승인): `read_hours.py`(규칙) 은 시험행의 `hours_read` 도 바꾸고 판정 결과는 같습니다(12/12). `read_hours --model`·`decide_indoor` 는 모델 호출 승인이 필요합니다.

## 부모가 정할 것

- **소개글 저장 정책 충돌**: 정본 `load_places.py` 는 `overview`(3,499행)·`experience_guide`(78행)를 `ac_place` 에 적재합니다. 그런데 2026-09-28 「소개글 DB 저장 안 함」 결정과 `load_csv_facts.py`·`db_column.md` 의 「소개글은 옮기지 않는다」는 이와 상충합니다. 마이그레이션 300 주석은 2026-10-12 사용자 결정으로 「부가 참고」라고 적고 있습니다. 정본 그대로 적재할지, 두 칸을 비운 사본을 `--csv` 로 적재할지(이 경우 `ac_load_meta` sha 가 정본과 달라짐) 결정이 필요합니다. 기본안은 팀 정본 그대로이며, 이 선택은 되돌릴 수 있습니다.
- 시험행 `T05c98c6740be` 를 보존할지(기본, 기존 행 변경 0) 지울지.

## 파일(이 폴더)

- `dbc.py`: 자격증명은 출력하지 않고, cluster sysid·datadir·read-only 를 assert 합니다.
- `inv1~4.py`: 현황 집계. 결과는 `*.out`
- `csv_inv.py`/`csv_inv.json`: CSV 사본 대조
- `compare.py`/`compare_acop_cs.json`: live 대조
- `rehearse.py`
  - 1차 결과: `rehearsal_run1_with_read_hours.json`(20/21), 로그 `rehearsal_run1.log`
  - 2차 결과: `rehearsal_gugu_replay_improved_20261025_no_read_hours.json`(21/21), 로그 `rehearsal_run2_no_read_hours.log`
- `control.py`/`negative_control.json`: 대조군
- `live_apply.py`: dry-run·롤백 리허설·실행 거부 로그 포함
- `backup_test_readonly/`

## 지킨 경계

- live acop_cs 쓰기 0입니다. 모든 세션이 `default_transaction_read_only=on` 이었고, pg_dump 는 읽기 전용입니다.
- 비교 DB 영구 쓰기 0입니다. 롤백 지문 9/9 동일, `actseed_*` 행 0을 확인했습니다.
- 원본 코드 수정·git pull/reset/checkout·push 0, live API/프런트 재시작 0.
- 모델 호출: 제품 E4B 0, 유료 0. 그래서 E4B lease 는 불필요했습니다. 개발 모델 호출도 이 작업자 외에는 0입니다.
