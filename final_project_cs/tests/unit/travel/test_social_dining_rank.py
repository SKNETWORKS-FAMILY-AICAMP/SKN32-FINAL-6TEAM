"""The model may rank already feasible pairs, never manufacture a new pair."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib
import json

import pytest


LINKS = [{"key": "wish-a", "priority": "must", "source_urls": ["https://private-share.test/token"],
          "note": "private customer note"}, {"key": "wish-b", "priority": "if_fits"}]
EDGES = {"wish-a": ["meal-1", "meal-2"], "wish-b": ["meal-2"]}
CHOICES = {"wish-a": {"name": "토속촌", "address": "서울 종로구", "latitude": 37.5, "longitude": 126.9},
           "wish-b": {"name": "금용문", "address": "서울 종로구"}}
SLOTS = [{"id": "meal-1", "kind": "dining", "title": "점심", "date": "2026-10-16",
          "starts_at": "12:00", "ends_at": "13:00", "place": {"name": "서울 식당"}},
         {"id": "meal-2", "kind": "dining", "title": "저녁", "date": "2026-10-16",
          "starts_at": "18:00", "ends_at": "19:00", "place": None}]


class Chat:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.sent = []

    def json(self, system, user):
        self.sent.append((system, json.loads(user)))
        if self.error:
            raise self.error
        return self.response


def rank(*, chat=None, edges=None):
    api = importlib.import_module("app.domains.travel_ops.components.intake.social_dining_rank")
    return api.rank_edges(LINKS, EDGES if edges is None else edges, CHOICES, slots=SLOTS, chat=chat)


def test_valid_model_order_changes_only_existing_pair_preferences():
    chat = Chat({"rankings": [{"key": "wish-a", "slot_ids": ["meal-2", "meal-1"]},
                              {"key": "wish-b", "slot_ids": ["meal-2"]}]})
    ranked, audit = rank(chat=chat)
    assert ranked == {"wish-a": ["meal-2", "meal-1"], "wish-b": ["meal-2"]}
    assert audit["mode"] == "model"
    assert audit["reason"] is None
    assert audit["omissions"] == []
    assert audit["prompt_version"]
    assert audit["prompt_hash"] == hashlib.sha256(chat.sent[0][0].encode()).hexdigest()


@pytest.mark.parametrize("response", [
    "not JSON", None, {}, {"rankings": "not a list"},
    {"rankings": [{"key": "invented-wish", "slot_ids": ["meal-1"]}]},
    {"rankings": [{"key": "wish-a", "slot_ids": ["made-up-slot"]}]},
    {"rankings": [{"key": "wish-b", "slot_ids": ["meal-1"]}]},
    {"rankings": [{"key": "wish-a", "slot_ids": ["meal-2", "meal-2"]}]},
    {"rankings": [{"key": [], "slot_ids": ["meal-1"]}]},
])
def test_invalid_or_fabricated_ids_preserve_the_original_graph(response):
    ranked, audit = rank(chat=Chat(response))
    assert ranked == EDGES
    assert audit["mode"] == "rules"
    assert audit["reason"] == "invalid_output"
    assert audit["messages"]


def test_partial_ranking_keeps_omitted_pairs_and_reports_the_omission():
    ranked, audit = rank(chat=Chat({"rankings": [{"key": "wish-a", "slot_ids": ["meal-2"]}]}))
    assert ranked == {"wish-a": ["meal-2", "meal-1"], "wish-b": ["meal-2"]}
    assert audit["mode"] == "partial"
    assert {row["reason"] for row in audit["omissions"]} == {"missing_ranking", "missing_slots"}


@pytest.mark.parametrize("chat,reason", [
    (None, "model_unavailable"),
    (Chat(error=RuntimeError("private endpoint token")), "model_failed"),
])
def test_unavailable_or_failed_model_keeps_verified_rule_preferences(chat, reason):
    ranked, audit = rank(chat=chat)
    assert ranked == EDGES
    assert audit["mode"] == "rules"
    assert audit["reason"] == reason
    assert "private endpoint token" not in str(audit)


def test_ranking_does_not_mutate_inputs_or_return_shared_edge_lists():
    before = deepcopy((LINKS, EDGES, CHOICES, SLOTS))
    ranked, _ = rank(chat=Chat({"rankings": [{"key": "wish-a", "slot_ids": ["meal-2", "meal-1"]}]}))
    assert (LINKS, EDGES, CHOICES, SLOTS) == before
    ranked["wish-a"].append("mutation")
    assert EDGES == {"wish-a": ["meal-1", "meal-2"], "wish-b": ["meal-2"]}


def test_prompt_uses_factual_slots_without_customer_raw_links_or_notes():
    chat = Chat({"rankings": []})
    _, audit = rank(chat=chat)
    sent = chat.sent[0][1]
    serialized = json.dumps(sent, ensure_ascii=False)
    assert "토속촌" in serialized
    assert "12:00" in serialized
    assert "private-share" not in serialized
    assert "private customer note" not in serialized
    assert "travel_minutes" not in serialized
    assert "private-share" not in str(audit)


def test_no_candidates_are_reported_without_asking_a_model():
    def fail_call(*args, **kwargs):
        pytest.fail("no feasible pair exists to rank")

    chat = Chat()
    chat.json = fail_call
    ranked, audit = rank(chat=chat, edges={"wish-a": [], "wish-b": []})
    assert ranked == {"wish-a": [], "wish-b": []}
    assert audit["reason"] == "no_candidates"
