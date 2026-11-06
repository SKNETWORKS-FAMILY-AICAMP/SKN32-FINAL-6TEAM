from pathlib import Path

t = Path(r'C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/wt/final_project_cs/tests/unit/travel')


def edit(name, pairs):
    p = t / name
    raw = p.read_bytes()
    crlf = b'\r\n' in raw
    s = raw.decode('utf-8').replace('\r\n', '\n')
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:80], s.count(old))
        s = s.replace(old, new)
    if crlf:
        s = s.replace('\n', '\r\n')
    p.write_bytes(s.encode('utf-8'))
    print(name, 'ok')


MERGE_NOTE = ("# `[2026-11-06 병합]` 날짜는 모델 판단(2026-10-26 사용자 확정) — 답 항목에 연도 인용(`year_quote`) · 날짜 형식(`date_form`)이 있어야 한다\n"
              "#   (형식 칸 없는 옛 답은 `agent_read._grounded_date` 가 날짜를 버린다). 시험 자료를 그 계약으로 맞췄다 — 단언은 그대로다.\n")

edit('test_date_generation.py', [
    ("    raw = item(date=expected, date_quote=text, time_quote=text)\n",
     "    form = dict(year_quote='2030', date_form='explicit_year') if text.startswith('2030') else dict(year_quote=None, date_form='relative')\n"
     "    raw = item(date=expected, date_quote=text, time_quote=text, **form)\n"),
    ("    rows = [item(date_quote=text.splitlines()[0],time_quote=text.splitlines()[0]),\n"
     "            item(place_quote='경복궁스테이',date='2030-01-03',date_quote=text.splitlines()[1],start='10:00',end='11:00',time_quote=text.splitlines()[1],kind='lodging')]\n",
     "    rows = [item(date_quote=text.splitlines()[0],time_quote=text.splitlines()[0],year_quote='2030'),\n"
     "            item(place_quote='경복궁스테이',date='2030-01-03',date_quote=text.splitlines()[1],start='10:00',end='11:00',time_quote=text.splitlines()[1],kind='lodging',\n"
     "                 year_quote='2030')]\n"),
    ("def item(**changes):\n"
     "    value = dict(place_quote='덕수궁', day=1, date='2030-01-02', date_quote=TEXT,\n",
     MERGE_NOTE + "def item(**changes):\n"
     "    value = dict(place_quote='덕수궁', day=1, date_quote=TEXT, year_quote='2030년', date_form='explicit_year', date='2030-01-02',\n"),
])
edit('test_intake_date_quote_grammar.py', [
    ('    base = {"place_quote": "합성궁", "day": 1, "date": None, "date_quote": None, "start": "10:00", "end": "11:00",\n',
     '    ' + MERGE_NOTE.replace('\n#', '\n    #').rstrip('\n') + '\n'
     '    base = {"place_quote": "합성궁", "day": 1, "date": None, "date_quote": None, "year_quote": None, "date_form": None,\n'
     '            "start": "10:00", "end": "11:00",\n'),
    ('@pytest.mark.parametrize("item", [{"date": None, "date_quote": None}, {"date": "2031-03-04", "date_quote": "2031년 3월 4일"}])\n',
     '@pytest.mark.parametrize("item", [{"date": None, "date_quote": None},\n'
     '                                  {"date": "2031-03-04", "date_quote": "2031년 3월 4일", "year_quote": "2031년", "date_form": "explicit_year"}])\n'),
])
