"""대상 저장소 안에서 실행되는 진입점. 도장 본체가 subprocess 로 부른다.

대상의 설정과 import 가 도장 프로세스를 오염시키지 않도록 프로세스를 분리한다.
"""
from __future__ import annotations

import json
import sys

from acop_dojo.tracer import canonical_json, run_in_process


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: python -m acop_dojo._runner <pytest-nodeid> <out.json>", file=sys.stderr)
        return 2
    nodeid, out_path = argv[1], argv[2]
    trace = run_in_process(nodeid)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(trace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
