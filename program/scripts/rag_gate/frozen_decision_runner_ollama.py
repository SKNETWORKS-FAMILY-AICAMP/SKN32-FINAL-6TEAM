"""고정 1,448문장을 **제품이 쓰는 경로**(제품 결정 코드 + Ollama `/api/chat` + 학습 E4B)로 재생한다.

`frozen_decision_runner.py`(llama-server 직접 호출 · 학습 없는 원본 · 출력 400토큰)와 다른 점 — 이 러너는 제품 코드를 그대로 쓴다:
  · 호출: `app.infrastructure.ollama_chat.OllamaChat.structured`(think:false · format=스키마 · temperature 0 · num_ctx)
  · 답 길이 상한: 제품 설정 `config/guardrails.yaml` 의 `travel.decision_unit.num_predict`(1200)
  · 「지금」 줄: 제품은 늘 현재 시각을 넣는다 → 여행 1일차 첫 일정 1시간 전으로 고정해 넣는다(NOW_MODE=trip 기본, `none` 이면 뺀다)
규정 검색 · 일정 변경 실행은 하지 않는다(결정 함수까지만). 실패 · 길이 초과는 분모에 남긴다(자동 재시도 없음).

환경 변수: PROMPTS(prompts.json 경로 — 같은 폴더의 source/ · dependencies/ · contract.json 을 쓴다) · TAG · OLLAMA_URL · MODEL · NUM_CTX · NOW_MODE
GPU 대기열(`gpu_eval_queue.py`)이 작업 폴더에서 `python3 runner.py` 로 부른다. 끝나면 모델을 내려(keep_alive=0) 다음 작업이 막히지 않게 한다.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

KST = timezone(timedelta(hours=9))


def main():
    root = Path(os.environ['PROMPTS']).parent
    sys.path[:0] = [str(root / 'source'), str(root / 'dependencies'), str(root)]
    from eval.decision_unit.replay import load_trips
    from app.domains.travel_ops.components.conversation import decision_unit as D
    from app.infrastructure.ollama_chat import OllamaChat
    from score_misanswer_frozen import score
    import yaml

    contract = json.loads((root / 'contract.json').read_text(encoding='utf-8'))
    for name, expected in contract['files'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
    rows = json.loads(Path(os.environ['PROMPTS']).read_text(encoding='utf-8'))
    assert hashlib.sha256(Path(os.environ['PROMPTS']).read_bytes()).hexdigest() == contract['prompts_sha256']
    guard = yaml.safe_load((root / 'source/config/guardrails.yaml').read_text(encoding='utf-8'))
    num_predict = int(guard['travel']['decision_unit']['num_predict'])
    trips = load_trips(root / 'source/eval/decision_unit/trips.json')
    items, changes = trips[contract['trip']]
    stops = D.stops_of(items)
    aliases = {s.item.item_id: s.alias for s in stops}
    url = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11435')
    model = os.environ.get('MODEL', 'tripilot-pointer:e4b-ft')
    num_ctx = int(os.environ.get('NUM_CTX', '8192'))
    now = None
    if os.environ.get('NOW_MODE', 'trip') == 'trip':
        now = (stops[0].item.starts_at - timedelta(hours=1)).astimezone(KST)
    version = json.load(urllib.request.urlopen(url + '/api/version', timeout=10))['version']

    class Response:
        """OllamaChat 이 기대하는 응답 모양(상태 · json() · text)."""
        def __init__(self, raw: bytes, status: int):
            self.status_code, self.text, self._raw = status, raw.decode('utf-8', 'replace'), raw

        def json(self):
            return json.loads(self._raw)

    seen = {}

    def post(address, payload):
        data = json.dumps(payload).encode()
        seen['payload_sha256'] = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        request = urllib.request.Request(address, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw, status = response.read(), response.status
        except urllib.error.HTTPError as error:
            raw, status = error.read(), error.code
        seen['raw_response'] = raw.decode('utf-8', 'replace')
        return Response(raw, status)

    chat = OllamaChat(base_url=url, model=model, timeout=180, transport=post, keep_alive='30m', num_ctx=num_ctx)
    decisions = {}
    blocked = None
    try:
        with Path('d_test_' + os.environ['TAG'] + '.jsonl').open('x', encoding='utf-8') as stream:
            for row in rows:
                begin = time.monotonic()
                seen.clear()
                if row['q'] not in decisions:
                    try:
                        if blocked:
                            raise RuntimeError('not_attempted: ' + blocked)
                        got = D.fact_first(D.decide(chat, stops=stops, changes=changes, history=[],
                            selected_item_id=None, message=row['q'], num_predict=num_predict, now=now))
                        decisions[row['q']] = dict(action=got.action,
                            item=aliases.get(getattr(got.item, 'item_id', None), 'none'),
                            fact=got.fact, error=None, seconds=time.monotonic() - begin)
                    except Exception as error:
                        decisions[row['q']] = dict(action=None, item=None, fact=None,
                            error=repr(error), seconds=time.monotonic() - begin)
                        if 'Connection' in repr(error) or 'URLError' in repr(error) or 'Ollama 호출 실패' in repr(error):
                            blocked = repr(error)
                decision = decisions[row['q']]
                record = dict(i=row['i'], q=row['q'], src=row['src'], decision=decision,
                    parsed=not bool(decision['error']), error=decision['error'],
                    observed_at_utc=datetime.now(timezone.utc).isoformat(), **seen)
                stream.write(json.dumps(record, ensure_ascii=False) + '\n'); stream.flush()
        Path('decisions.json').write_text(json.dumps(decisions, ensure_ascii=False, indent=2), encoding='utf-8')
        result = score(rows, decisions)
        result.update(regulatory_search_executed=False, actual_product_end_to_end=False,
                      independent_holdout=False, model_adoption=False, contract=contract, expected=len(rows),
                      run=dict(ollama_version=version, model=model, num_ctx=num_ctx, num_predict=num_predict,
                               now=now.isoformat() if now else None, backend='product OllamaChat.structured'))
        Path('summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        try:                                    # 모델을 내려 GPU 메모리를 비운다 — 대기열이 다음 작업을 시작할 수 있게
            request = urllib.request.Request(url + '/api/generate', data=json.dumps(
                dict(model=model, keep_alive=0)).encode(), headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(request, timeout=60).read()
        except Exception:
            pass


if __name__ == '__main__':
    main()
