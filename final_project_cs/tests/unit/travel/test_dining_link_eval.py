"""원장 ↔ 장소 연결 평가 — 채점 규칙과 정답셋 모양(DB 없이)."""
import json
import math

import pytest

from eval.runners.dining_link import DEV, HOLDOUT, label
from scripts.dining.make_link_eval import GROUPS, moved


@pytest.mark.parametrize("expected, got, want", [
    ("a", "a", "correct_link"), ("a", "b", "wrong_link"), ("a", None, "missed"),
    (None, None, "correct_abstain"), (None, "b", "wrong_link")])
def test_linking_another_shop_is_never_counted_as_right(expected, got, want):
    assert label(expected, got) == want


def test_moved_puts_the_point_at_the_asked_distance():
    lat, lng = moved(37.5665, 126.978, 100, 45)
    dy = (lat - 37.5665) * 111_320
    dx = (lng - 126.978) * 111_320 * math.cos(math.radians(37.5665))
    assert abs(math.hypot(dx, dy) - 100) < 1


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_dev_and_holdout_never_share_a_shop_and_every_group_is_present():
    dev, holdout = _rows(DEV), _rows(HOLDOUT)
    shops = lambda rows: {r["made_from"]["place_uid"] for r in rows}   # noqa: E731
    assert not shops(dev) & shops(holdout)
    assert {r["group"] for r in dev} == {g for g, *_ in GROUPS}
    abstain = {"not_in_ledger", "other_branch"}
    assert all((r["expect"]["place_uid"] is None) == (r["group"] in abstain) for r in dev + holdout)
