from __future__ import annotations


def build_agent_card(registry) -> dict:
    """Build the server capability document from the active Team Registry."""
    return {
        "name": "A-COP",
        "description": "Customer case agent capabilities",
        "capabilities": [
            {"team_id": m.team_id, "display_name": m.display_name, "capabilities": list(m.capabilities),
             "accepted_case_types": list(m.accepted_case_types), "contract_versions": list(m.supported_contract_versions)}
            for m in registry.manifests()
        ],
    }
