"""제품이 자기 조립 상태를 **데이터로** 낸다 (read-only).

★왜 필요한가 — 전에는 `/ui/admin` 이 이렇게 했다:

    registry = composition.build_registry()      # 대상 프로세스 안에서 파이썬을 실행

  **별도 대시보드 프로그램은 남의 프로세스에서 이걸 못 부른다.**
  이 런타임 결합을 끊지 않으면 분리가 껍데기가 된다.

★여기가 제품에 남는 표면이다. **아주 작아야 한다** — 콘솔 전체와 비교가 안 되게.
  내는 것은 "무엇으로 조립됐나" 뿐이고 고객 데이터는 한 줄도 나가지 않는다.

★소비자는 이 mapping 을 HTTP·파일 어디서 받아도 된다. 조립 절차를 몰라도 된다.
"""
from __future__ import annotations

from typing import Any

#: ★형식이 바뀌면 올린다. 대시보드는 이 값으로 호환을 판단한다.
CONTRACT_VERSION = "1.0"


def _manifest(manifest: Any) -> dict[str, Any]:
    return {
        "team_id": manifest.team_id,
        "display_name": manifest.display_name,
        "capabilities": list(manifest.capabilities),
        "allowed_tools": list(manifest.allowed_tools),
        "knowledge_scope": list(getattr(manifest, "knowledge_scope", [])),
        "max_steps": getattr(manifest, "max_steps", None),
        "active": bool(manifest.active),
        "revision": manifest.implementation_revision,
    }


def snapshot(*, config: Any | None = None, registry: Any | None = None,
             executor: Any | None = None) -> dict[str, Any]:
    """버전이 붙은 read-only 조립 스냅샷.

    ★API key 원문을 내지 않는다 (설계 원칙 §1).
    ★얻지 못한 값은 **생략하지 않고 `None`** 으로 남긴다 —
      빠뜨린 것과 없는 것을 구분해야 대시보드가 "모름" 을 표시할 수 있다.
    """
    from app import composition
    from acop_basement.core import settings as settings_module

    requested_config = config
    config = config or composition.load_project_config()
    if registry is None:
        registry = (composition.build_registry()
                    if requested_config is None
                    else composition.build_registry(config=config))
    executor = executor or composition.build_team_executor(registry=registry, config=config)

    settings = settings_module.get_settings()
    guardrails = settings_module.get_guardrails().as_dict()
    manifests = [_manifest(item) for item in registry.manifests()]

    return {
        "contract_version": CONTRACT_VERSION,
        "config_revision": getattr(config, "revision", None),
        "modules": {name: bool(value.enabled) for name, value in config.modules.items()},
        "ports": {
            "team_executor": config.ports.team_executor,
            "message_broker": config.ports.message_broker,
            "graph_store": config.ports.graph_store,
        },
        "team_manifests": manifests,
        # ★선언과 조립을 함께 낸다. 선언만 보면
        #   "켰다고 적혀 있는데 실제로는 안 올라간" 경우를 못 본다.
        "teams": _declared_teams(config, manifests),
        "port_implementations": _port_implementations(config, executor),
        "guardrails": guardrails,
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "api_key": "sk-****" if settings.openai_api_key else "missing",
        },
    }


def _declared_teams(config: Any, manifests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {m["team_id"]: m for m in manifests}
    declared = [{"team_id": t.team_id, "active": t.active,
                 "implementation_ref": t.implementation_ref,
                 "manifest": by_id.get(t.team_id)}
                for t in getattr(config, "teams", [])]
    known = {d["team_id"] for d in declared}
    # 선언에 없는데 조립된 Team (테스트 주입 등)도 빠뜨리지 않는다
    for team_id, manifest in by_id.items():
        if team_id not in known:
            declared.append({"team_id": team_id, "active": manifest["active"],
                             "implementation_ref": None, "manifest": manifest})
    return declared


def _port_implementations(config: Any, executor: Any) -> dict[str, str | None]:
    """실제로 **조립된** 구현 이름.

    ★이름 맵으로 추측하지 않는다. 전에는 `{"outbox": "OutboxBrokerAdapter"}` 같은
      하드코딩 표를 썼는데, 그건 선언을 되읽는 것이지 조립을 보는 게 아니다 —
      구현이 바뀌어도 화면은 옛 이름을 계속 말한다.
    ★얻지 못하면 `None`(모름)이다. 지어내지 않는다.
    """
    from app import composition
    from acop_basement.infrastructure.db.session import get_connection

    result: dict[str, str | None] = {"team_executor": type(executor).__name__,
                                     "message_broker": None, "graph_store": None}
    try:
        result["message_broker"] = type(composition.build_broker(
            connection_factory=get_connection, config=config)).__name__
    except Exception:
        pass
    try:
        if config.module_enabled("graph_store"):
            result["graph_store"] = type(composition.build_graph_store(
                connection=None, tenant_id="introspection", config=config)).__name__
    except Exception:
        pass
    return result


#: 별칭 — 부르는 쪽이 갈리지 않게 하나로 모은다
introspect = snapshot
build_snapshot = snapshot
describe = snapshot
