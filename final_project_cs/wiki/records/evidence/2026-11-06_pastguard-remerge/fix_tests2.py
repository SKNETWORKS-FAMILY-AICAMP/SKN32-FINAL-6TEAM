from pathlib import Path

base = Path(r'C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/wt/final_project_cs')


def edit(rel, pairs):
    p = base / rel
    raw = p.read_bytes()
    crlf = b'\r\n' in raw
    s = raw.decode('utf-8').replace('\r\n', '\n')
    for old, new in pairs:
        assert s.count(old) == 1, (rel, old[:80], s.count(old))
        s = s.replace(old, new)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print(rel, 'ok')


edit('app/domains/travel_ops/components/intake/pipeline.py', [
    ('    return bool(re.search(rf"(?<!\\d){year}(?!\\d)", quote) or re.search(rf"(?<!\\d){year[2:]}\\s*년", quote))\n',
     '    ★`[2026-11-06 병합]` 줄인 해에 붙는 따옴표(「\'26.3.5」 — 모델 연도 인용 `\'26`)도 적힌 해다 — 날짜 형식 규칙(agent_read SYSTEM)의 예와 같다\n'
     '    return bool(re.search(rf"(?<!\\d){year}(?!\\d)", quote) or re.search(rf"(?<!\\d){year[2:]}\\s*년", quote)\n'
     '                or re.search(rf"[\'’]{year[2:]}(?!\\d)", quote))\n'),
])
edit('tests/unit/travel/test_llm_date_form.py', [
    ('def test_schema_asks_the_model_for_the_date_form_and_the_year_quote():\n'
     '    item = agent_read.SCHEMA["properties"]["items"]["items"]\n'
     '    assert {"date_form", "year_quote"} <= set(item["required"])\n'
     '    assert item["properties"]["date_form"]["enum"] == ["explicit_year", "relative", "yearless", None]\n'
     '    order = list(item["properties"])\n'
     '    # 인용을 먼저 적고 → 판단 → 값(작은 모델이 근거를 보고 고르게)\n'
     '    assert order.index("date_quote") < order.index("year_quote") < order.index("date_form") < order.index("date")\n',
     'def test_schema_asks_the_model_for_the_date_form_and_the_year_quote():\n'
     '    # `[2026-11-06 병합]` 항목 스키마는 I05 의 두 갈래(날짜 없음 · 날짜+인용, `agent_read._dated_items`)다 — 두 갈래 모두 같은 칸 순서를 지킨다\n'
     '    branches = agent_read.SCHEMA["properties"]["items"]["items"]["anyOf"]\n'
     '    assert len(branches) == 2\n'
     '    for item in branches:\n'
     '        assert {"date_form", "year_quote"} <= set(item["required"])\n'
     '        assert item["properties"]["date_form"]["enum"] == ["explicit_year", "relative", "yearless", None]\n'
     '        order = list(item["properties"])\n'
     '        # 인용을 먼저 적고 → 판단 → 값(작은 모델이 근거를 보고 고르게)\n'
     '        assert order.index("date_quote") < order.index("year_quote") < order.index("date_form") < order.index("date")\n'),
])
