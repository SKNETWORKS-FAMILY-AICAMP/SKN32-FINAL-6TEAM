from itertools import product

import pytest

from app.domains.travel_ops.components.customer import service_improvement as improvement


def test_fixed_domains_and_one_contribution(monkeypatch):
    monkeypatch.setattr(improvement, "_geometric", lambda: 0)
    assert len(improvement.BINS) == 27
    data = improvement.synthesize([(4, 7, 35)], rows=500, noisy_min_count=1)
    assert data == {"schema": "trip_structure_v1", "rows": [
        {"party_bucket": "2-4", "days_bucket": "4+", "items_per_day_bucket": "4-6"}] * 500}


def test_support_threshold_uses_noisy_count_even_for_empty_input(monkeypatch):
    draws = iter([2, 0] * 27)
    monkeypatch.setattr(improvement, "_geometric", lambda: next(draws))
    assert improvement.synthesize([], rows=10, noisy_min_count=50) is not None


def test_negative_counts_are_postprocessed_and_empty_support_is_not_exported(monkeypatch):
    draws = iter([0, 10] * 27)
    monkeypatch.setattr(improvement, "_geometric", lambda: next(draws))
    assert improvement.synthesize([(1, 1, 1)], rows=10, noisy_min_count=1) is None


def test_geometric_uses_exact_fair_bits(monkeypatch):
    bits = iter([1, 1, 1, 0, 0])
    monkeypatch.setattr(improvement.secrets, "randbits", lambda n: next(bits))
    assert improvement._geometric() == 3
    assert improvement._geometric() == 0


@pytest.mark.parametrize("field", ["user_id", "trip_id", "title", "coordinates", "chat", "booking_number", "date"])
def test_identifier_and_original_fields_are_rejected(field):
    row = dict(zip(improvement.FIELDS, improvement.BINS[0], strict=True))
    row[field] = "must not escape"
    with pytest.raises(improvement.ImprovementError, match="forbidden_fields"):
        improvement.validate({"schema": "trip_structure_v1", "rows": [row]}, expected_rows=1)


@pytest.mark.parametrize("party,days,items", list(product([1, 2, 4, 5], [1, 2, 3, 4], [1, 3, 6, 7])))
def test_every_coarse_feature_stays_in_public_domain(party, days, items):
    assert improvement.bucket(party, days, items) in improvement.BINS


def test_payload_tampering_changes_review_hash():
    payload = {"schema": "trip_structure_v1", "rows": [{"party_bucket": "1", "days_bucket": "1", "items_per_day_bucket": "1-3"}]}
    sha = improvement.digest(payload)
    payload["rows"][0]["party_bucket"] = "5+"
    assert improvement.digest(payload) != sha
