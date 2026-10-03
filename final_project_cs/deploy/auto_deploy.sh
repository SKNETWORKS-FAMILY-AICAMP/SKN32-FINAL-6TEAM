#!/bin/sh
# 자동 반영 — 서버에서 몇 분마다(systemd 타이머) 돌며, 정한 저장소·브랜치의 새 커밋을 받아 이미지를 다시 만들고 반영한다. 실패하면 이전 이미지로 되돌린다.
#
#   설정: $BASE/autodeploy.conf  (DEPLOY_REPO · DEPLOY_BRANCH — 서버에만 둔다)
#   기록: $BASE/deploy.log · 상태: $BASE/state/
#
# ★안전장치(순서대로):
#   ① 한 번에 하나만(flock). ② 대상 커밋에 `final_project_cs/deploy/docker-compose.yml` 이 **없으면 건드리지 않는다**(배포 구성이 아직 안 합쳐진 브랜치).
#   ③ 배포에 쓰이는 폴더(app · config · prompts · scripts · deploy · frontend/apps/web · requirements)가 **바뀌지 않았으면 다시 빌드하지 않는다**(문서만 바뀐 커밋).
#   ④ 빌드 실패 → 실행 중인 것은 그대로(건드리지 않음). ⑤ 새 이미지로 기동했는데 건강하지 않으면 **이전 이미지로 되돌린다**. ⑥ 실패한 커밋은 다음 새 커밋이 올 때까지 다시 시도하지 않는다.
#   ⑦ DB 는 절대 지우지 않는다 — 마이그레이션은 재실행 안전한 앞으로 가기뿐이다. ⑧ 이전 이미지는 최근 3개만 남긴다.
# ★마이그레이션은 되돌리지 않는다(앞으로 가기뿐) — 되돌려도 이전 이미지가 새 표 구조를 견딘다는 가정이다. 파괴적인 마이그레이션은 이 방식에 맞지 않는다.
set -u

BASE="${TRIPILOT_BASE:-/root/tripilot-docker}"
STATE="$BASE/state"
LOG="$BASE/deploy.log"
REPO="$BASE/repo"
CS="final_project_cs"
mkdir -p "$STATE"

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
[ -f "$BASE/autodeploy.conf" ] || { echo "autodeploy.conf 가 없다"; exit 1; }
# shellcheck disable=SC1091
. "$BASE/autodeploy.conf"
: "${DEPLOY_REPO:?}" "${DEPLOY_BRANCH:?}"

exec 9>"$STATE/lock"
flock -n 9 || exit 0

# ── 1. 받아 오기 ─────────────────────────────────────────────
if [ ! -d "$REPO/.git" ]; then
  rm -rf "$REPO"
  git clone --quiet --depth 1 --filter=blob:none --no-checkout --branch "$DEPLOY_BRANCH" "$DEPLOY_REPO" "$REPO" 2>>"$LOG" \
    || { log "★받기 실패(clone) — 저장소 주소·브랜치를 확인한다"; exit 1; }
  git -C "$REPO" sparse-checkout set --cone "$CS/app" "$CS/config" "$CS/prompts" "$CS/scripts" "$CS/deploy" "$CS/frontend/apps/web" >>"$LOG" 2>&1
fi
git -C "$REPO" fetch --quiet --depth 1 origin "$DEPLOY_BRANCH" 2>>"$LOG" || { log "받기 실패(fetch) — 네트워크 일시 문제일 수 있다, 다음 회차에 다시"; exit 0; }
NEW="$(git -C "$REPO" rev-parse FETCH_HEAD)"
SHORT="$(printf '%s' "$NEW" | cut -c1-10)"

# ── 2. 배포할 것이 있나 ───────────────────────────────────────
if ! git -C "$REPO" cat-file -e "$NEW:$CS/deploy/docker-compose.yml" 2>/dev/null; then
  [ "$(cat "$STATE/last_skip" 2>/dev/null)" = "$SHORT" ] || { log "건너뜀 $SHORT — 이 커밋에는 $CS/deploy/ 가 없다(배포 구성이 아직 안 합쳐졌다)"; echo "$SHORT" > "$STATE/last_skip"; }
  exit 0
fi
FP="$(for p in app config prompts scripts deploy frontend/apps/web requirements.txt; do git -C "$REPO" rev-parse "$NEW:$CS/$p" 2>/dev/null || echo "-"; done | sha256sum | cut -c1-24)"
[ "$(cat "$STATE/deployed_fp" 2>/dev/null)" = "$FP" ] && exit 0                 # 배포에 쓰이는 폴더가 같다 — 다시 빌드할 이유가 없다
[ "$(cat "$STATE/bad_sha" 2>/dev/null)" = "$SHORT" ] && exit 0                   # 이 커밋은 이미 실패했다 — 새 커밋이 올 때까지 기다린다

log "시작 $SHORT ($DEPLOY_BRANCH)"
git -C "$REPO" checkout --quiet --force --detach "$NEW" >>"$LOG" 2>&1 || { log "★체크아웃 실패 $SHORT"; exit 1; }

# 저장소에 없는 파일 — 안내 문구틀(없으면 앱이 다시 만들지만 모델 호출이 다시 든다). 서버가 들고 있는 것을 빌드 맥락에 넣는다
mkdir -p "$REPO/$CS/var"
[ -f "$STATE/notice_phrasebook.json" ] || { [ -f "$BASE/src/var/notice_phrasebook.json" ] && cp "$BASE/src/var/notice_phrasebook.json" "$STATE/notice_phrasebook.json"; }
[ -f "$STATE/notice_phrasebook.json" ] && cp "$STATE/notice_phrasebook.json" "$REPO/$CS/var/notice_phrasebook.json"
[ -f "$REPO/$CS/var/notice_phrasebook.json" ] || echo '{}' > "$REPO/$CS/var/notice_phrasebook.json"

cp -p "$BASE/docker-compose.yml" "$STATE/docker-compose.prev.yml" 2>/dev/null
cp "$REPO/$CS/deploy/docker-compose.yml" "$BASE/docker-compose.yml"
cp "$REPO/$CS/deploy/auto_deploy.sh" "$STATE/auto_deploy.next.sh" 2>/dev/null          # 스크립트 갱신은 다음 회차에(실행 중인 자신을 덮지 않는다)

cd "$BASE" || exit 1
export TRIPILOT_SRC="./repo/$CS"
PREV="$(cat "$STATE/current_tag" 2>/dev/null || echo local)"

# ── 3. 빌드 — 실패해도 실행 중인 것은 그대로 ─────────────────────
if ! TRIPILOT_TAG="$SHORT" nice -n 10 docker compose build >"$STATE/build_$SHORT.log" 2>&1 </dev/null; then
  log "★빌드 실패 $SHORT — 실행 중인 것은 그대로 둔다(자세한 것: state/build_$SHORT.log)"
  echo "$SHORT" > "$STATE/bad_sha"; cp -p "$STATE/docker-compose.prev.yml" "$BASE/docker-compose.yml" 2>/dev/null
  exit 1
fi

# ── 4. 마이그레이션(앞으로 가기뿐) ───────────────────────────────
if ! TRIPILOT_TAG="$SHORT" docker compose up -d tripilot-db >>"$LOG" 2>&1 </dev/null \
   || ! TRIPILOT_TAG="$SHORT" docker compose run --rm --no-deps tripilot-api python -m app.infrastructure.db.migrate >>"$LOG" 2>&1 </dev/null; then
  log "★마이그레이션 실패 $SHORT — 실행 중인 것은 그대로 둔다"
  echo "$SHORT" > "$STATE/bad_sha"; cp -p "$STATE/docker-compose.prev.yml" "$BASE/docker-compose.yml" 2>/dev/null
  exit 1
fi

# ── 5. 반영 — 건강해질 때까지 기다린 뒤 **한 번 더 지켜본다** ─────────────
# ★`up --wait` 만으로는 모자랐다(시험 E): 건강 검사가 없는 컨테이너(일꾼)가 죽었다 살아나기를 반복해도 「실행 중」으로 보고 통과시켰다.
#   그래서 반영 뒤 SETTLE_SECONDS(기본 30초) 동안 지켜보고 ①컨테이너가 넷(DB · API · 웹 · 일꾼) 다 있고 ②모두 실행 중이며 ③**재시작이 한 번도 없어야** 성공으로 본다.
settle_ok() {
  sleep "${SETTLE_SECONDS:-30}"
  ids="$(docker compose ps -q </dev/null)"
  [ "$(printf '%s
' "$ids" | grep -c .)" -ge 4 ] || { log "  ✗ 컨테이너가 4개 미만이다"; return 1; }
  bad=0
  for c in $ids; do
    s="$(docker inspect -f '{{.Name}} {{.State.Status}} 재시작 {{.RestartCount}}' "$c" </dev/null)"
    case "$s" in *" running 재시작 0") ;; *) log "  ✗ $s"; bad=1 ;; esac
  done
  return "$bad"
}

if TRIPILOT_TAG="$SHORT" docker compose up -d --wait --wait-timeout 240 >>"$LOG" 2>&1 </dev/null && settle_ok; then
  echo "$SHORT" > "$STATE/current_tag"; echo "$FP" > "$STATE/deployed_fp"; echo "$NEW" > "$STATE/deployed_sha"
  : > "$STATE/bad_sha"
  # 새 이름으로 쓴 뒤 바꿔 끼운다(mv) — 실행 중인 이 파일의 내용을 제자리에서 덮으면 아래 줄이 깨진다
  [ -f "$STATE/auto_deploy.next.sh" ] && { cp "$STATE/auto_deploy.next.sh" "$BASE/auto_deploy.sh.new" && chmod +x "$BASE/auto_deploy.sh.new" && mv "$BASE/auto_deploy.sh.new" "$BASE/auto_deploy.sh"; }
  log "반영 완료 $SHORT (이전 $PREV)"
else
  log "★새 이미지가 건강하지 않거나 불안정하다 $SHORT — 이전($PREV)으로 되돌린다"
  echo "$SHORT" > "$STATE/bad_sha"
  cp -p "$STATE/docker-compose.prev.yml" "$BASE/docker-compose.yml" 2>/dev/null
  if TRIPILOT_TAG="$PREV" docker compose up -d --wait --wait-timeout 240 >>"$LOG" 2>&1 </dev/null; then
    log "되돌림 완료 — 서비스는 $PREV 로 돈다"
  else
    log "★★되돌림도 실패 — 사람이 봐야 한다(docker compose ps · docker logs)"
  fi
  exit 1
fi

# ── 6. 정리 — 이전 이미지는 최근 3개만 ───────────────────────────
for img in tripilot-api tripilot-web; do
  docker images "$img" --format '{{.CreatedAt}}|{{.Tag}}' </dev/null | sort -r | cut -d'|' -f2 | grep -v '^local$' | tail -n +4 \
    | while read -r tag; do docker rmi "$img:$tag" >/dev/null 2>&1 || true; done
done
exit 0
