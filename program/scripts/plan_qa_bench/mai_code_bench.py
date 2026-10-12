"""Compare MAI-Code-1.1-Flash through Copilot CLI on unchanged D3 inputs.

No tools, custom instructions, MCP tools, or remote-session export are enabled.
API transport and CLI overhead differ from the local FrogNano path.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERIFY_PROMPT = '고객이 여행 일정 안내 챗봇에게 이렇게 말했다: "{q}"\n챗봇이 이 말이 가리키는 일정 항목으로 아래를 골랐다.\n{line}\n고객의 말이 정말 이 일정 항목에 대한 질문 · 요청인가? 일상 대화 · 잡담이거나 이 항목과 무관하면 NO. 반드시 YES 또는 NO 한 단어로만 답하라.'
EXTRA = '\n\n(파일을 만들거나 명령을 실행하지 말고 JSON 한 개로만 답하라. verdict 는 YES 또는 NO. p_yes 는 「정답이 YES 일 확률」이다: 고객 말이 이 항목에 대한 말이 아니라고 확신하면 0.02 처럼 0 에 가깝게, 이 항목에 대한 말이라고 확신하면 0.98 처럼 1 에 가깝게. verdict 와 p_yes 가 서로 어긋나면 안 된다.)'


def ask(prompt):
    loader = Path(os.environ['APPDATA']) / 'npm/node_modules/@github/copilot/npm-loader.js'
    command = [shutil.which('node') or 'node', str(loader),
               '--model', 'mai-code-1.1-flash', '--no-auto-update',
               '--no-custom-instructions', '--disable-builtin-mcps',
               '--available-tools=', '--deny-tool', 'shell', '--deny-tool', 'write',
               '--deny-tool', 'read', '--no-ask-user', '--no-remote', '--no-remote-export',
               '--reasoning-effort', 'low', '--max-ai-credits', '30',
               '--silent', '--prompt', prompt]
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='mai-bench-') as isolated:
        result = subprocess.run(command, cwd=isolated, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=300)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-1200:])
    return result.stdout.strip(), round(time.perf_counter() - start, 3)


def run(items, output, phase, workers):
    done = set()
    if output.exists():
        for line in output.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if 'error' not in row:
                done.add(row['key'] if phase == 'verify' else row['i'])
    field = 'key' if phase == 'verify' else 'i'
    todo = [x for x in items if x[field] not in done]
    print(f'{phase}: remaining {len(todo)}/{len(items)}', flush=True)

    def one(item):
        row = {field: item[field], 'model': 'mai-code-1.1-flash', 'path': 'copilot-cli'}
        if phase == 'direct':
            row.update(type=item['type'], gold=item['gold'])
        try:
            prompt = VERIFY_PROMPT.format(**item) + EXTRA if phase == 'verify' else item['prompt'] + '\n\n(파일을 만들거나 명령을 실행하지 말고 JSON 한 개로만 답하라.)'
            text, seconds = ask(prompt)
            row.update(raw=text, sec=seconds)
            if phase == 'verify':
                match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', text)
                value = json.loads(match[0]) if match else {}
                if value.get('verdict') not in ('YES', 'NO'):
                    raise ValueError('Invalid verdict')
                p_yes = value.get('p_yes')
                if not isinstance(p_yes, (float, int)) or not 0 <= p_yes <= 1:
                    raise ValueError('Invalid declared confidence')
                row.update(content=value['verdict'], p_yes=p_yes)
            else:
                match = re.search(r'"item"\s*:\s*(null|\d+)', text)
                row.update(content=text, parsed=bool(match),
                           pick=None if not match or match[1] == 'null' else int(match[1]))
        except Exception as exc:
            row.update(error=f'{type(exc).__name__}: {exc}')
        return row

    with output.open('a', encoding='utf-8') as out, ThreadPoolExecutor(workers) as pool:
        for index, row in enumerate(pool.map(one, todo), 1):
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
            out.flush()
            if index <= 3 or index % 10 == 0:
                print(f'{phase}: {index}/{len(todo)} error={"error" in row}', flush=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--direct-input', required=True)
    ap.add_argument('--phase', choices=['verify', 'direct', 'both'], default='both')
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    dest = HERE / 'results/d_test'
    if args.phase in ('verify', 'both'):
        items = [x for x in json.loads((dest / 'verify_inputs.json').read_text(encoding='utf-8')) if x['ds'] == 'D3']
        run(items[:args.limit] if args.limit else items,
            dest / 'verify_mai_code_1_1_flash.jsonl', 'verify', args.workers)
    if args.phase in ('direct', 'both'):
        items = json.loads(Path(args.direct_input).read_text(encoding='utf-8'))
        run(items[:args.limit] if args.limit else items,
            dest / 'd_test_d3_mai_code_1_1_flash.jsonl', 'direct', args.workers)
    print('ALLDONE_MAI_REQUESTED_PHASES', flush=True)


if __name__ == '__main__':
    main()
