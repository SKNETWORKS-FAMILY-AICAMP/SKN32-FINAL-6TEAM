"""복원 시험 도구를 흉내 낸 도커로 검사한다(실제 도커·운영 DB 를 건드리지 않는다)."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('restore_check',
    Path(__file__).resolve().parents[3] / 'deploy/restore_check.py')
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

OLD, NEW = 'tripilot-api:keep-2026-10', 'tripilot-api:local'


class FakeDocker:
    def __init__(self, *, db_ready=True, new_migrate=0, old_migrate=0, healthy=True, logs='INFO started',
                 old_fields=('database_url', 'llm_model'), new_fields=('database_url', 'llm_model', 'brand_new')):
        self.__dict__.update(locals())
        self.missing = set()
        self.calls = []
        self.created = []

    def run(self, args, timeout=120, check=True):
        self.calls.append(args)
        head = args[0]
        if head == 'network' and args[1] == 'create':
            self.created.append(('net', args[-1]))
            return 0, ''
        if head == 'run' and '-d' in args:
            self.created.append(('ctr', args[args.index('--name') + 1]))
            return 0, ''
        if head == 'exec' and 'pg_isready' in args:
            return (0 if self.db_ready else 2), ''
        if head == 'exec' and 'curl' in args:
            return (0 if self.healthy else 7), ''
        if head == 'logs':
            return 0, self.logs
        if head == 'run' and '--rm' in args:
            if args[-1] == rc.LIST_FIELDS:
                image = args[args.index('--entrypoint') + 2]
                return 0, '\n'.join(self.new_fields if image == NEW else self.old_fields)
            image = args[args.index('--entrypoint') + 2]
            code = self.new_migrate if image == NEW else self.old_migrate
            return code, '' if code == 0 else 'psycopg.errors.UndefinedColumn: column "x" does not exist'
        if head == 'image' and args[1] == 'inspect':
            return (0 if args[-1] not in self.missing else 1), ''
        if head in ('rm', 'network'):
            return 0, ''
        raise AssertionError(args)


def go(docker, **kw):
    kw.setdefault('wait_seconds', 1)
    return rc.run_check(docker, old_image=OLD, new_image=NEW, say=lambda *_: None, sleep=lambda *_: None, **kw)


def removed(docker):
    gone = {a[-1] for a in docker.calls if a[0] == 'rm'} | {a[-1] for a in docker.calls if a[:2] == ['network', 'rm']}
    return all(name in gone for _kind, name in docker.created)


def test_all_pass_and_everything_is_cleaned_up():
    docker = FakeDocker()
    results = go(docker)
    assert [ok for _n, ok, _d in results] == [True, True, True, True, True]
    assert removed(docker)
    assert any(a[:3] == ['network', 'create', '--internal'] for a in docker.calls)     # 바깥과 연결되지 않는 네트워크
    assert not any('worker' in ' '.join(a) for a in docker.calls)                      # 일꾼은 띄우지 않는다


def test_old_migration_failure_is_reported_and_cleanup_still_runs():
    docker = FakeDocker(old_migrate=1)
    results = go(docker)
    failed = [n for n, ok, _d in results if not ok]
    assert any('옛 이미지의 마이그레이션' in n for n in failed)
    assert removed(docker)


def test_new_schema_build_failure_stops_early_and_cleans_up():
    docker = FakeDocker(new_migrate=1)
    results = go(docker)
    assert results[-1][1] is False and len(results) == 2
    assert removed(docker)


def test_db_not_ready_stops_early():
    docker = FakeDocker(db_ready=False)
    results = go(docker)
    assert results == [('임시 DB 준비', False, '')]
    assert removed(docker)


def test_unhealthy_api_and_schema_errors_in_logs_are_failures():
    docker = FakeDocker(healthy=False, logs='ERROR sqlalchemy.exc.ProgrammingError: UndefinedTable relation "foo" does not exist')
    results = {n: ok for n, ok, _d in go(docker)}
    assert results['옛 이미지 API 가 새 DB 구조에서 /health 응답'] is False
    assert results['기동 로그에 표·칸·설정 오류 없음'] is False


def test_exception_inside_still_cleans_up():
    class Boom(FakeDocker):
        def run(self, args, timeout=120, check=True):
            if args[0] == 'logs':
                raise rc.CheckError('중간 고장')
            return super().run(args, timeout, check)
    docker = Boom()
    with pytest.raises(rc.CheckError):
        go(docker)
    assert removed(docker)


def test_env_names_file_only_reads_names_and_flags_conflicts(tmp_path):
    env = tmp_path / '.env'
    env.write_text('ACOP_DATABASE_URL=postgres://secret@host/db\nACOP_BRAND_NEW=1\n# ACOP_COMMENTED=2\nOTHER=3\n', encoding='utf-8')
    assert rc.env_names(env) == {'database_url', 'brand_new'}
    results = go(FakeDocker(), env_names_files=[env])
    conflict = [(n, d) for n, ok, d in results if '새 이름이 옛 이미지를 막지 않음' in n]
    assert conflict and conflict[0][1].endswith('ACOP_BRAND_NEW')
    assert all('secret' not in d for _n, _ok, d in results)       # 값은 출력에 나오지 않는다


def test_mobility_dir_is_mounted_read_only():
    docker = FakeDocker()
    go(docker, mobility_dir='/data/mobility')
    start = next(a for a in docker.calls if a[0] == 'run' and '-d' in a and '--cpus' in a)
    assert '/data/mobility:/data/mobility/processed:ro' in start


def test_missing_old_image_fails_early_with_clear_message_and_creates_nothing():
    docker = FakeDocker()
    docker.missing = {OLD}
    with pytest.raises(rc.CheckError, match='이미지가 이 서버에 없다'):
        go(docker)
    assert docker.created == []
