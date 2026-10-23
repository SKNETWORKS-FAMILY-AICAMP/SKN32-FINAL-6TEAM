import json, glob, os, re, collections
T = 'C:/Users/PLAYDA~1/AppData/Local/Temp/claude/C--Users-playdata2-Documents-final-workspace/393ad054-3d33-4557-ac71-4cd1cf6e6401/'
ids = ['aa89520273c85fcea','a2b4ff7808e6bef99','a1023d30a51dc58fb','a0beb555c70792ad6','a2ac6fcab3be080ae','a28c493f3128f8c74','a51e42c8e08bf7fa0','ac17be33b111f64c0','a5b998271e321ebeb','ae9e39c4947c38d56','a07762d80ffd38ce7','aef5d3d566f15ecd8']
agg = collections.Counter(); odd = []
for aid in ids:
    p = T + 'tasks/' + aid + '.output'
    if not os.path.exists(p): odd.append((aid, 'no file')); continue
    for line in open(p, encoding='utf-8', errors='replace'):
        try: d = json.loads(line)
        except Exception: continue
        msg = d.get('message') or {}
        cont = msg.get('content')
        if not isinstance(cont, list): continue
        for c in cont:
            if isinstance(c, dict) and c.get('type') == 'tool_use':
                name = c.get('name'); inp = c.get('input') or {}
                tgt = inp.get('file_path') or inp.get('path') or inp.get('command') or ''
                agg[name] += 1
                ok = ('ai_run' in str(tgt)) or name not in ('Read', 'Write', 'Bash', 'Glob', 'Grep', 'Edit')
                if not ok or name not in ('Read', 'Write'):
                    odd.append((aid[:6], name, str(tgt)[:120]))
print('도구 호출 합계', dict(agg))
print('예외(이름이 Read/Write 가 아니거나 ai_run 밖):', odd)
# Codex 로그에서 실행한 명령
R = T + 'scratchpad/ai_run/codex_out/'
cmds = collections.Counter()
for lg in sorted(glob.glob(R + 'P*.log')):
    txt = open(lg, encoding='utf-8', errors='replace').read()
    for m in re.finditer(r'(?m)^\s*(?:exec|bash|\$)\s+(.{0,160})$', txt):
        cmds[(os.path.basename(lg), m.group(1)[:140])] += 1
print('Codex 로그 명령 후보 수', sum(cmds.values()))
for (f, c), n in list(cmds.items())[:40]: print(f, n, c)
print('Codex 로그에서 금지 파일 언급:', {os.path.basename(lg): [k for k in ('_층화키', 'gold/v1', 'draft_claude', 'ai_claude', 'pilot12_inputs', 'GUIDE') if k in open(lg, encoding='utf-8', errors='replace').read()] for lg in sorted(glob.glob(R + 'P*.log'))})
