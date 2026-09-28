"""실행 중인 조립 하나를 붙잡고, **무엇이 실제로 돌고 있는지** 를 말한다.

★왜 필요한가 — 이 전까지 `/introspection` 은 매 요청마다 선언을 **다시 읽어서**
  `config_revision` 을 계산했다(`introspection/contract.py`). 그래서 Composer 로
  선언을 바꾸면, 대상 프로세스는 아직 옛 조립으로 요청을 처리하고 있는데도
  화면에는 **새 revision 이 이미 반영된 것처럼** 보였다. 반영 안 된 상태를
  정상처럼 보이게 하는 것 — 설계검토(`docs/reports/2026-08-19_Composer_reload_
  계약_설계검토.md` §3)가 "허용하지 않는다" 고 적어 둔 바로 그 상태다.

여기서 구분하는 것은 셋이다:

    active_revision    지금 요청을 처리하는 Controller 를 **실제로 만든** 선언
    desired_revision   저장소(파일 또는 중앙 DB)에 지금 들어 있는 선언
    reload_state       둘이 다를 때 무슨 일이 있었는가

★`active` 는 관찰로 계산하지 않는다. 조립할 때 받아 적은 값이다. 다시 읽어서
  계산하면 그건 저장소를 보는 것이지 실행 중인 것을 보는 게 아니다.
"""
from __future__ import annotations

import threading
from typing import Any

#: 반영 상태. ★`pending_reload` 를 쓰지 않는다 — 이 런타임은 스스로 폴링하지
#:  않으므로, 아무도 reload 를 부르지 않으면 영원히 pending 이다. 기다리면
#:  되는 것처럼 보이는 이름을 붙이지 않는다.
STATE_ACTIVE = "active"
STATE_STALE = "stale"
STATE_FAILED = "reload_failed"
#: ★한쪽 revision 을 모르면 "같다" 도 "다르다" 도 말하지 않는다. 모르는 것을
#:  `stale` 로 적으면 없는 사실을 만든 것이고, `active` 로 적으면 반영 안 된
#:  상태를 정상으로 감춘 것이다.
STATE_UNKNOWN = "unknown"


class RuntimeComposition:
    """조립된 Controller 하나 + 그것을 만든 revision.

    ★교체는 **완성된 새 Controller 를 받은 뒤에만** 일어난다. 조립 도중에
      바꿔치면 어떤 요청은 새 registry, 어떤 요청은 옛 registry 를 보게 된다.
    """

    def __init__(self, controller: Any, revision: str | None) -> None:
        self._lock = threading.Lock()
        self._controller = controller
        self._revision = revision
        self._error: str | None = None
        self._failed_revision: str | None = None

    @property
    def controller(self) -> Any:
        return self._controller

    @property
    def active_revision(self) -> str | None:
        """★`None` 은 "모름" 이다(주입된 Controller 등). 지어내지 않는다."""
        return self._revision

    @property
    def last_error(self) -> str | None:
        return self._error

    @property
    def failed_revision(self) -> str | None:
        return self._failed_revision

    def state(self, desired_revision: str | None) -> str:
        """저장소의 선언과 견줘 지금 상태를 말한다."""
        if self._error is not None and self._failed_revision == desired_revision:
            return STATE_FAILED
        if self._revision is None or desired_revision is None:
            return STATE_UNKNOWN
        return STATE_ACTIVE if self._revision == desired_revision else STATE_STALE

    def swap(self, controller: Any, revision: str | None) -> None:
        """새 조립으로 갈아 끼운다. 성공한 조립만 여기 들어온다."""
        with self._lock:
            self._controller = controller
            self._revision = revision
            self._error = None
            self._failed_revision = None

    def mark_failed(self, revision: str | None, error: str) -> None:
        """★실패를 삼키지 않는다. 옛 조립은 그대로 두고 실패한 사실을 남긴다."""
        with self._lock:
            self._error = error
            self._failed_revision = revision


class ControllerProxy:
    """요청 때마다 **지금** 의 Controller 로 넘긴다.

    ★router 가 조립 시점의 Controller 객체를 붙잡고 있으면 교체해도 옛 것을
      계속 쓴다. 그래서 한 겹을 둔다 — 속성 접근을 그때그때 넘긴다.
      교체는 참조 하나를 바꾸는 것이라 요청 중간에 반쯤 바뀌는 일이 없다.
    """

    __slots__ = ("_runtime",)

    def __init__(self, runtime: RuntimeComposition) -> None:
        object.__setattr__(self, "_runtime", runtime)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_runtime").controller, name)

    def __repr__(self) -> str:  # 디버깅에서 프록시인 걸 숨기지 않는다
        runtime = object.__getattribute__(self, "_runtime")
        return f"<ControllerProxy revision={runtime.active_revision!r}>"
