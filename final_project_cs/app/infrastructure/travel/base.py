# -*- coding: utf-8 -*-
"""외부 데이터 어댑터의 공통 규칙.

여기 있는 것은 **판단이 아니라 규율**이다. 어떤 공급자를 붙이든 아래 넷은 같다.

  ① 못 가져오면 `None` — 지어내지 않고 폴백하지 않는다
  ② 성공하면 `confirmed_at`·`source` 를 **반드시** 함께 준다
  ③ HTTP 상태만 보고 성공을 판정하지 않는다
  ④ 왜 못 가져왔는지를 **센다** — 조용한 스킵을 만들지 않는다

★③ 은 지어낸 걱정이 아니다. 2026-09-09 실측:

    ODsay   `searchPubTransPathT` 키 없이 호출 → **HTTP 200**
            body: {"error":[{"code":"500","message":"[ApiKeyAuthFailed] ..."}]}

  `r.raise_for_status()` 만 쓰면 **인증 실패가 성공으로 지나간다.** 그러면
  `read.transit` 이 빈 dict 를 돌려주고, Team 은 그걸 「확인했다」로 읽는다.
  같은 호출에서 data.go.kr 계열은 401 로 정직하게 답했다 — 공급자마다 다르다.
  그래서 **본문까지 봐야 한다**는 것을 공통 규칙으로 못 박는다.

★②·④ 는 v10 §4-D 다. 「확인 시각·출처를 같이 저장한다 / 모르면 '미확인'」.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

#: 바깥 호출 상한(초). ★Team 전체 타임아웃(`reliability.team_timeout_seconds`)
#:  보다 **작아야** 한다 — 안 그러면 Team 이 먼저 죽어 어느 소스가 늦었는지 모른다.
DEFAULT_TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True)
class SourceMiss:
    """가져오지 못한 한 건. ★예외가 아니라 **기록**이다.

    예외로 던지면 Team 마다 잡는 방식이 갈리고, 안 잡으면 Case 하나가 통째로
    죽는다. 「모름」은 정상적인 결과 갈래이지 사고가 아니다.
    """

    source: str
    reason: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.source}: {self.reason}" + (f" ({self.detail})" if self.detail else "")


class TravelSource:
    """HTTP 로 바깥을 읽는 어댑터의 바닥.

    ★상태를 들고 있는 이유는 **미스를 세기 위해서**다. 세지 않으면 분모가
      줄어 성공률이 실제보다 좋아 보인다(`CLAUDE.md` §3 「조용한 스킵 금지」).
    """

    #: 하위 클래스가 자기 이름을 준다. 근거(`Evidence.source_id`)에 그대로 실린다.
    name: str = "unknown"

    def __init__(self, *, timeout: float = DEFAULT_TIMEOUT_SECONDS,
                 transport: Callable[..., httpx.Response] | None = None,
                 limiter: Any | None = None) -> None:
        self._timeout = timeout
        # ★테스트가 네트워크 없이 돌 수 있게 주입 지점을 연다. 기본값은 실제 호출이다.
        self._get = transport or self._http_get
        # ★속도 제한기. 없으면 제한 없이 나간다 - 단위 시험이 그 상태다.
        #   조립(`build_travel_sources`)은 반드시 넣는다.
        self._limiter = limiter
        self.misses: Counter[str] = Counter()

    # ── 하위 클래스가 쓰는 부품 ──────────────────────────────────
    def _http_get(self, url: str, params: dict[str, Any]) -> httpx.Response:
        return httpx.get(url, params=params, timeout=self._timeout)

    def _allow(self) -> bool:
        """속도 제한을 통과하면 True. 거부되면 세고 False.

        ★거부를 예외로 위에 던지지 않는다 - 「모름」은 정상 갈래이고,
          Case 하나가 통째로 죽을 일이 아니다.
        """
        if self._limiter is None:
            return True
        from .ratelimit import RateLimited

        try:
            self._limiter.acquire(self.name)
            return True
        except RateLimited as exc:
            self._miss("rate_limited", f"{exc.wait_seconds:.1f}s remaining")
            return False

    def _miss(self, reason: str, detail: str = "") -> None:
        """★`None` 을 돌려주기 **전에** 반드시 부른다. 이유 없는 모름은 못 고친다."""
        self.misses[reason] += 1
        logger.warning("travel source miss: %s", SourceMiss(self.name, reason, detail))

    def _fetch_json(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """읽고, **본문까지 검사하고**, 실패면 `None`.

        ★타임아웃을 성공으로 추정하지 않는다(`CLAUDE.md` §0.2). 재시도도 하지
          않는다 — 여기서 자동 재시도를 걸면 공급자 장애 때 우리가 부하를 보탠다.
        """
        if not self._allow():
            return None
        try:
            response = self._get(url, params)
        except httpx.TimeoutException as exc:
            self._miss("timeout", str(exc))
            return None
        except httpx.HTTPError as exc:
            self._miss("transport_error", f"{type(exc).__name__}: {exc}")
            return None

        if response.status_code != 200:
            self._miss(f"http_{response.status_code}", response.text[:200])
            return None

        try:
            payload = response.json()
        except ValueError:
            # ★JSON 이 아니면 대개 HTML 오류 페이지다. data.go.kr 이 그렇게 답한다.
            self._miss("not_json", response.text[:200])
            return None

        if not isinstance(payload, dict):
            self._miss("unexpected_shape", type(payload).__name__)
            return None

        problem = self._body_error(payload)
        if problem is not None:
            # ★HTTP 200 인데 본문이 오류인 경우. ODsay 가 실제로 이렇게 답한다.
            self._miss("body_error", problem)
            return None
        return payload

    def _fetch_xml(self, url: str, params: dict[str, Any]) -> str | None:
        """XML 을 문자열로 읽는다. 실패면 `None`.

        ★국가유산청은 JSON 을 주지 않는다 — `application/xml` 뿐이다.
          그래서 `_fetch_json` 을 못 쓴다. 규율(①~④)은 그대로 지킨다.
        """
        if not self._allow():
            return None
        try:
            response = self._get(url, params)
        except httpx.TimeoutException as exc:
            self._miss("timeout", str(exc))
            return None
        except httpx.HTTPError as exc:
            self._miss("transport_error", f"{type(exc).__name__}: {exc}")
            return None

        if response.status_code != 200:
            self._miss(f"http_{response.status_code}", response.text[:200])
            return None
        text = response.text
        if "<" not in text:
            # ★XML 이 아니면 대개 오류 페이지다. 빈 응답도 여기서 걸린다.
            self._miss("not_xml", text[:200])
            return None
        return text

    @staticmethod
    def _body_error(payload: dict[str, Any]) -> str | None:
        """본문이 오류를 말하고 있으면 그 문구를, 아니면 `None`.

        ★하위 클래스가 공급자별 모양으로 덮어쓴다. 여기 있는 것은 실측으로
          확인한 두 모양이다(2026-09-09).
        """
        error = payload.get("error")
        if isinstance(error, list) and error:
            first = error[0]
            if isinstance(first, dict):
                return str(first.get("message") or first)
            return str(first)
        if isinstance(error, dict):
            return str(error.get("message") or error)
        # ★★평평한 오류 봉투. `response` 감싸개 **없이** 최상위에 코드가 온다
        #   (2026-09-10 실측: detailCommon2 에 안 받는 인자를 주면
        #    {"responseTime":..., "resultCode":"10",
        #     "resultMsg":"INVALID_REQUEST_PARAMETER_ERROR(contentTypeId)"}).
        #   이걸 안 잡으면 진짜 이유가 「모양이 이상하다」로 가려져,
        #   인자 하나 틀린 것을 찾는 데 한참 걸린다.
        code = str(payload.get("resultCode", ""))
        if code and code not in ("00", "0000") and "response" not in payload:
            return f'{code} {payload.get("resultMsg", "")}'.strip()
        header = payload.get("OpenAPI_ServiceResponse")
        if isinstance(header, dict):
            message = header.get("cmmMsgHeader", {})
            if isinstance(message, dict) and message.get("errMsg"):
                return str(message["errMsg"])
        return None

    @staticmethod
    def stamp(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
        """조회 결과에 **확인 시각과 출처**를 박는다.

        ★`confirmed_at` 은 「우리가 확인한 시각」이지 「현장이 그러한 시각」이
          아니다. Team 이 이 둘을 섞어 말하면 예정 정보를 관찰처럼 전한다
          (v10 §4-D). Team 쪽 문구도 그렇게 적어 뒀다.
        """
        return {**payload, "confirmed_at": datetime.now(UTC).isoformat(),
                "source": source}


@dataclass
class TravelSources:
    """Team 이 쓰는 소스 묶음. ★없는 소스는 `None` 이고, 그건 「모름」이다.

    조립 지점(`app/composition.py`)이 만들어 `ReadToolbox` 에 넣는다.
    테스트는 넣지 않는다 — 그러면 도구가 전부 `None` 을 돌려주고 네트워크를
    타지 않는다.
    """

    weather: Any | None = None
    place: Any | None = None
    #: 한국천문연구원 특일 정보 — 공휴일. 공공데이터포털 공통 키를 쓴다.
    holiday: Any | None = None
    #: 국가유산청 — ★키가 필요 없어서 **항상 붙는다**(2026-09-10 실호출 확인).
    #:  좌표를 모르는 장소의 좌표를 채우는 데만 쓴다. 운영시간은 주지 않는다.
    heritage: Any | None = None
    #: 기상청 기상특보 — 지금 그 지역에 발효 중인 특보. 공공데이터포털 공통 키.
    warning: Any | None = None
    #: 외교부 여행경보 — 해외 확장용(v11 MVP 는 서울뿐이라 지금 부르는 Team 없음).
    advisory: Any | None = None
    #: 행정안전부 긴급재난문자. ★지금은 **샘플 CSV 판**(실키 발급 대기, 2026-09-14).
    disaster: Any | None = None
    #: 국토교통부 ITS 돌발상황 — 교통 사고·공사·통제(시내 도로 포함, 실측).
    traffic: Any | None = None
    #: 에어코리아 대기오염정보 — 구 측정소의 1시간 값(실측 2026-09-14).
    air: Any | None = None
    #: 경로에 걸린 운행·통제 사건(무정차·도로 통제). 지금은 재생 입력만 있다 —
    #:  실시간 지하철 운행·UTIC 통제가 붙으면 같은 `affecting()` 모양으로 끼운다.
    route_events: Any | None = None
    transit: Any | None = None
    route: Any | None = None
    #: 키가 없어 못 붙인 소스 이름들. ★조용히 비워 두지 않는다.
    unavailable: dict[str, str] = field(default_factory=dict)
    #: 소스 전부가 같은 것을 공유한다 - 따로 두면 한 키를 두 소스가 나눠
    #: 쓸 때 합계가 한도를 넘는다.
    limiter: Any | None = None


def _public_data_key(settings: Any, field: str) -> str:
    """공공데이터포털 키 하나를 고른다 — 서비스별 키 > 공통 키.

    ★`Settings.public_data_key()` 가 있으면 그것을 쓰고, 없으면(테스트가 넣는
      가짜 설정 객체) 같은 규칙을 여기서 적용한다. 규칙을 두 벌 쓰지 않으려고
      한 곳에 모았다.
    """
    override = getattr(settings, field, "") or ""
    resolver = getattr(settings, "public_data_key", None)
    if callable(resolver):
        return resolver(override)
    return override or getattr(settings, "data_go_kr_key", "") or ""


def build_travel_sources(settings: Any) -> TravelSources:
    """설정을 보고 붙일 수 있는 것만 붙인다.

    ★키가 없으면 **그 소스만** 빠진다. 앱이 죽지도 않고, 가짜로 채우지도
      않는다. 무엇이 왜 빠졌는지는 `unavailable` 이 들고 있고
      `/ui/admin` 이 그대로 보여 준다.
    """
    from .heritage import HeritageSource
    from .open_meteo import OpenMeteoWeather

    from .ratelimit import RateLimiter, interval_for

    limits = (settings.source_rate_limits()
              if hasattr(settings, "source_rate_limits") else {})
    limiter = RateLimiter(
        intervals={name: interval_for(per_day) for name, per_day in limits.items()},
        max_wait_seconds=float(getattr(settings, "rate_max_wait_seconds", 5.0)))

    sources = TravelSources(limiter=limiter)
    # ★키를 안 보고 붙인다 — 이 소스는 인증 파라미터 자체가 없다.
    sources.heritage = HeritageSource(limiter=limiter)
    # ── 기상: 1차 + 대체 (v11 §0-4 결정 15) ─────────────────────────
    # ★`weather_provider` 는 **어느 쪽이 먼저인가**만 정한다. 붙일 수 있는 것은
    #   전부 붙이고 나머지를 대체로 둔다 — 1차가 못 주면 대체가 값을 낸다.
    #   ☆2026-09-14 전에는 둘 중 하나만 붙였고, `kma` 를 고르면 `kma.py` 가 없어
    #     `ModuleNotFoundError` 로 **기동이 안 됐다.**
    provider = getattr(settings, "weather_provider", "open_meteo")
    weather_by_name: dict[str, Any] = {
        # ★키가 필요 없다(2026-09-09 실호출 200 확인). 그래서 조건 없이 붙는다.
        "open_meteo": OpenMeteoWeather(limiter=limiter),
    }
    # ★서비스별 키가 비면 공공데이터포털 공통 키로 떨어진다 — 계정 하나면
    #   키도 하나이기 때문이다. 둘 다 비면 빈 문자열이고 그건 「없음」이다.
    kma_key = _public_data_key(settings, "kma_api_key")
    if kma_key:
        from .kma import KmaWeather
        weather_by_name["kma"] = KmaWeather(service_key=kma_key, limiter=limiter)
    else:
        sources.unavailable["weather_kma"] = (
            "ACOP_DATA_GO_KR_KEY(또는 ACOP_KMA_API_KEY)가 비어 있다. "
            "공공데이터포털 「기상청_단기예보 조회서비스」 활용신청 후 "
            ".env.apikeys 에 채운다(승인 최소 1일). 대체 소스 없이 Open-Meteo 만 쓴다.")

    if provider not in ("open_meteo", "kma"):
        sources.unavailable["weather"] = f"모르는 weather_provider: {provider}"
    else:
        order = [provider] + [name for name in weather_by_name if name != provider]
        chain = [weather_by_name[name] for name in order if name in weather_by_name]
        if len(chain) == 1:
            sources.weather = chain[0]
        else:
            from .weather_chain import FallbackWeather
            sources.weather = FallbackWeather(chain)

    warning_key = _public_data_key(settings, "kma_warning_api_key")
    if warning_key:
        from .kma_warning import KmaWarningSource
        sources.warning = KmaWarningSource(service_key=warning_key, limiter=limiter)
    else:
        sources.unavailable["warning"] = (
            "ACOP_DATA_GO_KR_KEY(또는 ACOP_KMA_WARNING_API_KEY)가 비어 있다. "
            "공공데이터포털 「기상청_기상특보 조회서비스」 활용신청 후 .env.apikeys 에 채운다.")

    mofa_key = _public_data_key(settings, "mofa_api_key")
    if mofa_key:
        from .mofa import MofaTravelAlarm
        sources.advisory = MofaTravelAlarm(service_key=mofa_key, limiter=limiter)
    else:
        sources.unavailable["advisory"] = (
            "ACOP_DATA_GO_KR_KEY(또는 ACOP_MOFA_API_KEY)가 비어 있다. "
            "공공데이터포털 「외교부_국가·지역별 여행경보」 활용신청 후 .env.apikeys 에 채운다.")

    # ★재난문자 — 키가 아직 안 나와 **샘플 CSV** 를 쓴다(사용자 지시 2026-09-14).
    #   샘플 기간(2023-09-16~19) 밖을 물으면 점검이 「미연결」로 답한다 —
    #   「재난문자 없음」이라고 하지 않는다. 키가 나오면 `disaster_msg_source=api`.
    disaster_mode = getattr(settings, "disaster_msg_source", "sample")
    if disaster_mode == "sample":
        from pathlib import Path

        from .disaster_msg import DEFAULT_SAMPLE_PATH, DisasterMsgCsv
        sample = Path(getattr(settings, "disaster_msg_sample_path", "") or DEFAULT_SAMPLE_PATH)
        if sample.exists():
            sources.disaster = DisasterMsgCsv(sample)
        else:
            sources.unavailable["disaster"] = f"재난문자 샘플 CSV 가 없다: {sample}"
    else:
        sources.unavailable["disaster"] = (
            "행정안전부 긴급재난문자 API 판은 아직 없다 — 키 발급 대기 "
            "(data.go.kr/data/15134001)")

    # ★ITS 는 공공데이터포털 공통 키가 아니라 **ITS 가 발급한 키**를 쓴다.
    its_key = getattr(settings, "its_api_key", "") or ""
    if its_key:
        from .its_traffic import ItsTrafficEvents
        sources.traffic = ItsTrafficEvents(service_key=its_key, limiter=limiter)
    else:
        sources.unavailable["traffic"] = (
            "ACOP_ITS_API_KEY 가 비어 있다. ITS 국가교통정보센터(its.go.kr/opendata) 에서 "
            "발급한 키를 .env.apikeys 에 채운다. ★공공데이터포털 키와 다른 키다.")

    air_key = _public_data_key(settings, "airkorea_api_key")
    if air_key:
        from .air_quality import AirKoreaRealtime
        sources.air = AirKoreaRealtime(service_key=air_key, limiter=limiter)
    else:
        sources.unavailable["air"] = (
            "ACOP_DATA_GO_KR_KEY(또는 ACOP_AIRKOREA_API_KEY)가 비어 있다. "
            "공공데이터포털 「에어코리아 대기오염정보」 활용신청 후 채운다.")

    holiday_key = _public_data_key(settings, "holiday_api_key")
    if holiday_key:
        from .holiday import HolidaySource
        sources.holiday = HolidaySource(service_key=holiday_key, limiter=limiter)
    else:
        sources.unavailable["holiday"] = (
            "ACOP_DATA_GO_KR_KEY(또는 ACOP_HOLIDAY_API_KEY)가 비어 있다. "
            "공공데이터포털 「한국천문연구원_특일 정보」 활용신청 후 "
            ".env.apikeys 에 채운다.")

    if not _public_data_key(settings, "tour_api_key"):
        sources.unavailable["place"] = (
            "ACOP_DATA_GO_KR_KEY(또는 ACOP_TOUR_API_KEY)가 비어 있다. "
            "공공데이터포털 「한국관광공사_국문 관광정보 서비스」 활용신청 후 "
            ".env.apikeys 에 채운다.")
    else:
        from .tour_api import TourApiPlace
        sources.place = TourApiPlace(
            service_key=_public_data_key(settings, "tour_api_key"), limiter=limiter)

    if not getattr(settings, "odsay_api_key", ""):
        sources.unavailable["transit"] = (
            "ACOP_ODSAY_API_KEY 가 비어 있다. lab.odsay.com 에서 발급해 "
            ".env.apikeys 에 채운다. ★공공데이터포털 키와 **다른 키**다.")
    else:
        from .odsay import OdsayTransit
        source = OdsayTransit(service_key=settings.odsay_api_key, limiter=limiter)
        sources.transit = source
        sources.route = source
    return sources
