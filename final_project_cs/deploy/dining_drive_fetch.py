# -*- coding: utf-8 -*-
"""팀 구글 드라이브의 `dining` 폴더를 서버 자료 폴더로 받는다 — 로그인 없이(링크 공개 폴더). `[2026-10-19 사용자 지시]`

    python3 dining_drive_fetch.py --folder-id-file <ID 파일> --dest <자료 폴더>/dining [--backup-root <백업 폴더>]

★왜. x600 서버의 요식 원장은 10-03 에 개발 DB 를 한 번 떠서 넣은 판(09-30 갱신, 1,228곳)에서 멈춰 있었다.
  요식팀은 자료를 팀 드라이브 `datasets/dining` 에 올린다 — 서버가 거기서 직접 받게 한다.
★로그인 정보를 쓰지 않는다. 드라이브 폴더가 「링크가 있는 사람 보기」로 공유돼 있어 공개 목록(`embeddedfolderview`)과
  공개 내려받기 주소로 받는다. 공유를 끊으면 목록이 비고, 그때는 **아무것도 바꾸지 않는다**(아래 안전장치).
★폴더 ID 는 저장소에 적지 않는다 — 서버에만 둔 파일에서 읽는다.
★표준 라이브러리만 쓴다(서버 호스트 python3 로 돈다).

받는 것 · 안 받는 것
    받는다  `dining/processed/**`(적재 원본 · 검수 시트) · `dining/raw/*인허가*.csv`(이름 찾기용 인허가 식당)
    안 받는다 `processed/_build/`(적재 SQL — 서버가 원본으로 다시 만든다) · `processed/similarity/`(학습 결과, 적재와 무관)

안전장치
    ① 목록이 비거나 필수 원본(관광공사 목록 · 소개정보 · 공휴일)이 없으면 받지 않고 끝낸다(공유 해제 · 목록 실패).
    ② 새 판은 임시 폴더에 다 받은 뒤 한 번에 바꾼다 — 받다가 끊겨도 쓰던 폴더는 그대로다.
    ③ 바뀐 파일이 있으면 옛 폴더를 `--backup-root/<시각>/` 으로 옮긴다(지우지 않는다).
    ④ 받은 파일 수 · 지문(sha256)을 `--dest/../dining-fetch.json` 에 남긴다 — 적재기가 「바뀌었나」를 이것으로 본다.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

LIST_URL = "https://drive.google.com/embeddedfolderview?id={id}"
DOWNLOAD_URL = "https://drive.usercontent.google.com/download?id={id}&export=download&confirm=t"
#: 적재에 꼭 있어야 하는 원본 — 하나라도 없으면 받은 판을 쓰지 않는다
REQUIRED = ("processed/tourapi_서울_음식점_목록.json", "processed/tourapi_음식점_소개정보.json",
            "processed/holidays_2026_2027.json")
SKIP_DIRS = {"processed/_build", "processed/similarity"}
ENTRY = re.compile(r'<div class="flip-entry" id="entry-([^"]+)".*?<a href="([^"]+)".*?flip-entry-title">(.*?)</div>', re.S)


def _get(url: str, *, timeout: int = 60, tries: int = 4) -> bytes:
    """드라이브가 가끔 500 · 429 를 준다 — 잠깐 쉬고 다시 묻는다(2 · 4 · 8초)."""
    req = urllib.request.Request(url, headers={"User-Agent": "guguroute-dining-fetch/1"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as got:
                return got.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def list_folder(folder_id: str) -> list[tuple[str, bool, str]]:
    """(id, 폴더인가, 이름). 공개가 아니면 로그인 화면이 와서 빈 목록이 된다."""
    page = _get(LIST_URL.format(id=urllib.parse.quote(folder_id))).decode("utf-8", "replace")
    return [(eid, "/folders/" in href, html.unescape(title).strip()) for eid, href, title in ENTRY.findall(page)]


def walk(folder_id: str, prefix: str = "") -> list[tuple[str, str]]:
    """(상대 경로, 파일 id) 목록 — 받을 것만."""
    out: list[tuple[str, str]] = []
    for eid, is_dir, name in list_folder(folder_id):
        rel = f"{prefix}{name}"
        if is_dir:
            if rel in SKIP_DIRS:
                continue
            out += walk(eid, rel + "/")
        elif rel.startswith("processed/") or (rel.startswith("raw/") and "인허가" in name and name.endswith(".csv")):
            out.append((rel, eid))
    return out


def find_child(folder_id: str, name: str) -> str | None:
    for eid, is_dir, title in list_folder(folder_id):
        if is_dir and title == name:
            return eid
    return None


def download(file_id: str, path: str) -> None:
    data = _get(DOWNLOAD_URL.format(id=urllib.parse.quote(file_id)), timeout=300)
    if data[:15].lower().startswith(b"<!doctype html") and b"accounts.google.com" in data[:20000]:
        raise RuntimeError(f"로그인 화면이 왔다(공개 아님): {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def digest(root: str) -> tuple[str, int]:
    h, n = hashlib.sha256(), 0
    for base, _, files in sorted(os.walk(root)):
        for name in sorted(files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if rel.startswith("processed/_build/"):
                continue                     # 적재기가 다시 만드는 생성물
            h.update(rel.encode("utf-8") + b"\0")
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            n += 1
    return h.hexdigest(), n


def save_state(path: str, **values) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({**values, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print(json.dumps(values, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--folder-id-file", required=True, help="드라이브 `datasets` 폴더 ID 를 담은 파일(서버에만 둔다)")
    ap.add_argument("--dest", required=True, help="받을 자리 — 예 /root/tripilot-docker/datasets/dining")
    ap.add_argument("--backup-root", default=None, help="바뀐 옛 폴더를 옮길 곳(기본 <dest>/../_backup/dining-fetch)")
    args = ap.parse_args()

    dest = os.path.abspath(args.dest)
    state = os.path.join(os.path.dirname(dest), "dining-fetch.json")
    backup_root = args.backup_root or os.path.join(os.path.dirname(dest), "_backup", "dining-fetch")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(args.folder_id_file, encoding="utf-8") as f:
        root_id = f.read().strip()

    try:
        dining_id = find_child(root_id, "dining")
        files = walk(dining_id) if dining_id else []
    except Exception as exc:            # noqa: BLE001 — 네트워크 · 드라이브 응답 문제. 쓰던 폴더를 그대로 둔다
        save_state(state, result="list_error", note=f"드라이브 목록을 못 읽었다: {type(exc).__name__}: {exc}"[:300])
        return 1
    names = {rel for rel, _ in files}
    missing = [r for r in REQUIRED if r not in names]
    if not files or missing:
        save_state(state, result="skipped_incomplete",
                   note=f"드라이브 dining 목록이 비었거나 필수 원본이 없다 — 바꾸지 않는다(없음: {', '.join(missing) or '전부'})")
        return 1

    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)
    stage = tempfile.mkdtemp(prefix=".dining-fetch-", dir=parent)
    try:
        for rel, fid in files:
            download(fid, os.path.join(stage, *rel.split("/")))
        new_hash, new_count = digest(stage)
        old_hash = digest(dest)[0] if os.path.isdir(dest) else None
        if old_hash == new_hash:
            save_state(state, result="unchanged", files=new_count, sha256=new_hash)
            return 0
        if os.path.isdir(dest):
            os.makedirs(backup_root, exist_ok=True)
            moved = os.path.join(backup_root, time.strftime("%Y-%m-%d_%H%M%S"))
            os.replace(dest, moved)
        os.replace(stage, dest)
        stage = ""
        save_state(state, result="changed", files=new_count, sha256=new_hash, previous_sha256=old_hash)
        return 0
    except Exception as exc:            # noqa: BLE001
        save_state(state, result="download_error", note=f"{type(exc).__name__}: {exc}"[:300])
        return 1
    finally:
        if stage and os.path.isdir(stage):
            shutil.rmtree(stage, ignore_errors=True)   # 다 받지 못한 임시 폴더(쓰던 폴더가 아니다)


if __name__ == "__main__":
    sys.exit(main())
