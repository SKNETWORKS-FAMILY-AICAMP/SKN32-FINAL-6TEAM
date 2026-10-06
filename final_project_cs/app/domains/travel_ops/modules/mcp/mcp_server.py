# -*- coding: utf-8 -*-
"""triPilot MCP 서버 — 개인 AI(Claude · ChatGPT · Cursor …)가 **사용자 본인의 여행**을 다루는 입구. `[2026-10-02 사용자 지시]`

☆왜 새로 만들었나. 옛 도구 셋(`app/presentation/api/mcp.py` — 쇼핑몰 시절 Case 3개)은 **띄우는 곳이 한 번도 없었고**(git 이력 전체 · sample 저장소까지
  확인) 여행(trips) 도구가 없었다. 그대로 띄우면 호출 주체가 고정(`mcp:read`)이고 `customer_id` 를 호출자가 정해서 **남의 문의를 읽는 구멍**이 된다.
  경쟁 서비스(Wanderlog · Tripsy · Trvlrr · Trip Planner MCP)는 전부 「AI 가 일정 내용을 편집」하는 CRUD 도구다. 우리는 일정을 **검증하고 지켜보고
  틀어지면 고치는** 서비스라 도구도 그 동사다 — 조회 · 신고 · 다른 안으로 · 제안 고르기 · 되돌리기 · 검증받고 등록.

★설계 원칙(사용자와 정한 것 + 이 저장소 규칙).
  ① **MCP 는 새 규칙을 만들지 않는다.** 모든 도구는 웹 API(`/v1/web/*`)를 **그대로 부른다** — 인증 · 소유 확인 · 멱등 · 남용 방어 · 판정이
     웹과 같은 한 곳에 있다(한 규칙이 두 벌로 갈라지지 않게). 이 파일은 얇은 어댑터다.
  ② **호출자는 사용자 키가 정한다.** `Authorization: Bearer <사용자 키>` 또는 `X-User-Key`(웹이 쓰는 그 키, 025). 도구 인자로 `customer_id` 를 받지 않는다 —
     그 키의 사용자 **본인의 여행만** 열린다. 키 없음 · 틀림은 연결 단계에서 401 이다(도구까지 오지 않는다).
  ③ **읽기 도구는 늘 열려 있고, 쓰기 도구는 `travel.mcp.write_enabled` 가 켜졌을 때만 등록된다**(기본 꺼짐 — 프로젝트의 「MCP 는 read-only」 원칙, CLAUDE.md §0.2).
     쓰기라도 **일정만** 바꾸고(되돌리기 가능 · 판마다 기록) 결제 · 업체 예약은 건드리지 않는다. 켜려면 설정을 고치고 다시 띄운다.
  ④ **`mcp` 모듈 토글을 요청마다 본다**(`project.yaml` `modules.mcp.enabled`) — 끄면 404 다(표면이 없는 것처럼).
  ⑤ 키 원문은 오류 · 로그 어디에도 싣지 않는다.

★전송 두 가지.
  - **원격(Streamable HTTP)**: 고객 API 앱에 `/mcp/` 로 붙는다(`composition.build_mcp_surface`). 무상태(stateless) — 일꾼이 여럿이어도 맞다.
      claude mcp add --transport http tripilot https://<주소>/mcp/ --header "Authorization: Bearer <사용자 키>"
  - **로컬(stdio, 프록시)**: `python -m app.domains.travel_ops.modules.mcp.mcp_server --base-url http://127.0.0.1:8042` + 환경변수 `TRIPILOT_USER_KEY`.
      Claude Desktop · Cursor 가 프로세스로 띄운다. 실제 일은 원격 서버가 하고 이쪽은 전달만 한다.
"""
# ★`from __future__ import annotations` 를 쓰지 않는다 — FastMCP 가 도구 인자의 타입 표시를 함수 안에서 풀어 쓰는데,
#   문자열로 미뤄진 표시(`TripId` 같은 지역 별칭)는 풀리지 않는다.
import argparse
import asyncio
import json
import logging
import os
import re
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal, Protocol

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

log = logging.getLogger(__name__)

SERVER_NAME = "triPilot"

INSTRUCTIONS = """\
triPilot 은 여행 중 일정이 틀어질 때 지켜 주고 고쳐 주는 서비스입니다(서울 · 여행자 본인의 여행). 이 서버의 도구는 호출한 사용자 **본인의 여행**만 다룹니다.

사용 순서: 먼저 tripilot_list_trips 로 여행 id 를 얻고, tripilot_get_trip 으로 일정(항목마다 식사/활동/이동 구분 · 시각 · 장소 정보)을 읽습니다.
알림은 tripilot_get_notices, 서버가 고객에게 물어 둔 선택지는 tripilot_get_proposals 입니다.
곧 시작할 일정이 날씨 · 특보 · 재난 · 교통 통제 · 대기질 · 지진 때문에 문제가 될지는 tripilot_check_trip_risks, 두 장소 사이를 몇 시에 떠나 어떻게 가는지는 tripilot_judge_move 입니다 —
둘 다 읽기만 합니다. 결과의 status 가 unknown(확인 불가)이면 「문제 없다」고 말하지 말고 확인하지 못했다고 전하세요. 값을 지어내지 마세요.

일정을 바꾸는 도구(쓰기)가 보이면 — 지연 · 휴무 같은 **사실은 지어내지 말고** 사용자가 말한 것만 tripilot_report_issue 로 전하세요. 바꾼 결과의 문장은
서버가 돌려준 `answer` 를 그대로 전하고(서버가 가진 사실로만 만든 말입니다), 모르는 것을 추측해 메우지 마세요. 어떤 변경이든 tripilot_rollback 으로 되돌릴 수 있습니다.
식당 · 숙소 예약과 결제는 이 서버가 하지 않습니다. 시각은 한국 표준시(+09:00)입니다.
"""

#: 항목 종류가 아니라 **사람이 읽는 줄**을 만들 때 쓴다 — 서버가 `kind_label` · `meal` 을 이미 준다
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


class McpApiError(Exception):
    """웹 API 가 거절했다 — 사람이 읽을 이유(`message`)와 코드. ★키 원문은 담지 않는다."""

    def __init__(self, status: int, code: str, message: str, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}

    def text(self) -> str:
        tail = {k: v for k, v in self.extra.items() if k in ("problems", "relax", "reasons", "items", "fields", "retry_after_seconds")}
        return f"{self.message} ({self.code}, HTTP {self.status})" + (f" {json.dumps(tail, ensure_ascii=False)}" if tail else "")


@dataclass(frozen=True)
class Caller:
    key: str
    ip: str | None = None
    forwarded_for: str | None = None


class Backend(Protocol):
    async def request(self, method: str, path: str, *, caller: Caller, json: Any = None,
                      params: dict[str, Any] | None = None, form: dict[str, str] | None = None) -> Any: ...


def _error_of(response: httpx.Response) -> McpApiError:
    code, message, extra = "error", "요청을 처리하지 못했어요", {}
    try:
        body = response.json()
        error = (body.get("error") or (body.get("detail") or {}).get("error")) if isinstance(body, dict) else None
        if isinstance(error, dict):
            code, message = str(error.get("code") or code), str(error.get("message") or message)
            extra = {k: v for k, v in error.items() if k not in ("code", "message")}
        elif isinstance(body, dict) and isinstance(body.get("detail"), str):
            message = body["detail"]
    except ValueError:
        pass
    retry = response.headers.get("retry-after")
    if retry and retry.isdigit():
        extra.setdefault("retry_after_seconds", int(retry))
    return McpApiError(response.status_code, code, message, extra)


class _HttpxBackend:
    """공통 — 사용자 키는 `X-User-Key` 로만 보낸다."""

    timeout = 180.0           # 채팅 · 일정 짜기는 모델을 기다린다(서버 쪽 시간 제한 90 · 240초와 같은 단위)

    def _client(self, caller: Caller) -> httpx.AsyncClient:                      # pragma: no cover — 하위 클래스가 만든다
        raise NotImplementedError

    async def request(self, method: str, path: str, *, caller: Caller, json: Any = None,
                      params: dict[str, Any] | None = None, form: dict[str, str] | None = None) -> Any:
        headers = {"X-User-Key": caller.key, "Accept": "application/json"}
        if caller.forwarded_for:
            headers["X-Forwarded-For"] = caller.forwarded_for
        async with self._client(caller) as http:
            response = await http.request(method, path, headers=headers, json=json, params=params, data=form)
        if response.status_code >= 400:
            raise _error_of(response)
        return response.json()


class AsgiBackend(_HttpxBackend):
    """같은 프로세스의 앱을 **네트워크 없이** 부른다(원격 MCP 가 앱에 붙어 있을 때). 호출자 주소는 그대로 넘겨 남용 방어가 사용자 주소로 센다."""

    def __init__(self, app_getter: Callable[[], Any]) -> None:
        self._app = app_getter

    def _client(self, caller: Caller) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=self._app(), client=(caller.ip or "127.0.0.1", 0))
        return httpx.AsyncClient(transport=transport, base_url="http://tripilot.internal", timeout=self.timeout)


class HttpBackend(_HttpxBackend):
    """원격 서버를 HTTP 로 부른다(로컬 stdio 프록시)."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def _client(self, caller: Caller) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self._base, timeout=self.timeout)


# ── 호출자 ────────────────────────────────────────────────────────

def key_from_headers(headers: Any) -> str | None:
    """`Authorization: Bearer <키>` 또는 `X-User-Key`. 둘 다 있으면 Bearer 가 먼저."""
    auth = headers.get("authorization") or ""
    if auth.lower().startswith("bearer ") and auth[7:].strip():
        return auth[7:].strip()
    return (headers.get("x-user-key") or "").strip() or None


def caller_of(ctx: Context | None, *, env_key: str | None = None) -> Caller:
    """이 도구 호출의 주인 — HTTP 요청의 헤더(원격) 또는 환경변수(로컬 stdio). 없으면 ToolError(키 원문은 어디에도 싣지 않는다)."""
    request = None
    try:
        request = ctx.request_context.request if ctx is not None else None
    except Exception:                                      # noqa: BLE001 — 요청 맥락이 없는 전송(stdio · 메모리)
        request = None
    if request is not None:
        key = key_from_headers(request.headers)
        client = getattr(request, "client", None)
        if key:
            return Caller(key, getattr(client, "host", None), request.headers.get("x-forwarded-for"))
    key = env_key or os.environ.get("TRIPILOT_USER_KEY")
    if not key:
        raise ToolError("사용자 키가 없어요 — 연결할 때 `Authorization: Bearer <사용자 키>` 를 붙이거나 로컬이면 환경변수 TRIPILOT_USER_KEY 를 넣어 주세요. "
                        "키는 triPilot 웹의 마이페이지 「에이전트 연결」에서 로그인한 뒤 만들 수 있고, 만들 때 한 번만 보여 드립니다.")
    return Caller(key)


# ── 보기 줄이기 ──────────────────────────────────────────────────

def _hhmm(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%H:%M")
    except ValueError:
        return iso[11:16]


def outline_of(items: list[dict[str, Any]]) -> list[str]:
    """AI 가 사용자에게 그대로 옮기기 쉬운 줄 — `10-05 09:00–10:00 [식사·아침] 개화`. 이동 항목은 빼지 않는다(시간이 걸리는 일이다)."""
    lines = []
    for item in sorted(items, key=lambda i: (i.get("starts_at") or "", i.get("seq") or 0)):
        label = item.get("kind_label") or item.get("kind") or ""
        meal = f"·{item['meal']}" if item.get("meal") else ""
        end = f"–{_hhmm(item.get('ends_at'))}" if item.get("ends_at") else ""
        mark = " (예약)" if item.get("booked") else ""
        lines.append(f"{(item.get('starts_at') or '')[5:10]} {_hhmm(item.get('starts_at'))}{end} [{label}{meal}] {item.get('title')}{mark}")
    return lines


def trim_trip(view: dict[str, Any], day: str | None = None) -> dict[str, Any]:
    """웹 여행 조회를 AI 가 읽기 좋게 — 지도 핀(`map`) 은 빼고 줄글(`outline`)을 더한다. `day` 가 있으면 그날 항목만."""
    items = view.get("items") or []
    if day:
        items = [i for i in items if (i.get("starts_at") or "")[:10] == day]
    keep = ("item_id", "seq", "kind", "kind_label", "meal", "title", "place", "starts_at", "ends_at", "booked", "changed",
            "customer_pinned", "other_options", "place_info", "map_url")
    out = {k: v for k, v in view.items() if k not in ("items", "map", "history")}
    out["items"] = [{k: i.get(k) for k in keep} for i in items]
    out["outline"] = outline_of(items)
    out["recent_changes"] = (view.get("history") or [])[-5:]
    return out


def _request_id(given: str | None) -> str:
    return (given or "").strip() or f"mcp-{uuid.uuid4().hex}"


# ── 서버 ──────────────────────────────────────────────────────────

def build_server(backend: Backend, *, write_enabled: bool = False, env_key: str | None = None,
                 name: str = SERVER_NAME) -> FastMCP:
    """도구 묶음. `write_enabled` 가 거짓이면 쓰기 도구는 **등록하지 않는다**(보이지도 않는다)."""
    server = FastMCP(
        name, instructions=INSTRUCTIONS, stateless_http=True, json_response=True, streamable_http_path="/",
        # ★DNS 재바인딩 방어는 끈다 — 인증이 쿠키가 아니라 요청마다 붙는 키 헤더라 재바인딩으로 얻을 것이 없고, 켜면 실제 도메인 접속이 막힌다
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))

    async def call(ctx: Context | None, method: str, path: str, **kw: Any) -> Any:
        caller = caller_of(ctx, env_key=env_key)
        try:
            return await backend.request(method, path, caller=caller, **kw)
        except McpApiError as exc:
            raise ToolError(exc.text()) from None
        except httpx.HTTPError as exc:
            # 키가 헤더에 있어 메시지에 새지는 않지만, 내부 주소가 사용자에게 가지 않게 종류만 말한다
            raise ToolError(f"서버에 연결하지 못했어요 ({type(exc).__name__}) — 잠시 뒤 다시 시도해 주세요") from None

    TripId = Annotated[str, Field(description="여행 id (tripilot_list_trips 의 trip_id)")]

    # ── 읽기 ──
    @server.tool(name="tripilot_list_trips", annotations=READ, title="내 여행 목록",
                 description="이 사용자의 여행 목록(trip_id · 제목 · 판 번호 · 만든 시각). 다른 도구에 쓸 trip_id 를 여기서 얻는다.")
    async def list_trips(ctx: Context) -> dict[str, Any]:
        return await call(ctx, "GET", "/v1/web/trips")

    @server.tool(name="tripilot_get_trip", annotations=READ, title="여행 일정 보기",
                 description="여행 한 건의 일정. 항목마다 종류(kind_label: 식사·활동·이동·숙소) · 끼니(meal) · 시각 · 장소 정보(주소·전화·영업시간) · 예약 여부 · "
                             "서버가 마련해 둔 다른 안(other_options)이 있다. outline 은 사용자에게 보여 주기 좋은 한 줄씩의 요약. day(YYYY-MM-DD)를 주면 그날만. "
                             "plan_url 은 사용자가 직접 열어 볼 수 있는 계획서 링크.")
    async def get_trip(ctx: Context, trip_id: TripId,
                       day: Annotated[str | None, Field(description="YYYY-MM-DD — 그날 항목만 (없으면 전체)")] = None) -> dict[str, Any]:
        if day is not None and not _DAY.match(day):
            raise ToolError("day 는 YYYY-MM-DD 형식이에요 (예: 2026-10-05)")
        return trim_trip(await call(ctx, "GET", f"/v1/web/trips/{trip_id}"), day)

    @server.tool(name="tripilot_get_notices", annotations=READ, title="알림 보기",
                 description="이 여행에 서버가 보낸 알림 전부 — 일정 변경 통지 · 하루 시작/다음 일정 안내 · 안전 알림 · 선택 요청. type 으로 구분하고 version 은 그 알림이 만든 일정 판이다.")
    async def get_notices(ctx: Context, trip_id: TripId) -> dict[str, Any]:
        return await call(ctx, "GET", f"/v1/web/trips/{trip_id}/notices")

    @server.tool(name="tripilot_get_proposals", annotations=READ, title="대기 중인 제안 보기",
                 description="서버가 사용자에게 「바꿀까요?」 하고 물어 둔 선택지(변경하지 않은 상태로 기다리는 제안). 각 제안의 options 의 key 를 tripilot_choose_proposal 에 쓴다.")
    async def get_proposals(ctx: Context, trip_id: TripId) -> dict[str, Any]:
        return await call(ctx, "GET", f"/v1/web/trips/{trip_id}/proposals")

    @server.tool(name="tripilot_get_itinerary_schema", annotations=READ, title="일정 등록 형식",
                 description="tripilot_submit_itinerary 가 받는 일정 JSON 의 스키마(장소 places · 항목 items · 이동 routes). 직접 일정을 만들어 검증받으려면 먼저 이것을 읽는다.")
    async def get_schema() -> dict[str, Any]:
        from app.domains.travel_ops.entry.trip_api import CreateTrip

        schema = CreateTrip.model_json_schema()
        schema.get("properties", {}).pop("customer_id", None)          # 사용자는 키가 정한다 — 몸통에 넣지 않는다
        if "customer_id" in schema.get("required", []):
            schema["required"] = [r for r in schema["required"] if r != "customer_id"]
        return schema

    @server.tool(name="tripilot_check_trip_risks", annotations=READ, title="일정 위험 점검",
                 description="내 여행에서 곧 시작할 일정(기본: 지금부터 12시간 안 · 진행 중 포함)마다 외부 정보 6종 — 날씨 예보 · 기상 특보 · 재난문자 · 교통 통제 · 대기질 · 지진 — 이 문제를 가리키는지. "
                             "항목마다 status 는 problem(문제 있음 · problems 에 원인) · clear(확인할 종류를 모두 확인했고 문제 없음 — 실내 장소의 예보처럼 볼 필요 없는 종류는 not_applicable) · unknown(문제는 못 찾았지만 확인하지 못한 종류가 있음 — unknown_categories 의 code: not_cached · source_failed · not_connected · missing · partial(소스 일부만 답함) · too_early(시작까지 3시간 넘게 남아 지금 상태만 확인됨)). "
                             "★unknown 을 「문제 없음」으로 전하지 않는다. 각 종류의 confirmed_at 은 그 소스 값을 받아 온 시각이고 cautions 에 구분 못 한 재난문자 · 모델 추정 대기질 같은 주의가 실린다. 이미 시작한 일정은 지금 기준으로 점검한다. "
                             "기본은 감시가 모아 둔 최근 결과만 읽는다(바깥에 새로 묻지 않음 — 결과가 없는 종류는 unknown). fresh=true 로 캐시에 없는 것을 새로 확인할 수 있지만 횟수 · 항목 수 제한이 있다(공유 하루 한도를 쓴다). "
                             "item_id 로 한 항목만 점검할 수 있다. 읽기 전용이다.")
    async def check_trip_risks(ctx: Context, trip_id: TripId,
                               item_id: Annotated[str | None, Field(description="한 항목만 점검 (tripilot_get_trip 의 item_id)")] = None,
                               within_hours: Annotated[float | None, Field(gt=0, le=48, description="지금부터 몇 시간 안에 시작하는 일정까지 (기본 12)")] = None,
                               fresh: Annotated[bool, Field(description="true 면 캐시에 없는 종류를 새로 확인한다 (횟수 · 항목 수 제한 · 공유 하루 한도 사용). 기본 false")] = False) -> dict[str, Any]:
        params: dict[str, Any] = {"fresh": "true" if fresh else "false"}
        if item_id:
            params["item_id"] = item_id
        if within_hours is not None:
            params["within_hours"] = within_hours
        return await call(ctx, "GET", f"/v1/web/trips/{trip_id}/risks", params=params)

    @server.tool(name="tripilot_judge_move", annotations=READ, title="이동 판정",
                 description="서울 안 두 장소 사이를 이동 판정기가 시간표로 판정한다 — 출발 시각(depart_at) · 경로(route.label · uses 노선) · 소요(eta_min) · 도착 시각 · 대안(alternatives) · "
                             "근거 등급 grade(timetable=열차 시간표 판정 · estimate=도보 · 택시 · 버스(배차 추정)가 낀 경로이거나 판정기가 꺼져 직선 거리 어림만 · none=근거 없음) — 대안(alternatives)마다 grade 가 따로 있다 · 확인 시각 checked_at · 판정에 쓴 시간표 판(basis). "
                             "★시간표 판정이지 실시간 운행 확정이 아니다. 판정기가 꺼져 있거나 오류면 status=unavailable(직선 어림만), 갈 방법이 없으면 status=no_route(이유 그대로), 판정기가 판단하지 못했으면 status=undetermined(갈 방법이 없다는 뜻이 아니다) — 경로 · 시각을 지어내지 않는다. depart_at 이면 requested_depart_at · wait_min(요청 시각에서 고른 출발까지 분)이 붙고 earliest_not_guaranteed=true 면 그 출발이 가장 이른 출발이라는 보장이 없다(wait_min 이 첫차 대기가 아닐 수 있음). 못 찾으면 searched 에 어디까지 봤는지 적힌다. "
                             "장소는 이름 + 위도(lat) · 경도(lon), 또는 내 여행의 일정 항목(trip_id + item_id). 시각은 depart_at(이 시각에 출발) 또는 arrive_by(이 시각까지 도착) 중 하나, 둘 다 없으면 지금 출발. "
                             "읽기 전용이다.")
    async def judge_move(ctx: Context,
                         origin_lat: Annotated[float | None, Field(ge=-90, le=90, description="출발지 위도")] = None,
                         origin_lon: Annotated[float | None, Field(ge=-180, le=180, description="출발지 경도")] = None,
                         origin_name: Annotated[str | None, Field(max_length=80, description="출발지 이름")] = None,
                         destination_lat: Annotated[float | None, Field(ge=-90, le=90, description="도착지 위도")] = None,
                         destination_lon: Annotated[float | None, Field(ge=-180, le=180, description="도착지 경도")] = None,
                         destination_name: Annotated[str | None, Field(max_length=80, description="도착지 이름")] = None,
                         trip_id: Annotated[str | None, Field(description="일정 항목으로 가리킬 때 그 여행 id — 주면 그 여행의 인원 · 이동 선호를 판정에 쓴다")] = None,
                         origin_item_id: Annotated[str | None, Field(description="출발지를 이 여행의 일정 항목으로 (trip_id 필요)")] = None,
                         destination_item_id: Annotated[str | None, Field(description="도착지를 이 여행의 일정 항목으로 (trip_id 필요)")] = None,
                         depart_at: Annotated[str | None, Field(description="이 시각에 출발 — ISO 8601 (시간대 없으면 한국 시각)")] = None,
                         arrive_by: Annotated[str | None, Field(description="이 시각까지 도착 — ISO 8601 (시간대 없으면 한국 시각)")] = None) -> dict[str, Any]:
        def end(item_id: str | None, name: str | None, lat: float | None, lon: float | None) -> dict[str, Any]:
            return {k: v for k, v in (("item_id", item_id), ("name", name), ("lat", lat), ("lon", lon)) if v is not None}

        body: dict[str, Any] = {"origin": end(origin_item_id, origin_name, origin_lat, origin_lon),
                                "destination": end(destination_item_id, destination_name, destination_lat, destination_lon)}
        for key, value in (("trip_id", trip_id), ("depart_at", depart_at), ("arrive_by", arrive_by)):
            if value:
                body[key] = value
        return await call(ctx, "POST", "/v1/web/moves/judge", json=body)

    if not write_enabled:
        return server

    # ── 쓰기(일정만 바꾼다 · 되돌리기 가능 · 결제/업체 예약 없음) ──
    @server.tool(name="tripilot_ask", annotations=WRITE, title="에이전트에게 말하기",
                 description="사용자의 자유 문장을 서버의 여행 창구에 그대로 전한다(질문 · 변경 요청 모두). 「오늘 일정 요약」 같은 질문에는 사실로 답하고, 「점심 다른 데로」 같은 요청은 "
                             "조건을 확인해 바꾼다. 응답의 answer 를 사용자에게 그대로 전한다. 같은 request_id 로 다시 부르면 두 번 처리되지 않는다. "
                             "item_id 로 화면에서 고른 항목을 가리킬 수 있다.")
    async def ask(ctx: Context, trip_id: TripId,
                  message: Annotated[str, Field(min_length=1, description="사용자가 한 말 그대로")],
                  item_id: Annotated[str | None, Field(description="가리키는 항목 id (tripilot_get_trip 의 item_id)")] = None,
                  request_id: Annotated[str | None, Field(description="재시도 시 같은 값을 다시 보낸다 (없으면 새로 만든다)")] = None) -> dict[str, Any]:
        body: dict[str, Any] = {"request_id": _request_id(request_id), "message": message}
        if item_id:
            body["item_id"] = item_id
        return await call(ctx, "POST", f"/v1/web/trips/{trip_id}/messages", json=body)

    @server.tool(name="tripilot_report_issue", annotations=WRITE, title="문제 신고 (지연·휴무·품절)",
                 description="사용자가 겪은 사실을 구조화해서 전한다 — delay(minutes 분 늦음) · closed(가려던 곳이 닫음) · stock_out(products 가 품절, 근처 가게를 찾는다). "
                             "서버가 판정해 일정을 바꾸거나 선택지를 돌려준다. message 는 사용자가 말한 그대로. 사실을 지어내지 않는다.")
    async def report_issue(ctx: Context, trip_id: TripId,
                           type: Annotated[Literal["delay", "closed", "stock_out"], Field(description="delay | closed | stock_out")],
                           message: Annotated[str, Field(min_length=1, description="사용자가 한 말 그대로")],
                           minutes: Annotated[int | None, Field(ge=1, le=1440, description="delay 일 때 늦는 분")] = None,
                           products: Annotated[list[str] | None, Field(description="stock_out 일 때 품절된 상품")] = None,
                           request_id: Annotated[str | None, Field(description="재시도 시 같은 값")] = None) -> dict[str, Any]:
        body = {"request_id": _request_id(request_id), "type": type, "message": message,
                "minutes": minutes, "products": products or []}
        return await call(ctx, "POST", f"/v1/web/trips/{trip_id}/reports", json=body)

    @server.tool(name="tripilot_swap_item", annotations=WRITE, title="다른 안으로 바꾸기",
                 description="일정 항목 하나를 서버가 마련해 둔 다른 안(other_options 의 key)으로 바꾼다. choice 를 생략하면 새 대안을 찾는다. "
                             "바꾼 뒤 판이 오르고 tripilot_rollback 으로 되돌릴 수 있다.")
    async def swap_item(ctx: Context, trip_id: TripId, item_id: Annotated[str, Field(description="바꿀 항목 id")],
                        choice: Annotated[str | None, Field(description="other_options 의 key (없으면 새 대안)")] = None,
                        message: Annotated[str | None, Field(description="사용자가 한 말")] = None,
                        request_id: Annotated[str | None, Field(description="재시도 시 같은 값")] = None) -> dict[str, Any]:
        view = await call(ctx, "GET", f"/v1/web/trips/{trip_id}")
        body = {"request_id": _request_id(request_id), "base_version": view["version"], "choice": choice, "message": message}
        return await call(ctx, "POST", f"/v1/web/trips/{trip_id}/items/{item_id}/alternate", json=body)

    @server.tool(name="tripilot_choose_proposal", annotations=WRITE, title="제안 고르기",
                 description="서버가 물어 둔 제안(tripilot_get_proposals)에 답한다 — option_key 를 주면 그 안으로 바꾸고, 생략하면 원래 일정을 그대로 둔다. 먼저 고른 쪽이 이기고 나중 쪽은 거절된다.")
    async def choose_proposal(ctx: Context, trip_id: TripId, proposal_id: Annotated[str, Field(description="제안 id")],
                              option_key: Annotated[str | None, Field(description="고를 안의 key (없으면 원래대로)")] = None) -> dict[str, Any]:
        return await call(ctx, "POST", f"/v1/web/trips/{trip_id}/proposals/{proposal_id}/choose", json={"key": option_key})

    @server.tool(name="tripilot_rollback", annotations=WRITE, title="되돌리기",
                 description="일정을 옛 판으로 되돌린다(자동·수동 변경 모두). 판 번호는 tripilot_get_trip 의 recent_changes 나 version 에서 본다. 되돌린 것도 새 판으로 기록된다.")
    async def rollback(ctx: Context, trip_id: TripId, to_version: Annotated[int, Field(ge=1, description="되돌아갈 판 번호")],
                       message: Annotated[str | None, Field(description="이유")] = None,
                       request_id: Annotated[str | None, Field(description="재시도 시 같은 값")] = None) -> dict[str, Any]:
        view = await call(ctx, "GET", f"/v1/web/trips/{trip_id}")
        body = {"request_id": _request_id(request_id), "base_version": view["version"], "to_version": to_version, "message": message}
        return await call(ctx, "POST", f"/v1/web/trips/{trip_id}/rollback", json=body)

    @server.tool(name="tripilot_submit_itinerary", annotations=WRITE, title="만든 일정을 검증받고 등록",
                 description="AI 가 만든 일정을 서버가 **판정**(영업시간 · 이동 시간 · 동선 · 일정 밀도)하고 통과하면 사용자의 여행으로 등록한다. 형식은 tripilot_get_itinerary_schema. "
                             "통과 못 하면 어느 항목이 왜 안 되는지(problems)를 돌려주니 고쳐서 다시 보낸다. request_id 는 생략하면 새로 만든다. 등록하면 감시가 시작된다.")
    async def submit_itinerary(ctx: Context, itinerary: Annotated[dict[str, Any], Field(description="일정 JSON (스키마는 tripilot_get_itinerary_schema)")]) -> dict[str, Any]:
        body = dict(itinerary)
        body.pop("customer_id", None)
        body.setdefault("request_id", _request_id(None))
        return await call(ctx, "POST", "/v1/web/trips", json=body)

    @server.tool(name="tripilot_plan_trip", annotations=WRITE, title="서버가 일정 짜기",
                 description="서버의 일정 생성기가 서울 여행을 짜서 판정을 통과한 것만 등록한다. 첫날(start_date) · 일수(1~7) · 인원(1~4) 과 선택 사항 preferences(취향 · 못 먹는 것 등 글)를 준다. "
                             "못 짜면 이유와 완화 조건을 돌려준다(지어낸 일정은 등록하지 않는다). 시간이 걸릴 수 있다(수십 초).")
    async def plan_trip(ctx: Context, start_date: Annotated[str, Field(description="첫날 YYYY-MM-DD")],
                        days: Annotated[int, Field(ge=1, le=7)] = 2, party_size: Annotated[int, Field(ge=1, le=4)] = 2,
                        preferences: Annotated[str | None, Field(description="취향 · 조건을 글로")] = None) -> dict[str, Any]:
        if not _DAY.match(start_date):
            raise ToolError("start_date 는 YYYY-MM-DD 형식이에요")
        intake = await call(ctx, "POST", "/v1/web/trip-intakes", form={"text": (preferences or "").strip()})
        intake_id = intake["intake_id"]
        for _ in range(60):                                      # 읽기가 뒤에서 도는 동안 기다린다(최대 ~2분)
            view = await call(ctx, "GET", f"/v1/web/trip-intakes/{intake_id}")
            if view["status"] == "review":
                break
            if view["status"] == "fatal":
                raise ToolError(f"취향 글을 읽지 못했어요 ({view.get('fatal_code') or '알 수 없음'})")
            await asyncio.sleep(2)
        else:
            raise ToolError("읽는 데 시간이 너무 오래 걸려요 — 잠시 뒤 다시 시도해 주세요")
        plan = {"revision": view["revision"], "start_date": start_date, "days": days, "party_size": party_size,
                "keep_read_items": False}
        return await call(ctx, "POST", f"/v1/web/trip-intakes/{intake_id}/plan", json=plan)

    return server


# ── 앱에 붙이기 ───────────────────────────────────────────────────

class McpGate:
    """연결 단계의 문지기 — `mcp` 모듈 토글 · 사용자 키 확인. 통과한 요청만 MCP 서버가 본다(도구는 키 없는 호출을 못 받는다).

    - 모듈이 꺼져 있으면 **404** (표면이 없는 것처럼)
    - 키가 없거나 틀리면 **401** + `WWW-Authenticate: Bearer` (클라이언트가 「인증 필요」를 알게)
    """

    def __init__(self, inner: Callable[..., Awaitable[None]], *, enabled: Callable[[], bool],
                 authenticate: Callable[[str], bool]) -> None:
        self.inner, self.enabled, self.authenticate = inner, enabled, authenticate

    async def _reply(self, send: Callable[..., Awaitable[None]], status: int, code: str, message: str,
                     headers: list[tuple[bytes, bytes]] | None = None) -> None:
        body = json.dumps({"error": {"code": code, "message": message}}, ensure_ascii=False).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json; charset=utf-8"), *(headers or [])]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Awaitable[Any]],
                       send: Callable[..., Awaitable[None]]) -> None:
        if scope["type"] != "http":
            await self.inner(scope, receive, send)
            return
        try:
            on = bool(self.enabled())
        except Exception:                                    # noqa: BLE001 — 선언을 못 읽으면 닫는다(연 채로 두지 않는다)
            log.warning("mcp gate: module toggle unreadable", exc_info=True)
            on = False
        if not on:
            await self._reply(send, 404, "not_found", "resource not found")
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        key = key_from_headers(headers)
        if not key or not await asyncio.to_thread(self.authenticate, key):
            await self._reply(send, 401, "unauthenticated", "사용자 키가 없거나 맞지 않는다",
                              [(b"www-authenticate", b'Bearer realm="tripilot"')])
            return
        await self.inner(scope, receive, send)


class _AtMountRoot:
    """`/mcp`(끝 슬래시 없음)를 마운트의 `/mcp/` 와 같게 — 클라이언트마다 슬래시를 떼고 부른다(마운트는 슬래시 없는 경로를 307 로 돌려보낸다)."""

    def __init__(self, inner: Callable[..., Awaitable[None]], mount: str) -> None:
        self.inner, self.mount = inner, mount

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Awaitable[Any]],
                       send: Callable[..., Awaitable[None]]) -> None:
        if scope["type"] == "http":
            scope = {**scope, "root_path": (scope.get("root_path") or "") + self.mount, "path": "/", "raw_path": b"/"}
        await self.inner(scope, receive, send)


@dataclass
class McpSurface:
    """고객 API 앱에 붙는 MCP — `asgi` 를 `/mcp` 에 마운트하고, 앱 생명주기 안에서 `lifespan()` 을 연다(무상태 세션 관리자가 돈다).
    `root` 는 슬래시 없는 `/mcp` 용 같은 문(`Route` 로 단다)."""
    server: FastMCP
    asgi: McpGate
    lifespan: Callable[[], Any]
    root: Callable[..., Awaitable[None]]


def build_surface(app_getter: Callable[[], Any], *, enabled: Callable[[], bool], write_enabled: bool) -> McpSurface:
    from app.core import settings as settings_module
    from app.infrastructure.db.session import get_connection

    from app.domains.travel_ops.modules.web_account.web_session import resolve

    server = build_server(AsgiBackend(app_getter), write_enabled=write_enabled)
    inner = server.streamable_http_app()

    def authenticate(raw: str) -> bool:
        tenant = settings_module.get_settings().tenant_id
        with get_connection() as conn, conn.transaction():
            return resolve(conn, tenant_id=tenant, raw=raw) is not None

    @asynccontextmanager
    async def lifespan():
        async with server.session_manager.run():
            yield

    gate = McpGate(inner, enabled=enabled, authenticate=authenticate)
    return McpSurface(server=server, asgi=gate, lifespan=lifespan, root=_AtMountRoot(gate, "/mcp"))


# ── 로컬 stdio 프록시 ─────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="triPilot MCP (로컬 stdio 프록시) — 실제 일은 --base-url 의 서버가 한다")
    parser.add_argument("--base-url", default=os.environ.get("TRIPILOT_BASE_URL", "http://127.0.0.1:8042"))
    parser.add_argument("--write", action="store_true", help="쓰기 도구도 연다(일정을 바꾼다) — 기본은 읽기만")
    args = parser.parse_args(argv)
    if not os.environ.get("TRIPILOT_USER_KEY"):
        parser.error("환경변수 TRIPILOT_USER_KEY(사용자 키)가 필요해요")
    server = build_server(HttpBackend(args.base_url), write_enabled=args.write)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()


__all__ = ["AsgiBackend", "Backend", "Caller", "HttpBackend", "McpApiError", "McpGate", "McpSurface", "build_server",
           "build_surface", "caller_of", "key_from_headers", "outline_of", "trim_trip"]
