"""동결된 제품 결정 함수를 실제 로컬 모델로 재생한다. 규정 검색·변경 실행은 하지 않는다."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request


def main():
    root = Path(os.environ['PROMPTS']).parent
    sys.path[:0] = [str(root / 'source'), str(root / 'dependencies')]
    from eval.decision_unit.replay import load_trips
    from app.domains.travel_ops.components.conversation import decision_unit as D
    from score_misanswer_frozen import score
    contract = json.loads((root / 'contract.json').read_text())
    for name, expected in contract['files'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
    rows = json.loads(Path(os.environ['PROMPTS']).read_text())
    trips = load_trips(root / 'source/eval/decision_unit/trips.json')
    items, changes = trips[contract['trip']]
    stops = D.stops_of(items)
    aliases = {s.item.item_id: s.alias for s in stops}
    endpoint = 'http://127.0.0.1:' + os.environ['PORT']
    decisions = {}

    class Chat:
        def structured(self, system, user, schema, *, num_predict):
            payload = dict(messages=[dict(role='system', content=system), dict(role='user', content=user)],
                           temperature=0, max_tokens=num_predict, stream=False,
                           response_format=dict(type='json_schema', json_schema=dict(schema=schema)),
                           chat_template_kwargs=dict(enable_thinking=False))
            self.last = dict(payload_sha256=hashlib.sha256(json.dumps(payload, sort_keys=True,
                ensure_ascii=False).encode()).hexdigest())
            request = urllib.request.Request(endpoint + '/v1/chat/completions',
                data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = json.load(response)
            self.last['raw_response'] = raw
            choice = raw['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('생성 미완료: ' + str(choice.get('finish_reason')))
            value = json.loads(choice['message']['content'])
            if not isinstance(value, dict):
                raise ValueError('JSON 객체가 아닙니다')
            return value

    chat = Chat()
    engine = contract['engine']
    assert hashlib.sha256(Path(engine).read_bytes()).hexdigest() == contract['engine_sha256']
    command = [engine, '-m', os.environ['GGUF'], '-ngl', '99',
               '-t', '4', '-tb', '4', '-c', str(contract['context_tokens']), '-np', '1', '--jinja',
               '--no-context-shift',
               '--host', '127.0.0.1', '--port', os.environ['PORT']]
    if os.environ.get('LORA'):
        command += ['--lora', os.environ['LORA']]
    environment = dict(os.environ, LD_LIBRARY_PATH=str(Path(engine).parent))
    process = None
    blocked = None
    try:
        assert shutil.disk_usage('.').free > 3 * 2**30 + 64 * 2**20
        with Path('engine.log').open('x') as log:
            process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(180):
            if process.poll() is not None:
                raise RuntimeError('평가 모델 기동 실패')
            try:
                with urllib.request.urlopen(endpoint + '/health', timeout=2) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(1)
        else:
            raise TimeoutError('평가 모델 준비 시간 초과')
    except Exception as error:
        blocked = repr(error)
    try:
        with Path('d_test_' + os.environ['TAG'] + '.jsonl').open('x') as stream:
            for row in rows:
                begin = time.monotonic()
                chat.last = {}
                if row['q'] not in decisions:
                    if shutil.disk_usage('.').free <= 3 * 2**30 + 32 * 2**20:
                        blocked = 'storage_guard'
                    try:
                        if blocked:
                            raise RuntimeError('not_attempted: ' + blocked)
                        got = D.fact_first(D.decide(chat, stops=stops, changes=changes, history=[],
                            selected_item_id=None, message=row['q'], num_predict=contract['num_predict']))
                        decisions[row['q']] = dict(action=got.action,
                            item=aliases.get(getattr(got.item, 'item_id', None), 'none'),
                            fact=got.fact, error=None, seconds=time.monotonic()-begin)
                    except Exception as error:
                        decisions[row['q']] = dict(action=None, item=None, fact=None,
                            error=repr(error), seconds=time.monotonic()-begin)
                        # 입력별 JSON/분류 실패는 다음 문장으로 넘어간다. 연결 장애는 자동 재시도하지 않는다.
                        if 'URLError' in repr(error) or 'Connection' in repr(error):
                            blocked = repr(error)
                decision = decisions[row['q']]
                record = dict(i=row['i'], q=row['q'], src=row['src'], decision=decision,
                    parsed=not bool(decision['error']), error=decision['error'],
                    observed_at_utc=datetime.now(timezone.utc).isoformat(), **chat.last)
                stream.write(json.dumps(record, ensure_ascii=False)+'\n'); stream.flush()
        Path('decisions.json').write_text(json.dumps(decisions, ensure_ascii=False, indent=2))
        result = score(rows, decisions)
        result.update(regulatory_search_executed=False, actual_product_end_to_end=False,
                      independent_holdout=False, model_adoption=False, contract=contract,
                      engine_command=command, expected=len(rows))
        Path('summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()


if __name__ == '__main__':
    main()
