"""급행 표만 바꿔도 같은 프로세스의 새 출발 계산에 갱신이 반영돼야 한다."""
import gzip
import json
import os

import pytest

from app.domains.travel_ops.instances.mobility.engine import express as EX, runtime as RT, paths
from .test_review_fixes_runtime import _write_mini_data


def write_runs(path, shift=0):
    doc = dict(stations=list('ABCD'), runs={'weekday': [
        ['T1', False, 'D', [[0, None, 36000+shift], [1, 36120+shift, 36130+shift],
            [2, 36240+shift, 36250+shift], [3, 36360+shift, None]]]]})
    with gzip.open(path, 'wt', encoding='utf8') as out:
        json.dump(doc, out)
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns+1_000_000_000))


@pytest.fixture
def source(tmp_path, monkeypatch):
    path = tmp_path / 'express.json.gz'
    monkeypatch.setattr(EX, 'FILES', {'01호선': path})
    monkeypatch.setattr(EX, '_CACHE', {})
    if hasattr(EX, '_CACHE_SIGNATURES'):
        monkeypatch.setattr(EX, '_CACHE_SIGNATURES', {})
    monkeypatch.setattr(RT, '_SINGLETON', None)
    before = paths.DATA_DIR, paths.SOURCE
    yield path
    paths._layout(*before)


def test_changed_file_is_reloaded_without_clearing_process_cache(source):
    write_runs(source)
    first = EX.load_line('01호선')
    assert first['weekday'][0][1] == 600
    write_runs(source, 300)
    second = EX.load_line('01호선')
    assert second['weekday'][0][1] == 605
    assert first['weekday'][0][1] == 600
    assert EX.load_line('01호선') is second


def test_runtime_rebuilds_when_only_express_table_changes(tmp_path, source):
    _write_mini_data(tmp_path)
    write_runs(source)
    first = RT.get_verifier(quiet=True, data_dir=tmp_path, gh_url='', seoul_key='')
    assert first._v.tt.departures('01호선', 'A', 'weekday')[0].min == 600
    assert RT.get_verifier() is first
    case = {'id': 'travel-test', 'date': '2026-10-07', 'depart_at': '10:00',
        'legs': [{'line': '01호선', 'from': 'A', 'to': 'C'}], 'no_alternatives': True}
    old = first.verify_case(case)
    assert old.legs[0].depart_min == 600 and old.arrive_min == 604
    write_runs(source, 300)
    second = RT.get_verifier()
    assert second is not first
    new = second.verify_case(case)
    assert new.legs[0].code == 'before_first'
    assert new.legs[0].depart_min is None
    at_new_first = second.verify_case(dict(case, depart_at='10:05'))
    assert at_new_first.legs[0].depart_min == 605 and at_new_first.arrive_min == 609
    assert first._v.tt.departures('01호선', 'A', 'weekday')[0].min == 600


def test_missing_table_created_later_is_not_a_permanent_empty_cache(source):
    assert EX.load_line('01호선') is None
    write_runs(source)
    assert EX.load_line('01호선')['weekday'][0][1] == 600


def test_file_removal_does_not_return_old_runs(source):
    write_runs(source)
    assert EX.load_line('01호선')
    source.unlink()
    assert EX.load_line('01호선') is None


def test_same_line_at_new_path_is_not_old_cached_source(tmp_path, source, monkeypatch):
    write_runs(source)
    assert EX.load_line('01호선')['weekday'][0][1] == 600
    replacement = tmp_path / 'new-source.json.gz'
    write_runs(replacement, 600)
    monkeypatch.setattr(EX, 'FILES', {'01호선': replacement})
    assert EX.load_line('01호선')['weekday'][0][1] == 610


def test_runtime_detects_a_previously_missing_table(tmp_path, source):
    _write_mini_data(tmp_path)
    first = RT.get_verifier(quiet=True, data_dir=tmp_path, gh_url='', seoul_key='')
    assert first._v.tt.departures('01호선', 'A', 'weekday')[0].run is None
    write_runs(source)
    second = RT.get_verifier()
    assert second is not first
    assert second._v.tt.departures('01호선', 'A', 'weekday')[0].run is not None


def test_source_changed_during_read_does_not_publish_mixed_cache(source, monkeypatch):
    write_runs(source)
    original = EX.Run
    def changed_after_read(*args, **kwargs):
        value = original(*args, **kwargs)
        write_runs(source, 300)
        return value
    # gzip 읽기가 끝나고 열차 객체를 만드는 동안 실제 파일을 바꾼다.
    monkeypatch.setattr(EX, 'Run', changed_after_read)
    with pytest.raises(RuntimeError, match='입력이 바뀌었다'):
        EX.load_line('01호선')
    assert '01호선' not in EX._CACHE


def test_source_changed_during_rebuild_keeps_previous_runtime(tmp_path, source, monkeypatch):
    from app.domains.travel_ops.instances.mobility.engine.verify_time import Timetable
    _write_mini_data(tmp_path)
    write_runs(source)
    first = RT.get_verifier(quiet=True, data_dir=tmp_path, gh_url='', seoul_key='')
    write_runs(source, 300)
    original = Timetable.load
    def changed_after_read(*args, **kwargs):
        value = original(*args, **kwargs)
        write_runs(source, 600)
        return value
    monkeypatch.setattr(Timetable, 'load', changed_after_read)
    with pytest.raises(RuntimeError, match='구성하는 사이'):
        RT.get_verifier()
    assert RT._SINGLETON is first
    assert first._v.tt.departures('01호선', 'A', 'weekday')[0].min == 600
    monkeypatch.setattr(Timetable, 'load', original)
    write_runs(source, 300)
    second = RT.get_verifier()
    assert second is not first
    assert second._v.tt.departures('01호선', 'A', 'weekday')[0].min == 605
    assert first._v.tt.departures('01호선', 'A', 'weekday')[0].min == 600


def test_corrupt_source_is_not_cached_as_permanent_missing(source):
    source.write_bytes(b'bad gzip')
    assert EX.load_line('01호선') is None
    write_runs(source)
    assert EX.load_line('01호선')['weekday'][0][1] == 600


def same_metadata_tables(source):
    """표 내용만 다른 두 파일을 같은 크기·수정 시각으로 바꾸는 통제 입력."""
    write_runs(source)
    old = source.read_bytes()
    write_runs(source, 300)
    new = source.read_bytes()
    size = max(len(old), len(new))
    source.write_bytes(old.ljust(size, b'\0'))
    saved = source.stat()

    def replace():
        source.write_bytes(new.ljust(size, b'\0'))
        os.utime(source, ns=(saved.st_atime_ns, saved.st_mtime_ns))
        current = source.stat()
        assert (current.st_mtime_ns, current.st_size, current.st_ino) == (
            saved.st_mtime_ns, saved.st_size, saved.st_ino)
        assert source.read_bytes() != old.ljust(size, b'\0')

    return replace


def test_same_metadata_content_change_reloads_cached_runs(source):
    replace = same_metadata_tables(source)
    first = EX.load_line('01호선')
    assert first['weekday'][0][1] == 600
    replace()
    assert EX.load_line('01호선')['weekday'][0][1] == 605
    assert first['weekday'][0][1] == 600


def test_same_metadata_content_change_rebuilds_runtime(tmp_path, source):
    _write_mini_data(tmp_path)
    replace = same_metadata_tables(source)
    first = RT.get_verifier(quiet=True, data_dir=tmp_path, gh_url='', seoul_key='')
    assert first._v.tt.departures('01호선', 'A', 'weekday')[0].min == 600
    replace()
    second = RT.get_verifier()
    assert second is not first
    assert second._v.tt.departures('01호선', 'A', 'weekday')[0].min == 605
    assert first._v.tt.departures('01호선', 'A', 'weekday')[0].min == 600
