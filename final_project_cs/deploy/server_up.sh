#!/bin/sh
# 서버에서 한 번(처음) 또는 갱신할 때마다 — 이 디렉터리(`docker-compose.yml` 이 있는 곳)에서 실행한다.
#   ① 이미지 빌드  ② DB 컨테이너 기동  ③ 마이그레이션(표 구조)  ④ DB 가 비어 있으면 기준 데이터 적재  ⑤ 전체 기동
# ★재실행해도 안전하다 — 마이그레이션은 재실행 안전이고, 기준 데이터는 장소 목록이 **비어 있을 때만** 넣는다(있는 DB 를 덮지 않는다).
set -eu
cd "$(dirname "$0")"
[ -f .env ] || { echo "★.env 가 없다 — deploy/README.md 의 「서버 .env」를 먼저 만든다"; exit 1; }

docker compose build
docker compose up -d tripilot-db
docker compose run --rm --no-deps tripilot-api python -m app.infrastructure.db.migrate

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

docker compose up -d
docker compose ps
