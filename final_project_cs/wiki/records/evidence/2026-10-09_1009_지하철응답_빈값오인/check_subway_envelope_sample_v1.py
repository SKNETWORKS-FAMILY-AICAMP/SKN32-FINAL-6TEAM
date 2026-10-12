from pathlib import Path
from datetime import datetime
import hashlib
import json
import sys
import httpx

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'final_project_cs'))
from app.domains.travel_ops.ports.data_sources.seoul_subway import SeoulSubwayArrival

scratch = Path(__file__).parent
state = json.loads((scratch / 'subway-envelope-work-v1.json').read_text(encoding='utf8'))
ev = root / 'final_project_cs/wiki/records/evidence' / state['tag']
raw = root / 'datasets/mobility/raw' / (state['tag'] + '_public_sample')
raw.mkdir(exist_ok=False)
url = 'http://swopenapi.seoul.go.kr/api/subway/sample/json/realtimeStationArrival/0/5/%EC%84%9C%EC%9A%B8'
started = datetime.now().astimezone()
try:
    response = httpx.get(url, timeout=20)
    finished = datetime.now().astimezone()
    body = raw / 'response-v1.json'
    body.write_bytes(response.content)
    result = {'started_at': started.isoformat(), 'finished_at': finished.isoformat(),
              'url': url, 'http_status': response.status_code, 'response_bytes': len(response.content),
              'raw_path': body.relative_to(root).as_posix(),
              'raw_sha256': hashlib.sha256(response.content).hexdigest(), 'public_sample_requests': 1}
    if response.status_code == 200:
        payload = response.json()
        src = SeoulSubwayArrival(service_key='sample',
            transport=lambda u, p: httpx.Response(200, json=payload, request=httpx.Request('GET', u)))
        normalized = src.arrivals('\uC11C\uC6B8')
        result.update(normalized_success=normalized is not None,
                      train_count=len(normalized['trains']) if normalized else None,
                      misses=dict(src.misses),
                      response_code=(payload.get('errorMessage') or payload).get('code'),
                      claim='One provider snapshot for Seoul Station, replayed through public arrivals. Not train selection, journey measurement or runtime departure integration.')
        with (raw / 'normalized-v1.json').open('x', encoding='utf8') as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
except (httpx.HTTPError, ValueError, TypeError) as error:
    result = {'started_at': started.isoformat(), 'finished_at': datetime.now().astimezone().isoformat(),
              'url': url, 'public_sample_requests': 1, 'error_type': type(error).__name__,
              'error': str(error), 'normalized_success': False}
with (ev / 'public-sample-check-v1.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
with (raw / 'acquisition-v1.json').open('x', encoding='utf8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False))
