"""식당 확인의 최신 작업·종료·등록 경계. 이번 요청에서는 작성만 하고 실행하지 않는다."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.travel_ops.components.intake import dining_review
from app.domains.travel_ops.components.intake import pipeline
from app.domains.travel_ops.components.intake import review as review_module
from app.domains.travel_ops.instances.dining import judge
from app.domains.travel_ops.instances.dining.agent import AgentResult


NOW = datetime(2026, 10, 16, 3, tzinfo=timezone.utc)


def meal_review():
    return {"revision": 2, "ready": True, "items": [
        {"id": "0-1", "kind": "dining", "title": "서울 점심", "date": "2026-10-26", "starts_at": "12:00",
         "ends_at": "13:00", "status": "keep", "can_lock": True, "place": {"name": "서울 식당"},
         "rows": [{"row": "hours", "result": "unknown"}]}], "moves": []}


class Conn:
    def __init__(self):
        self.locked = False
        self.records = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @contextmanager
    def transaction(self):
        previous = self.locked
        try:
            yield
        finally:
            self.locked = previous

    def cursor(self):
        return self

    def execute(self, sql, params=()):
        self.records.append((sql, params))


@pytest.fixture
def storage(monkeypatch):
    conn = Conn()
    saved = {"payload": meal_review(), "state": ("review", 2)}

    def lock(c, tenant, intake):
        assert c is conn and (tenant, intake) == ("tenant", "intake")
        conn.locked = True
        return saved["state"]

    def load(c, tenant, intake, revision):
        assert conn.locked, "작업 토큰을 읽기 전에 같은 접수 행부터 잠가야 한다"
        assert (tenant, intake) == ("tenant", "intake")
        if revision != 2:
            return None                                  # 검사 계산이 앞 판(`previous_revision`)을 읽는 것은 정상이다

        return deepcopy(saved["payload"])

    def store(c, tenant, intake, revision, payload):
        assert conn.locked
        saved["payload"] = deepcopy(payload)

    monkeypatch.setattr(review_module, "intake_state", lock)
    monkeypatch.setattr(review_module, "load", load)
    monkeypatch.setattr(review_module, "store", store)
    return conn, saved


def prepare(storage, *, enabled=True):
    conn, saved = storage
    return dining_review.prepare(conn, "tenant", "intake", 2, saved["payload"], enabled=enabled, now=NOW)


def test_prepare_saves_pending_before_it_can_be_registered(storage):
    payload = prepare(storage)
    assert payload["dining_judge"]["status"] == "pending"
    assert payload["dining_judge"]["revision"] == 2
    assert payload["dining_judge"]["run_id"]
    issue = dining_review.registration_issue(payload)
    assert (issue["status"], issue["code"]) == (409, "intake_dining_check_pending")


def test_each_revalidation_replaces_the_token_and_rejects_the_older_worker(storage):
    conn, _ = storage
    first = prepare(storage)
    second = prepare(storage)
    assert first["dining_judge"]["run_id"] != second["dining_judge"]["run_id"]
    assert dining_review.begin(conn, "tenant", "intake", 2, first["dining_judge"]["run_id"], now=NOW) is None
    running = dining_review.begin(conn, "tenant", "intake", 2, second["dining_judge"]["run_id"], now=NOW)
    assert running["dining_judge"]["status"] == "running"


def test_refresh_turns_expired_pending_into_durable_failure(storage):
    conn, saved = storage
    payload = prepare(storage)
    expired = datetime.fromisoformat(payload["dining_judge"]["deadline_at"]) + timedelta(seconds=1)
    refreshed = dining_review.refresh(conn, "tenant", "intake", 2, payload, now=expired)
    assert refreshed["dining_judge"]["status"] == "failed"
    assert saved["payload"]["dining_judge"]["error_code"] == "dining_judge_deadline_exceeded"
    # `[2026-10-16 사용자 결정]` 실패는 「확인 못 함」 — 다시 시도는 두되 등록은 막지 않는다
    assert dining_review.registration_issue(refreshed) is None


def test_a_missing_deadline_cannot_leave_a_new_review_pending_forever(storage):
    conn, saved = storage
    payload = prepare(storage)
    saved["payload"]["dining_judge"]["deadline_at"] = None
    refreshed = dining_review.refresh(conn, "tenant", "intake", 2, payload, now=NOW)
    assert refreshed["dining_judge"]["status"] == "failed"
    assert refreshed["dining_judge"]["error_code"] == "dining_judge_state_invalid"


def test_all_meal_days_fit_in_the_deadline(storage):
    conn, saved = storage
    second = deepcopy(saved["payload"]["items"][0])
    second.update(id="0-2", date="2026-10-27")
    saved["payload"]["items"].append(second)
    payload = dining_review.prepare(conn, "tenant", "intake", 2, saved["payload"], enabled=True,
                                    now=NOW, deadline_s=30)
    assert datetime.fromisoformat(payload["dining_judge"]["deadline_at"]) >= NOW + timedelta(seconds=60)


@pytest.mark.parametrize("enabled,has_meals", [(False, True), (True, False)])
def test_disabled_and_no_meal_reviews_keep_existing_registration_behavior(storage, enabled, has_meals):
    _, saved = storage
    if not has_meals:
        saved["payload"]["items"] = []
    payload = prepare(storage, enabled=enabled)
    assert payload["dining_judge"]["status"] == "disabled"
    assert dining_review.registration_issue(payload) is None


def test_old_ready_false_and_unverified_agent_prose_do_not_become_a_new_registration_gate():
    payload = meal_review()
    payload["ready"] = False
    payload["items"][0]["rows"].append({"row": "dietary", "result": "bad", "by": "agent",
                                          "agent": {"verdict": "bad", "evidence": []}})
    assert dining_review.registration_issue(payload) is None


@pytest.mark.parametrize("verdict,required,want", [("bad", True, True), ("bad", False, False),
                                                  ("unknown", True, False), ("warn", True, False)])
def test_only_validated_required_bad_rows_block_registration(verdict, required, want):
    payload = meal_review()
    payload["items"][0]["rows"].append(
        {"row": "dietary", "result": verdict, "by": "agent", "text": "식사 조건 확인",
         "agent": {"check": "dietary", "verdict": verdict, "validated": True, "required": required,
                   "evidence": [{"tool": "check_attributes", "path": "attributes.halal.state", "value": "no"}]}})
    issue = dining_review.registration_issue(payload)
    assert bool(issue) is want
    if want:
        assert (issue["status"], issue["code"]) == (422, "intake_dining_conditions_unmet")
        assert issue["detail"]["items"][0]["item_id"] == "0-1"


def test_a_worker_cannot_overwrite_another_run_after_the_same_revision_is_revalidated(storage, monkeypatch):
    conn, saved = storage
    old = dining_review.prepare(conn, "tenant", "intake", 2, saved["payload"], enabled=True,
                                now=datetime.now(timezone.utc))
    old_token = old["dining_judge"]["run_id"]

    def decide(plan, **kw):
        replacement = dining_review.prepare(conn, "tenant", "intake", 2, saved["payload"], enabled=True,
                                             now=datetime.now(timezone.utc))
        assert replacement["dining_judge"]["run_id"] != old_token
        return AgentResult(items=[], skipped=[], stats={}, failure="model_failed")

    monkeypatch.setattr(judge, "judge_day", decide)
    result = judge.run(lambda: conn, tenant_id="tenant", intake_id="intake", revision=2, review=old,
                       notes="", chat=None, model="fake", tools_factory=lambda c: None)
    assert result["stale"] == 1
    assert saved["payload"]["dining_judge"]["status"] == "pending"
    assert saved["payload"]["dining_judge"]["run_id"] != old_token
    assert any(params[5] == "_stale" for _, params in conn.records)


@pytest.mark.parametrize("case", ["missing", "validation", "malformed", "exception"])
def test_missing_or_invalid_required_checks_and_model_exceptions_end_as_failed(storage, monkeypatch, case):
    conn, saved = storage
    payload = dining_review.prepare(conn, "tenant", "intake", 2, saved["payload"], enabled=True,
                                    now=datetime.now(timezone.utc))

    def decide(plan, **kw):
        assert conn.locked is False, "모델을 기다리는 동안 접수 행 잠금을 잡지 않는다"
        if case == "exception":
            raise RuntimeError("model unavailable")
        if case == "malformed":
            return AgentResult(items=[{"item_id": "0-1", "checks": "invalid"}], skipped=[], stats={})
        checks = [{"check": "found", "verdict": "unknown", "evidence": []}]
        if case == "validation":
            checks.append({"check": "open_at", "verdict": "unknown", "evidence": [],
                           "failure": "evidence_other_time"})
        return AgentResult(items=[{"item_id": "0-1", "checks": checks}], skipped=[], stats={})

    monkeypatch.setattr(judge, "judge_day", decide)
    judge.run(lambda: conn, tenant_id="tenant", intake_id="intake", revision=2, review=payload,
              notes="", chat=None, model="fake", tools_factory=lambda c: None)
    assert saved["payload"]["dining_judge"]["status"] == "failed"
    assert saved["payload"]["dining_judge"]["blocks_registration"] is False      # 실패는 「확인 못 함」 — 등록은 막지 않는다
    assert dining_review.registration_issue(saved["payload"]) is None


def test_fresh_validated_availability_bad_is_visible_and_required_even_if_the_model_calls_it_optional():
    payload = meal_review()
    payload["items"][0]["rows"] = [{"row": "hours", "result": "ok", "text": "기존 영업 확인"}]
    merged, changed = judge.merge(payload, {"0-1": [
        {"check": "open_at", "verdict": "bad", "required": False, "validated": True,
         "evidence": [{"tool": "check_open_at", "call_id": "c1", "path": "verdict", "value": "bad"}]}]})
    row = merged["items"][0]["rows"][0]
    assert changed == 1 and row["result"] == "bad" and row["rule_result"] == "ok"
    assert row["requirement"] == "required" and row["blocks_registration"] is True
    assert dining_review.registration_issue(merged)["code"] == "intake_dining_conditions_unmet"


def test_preference_bad_is_shown_as_warning_without_changing_ready():
    payload, _ = judge.merge(meal_review(), {"0-1": [
        {"check": "payment", "verdict": "bad", "required": False, "validated": True,
         "evidence": [{"tool": "check_attributes", "call_id": "c1", "path": "attributes.card.state", "value": "no"}]}]})
    row = payload["items"][0]["rows"][-1]
    assert row["result"] == "warn" and row["requirement"] == "preference"
    assert row["blocks_registration"] is False and payload["ready"] is True
    assert dining_review.registration_issue(payload) is None


def test_complete_unknown_checks_release_only_the_lifecycle_gate(storage, monkeypatch):
    conn, saved = storage
    payload = dining_review.prepare(conn, "tenant", "intake", 2, saved["payload"], enabled=True,
                                    now=datetime.now(timezone.utc))
    result = AgentResult(items=[{"item_id": "0-1", "checks": [
        {"check": "found", "verdict": "unknown", "evidence": []},
        {"check": "open_at", "verdict": "unknown", "evidence": []}]}], skipped=[], stats={})
    monkeypatch.setattr(judge, "judge_day", lambda *a, **kw: result)
    judge.run(lambda: conn, tenant_id="tenant", intake_id="intake", revision=2, review=payload,
              notes="", chat=None, model="fake", tools_factory=lambda c: None)
    assert saved["payload"]["dining_judge"]["status"] == "completed"
    assert saved["payload"]["dining_judge"]["blocks_registration"] is False
    assert dining_review.registration_issue(saved["payload"]) is None


def test_changed_same_revision_input_does_not_receive_the_old_result(storage):
    conn, saved = storage
    payload = prepare(storage)
    token = payload["dining_judge"]["run_id"]
    dining_review.begin(conn, "tenant", "intake", 2, token, now=NOW)
    saved["payload"]["items"][0]["starts_at"] = "13:00"
    applied = []
    finished = dining_review.finish(conn, "tenant", "intake", 2, token, now=NOW,
                                    update=lambda current: applied.append(current) or current)
    assert finished["dining_judge"]["status"] == "failed"
    assert finished["dining_judge"]["error_code"] == "dining_judge_input_changed" and applied == []


def test_force_review_prepares_the_new_token_before_returning(storage, monkeypatch):
    import app.core.settings as settings_module
    from app.domains.travel_ops.components.team_hooks import dining_ledger

    from app.domains.travel_ops.components.intake import risks
    monkeypatch.setattr(risks, "decorate", lambda conn, **kw: kw["review"])
    conn, saved = storage
    previous = prepare(storage)["dining_judge"]["run_id"]
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: lambda *a, **kw: None)
    monkeypatch.setattr(settings_module, "dining_agent_judge", lambda: {"deadline_s": 30})
    monkeypatch.setattr(review_module, "build", lambda *a, **kw: meal_review())
    payload, error = pipeline._review_of(conn, "tenant", "intake", 2, [{"transcript": "할랄 필수"}], [], force=True)
    assert error is None and payload["dining_judge"]["status"] == "pending"
    assert payload["dining_judge"]["run_id"] != previous
    assert saved["payload"]["dining_judge"]["run_id"] == payload["dining_judge"]["run_id"]
    assert payload["dining_judge"]["input_fingerprint"] == dining_review.fingerprint(payload, "할랄 필수")


def test_loading_an_old_cached_review_does_not_create_a_new_gate(storage, monkeypatch):
    from app.domains.travel_ops.components.intake import risks
    monkeypatch.setattr(risks, "decorate", lambda conn, **kw: kw["review"])
    conn, _ = storage
    payload, error = pipeline._review_of(conn, "tenant", "intake", 2, [], [])
    assert error is None and "dining_judge" not in payload


def test_changed_input_after_completion_is_not_treated_as_current_validation(storage):
    conn, saved = storage
    payload = prepare(storage)
    dining_review.begin(conn, "tenant", "intake", 2, payload["dining_judge"]["run_id"], now=NOW)
    complete = dining_review.finish(conn, "tenant", "intake", 2, payload["dining_judge"]["run_id"], now=NOW)
    saved["payload"]["items"][0]["place"]["name"] = "다른 서울 식당"
    refreshed = dining_review.refresh(conn, "tenant", "intake", 2, complete, now=NOW)
    assert refreshed["dining_judge"]["status"] == "failed"
    assert refreshed["dining_judge"]["error_code"] == "dining_judge_input_changed"


def test_result_after_deadline_cannot_merge_new_rows(storage):
    conn, saved = storage
    payload = prepare(storage)
    token = payload["dining_judge"]["run_id"]
    dining_review.begin(conn, "tenant", "intake", 2, token, now=NOW)
    applied = []
    expired = datetime.fromisoformat(payload["dining_judge"]["deadline_at"]) + timedelta(seconds=1)
    finished = dining_review.finish(conn, "tenant", "intake", 2, token, now=expired,
                                    update=lambda current: applied.append(current) or current)
    assert finished["dining_judge"]["status"] == "failed"
    assert finished["dining_judge"]["error_code"] == "dining_judge_deadline_exceeded"
    assert applied == [] and saved["payload"]["items"][0]["rows"] == [{"row": "hours", "result": "unknown"}]


@pytest.mark.parametrize("revision", [2, 3])
@pytest.mark.parametrize("excluded", [False, True])
def test_force_revalidation_keeps_the_saved_scope_answer(storage, monkeypatch, revision, excluded):
    from app.domains.travel_ops.components.intake import risks
    from app.domains.travel_ops.components.team_hooks import dining_ledger
    conn, saved = storage
    saved["state"] = ("review", revision)
    question = {"id": "q1", "quote": "할랄 필수", "attribute": "halal", "required": True,
                "choices": [], "answer": {"item_ids": [] if excluded else ["0-1"], "excluded": excluded}}
    saved["payload"]["dining_questions"] = [question]
    monkeypatch.setattr(risks, "decorate", lambda conn, **kw: kw["review"])
    monkeypatch.setattr(dining_ledger, "agent_judge_runner", lambda: None)
    monkeypatch.setattr(review_module, "build", lambda *a, **kw: {**meal_review(), "revision": revision})
    payload, error = pipeline._review_of(conn, "tenant", "intake", revision, [{"transcript": "할랄 필수"}], [], force=True)
    assert error is None
    assert payload["dining_questions"][0]["answer"] == question["answer"]
    assert payload["dining_questions"][0]["choices"][0]["item_id"] == "0-1"
