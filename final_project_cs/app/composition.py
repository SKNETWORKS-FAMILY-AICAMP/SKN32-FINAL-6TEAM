"""Application composition root.

Concrete adapters and Team implementations are assembled here.  The core
runtime only receives their ports, registries, and callable dependencies.
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

from app.application.controller import Controller
from app.core.context import ContextBroker
from app.core.project_config import ProjectConfig, load_project_config
from app.core.registry import TeamRegistry
from app.core.remote_team.a2a_executor import A2ATeamExecutor
from app.core.remote_team.executor import LocalTeamExecutor, TeamExecutorPort
from app.infrastructure.db import repository
from app.infrastructure.db.session import get_connection
from app.core.settings import get_settings
from app.infrastructure.llm.local_ft import LocalFTTeamLLM
from app.infrastructure.llm.openai import OpenAITeamLLM
from app.infrastructure.messaging.outbox import OutboxBrokerAdapter
from app.infrastructure.rag.retriever import search_policy
from app.modules.customer_ops import feedback
from app.presentation.security import masked
from app.tools.read_tools import ReadToolbox


def build_classifier(*, config: ProjectConfig | None = None):
    """Build the configured classifier, failing explicitly when unconfigured.

    ★**인라인 분류는 `voc` 모듈 소관이 아니다** — 진입·분류 층의 공통 처리다.
      계획서 v7.1 이 §7 과 §7-A 의 모순을 해소하며 그렇게 정했고, v8 §0 변경
      요약표와 §7-B 본문에 그대로 있다:

        "[v7.1] 이 인라인 분류는 VOC Team 의 업무가 아니라 진입·분류 층의
         공통 처리다. VOC 는 이미 분류된 Case events 를 입력받는다."

      ★2026-08-30 `9c11327`(모듈 게이트 실효화)이 여기에 `require_module("voc")`
      를 걸었다. 게이트를 만든 작업 자체는 정당했지만, 인라인 분류가
      **뺄 수 있는 Team 자리**(`app/modules/customer_ops/feedback.py`)에 있고
      테스트도 `tests/unit/voc/` 에 있어서 **파일 위치를 소관으로 착각**한
      것이다. 근거로 삼은 `CLAUDE.md` §1 문장의 출처인 v8 §3-A 는 v7.1 개정이
      반영되지 않은 낡은 절이었다.

      그래서 게이트를 뺐다. "인라인 분류는 선택 기능이 아니다" 는 여전히 맞다 —
      다만 그건 **끌 수 없다는 뜻이지 voc 소관이라는 뜻이 아니다.**

      ★**분류 절차는 코어 1 로 올렸다**(`app/application/classification.py`,
      2026-09-01). 파일을 통째로 옮기는 방식은 안 됐다 — `app/application/` 은
      basement 라 `order_payment_failed` 같은 업무 어휘를 둘 수 없고, 실제로
      옮겼다가 `test_basement_is_domain_free.py` 에 걸렸다. 그래서 §3-A 가 본래
      적은 경계대로 **둘로 나눴다**:

        언제 부르고 / 실패를 어떻게 처리하고 / 어느 상태로 보내는가
            → `app/application/classification.py::classify_case` (코어 1)
        라벨 어휘 · 프롬프트 · provider 호출
            → `app/modules/customer_ops/feedback.py` (모델)

      이 함수는 그 둘을 잇는 **배선**이다 — 도메인 모듈의 `classify` 를 마스킹과
      함께 감싸 코어 1 이 부를 수 있는 모양으로 만든다.

      ★일일 집계 배치(`feedback_job.py`)도 마찬가지다. v8 §7 재판정이 VOC 를
      **관측층(코어 1)과 판단층(Team 껍데기)** 으로 나눴고, §16 이 "Feedback
      Analytics 집계 배치" 를 코어 1 책임으로 적었다. 그래서 배치의 voc 게이트도
      뺐다 — `voc: false` 는 **판단·화면**을 끄는 것이지 관측을 끄는 게 아니다.
    """
    from app.core.settings import get_settings

    config = config or load_project_config()
    if not get_settings().openai_api_key:
        raise RuntimeError("OpenAI API key is missing")

    def classify(message: str) -> dict[str, str]:
        result = feedback.classify(masked(message))
        return {"intent": result.intent, "issue_code": result.issue_code, "sentiment": result.sentiment}

    return classify


class CompositionError(RuntimeError):
    """The declaration cannot be turned into a runnable composition."""


# Module implementations are registered here, at the composition boundary.
# UI modules are deliberately separate entries: enabling one must not imply
# that the other UI is available.
_MODULE_IMPLEMENTATIONS = frozenset({
    "vector_rag", "graph_store", "a2a_executor", "mcp", "voc",
    "ops_ui",
})


def _validate_modules(config: ProjectConfig) -> None:
    unknown_enabled = sorted(name for name, value in config.modules.items()
                             if value.enabled and name not in _MODULE_IMPLEMENTATIONS)
    if unknown_enabled:
        raise CompositionError(
            "enabled module has no implementation: " + ", ".join(unknown_enabled)
        )
    if config.ports.message_broker == "redis_streams":
        raise CompositionError("port message_broker=redis_streams is declared but not implemented")
    if config.ports.graph_store in {"age", "neo4j"}:
        raise CompositionError(
            f"port graph_store={config.ports.graph_store} is declared but not implemented"
        )
    if config.ports.team_executor == "a2a" and not config.module_enabled("a2a_executor"):
        raise CompositionError("port team_executor=a2a requires enabled module 'a2a_executor'")


def _import_ref(ref: str, team_id: str) -> type:
    try:
        module_name, separator, attribute = ref.partition(":")
        if not separator or not module_name or not attribute:
            raise ImportError("expected module.path:Attribute")
        implementation = getattr(importlib.import_module(module_name), attribute)
        if not callable(implementation):
            raise TypeError(f"{ref} is not callable")
        return implementation
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        raise CompositionError(
            f"active team '{team_id}' implementation_ref cannot be imported: {ref} ({exc})"
        ) from exc


def _instantiate_team(implementation: type, tools: ReadToolbox, llm: Any | None) -> Any:
    """Support both built-in (tools, llm) teams and small test implementations."""
    try:
        parameters = list(inspect.signature(implementation).parameters.values())
        positional = [parameter for parameter in parameters
                      if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)]
        required = [parameter for parameter in positional if parameter.default is parameter.empty]
        if not positional:
            return implementation()
        if len(required) <= 1 and len(positional) <= 1:
            # ★단일 인자 생성자는 이름으로 무엇을 받는지 구분한다 — 개수만 보면
            #   `__init__(self, llm=None)` 형태(예: ResponseGenerationReviewTeam)에
            #   ReadToolbox 가 llm 자리로 잘못 들어간다(2026-08-19 발견,
            #   docs/reports/debugs/2026-08-19_composition_단일인자_Team_llm_오배선.md).
            if positional[0].name == "llm":
                return implementation(llm)
            return implementation(tools)
        return implementation(tools, llm)
    except (TypeError, ValueError) as exc:
        raise CompositionError(f"cannot instantiate Team implementation {implementation}: {exc}") from exc


def build_registry(*, tools: ReadToolbox | None = None, llm: Any | None = None,
                   config_path: str | Path | None = None,
                   config: ProjectConfig | None = None) -> TeamRegistry:
    """Read the declaration, dynamically load every Team, and register it."""
    config = config or load_project_config(config_path)
    _validate_modules(config)
    if tools is None:
        config.require_module("vector_rag", "default ReadToolbox")
        tools = ReadToolbox(get_connection, policy_search=search_policy)
    teams = []
    capabilities: dict[str, str] = {}
    for declaration in config.teams:
        implementation = _import_ref(declaration.implementation_ref, declaration.team_id)
        team = _instantiate_team(implementation, tools, llm)
        if not hasattr(team, "manifest") or not hasattr(team, "execute"):
            raise CompositionError(
                f"team '{declaration.team_id}' implementation must provide manifest and execute"
            )
        team.manifest = team.manifest.model_copy(update={"active": declaration.active,
                                                         "team_id": declaration.team_id})
        for capability in team.manifest.capabilities:
            previous = capabilities.get(capability)
            if previous is not None:
                raise CompositionError(
                    f"duplicate capability '{capability}' claimed by teams '{previous}' and '{declaration.team_id}'"
                )
            capabilities[capability] = declaration.team_id
        teams.append(team)
    return TeamRegistry(teams)


def build_team_executor(registry: TeamRegistry, *, config: ProjectConfig | None = None,
                        transport: Any | None = None, capability_resolver: Any | None = None) -> TeamExecutorPort:
    config = config or load_project_config()
    _validate_modules(config)
    if config.ports.team_executor == "local":
        return LocalTeamExecutor(registry)
    if transport is None or capability_resolver is None:
        raise CompositionError("port team_executor=a2a requires injected transport and capability_resolver")
    return A2ATeamExecutor(transport, capability_resolver)


def build_graph_store(*, connection: Any, tenant_id: str,
                      config: ProjectConfig | None = None) -> Any:
    """Build the selected graph adapter, or fail if the optional module is off."""
    config = config or load_project_config()
    _validate_modules(config)
    config.require_module("graph_store", "GraphStore adapter")
    from app.infrastructure.graphstore.sql_adapter import SqlGraphAdapter
    return SqlGraphAdapter(connection, tenant_id=tenant_id)


def build_broker(*, connection_factory=get_connection,
                 config: ProjectConfig | None = None) -> Any:
    config = config or load_project_config()
    _validate_modules(config)
    if config.ports.message_broker != "outbox":
        raise CompositionError(f"unsupported message broker port: {config.ports.message_broker}")
    return OutboxBrokerAdapter(connection_factory)


def build_controller(*, registry: TeamRegistry | None = None,
                     team_executor: TeamExecutorPort | None = None,
                     broker: Any | None = None, tools: ReadToolbox | None = None,
                     llm: Any | None = None, policy_search_fn=search_policy,
                     config_path: str | Path | None = None,
                     config: ProjectConfig | None = None) -> Controller:
    """Assemble the application Controller and inject every concrete adapter.

    ★`config` 를 주면 **그 선언 그대로** 조립한다(2026-09-06, reload 계약).
      reload 는 "읽은 선언으로 조립하고, 그 선언의 revision 을 active 로 적는다"
      가 성립해야 한다. 여기서 다시 읽으면 그 사이 바뀐 선언으로 조립해 놓고
      **읽었던 revision 을 실행 중인 것으로 잘못 적게** 된다.
    """
    config = config if config is not None else load_project_config(config_path)
    _validate_modules(config)
    if llm is None:
        settings = get_settings()
        if settings.llm_provider == "local_ft":
            if not settings.local_ft_base_url:
                raise CompositionError("ACOP_LOCAL_FT_BASE_URL is required when ACOP_LLM_PROVIDER=local_ft")
            llm = LocalFTTeamLLM(base_url=settings.local_ft_base_url, connection_factory=get_connection)
        else:
            llm = OpenAITeamLLM(connection_factory=get_connection)
    registry = registry or build_registry(tools=tools, llm=llm, config=config)
    team_executor = team_executor or build_team_executor(registry, config=config)
    verification_policy, fact_queries = build_verification(config=config)
    return Controller(
        registry,
        context_broker=ContextBroker(),
        policy_search=policy_search_fn,
        connection_factory=get_connection,
        repository=repository,
        team_executor=team_executor,
        broker=broker if broker is not None else build_broker(config=config),
        # ★대조 어휘는 도메인 선언에서 온다. Controller 는 무엇을 대조하는지 모른다.
        verification_policy=verification_policy,
        fact_queries=fact_queries,
        response_review=config.response_review,
    )


def build_verification(*, config=None):
    """도메인의 대조 선언을 가져온다 (v7 §9-E).

    ★basement 는 규칙 엔진만 갖고, **어휘는 도메인이 선언**한다.
      쇼핑몰 CS 로 복사하면 이 함수가 가리키는 모듈만 갈아 끼운다.

    ★선언이 없으면 **빈 정책**을 준다 — 그러면 대조할 것이 없어 통과가 아니라
      "선언되지 않은 필드" 로 전부 거부된다. 도메인을 안 붙이면 아무 Action 도 못 한다.
      조용히 통과시키는 것보다 낫다.
    """
    from app.core.verification import VerificationPolicy
    try:
        from app.modules.customer_ops.verification_policy import (
            CUSTOMER_OPS_POLICY, FACT_QUERIES)
    except ImportError:
        return VerificationPolicy(), ()
    return CUSTOMER_OPS_POLICY, FACT_QUERIES


__all__ = ["CompositionError", "build_broker", "build_classifier", "build_controller",
           "build_graph_store", "build_registry", "build_team_executor"]
