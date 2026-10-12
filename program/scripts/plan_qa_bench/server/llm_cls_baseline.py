# 서버 A(올라마)에서: 서비스가 지금 쓰는 분류 방식 그대로(코드의 시스템 프롬프트 + gemma4:12b JSON 출력)를 시험 자료에 돌려 기준선을 만든다. 같은 프롬프트로 E4B QAT 도 잰다.
# 사용: python3 llm_cls_baseline.py <모델> <test.jsonl,...>   → llm_cls_<모델>.json
import json, re, sys, time, urllib.request
MODEL, TESTS = sys.argv[1], sys.argv[2].split(',')
PROMPT = open('product_prompt.txt', encoding='utf-8').read()
def ask(msg):
    body = {'model': MODEL, 'stream': False, 'format': 'json', 'think': False, 'options': {'temperature': 0, 'num_predict': 120},
            'messages': [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': msg}]}
    req = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    t0 = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=300))
    return r['message']['content'], time.time() - t0
out = {}
for t in TESTS:
    rows = [json.loads(l) for l in open(t, encoding='utf-8')]
    res, lat = [], []
    for r in rows:
        try:
            txt, dt = ask(r['message'])
            d = json.loads(txt)
        except Exception as e:  # noqa: BLE001
            d, dt = {}, 0.0
        lat.append(dt)
        ic = str(d.get('issue_code', 'other'))
        res.append({'id': r['id'], 'intent': d.get('intent'), 'sentiment': d.get('sentiment'), 'severity': d.get('severity'), 'case_type': ic.split('_')[0] if ic != 'other' else 'other'})
    out[t] = {'preds': res, 'lat_median_s': sorted(lat)[len(lat) // 2], 'n': len(rows)}
    print(MODEL, t, len(rows), 'median', round(out[t]['lat_median_s'], 2), 's', flush=True)
json.dump(out, open('llm_cls_' + MODEL.replace(':', '_').replace('/', '_') + '.json', 'w', encoding='utf-8'), ensure_ascii=False)
