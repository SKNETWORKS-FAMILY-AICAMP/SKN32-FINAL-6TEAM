#!/bin/sh
# 운영 웹앱만 별도 반영한다. 고객 컨테이너와 공개 프록시는 변경하지 않는다.
set -eu
BASE="${TRIPILOT_BASE:-/root/tripilot-docker}"
cd "$BASE"
SRC="${TRIPILOT_SRC:-./repo/final_project_cs}"
export TRIPILOT_SRC="$SRC"
export TRIPILOT_TAG="${TRIPILOT_TAG:-$(cat state/current_tag)}"
OVERRIDE="$SRC/deploy/docker-compose.admin.yml"
compose_admin() {
  docker compose -f docker-compose.yml -f "$OVERRIDE" --profile operations "$@"
}
# API 이미지를 먼저 만든 고객 배포가 끝난 뒤 실행한다.
docker image inspect "tripilot-api:$TRIPILOT_TAG" >/dev/null
compose_admin build tripilot-admin
compose_admin up -d --no-deps --wait --wait-timeout 180 tripilot-admin
printf '%s\n' "$TRIPILOT_TAG" > state/admin_tag
