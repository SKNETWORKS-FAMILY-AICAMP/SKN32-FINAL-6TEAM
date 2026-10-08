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
from app.domains.travel_ops.components.core_hooks import feedback
from app.core.redaction import masked
from app.tools.read_tools import ReadToolbox


def _llm_failover_budget(settings: Any):
    """모델 서버 넘김 장치(`llm_failover.py`)가 **API 로 넘긴 호출**을 세는 장치 — `external_call_budget` 의 `openai_failover` 줄(일 · 월 상한).
    ★인프라는 도메인의 `CallBudget` 을 모르므로(계층 규칙) 조립 루트가 만들어 꽂는다. 한도 표를 못 읽으면 **부른다**(서비스를 살리는 쪽) — 경고를 남긴다.
    한도를 넘으면 `False` — 넘김 장치가 더 부르지 않고 실패로 올린다."""
    import logging

    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget
    from app.infrastructure.llm_failover import METER

    budget = CallBudget(connection_factory=get_connection,
                        caps={METER: {"day": int(settings.llm_failover_daily_cap), "month": int(settings.llm_failover_monthly_cap)}})

    def allowed() -> bool:
        try:
            return bool(budget.try_reserve(METER))
        except Exception as exc:                                  # noqa: BLE001 — 세는 일이 서비스를 막지 않게
            logging.getLogger("app.llm_failover").warning("call budget unreadable (%s) — calling the API anyway", type(exc).__name__)
            return True
    return allowed


def _register_llm_failover() -> None:
    from app.infrastructure.llm_failover import register_budget_provider

    register_budget_provider(_llm_failover_budget)


_register_llm_failover()           # import 때 한 번 — 꽂기만 한다(I/O 없음, 부를 때 일한다)


def build_classifier(*, config: ProjectConfig | None = None):
    """Build the configured classifier, failing explicitly when unconfigured.

    ★**인라인 분류는 `voc` 모듈 소관이 아니다** — 진입·분류 층의 공통 처리다.
      계획서 v7.1 이 §7 과 §7-A 의 모순을 해소하며 그렇게 정했고, v8 §0 변경
      요약표와 §7-B 본문에 그대로 있다:

        "[v7.1] 이 인라인 분류는 VOC Team 의 업무가 아니라 진입·분류 층의
         공통 처리다. VOC 는 이미 분류된 Case events 를 입력받는다."

      ★2026-08-30 `9c11327`(모듈 게이트 실효화)이 여기에 `require_module("voc")`
      를 걸었다. 게이트를 만든 작업 자체는 정당했지만, 인라인 분류가
      **뺄 수 있는 Team 자리**(그때는 `app/modules/customer_ops/feedback.py`)에 있고
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
            → `app/domains/travel_ops/components/core_hooks/feedback.py` (모델)

      이 함수는 그 둘을 잇는 **배선**이다 — 도메인 모듈의 `classify` 를 마스킹과
      함께 감싸 코어 1 이 부를 수 있는 모양으로 만든다.

      ★일일 집계 배치(`feedback_job.py`)도 마찬가지다. v8 §7 재판정이 VOC 를
      **관측층(코어 1)과 판단층(Team 껍데기)** 으로 나눴고, §16 이 "Feedback
      Analytics 집계 배치" 를 코어 1 책임으로 적었다. 그래서 배치의 voc 게이트도
      뺐다 — `voc: false` 는 **판단·화면**을 끄는 것이지 관측을 끄는 게 아니다.
    """
    from app.core.settings import get_settings

    config = config or load_project_config()
    settings = get_settings()
    # ★제공자는 둘 중 하나면 된다 — OpenAI 키, 또는 로컬 Ollama 주소(2026-09-14, 크레딧 소진).
    if not settings.openai_api_key and not (settings.ollama_base_url or "").strip():
        raise RuntimeError("LLM provider is missing — set ACOP_OPENAI_API_KEY or ACOP_OLLAMA_BASE_URL")

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
            #   wiki/records/reports/debugs/2026-08-19_composition_단일인자_Team_llm_오배선.md).
            if positional[0].name == "llm":
                return implementation(llm)
            return implementation(tools)
        return implementation(tools, llm)
    except (TypeError, ValueError) as exc:
        raise CompositionError(f"cannot instantiate Team implementation {implementation}: {exc}") from exc


def build_report_extractor():
    """고객 문장에서 여행 신고(늦음·휴무·품절·재요청)를 뽑는 함수 — Case 버전 Team 의 `read.customer_report`.

    ★`[2026-09-17]` 이 자리가 비어 있었다. 시험과 시나리오 모드는 조립기(`case_engine`)에 직접
      넣어서 돌았고, **운영 조립(`build_registry`)만 안 넣어** 실제 `/v1/cases` 로 온 여행 신고가
      Team 에서 「신고 내용 모름」으로 사람에게 갈 자리였다.
    ★Ollama(Gemma 4)가 설정돼 있을 때만 만든다. 없으면 `None` — Team 은 지어내지 않고 escalate 한다.
      만드는 것 자체는 I/O 가 없다(부를 때 나간다).
    """
    from app.infrastructure.ollama_chat import from_settings

    chat = from_settings(get_settings())
    if chat is None:
        return None
    from app.domains.travel_ops.components.conversation.trip_intake import extract

    return lambda text: extract(text, chat)


def build_kakao_local() -> Any | None:
    """카카오 로컬(키워드 검색). 키가 없으면 `None` — 그 단계만 건너뛴다(「없음」이 아니라 「모름」).

    ★**장소 이름 찾기·존재 확인** 전용이다(`intake/places.py` · `read.place_lookup`). 응답은 저장하지 않는다.
    호출 예산이 필수다(무료 한도 초과 사용은 약관 위반) — `travel.kakao_budget`.
    """
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget, kakao_caps
    from app.domains.travel_ops.ports.data_sources.kakao_local import KakaoLocal

    # ★설정 객체에 키 필드가 없으면(시험용 설정) 키가 없는 것과 같다 — 조립을 깨지 않는다
    key = getattr(get_settings(), "kakao_rest_api_key", "")
    if not key:
        return None
    return KakaoLocal(api_key=key, budget=CallBudget(connection_factory=get_connection, caps=kakao_caps()))


def build_activity_judge_llm() -> Any | None:
    """활동 판정 LLM(D-CS-008) — Responses API 어댑터. 쓰지 않을 때는 `None`.

    ★`None` 인 경우: `activity_judge_mode = rule` 이거나 OpenAI 키가 없을 때. 그러면 Team 은 규칙 판정만 한다
      (키가 없는데 섀도로 돌려 매번 실패를 남기지 않는다). 만드는 것 자체는 I/O 가 없다 — 부를 때 나간다.
    ★설정 객체에 칸이 없으면(시험용 설정) `rule` 과 같다 — 조립을 깨지 않는다(`build_kakao_local` 과 같은 방식).
    """
    from app.infrastructure.llm.openai_responses import OpenAIResponsesJudgeLLM

    settings = get_settings()
    if getattr(settings, "activity_judge_mode", "rule") == "rule":
        return None
    if not (getattr(settings, "openai_api_key", "") or "").strip():
        return None
    return OpenAIResponsesJudgeLLM(connection_factory=get_connection)


def build_activity_judge_shadow_sink():
    """섀도 기록 한 줄을 표 `activity_judge_shadow` 한 행으로 쓰는 함수(A안, 2026-10-06).

    ★호출마다 연결을 새로 연다 — 백그라운드 스레드에서 불리고, 판정 한 건에 한 번이라 연결 풀을 따로 두지 않는다.
    """
    from app.infrastructure.db.repository import create_activity_judge_shadow

    def sink(record: dict[str, Any]) -> None:
        with get_connection() as conn, conn.transaction():
            create_activity_judge_shadow(conn, record)

    return sink


def build_registry(*, tools: ReadToolbox | None = None, llm: Any | None = None,
                   config_path: str | Path | None = None,
                   config: ProjectConfig | None = None) -> TeamRegistry:
    """Read the declaration, dynamically load every Team, and register it."""
    config = config or load_project_config(config_path)
    _validate_modules(config)
    # ★판정 LLM 은 운영 조립(도구를 직접 만드는 경로)에서만 넣는다 — 도구를 주입한 조립(시험)이
    #   조용히 네트워크를 타지 않게. 위 `build_travel_sources` 와 같은 이유다.
    judge_llm = None
    shadow_sink = None
    if tools is None:
        judge_llm = build_activity_judge_llm()
        shadow_sink = build_activity_judge_shadow_sink() if judge_llm is not None else None
        config.require_module("vector_rag", "default ReadToolbox")
        # ★바깥 소스는 **조립이 넣는다.** 도구가 스스로 만들면 테스트가 조용히
        #   네트워크를 탄다. 만드는 것 자체는 I/O 가 없다 — 호출할 때만 나간다.
        from app.domains.travel_ops.ports.data_sources import build_travel_sources

        sources = build_travel_sources(get_settings())
        tools = ReadToolbox(get_connection, policy_search=search_policy,
                            travel=sources,
                            report_extractor=build_report_extractor(),
                            kakao=build_kakao_local(),
                            google_places=build_google_places(limiter=sources.limiter))
        # ☆`[2026-09-29 이동 계산기 문제목록 #24·#31·#34]` 이동 계산기를 설정대로 켜거나 끈다 — 켜면 자료를 확인하고
        #   (없거나 판 명세와 다르면 기동을 멈춘다, 결정 15) 적재까지 한다(첫 고객 요청이 약 33초를 기다리지 않게).
        #   설정 mobility_data_dir 가 비면 꺼짐. 도구를 주입한 조립(시험)은 건너뛴다.
        from app.domains.travel_ops.instances.mobility import wiring as mobility_wiring

        # ★`[2026-10-05]` 따릉이 실시간 조회의 호출 한도 문(env 하루 한도 + DB 예산) — 이동 쪽은 infrastructure 를 import 하지 않으니 여기서 만들어 넘긴다.
        #   못 만들면 문 없이 부르지 않고 실시간을 끈다(이동 쪽이 처리).
        _bike_gate = None
        # ★설정 객체에 그 칸이 없을 수 있다(시험이 넣는 일부 칸짜리 대역) — 칸이 없으면 키가 없는 것과 같다(`wiring.configure_from_settings` 와 같은 규칙)
        if getattr(get_settings(), "seoul_openapi_key", ""):
            try:
                from app.domains.travel_ops.ports.data_sources.source_budget import build_gate

                _bike_gate = build_gate(get_settings(), ["seoul_bike"])
            except Exception as exc:  # noqa: BLE001 — 문을 못 만들면 실시간만 끈다(서비스는 계속)
                import logging

                logging.getLogger(__name__).warning("따릉이 실시간 한도 문을 못 만들었다: %s: %s", type(exc).__name__, exc)
        mobility_wiring.configure_from_settings(get_settings(), bike_gate=_bike_gate)
    teams = []
    capabilities: dict[str, str] = {}
    for declaration in config.teams:
        implementation = _import_ref(declaration.implementation_ref, declaration.team_id)
        team = _instantiate_team(implementation, tools, llm)
        if not hasattr(team, "manifest") or not hasattr(team, "execute"):
            raise CompositionError(
                f"team '{declaration.team_id}' implementation must provide manifest and execute"
            )
        if judge_llm is not None and hasattr(team, "judge_llm"):
            team.judge_llm = judge_llm
            team.judge_shadow_sink = shadow_sink
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


def build_google_places(*, limiter: Any = None) -> Any:
    """구글 장소 어댑터 — 키가 없으면 `None`(부르는 쪽이 「모름」으로 넘어간다).

    ★`[2026-09-30 사용자 결정]` 식당 가격 조회(`price`)는 하루 상한 없이 부르고, 월 무료 한도를 넘는
      첫 호출에 운영자에게 알린다(`google_over_free_alert`). 영업시간 조회는 지금처럼 DB 예산 안에서만 부른다.
    """
    key = getattr(get_settings(), "google_maps_api_key", "")
    if not key:
        return None
    from app.infrastructure.notify.ops_alert import google_over_free_alert
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget, google_caps
    from app.domains.travel_ops.ports.data_sources.google_places import GooglePlaces

    return GooglePlaces(api_key=key, budget=CallBudget(connection_factory=get_connection, caps=google_caps()),
                        limiter=limiter, on_over_free=google_over_free_alert)


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
                     config: ProjectConfig | None = None,
                     action_handlers: Any | None = None) -> Controller:
    """Assemble the application Controller and inject every concrete adapter.

    ★`config` 를 주면 **그 선언 그대로** 조립한다(2026-09-06, reload 계약).
      reload 는 "읽은 선언으로 조립하고, 그 선언의 revision 을 active 로 적는다"
      가 성립해야 한다. 여기서 다시 읽으면 그 사이 바뀐 선언으로 조립해 놓고
      **읽었던 revision 을 실행 중인 것으로 잘못 적게** 된다.
    """
    wire_optional_features()                      # 끌 수 있는 기능이 끼움 자리에 규칙을 꽂는다(2026-10-06)
    wire_domain_teams()                           # 팀이 자기 계산을 부품의 끼움 자리에 꽂는다(동)
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
        action_handlers=action_handlers if action_handlers is not None else build_action_handlers(),
        # ★`[2026-10-06]` 라우팅이 어긋났을 때 한 번 더 고르는 자리 — 어휘는 도메인이 갖는다.
        reroute=build_reroute(),
    )


def build_mcp_surface(app_getter):
    """개인 AI(Claude · ChatGPT · Cursor …)가 **사용자 본인의 여행**을 다루는 MCP 표면 — 고객 API 앱에 `/mcp/` 로 붙는다. `[2026-10-02]`

    ★도구는 웹 API(`/v1/web/*`)를 그대로 부르는 얇은 어댑터다(`mcp_server.py`) — 규칙을 새로 만들지 않는다. `mcp` 모듈 토글은 **요청마다** 읽는다
      (끄면 404). 쓰기 도구는 `travel.mcp.write_enabled` 가 켜졌을 때만 등록한다(기본 꺼짐 — 「MCP 는 read-only」). presentation 은 도메인을
      import 하지 못해(INV-CS-ARCH-001) 조립이 만들어 `create_app()` 에 준다. `app_getter` 는 이 표면이 붙을 앱을 돌려준다(네트워크 없이 부르려고).
    """
    from app.core.settings import get_guardrails
    from app.domains.travel_ops.modules.mcp.mcp_server import build_surface

    def enabled() -> bool:
        return load_project_config().module_enabled("mcp")

    write = bool(get_guardrails().get("travel.mcp.write_enabled"))
    return build_surface(app_getter, enabled=enabled, write_enabled=write)


def build_reroute():
    """라우팅 재배분기 — 꺼져 있으면 `None`(Controller 는 종전대로 곧바로 escalated). `[2026-10-06]`

    ★가드레일 `travel.routing.reroute_enabled` 로 끈다. 모델 호출이 늘어나는 자리라 끌 수 있어야 한다.
      ★**호출 때 읽는다** — 시험이 바꿔 끼운 값을 따른다.
    """
    def _call(**kwargs):
        from app.core.settings import get_guardrails

        if not get_guardrails().get("travel.routing.reroute_enabled"):
            return None
        from app.domains.travel_ops.components.core_hooks.reroute import reroute

        return reroute(**kwargs)
    return _call


def wire_optional_features() -> list[str]:
    """끌 수 있는 기능이 **자기 규칙을 끼움 자리에 꽂는 곳**. `[2026-10-06]` D-CS-013

    ★왜 여기인가. 필수 부품이 기능 쪽을 직접 import 하면 그 기능을 바꾸거나 끄는 순간 부품이
      같이 멈춘다 — 실제로 감시·안내가 웹 로그인 표를 직접 보고 있었다. 방향을 뒤집어
      **기능이 조립 때 자기 규칙을 등록**하고, 부품은 끼움 자리만 본다.

    꽂지 않으면 부품은 기본값으로 돈다(감시 대상 좁히기 없음 = 전부 감시).
    """
    from app.domains.travel_ops.components.itinerary import trip_scope
    from app.domains.travel_ops.modules.web_account.guest_policy import not_guest_sql

    # 게스트(로그인 안 한 웹 사용자)의 여행은 안내·감시 대상이 아니다 — D-CS-011 §2.
    trip_scope.register("web_account.guest", not_guest_sql)

    # 운영자가 관리 화면에서 바꾼 값(채팅 해석 방식 등)을 읽는 자리. 표는 웹 제한값 기능이 들고 있다.
    from app.domains.travel_ops.components import settings_hook
    from app.domains.travel_ops.modules.web_account import web_guard

    settings_hook.register(lambda tenant_id, name: web_guard.values(tenant_id).get(name))

    # 접수 읽기의 진행 알림을 화면이 읽는 모양(SSE)으로 포장하는 자리.
    from app.domains.travel_ops.components import progress_hook
    from app.domains.travel_ops.modules.live_progress import op_stream

    progress_hook.register(op_stream.sse)

    # ★`[2026-10-07 사용자 지시]` 일정 항목 짚기 — 우리 데이터로 가르친 모델 자리. `.env` 에 `ACOP_OLLAMA_POINTER_MODEL` 이 있을 때만 꽂는다
    #  (없으면 낱말 규칙만 — 지금까지와 같다). 켜고 끄기: 가드레일 `travel.pointer.mode`(off · shadow · on).
    from app.domains.travel_ops.components.conversation import item_pointer

    pointer = item_pointer.register_from_settings(get_settings())
    return (list(trip_scope.registered())
            + (["settings"] if settings_hook.is_registered() else [])
            + (["progress"] if progress_hook.is_registered() else [])
            + (["item_pointer"] if pointer is not None else []))


def wire_domain_teams() -> list[str]:
    """**팀이 자기 계산을 부품의 끼움 자리에 꽂는 곳.** `[2026-10-06]` D-CS-013

    ★왜 여기인가. 감시 · 대화 · 계획 · 접수 부품이 요식 · 이동 · 활동 팀 **내부**를 직접 가져다
      썼다(14곳). 그러면 「팀은 꽂고 뺄 수 있다」가 거짓이 된다 — 팀 하나를 빼면 부품이 import
      단계에서 깨진다. 방향을 뒤집어 팀이 조립 때 등록하고, 부품은 자리만 본다.

    ★꽂지 않으면 부품은 그 팀이 없을 때의 길로 간다 — 이동은 어림값, 요식 판정은 모름,
      활동 유사도 없음, 그 종류의 감시는 건너뜀. **값을 지어내지 않는다**(`components/team_hooks/`).
    """
    from app.domains.travel_ops.components.team_hooks import dining_ledger, legs, similarity, watch_planners

    # 이동 — 두 지점 사이 시간 · 노선 · 사고 반영. 도보 상한은 이동 팀의 가드레일에 있다.
    from app.domains.travel_ops.instances.mobility import wiring as mobility_wiring
    from app.domains.travel_ops.instances.mobility.engine import guardrails as mobility_guardrails

    def walk_limit_m() -> float | None:
        """`mobility.limits.walk_m.default`. 선언에 없으면 None — 부르는 쪽이 보수적으로 간다."""
        try:
            return float(mobility_guardrails.lookup("mobility.limits.walk_m.default"))
        except mobility_guardrails.GuardrailMissing:
            return None

    # ★함수를 **그 자리에서 쥐지 않고** 부를 때 모듈에서 읽는다 — 이동 계산기는 켜짐/꺼짐이 실행 중에
    #   바뀌고(`wiring.configure`), 시험이 팀 함수를 바꿔 끼우기도 한다. 객체를 쥐면 옛 것을 계속 쓴다.
    legs.register(leg_planner=lambda *a, **kw: mobility_wiring.leg_planner(*a, **kw),
                  disruptions_from_events=lambda events: mobility_wiring.disruptions_from_events(events),
                  walk_limit_m=walk_limit_m,
                  basis=lambda: mobility_wiring.basis())

    # 요식 — 원장이 식당의 정본이다(근처 들여놓기 · 시간대 판정 · 이름으로 찾기).
    from app.domains.travel_ops.instances.dining import ledger as dining_ledger_impl
    from app.domains.travel_ops.instances.dining import nearby as dining_nearby

    dining_ledger.register(add_nearby=lambda *a, **kw: dining_nearby.add_nearby(*a, **kw),
                           states=lambda *a, **kw: dining_ledger_impl.dining_states(*a, **kw),
                           state=lambda *a, **kw: dining_ledger_impl.dining_state(*a, **kw),
                           find_by_name=lambda *a, **kw: dining_ledger_impl.find_place_by_name(*a, **kw))

    # 활동 — 비슷한 곳 순서와 설문 선호.
    from app.domains.travel_ops.instances.activity import similarity as activity_similarity

    similarity.register(score=lambda *a, **kw: activity_similarity.score(*a, **kw),
                        preference_of=lambda c: activity_similarity.preference_of(c),
                        distance_first=lambda pref: activity_similarity.distance_first(pref))

    # 감시 묶음 — 항목 종류마다 그 팀의 점검 계산.
    from app.domains.travel_ops.instances.activity import team as activity_team
    from app.domains.travel_ops.instances.dining import team as dining_team
    from app.domains.travel_ops.instances.mobility import team as mobility_team

    watch_planners.register("activity", lambda *a, **kw: activity_team.plan_activity_trigger(*a, **kw))
    watch_planners.register("dining", lambda *a, **kw: dining_team.plan_dining_trigger(*a, **kw))
    watch_planners.register("mobility", lambda *a, **kw: mobility_team.plan_mobility_trigger(*a, **kw))

    return ([name for name, hook in (("legs", legs), ("dining_ledger", dining_ledger),
                                     ("similarity", similarity)) if hook.is_registered()]
            + [f"watch:{kind}" for kind in watch_planners.registered()])


def build_domain_routers() -> list:
    """**고객 API 앱**이 여는 도메인 HTTP 표면 — 여행 API · 위임. ★`[2026-09-29]` 시나리오 모드 · 웹 제한값 운영 API 는
    운영 앱으로 옮겼다(`build_ops_routers`).

    `[정정 2026-09-22]` 이 줄은 「여행 API 하나」라고 적혀 있었다. 시나리오 라우터가
    늘어난 뒤에도 안 고쳐져 있었고, 여기에 위임까지 더해 셋이 됐다.

    ★presentation 은 도메인을 import 하지 못한다(INV-CS-ARCH-001). 그래서 조립이
      만들어 `create_app()` 에 넣는다. 점검기는 **처음 쓸 때** 조립한다 — 기동이
      바깥 소스(기상·교통·대기) 조립을 기다리지 않게.
    """
    wire_optional_features()                      # 동(고객 API 앱 경로)
    wire_domain_teams()                           # 동
    from app.domains.travel_ops.entry.trip_api import build_trip_router
    from app.domains.travel_ops.modules.web_account.admin_customer_api import build_router as build_customer_support_router

    def check_factory():
        from app.core.settings import get_settings
        from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
        from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck

        return DisruptionCheck(build_travel_sources(get_settings())).check

    def cached_check_factory():
        # ★`[2026-10-06]` MCP 일정 위험 점검의 기본 — 공유 응답 캐시만 읽는다(바깥에 안 나간다 · 하루 한도를 안 쓴다)
        from app.core.settings import get_settings
        from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
        from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck

        return DisruptionCheck(build_travel_sources(get_settings(), cache_only=True)).check

    def fresh_check_factory():
        # ★`[2026-10-06]` MCP 일정 위험 점검의 「새로 확인」 — 낮은 우선순위(소스의 하루 · 이번 달 한도의 `fresh_share` 까지만 쓰고 DB 를 못 읽으면 안 부른다)
        from app.core.settings import get_guardrails, get_settings
        from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
        from app.domains.travel_ops.ports.data_sources.disruptions import DisruptionCheck

        share = float(get_guardrails().get("travel.mcp.risk_check.fresh_share"))
        return DisruptionCheck(build_travel_sources(get_settings(), low_priority_share=share)).check

    def chat_factory():
        # ★자유 문장에서 신고를 뽑는 LLM — 로컬 Ollama(Gemma 4). 없으면 None → 추출 없이 escalate.
        from app.core.settings import get_settings
        from app.infrastructure.ollama_chat import from_settings

        return from_settings(get_settings())

    from app.domains.travel_ops.entry.delegation_api import build_delegation_router
    from app.domains.travel_ops.modules.web_account.web_auth_api import build_auth_router

    def place_factory():
        # ★일정 생성기의 **마지막 후보 소스**(`planner.py`) — `place_catalog` 이 비었을 때만
        #   실제로 불린다. 키가 없으면 `None` 이고 그러면 그 경로가 아예 안 열린다.
        from app.core.settings import get_settings
        from app.domains.travel_ops.ports.data_sources.base import build_travel_sources

        return build_travel_sources(get_settings()).place

    kakao_factory = build_kakao_local

    return [build_trip_router(check_factory=check_factory, classifier_factory=build_classifier,
                              chat_factory=chat_factory, place_factory=place_factory,
                              kakao_factory=kakao_factory,
                              # ★채팅의 질문 — 여행 규정 검색(RAG). 문턱은 `travel.question.min_policy_score`
                              policy_search_factory=lambda: search_policy,
                              # ★`[2026-10-06]` MCP 읽기 도구 「일정 위험 점검」 — 캐시만 읽는 점검기(기본) · 낮은 우선순위로 새로 부르는 점검기(fresh)
                              cached_check_factory=cached_check_factory, fresh_check_factory=fresh_check_factory),
            # ★위임 — 승인 뒤 자동 실행을 여는 둘째 문을 주고 거두는 자리(2026-09-22).
            #   운영 화면 `/ui/delegations` 가 이 경로를 부른다.
            build_delegation_router(),
            # ★소셜 로그인(구글 먼저) — 업체 설정이 없으면 `GET /v1/web/auth/providers` 가 빈 목록이고 나머지는 「쓸 수 없다」로 답한다(2026-10-03)
            build_auth_router(),
            build_customer_support_router()]


def build_admin_snapshot(conn, tenant_id: str, default_chat_limit: int):
    """운영 화면의 도메인 조회를 조립 자리에서 제공한다."""
    from app.domains.travel_ops.modules.web_account.admin_snapshot import snapshot

    return snapshot(conn, tenant_id, default_chat_limit)


def build_ops_routers() -> list:
    """**운영 앱**(`app/ops_entrypoint.py`)이 여는 도메인 경로 — 웹 제한값 운영 API. `[2026-09-29]`

    ★고객 API 앱(8042)에는 없다(사용자 지시 — 운영 경로는 외부에서 닿지 못하게 다른 프로세스 · 127.0.0.1).
    ★`[2026-09-30 사용자 지시]` **시나리오(시연) 모드는 운영 앱에서 뗐다** — 실서비스 운영 화면과 데모가 같은 프로세스에 있으면
      안 된다. 압축 보관: `legacy/scenario_mode/scenario_mode_2026-09-30.zip`(복원 방법은 그 안의 README.md).
    """
    from app.domains.travel_ops.modules.web_account.web_limits_api import build_limits_router, build_retention_ops_router

    return [build_limits_router(), build_retention_ops_router()]


def build_subject_resolver():
    """Case 가 가리키는 대상을 확인하는 도메인 확인기(`[결정 2026-09-17]`).

    ★선언이 없으면 `None` — 그 조립에서 `subject_ref` 를 보내면 422 다(조용히 무시하지 않는다).
    """
    try:
        from app.domains.travel_ops.components.core_hooks.subjects import resolve_subject
    except ImportError:
        return None
    return resolve_subject


def build_subject_interpreter():
    """`[2026-09-17]` 대상이 정해진 고객 Case 의 문장 해석기. 선언이 없으면 `None`."""
    try:
        from app.domains.travel_ops.components.core_hooks.subjects import make_subject_interpreter
    except ImportError:
        return None
    return make_subject_interpreter(build_report_extractor())


def build_action_handlers():
    """제안의 도메인 적용기 — 승인 없이 적용되는 것(`[결정 2026-09-17]`)과 승인 뒤 실행되는 것(`[2026-09-18]`).

    ★선언이 없으면 빈 표 — 승인 없는 제안은 전부 escalated 로 간다.
    """
    from app.core.actions import ActionHandlers
    try:
        from app.domains.travel_ops.components.actions.booking_actions import APPROVED_HANDLERS
        from app.domains.travel_ops.components.actions.itinerary_actions import ACTION_HANDLERS
    except ImportError:
        return ActionHandlers()
    # ★`[2026-09-18]` 승인된 예약 제안의 적용기도 싣는다(`auto_apply=False` — 승인 없이는 안 돈다).
    return ActionHandlers([*ACTION_HANDLERS, *APPROVED_HANDLERS])


def build_verification(*, config=None):
    """도메인의 대조 선언을 가져온다 (v7 §9-E).

    ★basement 는 규칙 엔진만 갖고, **어휘는 도메인이 선언**한다.
      도메인을 갈아끼우면 이 함수가 가리키는 모듈만 바뀐다 — 2026-09-10 에
      실제로 `customer_ops` → `travel_ops` 로 한 줄 바꿨다.

    ★선언이 없으면 **빈 정책**을 준다 — 그러면 대조할 것이 없어 통과가 아니라
      "선언되지 않은 필드" 로 전부 거부된다. 도메인을 안 붙이면 아무 Action 도 못 한다.
      조용히 통과시키는 것보다 낫다.
    """
    from app.core.verification import VerificationPolicy
    try:
        from app.domains.travel_ops.components.core_hooks.verification_policy import (
            FACT_QUERIES, TRAVEL_OPS_POLICY)
    except ImportError:
        return VerificationPolicy(), ()
    return TRAVEL_OPS_POLICY, FACT_QUERIES


__all__ = ["CompositionError", "build_broker", "build_classifier", "build_controller", "build_report_extractor",
           "build_google_places", "build_graph_store", "build_registry", "build_team_executor"]
