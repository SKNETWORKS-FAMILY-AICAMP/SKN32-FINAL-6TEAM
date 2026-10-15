"""안내 저장 검사는 실제 급행 내용만 읽고 무거운 적재와 도착 조회를 하지 않는다."""
import pytest

from app.domains.travel_ops.instances.mobility import wiring
from app.domains.travel_ops.instances.mobility.engine import express as EX
from app.domains.travel_ops.instances.mobility.engine.departure_context import express_version
from .test_express_source_reload_v1 import source, write_runs  # noqa: F401


def test_real_content_is_checked_without_runtime_reload(source, monkeypatch):
    wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(wiring.engine_runtime, 'get_verifier', lambda **kw: pytest.fail('시간표 재적재 금지'))
    write_runs(source)
    basis = {'timetable_built_at': 'fixture', 'rules_version': 'fixture',
             'express_version': express_version(EX.source_signatures())}
    assert wiring.validate_departure_basis(basis) is True
    write_runs(source, 300)
    assert wiring.validate_departure_basis(basis) is False


@pytest.mark.parametrize('basis', [None, {}, [], {'express_version': 'a'*64},
    {'timetable_built_at': 'fixture', 'rules_version': 'fixture', 'express_version': None},
    {'timetable_built_at': 'fixture', 'rules_version': 'fixture', 'express_version': 'z'*64}])
def test_invalid_observed_basis_is_not_success(basis):
    wiring._STATE.update(mode='enabled', kw={})
    with pytest.raises(ValueError):
        wiring.validate_departure_basis(basis)


def test_source_read_error_is_not_hidden(monkeypatch):
    wiring._STATE.update(mode='enabled', kw={})
    def broken():
        raise OSError('controlled read failure')
    monkeypatch.setattr(EX, 'source_signatures', broken)
    with pytest.raises(OSError):
        wiring.validate_departure_basis({'timetable_built_at': 'fixture', 'rules_version': 'fixture',
                                         'express_version': 'a'*64})


def test_untracked_manual_runtime_compatibility_does_not_read_files(monkeypatch):
    wiring._STATE.update(mode='enabled', kw={})
    monkeypatch.setattr(EX, 'source_signatures', lambda: pytest.fail('추적 없는 문맥의 파일 조회 금지'))
    assert wiring.validate_departure_basis({'timetable_built_at': 'fixture', 'rules_version': 'fixture'}) is True


def test_disabled_engine_does_not_confirm_basis():
    wiring._STATE.update(mode='disabled', kw=None)
    with pytest.raises(wiring.MobilityUnavailable):
        wiring.validate_departure_basis({'timetable_built_at': 'fixture', 'rules_version': 'fixture'})
