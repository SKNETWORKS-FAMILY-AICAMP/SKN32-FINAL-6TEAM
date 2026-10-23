"""Dependency-free registry for Team manifests and injected implementations."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.contracts import TeamManifest, TeamModule
from app.core.team_availability import TeamContractViolation, TeamUnavailable


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
    """Maps capabilities to injected Team modules; never imports app.domains."""

    def __init__(self, teams: list[TeamModule] | None = None, *, contract_version: str = "1.0") -> None:
        self.contract_version = contract_version
        self._teams: dict[str, RegisteredTeam] = {}
        self._unavailable: dict[str, str] = {}
        self._declared_capabilities: dict[str, tuple[str, ...]] = {}
        self._known_case_types: dict[str, frozenset[str]] = {}
        for team in teams or []:
            self.register(team)

    def register(self, team: TeamModule) -> TeamManifest:
        manifest = team.manifest
        if not _compatible(self.contract_version, manifest.supported_contract_versions):
            raise RegistryError(f"{manifest.team_id} does not support contract {self.contract_version}")
        if manifest.team_id in self._teams or manifest.team_id in self._unavailable:
            raise RegistryError(f"duplicate team_id: {manifest.team_id}")
        capabilities = tuple(manifest.capabilities)
        if len(set(capabilities)) != len(capabilities):
            raise RegistryError(f"duplicate capability in team: {manifest.team_id}")
        claimed = {capability for values in self._declared_capabilities.values() for capability in values}
        overlap = claimed.intersection(capabilities)
        if overlap:
            raise RegistryError(f"duplicate capability: {', '.join(sorted(overlap))}")
        normalized_case_types = frozenset(value.lower() for value in manifest.accepted_case_types)
        entry = RegisteredTeam(manifest, team, normalized_case_types)
        self._teams[manifest.team_id] = entry
        self._declared_capabilities[manifest.team_id] = capabilities
        return manifest

    def declare_unavailable(self, team_id: str, reason: str, *, manifest=None,
                            capabilities: list[str] | None = None) -> None:
        """Declare an absent plugin without importing or instantiating its code."""
        if reason not in {"disabled", "not_installed", "load_failed", "remote_unavailable"}:
            raise RegistryError(f"invalid team availability reason: {reason}")
        if manifest is not None:
            if manifest.team_id != team_id or manifest.active:
                raise RegistryError("unavailable metadata must identify the same inactive team")
            from types import SimpleNamespace
            self.register(SimpleNamespace(manifest=manifest))
        elif team_id in self._teams:
            if capabilities is not None and tuple(capabilities) != self._declared_capabilities[team_id]:
                raise RegistryError(f"availability cannot change capabilities: {team_id}")
        elif team_id in self._unavailable:
            raise RegistryError(f"duplicate team_id: {team_id}")
        else:
            values = tuple(capabilities or ())
            claimed = {value for items in self._declared_capabilities.values() for value in items}
            if len(set(values)) != len(values) or claimed.intersection(values):
                raise RegistryError(f"duplicate capability for unavailable team: {team_id}")
            self._declared_capabilities[team_id] = values
        self._unavailable[team_id] = reason

    def declare_case_types(self, team_id: str, case_types: list[str] | tuple[str, ...]) -> None:
        """Inject known routing ownership without loading the implementation."""
        if not isinstance(team_id, str) or not team_id.strip():
            raise RegistryError("known routing owner must be nonempty")
        if (not isinstance(case_types, (list, tuple)) or not case_types
                or any(not isinstance(value, str) or not value.strip() for value in case_types)):
            raise RegistryError("known case types must be nonempty strings")
        normalized = frozenset(value.lower() for value in case_types)
        if len(normalized) != len(case_types):
            raise RegistryError(f"duplicate known case type: {team_id}")
        if team_id in self._known_case_types:
            raise RegistryError(f"duplicate known routing owner: {team_id}")
        self._known_case_types[team_id] = normalized

    def availability(self) -> dict[str, dict[str, object]]:
        """Return detached diagnostics for the assembled generation."""
        return {
            team_id: {
                "available": team_id not in self._unavailable and
                team_id in self._teams and self._teams[team_id].manifest.active,
                "reason": self._unavailable.get(team_id) or (
                    "disabled" if team_id in self._teams and not self._teams[team_id].manifest.active else None),
                "capabilities": list(capabilities),
            }
            for team_id, capabilities in self._declared_capabilities.items()
        }

    def require_runnable(self, team_id: str, capability: str | None = None) -> RegisteredTeam:
        """Acquire an implementation only after availability and ownership checks."""
        if team_id in self._unavailable:
            raise TeamUnavailable(team_id, self._unavailable[team_id])
        entry = self._teams.get(team_id)
        if entry is None:
            raise TeamUnavailable(team_id, "not_installed")
        if not entry.manifest.active:
            raise TeamUnavailable(team_id, "disabled")
        if not _compatible(self.contract_version, entry.manifest.supported_contract_versions):
            raise TeamContractViolation(f"{team_id}: incompatible registered contract")
        if capability is not None and capability not in entry.manifest.capabilities:
            raise TeamContractViolation(f"{team_id}: undeclared capability '{capability}'")
        return entry

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
        if case_type in self._unavailable:
            self.require_runnable(case_type)
        matches = [
            entry for entry in self._teams.values()
            if entry.manifest.active and entry.manifest.team_id not in self._unavailable
            and case_type in entry.normalized_case_types
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
            if not matches:
                unavailable = [entry.manifest.team_id for entry in self._teams.values()
                               if case_type in entry.normalized_case_types
                               and (not entry.manifest.active or entry.manifest.team_id in self._unavailable)]
                unavailable.extend(team_id for team_id, values in self._declared_capabilities.items()
                                   if team_id in self._unavailable and team_id not in unavailable
                                   and any(value == case_type or value.startswith(case_type + ".") for value in values))
                if len(unavailable) == 1:
                    self.require_runnable(unavailable[0])
                known = [team_id for team_id, values in self._known_case_types.items()
                         if case_type in values]
                if not unavailable and len(known) == 1:
                    self.require_runnable(known[0])
            raise RegistryError(f"case must resolve to exactly one active team: {case_type}")
        return matches[0]

    @staticmethod
    def capability_for(entry: RegisteredTeam, intent: str | None = None, *, input_text: str | None = None,
                       state: dict | None = None) -> str:
        """Return the registered capability selected for a resolved Team."""
        # ★intent(5종, 거친 라벨)만으로는 팀의 capability(팀마다 2~6종,
        #   세분화된 동작) 중 어느 것이 맞는지 못 가른다 — 실측으로 확인된
        #   구체 사례는 docs/reports/debugs/
        #   2026-09-01_capability_for_폴백이_근거없이_기능을_고른다.md 를 본다
        #   (basement 는 그 사례의 업무 어휘를 여기 적지 않는다 — 도메인은
        #   app/domains/ 에 남긴다).
        #
        #   Registry가 문자열 네임스페이스로 대신 추측하지 않는다 — 팀이
        #   자기 capability의 의미를 안다. entry.module이 선택적으로
        #   select_capability(intent, input_text) -> str | None 을 구현하면
        #   그 판단을 먼저 묻는다. None을 돌려주면(또는 아예 구현하지 않으면)
        #   아래 기존 규칙(네임스페이스 매칭 → default_capability →
        #   capabilities[0])으로 그대로 떨어진다 — 하위호환.
        intent = (intent or "").lower() or None
        select = getattr(entry.module, "select_capability", None)
        if callable(select):
            # ★`[결정 2026-09-17]` 세 번째 인자(`state`)를 **선언한 모듈에만** 넘긴다.
            #   두 인자 모듈은 그대로 돈다 — 모든 Team 을 한꺼번에 고치지 않게.
            import inspect

            try:
                accepts_state = len(inspect.signature(select).parameters) >= 3
            except (TypeError, ValueError):
                accepts_state = False
            chosen = (select(intent, input_text or "", dict(state or {})) if accepts_state
                      else select(intent, input_text or ""))
            if chosen is not None:
                if chosen not in entry.manifest.capabilities:
                    raise RegistryError(
                        f"team '{entry.manifest.team_id}'.select_capability returned "
                        f"an undeclared capability: {chosen}"
                    )
                return chosen
        if intent:
            for capability in entry.manifest.capabilities:
                if capability.lower() == intent or capability.lower().startswith(intent + "."):
                    return capability
        return entry.manifest.default_capability or entry.manifest.capabilities[0]

    def manifests(self) -> tuple[TeamManifest, ...]:
        return tuple(entry.manifest for entry in self._teams.values())
