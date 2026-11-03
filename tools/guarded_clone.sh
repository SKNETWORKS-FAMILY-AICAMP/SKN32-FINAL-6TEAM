#!/usr/bin/env bash
# Guarded clone: reuse an idle registered clone, else reserve space -> git clone -> record measured size.
# Never deletes. Usage: tools/guarded_clone.sh <source> <dest-under-managed-root> <owner> <purpose> [expected-bytes]
# Prints the clone path to use on the last line of stdout. Exit 3 = refused by the guard.
set -u
here="$(cd "$(dirname "$0")" && { pwd -W 2>/dev/null || pwd; })"  # native path: MSYS path conversion may be off
guard() { python "$here/disk_guard.py" "$@"; }
[ $# -ge 4 ] || { echo "usage: $0 source dest owner purpose [expected-bytes]" >&2; exit 2; }
src=$1 dest=$2 owner=$3 purpose=$4 expected=${5:-}

out=$(guard acquire --source "$src" --owner "$owner" --purpose "$purpose"); rc=$?
if [ $rc -eq 0 ]; then
  echo "$out"
  python -c "import json,sys; print(json.load(sys.stdin)['dest'])" <<<"$out"
  exit 0
elif [ $rc -ne 3 ]; then
  echo "$out" >&2; exit $rc  # config/usage error: stop, never fall through to cloning
fi
args=(reserve --source "$src" --dest "$dest" --owner "$owner" --purpose "$purpose")
[ -n "$expected" ] && args+=(--expected-bytes "$expected")
guard "${args[@]}" || exit $?
if git clone "$src" "$dest"; then
  guard complete --dest "$dest" || exit $?
  echo "$dest"
else
  rc=$?
  if [ -e "$dest" ]; then
    echo "git clone failed (exit $rc); partial destination kept for inspection, reservation left pending: $dest" >&2
  else
    guard abandon --dest "$dest" --owner "$owner" >&2
  fi
  exit $rc
fi
