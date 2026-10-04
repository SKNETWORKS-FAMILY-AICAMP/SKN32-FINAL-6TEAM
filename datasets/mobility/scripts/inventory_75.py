# -*- coding: utf-8 -*-
"""75번 방 ① 인벤토리 — processed\\mobility 전 파일 + raw\\mobility 크기표.

읽기만 한다(정본 무변경). 산출은 이 스크립트 옆 `inventory_75.json` · `inventory_75_summary.md`.

실행(노트북 PowerShell · 저장소 루트 · 표준 라이브러리만 · 산출은 datasets/mobility/processed/ 에 — git 밖):
    python datasets/mobility/scripts/inventory_75.py --root <DATA_DIR>\\travel\\processed\\mobility --raw <DATA_DIR>\\travel\\raw\\mobility

옵션:
    --root  C:\\final_project\\data\\travel\\processed\\mobility   (기본)
    --raw   C:\\final_project\\data\\travel\\raw\\mobility         (기본 · 크기표만)
    --no-sha   sha256 생략(빠르게 볼 때)
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import sys
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parent / "processed"          # 산출 자리(git 밖 · .gitignore 가 막음)
SKIP_DIRS = {"__pycache__"}
BIG_NO_SHA = 300 * 1024 * 1024          # 이보다 크면 sha 생략(gh 그래프 캐시)
DISTINCT_CAP = 60                        # 열별 고유값 세기 상한(넘으면 "60+")
EXAMPLE_MAXLEN = 600


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _open_text(p: Path):
    if p.suffix == ".gz":
        return gzip.open(p, "rt", encoding="utf-8")
    return open(p, encoding="utf-8")


def _trim(v):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= EXAMPLE_MAXLEN else s[:EXAMPLE_MAXLEN] + " …"


def scan_jsonl(p: Path):
    rows = 0
    blank = 0
    bad = 0
    keys = OrderedDict()   # key → {"n": present&non-null, "null": present&null, "types": set, "distinct": set|None}
    first = None
    meta_rows = []
    with _open_text(p) as f:
        for raw in f:
            s = raw.strip()
            if not s:
                blank += 1
                continue
            try:
                r = json.loads(s)
            except ValueError:
                bad += 1
                continue
            if isinstance(r, dict) and r.get("_meta"):
                meta_rows.append(r)
                continue
            rows += 1
            if first is None:
                first = r
            if not isinstance(r, dict):
                continue
            for k, v in r.items():
                d = keys.get(k)
                if d is None:
                    d = keys[k] = {"n": 0, "null": 0, "types": set(), "distinct": set()}
                if v is None:
                    d["null"] += 1
                    continue
                d["n"] += 1
                d["types"].add(type(v).__name__)
                if d["distinct"] is not None:
                    try:
                        d["distinct"].add(v if isinstance(v, (str, int, float, bool)) else json.dumps(v, ensure_ascii=False, sort_keys=True))
                    except TypeError:
                        d["distinct"] = None
                    if d["distinct"] is not None and len(d["distinct"]) > DISTINCT_CAP:
                        d["distinct"] = None
    cols = []
    for k, d in keys.items():
        dist = d["distinct"]
        cols.append({
            "key": k,
            "present_nonnull": d["n"],
            "null": d["null"],
            "types": sorted(d["types"]),
            "distinct": (len(dist) if dist is not None else f"{DISTINCT_CAP}+"),
            "values": (sorted(map(str, dist))[:20] if dist is not None else None),
        })
    return {"kind": "jsonl", "rows": rows, "blank_lines": blank, "bad_lines": bad,
            "meta_rows": [_trim(m) for m in meta_rows[:3]],
            "columns": cols, "example": _trim(first) if first is not None else None}


def describe_json_value(v, depth=0):
    if isinstance(v, dict):
        out = {"type": "dict", "len": len(v)}
        if depth < 2:
            sub = OrderedDict()
            for i, (k, x) in enumerate(v.items()):
                if i >= 12:
                    sub["…"] = f"(+{len(v) - 12} keys)"
                    break
                sub[k] = describe_json_value(x, depth + 1)
            out["keys"] = sub
        return out
    if isinstance(v, list):
        out = {"type": "list", "len": len(v)}
        if v and depth < 2:
            out["item0"] = describe_json_value(v[0], depth + 1)
        return out
    return {"type": type(v).__name__, "example": _trim(v)}


def scan_json(p: Path):
    with _open_text(p) as f:
        doc = json.load(f)
    d = {"kind": "json", "shape": describe_json_value(doc)}
    if isinstance(doc, dict):
        # 큰 표 칸(stations · entries · pairs · exits · lines …)의 첫 항목을 예시로
        for k, v in doc.items():
            if isinstance(v, dict) and len(v) > 20:
                k0 = next(iter(v))
                d.setdefault("table_examples", {})[k] = {"count": len(v), "first_key": k0, "first": _trim(v[k0])}
            elif isinstance(v, list) and len(v) > 20:
                d.setdefault("table_examples", {})[k] = {"count": len(v), "first": _trim(v[0])}
    return d


def scan_csv(p: Path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(p, encoding=enc, newline="") as f:
                rd = csv.reader(f)
                header = next(rd, [])
                first = next(rd, None)
                n = 1 if first is not None else 0
                for _ in rd:
                    n += 1
            return {"kind": "csv", "encoding": enc, "rows": n, "columns": header,
                    "example": dict(zip(header, first)) if first else None}
        except UnicodeDecodeError:
            continue
    return {"kind": "csv", "error": "decode failed"}


def scan_file(p: Path, do_sha: bool):
    st = p.stat()
    rec = {"path": None, "size": st.st_size,
           "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
           "sha256": None}
    name = p.name.lower()
    try:
        if do_sha and st.st_size <= BIG_NO_SHA:
            rec["sha256"] = sha256(p)
        if name.endswith(".jsonl") or name.endswith(".jsonl.gz"):
            rec.update(scan_jsonl(p))
        elif name.endswith(".json"):
            rec.update(scan_json(p))
        elif name.endswith(".geojson"):
            rec["kind"] = "geojson"
        elif name.endswith(".csv"):
            rec.update(scan_csv(p))
        elif name.endswith(".md"):
            rec["kind"] = "md"
        else:
            rec["kind"] = "other"
    except Exception as e:      # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def walk(root: Path, do_sha: bool, deep: bool):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        rel_dir = Path(dp).relative_to(root)
        # gh 그래프 캐시·로그는 크기만(재빌드 대상 · C)
        shallow = (not deep) or str(rel_dir).replace("\\", "/").startswith("graph/gh")
        for fn in sorted(fns):
            p = Path(dp) / fn
            rel = str(Path(rel_dir) / fn).replace("\\", "/") if str(rel_dir) != "." else fn
            if shallow:
                st = p.stat()
                rec = {"path": rel, "size": st.st_size, "kind": "size-only",
                       "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}
            else:
                t0 = time.time()
                rec = scan_file(p, do_sha)
                rec["path"] = rel
                rec["scan_sec"] = round(time.time() - t0, 1)
                print(f"  {rel}  {st_fmt(rec['size'])}  {rec.get('kind')}  rows={rec.get('rows', '')}  {rec['scan_sec']}s")
            out.append(rec)
    return out


def st_fmt(n):
    return f"{n / 1048576:,.1f} MB" if n >= 1048576 else f"{n / 1024:,.1f} KB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"C:\final_project\data\travel\processed\mobility")
    ap.add_argument("--raw", default=r"C:\final_project\data\travel\raw\mobility")
    ap.add_argument("--no-sha", action="store_true")
    a = ap.parse_args()
    root, raw = Path(a.root), Path(a.raw)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[75] processed 인벤토리: {root}")
    proc = walk(root, not a.no_sha, deep=True)
    print(f"[75] raw 크기표: {raw}")
    rawl = walk(raw, False, deep=False) if raw.exists() else []
    doc = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "device": os.environ.get("COMPUTERNAME"),
           "root": str(root), "raw_root": str(raw),
           "processed_total_bytes": sum(r["size"] for r in proc),
           "raw_total_bytes": sum(r["size"] for r in rawl),
           "processed": proc, "raw": rawl}
    (OUT_DIR / "inventory_75.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    # 요약 md
    lines = [f"# 75 인벤토리 요약 — {doc['generated_at']} · {doc['device']}", "",
             f"processed 합계 {st_fmt(doc['processed_total_bytes'])} · raw 합계 {st_fmt(doc['raw_total_bytes'])}", "",
             "| 파일 | 크기 | 종류 | 행수 | 열 |", "|---|---|---|---|---|"]
    for r in proc:
        cols = r.get("columns")
        if isinstance(cols, list) and cols and isinstance(cols[0], dict):
            cols = ", ".join(c["key"] for c in cols)
        elif isinstance(cols, list):
            cols = ", ".join(cols)
        lines.append(f"| `{r['path']}` | {st_fmt(r['size'])} | {r.get('kind')} | {r.get('rows', '')} | {cols or ''} |")
    (OUT_DIR / "inventory_75_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[75] 끝 — {OUT_DIR / 'inventory_75.json'} · {OUT_DIR / 'inventory_75_summary.md'}")


if __name__ == "__main__":
    main()
