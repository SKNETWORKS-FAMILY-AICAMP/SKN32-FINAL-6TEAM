"""행의 값·필드를 유지하면서 반복되는 문자열의 메모리를 공유한다."""
from __future__ import annotations

import json
from sys import intern


def load_shared_row(raw: str) -> dict:
    """JSON 행의 반복 키·문자열을 공유한다. 숫자·불리언·빈 값은 그대로 둔다."""
    return json.loads(raw, object_hook=_shared_strings)


def _shared_strings(row: dict) -> dict:
    return {intern(key): intern(value) if isinstance(value, str) else value
            for key, value in row.items()}
