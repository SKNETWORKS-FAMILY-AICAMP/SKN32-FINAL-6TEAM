"""Dependency-free registry for Team manifests and injected implementations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.contracts import TeamManifest, TeamModule


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
    # ★register() 에서 한 번만 계산한다. resolve() 는 Case 마다(팀 6개 기준
    #   매 호출) 다시 계산하지 않는다 — 매니페스트는 등록 뒤 안 바뀐다.
    normalized_case_types: frozenset[str]


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
        normalized_case_types = frozenset(value.lower() for value in manifest.accepted_case_types)
        entry = RegisteredTeam(manifest, team, normalized_case_types)
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
        # ★case_type/intent 는 이미 검증된 값이다(classifier 가 INTENTS 밖이면
        #   막는다, feedback.py). 여기서 다시 .lower() 하면 "이 값을 못 믿는다"는
        #   신호를 준다 — 검증된 값을 또 방어하지 않는다.
        case_type = case_type or ""
        intent = intent or None
        matches = [
            entry for entry in self._teams.values()
            if entry.manifest.active and case_type in entry.normalized_case_types
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
        """Return the registered capability selected for a resolved Team.

        ★intent(5종, 거친 라벨)로 팀의 capability(팀마다 2~6종, 세분화된
          동작)를 고르는 지금 방식은 태생적으로 다 못 맞는다 — 실측으로
          intent 5개 중 3개(shipping·exchange·other)가 이름으로 매칭되는
          capability가 하나도 없다(register()에서 라우팅 자체는 되므로
          이건 resolve()가 아니라 여기, capability 선택만의 문제다).
          그때는 팀이 `manifest.default_capability`로 선언한 값을 쓴다.
          선언이 없으면 `capabilities[0]`을 쓰는데, 이건 "이 팀이 이
          intent 를 위해 이걸 골랐다"는 근거가 아니라 그냥 목록 첫 자리라는
          점을 호출하는 쪽이 알아야 한다
          (docs/reports/debugs/2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md
          — RegistryError로 막는 시도는 정상 라우팅 다수를 깨서 되돌렸다).
        """
        intent = (intent or "").lower()
        if intent:
            for capability in entry.manifest.capabilities:
                if capability.lower() == intent or capability.lower().startswith(intent + "."):
                    return capability
        return entry.manifest.default_capability or entry.manifest.capabilities[0]

    def manifests(self) -> tuple[TeamManifest, ...]:
        return tuple(entry.manifest for entry in self._teams.values())

