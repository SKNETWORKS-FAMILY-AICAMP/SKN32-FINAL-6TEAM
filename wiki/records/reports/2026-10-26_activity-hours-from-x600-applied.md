# Activity 운영시간 x600 → 로컬 `acop_cs` 빈 칸 채움 — 2026-10-26 05:20 KST

## 결론

- 로컬 `acop_cs` 의 `activity.ac_place` 서울 6,333행 중 **`hours_week`·`hours_read` 를 3,681/6,333 = 58.1% 채웠습니다** (전에는 0/6,333 = 0%). 기존 값은 덮지 않았습니다(채우기 전 비어 있지 않은 행 0행).
- `hours_from_row` 기준으로 운영시간을 아는(`known`) 행은 1,531/6,333 = 24.2%(규칙으로만 읽던 상태를 재현한 값)에서 **4,227/6,333 = 66.7%** 로 늘었습니다. 대표 4곳(126508·126535·126537·129703)은 0/4 → **4/4** 입니다.
- `public.catalog_hours`(tenant `demo`, source `tour_api`)에는 로컬에 없던 3,502행을 넣었습니다(1,615 → 5,117). 원래 있던 1,615행은 바뀌지 않았습니다(행별 md5 비교).
- 충돌 381건은 **적용하지 않고 목록만** 남겼습니다. x600 `catalog_hours.hours_origin` 원문과 로컬 `usetime_text`·`restdate_text` 의 글자가 다른 경우입니다(restdate만 158, usetime만 147, 둘 다 76).
- x600 쪽은 읽기만 했습니다(`docker exec` + `psql`, `default_transaction_read_only=on`). x600 의 `activity.ac_place` 는 **0행**이었습니다. 그래서 자료원은 x600 `catalog_hours`(tenant `live`) 4,806행입니다. live API 는 재시작하지 않았습니다.

## 자료원(x600, 읽기 전용)

| 항목 | 값 |
|---|---|
| 접속 | SSH 키 `Yeon@192.168.0.8` (`BatchMode=yes`, `StrictHostKeyChecking=yes`), hostname `x600_251214` |
| 컨테이너 · DB | `tripilot-tripilot-db-1` (pgvector/pgvector:pg17, PostgreSQL 17.11) · DB `acop_cs` · 사용자 `acop` (`final_project_cs/deploy/docker-compose.yml` 의 `tripilot-db`) |
| `activity.ac_place` | 0행 (스키마는 로컬과 같은 30칸) |
| `public.catalog_hours` | 4,806행 (tenant `live`, source `tour_api`; `hours_week` 4,429 · `hours_read`/`hours_origin` 4,806) |
| 받은 파일 | `x600_catalog_hours.csv` sha256 `2fea23f2ca4095023afdee26f6a18258b32ca7880c40c012f750d92336e7048e` |
| 고객 표 | 읽지 않음 |

## 적용 규칙(`apply_hours.py`)

1. **`activity.ac_place`**: 다음 조건을 모두 만족할 때만 `hours_week`·`hours_read` 를 함께 넣습니다.
   - 로컬 행의 두 칸이 모두 NULL 입니다.
   - x600 `hours_week` 가 NULL 이 아닙니다. 365건은 x600 에도 요일표가 없어서 건너뛰었습니다. 넣으면 `hours_from_row` 의 규칙 대체 경로가 막히기 때문입니다.
   - x600 `hours_origin.usetime`/`restdate` 가 로컬 원문과 같습니다. 비교할 때 `<br>` 태그와 공백만 무시합니다.
   이 원문 조건을 둔 이유가 있습니다. `ledger.py` 계약상 미리 편 요일표는 같은 원문을 편 것이어야 하기 때문입니다.
2. **`public.catalog_hours`**: 로컬 `ac_place` 에 있는 content_id 이고, (`demo`, `tour_api`, content_id) 행이 없을 때만 `INSERT … ON CONFLICT DO NOTHING` 으로 넣었습니다. 이미 있던 925행은 x600 과 값이 같았고, 충돌은 0건이었습니다.

## 실행 순서 · 검증

| 단계 | 결과 |
|---|---|
| dry-run (`acop_cs` read-only) | 채울 행 3,681 · 넣을 행 3,502 · 충돌 381 |
| 리허설 `gugu_replay_improved_20261025` | 트랜잭션 안에서 `acop_cs` ac_place 6,333행을 복사한 뒤 적용 → 검증 **11/11 = 100%** → ROLLBACK. 롤백 뒤 ac_place 1행 · ac_load_meta 1행 · catalog_hours 1,618행·md5 그대로 |
| 백업 | `backup/acop_cs_activity_schema_20261026-052036.dump` (`pg_dump -Fc -n activity`, 1,092,353 B, sha256 `ddeddabf3792587ff25bc6468b6c636f6912bd9daac4d0a2b048647ec7398e05`) · `backup/acop_cs_catalog_hours_20261026-052036.dump` (`-t public.catalog_hours`, 65,323 B, sha256 `ebf7e458e08bb0e7676814a9bf8a1627532311a7e9228076158011bedc8a47f4`) |
| `acop_cs` 한 트랜잭션 | 검증 **11/11 = 100%** → COMMIT. systemID `7700321712607772424`, port 5433 확인 |
| 사후 `control.py` | 대표 5개 이름 found 5/5, `state_by_content(126535)` known=True (전 False) |

검증 11항목은 다음과 같습니다.
- 갱신한 행 수와 넣은 행 수가 계획과 같음
- ac_place 행 수가 같음
- ac_place 의 운영시간 외 칸 md5 가 같음
- 채워진 행이 정확히 +3,681
- catalog_hours 가 정확히 +3,502이고, 원래 있던 행의 md5 가 같음
- place_catalog·places·ac_load_meta 행 수가 같음
- 채운 행 모두 `hours_week` 가 있음

## 되돌리기

`pg_restore` 로 위 두 dump 를 되살립니다(`activity` 스키마, `public.catalog_hours`). 또는 다음 두 작업을 합니다.
- `UPDATE activity.ac_place SET hours_week=NULL, hours_read=NULL WHERE content_id = ANY(<채운 3,681건>)`
- 넣은 3,502건을 `DELETE` 합니다(id 목록은 conflicts/plan JSON 과 x600 CSV 로 다시 만들 수 있습니다).

## 남은 것

- 충돌 381건: 로컬 원문(develop `activity_total_data.csv`)과 x600 `catalog_hours` 원문이 다릅니다(수정 시점 차이). 이 행들은 지금 규칙 대체 경로로 읽힙니다. 고르려면 사용자 결정이 필요합니다.
- x600 에도 요일표가 없는 365건과, x600 에 없는 나머지 행은 여전히 `known=False` 이거나 규칙으로 읽힙니다.
- 126535 `hours_week` 의 주말 마감은 22:30 인데 원문은 「주말 10:00~23:00」 입니다. x600 이 편 값 그대로라서 고치지 않았습니다(판독 품질 문제는 별도).

## 증거 위치

`C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/x600-hours-20261026-051844/`
- `apply_hours.py` (sha256 `85e39d58…`)
- `dry_run_*.json`, `rehearse_rollback_*.json`, `execute_acop_cs_052036.json`
- `conflicts_execute_acop_cs_052036.json`
- `control-after.log`, `post_known.log`, `pre_known_sim.log`
