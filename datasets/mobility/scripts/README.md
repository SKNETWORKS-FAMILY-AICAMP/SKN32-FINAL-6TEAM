# datasets/mobility/scripts

| 파일 | 하는 일 |
|---|---|
| `inventory_75.py` | 정본 `DATA_DIR\travel\processed\mobility` 전 파일 인벤토리(열·행·sha256) → `../processed/inventory_75.json`(git 밖) |
| `reduce_75.py` | 정본 → `../processed/mobility/` 줄인 판(시간표 8열 · 나머지 그대로 · 행 삭제 0) + `MANIFEST_git_v1.json` + 크기표 |

**원자료 수집·가공 본체는 저장소 루트 `mobility_scripts/collect/`** (`build_timetable_v1.py` · `fill_timetable_dest_v1.py` · `build_bus_all_v1.py` · `build_bus_seg_profile_v1.py` · `station_coords_build.py` · `congestion_build.py` 등 — 파일별 대응은 `docs/mobility/DATA_IN_GIT_v1.md` §2). 여기로 옮기는 건 재생성 경로 합의 뒤(팀장 #57~62 구조 정리 · 발표 뒤).
