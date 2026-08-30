from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.tools.read_tools import ALLOWED_PROMPT_KEYS, register_prompt_files


class _NoopCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _NoopConnection:
    def transaction(self):
        return _NoopCursor()

    def cursor(self):
        return _NoopCursor()


def test_prompt_registration_allowlist_matches_cs_pack_teams():
    """2026-08-19 legacy isolation emptied this allowlist (legacy order_shipping/
    return_exchange prompt keys removed). It stayed empty until 2026-08-30, which
    silently broke ResponseGenerationReviewTeam's DB-audited LLM path (every real
    call raised 'no active prompt registered for response.generate') -- see
    docs/reports/2026-08-30_S-PROMPT-KEY-REGISTRATION-GAP_리포트.md. This asserts
    the current, deliberate CS-pack set rather than "empty forever"."""
    assert ALLOWED_PROMPT_KEYS == frozenset({"response.generate", "response.review_tone"})


def test_empty_prompt_directory_registers_nothing():
    root = Path("tests") / f".prompt_registration_{uuid4().hex}"
    root.mkdir()
    try:
        ids, skipped = register_prompt_files(_NoopConnection(), str(root))
        assert ids == []
        assert skipped == []
    finally:
        root.rmdir()


def test_disallowed_prompt_is_skipped_even_for_same_version_collision_shape():
    root = Path("tests") / f".prompt_registration_{uuid4().hex}"
    prompt_dir = root / "foo"
    prompt_dir.mkdir(parents=True)
    first = prompt_dir / "bar.v1.md"
    first.write_text("first", encoding="utf-8")

    try:
        ids, skipped = register_prompt_files(_NoopConnection(), str(root))
        assert ids == []
        assert skipped == [str(first)]

        first.write_text("second", encoding="utf-8")
        ids, skipped = register_prompt_files(_NoopConnection(), str(root))
        assert ids == []
        assert skipped == [str(first)]
    finally:
        first.unlink(missing_ok=True)
        prompt_dir.rmdir()
        root.rmdir()
