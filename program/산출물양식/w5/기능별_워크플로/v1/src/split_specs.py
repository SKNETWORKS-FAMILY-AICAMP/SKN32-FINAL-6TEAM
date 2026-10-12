# -*- coding: utf-8 -*-
"""코덱스가 낸 명세 묶음(out1~3.md)을 기능별 파일(../spec/<id>.md)로 나누고 YAML 흐름이 읽히는지 본다."""
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent / "spec"


def blocks(text):
    parts = re.split(r"(?m)^## (?=[FA]\d\d )", text)
    for p in parts[1:]:
        fid = p.split()[0]
        yield fid, "## " + p.rstrip() + "\n"


def flow_of(md):
    tail = md.split("### 그림용 흐름", 1)
    m = re.search(r"```yaml\n(.*?)```", tail[1] if len(tail) > 1 else md, re.S)
    if not m:
        raise ValueError("yaml 블록 없음")
    body = re.sub(r'((?:title|label): )([^"\'{}\[\],\n]*\?)(?=\s*[,}])', lambda x: f'{x.group(1)}"{x.group(2).strip()}"', m.group(1))
    return yaml.safe_load(body)


def main(paths):
    SPEC.mkdir(parents=True, exist_ok=True)
    for path in paths:
        for fid, md in blocks(Path(path).read_text(encoding="utf-8")):
            (SPEC / f"{fid}.md").write_text(md, encoding="utf-8")
            try:
                fl = flow_of(md)
                ids = {n["id"] for n in fl["nodes"]}
                bad = [e for e in fl["edges"] if e["from"] not in ids or e["to"] not in ids]
                kinds = {}
                for n in fl["nodes"]:
                    kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
                print(fid, "nodes", len(fl["nodes"]), "edges", len(fl["edges"]), kinds, "끊긴 선", len(bad))
            except Exception as exc:  # noqa: BLE001
                print(fid, "YAML 오류", exc)


if __name__ == "__main__":
    main(sys.argv[1:])
