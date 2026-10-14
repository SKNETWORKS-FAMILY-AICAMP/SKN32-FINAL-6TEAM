"""실제 앱 계약의 합성 여행 질의로 빈 답변과 출력 한도 영향을 진단한다."""
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request


def inspect_response(response, expected):
    choice = response['choices'][0]
    message = choice['message']
    content = message.get('content')
    try:
        parsed = json.loads(content) if isinstance(content, str) else None
    except (ValueError, TypeError):
        parsed = None
    valid = isinstance(parsed, dict)
    correct = valid and all(parsed.get(k) == v for k, v in expected.items())
    return dict(parsed=valid, pick=parsed, correct=correct,
                finish_reason=choice.get('finish_reason'),
                empty_content=not isinstance(content, str) or not content.strip(),
                reasoning_characters=len(message.get('reasoning_content') or ''),
                usage=response.get('usage', {}), timings=response.get('timings', {}))


def main():
    port = os.environ['PORT']
    endpoint = 'http://127.0.0.1:' + port
    command = [os.environ['LLAMA_SERVER'], '-m', os.environ['GGUF'], '-ngl', '99',
               '-t', '4', '-tb', '4', '-c', '4096', '-np', '1', '--jinja',
               '--host', '127.0.0.1', '--port', port]
    if os.environ.get('LORA'):
        command += ['--lora', os.environ['LORA']]
    environment = dict(os.environ, LD_LIBRARY_PATH=str(Path(os.environ['LLAMA_SERVER']).parent))
    with Path('engine.log').open('x') as engine_log:
        process = subprocess.Popen(command, env=environment, stdout=engine_log, stderr=subprocess.STDOUT)
        try:
            for _ in range(180):
                if process.poll() is not None:
                    raise RuntimeError('진단 모델 기동 실패')
                try:
                    with urllib.request.urlopen(endpoint + '/health', timeout=2) as response:
                        if response.status == 200:
                            break
                except (OSError, urllib.error.URLError):
                    time.sleep(1)
            else:
                raise TimeoutError('진단 모델 준비 시간 초과')
            rows = json.loads(Path(os.environ['PROMPTS']).read_text())
            with Path('d_test_' + os.environ['TAG'] + '.jsonl').open('x') as answers:
                for row in rows:
                    started = time.monotonic()
                    result = dict(i=row['i'], case=row['case'], history=row['history'],
                                  budget=row['budget'], repeat=row['repeat'], gold=row['gold'])
                    request = urllib.request.Request(endpoint + '/v1/chat/completions',
                        data=json.dumps(row['payload']).encode(), headers={'Content-Type': 'application/json'})
                    try:
                        with urllib.request.urlopen(request, timeout=180) as response:
                            raw = json.load(response)
                        result.update(inspect_response(raw, row['gold']), raw_response=raw)
                    except Exception as error:
                        result.update(parsed=False, correct=False, pick=None, error=type(error).__name__)
                    result['seconds'] = time.monotonic() - started
                    answers.write(json.dumps(result, ensure_ascii=False) + '\n')
                    answers.flush()
        finally:
            # 이 진단에서 만든 자식만 종료하며 기존 실행기는 건드리지 않는다.
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    main()
