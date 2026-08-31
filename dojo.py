"""A-COP 도장 실행기.

`python -m acop_dojo` 는 패키지 폴더 안에서만 되고, 팀원이 워크스페이스 루트에서
바로 쓰기 어렵다. 설치 없이 어디서든 돌아가게 하는 얇은 진입점이다.

    python dojo.py doctor
    python dojo.py learn 0

정식으로 설치해 `acop-dojo` 명령을 쓰려면 `pip install -e acop_dojo` 를 한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "acop_dojo"))

from acop_dojo.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
