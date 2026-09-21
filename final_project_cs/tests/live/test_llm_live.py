from __future__ import annotations

import pytest

from app.infrastructure.llm import OpenAITeamLLM


@pytest.mark.live
@pytest.mark.asyncio
async def test_team_llm_live_smoke() -> None:
    response = await OpenAITeamLLM().complete(
        "live.smoke",
        "Return a JSON object with the key 'ok' set to true.",
        {},
    )
    assert isinstance(response, dict)
    assert response
