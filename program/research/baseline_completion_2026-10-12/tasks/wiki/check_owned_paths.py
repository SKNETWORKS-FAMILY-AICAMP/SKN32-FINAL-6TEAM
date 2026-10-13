"""담당 안내 두 페이지의 모든 로컬 링크와 등록 구현 참조를 확인한다."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[5]
rows = []
for name in ('wiki/delivery/roles.md', 'final_project_cs/wiki/teams/code-layout.md'):
    path = ROOT/name
    raw = path.read_text(encoding='utf-8')
    for value in sorted(set(re.findall(r'\]\(([^)]+)\)', raw))):
        if '://' in value or value.startswith('#'):
            continue
        target = (path.parent/value.split('#', 1)[0]).resolve()
        rows.append({'source': name, 'target': value, 'exists': target.exists()})
data = {'checked_at_kst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'scope': '역할·코드 위치 안내 2개 본문의 로컬 링크 대상. 경로 존재가 기능 통과·담당 배정·외부 약관 적합성을 뜻하지 않음',
        'checked': len(rows), 'passed': sum(r['exists'] for r in rows), 'rows': rows,
        'readme_sha256': hashlib.sha256((ROOT/'README.md').read_bytes()).hexdigest()}
p = Path(__file__).parent/'owned-paths.json'
p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(f"로컬 링크 대상 {data['passed']}/{data['checked']}")
raise SystemExit(int(data['passed'] != data['checked']))
