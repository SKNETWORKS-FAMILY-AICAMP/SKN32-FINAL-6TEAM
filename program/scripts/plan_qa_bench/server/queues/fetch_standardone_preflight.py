"""공개 후보의 수정판·파일 크기·작은 공식 설명 파일만 보관한다."""
import hashlib
import json
from pathlib import Path
import urllib.request

workspace = Path(__file__).resolve().parents[5]
root = workspace / 'program/scripts/plan_qa_bench/results/standardone_preflight_20261008'
root.mkdir(exist_ok=True)
for size in ['3B', '8B']:
    repo = 'StandardThinking/StandardOne-' + size
    url = 'https://huggingface.co/api/models/' + repo + '?blobs=true'
    with urllib.request.urlopen(url, timeout=40) as response:
        api = json.load(response)
    revision = api['sha']
    folder = root / (size + '_' + revision)
    folder.mkdir(exist_ok=True)
    if not (folder / 'model_api.json').exists():
        with (folder / 'model_api.json').open('x', encoding='utf-8') as f:
            json.dump(api, f, ensure_ascii=False, indent=2)
    files = {s['rfilename']: s for s in api['siblings']}
    requested = ['LICENSE', 'NOTICE', 'config.json', 'release-manifest.json',
                 'MERGE_REPORT.json', 'QUICKSTART.md', 'README.md']
    if size == '8B':
        requested += [n for n, s in files.items() if n.startswith('server/')
                      and not n.endswith(('.lock', '.jsonl')) and s.get('size', 0) <= 250000]
    fetched = []
    for name in requested:
        if name not in files:
            continue
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            source = 'https://huggingface.co/' + repo + '/resolve/' + revision + '/' + name
            with urllib.request.urlopen(source, timeout=40) as response:
                data = response.read(300001)
            if len(data) > 300000:
                raise ValueError('Metadata size limit exceeded')
            with target.open('xb') as f:
                f.write(data)
        fetched.append(name)
    weight_bytes = sum(s.get('size', s.get('lfs', {}).get('size', 0))
                       for n, s in files.items() if n.endswith('.safetensors'))
    summary = dict(repo_id=repo, revision_sha=revision, weights_bytes=weight_bytes,
                   last_modified=api.get('lastModified'), safetensors=api.get('safetensors'),
                   fetched_files=fetched,
                   license_sha256=hashlib.sha256((folder / 'LICENSE').read_bytes()).hexdigest())
    if not (folder / 'preflight.json').exists():
        with (folder / 'preflight.json').open('x', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=True))
