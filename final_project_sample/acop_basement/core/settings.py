"""A-COP 설정 — .env + config/guardrails.yaml 의 유일한 진입점.

규칙 (RULE.md §3.1, §3.2):
  - 하드코딩 금지. API 키·모델명·경로·가드레일 수치를 코드에 직접 쓰지 않는다.
  - 폴백 금지. 값이 없으면 명시적 예외로 실패한다. 기본값으로 조용히 대체하지 않는다.

가드레일 수치는 config/guardrails.yaml 이 유일한 정의처다.
같은 숫자를 코드 두 곳에 쓰면 그 자체가 결함이다(docs/handoff/06_가드레일_수치.md).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """설정이 없거나 잘못됐다. 폴백하지 않고 여기서 멈춘다."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ACOP_",
        env_file=REPO_ROOT / ".env",
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

    # 앱
    env: str = "dev"
    tenant_id: str
    secret_key: str
    composer_jwt_secret: str
    composer_issuer_secret: str

    # 경로
    guardrails_path: str = "config/guardrails.yaml"

    # 구성 선언을 어디서 읽는가
    #   file    — 로컬 `config/project.yaml`(기본). 개발·단일 배포용
    #   central — 중앙 설정 저장소. 대상이 수천 개일 때의 운영 형태
    #             (`program/plan/A-COP_Composer_중앙설정저장소_결정.md`)
    #: ★기본이 file 인 이유는 하위호환이다. 중앙 저장소를 켜는 것은 **명시적
    #:  선택**이어야 한다 — 설정을 어디서 읽는지가 조용히 바뀌면 안 된다.
    config_source: Literal["file", "central"] = "file"
    #: 중앙 저장소에서 자기 선언을 찾는 키. `config_source="central"` 일 때 필수다.
    #: ★업무 개념인 `tenant_id` 와 일부러 분리한다 — 한 테넌트가 여러 배포를
    #:  가질 수 있고, 그 둘은 서로 다른 선언을 가질 수 있다.
    deployment_id: str = ""


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
