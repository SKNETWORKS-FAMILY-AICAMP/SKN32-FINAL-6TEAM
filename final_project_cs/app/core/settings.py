"""A-COP 설정 — .env + config/guardrails.yaml 의 유일한 진입점.

규칙 (RULE.md §3.1, §3.2):
  - 하드코딩 금지. API 키·모델명·경로·가드레일 수치를 코드에 직접 쓰지 않는다.
  - 폴백 금지. 값이 없으면 명시적 예외로 실패한다. 기본값으로 조용히 대체하지 않는다.

가드레일 수치는 config/guardrails.yaml 이 유일한 정의처다.
같은 숫자를 코드 두 곳에 쓰면 그 자체가 결함이다(wiki/records/handoff/06_가드레일_수치.md).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """설정이 없거나 잘못됐다. 폴백하지 않고 여기서 멈춘다."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACOP_",
        # ★두 파일을 읽는다. **뒤에 오는 쪽이 이긴다**(2026-09-10 실측).
        #   `.env`          — DB·LLM·앱 설정. 예전부터 있던 파일
        #   `.env.apikeys`  — 바깥 데이터 소스 키만. 둘 다 커밋하지 않는다
        #   키를 따로 둔 이유: 팀원마다 발급 상태가 다르고, 승인 대기 중인
        #   키가 섞이면 `.env` 전체를 주고받게 된다. 키만 갈아끼울 수 있어야 한다.
        # ★★`extra="forbid"` 라 **선언하지 않은 이름을 파일에 적으면 앱이
        #   기동조차 못 한다**(ValidationError). 키를 새로 넣을 때는 아래에
        #   필드부터 만든다. 이 함정은 `.env.apikeys.example` 첫 줄에도 적어 뒀다.
        env_file=(REPO_ROOT / ".env", REPO_ROOT / ".env.apikeys"),
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # DB
    database_url: str

    # LLM
    llm_provider: str = "openai"
    openai_api_key: str
    llm_model: str
    embedding_model: str
    llm_temperature: float = 0.0
    llm_seed: int = 7
    local_ft_base_url: str = ""

    # ── 여행 외부 소스 ─────────────────────────────────────────
    # ★기본값이 빈 문자열이다 = **그 소스를 안 붙인다.** 가짜로 채우지 않는다.
    #   무엇이 왜 빠졌는지는 `build_travel_sources()` 의 `unavailable` 이 들고
    #   있고 `/ui/admin` 이 그대로 보여 준다.
    # ★값은 `.env.apikeys` 에 넣는다(커밋 안 함). 형식은 `.env.apikeys.example`.
    weather_provider: str = "open_meteo"     # open_meteo | kma

    # 공공데이터포털 — ★계정마다 인증키가 **하나**고, 활용신청을 승인받은
    #   서비스 전부에 같은 키를 쓴다. 그래서 이것만 채우면 아래가 전부 산다.
    #   아래 서비스별 필드는 **다른 계정을 쓸 때만** 채우는 덮어쓰기 자리다.
    data_go_kr_key: str = ""                 # https://www.data.go.kr 공통 인증키

    #: 한국관광공사 국문 관광정보 — 장소·운영시간   data.go.kr/data/15101578
    tour_api_key: str = ""
    #: 기상청 단기예보 — Open-Meteo 대안            data.go.kr/data/15084084
    kma_api_key: str = ""
    #: 기상청 기상특보 — ★지속관리 루프의 트리거    data.go.kr/data/15000415
    kma_warning_api_key: str = ""
    #: 한국천문연구원 특일 정보 — ★공휴일 휴무 판정 data.go.kr/data/15012690
    holiday_api_key: str = ""
    #: 국토교통부 TAGO — 버스·지하철·열차 운행      data.go.kr/data/15098530
    tago_api_key: str = ""
    #: 한국환경공단 에어코리아 — 야외활동 대기질    data.go.kr/data/15073861
    airkorea_api_key: str = ""
    #: 국립해양조사원 — 수상레저 활동 성립 판정
    #:  ★쓸 서비스는 **서핑지수(15142490)** 와 **TideBED 예측조위(15156026)** 둘이다.
    #:    서핑지수는 기관이 성립 여부를 판정해 주므로 우리가 기준을 만들지 않아도
    #:    되고, TideBED 는 **위도·경도로 조회된다** — 우리 `places` 에는 좌표만
    #:    있고 관측소 코드가 없다(다른 조석 API 는 전부 관측소 코드를 받는다).
    #:  ★(구)바다누리 자체 OpenAPI 는 종료 예정이라 공통 키로 충분하다.
    khoa_api_key: str = ""
    #: 국가유산청 — ★**키가 필요 없다**(2026-09-10 실호출 확인). 그래서 이 칸은
    #:  비워 둔다. 어댑터(`app/infrastructure/travel/heritage.py`)가 인증
    #:  파라미터 없이 부른다. 공공데이터포털 쪽 문화재 공간정보
    #:  (data.go.kr/data/3070426)를 따로 쓸 때만 채운다.
    heritage_api_key: str = ""
    #: 한국공항공사 실시간 운항 — Flight 결항·지연  data.go.kr/data/15113771
    #: `[미확보]` 2026-09-09 엔드포인트 경로를 확인하지 못했다(400 NO_OPENAPI_SERVICE_ERROR)
    airport_api_key: str = ""
    #: 외교부 국가·지역별 여행경보 — 해외 확장 시   data.go.kr/data/15076237
    mofa_api_key: str = ""

    # 정부 교통정보 — ★공공데이터포털 공통 키와 **다른 키**다(각 기관이 따로 발급).
    #: 국토교통부 ITS 국가교통정보센터 — 돌발상황  its.go.kr/opendata
    #:  ★2026-09-14 발급·실호출 확인. 고속도로·국도만이 아니라 **시내 도로(시군도)도
    #:    온다**(서울 122건 중 시군도 10·국도 6·지방도 2). 공공데이터포털 15040465 는
    #:    LINK 형이라 키가 ITS 에서 나온다.
    its_api_key: str = ""
    #: 경찰청 UTIC 도시교통정보센터 — 도로위험상황예보·돌발(행사·집회 포함)  utic.go.kr
    #:  ★2026-09-14 신청, 승인 대기. **등록한 IP 에서만** 호출된다(<학원 PC IP>).
    utic_api_key: str = ""

    # 민간 — ★공공데이터포털 키와 **다른 키**다. 공통 키가 대신하지 않는다.
    odsay_api_key: str = ""                  # ODsay 대중교통 길찾기 lab.odsay.com
    kakao_rest_api_key: str = ""             # 카카오 지도 — 주소→좌표 developers.kakao.com
    #: 디스코드 웹훅 — 고객 알림 채널(v11 §6-A). ★비어 있으면 알림을 **보내지 않았다고**
    #:  기록한다(dead_letter). 보낸 것처럼 `delivered` 로 찍지 않는다.
    discord_webhook_url: str = ""

    # 호출 속도 제한 (2026-09-10 신설)
    # 하루 한도를 하루에 걸쳐 쓴다.  최소 간격(초) = 86400 / 하루 한도
    # 시험한다고 빨리 두들기면 그날치 한도를 태우고 차단당한다.
    # 0 을 넣으면 그 소스는 제한 없음이다(권하지 않는다).
    #
    # 값의 출처를 갈라 적는다 - 「확인」은 공급자 문서/상세페이지에서 본 수,
    # 「미확인」은 data.go.kr 개발계정 통상값으로 보수적으로 잡은 수다.
    rate_open_meteo_per_day: int = 10000     # 확인: 비상업 하루 10,000
    rate_kma_warning_per_day: int = 10000    # 확인: 기상특보 개발계정
    rate_khoa_per_day: int = 10000           # 확인: 서핑지수/TideBED 개발계정
    rate_airkorea_per_day: int = 500         # 확인: 에어코리아 개발계정(낮다)
    rate_tour_api_per_day: int = 1000        # 미확인 - 보수적
    rate_kasi_holiday_per_day: int = 1000    # 미확인 - 보수적
    rate_tago_per_day: int = 1000            # 미확인 - 보수적
    rate_kma_per_day: int = 1000             # 미확인 - 보수적
    rate_airport_per_day: int = 1000         # 미확인 - 보수적
    rate_mofa_per_day: int = 1000            # 미확인 - 보수적
    rate_its_per_day: int = 1000             # 미확인 - 보수적(ITS 공개 한도 못 찾음)
    rate_odsay_per_day: int = 1000           # 미확인 - 무료 구간 한도 못 찾음
    rate_kakao_per_day: int = 1000           # 미확인 - 보수적
    #: 국가유산청은 키가 없고 공개된 한도도 못 찾았다. 그래도 스스로 조인다 -
    #: 한도를 모른다는 것이 마음껏 두들겨도 된다는 뜻은 아니다.
    rate_heritage_khs_per_day: int = 1000

    #: 간격이 안 찼을 때 기다려 볼 최대 시간(초). 고객 요청이 여기서 멈춘다.
    #:  넘으면 기다리지 않고 거부하고, Team 은 「모름」으로 넘어간다.
    rate_max_wait_seconds: float = 5.0

    def source_rate_limits(self) -> dict[str, int]:
        """`TravelSource.name` -> 하루 한도. 어댑터 이름과 정확히 맞춘다.

        이름이 어긋나면 제한이 조용히 안 걸린다. 그래서 한 곳에 모아 둔다.
        """
        return {
            "open_meteo": self.rate_open_meteo_per_day,
            "heritage_khs": self.rate_heritage_khs_per_day,
            "kasi_holiday": self.rate_kasi_holiday_per_day,
            "tour_api": self.rate_tour_api_per_day,
            "kma_warning": self.rate_kma_warning_per_day,
            "kma": self.rate_kma_per_day,
            "airkorea": self.rate_airkorea_per_day,
            "khoa": self.rate_khoa_per_day,
            "tago": self.rate_tago_per_day,
            "airport": self.rate_airport_per_day,
            "mofa": self.rate_mofa_per_day,
            "its": self.rate_its_per_day,
            "odsay": self.rate_odsay_per_day,
            "kakao": self.rate_kakao_per_day,
        }

    def public_data_key(self, override: str = "") -> str:
        """공공데이터포털 서비스 하나가 쓸 키. 둘 다 비었으면 빈 문자열.

        ★빈 문자열을 그대로 돌려준다 — 「키 없음」은 부르는 쪽이 보고 판단한다.
          여기서 예외를 던지면 키 하나 없다고 앱 전체가 안 뜬다.

        ★★**URL 디코드해서 돌려준다**(2026-09-10 실측으로 확정).
          포털이 인증키를 **일반(Decoding)** 과 **Encoding** 두 벌로 준다.
          Encoding 쪽은 `=` 가 `%3D` 로 들어 있는데, 그대로 httpx `params=` 에
          넘기면 `%` 가 다시 인코딩돼 `%253D` 가 되고 인증이 깨진다.

              키 그대로 + params    → HTTP 403 SERVICE_KEY_IS_NOT_REGISTERED_ERROR
              unquote() + params    → HTTP 200  ★

          ☆**오류 문구가 사실을 잘못 전한다.** "등록되지 않은 키"라고 하지만
            원인은 인코딩이다. 그 말을 믿고 키를 재발급하러 가면 시간을 버린다.

          `unquote()` 는 Decoding 키에도 안전하다 — `%XX` 가 없으면 그대로 둔다.
        """
        from urllib.parse import unquote

        return unquote(override or self.data_go_kr_key)

    # 앱
    env: str = "dev"
    tenant_id: str
    secret_key: str
    composer_jwt_secret: str
    composer_issuer_secret: str

    # 경로
    guardrails_path: str = "config/guardrails.yaml"


class Guardrails:
    """config/guardrails.yaml 을 읽기 전용으로 감싼다.

    점 경로로 읽는다: guardrails.get("context.token_budget") -> 12000
    없는 키를 조용히 None 으로 돌려주지 않는다 (조용한 스킵 금지, CLAUDE.md §3).
    """

    def __init__(self, data: dict[str, Any], source: Path) -> None:
        self._data = data
        self._source = source

    @property
    def source(self) -> Path:
        return self._source

    def get(self, dotted_key: str) -> Any:
        node: Any = self._data
        walked: list[str] = []
        for part in dotted_key.split("."):
            walked.append(part)
            if not isinstance(node, dict) or part not in node:
                raise ConfigError(
                    f"guardrails 키 없음: '{dotted_key}' "
                    f"({'.'.join(walked)} 에서 끊김, 출처={self._source})"
                )
            node = node[part]
        return node

    def as_dict(self) -> dict[str, Any]:
        return self._data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        raise ConfigError(
            "필수 환경변수가 없거나 잘못됐다. .env.example 를 .env 로 복사해서 채운다.\n"
            f"{exc}"
        ) from exc


@lru_cache(maxsize=1)
def get_guardrails() -> Guardrails:
    path = (REPO_ROOT / get_settings().guardrails_path).resolve()
    if not path.is_file():
        raise ConfigError(f"guardrails 파일 없음: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"guardrails 파일이 매핑이 아니다: {path}")
    return Guardrails(data, path)
