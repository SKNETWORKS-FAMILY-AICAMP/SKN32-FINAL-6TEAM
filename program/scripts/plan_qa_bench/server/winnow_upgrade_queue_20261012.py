"""Exclusive-queue control job: verified base staging or smoke/full training.

The 1-row output is an execution gate, never an accuracy observation.
Configuration contains private machine paths and lives outside this source file.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def reserve(extra=0):
    assert shutil.disk_usage('/').free >= 3 * 2**30 + extra, 'root disk reserve'


def stage(config):
    target = Path(config['gguf'])
    if target.exists():
        assert target.stat().st_size == config['gguf_size']
        assert digest(target) == config['gguf_sha256']
        return {'already_verified': True}
    assert not Path(config['predecessor_proc']).exists(), 'predecessor is still alive'
    size = config['gguf_size']
    assert shutil.disk_usage('/dev/shm').free > size + 2 * 2**30, 'tmpfs reserve'
    limit = int(Path('/sys/fs/cgroup/memory.max').read_text())
    current = int(Path('/sys/fs/cgroup/memory.current').read_text())
    assert limit - current > size + 6 * 2**30, 'cgroup RAM reserve'
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix('.part')
    assert not partial.exists(), 'preserve previous incomplete download; explicit review required'
    sha = hashlib.sha256()
    count = 0
    request = urllib.request.Request(config['gguf_url'], headers={'User-Agent': 'triPilot-research'})
    with urllib.request.urlopen(request, timeout=180) as response, partial.open('xb') as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            sha.update(chunk)
            count += len(chunk)
            assert count <= size, 'download exceeded immutable expected size'
    assert count == size and sha.hexdigest() == config['gguf_sha256'], 'immutable base mismatch'
    os.replace(partial, target)
    return {'bytes': count, 'sha256': sha.hexdigest(), 'ephemeral_tmpfs': True}


def train(config):
    reserve(240_000_000)
    assert digest(config['train']) == config['train_sha256'], 'training data mismatch'
    assert digest(Path(config['hf_base']) / 'config.json') == config['hf_config_sha256']
    assert digest(Path(config['hf_base']) / 'model.safetensors') == config['hf_weights_sha256']
    output = Path(config['adapter'])
    converted = Path(config['lora'])
    assert not output.exists() and not converted.exists(), 'never overwrite trained artifacts'
    common = [config['python'], config['trainer'], config['hf_base'], config['train']]
    smoke = Path(config['smoke_adapter'])
    assert not smoke.exists(), 'previous smoke preserved; no automatic retry'
    subprocess.run(common + [str(smoke), '--epochs', '1', '--limit', '16', '--accum', '8',
                             '--maxlen', '4096', '--rank', '16', '--lr', '5e-5',
                             '--seed', '20261019', '--family', 'gemma'], check=True)
    smoke_proof = json.loads((smoke / 'training_proof.json').read_text())
    assert smoke_proof['optimizer_steps'] == 2 and smoke_proof['adapter_changed']
    assert smoke_proof['base_frozen'] and smoke_proof['kept_rows'] == 16
    reserve(240_000_000)
    subprocess.run(common + [str(output), '--epochs', '2', '--accum', '8', '--maxlen', '4096',
                             '--rank', '16', '--lr', '5e-5', '--seed', '20261019',
                             '--family', 'gemma'], check=True)
    proof = json.loads((output / 'training_proof.json').read_text())
    assert proof['kept_rows'] == 2613 and proof['adapter_changed'] and proof['base_frozen']
    partial = converted.with_suffix('.partial.gguf')
    assert not partial.exists()
    subprocess.run([config['python'], config['converter'], str(output), '--base', config['hf_base'],
                    '--outfile', str(partial), '--outtype', 'f16'], check=True)
    assert partial.stat().st_size > 1_000_000
    os.replace(partial, converted)
    reserve()
    return {'proof': proof, 'adapter_sha256': digest(output / 'adapter_model.safetensors'),
            'lora_sha256': digest(converted), 'lora_bytes': converted.stat().st_size}


if __name__ == '__main__':
    config = json.loads(Path(__file__).with_name('config.json').read_text())
    tag = os.environ['TAG']
    assert not Path(f'd_test_{tag}.jsonl').exists()
    kind = 'stage' if tag.endswith('_stage') else 'train'
    result = {'kind': kind, 'accuracy_measured': False, 'result': stage(config) if kind == 'stage' else train(config)}
    Path(f'd_test_{tag}.jsonl').write_text(json.dumps({'i': 0, 'parsed': result}) + '\n')
