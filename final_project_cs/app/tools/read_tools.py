"""Tenant-scoped, named read tools for Team modules.

The tool layer deliberately exposes no SQL interface.  A Team supplies only
the tool name and business arguments; tenant/customer scope is taken from the
validated ContextPack.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import UUID

from app.core.contracts import ContextPack, ToolNotAllowed
from app.infrastructure.rag.retriever import search_policy


class ToolBudgetExceeded(RuntimeError):
    """도구 호출이 `manifest.max_steps` 예산을 넘었다.

    ★`ToolLoopExceeded` 와 **다른 예외다.** 원인이 다르기 때문이다 —
      전자는 "같은 것을 또 불렀다"(중복), 이쪽은 "너무 많이 불렀다"(예산).
      한 예외로 묶으면 로그에서 둘을 못 가른다.

    ★2026-09-09 신설. 그전까지 `max_steps` 는 **선언만 되고 아무도 강제하지
      않았다** — 정의·화면표시·introspection 에만 있고 실행 경로 3곳
      (executor·controller·read_tools)에 0회였다. 테스트까지 있었지만
      `manifest.max_steps == 6` 이라는 **선언값**만 봤다.
      경위: wiki/records/reports/debugs/2026-09-09_max_steps가_강제되지_않는다.md
    """


class ToolLoopExceeded(RuntimeError):
    """The same named tool and normalized arguments were requested twice."""


def _as_datetime(value: Any) -> Any:
    """문자열로 온 시각을 `datetime` 으로. ★못 읽으면 `None` — 지금으로 대체하지 않는다.

    지금 시각으로 대체하면 「내일 오후 골프」를 물었는데 오늘 날씨로 답한다.
    """
    from datetime import datetime

    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


@dataclass
class ToolContext:
    tenant_id: str
    customer_id: UUID
    case_id: UUID
    knowledge_scope: list[str]

    @classmethod
    def from_pack(cls, pack: ContextPack) -> "ToolContext":
        customer = pack.current_state.get("customer_id")
        if customer is None:
            raise ValueError("ContextPack.current_state.customer_id is required for read tools")
        return cls(pack.tenant_id, UUID(str(customer)), pack.case_id, pack.knowledge_scope)


@dataclass
class ReadToolbox:
    """Named database operations with injectable connection and policy search."""

    connection_factory: Callable[[], Any]
    policy_search: Callable[..., list[Any]] = search_policy
    #: 바깥 데이터 소스 묶음(`app/infrastructure/travel/`). ★기본값이 `None` 이다 —
    #:  **안 넣으면 여행 도구가 전부 「모름」을 돌려주고 네트워크를 타지 않는다.**
    #:  테스트가 조용히 바깥으로 나가는 사고를 구조로 막는다.
    travel: Any | None = None

    def _one(self, sql: str, params: tuple[Any, ...], columns: tuple[str, ...]) -> dict[str, Any] | None:
        with self.connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        return None if row is None else dict(zip(columns, row))

    # ─────────────────────────────────────────────────────────────
    # 도메인 무관 도구
    #
    # ★2026-09-10 — 여기 있던 커머스 도구 다섯(`read.order`·`read.shipment`·
    #   `read.catalog`·`read.order_items`·`read.return`)을 걷어냈다.
    #   `orders`·`order_items`·`shipments`·`returns`·`products` 를 읽던
    #   함수들이고, 등록된 여행 Team 여섯 중 **아무도 선언하지 않는다**
    #   (`build_registry().manifests()` 로 확인). 남겨 두면 도구 표가
    #   "쓸 수 있는 것" 이 아니라 "옛날에 쓰던 것" 목록이 된다.
    #
    # ★기록해 둔다 — `wiki/records/handoff/10_도메인_교체_가이드.md` §1 은 이
    #   파일을 교체 지점으로 놓지 않았다. basement 순수성 게이트가 `app/tools/`
    #   를 대상에서 빼먹었기 때문이다. 실제로 이 파일은 `app/modules/` 와
    #   마찬가지로 **도메인을 안다.** 게이트 확장은 별도 작업으로 남아 있다.
    def policy(self, scope: ToolContext, *, query: str, **_: Any) -> list[Any]:
        return self.policy_search(scope.tenant_id, query, scope.knowledge_scope)

    def account(self, scope: ToolContext, **_: Any) -> dict[str, Any] | None:
        # ★`customers` 는 core 테이블이다(001_schema.sql). 도메인 유출이 아니다.
        # ★`[미확보]` 2026-09-10 현재 이 도구를 `allowed_tools` 에 적은 Team 은
        #   **없다**(등록 여섯의 manifest 를 세어 확인). 도메인 무관이라 남겨
        #   두지만, 계속 아무도 안 쓰면 지운다.
        return self._one(
            "SELECT customer_id, external_id, email_hash, created_at FROM customers WHERE tenant_id=%s AND customer_id=%s",
            (scope.tenant_id, scope.customer_id),
            ("customer_id", "external_id", "email_hash", "created_at"),
        )

    # ─────────────────────────────────────────────────────────────
    # 여행 도메인 도구 (v10 §5-A · §7 "Mock 허용")
    #
    # ★지금은 전부 **"모름"을 돌려준다.** 지어낸 값을 주지 않는다 —
    #   Team 은 모르면 `escalated` 로 가야 하고, 그 갈래가 처음부터
    #   돌아야 나중에 실데이터를 꽂았을 때 무엇이 달라지는지 알 수 있다.
    #   빈 dict 가 아니라 `None` 인 이유: 빈 값은 "없다"로 읽히고
    #   `None` 은 "모른다"로 읽힌다. 이 도메인에서 둘은 다르다.
    #
    # ★실데이터를 꽂을 때 **확인 시각(confirmed_at)과 출처를 같이** 담는다.
    #   제공자의 영업시간은 "오늘부터 며칠의 예정"이지 조회 순간의 확인이
    #   아니다(v10 §4-D). 재조회 시각을 현장 관찰처럼 표시하면 안 된다.
    def _travel_tools(self) -> dict[str, Any]:
        return {
            "read.booking":  self.booking,
            "read.disruptions": self.disruptions,
            "read.weather_warning": self.weather_warning,
            "read.travel_advisory": self.travel_advisory,
            "read.place":    self.place,
            "read.weather":  self.weather,
            "read.route":    self.route,
            "read.transit":  self.transit,
            "read.supplier": self.supplier,
            "read.holiday":  self.holiday,
        }

    #: 여행 예약의 컬럼. ★`_one()` 이 zip 으로 붙이므로 SELECT 순서와 **같아야** 한다.
    _BOOKING_COLUMNS = ("booking_id", "booking_no", "kind", "status", "starts_at",
                        "party_size", "capacity", "amount_cents", "locked", "place_id")
    _PLACE_COLUMNS = ("place_id", "name", "kind", "latitude", "longitude",
                      "weather_sensitive", "confirmed_at", "open_at_slot",
                      "dietary", "dietary_absent")

    def booking(self, scope: ToolContext, *, booking_id: str | None = None,
                **_: Any) -> dict[str, Any] | None:
        """예약 한 건. 없으면 `None`(모름).

        ★`booking_id` 를 주면 그 건을, 안 주면 **가장 임박한** 예약을 본다.
          「가장 최근에 만든 것」이 아니다 — 여행 CS 에서 문제가 되는 것은
          다가오는 일정이지 방금 만든 예약이 아니다.

        ★tenant·customer 조건을 뺀 조회는 그 자체가 보안 결함이다
          (`CLAUDE.md` §1, `tests/security/`).
        """
        select = ("SELECT booking_id, booking_no, kind, status, starts_at, party_size, "
                  "capacity, amount_cents, locked, place_id FROM bookings "
                  "WHERE tenant_id=%s AND customer_id=%s")
        if booking_id is not None:
            return self._one(select + " AND booking_id=%s",
                             (scope.tenant_id, scope.customer_id, booking_id),
                             self._BOOKING_COLUMNS)
        return self._one(select + " ORDER BY starts_at ASC LIMIT 1",
                         (scope.tenant_id, scope.customer_id), self._BOOKING_COLUMNS)

    def place(self, scope: ToolContext, *, place_id: str | None = None,
              **_: Any) -> dict[str, Any] | None:
        """장소·운영 정보. 없으면 `None`(모름).

        ★`weather_sensitive`·`open_at_slot` 은 NULL 일 수 있고 그건 **모름**이다.
          받는 쪽이 NULL 을 「아니다」로 읽으면 안 된다 — 그 구분을 Team 이 한다.

        ★`confirmed_at` 은 「영업 정보를 확인한 시각」이다. 이 값이 없으면
          Team 은 "확인했다" 고 말하지 않는다(v10 §4-D).
        """
        if place_id is None:
            return None      # ★어느 장소인지 모르면 조회하지 않는다
        row = self._one(
            "SELECT place_id, name, kind, latitude, longitude, weather_sensitive, "
            "hours_confirmed_at, open_at_slot, dietary, dietary_absent FROM places "
            "WHERE tenant_id=%s AND place_id=%s",
            (scope.tenant_id, place_id), self._PLACE_COLUMNS)
        return self._fill_coordinates(row)

    def _fill_coordinates(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        """좌표가 비었으면 국가유산청에서 채운다. ★**어디서 왔는지 남긴다.**

        ★좌표가 없으면 `read.weather` 가 아무것도 못 한다 — 「어디인지 모르는
          곳의 날씨」는 없다. 그래서 채울 수 있으면 채운다.

        ★★**출처를 안 남기면 안 된다.** 우리 DB 값과 바깥에서 온 값이 한
          dict 에 섞이는데, 나중에 좌표가 틀렸을 때 어디를 고쳐야 하는지
          알 수 없게 된다. `coordinates_source` 가 그걸 말한다.
        """
        if row is None:
            return None
        if row.get("latitude") is not None and row.get("longitude") is not None:
            row["coordinates_source"] = "db"
            return row
        source = getattr(self.travel, "heritage", None) if self.travel else None
        if source is None or not row.get("name"):
            return row      # ★못 채우면 비운 채 둔다. 지어내지 않는다
        found = source.locate(str(row["name"]))
        if found is None:
            return row
        row["latitude"] = found["latitude"]
        row["longitude"] = found["longitude"]
        row["coordinates_source"] = found["source"]
        row["coordinates_confirmed_at"] = found["confirmed_at"]
        return row

    def holiday(self, scope: ToolContext, *, on: Any = None,
                **_: Any) -> dict[str, Any] | None:
        """그 날짜가 공휴일인가. 모르면 `None`.

        ★★**「그 장소가 쉬는가」는 답하지 않는다.** 공휴일에 여는 식당도 많고
          공휴일에만 여는 곳도 있다. 둘을 같게 다루면 근거 없는 확정이 된다 —
          응답의 `answers_whether_the_place_is_closed` 가 그 사실을 들고 있다.
        """
        from datetime import date, datetime

        if self.travel is None or self.travel.holiday is None:
            return None
        when = _as_datetime(on) if not isinstance(on, date) or isinstance(on, datetime) else on
        if isinstance(when, datetime):
            when = when.date()
        if not isinstance(when, date):
            return None      # ★언제인지 모르면 묻지 않는다
        return self.travel.holiday.is_holiday(when)

    def weather(self, scope: ToolContext, *, latitude: float | None = None,
                longitude: float | None = None, at: Any = None,
                **_: Any) -> dict[str, Any] | None:
        """그 좌표·그 시각의 기상 예보. 모르면 `None`.

        ★**좌표를 모르면 묻지 않는다.** 「어디인지 모르는 곳의 날씨」는 없다.
          좌표는 예약(`read.booking`)이나 장소(`read.place`)에서 온다.

        ★`place_id` 만 주는 호출도 받는다(인자를 `**_` 로 흘린다). 그때는
          좌표가 없으므로 `None` = 모름이다. 장소 소스가 붙으면 그 자리에서
          좌표를 얻어 넘기게 바꾼다.

        ★반환값은 **예보**다(`kind="forecast"`). 관찰이 아니다 — Team 이
          문구를 그렇게 쓴다(v10 §4-D).
        """
        if self.travel is None or self.travel.weather is None:
            return None
        if latitude is None or longitude is None:
            return None
        return self.travel.weather.forecast(
            latitude=float(latitude), longitude=float(longitude),
            at=_as_datetime(at))

    def disruptions(self, scope: ToolContext, *, place_id: Any = None,
                    latitude: float | None = None, longitude: float | None = None,
                    weather_sensitive: bool | None = None, region: str = "서울",
                    district: str | None = None, starts_at: Any = None,
                    **_: Any) -> dict[str, Any] | None:
        """일정 항목 하나의 **성립 점검** — 바깥 소스를 한 번에 돌려 판정 하나로.

        ★Team 은 예보·특보를 따로 부르지 않고 이것 하나만 부른다(도구 1회).
          감시 루프도 같은 판정을 쓴다 — 문의 때와 감시 때 기준이 갈리지 않게.
        ★소스 묶음이 주입되지 않았으면 `None` — 바깥으로 나가지 않는다.
        """
        if self.travel is None:
            return None
        from app.infrastructure.travel.disruptions import DisruptionCheck

        return DisruptionCheck(self.travel).check(
            place={"place_id": place_id, "latitude": latitude, "longitude": longitude,
                   "weather_sensitive": bool(weather_sensitive), "district": district},
            starts_at=_as_datetime(starts_at), region=str(region))

    def weather_warning(self, scope: ToolContext, *, region: str = "서울",
                        **_: Any) -> dict[str, Any] | None:
        """지금 발효 중인 기상특보와 그중 `region` 을 덮는 것. 모르면 `None`.

        ★빈 목록(`for_region=[]`)은 「그 지역 특보 없음」이라는 **아는 사실**이고,
          `None` 은 조회를 못 한 것이다. Team 이 둘을 섞으면 조회가 죽은 날
          「특보 없음」이라고 답한다.
        """
        if self.travel is None or getattr(self.travel, "warning", None) is None:
            return None
        return self.travel.warning.active(region=str(region))

    def travel_advisory(self, scope: ToolContext, *, country_iso2: str | None = None,
                        **_: Any) -> dict[str, Any] | None:
        """그 나라의 외교부 여행경보. 나라 코드를 모르면 묻지 않는다(`None`).

        ★v11 MVP 는 서울뿐이라 이 도구를 선언한 Team 은 아직 없다 — 해외로
          넓힐 때 쓸 자리를 먼저 둔다.
        """
        if self.travel is None or getattr(self.travel, "advisory", None) is None:
            return None
        if not country_iso2:
            return None
        return self.travel.advisory.country(iso2=str(country_iso2))

    def route(self, scope: ToolContext, **_: Any) -> None:
        """이동 시간. `[미구현]` — Routes API 를 붙일 자리."""
        return None

    def transit(self, scope: ToolContext, **_: Any) -> None:
        """운행·막차. `[미구현]`."""
        return None

    def supplier(self, scope: ToolContext, *, booking_id: str | None = None,
                 **_: Any) -> dict[str, Any] | None:
        """공급자 원장의 그 예약. 없으면 `None`(모름).

        ★우리 `bookings.status` 와 **따로** 산다. 어긋나는 것이 정상이고,
          어긋남을 찾는 것이 `booking.verify` 의 일이다. 한 곳에서 읽어 오면
          그 capability 가 자기 자신과 비교하는 꼴이 된다.

        ★지금 원본은 우리 DB 의 `supplier_bookings` 다(시연용 Mock 공급자).
          실제 공급자 API 가 붙으면 이 함수만 바뀌고 Team 은 안 바뀐다.
        """
        if booking_id is None:
            return None
        return self._one(
            "SELECT supplier_booking_id, supplier, supplier_ref, status, confirmed_at "
            "FROM supplier_bookings WHERE tenant_id=%s AND booking_id=%s",
            (scope.tenant_id, booking_id),
            ("supplier_booking_id", "supplier", "supplier_ref", "status", "confirmed_at"))

    def call(self, name: str, context: ContextPack, arguments: dict[str, Any],
             allowed_tools: list[str], seen: set[str], budget: int | None = None) -> Any:
        """`budget` 은 이 Team 이 쓸 수 있는 도구 호출 수 상한이다.

        ★기본값이 `None` 이라 **안 넘기면 예전과 똑같이 동작한다.** 호출부를
          한꺼번에 고치지 않아도 되게 한 것이고, 넘기는 쪽은
          `self.manifest.max_steps` 를 준다.
        ★`seen` 의 크기를 그대로 센다 — 새 카운터를 만들지 않았다.
          `seen` 은 중복 차단기지만 그 크기가 곧 호출 횟수라 예산으로 맞는다.
        """
        # ★예산 검사를 allowlist 보다 **먼저** 두지 않는다. 권한 없는 도구는
        #   예산과 무관하게 거부돼야 하고, 그 편이 오류 메시지도 정확하다.
        if name not in allowed_tools:
            raise ToolNotAllowed(f"tool '{name}' is not allowed for this task")
        functions = {
            **self._travel_tools(),
            "read.policy": self.policy,
            "read.account": self.account,
        }
        if name not in functions:
            raise ToolNotAllowed(f"unknown tool '{name}'")
        signature = name + ":" + json.dumps(arguments, sort_keys=True, default=str, separators=(",", ":"))
        if signature in seen:
            raise ToolLoopExceeded(f"repeated tool request: {name}")
        if budget is not None and len(seen) >= budget:
            raise ToolBudgetExceeded(
                f"tool budget {budget} exhausted before '{name}' "
                f"(already called {len(seen)})")
        seen.add(signature)
        return functions[name](ToolContext.from_pack(context), **arguments)


ALLOWED_PROMPT_KEYS = frozenset({"response.generate", "response.review_tone"})


def register_prompt_files(
    conn: Any, prompt_root: str = "prompts", model_family: str = "unknown"
) -> tuple[list[UUID], list[str]]:
    """Register and activate the supported versioned prompt files atomically."""
    import hashlib
    from pathlib import Path

    root = Path(prompt_root)
    ids: list[UUID] = []
    skipped: list[str] = []
    candidates: list[tuple[Any, str, str, str, str]] = []
    for path in sorted(root.glob("*/**/*.v*.md")):
        stem, version = path.name.rsplit(".v", 1)
        version = version.removesuffix(".md")
        key = f"{path.parent.name}.{stem}"
        if key not in ALLOWED_PROMPT_KEYS:
            skipped.append(str(path))
            continue
        text = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        candidates.append((path, key, version, text, digest))

    with conn.transaction():
        with conn.cursor() as cur:
            for path, key, version, text, digest in candidates:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key,))
                cur.execute(
                    "SELECT prompt_id, version, sha256 FROM prompts "
                    "WHERE prompt_key=%s AND (sha256=%s OR version=%s)",
                    (key, digest, version),
                )
                rows = cur.fetchall()
                same_hash = next((row for row in rows if row[2] == digest), None)
                same_version = next((row for row in rows if row[1] == version), None)
                if same_version is not None and same_version[2] != digest:
                    raise ValueError(
                        f"prompt version collision for {key} v{version}: content differs"
                    )
                if same_hash is not None:
                    prompt_id = same_hash[0]
                else:
                    cur.execute(
                        "INSERT INTO prompts (prompt_key, version, template, sha256, model_family, active) "
                        "VALUES (%s,%s,%s,%s,%s,false) RETURNING prompt_id",
                        (key, version, text, digest, model_family),
                    )
                    prompt_id = cur.fetchone()[0]
                cur.execute("UPDATE prompts SET active=false WHERE prompt_key=%s", (key,))
                cur.execute("UPDATE prompts SET active=true WHERE prompt_id=%s", (prompt_id,))
                cur.execute("SELECT count(*) FROM prompts WHERE prompt_key=%s AND active=true", (key,))
                if cur.fetchone()[0] != 1:
                    raise RuntimeError(f"expected exactly one active prompt for {key}")
                ids.append(prompt_id)
    return ids, skipped


register_prompts = register_prompt_files


def record_llm_call(conn: Any, *, run_id: UUID | None, prompt_id: UUID, provider: str, model: str, response_json: dict[str, Any] | None = None, input_tokens: int | None = None, output_tokens: int | None = None, latency_ms: int | None = None, cost_microusd: int | None = None) -> UUID:
    """Record an invocation with the exact registered prompt FK."""
    from app.infrastructure.db.repository import create_llm_call

    return create_llm_call(conn, run_id=run_id, prompt_id=prompt_id, provider=provider, model=model, response_json=response_json, input_tokens=input_tokens, output_tokens=output_tokens, latency_ms=latency_ms, cost_microusd=cost_microusd)
