import json
SC = 'C:/Users/PLAYDA~1/AppData/Local/Temp/claude/C--Users-playdata2-Documents-final-workspace/393ad054-3d33-4557-ac71-4cd1cf6e6401/scratchpad/pilot/'
OUT = 'C:/Users/playdata2/Documents/final_workspace/datasets/travel/plan_samples/korea/seoul/gold/pilot12_20261023/'
s = open(SC + 'form_template.html', encoding='utf-8').read()
posts = [json.loads(l) for l in open(OUT + 'pilot12_inputs.jsonl', encoding='utf-8') if l.strip()]
key = json.load(open(OUT + '_층화키_라벨후열기.json', encoding='utf-8'))
relabel = [k['pilot_id'] for k in key['items'] if k['relabel_after_24h']]
data = json.dumps([{'pilot_id': q['pilot_id'], 'plan_id': q['plan_id'], 'title': q['title'], 'text': q['text']} for q in posts], ensure_ascii=False)
data = data.replace('</', '<\\/').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
html = s.replace('__DATA__', data).replace('__RELABEL__', json.dumps(relabel))
open(OUT + 'label_form_pilot12.html', 'w', encoding='utf-8', newline='\n').write(html)
print('ok', len(html), relabel)
