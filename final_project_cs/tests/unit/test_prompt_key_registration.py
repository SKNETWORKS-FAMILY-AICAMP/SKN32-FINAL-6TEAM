"""Guards the exact class of bug found 2026-08-30: ``ALLOWED_PROMPT_KEYS``
was emptied by the 2026-08-19 legacy-team isolation and never repopulated
with the CS-pack prompt keys that ``ResponseGenerationReviewTeam`` actually
calls (``response.generate``, ``response.review_tone``).

Reproduced live: ``OpenAITeamLLM(connection_factory=get_connection).complete(...)``
raised ``RuntimeError: no active prompt registered for response.generate``
on every real invocation -- the Response Generation & Review Team (one of
the two confirmed CS-pack teams, v8 §8-B) could not function through the
real DB-audited path at all. The pre-existing live smoke test
(``tests/live/test_response_review_live_smoke.py``) did not catch this
because it constructs ``OpenAITeamLLM()`` with no ``connection_factory``,
which skips the prompts-table lookup entirely.

See ``docs/reports/2026-08-30_S-PROMPT-KEY-REGISTRATION-GAP_리포트.md``.
"""
from pathlib import Path

from app.tools.read_tools import ALLOWED_PROMPT_KEYS

USED_PROMPT_KEYS = frozenset({"response.generate", "response.review_tone"})


def test_every_prompt_key_a_team_calls_is_allowlisted():
    missing = USED_PROMPT_KEYS - ALLOWED_PROMPT_KEYS
    assert not missing, (
        f"prompt_key(s) {missing} are called by a Team's llm.complete() but not in "
        "ALLOWED_PROMPT_KEYS -- register_prompt_files() will silently skip their "
        "template files and OpenAITeamLLM will raise 'no active prompt registered' "
        "on every real (DB-audited) call."
    )


def test_every_allowlisted_key_has_a_template_file_on_disk():
    root = Path(__file__).resolve().parents[2] / "prompts"
    found = set()
    for path in root.glob("*/**/*.v*.md"):
        stem, version = path.name.rsplit(".v", 1)
        found.add(f"{path.parent.name}.{stem}")
    missing = ALLOWED_PROMPT_KEYS - found
    assert not missing, (
        f"prompt_key(s) {missing} are allowlisted but have no prompts/<dir>/<name>.v<N>.md "
        "file on disk -- register_prompt_files() has nothing to register for them."
    )
