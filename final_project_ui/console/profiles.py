"""콘솔이 대상에 연결할 때 사용하는 선택적 프로필."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Profile:
    name: str
    path: Path
    database_url: str | None = None
    introspection_url: str | None = None
    introspection_token: str | None = None
    contract_versions: tuple[str, ...] = field(default_factory=tuple)
    composer_url: str | None = None
    composer_issuer_secret: str | None = None
    #: 어느 방식으로 구성을 관리하나 (2026-08-30).
    #:
    #:   direct  — 대상 제품에 Composer 가 함께 설치돼 있고, 그 대상의
    #:             `/composer/*` 를 직접 부른다. 대상 하나를 붙일 때 쓴다.
    #:   central — 중앙 **설정 서비스** 한 곳을 부르고 `deployment_id` 로 어느
    #:             대상의 구성인지 지정한다. 대상이 많을 때 쓴다.
    #:
    #: ★두 방식의 요청·응답 모양은 같다 — 주소와 헤더 하나만 다르다. 그래서
    #:  화면·클라이언트 코드는 그대로 두고 프로필로 고를 수 있다.
    composer_mode: str = "direct"
    #: `composer_mode="central"` 일 때 필수. 어느 대상의 구성을 다루는가.
    composer_deployment_id: str | None = None
    #: 대상의 `POST /admin/reload`(scope `ops:reload`) 토큰. 2026-08-31.
    #:
    #: ★`introspection_token`(조회)과 **다른 토큰**이다. 대상이 scope 를 나눠
    #:  뒀기 때문이다 — 조회 권한만으로 살아 있는 트래픽의 조립을 갈아 끼울 수
    #:  있으면 안 된다. 없으면 [반영] 버튼을 내지 않고, **왜 없는지 화면에 적는다.**
    reload_token: str | None = None


def profile_for(project: str | Path) -> Profile:
    """환경에서 선택적 연결 정보를 읽는다. 비밀값은 환경에만 둔다."""
    path = Path(project)
    # ★기본값은 `1.0` 이다. 대상이 실제로 내는 `contract_version` 이 `1.0` 이기 때문이다
    #   (2026-08-17 P8 실연결 검증에서 `CONSOLE_CONTRACT_VERSIONS=1.0` 으로 맞춰야
    #   `조립 실측: 읽음` 이 됐다). 한때 기본값이 `v1` 이었는데 이 문자열을 내는 대상은
    #   하나도 없었다 — 환경변수를 손으로 맞추지 않으면 조립 실측과 빠른 토글 카드가
    #   조용히 안 떴다(2026-08-28 결함 점검에서 실측).
    #   여러 버전을 알아야 하면 콤마로 나열한다(`CONSOLE_CONTRACT_VERSIONS=1.0,1.1`).
    #   ★기본값에 `1.1` 을 더했다(2026-08-31) — 대상이 실행 중인 조립과 저장된
    #   선언을 구분해 내기 시작하면서 버전이 올랐다(`active_revision`·
    #   `desired_revision`·`reload_state`). 옛 대상(1.0)도 그대로 붙어야 하므로
    #   둘 다 안다. 모르는 버전을 만나면 여전히 "계약 버전 모름" 이다.
    versions = tuple(v.strip() for v in os.environ.get("CONSOLE_CONTRACT_VERSIONS", "1.0,1.1").split(",") if v.strip())
    return Profile(
        name=path.name or str(path),
        path=path,
        database_url=os.environ.get("CONSOLE_DATABASE_URL") or None,
        introspection_url=os.environ.get("CONSOLE_INTROSPECTION_URL") or None,
        # ★대상 `/introspection` 은 scope 인증이 걸려 있다(예: `ops:introspect`).
        #   토큰 없이 실서버에 붙여 실측했더니 401 이 났다 — 헤더가 아예 안 나가고 있었다.
        introspection_token=os.environ.get("CONSOLE_INTROSPECTION_TOKEN") or None,
        contract_versions=versions,
        # ★대상의 Composer 쓰기 채널(`/composer/*`). CLAUDE.md §0.3 예외 —
        #   대상이 인증해 검증·저장하는 유일한 경로를 호출할 뿐, 파일을 직접 안 쓴다.
        composer_url=os.environ.get("CONSOLE_COMPOSER_URL") or None,
        composer_issuer_secret=os.environ.get("CONSOLE_COMPOSER_ISSUER_SECRET") or None,
        # ★기본은 `direct` 다 — 지금까지의 동작이고, 대상 하나에 붙는 가장
        #   단순한 형태다. 중앙 방식은 명시적으로 켠다.
        #   `deployment_id` 를 줬는데 mode 를 안 바꾼 경우도 central 로 본다 —
        #   그 값은 중앙 방식에서만 쓰이므로, 줬다는 것 자체가 의도 표현이다.
        composer_mode=_composer_mode(),
        composer_deployment_id=os.environ.get("CONSOLE_COMPOSER_DEPLOYMENT_ID") or None,
        reload_token=os.environ.get("CONSOLE_RELOAD_TOKEN") or None,
    )


def _composer_mode() -> str:
    """`CONSOLE_COMPOSER_MODE` 를 읽되 알 수 없는 값은 조용히 넘기지 않는다."""
    raw = (os.environ.get("CONSOLE_COMPOSER_MODE") or "").strip().lower()
    if raw in ("direct", "central"):
        return raw
    if raw:
        # ★오타를 기본값으로 삼키면 "중앙으로 켠 줄 알았는데 대상을 직접
        #   건드리고 있었다" 가 된다. 그건 남의 설정을 바꾸는 사고다.
        raise ValueError(
            f"CONSOLE_COMPOSER_MODE 는 direct 또는 central 이어야 한다: {raw!r}")
    return "central" if os.environ.get("CONSOLE_COMPOSER_DEPLOYMENT_ID") else "direct"
