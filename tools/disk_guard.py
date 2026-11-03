"""Project disk-growth guard: free-space preflight, reusable clone ledger and owned-copy inventory.

It never deletes, moves, resets or checks out anything. It refuses (fail closed) when:
- the configuration file is missing/invalid (no built-in threshold, no silent fallback),
- free space after the declared write would drop below `min_free_bytes`,
- free space is below `target_free_bytes` and an idle registered clone of the same source exists
  (reuse it with `acquire` instead of making another copy),
- the expected size of a write is unknown (no measured clone of the source and no --expected-bytes).

Configuration: --config, else env TRIPILOT_DISK_GUARD_CONFIG, else tools/disk_guard.json next to this file.

Commands (all print JSON; exit 0 = allowed/ok, 3 = refused, 2 = usage/config error):
  check     --path P --need-bytes N              preflight for any large write (exports, engines, copies)
  reserve   --source S --dest D --owner O --purpose T [--expected-bytes N]
            records a pending reservation for a new clone after the checks above
  complete  --dest D                            measures the finished clone and marks it leased by its owner
  acquire   --source S --owner O --purpose T    leases an idle registered clone of S (reuse instead of cloning)
  release   --dest D --owner O                  marks a clone idle so another worker can reuse it
  abandon   --dest D --owner O                  drops a pending reservation that never produced a clone
  inventory                                     ledger entries plus unregistered top-level folders under watch roots
Use tools/guarded_clone.sh to run reserve -> git clone -> complete in one step.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFUSED, USAGE = 3, 2
REQUIRED_KEYS = {"min_free_bytes", "target_free_bytes", "ledger_path", "managed_roots", "below_target_policy"}
POLICIES = {"reuse_first", "deny_new"}


class GuardError(Exception):
    def __init__(self, code: int, message: str, **detail):
        super().__init__(message)
        self.code, self.message, self.detail = code, message, detail


# ---------- configuration ----------
def config_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("TRIPILOT_DISK_GUARD_CONFIG")
    return Path(env) if env else HERE / "disk_guard.json"


def load_config(path: Path) -> dict:
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GuardError(USAGE, f"disk guard config not found: {path}; set an explicit threshold, no default is assumed")
    except (OSError, ValueError) as exc:
        raise GuardError(USAGE, f"disk guard config unreadable: {path}: {exc}")
    missing = sorted(REQUIRED_KEYS - cfg.keys())
    if missing:
        raise GuardError(USAGE, f"disk guard config missing keys {missing}: {path}")
    for key in ("min_free_bytes", "target_free_bytes"):
        if not isinstance(cfg[key], int) or isinstance(cfg[key], bool) or cfg[key] <= 0:
            raise GuardError(USAGE, f"{key} must be a positive integer byte count")
    if cfg["target_free_bytes"] < cfg["min_free_bytes"]:
        raise GuardError(USAGE, "target_free_bytes must be >= min_free_bytes")
    if cfg["below_target_policy"] not in POLICIES:
        raise GuardError(USAGE, f"below_target_policy must be one of {sorted(POLICIES)}")
    if not isinstance(cfg["managed_roots"], list) or not all(isinstance(r, str) for r in cfg["managed_roots"]):
        raise GuardError(USAGE, "managed_roots must be a list of paths")
    base = path.resolve().parent
    cfg["ledger_path"] = str((base / cfg["ledger_path"]).resolve())
    cfg["_config"] = str(path.resolve())
    return cfg


# ---------- measurement ----------
def free_bytes(path: str) -> int:
    probe = Path(path)
    while not probe.exists():  # destination may not exist yet; measure its nearest existing parent
        if probe.parent == probe:
            raise GuardError(USAGE, f"no existing parent for {path}")
        probe = probe.parent
    return shutil.disk_usage(probe).free


def tree_bytes(path: str) -> int:
    """Logical size without following reparse points; unreadable entries raise (no silent undercount)."""
    total, stack = 0, [path]
    while stack:
        with os.scandir(stack.pop()) as it:
            for entry in it:
                st = entry.stat(follow_symlinks=False)
                if getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    continue
                if stat.S_ISDIR(st.st_mode):
                    stack.append(entry.path)
                else:
                    total += st.st_size
    return total


def norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def drive_key(path: str) -> str:
    return os.path.splitdrive(norm(path))[0] or "/"


# ---------- ledger (atomic, lock-file serialised for concurrent workers) ----------
@contextlib.contextmanager
def locked_ledger(cfg: dict, timeout_s: float = 30.0):
    ledger = Path(cfg["ledger_path"])
    ledger.parent.mkdir(parents=True, exist_ok=True)
    lock = ledger.with_suffix(ledger.suffix + ".lock")
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}".encode())
            os.close(fd)
            break
        except (FileExistsError, PermissionError):  # Windows reports a lock file pending deletion as access denied
            if time.monotonic() > deadline:
                raise GuardError(USAGE, f"ledger lock busy: {lock}; inspect it, never delete it while a worker runs")
            time.sleep(0.2)
    try:
        data = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {"entries": []}
        yield data
        tmp = ledger.with_suffix(ledger.suffix + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, ledger)
    finally:
        os.remove(lock)


def find(data: dict, dest: str) -> dict | None:
    return next((e for e in data["entries"] if norm(e["dest"]) == norm(dest)), None)


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------- decisions ----------
def pending_bytes(data: dict, path: str) -> int:
    key = drive_key(path)
    return sum(e.get("expected_bytes", 0) for e in data["entries"] if e["state"] == "pending" and drive_key(e["dest"]) == key)


def evaluate(cfg: dict, path: str, need: int, reserved: int) -> dict:
    free = free_bytes(path)
    after = free - reserved - need
    result = {"path": path, "free_bytes": free, "pending_reserved_bytes": reserved, "need_bytes": need,
              "free_after_bytes": after, "min_free_bytes": cfg["min_free_bytes"],
              "target_free_bytes": cfg["target_free_bytes"], "below_target": free < cfg["target_free_bytes"],
              "config": cfg["_config"]}
    if after < cfg["min_free_bytes"]:
        raise GuardError(REFUSED, "refused: write would drop free space below min_free_bytes", **result)
    return result


def cmd_check(cfg: dict, a) -> dict:
    if a.need_bytes is None or a.need_bytes < 0:
        raise GuardError(USAGE, "--need-bytes is required; an unknown write size is not assumed")
    with locked_ledger(cfg) as data:
        return {"allowed": True, **evaluate(cfg, a.path, a.need_bytes, pending_bytes(data, a.path))}


def under_managed_root(cfg: dict, dest: str) -> bool:
    d = norm(dest)
    return any(d.startswith(norm(r).rstrip("\\/") + os.sep) for r in cfg["managed_roots"])


def cmd_reserve(cfg: dict, a) -> dict:
    if not under_managed_root(cfg, a.dest):
        raise GuardError(REFUSED, "refused: clone destination is outside configured managed_roots", dest=a.dest,
                         managed_roots=cfg["managed_roots"])
    if os.path.exists(a.dest):
        raise GuardError(REFUSED, "refused: destination already exists; acquire or inspect it instead", dest=a.dest)
    with locked_ledger(cfg) as data:
        same = [e for e in data["entries"] if norm(e["source"]) == norm(a.source)]
        idle = [e for e in same if e["state"] == "idle"]
        measured = [e["measured_bytes"] for e in same if e.get("measured_bytes")]
        expected = a.expected_bytes if a.expected_bytes is not None else (max(measured) if measured else None)
        if expected is None:
            raise GuardError(REFUSED, "refused: clone size unknown; pass --expected-bytes measured from the source",
                             source=a.source)
        result = evaluate(cfg, a.dest, expected, pending_bytes(data, a.dest))
        if result["below_target"]:
            if cfg["below_target_policy"] == "deny_new":
                raise GuardError(REFUSED, "refused: free space below target_free_bytes and policy is deny_new", **result)
            if idle:
                raise GuardError(REFUSED, "refused: below target and an idle clone of this source exists; use acquire",
                                 idle=[e["dest"] for e in idle], **result)
        data["entries"].append({"dest": a.dest, "source": a.source, "owner": a.owner, "purpose": a.purpose,
                                "state": "pending", "expected_bytes": expected, "reserved_at": now()})
        return {"allowed": True, "reserved": a.dest, **result}


def cmd_complete(cfg: dict, a) -> dict:
    with locked_ledger(cfg) as data:
        entry = find(data, a.dest)
        if not entry or entry["state"] != "pending":
            raise GuardError(REFUSED, "no pending reservation for this destination", dest=a.dest)
        if not os.path.isdir(a.dest):
            raise GuardError(REFUSED, "destination missing; use abandon if the clone failed", dest=a.dest)
        entry.update(state="leased", lessee=entry["owner"], measured_bytes=tree_bytes(a.dest), completed_at=now())
        entry.pop("expected_bytes", None)
        return {"ok": True, "entry": entry}


def cmd_acquire(cfg: dict, a) -> dict:
    with locked_ledger(cfg) as data:
        for entry in data["entries"]:
            if norm(entry["source"]) == norm(a.source) and entry["state"] == "idle" and os.path.isdir(entry["dest"]):
                entry.update(state="leased", lessee=a.owner, purpose=a.purpose, leased_at=now())
                return {"ok": True, "dest": entry["dest"],
                        "note": "reused clone: verify `git status --porcelain` is empty before switching refs"}
        raise GuardError(REFUSED, "no idle registered clone for this source", source=a.source)


def cmd_release(cfg: dict, a) -> dict:
    with locked_ledger(cfg) as data:
        entry = find(data, a.dest)
        if not entry or entry["state"] != "leased" or entry.get("lessee") != a.owner:
            raise GuardError(REFUSED, "clone is not leased by this owner", dest=a.dest)
        entry.update(state="idle", lessee=None, released_at=now(), measured_bytes=tree_bytes(a.dest))
        return {"ok": True, "entry": entry}


def cmd_abandon(cfg: dict, a) -> dict:
    with locked_ledger(cfg) as data:
        entry = find(data, a.dest)
        if not entry or entry["state"] != "pending" or entry["owner"] != a.owner:
            raise GuardError(REFUSED, "no pending reservation by this owner", dest=a.dest)
        if os.path.exists(a.dest):
            raise GuardError(REFUSED, "destination exists; inspect it (complete or report), not abandoned", dest=a.dest)
        data["entries"].remove(entry)
        return {"ok": True, "abandoned": a.dest}


def cmd_inventory(cfg: dict, a) -> dict:
    with locked_ledger(cfg) as data:
        entries = list(data["entries"])
    known = {norm(e["dest"]) for e in entries}
    unregistered = []
    for root in cfg["managed_roots"]:
        if os.path.isdir(root):
            for entry in os.scandir(root):
                if entry.is_dir(follow_symlinks=False) and norm(entry.path) not in known:
                    unregistered.append(entry.path)
    totals: dict[str, int] = {}
    for e in entries:
        totals[e["state"]] = totals.get(e["state"], 0) + e.get("measured_bytes", e.get("expected_bytes", 0))
    return {"entries": entries, "bytes_by_state": totals, "unregistered_dirs": unregistered,
            "free_bytes": {r: free_bytes(r) for r in cfg["managed_roots"]},
            "min_free_bytes": cfg["min_free_bytes"], "target_free_bytes": cfg["target_free_bytes"]}


COMMANDS = {"check": cmd_check, "reserve": cmd_reserve, "complete": cmd_complete, "acquire": cmd_acquire,
            "release": cmd_release, "abandon": cmd_abandon, "inventory": cmd_inventory}


def require_free(path: str, need_bytes: int, config: str | None = None) -> dict:
    """Library preflight for scripts that write large artifacts. Raises GuardError when refused."""
    cfg = load_config(config_path(config))
    with locked_ledger(cfg) as data:
        return evaluate(cfg, path, need_bytes, pending_bytes(data, path))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="project disk growth guard (never deletes)")
    p.add_argument("--config")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("check"); s.add_argument("--path", required=True); s.add_argument("--need-bytes", type=int)
    s = sub.add_parser("reserve")
    for k in ("--source", "--dest", "--owner", "--purpose"):
        s.add_argument(k, required=True)
    s.add_argument("--expected-bytes", type=int)
    s = sub.add_parser("complete"); s.add_argument("--dest", required=True)
    s = sub.add_parser("acquire")
    for k in ("--source", "--owner", "--purpose"):
        s.add_argument(k, required=True)
    for name in ("release", "abandon"):
        s = sub.add_parser(name); s.add_argument("--dest", required=True); s.add_argument("--owner", required=True)
    sub.add_parser("inventory")
    return p


def main(argv: list[str] | None = None) -> int:
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(encoding="utf8")
    args = parser().parse_args(argv)
    try:
        cfg = load_config(config_path(args.config))
        print(json.dumps(COMMANDS[args.command](cfg, args), ensure_ascii=False, indent=1))
        return 0
    except GuardError as exc:
        print(json.dumps({"allowed": False, "error": exc.message, **exc.detail}, ensure_ascii=False, indent=1))
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
