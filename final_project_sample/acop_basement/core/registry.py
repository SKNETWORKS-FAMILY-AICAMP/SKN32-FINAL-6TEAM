"""Dependency-free registry for Team manifests and injected implementations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from acop_basement.core.contracts import TeamManifest, TeamModule


class RegistryError(ValueError):
    pass


def _compatible(requested: str, supported: list[str]) -> bool:
    """A contract is compatible only within the same major version."""
    try:
        major = requested.split(".", 1)[0]
        return any(version.split(".", 1)[0] == major for version in supported)
    except (AttributeError, IndexError):
        return False


@dataclass(frozen=True)
class RegisteredTeam:
    manifest: TeamManifest
    module: TeamModule


class TeamRegistry:
    """Maps capabilities to injected Team modules; never imports app.modules."""

    def __init__(self, teams: list[TeamModule] | None = None, *, contract_version: str = "1.0") -> None:
        self.contract_version = contract_version
        self._teams: dict[str, RegisteredTeam] = {}
        for team in teams or []:
            self.register(team)

    def register(self, team: TeamModule) -> TeamManifest:
        manifest = team.manifest
        if not _compatible(self.contract_version, manifest.supported_contract_versions):
            raise RegistryError(f"{manifest.team_id} does not support contract {self.contract_version}")
        if manifest.team_id in self._teams:
            raise RegistryError(f"duplicate team_id: {manifest.team_id}")
        entry = RegisteredTeam(manifest, team)
        self._teams[manifest.team_id] = entry
        return manifest

    def get(self, team_id: str) -> RegisteredTeam:
        try:
            return self._teams[team_id]
        except KeyError as exc:
            raise RegistryError(f"unknown team: {team_id}") from exc

    def resolve(self, *, case_type: str, intent: str | None = None) -> RegisteredTeam:
        """Resolve a case to exactly one active, compatible registered Team.

        ``case_type`` is matched against the manifest's accepted case types.
        When an intent is supplied, an exact capability or a capability in
        that intent namespace (for example ``demo`` -> ``demo.investigate``)
        is preferred.  The registry owns this vocabulary; callers do not need
        to know any Team IDs or capabilities.
        """
        case_type = (case_type or "").lower()
        intent = (intent or "").lower() or None
        matches = [
            entry for entry in self._teams.values()
            if entry.manifest.active and case_type in {value.lower() for value in entry.manifest.accepted_case_types}
        ]
        if intent:
            intent_matches = [
                entry for entry in matches
                if any(capability.lower() == intent or capability.lower().startswith(intent + ".")
                       for capability in entry.manifest.capabilities)
            ]
            if intent_matches:
                matches = intent_matches
        if len(matches) != 1:
            raise RegistryError(f"case must resolve to exactly one active team: {case_type}")
        return matches[0]

    @staticmethod
    def capability_for(entry: RegisteredTeam, intent: str | None = None) -> str:
        """Return the registered capability selected for a resolved Team."""
        intent = (intent or "").lower()
        if intent:
            for capability in entry.manifest.capabilities:
                if capability.lower() == intent or capability.lower().startswith(intent + "."):
                    return capability
        return entry.manifest.capabilities[0]

    def manifests(self) -> tuple[TeamManifest, ...]:
        return tuple(entry.manifest for entry in self._teams.values())

