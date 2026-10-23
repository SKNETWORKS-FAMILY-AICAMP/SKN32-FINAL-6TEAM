#!/bin/sh
# 오라클 서버 관리자웹앱의 비공개 설정(control/.env.admin)을 고치고 관리자웹앱만 다시 띄운다. `[2026-10-15]`
#   sudo ./admin_env.sh operator --id 이름   운영자 계정 넣기 · 비밀번호 바꾸기(비밀번호는 직접 입력)
#   sudo ./admin_env.sh remove --id 이름     운영자 계정 빼기
#   sudo ./admin_env.sh keys                 고객 API 열쇠 넣기(처음 한 번)
#   sudo ./admin_env.sh list                 계정 id · 열쇠 유무만 보기
# 자동 배포·질의 검사와 같은 잠금을 잡고 다시 띄운다 — 그 회차가 돌고 있으면 끝날 때까지 기다린다.
set -eu
CONTROL=$(cd "$(dirname "$0")" && pwd)
BASE=$(dirname "$CONTROL")
TAG=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["current"][:12])' "$BASE/state.json")
if ! docker image inspect "tripilot-arm-admin:$TAG" >/dev/null 2>&1; then
  echo "관리자웹앱 이미지가 아직 없다(tripilot-arm-admin:$TAG) — 자동 배포가 만든 뒤 다시 한다" >&2
  exit 2
fi
touch "$CONTROL/.env.admin"
chmod 600 "$CONTROL/.env.admin"
dc() { IMAGE_TAG="$TAG" docker compose --env-file "$CONTROL/.env" -f "$CONTROL/compose.yml" "$@"; }
dc run --rm --no-deps -v "$CONTROL:/control" -e PYTHONPATH=/srv admin python /control/admin_env.py "$@"
case "${1:-}" in
  list) exit 0 ;;
esac
echo "관리자웹앱을 다시 띄운다(배포·질의 검사 회차가 돌고 있으면 끝날 때까지 최대 15분 기다린다)"
flock -w 900 "$BASE/deploy.lock" sh -c "IMAGE_TAG='$TAG' docker compose --env-file '$CONTROL/.env' -f '$CONTROL/compose.yml' up -d --no-deps --force-recreate --wait --wait-timeout 180 admin"
echo "끝 — 관리자웹앱이 새 설정으로 다시 떴다"
