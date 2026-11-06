from pathlib import Path

root = Path(r'C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/wt/final_project_cs/app/domains/travel_ops/components/intake')


def edit(name, pairs):
    p = root / name
    raw = p.read_bytes()
    crlf = b'\r\n' in raw
    s = raw.decode('utf-8').replace('\r\n', '\n')
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:80], s.count(old))
        s = s.replace(old, new)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print(name, 'ok', 'crlf' if crlf else 'lf')


edit('agent_read.py', [
    ('    date_invalid: str | None = None          # 모델 날짜가 달력에 없는 날이었다 — 그 날짜 인용(원문). 날짜 해석이 첫날로 채우지 않고 「모름」으로 둔다(`dates.resolve_dates`)\n',
     '    date_invalid: str | None = None          # 모델 날짜가 달력에 없는 날이었다 — 그 날짜 인용(원문). 날짜 해석이 첫날로 채우지 않고 「모름」으로 둔다(`dates.resolve_dates`)\n'
     '    year_quote: str | None = None            # 연도를 적은 날(explicit_year)의 모델 연도 인용 — 원문에서 확인한 것만. 모델 날짜의 해와 맞는지 `pipeline._year_written` 이 본다\n'),
    ('        when, relative, unverified, invalid = _grounded_date(it, dq, lines, dropped)\n',
     '        when, relative, unverified, invalid = _grounded_date(it, dq, lines, dropped)\n'
     '        # `[2026-11-06 병합 — A13 과 date_form]` 연도 근거는 모델이 인용한 연도 조각이다(머리줄 「2025년 가을 여행」처럼 날짜 인용 밖일 수 있다)\n'
     '        yq = it.get("year_quote") if when and ISO.match(when) and not relative and isinstance(it.get("year_quote"), str) else None\n'),
    ('            date_guessed=relative, year_unverified=unverified, date_invalid=invalid, start=start,',
     '            date_guessed=relative, year_unverified=unverified, date_invalid=invalid, year_quote=yq, start=start,'),
])
edit('pipeline.py', [
    ('        elif it.date and it.date_quote is not None and not _year_written(it.date[:4], it.date_quote.text):\n'
     '            # `[2026-10-28 전수검사 A13]` 인용(「10월 30일」)에 해가 없는데 모델이 해를 붙였다 — 값은 두고 확인 표시만 붙인다\n',
     '        elif it.date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", it.date) and it.date_quote is not None and not _year_written(it.date[:4], it.year_quote or it.date_quote.text):\n'
     '            # `[2026-10-28 전수검사 A13]` 인용(「10월 30일」)에 해가 없는데 모델이 해를 붙였다 — 값은 두고 확인 표시만 붙인다.\n'
     '            #   `[2026-11-06 병합]` 연도를 적은 날(explicit_year)은 모델이 원문에서 인용한 연도 조각(`year_quote`)과 해를 맞춰 본다 — 머리줄의 해도 근거다.\n'
     '            #   연도 없는 날(`--MM-DD`)은 날짜 해석이 이미 `year_filled`(확인 필요)로 채우므로 여기서 다시 보지 않는다\n'),
])
