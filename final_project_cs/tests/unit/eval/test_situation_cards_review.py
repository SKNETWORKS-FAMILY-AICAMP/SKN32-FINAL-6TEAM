"""상황 카드 사람 작업 — 검토 시트가 상대 카드만 · 정답 없이 싣는지, 문장 합치기 검사, 라벨 시트 블라인드 · 왕복. DB 없이."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from eval.human_review import agreement, core
from eval.human_review.adapters import situation_cards as adapter
from eval.human_review.adapters.paths import Sources
from eval.situation_cards import review_sheets as rs

REAL = Path(rs.__file__).resolve().parent


@pytest.fixture
def cards_dir(tmp_path, monkeypatch):
    """결합본 · 작성자 시트를 tmp 저장소(`final_project_cs/eval/situation_cards`)로 복사하고 모듈 경로를 그쪽으로 돌린다."""
    folder = tmp_path / "final_project_cs" / "eval" / "situation_cards"
    folder.mkdir(parents=True)
    for name in ("cards_llm_bound_v0.jsonl", "sheet_llm_bound_v0.csv"):
        shutil.copy(REAL / name, folder / name)
    monkeypatch.setattr(rs, "HERE", folder)
    monkeypatch.setattr(rs, "BOUND", folder / "cards_llm_bound_v0.jsonl")
    monkeypatch.setattr(rs, "SHEET", folder / "sheet_llm_bound_v0.csv")
    monkeypatch.setattr(rs, "RESPONSES", folder / "responses_llm_bound_v0.csv")
    return folder


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def fill_writer_sheet(folder: Path, out: Path, writer: str | None = None) -> None:
    """시험 전용 가짜 작성자 — 자기 행에 「문장 L-xx」 를 적는다."""
    data = rows(folder / "sheet_llm_bound_v0.csv")
    for r in data:
        if writer is None or r["작성자"] == writer:
            r[rs.TEXT_COL] = f"문장 {r['카드']} 바꿔 주세요"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)


def test_review_sheets_cover_only_the_other_writers_cards_and_hide_answer_keys(cards_dir):
    rs.cmd_review(None)
    sheet = rows(cards_dir / "sheet_llm_bound_v0.csv")
    owner = {r["카드"]: r["작성자"] for r in sheet}
    cards = rs.load_bound()
    seen: list[str] = []
    for writer in sorted(set(owner.values())):
        path = cards_dir / f"review_by_{writer}.csv"
        got = rows(path)
        assert got and all(owner[r["카드"]] != writer for r in got)            # ★자기가 쓸 카드는 없다
        seen += [r["카드"] for r in got]
        text = path.read_text(encoding="utf-8-sig")
        for r in got:
            c = cards[r["카드"]]
            for hidden in (c["needs_review"], *c.get("acceptable_draft", [])):
                if hidden:
                    assert hidden not in text, (r["카드"], hidden)
            # 후보 칸은 이름 · 분류 · 코드 이유뿐 — 속성 초안(auto_tags)이 붙지 않는다
            assert [r["후보 1(코드 순서)"], r["후보 2"], r["후보 3"]][:len(c["candidates"])] == \
                [f"{x['title']} ({x['class']}) — {x['code_reason']}" for x in c["candidates"]]
        assert "priority:" not in text and "stratum" not in text                # 설문 칸에 priority 값이 없다(머리말 「priority 뺌」은 제외)
    assert sorted(seen) == sorted(owner)                                         # 80장이 한 번씩
    with pytest.raises(SystemExit):
        rs.cmd_review(None)                                                      # 덮어쓰지 않는다


def test_merge_takes_each_writers_rows_and_rejects_gaps_or_stale_sheets(cards_dir, tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    fill_writer_sheet(cards_dir, a, "작성자1")
    with pytest.raises(SystemExit, match="문장이 없다"):
        rs.main(["merge", str(a)])                                               # 작성자2 몫이 비었다
    assert not rs.RESPONSES.exists()
    stale = rows(a)
    stale[0]["상황"] = "옛 문장"
    with (tmp_path / "stale.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(stale[0]))
        w.writeheader()
        w.writerows(stale)
    fill_writer_sheet(cards_dir, b, "작성자2")
    with pytest.raises(SystemExit, match="결합본과 다르다"):
        rs.main(["merge", str(tmp_path / "stale.csv"), str(b)])
    rs.main(["merge", str(a), str(b)])
    merged = rows(rs.RESPONSES)
    assert len(merged) == 80 and all(r[rs.TEXT_COL].startswith("문장 ") for r in merged)


def test_label_sheet_is_blind_round_trips_and_rejects_overlap(cards_dir, tmp_path):
    filled = tmp_path / "all.csv"
    fill_writer_sheet(cards_dir, filled)
    rs.main(["merge", str(filled)])
    bundle = adapter.build(Sources(repo_root=tmp_path))
    assert len(bundle.items) == 80 and set(bundle.subsets) == {"writer_작성자1", "writer_작성자2"}
    cards = rs.load_bound()
    path = tmp_path / "label.csv"
    core.export_sheet(bundle, path)
    text = path.read_text(encoding="utf-8-sig")
    for it in bundle.items:
        c = cards[it.id]
        assert c["situation"] not in text                                        # 작성자 지시문 · 정답 키는 없다
        for i in c.get("acceptable_draft", []):
            assert i not in text
    # 사람 둘: 하나는 1번, 하나는 AI 초안을 적은 가짜 검토자 → 들이기 · 일치도
    data = rows(path)
    for r in data:
        r[bundle.fields[0].column] = "1"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    out = core.apply_sheet(bundle, path, "가짜A", tmp_path / "labels")
    labels = json.loads(out.read_text(encoding="utf-8"))["labels"]
    result = agreement.compare(bundle, labels, bundle.ai_labels(adapter.AI_SOURCE), "A", "AI")
    assert result["fields"]["acceptable"]["n"] > 0
    data[0][bundle.fields[1].column] = "1"                                       # 같은 번호를 위험에도
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    with pytest.raises(core.SheetError, match="함께 있다"):
        core.read_sheet(bundle, path)


def test_split_gives_each_writer_only_own_rows_after_review_is_done(cards_dir):
    for name in ("review_by_작성자1.csv", "review_by_작성자2.csv"):
        shutil.copy(REAL / name, cards_dir / name)
    review = cards_dir / "review_by_작성자1.csv"
    data = rows(review)
    data[0][rs.VERDICT_COL] = "고침"
    with review.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    with pytest.raises(SystemExit):
        rs.main(["split"])                                                      # 검토가 덜 끝났다
    data[0][rs.VERDICT_COL] = "괜찮음"
    with review.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
    rs.main(["split"])
    sheet = rows(cards_dir / "sheet_llm_bound_v0.csv")
    for writer in ("작성자1", "작성자2"):
        mine = rows(cards_dir / f"write_by_{writer}.csv")
        assert {r["작성자"] for r in mine} == {writer}
        assert [r["카드"] for r in mine] == [r["카드"] for r in sheet if r["작성자"] == writer]
    with pytest.raises(SystemExit):
        rs.main(["split"])                                                      # 덮어쓰지 않는다
