#!/bin/sh
# 구글 드라이브 공유 폴더를 오라클 ARM 서버의 자료 폴더로 맞춘다 — 드라이브의 폴더·파일 경로를 그대로 둔다.
#   드라이브 <공유 폴더>/a/b.csv  →  $DATASET_DIR/a/b.csv
#
#   설정: /etc/tripilot-arm-dataset-sync.env (DEPLOY_BASE · GDRIVE_FOLDER_ID — 폴더 ID 는 서버에만 둔다)
#   로그인 정보: $DEPLOY_BASE/control/rclone-gdrive.conf (읽기 전용 구글 로그인, 사람이 gdrive_login.ps1 로 한 번 넣는다)
#   상태: $DEPLOY_BASE/dataset-sync.json · 기록: journalctl -u tripilot-arm-dataset-sync.service
#
# ★안전장치
#   ① 한 번에 하나만(flock). 앱 배포 잠금과는 따로다 — 앱 컨테이너는 이 폴더를 읽지 않는다.
#   ② 로그인 정보가 없으면 아무것도 안 하고 「로그인 대기」만 남긴다.
#   ③ 드라이브가 비어 보이는데 서버에 파일이 있으면 맞추지 않는다(로그인 만료·권한 회수로 목록이 비는 경우).
#   ④ 받은 뒤 남는 공간이 MIN_FREE_GIB(기본 12GiB) 미만이면 받지 않는다 — 앱 자동 배포가 빌드에 10GiB 를 요구한다.
#   ⑤ 드라이브에서 지우거나 바꾼 파일의 옛 판은 지우지 않고 $DEPLOY_BASE/_backup/datasets-sync/<시각>/ 으로 옮긴다.
set -eu

: "${DEPLOY_BASE:?}" "${GDRIVE_FOLDER_ID:?}"
CONF="${RCLONE_CONF:-$DEPLOY_BASE/control/rclone-gdrive.conf}"
DEST="${DATASET_DIR:-$DEPLOY_BASE/datasets}"
BACKUP_ROOT="$DEPLOY_BASE/_backup/datasets-sync"
STATE="$DEPLOY_BASE/dataset-sync.json"
MIN_FREE_GIB="${MIN_FREE_GIB:-12}"
REMOTE="tripilot_gdrive:"

save() {  # save <결과> <설명>
  python3 - "$STATE" "$1" "$2" <<'PY'
import json, sys, time
path, result, note = sys.argv[1:4]
temp = path + ".tmp"
with open(temp, "w", encoding="utf-8") as f:
    json.dump({"result": result, "note": note, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, f, ensure_ascii=False, indent=2)
import os; os.replace(temp, path)
PY
  echo "$1: $2"
}

exec 9>"$DEPLOY_BASE/dataset-sync.lock"
flock -n 9 || { echo "이전 회차 실행 중"; exit 0; }

if [ ! -s "$CONF" ]; then
  save waiting_login "구글 로그인 정보가 없다 — PC 에서 deploy/arm/gdrive_login.ps1 을 한 번 실행한다"
  exit 0
fi

set -- --config "$CONF" --drive-root-folder-id "$GDRIVE_FOLDER_ID" --drive-skip-gdocs

# 드라이브 쪽 크기·개수 — 실패하면(로그인 만료·네트워크) 이번 회차는 건너뛴다
ERR="$(mktemp)"
trap 'rm -f "$ERR"' EXIT
if ! SIZE_JSON="$(rclone size --json "$@" "$REMOTE" 2>"$ERR")"; then
  save remote_error "드라이브 목록을 못 읽었다: $(tail -1 "$ERR")"
  exit 1
fi
REMOTE_COUNT="$(printf '%s' "$SIZE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["count"])')"
REMOTE_BYTES="$(printf '%s' "$SIZE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["bytes"])')"

mkdir -p "$DEST"
LOCAL_COUNT="$(find "$DEST" -type f | wc -l)"
LOCAL_BYTES="$(du -sb "$DEST" | cut -f1)"

if [ "$REMOTE_COUNT" -eq 0 ] && [ "$LOCAL_COUNT" -gt 0 ]; then
  save skipped_empty_remote "드라이브가 비어 보인다(서버 파일 $LOCAL_COUNT 개) — 지우지 않고 건너뛴다"
  exit 0
fi

FREE_BYTES="$(df -B1 --output=avail "$DEPLOY_BASE" | tail -1 | tr -d ' ')"
NEED_BYTES=$(( REMOTE_BYTES > LOCAL_BYTES ? REMOTE_BYTES - LOCAL_BYTES : 0 ))
MIN_FREE_BYTES=$(( MIN_FREE_GIB * 1024 * 1024 * 1024 ))
if [ $(( FREE_BYTES - NEED_BYTES )) -lt "$MIN_FREE_BYTES" ]; then
  save skipped_disk "받으면 남는 공간이 ${MIN_FREE_GIB}GiB 미만이다(남은 $(( FREE_BYTES / 1073741824 ))GiB · 더 필요 $(( NEED_BYTES / 1073741824 ))GiB)"
  exit 0
fi

BACKUP_DIR="$BACKUP_ROOT/$(date +%Y-%m-%d_%H%M%S)"
if rclone sync "$@" "$REMOTE" "$DEST" \
     --backup-dir "$BACKUP_DIR" --create-empty-src-dirs \
     --transfers 2 --checkers 4 --retries 3 --low-level-retries 10 \
     --stats-one-line --stats 60s -v 2>&1; then
  save ok "드라이브 파일 $REMOTE_COUNT 개 · $(( REMOTE_BYTES / 1048576 ))MiB 와 같아졌다"
else
  save sync_error "맞추기 실패 — journalctl -u tripilot-arm-dataset-sync.service 를 본다"
  exit 1
fi
