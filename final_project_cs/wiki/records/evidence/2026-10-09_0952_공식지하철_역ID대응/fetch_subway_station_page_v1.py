from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import httpx

p = Path(__file__).parent / 'subway-station-page-20261009-v1.html'
assert not p.exists()
url = 'https://data.seoul.go.kr/dataList/OA-12764/F/1/datasetView.do'
r = httpx.get(url, timeout=25)
r.raise_for_status()
p.write_bytes(r.content)
meta = {'url': url, 'created_at': datetime.now().astimezone().isoformat(), 'http_status': r.status_code,
        'sha256': hashlib.sha256(r.content).hexdigest(), 'bytes': len(r.content)}
(p.parent / 'subway-station-page-fetch-v1.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf8')
for token in ['20260902', 'fn_fileDownload', 'fileDownload', 'downloadFile']:
    for m in list(re.finditer(token, r.text))[:3]:
        print(r.text[max(0, m.start()-240):m.end()+320])
