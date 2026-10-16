"""Application composition root.

Concrete adapters and Team implementations are assembled here.  The core
runtime only receives their ports, registries, and callable dependencies.
"""
from __future__ import annotations

import importlib
import inspect
import logging
import threading
from pathlib import Path
from typing import Any

from app.application.controller import Controller
from app.core.context import ContextBroker
from app.core.project_config import ProjectConfig, load_project_config, config_revision
from app.core.registry import TeamRegistry
from app.core.service_bindings import BindingTable, collect_services, collect_registration, collecting_services
from app.core.remote_team.a2a_executor import A2ATeamExecutor
from app.core.remote_team.executor import TeamExecutorPort
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


_mobility_configuration_lock = threading.Lock()
_mobility_configuration_key = None


def _configure_mobility(settings):
    """Engine configuration is process-scoped; reload never edits a live engine.

    Changed engine settings require a process restart. Team enable/disable and
    service-table reload remain independent of this engine lifecycle.
    """
    global _mobility_configuration_key
    from app.domains.travel_ops.instances.mobility import wiring as mobility_wiring

    key = tuple(getattr(settings, name, None) for name in (
        "mobility_data_dir", "mobility_gh_url", "seoul_openapi_key",
        "guardrails_path", "mobility_local_router"))
    with _mobility_configuration_lock:
        mode = mobility_wiring.mode()
        initial_failure = mode == "broken" and _mobility_configuration_key is None
        if mode != "unconfigured" and not initial_failure:
            if key != _mobility_configuration_key:
                raise CompositionError("live mobility engine settings require a process restart")
            return {"mode": mobility_wiring.mode()}
        result = _configure_mobility_once(settings)
        _mobility_configuration_key = key
        return result


def _configure_mobility_once(settings):
    """요청 조립과 출발 안내 단독 실행이 같은 이동 기동·호출 예산을 사용한다."""
    from app.domains.travel_ops.instances.mobility import wiring as mobility_wiring
    bike_gate = None
    if getattr(settings, 'seoul_openapi_key', ''):
        try:
            from app.domains.travel_ops.ports.data_sources.source_budget import build_gate
            bike_gate = build_gate(settings, ['seoul_bike'])
        except Exception as exc:  # noqa: BLE001 — 문 없이는 따릉이 실시간을 끈다
            import logging
            logging.getLogger(__name__).warning('따릉이 실시간 한도 문 준비 실패: %s', type(exc).__name__)
    return mobility_wiring.configure_from_settings(settings, bike_gate=bike_gate)


def build_mobility_departure_observer(settings, sources, *, guardrails=None):
    """현재 구간 재검증에 기존 도착정보 소스·캐시·정책을 꽂는다. 배포·전송은 하지 않는다."""
    from app.core.service_bindings import current_bindings
    from app.core.team_availability import TeamUnavailable

    table = current_bindings()
    if table is not None:
        try:
            table.registry.require_runnable("mobility")
        except TeamUnavailable as exc:
            logging.getLogger(__name__).info("departure_observation_omitted", extra={
                "team_id": exc.team_id, "reason": exc.reason, "composition_revision": table.revision})
            return None
    if not getattr(settings, 'mobility_data_dir', ''):
        return None
    from app.domains.travel_ops.instances.mobility import wiring as mobility_wiring
    if mobility_wiring.mode() == 'unconfigured':
        _configure_mobility(settings)
    if mobility_wiring.mode() != 'enabled':
        raise mobility_wiring.MobilityUnavailable('출발 관측에 필요한 이동 계산기가 켜지지 않았다')
    if guardrails is None:
        from app.core.settings import get_guardrails
        guardrails = get_guardrails()
    import math
    policy = {key: guardrails.get(path) for key, path in {
        'max_age_seconds': 'travel.bus_arrival_cache_seconds',
        'max_provider_age_seconds': 'mobility.departure_observation.max_provider_age_seconds',
        'max_provider_clock_ahead_seconds': 'mobility.departure_observation.max_provider_clock_ahead_seconds',
    }.items()}
    for key, value in policy.items():
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or value < 0 or (key != 'max_provider_clock_ahead_seconds' and value == 0)):
            raise ValueError(f'출발 관측 정책 값이 올바르지 않다: {key}')
    source = getattr(sources, 'bus_arrival', None)
    def bus_arrival(route_id, **kwargs):
        if source is None:
            return {'status': 'unavailable', 'reason': 'bus_arrival_source_unconfigured'}
        return source.boardable_arrival(route_id, **policy, **kwargs)
    subway_source = getattr(sources, 'subway_arrival', None)
    subway_policy = dict(policy)
    if subway_source is not None:
        age = guardrails.get('travel.subway_arrival_cache_seconds')
        if (isinstance(age, bool) or not isinstance(age, (int, float)) or not math.isfinite(age) or age <= 0):
            raise ValueError('지하철 출발 관측 보관 정책 값이 올바르지 않다')
        subway_policy['max_age_seconds'] = age
    def subway_arrival(station, **kwargs):
        if subway_source is None:
            return {'status': 'unavailable', 'reason': 'subway_arrival_source_unconfigured'}
        return subway_source.boardable_arrival(station, **subway_policy, **kwargs)
    from app.domains.travel_ops.components.watch.departure_revalidation import build_observer
    return build_observer(bus_arrival=bus_arrival, subway_arrival=subway_arrival,
                          basis_validator=lambda basis: mobility_wiring.validate_departure_basis(basis))

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


def build_activity_judge_budget():
    """판정 LLM 호출 예산 — 판정 종류 → 「불러도 되나」. `external_call_budget` 의 두 줄로 센다. `[2026-10-13]`
    활동 코어 전달 사항 7번.

    ★줄: `activity_judge`(원문 해석) · `activity_judge_web`(웹 검색 — 호출당 비용이 약 100배라 따로 센다).
      상한은 `guardrails.yaml travel.activity_judge.budget`. 프로세스 · 재기동과 상관없이 DB 에서 같이 센다.
    ★넘거나 세다가 실패하면 활동이 **부르지 않는다**(`budget_exhausted` · `budget_unreadable`) — 모델 서버 넘김
      장치(`_llm_failover_budget`)와 반대다. 판정 LLM 은 규칙 판정을 돕는 쪽이라 안 불러도 고객 답이 나간다.
    """
    from app.domains.travel_ops.instances.activity.judge.modes import budget_caps, budget_meter
    from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget

    budget = CallBudget(connection_factory=get_connection, caps=budget_caps())
    return lambda kind: budget.try_reserve(budget_meter(kind))


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
    judge_budget = None
    production = tools is None           # 아래에서 tools 를 만들어 넣으므로 먼저 적어 둔다
    if tools is None:
        judge_llm = build_activity_judge_llm()
        shadow_sink = build_activity_judge_shadow_sink() if judge_llm is not None else None
        judge_budget = build_activity_judge_budget() if judge_llm is not None else None
        config.require_module("vector_rag", "default ReadToolbox")
        # ★바깥 소스는 **조립이 넣는다.** 도구가 스스로 만들면 테스트가 조용히
        #   네트워크를 탄다. 만드는 것 자체는 I/O 가 없다 — 호출할 때만 나간다.
        from app.domains.travel_ops.ports.data_sources import build_travel_sources

        sources = build_travel_sources(get_settings())
        tools = ReadToolbox(get_connection, policy_search=search_policy,
                            travel=sources,
                            report_extractor=build_report_extractor(),
                            kakao=build_kakao_local(),
                            google_places=build_google_places(limiter=sources.limiter),
                            place_status=build_place_status())
        # ☆`[2026-09-29 이동 계산기 문제목록 #24·#31·#34]` 이동 계산기를 설정대로 켜거나 끈다 — 켜면 자료를 확인하고
        #   (없거나 판 명세와 다르면 기동을 멈춘다, 결정 15) 적재까지 한다(첫 고객 요청이 약 33초를 기다리지 않게).
        #   설정 mobility_data_dir 가 비면 꺼짐. 도구를 주입한 조립(시험)은 건너뛴다.
    registry = TeamRegistry()
    from app.domains.travel_ops.components.core_hooks.routing import KNOWN_TEAM_CASE_TYPES

    for team_id, case_types in KNOWN_TEAM_CASE_TYPES.items():
        registry.declare_case_types(team_id, case_types)
    teams = []
    capabilities: dict[str, str] = {}
    for declaration in config.teams:
        if not declaration.active:
            registry.declare_unavailable(declaration.team_id, "disabled",
                                         capabilities=declaration.capabilities)
            continue
        try:
            implementation = _import_ref(declaration.implementation_ref, declaration.team_id)
            team = _instantiate_team(implementation, tools, llm)
        except Exception as exc:
            if declaration.required:
                raise
            logging.getLogger(__name__).error("optional_team_load_failed team_id=%s error_type=%s",
                                              declaration.team_id, type(exc).__name__)
            registry.declare_unavailable(declaration.team_id, "load_failed",
                                         capabilities=declaration.capabilities)
            continue
        if not hasattr(team, "manifest") or not hasattr(team, "execute"):
            raise CompositionError(
                f"team '{declaration.team_id}' implementation must provide manifest and execute"
            )
        if judge_llm is not None and hasattr(team, "judge_llm"):
            # ★`[2026-10-09]` 팀이 받는 모드를 밝혔으면 지킨다(D-CS-015 — develop 판 활동 팀은 `rule` · `shadow` 만).
            #   `llm` 을 켰는데 팀이 섀도로만 돈다면 조용한 축소다 — 기동을 멈추고 이유를 말한다.
            mode = getattr(get_settings(), "activity_judge_mode", "rule")
            supported = getattr(team, "judge_modes", None)
            if supported is not None and mode not in supported:
                raise CompositionError(
                    f"team '{declaration.team_id}' supports activity_judge_mode {list(supported)}, got '{mode}'")
            team.judge_llm = judge_llm
            team.judge_shadow_sink = shadow_sink
            if hasattr(team, "judge_budget"):
                team.judge_budget = judge_budget
        if production and hasattr(team, "live_lookup"):
            # ★`[2026-10-13]` 활동 → 코어 전달 사항 1번 — 배치가 저장한 실시간 운영 상태(`activity.ac_live_status`)를 팀이 읽는 함수.
            #   팀은 DB 를 직접 열지 않으므로 조립이 꽂는다(`judge_budget` 과 같은 방식). 도구를 주입한 조립(시험)에는 꽂지 않는다.
            from app.domains.travel_ops.instances.activity import live_store

            team.live_lookup = live_store.build_lookup(get_connection)
        team.manifest = team.manifest.model_copy(update={"active": declaration.active,
                                                         "team_id": declaration.team_id})
        if declaration.capabilities is not None and set(declaration.capabilities) != set(team.manifest.capabilities):
            raise CompositionError(f"declared capabilities do not match manifest: {declaration.team_id}")
        for capability in team.manifest.capabilities:
            previous = capabilities.get(capability)
            if previous is not None:
                raise CompositionError(
                    f"duplicate capability '{capability}' claimed by teams '{previous}' and '{declaration.team_id}'"
                )
            capabilities[capability] = declaration.team_id
        teams.append(team)
        registry.register(team)
    return registry


def build_team_executor(registry: TeamRegistry, *, config: ProjectConfig | None = None,
                        transport: Any | None = None, capability_resolver: Any | None = None,
                        execution_planner: Any | None = None, diagnostic_recorder: Any | None = None) -> TeamExecutorPort:
    config = config or load_project_config()
    _validate_modules(config)
    if config.ports.team_executor == "local":
        from app.domains.travel_ops.components.watch.batch_executor import TravelBatchExecutor

        return TravelBatchExecutor(registry, planner=execution_planner, diagnostic_recorder=diagnostic_recorder)
    if transport is None or capability_resolver is None:
        raise CompositionError("port team_executor=a2a requires injected transport and capability_resolver")
    return A2ATeamExecutor(transport, capability_resolver, registry=registry)


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
                     action_handlers: Any | None = None,
                     execution_planner: Any | None = None) -> Controller:
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
    if config.response_review.enabled:
        registry.require_runnable(config.response_review.owner_team_id)
    diagnostic_recorder = build_operations_recorder(config=config)
    team_executor = team_executor or build_team_executor(registry, config=config, execution_planner=execution_planner,
                                                         diagnostic_recorder=diagnostic_recorder)
    verification_policy, fact_queries = build_verification(config=config)
    controller = Controller(
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
        diagnostic_recorder=diagnostic_recorder,
    )
    with collect_services() as bindings:
        wire_domain_teams(config=config, registry=registry)
    if config.response_review.enabled:
        registry.require_runnable(config.response_review.owner_team_id)
    controller.composition_revision = config_revision(config)
    controller.project_config = config.model_copy(deep=True)
    controller.service_bindings = BindingTable(bindings, registry, controller.composition_revision)
    if tools is None and ("legs", "leg_planner") in bindings:
        _configure_mobility(get_settings())
    return controller


def build_operations_recorder(*, config: ProjectConfig | None = None):
    from app.application.operations_diagnostics import execution_recorder

    config = config if config is not None else load_project_config()
    collect = execution_recorder(connection_factory=get_connection, policy_version=config_revision(config))

    def record(payload):
        # 중립 Controller는 subject_ref의 업무 뜻을 모른다. 조립부만 여행 UUID를 추출한다.
        if payload.get("case_id") and not payload.get("customer_id"):
            with get_connection() as conn:
                case = repository.get_case(conn, tenant_id=payload["tenant_id"], case_id=payload["case_id"])
            if case is not None:
                payload = {**payload, "customer_id": case["customer_id"],
                           "subject_ref": (case.get("state_json") or {}).get("subject_ref")}
        ref = payload.get("subject_ref") or {}
        return collect({**payload, "trip_id": payload.get("trip_id") or (ref.get("id") if ref.get("kind") == "trip" else None)})

    return record


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

    # ★`[2026-10-15 사용자 지시]` 관리 콘솔 「모델 경로」(local · ssh · api) — 채팅 해석 · 계획 읽기 · 번역은 부를 때마다,
    #  일정 짚기 · 공지 확인은 주소를 부를 때마다 읽는다(재기동 없이 반영, 운영 설정 캐시만큼 늦을 수 있다). SSH 터널은 앱 밖 프로그램이 연다.
    from app.infrastructure import ollama_chat

    route_tenant = get_settings().tenant_id
    ollama_chat.register_route_provider(lambda: settings_hook.model_route(route_tenant))

    # 접수 읽기의 진행 알림을 화면이 읽는 모양(SSE)으로 포장하는 자리.
    from app.domains.travel_ops.components import progress_hook
    from app.domains.travel_ops.modules.live_progress import op_stream

    progress_hook.register(op_stream.sse)

    from app.domains.travel_ops.ports.data_sources import simulation_hook
    from app.domains.travel_ops.components.watch import simulation

    simulation_hook.register(simulation)

    # ★`[2026-10-07 사용자 지시]` 일정 항목 짚기 — 우리 데이터로 가르친 모델 자리. `.env` 에 `ACOP_OLLAMA_POINTER_MODEL` 이 있을 때만 꽂는다
    #  (없으면 낱말 규칙만 — 지금까지와 같다). 켜고 끄기: 가드레일 `travel.pointer.mode`(off · shadow · on).
    from app.domains.travel_ops.components.conversation import item_pointer

    route_settings = get_settings()
    pointer = item_pointer.register_from_settings(route_settings, base_url_for=lambda: ollama_chat.route_base_url(route_settings))

    # ★`[2026-10-13 사용자 지시]` 공지 「끝났나」 2차 확인 — 규칙이 「끝남」이라 한 공지를 가르친 모델이 한 번 더 본다. `.env` 에
    #  `ACOP_OLLAMA_NOTICE_MODEL` 이 있을 때만 꽂는다(없으면 규칙만). 켜고 끄기: 가드레일 `travel.notice_end.mode`(off · shadow · on).
    from app.domains.travel_ops.ports.data_sources import notice_end_model

    notice_judge = notice_end_model.register_from_settings(route_settings, base_url_for=lambda: ollama_chat.route_base_url(route_settings))
    # `[2026-10-13 사용자 결정]` 여행 영향이 없다고 보고 보내지 않은 「기타」 재난 문자를 DB 에 남긴다(관리자 웹앱 「걸러진 재난 문자」)
    from app.domains.travel_ops.components.watch import notice_exclusions

    notice_exclusions.register()
    return (list(trip_scope.registered())
            + (["settings"] if settings_hook.is_registered() else [])
            + (["progress"] if progress_hook.is_registered() else [])
            + (["item_pointer"] if pointer is not None else [])
            + (["notice_end_model"] if notice_judge is not None else []))


def wire_domain_teams(*, config: ProjectConfig | None = None, registry: TeamRegistry | None = None) -> list[str]:
    from app.core.team_availability import TeamUnavailable

    config = config or load_project_config()
    if registry is None or not collecting_services():
        return _wire_domain_providers(config=config, registry=registry)
    connected = []
    for declaration in config.teams:
        try:
            registry.require_runnable(declaration.team_id)
        except TeamUnavailable:
            continue
        try:
            with collect_services() as staged:
                names = _wire_domain_providers(config=config, active_ids={declaration.team_id})
        except CompositionError:
            raise
        except Exception as exc:
            if declaration.required:
                raise
            registry.declare_unavailable(declaration.team_id, "load_failed")
            logging.getLogger(__name__).error("optional_team_hook_load_failed team_id=%s error_type=%s",
                                              declaration.team_id, type(exc).__name__)
            continue
        for group in {key[0] for key in staged}:
            collect_registration(group, {key: value for (kind, key), value in staged.items() if kind == group})
        connected.extend(names)
    return connected


def _dining_agent_judge():
    """요식 판정 에이전트 — 가드레일 `travel.dining.agent_judge.enabled`(기본 켜짐)일 때 실행기를 만든다. `[2026-10-13 · 2026-10-16]`
    ★실행기는 `instances/dining/judge.run` — 판정을 접수 확인 줄에 합친다(화면 문장은 지금처럼 코드가 만든다).
    ★모의 모델(`ACOP_LLM_PROVIDER=mock` — 시험 · CI)이면 만들지 않는다 — 가짜 키로 실제 모델을 부르지 않게.

    모델은 가드레일 `model` 로 고른다 — `openai:<모델>`(키 `ACOP_OPENAI_API_KEY`) · `ollama:<모델>`(주소 `ACOP_OLLAMA_BASE_URL`).
    ★키 · 주소가 없으면 만들지 않고 경고만 남긴다(없으면 규칙 검사 그대로 — 기동을 막지 않는다)."""
    from app.core.settings import dining_agent_judge, get_settings

    judge_settings = dining_agent_judge()
    if judge_settings is None:
        return None
    from functools import partial

    from app.domains.travel_ops.instances.dining import judge as dining_judge
    from app.infrastructure.llm.tool_chat import OllamaToolChat, OpenAIToolChat

    settings = get_settings()
    if getattr(settings, "llm_provider", "") == "mock":
        return None
    kind, _, model = judge_settings["model"].partition(":")
    if kind == "openai" and (settings.openai_api_key or "").strip():
        chat = OpenAIToolChat(api_key=settings.openai_api_key, model=model or "gpt-6-luna")
    elif kind == "ollama" and (settings.ollama_base_url or "").strip():
        chat = OllamaToolChat(base_url=settings.ollama_base_url, model=model or settings.ollama_model)
    else:
        logging.getLogger(__name__).warning("dining agent judge enabled but model %s has no key/address — rule review only",
                                            judge_settings["model"])
        return None
    # ★`[2026-10-16]` 원장이 모를 때 에이전트가 고를 바깥 조회 — 지도(카카오 `map_search`) · 실시간 영업(구글 `live_open_check`).
    #   ☆전에는 기본 `DiningTools(connect)` 라 둘 다 None — 스위치를 켜도 바깥 조회는 늘 「모름」이었다(LLM 켜짐 점검).
    #   키가 없으면 그 도구만 「모름」(어댑터 None). 호출 예산은 각 어댑터의 DB 예산 그대로다
    from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

    tools_factory = partial(DiningTools, kakao=build_kakao_local(), google=build_google_places())
    return partial(dining_judge.run, chat=chat, model=judge_settings["model"], deadline_s=judge_settings["deadline_s"],
                   tools_factory=tools_factory)


def _dining_meal_picker():
    """대체 식당 셋 중 고르기 — 가드레일 `travel.dining.meal_pick.enabled` 를 켰을 때만 선택기를 만든다(기본 꺼짐 → None). `[2026-10-15]`

    모델은 가드레일 `model` — `openai:<모델>`(키 `ACOP_OPENAI_API_KEY`) · `ollama:<모델>`(주소 `ACOP_OLLAMA_BASE_URL`).
    ★키 · 주소가 없으면 만들지 않고 경고만 남긴다 — 선택기가 없으면 규칙 1등 그대로다(기동을 막지 않는다)."""
    from app.core.settings import dining_meal_pick, get_settings

    pick_settings = dining_meal_pick()
    if pick_settings is None:
        return None
    from app.domains.travel_ops.components.planning import meal_pick

    settings = get_settings()
    kind, _, model = pick_settings["model"].partition(":")
    if kind == "openai" and (settings.openai_api_key or "").strip():
        from app.infrastructure.llm_failover import OpenAIChat

        chat = OpenAIChat(api_key=settings.openai_api_key, model=model or "gpt-6-luna", timeout=30.0)
    elif kind == "ollama" and (settings.ollama_base_url or "").strip():
        from app.infrastructure.ollama_chat import OllamaChat

        chat = OllamaChat(base_url=settings.ollama_base_url, model=model or settings.ollama_model, timeout=60.0)
    else:
        logging.getLogger(__name__).warning("dining meal_pick enabled but model %s has no key/address — rule pick only",
                                            pick_settings["model"])
        return None
    # ★`[2026-10-16 사용자 결정]` 「흐름 한 칸」 — 규칙 1위는 그대로 두고 모델이 그날 흐름 · 취향으로 다른 안 하나를 고른다(고객이 고른다).
    #   1위를 바꾸는 `make_picker` 는 평가용으로 남긴다(eval/runners/dining_alternatives)
    return meal_pick.make_flow_picker(chat)


def _wire_domain_providers(*, config=None, registry=None, active_ids=None) -> list[str]:
    """Connect only active, loaded providers; collect_services isolates candidate assembly.

    Outside collection this remains the explicit standalone/unit-test assembly seam.
    Production stores the returned registrations in a per-controller BindingTable.
    """
    from app.domains.travel_ops.components.team_hooks import activity_alternatives, activity_ledger, dining_alternatives, dining_ledger, legs, lodging_ledger, mobility_shapes, similarity, watch_planners

    if active_ids is not None:
        pass
    elif registry is not None:
        active_ids = {m.team_id for m in registry.manifests() if m.active}
    else:
        config = config or load_project_config()
        active_ids = {declaration.team_id for declaration in config.teams if declaration.active}
    if "mobility" in active_ids:
        # 이동 — 두 지점 사이 시간 · 노선 · 사고 반영. 도보 상한은 이동 팀의 가드레일에 있다.
        from app.domains.travel_ops.instances.mobility import wiring as mobility_wiring
        from app.domains.travel_ops.instances.mobility import route_shape as mobility_route_shape
        from app.domains.travel_ops.instances.mobility.engine import guardrails as mobility_guardrails

        def walk_limit_m() -> float | None:
            """`mobility.limits.walk_m.default`. 선언에 없으면 None — 부르는 쪽이 보수적으로 간다."""
            try:
                return float(mobility_guardrails.lookup("mobility.limits.walk_m.default"))
            except mobility_guardrails.GuardrailMissing:
                return None

        # 요청 판이 같은 함수 객체를 끝까지 사용한다. 엔진 설정은 프로세스 수명에 고정한다.
        legs.register(leg_planner=mobility_wiring.leg_planner,
                      disruptions_from_events=mobility_wiring.disruptions_from_events,
                      walk_limit_m=walk_limit_m,
                      basis=mobility_wiring.basis,
                      departure_observer=mobility_wiring.observe_departure)
        mobility_shapes.register(items=mobility_route_shape.shapes_for_items,
                                 review=mobility_route_shape.shapes_for_review)

    if "dining" in active_ids:
        # 요식 — 원장이 식당의 정본이다(근처 들여놓기 · 시간대 판정 · 이름으로 찾기).
        from app.domains.travel_ops.instances.dining import ledger as dining_ledger_impl
        from app.domains.travel_ops.instances.dining import nearby as dining_nearby
        from app.domains.travel_ops.instances.dining.place_lookup import LedgerPlaceLookup

        dining_ledger.register(add_nearby=dining_nearby.add_nearby,
                               states=dining_ledger_impl.dining_states,
                               state=dining_ledger_impl.dining_state,
                               find_by_name=dining_ledger_impl.find_place_by_name,
                               catalog_state=dining_ledger_impl.catalog_state,
                               lookup_factory=LedgerPlaceLookup,
                               slot_verdicts=dining_ledger_impl.slot_verdicts,
                               planner_factory=dining_ledger_impl.PlannerLedger,
                               link_core_place=dining_ledger_impl.link_core_place_to,
                               closure_observation=dining_ledger_impl.closure_observation,
                               agent_judge=_dining_agent_judge(),
                               meal_picker=_dining_meal_picker())

        # 요식 — 확인 화면 「다른 식당」 후보(`[2026-10-15]` 후보 공급은 팀이, 조립은 우리가). 미등록이면 확인 화면 자체 고르기로 간다
        from app.domains.travel_ops.instances.dining import review_alternatives as dining_review_alternatives

        dining_alternatives.register(rank=dining_review_alternatives.rank)

    if "activity" in active_ids:
        # 활동 — 비슷한 곳 순서와 설문 선호.
        from app.domains.travel_ops.instances.activity import similarity as activity_similarity

        similarity.register(score=activity_similarity.score,
                            preference_of=activity_similarity.preference_of,
                            distance_first=activity_similarity.distance_first)

        # 활동 — 휴무 · 운영시간 · 재난 영향 판정의 정본(활동 원장). 확인 화면 · 감시가 고객 문의와 같은 판정을 쓴다
        from app.domains.travel_ops.instances.activity import ledger as activity_ledger_impl
        from app.domains.travel_ops.instances.activity import verdicts as activity_verdicts

        activity_ledger.register(state=activity_ledger_impl.state,
                                 state_by_content=activity_ledger_impl.state_by_content,
                                 indoor=activity_ledger_impl.indoor,
                                 disaster=activity_verdicts.disaster_verdict)

        # 활동 — 확인 화면 「다른 곳」 후보를 고르는 대체안 엔진(`[2026-10-15]` 후보 공급은 팀이, 조립은 우리가). 미등록이면 확인 화면 자체 고르기로 간다
        from app.domains.travel_ops.instances.activity import review_alternatives as activity_review_alternatives

        activity_alternatives.register(rank=activity_review_alternatives.rank)

    if "activity" in active_ids:
        from app.domains.travel_ops.instances.activity.team import plan_activity_trigger
        watch_planners.register("activity", plan_activity_trigger)
    if "dining" in active_ids:
        from app.domains.travel_ops.instances.dining.team import plan_dining_trigger
        watch_planners.register("dining", plan_dining_trigger)
    if "mobility" in active_ids:
        from app.domains.travel_ops.instances.mobility.team import plan_mobility_trigger
        watch_planners.register("mobility", plan_mobility_trigger)
    if "lodging" in active_ids:
        # 숙소 · 항공(확장) — 보여 준 후보 기억 · 고른 MCP 숙소를 그 여행 전용 장소로 들여놓기. `[2026-10-12]` 요식 원장과 같은 모양.
        #   `[2026-10-13]` 부르는 곳: 「다른 후보」 제안(`itinerary_actions._ask_options`) · 고르기(`pending.choose`) · `read.offers_shown`
        from app.domains.travel_ops.instances.lodging import ledger as lodging_ledger_impl

        lodging_ledger.register(remember=lodging_ledger_impl.remember_shown,
                                shown=lodging_ledger_impl.shown_keys,
                                adopt=lodging_ledger_impl.adopt_option,
                                item_key=lodging_ledger_impl.item_key,
                                offers=lodging_ledger_impl.shown_offers)
    # 팀 정기 작업 — 활성 팀이 `instances/<팀>/jobs.py` 에 `JOBS` 를 두면 등록한다. 작업 실행기가 시간대 안에서 부른다.
    #   `[2026-10-13]` 활동 → 코어 전달 사항 2번: 전에는 실행기에 작업이 고정돼 있어 팀 배치마다 코어를 고쳐야 했다.
    from app.domains.travel_ops.components.team_hooks import scheduled_jobs

    for team_id in sorted(active_ids):
        module_name = f"app.domains.travel_ops.instances.{team_id}.jobs"
        try:
            jobs_module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name and module_name.startswith(exc.name):      # 그 팀은 정기 작업이 없다(파일이 없다)
                continue
            raise                                                   # jobs.py 안의 import 가 깨졌다 — 숨기지 않는다
        for job in getattr(jobs_module, "JOBS", ()):
            scheduled_jobs.register(team_id, job)
    if "activity" in active_ids:
        # ★`[2026-10-14]` 활동 웹 운영 확인 정기 작업에 연결 · 판정 LLM · 웹 예산을 꽂는다 — 팀 폴더는 인프라를 직접 열지 않는다(DoD-22).
        #   판정 LLM 이 없으면(`rule` · 키 없음) 작업이 `disabled` 로 답한다. 만드는 것 자체는 I/O 가 없다.
        from app.domains.travel_ops.instances.activity import jobs as activity_jobs

        from app.application.job_gate import claim

        activity_jobs.configure(connection_factory=get_connection, judge_llm=build_activity_judge_llm(),
                                budget=build_activity_judge_budget(), claim=claim)

    names = {"mobility": ("legs",), "dining": ("dining_ledger", "dining_alternatives"), "activity": ("similarity", "activity_ledger", "activity_alternatives")}
    # 숙소는 감시 없이 원장만 — 감시(`watch:`)는 `names` 의 팀만 센다
    hook_names = {**names, "lodging": ("lodging_ledger",)}
    connected = [name for owner, hooks in hook_names.items() if owner in active_ids for name in hooks]
    connected += [f"watch:{kind}" for kind in sorted(active_ids & names.keys())]
    for declaration in (config.teams if config else []):
        if declaration.active and declaration.team_id in active_ids and declaration.hooks is not None:
            actual = {name for name in connected if name in hook_names.get(declaration.team_id, ())
                      or name == f"watch:{declaration.team_id}"}
            if set(declaration.hooks) != actual:
                raise CompositionError(f"declared hooks do not match provider: {declaration.team_id}")
    return connected


def build_place_status(google=None):
    from app.domains.travel_ops.components.watch.place_status import PlaceStatus
    return PlaceStatus(get_connection, google=google)


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

    def policy_search_factory():
        # ★`[2026-10-15]` 채팅 규정 질문의 검색 — 가드레일 `travel.question.rerank.mode` 가 `off`(기본)면 `search_policy` 와 똑같이 움직이고,
        #   `on`/`shadow` 일 때만 후보를 모델이 다시 고른다(`components/conversation/policy_rerank.py`). 규정 질문이 아닌 곳은 `__call__` 로 지금과 같다
        from app.domains.travel_ops.components.conversation.policy_rerank import build_policy_search

        return build_policy_search()

    return [build_trip_router(check_factory=check_factory, classifier_factory=build_classifier,
                              chat_factory=chat_factory, place_factory=place_factory,
                              kakao_factory=kakao_factory,
                              # ★채팅의 질문 — 여행 규정 검색(RAG). 문턱은 `travel.question.min_policy_score`
                              policy_search_factory=policy_search_factory,
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
