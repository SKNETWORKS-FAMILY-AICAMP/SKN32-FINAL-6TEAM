"""Download vendor test binaries into this task only; no system installation."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

root = Path(__file__).resolve().parent / '_runtime'
root.mkdir(exist_ok=True)
urls = {
    'postgres.zip': 'https://repository.cybertec.at/windows/public/16/postgresql-ee-16.15_EE_1.3.13-public-1.zip',
    'vector.zip': 'https://repository.cybertec.at/windows/public/16/extension/pgvector-16-public-v0.8.2-1.zip',
}

def fetch(item):
    name, url = item
    target = root / name
    if not target.exists():
        urllib.request.urlretrieve(url, target)
    with zipfile.ZipFile(target) as archive:
        for entry in archive.infolist():
            dest = (root / name.removesuffix('.zip') / entry.filename).resolve()
            if not dest.is_relative_to(root):
                raise ValueError('archive path escape')
        archive.extractall(root / name.removesuffix('.zip'))
    return {'file': name, 'url': url, 'bytes': target.stat().st_size,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    manifest = list(pool.map(fetch, urls.items()))
(root.parent / 'runtime-downloads.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps(manifest))
