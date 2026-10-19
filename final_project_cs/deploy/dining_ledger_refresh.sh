#!/bin/sh
# x600 서버 — 팀 구글 드라이브 `datasets/dining` 을 받아, 바뀌었으면 cs 프로젝트 DB 의 요식 원장을 다시 채운다. `[2026-10-19 사용자 지시]`
#
#   sh dining_ledger_refresh.sh            받기 → 바뀌었으면 백업 → 시험 적재(되돌림) → 반영
#   sh dining_ledger_refresh.sh --dry-run  받기 → 시험 적재까지만(DB 는 그대로)
#   sh dining_ledger_refresh.sh --force    드라이브가 안 바뀌었어도 다시 채운다
#
#   설정(서버에만 둔다): $BASE/control/gdrive_datasets_folder_id — 드라이브 `datasets` 폴더 ID 한 줄(오라클 ARM 서버와 같은 폴더)
#   자료: $BASE/datasets/dining · 받은 상태: $BASE/datasets/dining-fetch.json · 적재 상태: $BASE/state/dining-ledger.json
#   백업: $BASE/_backup/dining-ledger/<시각>.sql.gz (적재 직전 `dining` 스키마 전체 — 되돌릴 때 이것을 넣는다)
#
# ★왜. x600 의 요식 원장은 10-03 에 개발 DB 를 한 번 떠서 넣은 뒤(09-30 판, 1,228곳) 다시 채우는 길이 없었다.
# ★안전장치
#   ① 한 번에 하나(flock). ② 드라이브 목록이 비거나 필수 원본이 없으면 받지 않는다(`dining_drive_fetch.py`).
#   ③ 적재 직전 `dining` 스키마를 통째로 백업한다. ④ 적재는 한 트랜잭션 — 실패 · 확인 실패면 통째로 되돌아간다(`dining_ledger_load.py`).
#   ⑤ 지금 떠 있는 api 와 **같은 이미지**로 돈다(태그를 떠 있는 컨테이너에서 읽는다 — 이름표 없는 `local` 옛 이미지로 돌지 않게).
set -eu

BASE="${TRIPILOT_BASE:-/root/tripilot-docker}"
CS="${TRIPILOT_CS:-$BASE/repo/final_project_cs}"   # 스크립트 자리 — 배포 저장소 사본(자동 배포가 갱신)
DATA="$BASE/datasets/dining"
STATE_FILE="$BASE/state/dining-ledger.json"
BACKUP_DIR="$BASE/_backup/dining-ledger"
DB_CONTAINER="${DB_CONTAINER:-tripilot-tripilot-db-1}"
API_CONTAINER="${API_CONTAINER:-tripilot-tripilot-api-1}"
MODE="apply"
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) MODE="dry-run" ;;
    --force) FORCE=1 ;;
    *) echo "모르는 인자: $arg"; exit 2 ;;
  esac
done

mkdir -p "$BASE/state" "$BACKUP_DIR"
exec 9>"$BASE/state/dining-ledger.lock"
flock -n 9 || { echo "이전 회차 실행 중"; exit 0; }

python3 "$CS/deploy/dining_drive_fetch.py" --folder-id-file "$BASE/control/gdrive_datasets_folder_id" --dest "$DATA" || exit 1

fetched="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$BASE/datasets/dining-fetch.json")"
loaded="$(python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get("sha256",""))
except FileNotFoundError: print("")' "$STATE_FILE")"
if [ "$fetched" = "$loaded" ] && [ "$FORCE" -eq 0 ] && [ "$MODE" = "apply" ]; then
  echo "드라이브 자료가 지난 적재와 같다 — 그대로 둔다"; exit 0
fi

TAG="$(docker inspect -f '{{.Config.Image}}' "$API_CONTAINER" | sed 's/.*://')"
[ -n "$TAG" ] && [ "$TAG" != "local" ] || { echo "떠 있는 api 이미지 태그를 못 읽었다 — 멈춘다"; exit 1; }

run_load() {  # run_load [--apply]
  (cd "$BASE" && TRIPILOT_TAG="$TAG" docker compose run --rm --no-deps -T \
      -v "$DATA:/data/dining:ro" -v "$CS/deploy/dining_ledger_load.py:/work/dining_ledger_load.py:ro" \
      tripilot-api python /work/dining_ledger_load.py --data /data/dining "$@")
}

# 시험 적재 — 끝까지 넣어 보고 되돌린다. 여기서 걸리면 반영하지 않는다
run_load || { echo "시험 적재 실패 — 반영하지 않는다"; exit 1; }
[ "$MODE" = "dry-run" ] && exit 0

U="$(docker exec "$DB_CONTAINER" printenv POSTGRES_USER)"
D="$(docker exec "$DB_CONTAINER" printenv POSTGRES_DB)"
STAMP="$(date +%Y-%m-%d_%H%M%S)"
docker exec "$DB_CONTAINER" pg_dump -U "$U" -d "$D" -n dining | gzip > "$BACKUP_DIR/$STAMP.sql.gz"
[ -s "$BACKUP_DIR/$STAMP.sql.gz" ] || { echo "백업이 비었다 — 반영하지 않는다"; exit 1; }

run_load --apply || { echo "반영 실패 — 트랜잭션이 되돌아가 쓰던 원장이 그대로다(백업 $BACKUP_DIR/$STAMP.sql.gz)"; exit 1; }
python3 - "$STATE_FILE" "$fetched" "$TAG" "$BACKUP_DIR/$STAMP.sql.gz" <<'PY'
import json, os, sys, time
path, sha, tag, backup = sys.argv[1:5]
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump({"sha256": sha, "image_tag": tag, "backup": backup, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, f, ensure_ascii=False, indent=2)
os.replace(tmp, path)
PY
echo "요식 원장을 드라이브 판으로 다시 채웠다(백업 $BACKUP_DIR/$STAMP.sql.gz)"
