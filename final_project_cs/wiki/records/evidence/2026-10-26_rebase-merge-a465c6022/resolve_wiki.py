"""Resolve the 4 wiki conflicts of merging 07dcebe35 onto a465c6022, per file, keeping both intents.
Line endings are kept as found (works on bytes split by b'\n')."""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def blocks(data: bytes):
    """Yield ('text', lines) / ('conflict', ours_lines, theirs_lines) keeping raw line bytes (with \r)."""
    lines = data.split(b"\n")
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith(b"<<<<<<< "):
            j = i + 1
            ours = []
            while not lines[j].startswith(b"======="):
                ours.append(lines[j]); j += 1
            j += 1
            theirs = []
            while not lines[j].startswith(b">>>>>>> "):
                theirs.append(lines[j]); j += 1
            out.append(("conflict", ours, theirs))
            i = j + 1
        else:
            out.append(("text", [lines[i]]))
            i += 1
    return out


def resolve(path: str, fn):
    p = ROOT / path
    data = p.read_bytes()
    parts = blocks(data)
    n = sum(1 for b in parts if b[0] == "conflict")
    assert n == 1, (path, n)
    res = []
    for b in parts:
        res.extend(b[1] if b[0] == "text" else fn(b[1], b[2]))
    new = b"\n".join(res)
    assert b"<<<<<<<" not in new and b">>>>>>>" not in new and b"\n=======\r" not in new and b"\n=======\n" not in new
    p.write_bytes(new)
    print(path, "resolved; CR count", data.count(b"\r"), "->", new.count(b"\r"))


eol = b""  # the four blobs are LF (checked: CRLF count 0); line items already carry no \r


def trip_chat(ours, theirs):
    # HEAD added new 10-25/10-26 sections at the end; ours appended two past-date bullets after the 10-20 section.
    # Keep HEAD's sections, then our bullets under their own dated heading (they are not about near search).
    body = [l for l in theirs]
    while body and body[-1].strip() == b"":
        body.pop()
    return ours + [eol, "## 2026-10-26 채팅 수정의 지난 날짜 · 지난 일정 (과거 날짜 가드레일 확장 · 삭제만)".encode() + eol, eol] + body


def fcs_index(ours, theirs):
    # HEAD side empty; theirs = our four 2026-10-26 entries + a 2026-10-25 pair that already exists below in HEAD.
    cut = next(i for i, l in enumerate(theirs) if l.startswith("2026-10-25".encode()))
    assert all(t in ROOT.joinpath("final_project_cs/wiki/index.md").read_bytes() for t in theirs[cut:] if t.strip())
    return theirs[:cut]


def log_md(ours, theirs):
    return theirs + ours  # our later 10-26 entries first, then HEAD's 10-26 example-loader entry


def root_index(ours, theirs):
    # HEAD kept only the 'role-manager 21개' 10-25 pair (its own merge chose it); ours kept both variants.
    cut = next(i for i, l in enumerate(theirs) if l.startswith("2026-10-25".encode()))
    return theirs[:cut] + ours


resolve("final_project_cs/wiki/external/trip-chat-context.md", trip_chat)
resolve("final_project_cs/wiki/index.md", fcs_index)
resolve("final_project_cs/wiki/log.md", log_md)
resolve("wiki/index.md", root_index)
