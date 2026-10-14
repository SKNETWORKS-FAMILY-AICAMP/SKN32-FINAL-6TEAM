"""이미지 정리 규칙을 흉내 낸 도커로 검사한다(실제 도커를 건드리지 않는다)."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('image_retention',
    Path(__file__).resolve().parents[3] / 'deploy/image_retention.py')
ret = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ret)

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def at(days_ago):
    return NOW - timedelta(days=days_ago)


class FakeDocker:
    def __init__(self, images, used=()):
        # images: [(repo, tag, id, created)]
        self.images = [dict(repo=r, tag=t, id=i, created=c) for r, t, i, c in images]
        self.used = set(used)
        self.calls = []
        self.last_tag = {}

    def run(self, args, timeout=120):
        self.calls.append(args)
        if args[0] == 'images':
            return ''.join(f"{i['repo']}\t{i['tag']}\t{i['id']}\t{i['created'].strftime('%Y-%m-%d %H:%M:%S +0000 UTC')}\n"
                           for i in self.images)
        if args[0] == 'ps':
            return 'c1\n' if self.used else ''
        if args[0] == 'inspect':
            return '\n'.join(self.used) + '\n'
        if args[:2] == ['image', 'inspect']:
            stamp = self.last_tag.get(args[-1], NOW)
            # 실제 docker inspect 가 시각을 찍는 모양(Go 기본 출력, 소수점 아래 9자리 + 영역 이름)
            return stamp.strftime('%Y-%m-%d %H:%M:%S.123456789 +0000 UTC')
        if args[0] == 'tag':
            repo, tag = args[1].split(':')
            src = next(i for i in self.images if i['repo'] == repo and i['tag'] == tag)
            alias = args[2].split(':')[1]
            self.images = [i for i in self.images if not (i['repo'] == repo and i['tag'] == alias)]
            self.images.append(dict(src, tag=alias))
            return ''
        if args[0] == 'rmi':
            repo, tag = args[1].split(':')
            hit = [i for i in self.images if i['repo'] == repo and i['tag'] == tag]
            if not hit:
                raise ret.RetentionError('없음')
            others = [i for i in self.images if i['id'] == hit[0]['id'] and i is not hit[0]]
            if hit[0]['id'] in self.used and not others:
                raise ret.RetentionError('사용 중')
            self.images.remove(hit[0])
            return ''
        if args[:2] == ['image', 'prune']:
            return ''
        if args[:2] == ['builder', 'prune']:
            return ''
        raise AssertionError(args)

    def tags(self, repo):
        return sorted(i['tag'] for i in self.images if i['repo'] == repo)


def sha(n):
    return f'{n:010x}'


def app_images(spec_days):
    rows = []
    for n, days in spec_days.items():
        for repo in ('tripilot-api', 'tripilot-web', 'tripilot-admin'):
            rows.append((repo, sha(n), f'sha256:{repo}-{n}', at(days)))
    return rows


def run(docker, **kw):
    kw.setdefault('app_repos', ['tripilot-api', 'tripilot-web', 'tripilot-admin'])
    kw.setdefault('now', NOW)
    kw.setdefault('say', lambda *_: None)
    return ret.run_retention(docker, **kw)


def test_keeps_recent_three_and_one_per_month_and_deletes_the_rest():
    days = {1: 1, 2: 2, 3: 3, 4: 4, 5: 12, 6: 20, 7: 40, 8: 45, 9: 75, 10: 400}
    docker = FakeDocker(app_images(days))
    run(docker, apply=True, keep_months=3)
    kept = {t for t in docker.tags('tripilot-api') if not t.startswith('keep-')}
    # 최근 3(1·2·3) + 달별 하나씩: 10월=1번(최근과 겹침) · 9월=6번(20일 전) · 8월=8번(45일 전)
    assert sha(1) in kept and sha(2) in kept and sha(3) in kept
    assert sha(10) not in kept and sha(9) not in kept          # 3개월 창 밖
    # 같은 커밋은 저장소가 달라도 함께 남고 함께 지워진다
    assert kept == {t for t in docker.tags('tripilot-web') if not t.startswith('keep-')}
    assert kept == {t for t in docker.tags('tripilot-admin') if not t.startswith('keep-')}
    assert any(t.startswith('keep-2026-') for t in docker.tags('tripilot-api'))


def test_never_deletes_current_tag_running_image_or_foreign_names():
    rows = app_images({1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6})
    rows += [('tripilot-api', 'local', 'sha256:tripilot-api-6', at(6)),
             ('tripilot-api', 'manual-rollback', 'sha256:man', at(90)),
             ('tripilot-chat-rollback-api', sha(9), 'sha256:other', at(99)),
             ('jikimi-docker-llm', 'latest', 'sha256:jikimi', at(99))]
    docker = FakeDocker(rows, used={'sha256:tripilot-web-5'})
    run(docker, apply=True, keep_months=0, protected_tags=[sha(6)])
    api = docker.tags('tripilot-api')
    assert sha(6) in api and sha(5) in api            # 현재 배포 태그 · 실행 중 컨테이너가 쓰는 묶음
    assert 'local' in api and 'manual-rollback' in api
    assert docker.tags('tripilot-chat-rollback-api') == [sha(9)]
    assert docker.tags('jikimi-docker-llm') == ['latest']
    assert sha(4) not in api and sha(4) not in docker.tags('tripilot-web')


def test_monthly_pick_uses_successful_deploys_only_when_log_exists():
    rows = app_images({1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 40, 7: 41})
    good = {sha(7): at(41)}       # 9월에 성공한 것은 7번뿐 — 6번은 빌드만 되고 실패
    docker = FakeDocker(rows)
    run(docker, apply=True, keep_months=2, good={**good, sha(1): at(1), sha(2): at(2), sha(3): at(3)})
    api = docker.tags('tripilot-api')
    assert sha(7) in api and sha(6) not in api
    assert 'keep-2026-09' in api


def test_alias_moves_to_newer_pick_and_old_month_alias_is_dropped():
    rows = app_images({1: 1, 2: 2, 3: 3, 4: 4, 5: 5})
    rows += [('tripilot-api', 'keep-2026-10', 'sha256:tripilot-api-5', at(5)),
             ('tripilot-api', 'keep-2025-01', 'sha256:tripilot-api-5', at(5))]
    docker = FakeDocker(rows)
    run(docker, apply=True, keep_months=2)
    api = docker.tags('tripilot-api')
    assert 'keep-2026-10' in api and 'keep-2025-01' not in api
    alias = next(i for i in docker.images if i['repo'] == 'tripilot-api' and i['tag'] == 'keep-2026-10')
    assert alias['id'] == 'sha256:tripilot-api-1'        # 이달 가장 새 것으로 옮겨 붙음


def test_dry_run_changes_nothing():
    docker = FakeDocker(app_images({n: n for n in range(1, 9)}))
    before = list(docker.images)
    out = run(docker, apply=False)
    assert docker.images == before
    assert out['plan']['delete']
    assert not any(c[0] in ('rmi', 'tag') for c in docker.calls)


def recovery_state(tmp_path, entries):
    """entries: [(token, days_ago)] — 상태 폴더와 이미지 목록을 함께 만든다."""
    rows = []
    for token, days in entries:
        epoch = int((NOW - timedelta(days=days)).timestamp())
        folder = tmp_path / f'migration-safety-{sha(epoch % 1000)}-{epoch}'
        folder.mkdir()
        records = {}
        for service in ('tripilot-api', 'tripilot-worker', 'tripilot-web'):
            tag = f'{token}-{service}'
            records[service] = {'recovery_tag': f'tripilot-recovery:{tag}'}
            rows.append(('tripilot-recovery', tag, f'sha256:{token}-{service}', at(days + 1)))
        (folder / 'baseline.json').write_text(json.dumps(records))
        (folder / 'recovery.compose.json').write_text('{}')
    return rows


def test_recovery_keeps_newest_sets_and_removes_expired_sets_and_their_state(tmp_path):
    tokens = [f'{n:032x}' for n in range(1, 8)]
    rows = recovery_state(tmp_path, [(t, i) for i, t in enumerate(tokens)])
    docker = FakeDocker(rows)
    run(docker, apply=True, app_repos=['tripilot-api'], recovery_repo='tripilot-recovery',
        state_dir=tmp_path, recovery_keep=2, min_age_hours=2)
    left = {t.split('-')[0] for t in docker.tags('tripilot-recovery')}
    assert left == {tokens[0], tokens[1]}
    assert len(list(tmp_path.glob('migration-safety-*'))) == 2


def test_recovery_in_progress_set_is_never_removed_even_when_over_limit(tmp_path):
    tokens = [f'{n:032x}' for n in range(1, 5)]
    rows = recovery_state(tmp_path, [(t, d) for t, d in zip(tokens, (0.01, 0.02, 0.03, 5))])
    docker = FakeDocker(rows)
    run(docker, apply=True, app_repos=['tripilot-api'], recovery_repo='tripilot-recovery',
        state_dir=tmp_path, recovery_keep=1, min_age_hours=2)
    left = {t.split('-')[0] for t in docker.tags('tripilot-recovery')}
    assert left == set(tokens[:3])        # 2시간 안의 세트는 개수 한도를 넘어도 남는다


def test_recovery_without_state_folder_uses_last_tag_time_and_is_conservative(tmp_path):
    old, fresh = f'{1:032x}', f'{2:032x}'
    rows = [('tripilot-recovery', f'{old}-tripilot-api', 'sha256:old', at(900)),
            ('tripilot-recovery', f'{fresh}-tripilot-api', 'sha256:fresh', at(900)),   # 이미지는 오래됐지만 방금 이름표
            ('tripilot-recovery', f'{3:032x}-tripilot-api', 'sha256:keep1', at(1)),
            ('tripilot-recovery', f'{4:032x}-tripilot-api', 'sha256:keep2', at(1))]
    docker = FakeDocker(rows)
    docker.last_tag = {'sha256:old': at(60), 'sha256:fresh': NOW - timedelta(minutes=5),
                       'sha256:keep1': NOW, 'sha256:keep2': NOW - timedelta(minutes=1)}
    run(docker, apply=True, app_repos=['tripilot-api'], recovery_repo='tripilot-recovery',
        state_dir=tmp_path, recovery_keep=1, min_age_hours=2)
    left = {t.split('-')[0] for t in docker.tags('tripilot-recovery')}
    assert f'{2:032x}' in left            # 방금 붙인 이름표는 이미지가 오래돼도 지우지 않는다
    assert f'{1:032x}' not in left


def test_failed_removal_does_not_stop_the_rest():
    rows = app_images({n: n for n in range(1, 8)})
    docker = FakeDocker(rows)
    original = docker.run

    def flaky(args, timeout=120):
        if args[0] == 'rmi' and args[1] == f'tripilot-api:{sha(5)}':
            raise ret.RetentionError('사용 중')
        return original(args, timeout)
    docker.run = flaky
    out = run(docker, apply=True, keep_months=0)
    assert out['failed'] == 1
    assert sha(6) not in docker.tags('tripilot-api') and sha(7) not in docker.tags('tripilot-api')


def test_read_deploy_log_extracts_successful_deploys(tmp_path):
    log = tmp_path / 'deploy.log'
    log.write_text('2026-10-13 09:00:01 시작 aaaaaaaaaa (x)\n2026-10-13 09:05:00 반영 완료 aaaaaaaaaa (이전 bbbbbbbbbb)\n'
                   '2026-10-13 10:00:00 ★새 이미지 반영 실패 cccccccccc\n', encoding='utf-8')
    good = ret.read_deploy_log(log)
    assert list(good) == ['aaaaaaaaaa'] and good['aaaaaaaaaa'].day == 13
    assert ret.read_deploy_log(tmp_path / 'none.log') == {}


def test_release_dirs_keep_kept_and_protected_only(tmp_path):
    for name in ('a' * 40, 'b' * 40, 'c' * 40, 'd' * 40):
        (tmp_path / name).mkdir()
    removed = ret.prune_release_dirs(tmp_path, ['a' * 12], ['b' * 40], True, lambda *_: None)
    assert sorted(removed) == ['c' * 40, 'd' * 40]
    assert sorted(p.name for p in tmp_path.iterdir()) == ['a' * 40, 'b' * 40]


def test_recent_months_wraps_year():
    assert ret.recent_months(datetime(2026, 2, 3, tzinfo=timezone.utc), 4) == ['2026-02', '2026-01', '2025-12', '2025-11']


@pytest.mark.parametrize('text', ['2026-10-14 12:00:00 +0900 KST', '2026-10-14 12:00:00.123456789 +0900 KST',
                                  '2026-10-14T12:00:00.5+09:00', '2026-10-14T03:00:00Z'])
def test_parse_time_reads_every_docker_format(text):
    assert ret.parse_time(text) == datetime(2026, 10, 14, 3, 0, tzinfo=timezone.utc)


def test_unreadable_age_is_kept_and_reported(tmp_path):
    rows = [('tripilot-recovery', f'{1:032x}-tripilot-api', 'sha256:x', at(9)),
            ('tripilot-recovery', f'{2:032x}-tripilot-api', 'sha256:y', at(9)),
            ('tripilot-recovery', f'{3:032x}-tripilot-api', 'sha256:z', at(9))]
    docker = FakeDocker(rows)
    original = docker.run
    docker.run = lambda args, timeout=120: ('없음' if args[:2] == ['image', 'inspect'] else original(args, timeout))
    lines = []
    run(docker, apply=True, app_repos=['tripilot-api'], recovery_repo='tripilot-recovery', state_dir=tmp_path,
        recovery_keep=1, say=lines.append)
    assert len(docker.tags('tripilot-recovery')) == 3
    assert any('나이를 못 읽은' in line for line in lines)


def test_builder_cache_prune_runs_only_when_asked_and_only_on_apply():
    docker = FakeDocker(app_images({1: 1}))
    run(docker, apply=True)
    assert not any(c[0] == 'builder' for c in docker.calls)
    run(docker, apply=False, builder_keep_gb=20)
    assert not any(c[0] == 'builder' for c in docker.calls)
    run(docker, apply=True, builder_keep_gb=20)
    assert ['builder', 'prune', '-f', '--keep-storage', '20GB'] in docker.calls
