from pathlib import Path

p = Path(r'C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/wt/final_project_cs/app/domains/travel_ops/components/intake/agent_read.py')
s = p.read_text(encoding='utf-8')
BS = ''


def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:90], s.count(old))
    s = s.replace(old, new)


rep('Message: 모레 11시 낙성대공원 산책하고 택시로 샤로수길 가서 1시에 점심, 비 오면',
    'Message: 모레 11시 낙성대공원 산책하고 택시로 샤로수길 가서 1시에 점심(예약 완료), 비 오면')
for kind in ('activity', 'dining'):
    old = f'{BS}"kind{BS}":{BS}"{kind}{BS}"}}}}'
    new = f'{BS}"kind{BS}":{BS}"{kind}{BS}",{BS}"locked{BS}":null,{BS}"locked_quote{BS}":null}}}}'
    rep(old, new)
tail = '"trip' + BS + '":{{' + BS + '"party_size' + BS + '":null,' + BS + '"days' + BS + '":null,' + BS + '"nights' + BS + '":null}}}}"""\n'
rep(tail, tail + '\n\nPROMPT_VERSION = "intake.agent_read.v4-date-form"   # v2: 명시 고정 locked/locked_quote · v3: 예약만 있는 항목 예시(locked null) · 예약 말 인용 금지 · '
    'v4(2026-11-06 병합): 날짜 인용 → year_quote → date_form → date 순서\n'
    'PROMPT_HASH = hashlib.sha256(SYSTEM.encode()).hexdigest()\n')
# I06 locked grounding + our _grounded_date: the HEAD 3-line "drop date without quote" is now inside _grounded_date
rep('''        if when and dq is None:
            dropped["date"] += 1
            when = None
''', '')
rep('''    dropped = {"item": 0, "time": 0, "date": 0, "date_form": 0, "date_year": 0, "date_mismatch": 0, "move": 0, "move_end": 0, "condition": 0, "preference": 0,
               "piece": 0, "gap": 0}''',
    '''    dropped = {"item": 0, "time": 0, "date": 0, "date_form": 0, "date_year": 0, "date_mismatch": 0, "move": 0, "move_end": 0, "condition": 0, "preference": 0,
               "piece": 0, "gap": 0, "locked": 0}''')
p.write_text(s, encoding='utf-8', newline='\n')
print('ok')
