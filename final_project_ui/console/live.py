"""대상의 introspection HTTP 응답을 읽는 어댑터.

★`trigger_reload()` 하나만 read-only 가 아니다. 이건 §0.3 의 예외와 같은
  성격이다 — 대상이 인증해서(scope `ops:reload`) 자기 프로세스 안에서 수행하는
  일을 **부를 뿐**, 여기서 대상의 파일·DB·파이썬을 건드리지 않는다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LiveRead:
    status: str
    value: dict | None = None
    detail: str = ""


def read_introspection(url: str | None, supported_versions: tuple[str, ...] = (),
                        token: str | None = None) -> LiveRead:
    if not url:
        return LiveRead("연결 안 함", detail="introspection_url 이 프로필에 없음")
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        request = Request(url, method="GET", headers=headers)
        with urlopen(request, timeout=3) as response:
            if response.status == 404:
                return LiveRead("그 경로가 없음", detail=url)
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return LiveRead("그 경로가 없음", detail=url)
        if exc.code in (401, 403):
            # ★"대상이 응답하지 않음" 으로 뭉치면 사실이 아니다 — 대상은 응답했다,
            #   인증이 안 됐을 뿐이다. 실측(scope `ops:introspect`)으로 확인했다.
            detail = "introspection_token 이 프로필에 없거나 scope 가 안 맞음" if not token else f"HTTP {exc.code}"
            return LiveRead("인증 실패", detail=detail)
        return LiveRead("대상이 응답하지 않음", detail=f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return LiveRead("대상이 응답하지 않음", detail=str(exc))
    if not isinstance(raw, dict):
        return LiveRead("계약 버전 모름", detail="응답이 객체가 아님")
    version = raw.get("contract_version")
    if version not in supported_versions:
        return LiveRead("계약 버전 모름", value=raw, detail=f"contract_version={version!r}")
    return LiveRead("읽음", value=raw, detail=f"contract_version={version}")


def reload_url_for(introspection_url: str | None) -> str | None:
    """`/introspection` 주소에서 `/admin/reload` 주소를 만든다.

    ★두 표면은 같은 프로세스의 것이다. 주소를 따로 받게 하면 운영자가 서로
      다른 대상을 가리켜 놓고 **남의 프로세스를 반영시키는** 사고가 난다.
    """
    if not introspection_url:
        return None
    root = introspection_url.rstrip("/")
    if root.endswith("/introspection"):
        root = root[: -len("/introspection")]
    return f"{root}/admin/reload"


def trigger_reload(introspection_url: str | None, token: str | None) -> LiveRead:
    """대상에게 **지금** 반영하라고 요청한다 (`POST /admin/reload`).

    ★대상은 새 조립이 전부 성공한 뒤에만 갈아 끼운다. 실패하면 409 와 함께
      옛 조립을 그대로 쓴다 — 여기서는 그 사실을 **그대로 전한다.** 실패를
      "적용됨" 뒤에 숨기지 않는다.
    """
    url = reload_url_for(introspection_url)
    if not url:
        return LiveRead("연결 안 함", detail="introspection_url 이 프로필에 없음")
    if not token:
        # ★버튼을 눌렀는데 토큰이 없으면 401 이 난다. 왜 안 되는지 먼저 말한다.
        return LiveRead("연결 안 함",
                        detail="CONSOLE_RELOAD_TOKEN 이 없음 (대상 scope `ops:reload`)")
    try:
        request = Request(url, method="POST", data=b"",
                          headers={"Authorization": f"Bearer {token}"})
        with urlopen(request, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {}
        if exc.code in (401, 403):
            return LiveRead("인증 실패",
                            detail="CONSOLE_RELOAD_TOKEN 의 scope 가 `ops:reload` 가 아님")
        if exc.code == 404:
            return LiveRead("그 경로가 없음",
                            detail=f"{url} — 대상이 아직 reload 를 지원하지 않음(계약 1.0)")
        if exc.code == 409:
            # 대상이 새 선언으로 조립하지 못했다. 옛 조립이 계속 돈다.
            error = (body.get("error") or {})
            return LiveRead("반영 실패", value=body,
                            detail=error.get("message") or f"HTTP {exc.code}")
        return LiveRead("대상이 응답하지 않음", detail=f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return LiveRead("대상이 응답하지 않음", detail=str(exc))
    if not isinstance(raw, dict):
        return LiveRead("대상이 응답하지 않음", detail="응답이 객체가 아님")
    return LiveRead("반영됨", value=raw,
                    detail=f"active_revision={raw.get('active_revision')}")
