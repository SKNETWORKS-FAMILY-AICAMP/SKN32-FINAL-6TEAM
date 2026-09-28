from __future__ import annotations

from acop_basement.core.contracts import TeamModule, TeamManifest
from app.modules.customer_ops.feedback_team import FeedbackAnalyticsTeam


def test_team_manifests_implement_protocol():
    for team in (FeedbackAnalyticsTeam,):
        assert isinstance(team.__new__(team), TeamModule)
        manifest = team.manifest
        assert isinstance(manifest, TeamManifest)
        assert manifest.contract_name == "a_cop.team_task"
        assert manifest.supported_contract_versions == ["1.0"]
        assert manifest.max_steps == 1
        assert manifest.active


def test_manifest_scopes_are_exact():
    assert FeedbackAnalyticsTeam.manifest.allowed_tools == []
