"""골든셋 라벨 사람 검토(WS-1.1) — 시트 내보내기 · 들이기 · 골든셋 덮어쓰기. 네트워크 없이."""
from __future__ import annotations

import csv
import json

import pytest

from eval.activity_judge import build, review


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _fill(path, answers):
    rows = _rows(path)
    for row in rows:
        row["정답"], row[review.HEADER[7]] = answers.get(row["case_id"], ("", ""))
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review.HEADER)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def sheet(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "HUMAN_LABELS", tmp_path / "labels_human.json")
    path = tmp_path / "labels_review.csv"
    review.export(path)
    return path


def _author_answers():
    return {c["case_id"]: (c["expected"], ";".join(v for v in c["acceptable"] if v != c["expected"]))
            for c in review.load_cases()}


def test_sheet_hides_author_labels_and_skips_unlabeled_kind(sheet):
    """★라벨은 앞선 라벨을 보기 전에 고정한다 — 시트에 작성자 정답 · 허용 값 · 메모가 없어야 한다."""
    rows = _rows(sheet)
    assert len(rows) == 52 and all(r["종류"] != "live_status" for r in rows)
    assert all(r["정답"] == "" and r[review.HEADER[7]] == "" and r["메모"] == "" for r in rows)
    assert "작성자" not in sheet.read_text(encoding="utf-8-sig")


def test_round_trip_reproduces_the_author_dataset(sheet):
    """작성자 라벨을 그대로 적어 넣으면 골든셋이 한 글자도 안 바뀐다 — 덮어쓰기가 다른 칸을 건드리지 않는다."""
    _fill(sheet, _author_answers())
    review.apply(sheet, reviewer="검토자")
    stored = json.loads(review.HUMAN_LABELS.read_text(encoding="utf-8"))
    cases = build.labeled_cases(stored)
    assert [c["expected"] for c in cases] == [c["expected"] for c in build.CASES]
    assert [sorted(c["acceptable"]) for c in cases] == [sorted(c["acceptable"]) for c in build.CASES]


def test_human_label_overrides_author_label(sheet):
    answers = _author_answers()
    answers["disaster-03"] = ("no_effect", "")
    _fill(sheet, answers)
    review.apply(sheet, reviewer="검토자")
    cases = {c["case_id"]: c for c in build.labeled_cases(json.loads(review.HUMAN_LABELS.read_text(encoding="utf-8")))}
    assert cases["disaster-03"]["expected"] == "no_effect" and cases["disaster-03"]["acceptable"] == ["no_effect"]
    assert cases["live-01"]["expected"] is None          # 사람이 안 본 종류는 그대로


@pytest.mark.parametrize("bad, message", [
    (("", ""), "정답이 비었다"),
    (("maybe", ""), "고를 수 없는 값"),
    (("closed", "blocks"), "고를 수 없는 값"),
])
def test_bad_sheet_writes_nothing(sheet, bad, message):
    answers = _author_answers()
    answers["closure-01"] = bad
    _fill(sheet, answers)
    with pytest.raises(SystemExit, match=message):
        review.apply(sheet, reviewer="검토자")
    assert not review.HUMAN_LABELS.exists()
