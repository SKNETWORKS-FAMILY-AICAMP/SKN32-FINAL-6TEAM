#!/bin/sh
# 서버에서 한 번(처음) 또는 갱신할 때마다 — 이 디렉터리(`docker-compose.yml` 이 있는 곳)에서 실행한다.
#   ① 이미지 빌드  ② DB 컨테이너 기동  ③ 마이그레이션(표 구조)  ④ DB 가 비어 있으면 기준 데이터 적재  ⑤ 전체 기동
# ★재실행해도 안전하다 — 마이그레이션은 재실행 안전이고, 기준 데이터는 장소 목록이 **비어 있을 때만** 넣는다(있는 DB 를 덮지 않는다).
set -eu
cd "$(dirname "$0")"
[ -f .env ] || { echo "★.env 가 없다 — deploy/README.md 의 「서버 .env」를 먼저 만든다"; exit 1; }
[ -f .env.apikeys ] || { echo "★.env.apikeys 가 없다 — make_server_env.py 가 .env 와 함께 만든다(비어 있어도 파일은 있어야 한다)"; exit 1; }

GUARD="$(pwd)/migration_safe_deploy.py"
SAFETY_STATE="$(pwd)/state/manual-safety-$(date +%s)"
mkdir -p state
exec 9>state/lock
flock -n 9 || { echo "다른 cs 프로젝트 배포가 진행 중입니다"; exit 1; }
HAS_BASELINE=0
if [ -n "$(docker compose ps -a -q tripilot-api)" ]; then
  python3 "$GUARD" snapshot --state-dir "$SAFETY_STATE"
  HAS_BASELINE=1
fi
timeout --foreground --kill-after=15s 600 docker compose build
python3 "$GUARD" check --state-dir "$SAFETY_STATE"
timeout --foreground --kill-after=15s 120 docker compose up -d --no-recreate tripilot-db
python3 "$GUARD" migrate --state-dir "$SAFETY_STATE" --timeout 180

rows="$(docker compose exec -T tripilot-db psql -U acop -d acop_cs -tAc 'select count(*) from place_catalog')"
if [ "$rows" = "0" ]; then
  if [ -f reference_data.sql.gz ]; then
    echo "기준 데이터 적재 중…"
    gunzip -c reference_data.sql.gz | docker compose exec -T tripilot-db psql -U acop -d acop_cs -v ON_ERROR_STOP=1 -q
  else
    echo "★장소 목록이 비어 있고 reference_data.sql.gz 도 없다 — 추천 품질이 낮다"
  fi
else
  echo "기준 데이터는 이미 있다(장소 목록 ${rows}행) — 건너뜀"
fi

if [ "$HAS_BASELINE" = 1 ]; then
  python3 "$GUARD" rollout --state-dir "$SAFETY_STATE" --timeout 240
else
  # 최초 설치에는 복구할 이전 앱이 없다. 실패를 알리고 자동 재시도하지 않는다.
  timeout --foreground --kill-after=15s 240 docker compose up -d --wait --wait-timeout 210
fi
docker compose ps
