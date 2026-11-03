# 2026-10-26 로컬 acop_cs Activity 서울 장소 원장 적재 (사용자 승인)

- 승인: 사용자 "2번 해" (팀 정본 그대로 적재, 소개글 포함 기본안).
- 백업: `cache/scratch/activity-seoul-place-20261026-011437-9255/live-backup-0300/acop_cs_activity_schema_20261026-030822.dump` (13,487B, sha256 d5eadec6…0696, `pg_dump -Fc -n activity`).
- dry-run: csv_rows 6333 · existing 1 · overlap_same_id 0 · expected 6334 (기대 일치).
- 실행: `parent_exec/live_apply_parent.py --execute --i-have-parent-approval` (워커판에서 차단 줄 1개 제거, dbc 쓰기 허용 목록에 acop_cs 추가한 부모 사본). 한 트랜잭션: 마이그레이션 304·306·307 + 앱 권한 + 장소 6,333 + 별칭 131 → 검증 **14/14** 후 COMMIT (`live_apply_execute_acop_cs_030849.json`).
- 사후(읽기 전용 control.py): 경복궁·남산서울타워·남산타워·북촌한옥마을·국립중앙박물관 5/5 found (적재 전 not_found). 남산서울타워 운영시간은 규칙으로 못 펴서 known=false(모델 펴기 미실행).
- 불변: 기존 시험행·place_catalog·places·catalog_hours·별칭 핵심·ac_indoor.
- 되돌리기: 새 load_id 행 삭제 또는 `pg_restore --clean -n activity` 위 덤프.
- live API 재시작 불필요.
