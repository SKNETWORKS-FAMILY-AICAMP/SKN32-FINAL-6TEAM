"""Run unchanged travel prompts through a local OpenAI-compatible engine.

Keep failed requests in the denominator and retain raw answers. Resume only
successful responses; transport failures are retried on the next invocation.
"""
import argparse
import json
import re
import time
import urllib.request
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--url', default='http://127.0.0.1:8330/v1/chat/completions')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--model', default='strata')
    args = ap.parse_args()
    items = sorted(json.loads(Path(args.input).read_text(encoding='utf-8')),
                   key=lambda x: (x['set'], x['qi']))
    if args.limit:
        items = items[:args.limit]
    dst = Path(args.output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if dst.exists():
        for line in dst.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if 'error' not in row:
                done[row['i']] = row
    with dst.open('a', encoding='utf-8') as out:
        for index, item in enumerate(items, 1):
            if item['i'] in done:
                continue
            row = {k: v for k, v in item.items() if k != 'prompt'}
            start = time.perf_counter()
            try:
                body = {'model': args.model,
                        'messages': [{'role': 'user', 'content': item['prompt']}],
                        'temperature': 0, 'max_tokens': 16, 'cache_prompt': True,
                        'reasoning_effort': 'none',
                        'chat_template_kwargs': {'enable_thinking': False}}
                request = urllib.request.Request(args.url,
                    data=json.dumps(body).encode(),
                    headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=900) as response:
                    result = json.load(response)
                content = result['choices'][0]['message'].get('content') or ''
                match = re.search(r'"item"\s*:\s*(null|\d+)', content)
                row.update(content=content, parsed=bool(match),
                           pick=None if not match or match[1] == 'null' else int(match[1]),
                           usage=result.get('usage'), timings=result.get('timings'))
            except Exception as exc:
                row.update(content='', parsed=False, pick=None,
                           error=f'{type(exc).__name__}: {exc}')
            row['ms'] = round((time.perf_counter() - start) * 1000)
            row['correct'] = row['parsed'] and row['pick'] == item['gold']
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
            out.flush()
            if 'error' not in row:
                done[row['i']] = row
            if index <= 3 or index % 25 == 0:
                print(f'{index}/{len(items)} parsed={row["parsed"]} ms={row["ms"]}', flush=True)
    latest = {}
    for line in dst.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        latest[row['i']] = row
    summary = {'n': len(items), 'responses': len(latest),
               'correct': sum(latest.get(x['i'], {}).get('correct', False) for x in items),
               'parse_or_transport_failures': sum(not latest.get(x['i'], {}).get('parsed', False) for x in items),
               'endpoint': args.url, 'model': args.model}
    Path(str(dst) + '.summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
