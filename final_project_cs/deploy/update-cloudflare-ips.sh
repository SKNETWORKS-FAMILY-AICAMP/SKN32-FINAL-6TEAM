#!/bin/bash
# Oracle (run as root, e.g. by cron weekly + once by hand): rebuild /etc/caddy/conf.d/05-cloudflare-only.caddy from Cloudflare's
# published IP ranges. Sites that `import cloudflare_only` answer 403 to anything that is not Cloudflare (or loopback), so the
# Cloudflare Access login on /private/ cannot be skipped by calling the server's address directly.
# NOT part of the CI/CD deploy (it runs as root): install by hand:  sudo install -m 755 -o root -g root update-cloudflare-ips.sh /usr/local/bin/
set -euo pipefail
OUT=/etc/caddy/conf.d/05-cloudflare-only.caddy
TMP=$(mktemp)
trap 'rm -f "$TMP" "$TMP.new"' EXIT
v4=$(curl -fsS -m 20 https://www.cloudflare.com/ips-v4)
v6=$(curl -fsS -m 20 https://www.cloudflare.com/ips-v6)
cidr='^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$|^[0-9a-fA-F:]+/[0-9]{1,3}$'
ranges=$(printf '%s\n%s\n' "$v4" "$v6" | grep -E "$cidr" || true)
n=$(printf '%s\n' "$ranges" | grep -c . || true)
[ "$n" -ge 10 ] || { echo "refusing to update: only $n ranges parsed"; exit 1; }
{
  echo "# generated $(date -u +%FT%TZ) by update-cloudflare-ips.sh ($n ranges) - do not edit by hand"
  echo "(cloudflare_only) {"
  printf '\t@not_cloudflare not remote_ip 127.0.0.1 ::1'
  printf '%s\n' "$ranges" | while read -r r; do printf ' %s' "$r"; done
  echo
  echo '	respond @not_cloudflare "Forbidden" 403'
  echo "}"
} > "$TMP.new"
# Compare the ranges only: the first line carries a timestamp and would make every run look changed.
old_ranges=$( [ -f "$OUT" ] && grep -v '^# generated' "$OUT" || true )
new_ranges=$(grep -v '^# generated' "$TMP.new")
if [ "$old_ranges" = "$new_ranges" ]; then echo "cloudflare ranges unchanged"; exit 0; fi
BAK=""
[ -f "$OUT" ] && { BAK=$(mktemp); cp -p "$OUT" "$BAK"; }
install -m 644 "$TMP.new" "$OUT"
if caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
  # On this host Caddy 2.6.2 panics inside `systemctl reload` (seen 2026-10-12 at 04:17 and 06:45): the process dies after
  # reload reports success. So the new ranges are applied with a restart, and success is reported only if caddy is still up.
  systemctl restart caddy
  sleep 3
  systemctl is-active --quiet caddy || { echo "caddy still down after restart" >&2; exit 1; }
  echo "updated ($n ranges), caddy restarted"
else
  echo "new range file invalid - restoring previous" >&2
  [ -n "$BAK" ] && install -m 644 "$BAK" "$OUT" || rm -f "$OUT"
  exit 1
fi
[ -n "$BAK" ] && rm -f "$BAK" || true
