"""예상하지 못한 읽기 장애(`reading_failed`)는 고객 화면에 내부 예외를 보이지 않는다.

`[2026-10-26 라우팅 감사 1번]` 로컬 접수 1건의 실패 내용이 `PermissionError: unapproved_egress` 그대로 저장됐다. `view()` 는
`fatal.detail` 을 그대로 돌려주고 웹(`intake-review.tsx`)은 그 글을 경고 문단으로 보인다. 다른 실패 코드는 이미 고객용 문장을 저장한다
(`reading_model_failed` = `READING_FAILED_TEXT`, `all_dates_in_past`). 원본 예외는 서버 로그(`exc_info`)에만 남긴다.
DB · 모델 · 공급자 호출 없음 — `test_intake_all_past_gate._run` 의 기록 대역을 그대로 쓰고, 그 대역이 덮지 않는
읽기 단계(`progress_module.sink`)에서 장애를 낸다.
"""
import logging

from app.domains.travel_ops.components.intake import pipeline
from tests.unit.travel.test_intake_all_past_gate import _run


def _boom(exc):
    def raise_(*args, **kwargs):
        raise exc
    return raise_


def test_unexpected_reading_error_stores_a_public_text_not_the_exception(monkeypatch, caplog):
    caplog.set_level(logging.WARNING, logger=pipeline.log.name)
    monkeypatch.setattr(pipeline.progress_module, "sink", _boom(PermissionError("unapproved_egress")))
    got, state, _, _ = _run(monkeypatch, None)
    assert got == "fatal"
    code, detail = state["fatal"]
    assert code == "reading_failed"
    assert detail == getattr(pipeline, "READING_ERROR_TEXT", None)
    assert "PermissionError" not in detail and "unapproved_egress" not in detail
    # 진단은 서버 로그에만 — 예외 종류가 남는다
    assert any(r.exc_info and r.exc_info[0] is PermissionError for r in caplog.records)


def test_designed_rejections_keep_their_customer_message(monkeypatch):
    """의도한 거절(`IntakeRejected`)은 지금처럼 그 코드와 고객용 문장을 그대로 남긴다(paired)."""
    monkeypatch.setattr(pipeline.progress_module, "sink",
                        _boom(pipeline.IntakeRejected("reading_model_failed", pipeline.READING_FAILED_TEXT)))
    got, state, _, _ = _run(monkeypatch, None)
    assert got == "fatal"
    assert state["fatal"] == ("reading_model_failed", pipeline.READING_FAILED_TEXT)


def test_public_reading_error_text_is_customer_wording():
    text = getattr(pipeline, "READING_ERROR_TEXT", None)
    assert text and text != pipeline.READING_FAILED_TEXT
    assert "Error" not in text and ":" not in text
