"""공표 승차 시각의 범위·완전성·입력 판을 검사한다. 실제 도착 시험은 아니다."""
from copy import deepcopy
import json
import os

import pytest

from app.domains.travel_ops.instances.mobility.engine import published_boarding as PB, runtime as RT, paths, express
from app.domains.travel_ops.instances.mobility.engine.departure_context import input_basis
from app.domains.travel_ops.instances.mobility.engine.verify_time import Timetable
from .test_review_fixes_runtime import _write_mini_data


def row(station='A', minute=600, direction='D', day='weekday'):
    return {'line': '01호선', 'station_nm': station, 'dir': direction, 'day_type': day,
            'dep_time': f'{minute // 60:02d}:{minute % 60:02d}:30', 'dest_nm': 'D',
            'fetched_at': '2026-10-01'}


def payload(table, minutes=(600, 610)):
    return {'schema_version': '1.0', 'timetable_sha256': PB.file_sha256(table), 'groups': [
        {'line': '01호선', 'station_nm': 'A', 'dir': 'D', 'day_type': 'weekday',
         'minutes': list(minutes), 'complete': True, 'source_url': 'https://example.org/timetable',
         'observed_at': '2026-10-09T13:00:00+09:00'}]}


def write(path, doc):
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf8')


@pytest.fixture
def table(tmp_path):
    path = tmp_path / 'time.jsonl'
    path.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in
                    [row(minute=600), row(minute=605), row(minute=610),
                     row('B', 605), row(minute=605, direction='U'), row(minute=605, day='holiday')]),
                    encoding='utf8')
    return path


def test_exact_published_group_filters_only_unsupported_boardings(table):
    guard = PB.PublishedBoarding(payload(table), ('test', 'a' * 64))
    before = PB.file_sha256(table)
    tt = Timetable.load(table, published_boarding=guard)
    deps = tt.departures('01호선', 'A', 'weekday')
    assert [(d.min, d.dir) for d in deps] == [(600, 'D'), (605, 'U'), (610, 'D')]
    assert deps[0].dest == 'D' and deps[0].inferred is None
    assert tt.departures('01호선', 'B', 'weekday')[0].min == 605
    assert tt.departures('01호선', 'A', 'holiday')[0].min == 605
    assert guard.summary()[0]['matched'] == 2 and guard.summary()[0]['excluded'] == 1
    assert PB.file_sha256(table) == before


def test_wanted_subset_still_validates_complete_original_source(table):
    guard = PB.PublishedBoarding(payload(table), ('test', 'a' * 64))
    tt = Timetable.load(table, wanted={('01호선', 'B')}, published_boarding=guard)
    assert len(tt.stations) == 1 and guard.summary()[0]['matched'] == 2


@pytest.mark.parametrize('minutes', [(600, 620), (600, 605, 610, 620)])
def test_missing_published_minute_fails_instead_of_inventing_train(table, minutes):
    with pytest.raises(RuntimeError, match='1대1'):
        Timetable.load(table, published_boarding=PB.PublishedBoarding(payload(table, minutes), ('test', 'a' * 64)))


def test_duplicate_minute_with_conflicting_destination_is_not_arbitrarily_chosen(table):
    with table.open('a', encoding='utf8') as stream:
        stream.write('\n' + json.dumps(dict(row(minute=600), dest_nm='C'), ensure_ascii=False))
    with pytest.raises(RuntimeError, match='1대1'):
        Timetable.load(table, published_boarding=PB.PublishedBoarding(payload(table), ('test', 'a' * 64)))


def test_changed_base_is_not_silently_filtered(table):
    doc = payload(table)
    with table.open('a', encoding='utf8') as stream:
        stream.write('\n')
    with pytest.raises(RuntimeError, match='원시간표 판'):
        Timetable.load(table, published_boarding=PB.PublishedBoarding(doc, ('test', 'a' * 64)))


@pytest.mark.parametrize(('field', 'value'), [
    ('minutes', []), ('minutes', [610, 600]), ('minutes', [600, 600]),
    ('minutes', [True]), ('minutes', [600.0]), ('minutes', [-1]), ('minutes', [1801]),
    ('complete', False), ('source_url', 'http://example.org'),
    ('observed_at', '2026-10-09'), ('day_type', 'today'), ('dir', 'unknown'),
    ('station_nm', ' A')])
def test_invalid_or_partial_source_does_not_enable_filter(table, field, value):
    doc = payload(table)
    doc['groups'][0][field] = value
    with pytest.raises(ValueError):
        PB.PublishedBoarding(doc, ('test', 'a' * 64))


def test_duplicate_groups_fail(table):
    doc = payload(table)
    doc['groups'].append(deepcopy(doc['groups'][0]))
    with pytest.raises(ValueError, match='중복'):
        PB.PublishedBoarding(doc, ('test', 'a' * 64))


@pytest.fixture
def mini(tmp_path, monkeypatch):
    _write_mini_data(tmp_path)
    before = paths.DATA_DIR, paths.SOURCE
    monkeypatch.setattr(RT, '_SINGLETON', None)
    monkeypatch.setattr(express, 'FILES', {})
    directory = tmp_path / 'travel/processed/mobility'
    yield directory, tmp_path
    paths._layout(*before)


def enable(directory, remove=600):
    table = directory / 'timetable_v1.jsonl'
    doc = payload(table, tuple(m for m in range(360, 1321, 60) if m != remove))
    write(directory / PB.FILE, doc)
    return doc


def test_runtime_new_source_reloads_and_invalidates_saved_departure_basis(mini):
    directory, root = mini
    first = RT.get_verifier(data_dir=root, gh_url='', seoul_key='', quiet=True)
    old_basis = input_basis(first)
    assert 600 in [d.min for d in first._v.tt.departures('01호선', 'A', 'weekday')]
    enable(directory)
    second = RT.get_verifier()
    assert first is not second and input_basis(second) != old_basis
    assert 600 not in [d.min for d in second._v.tt.departures('01호선', 'A', 'weekday')]
    assert second.stats['published_boarding'][0]['excluded'] == 1
    assert first.stats['timetable_age_basis'] == second.stats['timetable_age_basis']
    assert first.stats['timetable_age_days'] == second.stats['timetable_age_days']
    ev = second._v._ev_tt('01호선', 'A', 'weekday', '승차 후보')
    assert '|boarding:' in ev['source_id'] and 'https://example.org/timetable' in ev['claim']
    assert second._v.tt.fetched_at == first._v.tt.fetched_at


def test_same_size_and_mtime_content_replacement_is_detected(mini):
    directory, root = mini
    doc = enable(directory)
    first = RT.get_verifier(data_dir=root, gh_url='', seoul_key='', quiet=True)
    source = directory / PB.FILE
    stat = source.stat()
    doc['groups'][0]['observed_at'] = '2026-10-09T13:01:00+09:00'
    write(source, doc)
    assert source.stat().st_size == stat.st_size
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert 'published_boarding' in first.changed_sources()
    second = RT.get_verifier()
    assert second is not first and input_basis(second) != input_basis(first)


def test_bad_replacement_keeps_old_singleton_and_raises(mini):
    directory, root = mini
    enable(directory)
    first = RT.get_verifier(data_dir=root, gh_url='', seoul_key='', quiet=True)
    (directory / PB.FILE).write_text('{bad json', encoding='utf8')
    with pytest.raises(ValueError):
        RT.get_verifier()
    assert RT._SINGLETON is first


def test_removal_does_not_restore_known_unverified_boardings(mini):
    directory, root = mini
    enable(directory)
    first = RT.get_verifier(data_dir=root, gh_url='', seoul_key='', quiet=True)
    (directory / PB.FILE).unlink()
    with pytest.raises(RuntimeError, match='사라졌다'):
        RT.get_verifier()
    assert RT._SINGLETON is first
    assert 600 not in [d.min for d in first._v.tt.departures('01호선', 'A', 'weekday')]


def test_reading_source_changes_during_build_fails(mini, monkeypatch):
    directory, root = mini
    doc = enable(directory)
    original = Timetable.load
    def load_then_replace(*args, **kwargs):
        value = original(*args, **kwargs)
        doc['groups'][0]['observed_at'] = '2026-10-09T13:01:00+09:00'
        write(directory / PB.FILE, doc)
        return value
    monkeypatch.setattr(Timetable, 'load', load_then_replace)
    with pytest.raises(RuntimeError, match='구성하는 사이'):
        RT.build_verifier(data_dir=root, gh_url='', seoul_key='', quiet=True)


def test_manifest_registered_source_is_required_even_on_cold_start(mini):
    from app.domains.travel_ops.instances.mobility.engine import datacheck
    directory, root = mini
    enable(directory)
    paths.configure(root)
    files = [{'path': p.relative_to(directory).as_posix(), 'bytes': p.stat().st_size,
              'sha256': PB.file_sha256(p)} for p in datacheck._paths().values() if p.exists()]
    write(directory / datacheck.GIT_MANIFEST_NAME, {'files': files})
    assert datacheck.check()['ok']
    (directory / PB.FILE).unlink()
    check = datacheck.check()
    assert not check['ok'] and any(r['file'] == 'published_boarding' for r in check['mismatched'])
    with pytest.raises(RuntimeError, match='판 명세'):
        RT.build_verifier(data_dir=root, gh_url='', seoul_key='', quiet=True)
