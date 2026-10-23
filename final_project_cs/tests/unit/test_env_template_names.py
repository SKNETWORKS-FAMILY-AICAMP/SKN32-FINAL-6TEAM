# -*- coding: utf-8 -*-
"""`.env.apikeys.example` 의 `ACOP_` 이름은 전부 설정(`Settings`)이 아는 이름이어야 한다.

★설정은 모르는 이름을 **받지 않고 기동을 거부한다**(`extra="forbid"`) — 사용자가 템플릿에 없는 이름으로 키를 넣으면(2026-10-05
`ACOP_SEOUL_METRO_API_KEY`) 앱이 안 뜬다. 템플릿이 실제 설정과 어긋나면 여기서 먼저 걸린다.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.core.settings import Settings

TEMPLATE = Path(__file__).resolve().parents[2] / ".env.apikeys.example"


def test_every_acop_name_in_the_apikeys_template_is_a_known_setting():
    names = re.findall(r"^\s*ACOP_([A-Z0-9_]+)\s*=", TEMPLATE.read_text(encoding="utf-8"), flags=re.M)
    assert names, "템플릿에서 이름을 못 읽었다"
    known = {name.lower() for name in Settings.model_fields}
    unknown = sorted(n for n in names if n.lower() not in known)
    assert not unknown, f"설정이 모르는 이름(넣으면 기동 거부): {unknown}"
