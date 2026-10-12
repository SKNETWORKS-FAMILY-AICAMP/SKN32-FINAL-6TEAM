"""Stateful Docker control simulation; not a real container deployment."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('migration_safe_deploy',
    Path(__file__).resolve().parents[3] / 'deploy/migration_safe_deploy.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class DockerSimulation:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []
        self.live = {s: 'sha256:old-' + s for s in guard.SERVICES}
        self.declared = {s: 'tag-' + s for s in guard.SERVICES}
        self.config = {'name': 'tripilot', 'services': {s: {
            'image': 'tag-' + s, 'volumes': [{'type': 'bind', 'source': '/private/override',
                                            'target': '/srv/retained', 'read_only': True}]}
            for s in guard.SERVICES}}
        self.up_count = 0
        self.job_name = None
        self.manifest = {'contract_version': 2, 'historical': ['a','b','c','d'], 'sha256': {'x':'ok'}}
        self.observations = 0

    def run(self, args, timeout=60):
        self.calls.append((args, timeout))
        if args[0] == 'tag':
            return ''
        if 'config' in args:
            if '--hash' in args:
                config = json.loads(Path(args[args.index('-f')+1]).read_text()) if '-f' in args else self.config
                return '\n'.join(s + ' hash-' + s + ':' + config['services'][s]['image'] for s in guard.SERVICES)
            return json.dumps(self.config)
        if args[:2] == ['image', 'inspect']:
            return json.dumps([{'Id': args[-1] if args[-1].startswith('sha256:')
                               else 'sha256:new-' + args[-1].removeprefix('tag-')}])
        if 'up' in args:
            self.up_count += 1
            path = Path(args[args.index('-f') + 1])
            config = json.loads(path.read_text())
            assert '--no-build' in args and '--pull' in args and 'never' in args
            assert 'tripilot-db' not in args
            if self.up_count == 1 and self.failure in ('partial', 'timeout', 'recovery'):
                self.live['tripilot-api'] = config['services']['tripilot-api']['image']
                raise guard.DeployError('timeout or partial apply')
            if self.up_count == 2 and self.failure == 'recovery':
                raise guard.DeployError('recovery failed')
            self.live = {s: config['services'][s]['image'] for s in guard.SERVICES}
            self.declared = self.live.copy()
            return ''
        if 'ps' in args:
            return 'job-id' if '--filter' in args else 'container-' + args[-1]
        if args[0] == 'inspect':
            service = args[-1].removeprefix('container-')
            if service == 'tripilot-db':
                return json.dumps([{'State':{'Status':'running', 'Health':{'Status':'healthy'}}}])
            self.observations += 1
            return json.dumps([{'Id': 'container-' + service, 'Image': self.live[service],
                'RestartCount': int(self.failure == 'restart' and self.up_count == 1 and self.observations > 6),
                'State': {'Status': 'running', 'Health': {'Status':
                    'unhealthy' if self.failure == 'health' and self.up_count == 1 else 'healthy'}},
                'Config': {'Image':self.declared[service], 'Labels': {'com.docker.compose.config-hash':
                    'drift' if self.failure == 'drift' else 'hash-' + service + ':' + self.declared[service]}}}])
        if 'run' in args:
            if '--name' in args:
                self.job_name = args[args.index('--name') + 1]
                if self.failure == 'migration_timeout':
                    raise guard.DeployError('job timeout')
                return ''
            native = args[0] == 'run'
            if native and self.failure == 'old_image':
                raise guard.DeployError('safety_manifest import failed')
            result = copy.deepcopy(self.manifest)
            if not native and self.failure == 'old_override':
                result['sha256']['x'] = 'old'
            return json.dumps(result)
        if args[:2] == ['rm', '-f']:
            return ''
        raise AssertionError(args)


def test_snapshot_pins_running_image_even_if_tag_points_elsewhere(tmp_path):
    docker = DockerSimulation()
    guard.snapshot(docker, guard.compose(), tmp_path)
    config = json.loads((tmp_path/'recovery.compose.json').read_text())
    for s in guard.SERVICES:
        assert config['services'][s]['image'] == 'sha256:old-' + s
        assert config['services'][s]['volumes'] == docker.config['services'][s]['volumes']
    assert len([args for args,_ in docker.calls if args[0]=='tag']) == 3
    with pytest.raises(FileExistsError):
        guard.snapshot(docker, guard.compose(), tmp_path)


def test_config_drift_stops_before_snapshot_or_mutation(tmp_path):
    docker = DockerSimulation('drift')
    with pytest.raises(guard.DeployError, match='drift'):
        guard.snapshot(docker, guard.compose(), tmp_path)
    assert not (tmp_path/'baseline.json').exists() and docker.up_count == 0


@pytest.mark.parametrize('failure', ['old_image', 'old_override'])
def test_missing_safety_in_native_image_or_override_blocks_before_up(tmp_path, failure):
    docker = DockerSimulation(failure)
    guard.snapshot(docker, guard.compose(), tmp_path)
    with pytest.raises(guard.DeployError):
        guard.rollout(docker, guard.compose(['explicit.compose.yml']), tmp_path, settle=0)
    assert docker.up_count == 0
    assert all('sha256:old-' in image for image in docker.live.values())


@pytest.mark.parametrize('failure', ['partial', 'timeout', 'health'])
def test_partial_failure_timeout_and_bad_health_restore_all_exact_images(tmp_path, failure):
    docker = DockerSimulation(failure)
    guard.snapshot(docker, guard.compose(), tmp_path)
    with pytest.raises(guard.DeployError, match='recovery verified'):
        guard.rollout(docker, guard.compose(), tmp_path, timeout=8, settle=0)
    assert docker.live == {s:'sha256:old-' + s for s in guard.SERVICES}
    assert docker.up_count == 2


def test_recovery_failure_is_never_reported_as_success(tmp_path):
    docker = DockerSimulation('recovery')
    guard.snapshot(docker, guard.compose(), tmp_path)
    with pytest.raises(guard.DeployError, match='manual action required'):
        guard.rollout(docker, guard.compose(), tmp_path, settle=0)


def test_success_pins_candidates_and_keeps_automatic_overrides(tmp_path):
    docker = DockerSimulation()
    guard.snapshot(docker, guard.compose(), tmp_path)
    images = guard.rollout(docker, guard.compose(), tmp_path, settle=0)
    candidate = json.loads((tmp_path/'candidate.compose.json').read_text())
    assert docker.live == images
    assert docker.up_count == 1
    assert candidate['services']['tripilot-api']['volumes'] == docker.config['services']['tripilot-api']['volumes']


def test_incomplete_recovery_material_blocks_before_up(tmp_path):
    (tmp_path/'baseline.json').write_text('{}')
    docker = DockerSimulation()
    with pytest.raises(guard.DeployError, match='Incomplete'):
        guard.rollout(docker, guard.compose(), tmp_path)
    assert docker.up_count == 0


def test_migration_timeout_stops_named_job_and_does_not_retry():
    docker = DockerSimulation('migration_timeout')
    with pytest.raises(guard.DeployError, match='before retry'):
        guard.migrate(docker, guard.compose(), timeout=1)
    jobs = [a for a,_ in docker.calls if '--name' in a]
    assert len(jobs) == 1 and docker.job_name.startswith('tripilot-migration-')
    assert any(a == ['rm','-f','job-id'] for a,_ in docker.calls)


def test_docker_timeout_and_error_do_not_echo_sensitive_output(monkeypatch):
    def expired(*a, **k):
        raise subprocess.TimeoutExpired('docker', 1, stderr='secret')
    monkeypatch.setattr(subprocess, 'run', expired)
    with pytest.raises(guard.DeployError, match='timed out') as error:
        guard.Docker().run(['info'], timeout=1)
    assert 'secret' not in str(error.value)
    monkeypatch.setattr(subprocess, 'run', lambda *a,**k: subprocess.CompletedProcess(a,1,'','secret'))
    with pytest.raises(guard.DeployError) as error:
        guard.Docker().run(['info'])
    assert 'secret' not in str(error.value)


def test_compose_roundtrip_escapes_dollar_in_environment_and_command(tmp_path):
    path = tmp_path/'roundtrip.json'
    guard.compose_json(path, {'environment':{'TOKEN':'a$b${c}'}, 'command':['echo', '$VALUE']})
    stored = json.loads(path.read_text())
    assert stored == {'environment':{'TOKEN':'a$$b$${c}'}, 'command':['echo', '$$VALUE']}


def test_restarts_during_observation_trigger_recovery(tmp_path, monkeypatch):
    docker = DockerSimulation('restart')
    monkeypatch.setattr(guard.time, 'sleep', lambda seconds: None)
    guard.snapshot(docker, guard.compose(), tmp_path)
    with pytest.raises(guard.DeployError, match='recovery verified'):
        guard.rollout(docker, guard.compose(), tmp_path, settle=4)
    assert docker.live == {s:'sha256:old-' + s for s in guard.SERVICES}


def test_next_snapshot_accepts_previous_immutable_rollout(tmp_path):
    docker = DockerSimulation()
    guard.snapshot(docker, guard.compose(), tmp_path/'first')
    guard.rollout(docker, guard.compose(), tmp_path/'first', settle=0)
    records = guard.snapshot(docker, guard.compose(), tmp_path/'second')
    assert {s:row['image'] for s,row in records.items()} == docker.live


def test_prepare_removes_only_old_migration_overrides_and_preserves_recovery(tmp_path):
    docker = DockerSimulation()
    guard.snapshot(docker, guard.compose(), tmp_path/'different')
    with pytest.raises(guard.DeployError, match='different base images'):
        guard.prepare_candidate(tmp_path/'different', 'sha256:new-api')
    tmp_path = tmp_path/'same'
    docker.live['tripilot-worker'] = docker.live['tripilot-api']
    docker.config['services']['tripilot-api']['volumes'].append({
        'type':'bind', 'source':'/private/old-migrate.py', 'target':'/srv/app/infrastructure/db/migrate.py'})
    guard.snapshot(docker, guard.compose(), tmp_path)
    before = (tmp_path/'recovery.compose.json').read_bytes()
    path = guard.prepare_candidate(tmp_path, 'sha256:new-api')
    config = json.loads(path.read_text())
    assert config['services']['tripilot-api']['image'] == 'sha256:new-api'
    assert config['services']['tripilot-worker']['image'] == 'sha256:new-api'
    assert config['services']['tripilot-web']['image'] == 'sha256:old-tripilot-web'
    assert [m['target'] for m in config['services']['tripilot-api']['volumes']] == ['/srv/retained']
    assert (tmp_path/'recovery.compose.json').read_bytes() == before
