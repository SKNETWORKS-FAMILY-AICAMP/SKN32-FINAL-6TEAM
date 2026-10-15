"""규정 재순위 프롬프트(prompts.json)를 **제품이 쓰는 호출**(`OllamaChat._chat(json_mode=True)` — `/api/chat` · think:false · format json · temperature 0 · num_ctx)로
GPU 서버의 x600 재현 올라마(학습 E4B `tripilot-pointer:e4b-ft`)에 한 건씩 보내 모델 답과 지연을 남긴다. (2026-10-15)

`product_rerank_eval.py plan` 이 만든 prompts.json(행: i · system · user)을 읽는다. 점수 계산은 여기서 하지 않는다 — 로컬 `product_rerank_eval.py score` 가 한다.
GPU 대기열(`gpu_eval_queue.py`)이 작업 폴더에서 `python3 product_rerank_runner.py`(= 작업 폴더의 runner.py)로 부른다. 같은 GPU 에 다른 작업과 겹치지 않는다(대기열이 한 번에 하나).

환경 변수: PROMPTS(prompts.json 경로 — 같은 폴더의 contract.json · source/ 를 쓴다) · TAG · OLLAMA_URL(기본 http://127.0.0.1:11435) · MODEL(기본 tripilot-pointer:e4b-ft) · NUM_CTX(8192)
출력: d_test_<TAG>.jsonl — 행: i · raw(모델 답 문자열) · parsed(`{"ranking":[…]}` 모양인가) · seconds(호출 한 건의 벽시계) · total_ms · load_ms · prompt_tokens · eval_tokens · error
실패·형식 오류도 분모에 남긴다(자동 재시도 없음). 앞 3건은 모델을 올리는 몸풀기(기록하지 않는다). 끝나면 모델을 내려(keep_alive=0) 다음 작업이 막히지 않게 한다.
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    root = Path(os.environ['PROMPTS']).parent
    sys.path[:0] = [str(root / 'source')]
    from app.infrastructure.ollama_chat import OllamaChat

    contract = json.loads((root / 'contract.json').read_text(encoding='utf-8'))
    for name, expected in contract['files'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
    rows = json.loads(Path(os.environ['PROMPTS']).read_text(encoding='utf-8'))
    url = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11435')
    model = os.environ.get('MODEL', 'tripilot-pointer:e4b-ft')
    num_ctx = int(os.environ.get('NUM_CTX', '8192'))
    version = json.load(urllib.request.urlopen(url + '/api/version', timeout=10))['version']
    tags = json.load(urllib.request.urlopen(url + '/api/tags', timeout=10))['models']
    info = next((m for m in tags if m.get('name') == model), None)
    assert info, f'{model} 이 {url} 에 없다'
    print('ollama', version, 'model', model, info.get('digest', '')[:12], flush=True)

    class Response:
        def __init__(self, raw, status):
            self.status_code, self.text, self._raw = status, raw.decode('utf-8', 'replace'), raw

        def json(self):
            return json.loads(self._raw)

    seen = {}

    def post(address, payload):
        request = urllib.request.Request(address, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                raw, status = response.read(), response.status
        except urllib.error.HTTPError as error:
            raw, status = error.read(), error.code
        seen['raw'] = raw
        return Response(raw, status)

    chat = OllamaChat(base_url=url, model=model, timeout=120, transport=post, keep_alive='30m', num_ctx=num_ctx)
    from app.infrastructure.ollama_chat import OllamaError

    for row in rows[:3]:                                  # 몸풀기 — 모델을 올린다(기록하지 않는다)
        try:
            chat._chat(row['system'], row['user'], json_mode=True)
        except OllamaError as exc:
            print('몸풀기 실패', exc, flush=True)
    done = 0
    t_all = time.time()
    with Path('d_test_' + os.environ['TAG'] + '.jsonl').open('x', encoding='utf-8') as stream:
        for row in rows:
            rec = {'i': row['i']}
            t0 = time.perf_counter()
            try:
                raw = chat._chat(row['system'], row['user'], json_mode=True)
                rec['raw'] = raw
                try:
                    value = json.loads(raw)
                    rec['parsed'] = isinstance(value, dict) and isinstance(value.get('ranking'), list)
                except ValueError:
                    rec['parsed'] = False
            except OllamaError as exc:
                rec.update(parsed=False, error=str(exc)[:200])
            rec['seconds'] = round(time.perf_counter() - t0, 3)
            try:
                meta = json.loads(seen.get('raw') or b'{}')
                rec.update(total_ms=round(meta.get('total_duration', 0) / 1e6), load_ms=round(meta.get('load_duration', 0) / 1e6),
                           prompt_tokens=meta.get('prompt_eval_count'), eval_tokens=meta.get('eval_count'))
            except ValueError:
                pass
            seen.pop('raw', None)
            stream.write(json.dumps(rec, ensure_ascii=False) + '\n')
            stream.flush()
            done += 1
            if done % 100 == 0:
                print(done, '/', len(rows), round(time.time() - t_all), '초', flush=True)
    try:                                                    # 모델을 내려 같은 GPU 의 다음 작업이 막히지 않게 한다
        post(url + '/api/generate', {'model': model, 'keep_alive': 0})
    except Exception as exc:                                # noqa: BLE001
        print('모델 내리기 실패', exc, flush=True)
    print('끝', done, '건', round(time.time() - t_all), '초', flush=True)


if __name__ == '__main__':
    main()
