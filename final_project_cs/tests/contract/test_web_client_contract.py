"""웹(`frontend/apps/web`)이 기대하는 서버가 **지금 서버와 같은가** (2026-09-28, ST4F-161 · develop 판을 우리 웹 호출 모양에 맞춤).

★왜 여기 있는가. 웹의 시험(`npm run test:live` — 웹 CI 는 아직 우리 쪽에 없다)은 실제 서버 없이 돈다 — 손으로 만든 mock 서버
  (`tests/live/stub-server.mjs`)를 상대한다. 그래서 서버가 `/v1/web/*` 경로나 설문 모양을 바꾸면
  웹 시험은 **그대로 통과하고 실제 화면만 깨진다.** 이 시험은 웹 소스를 읽어 서버 쪽과 맞춰 본다.
  서버를 바꾼 PR 의 develop 관문에서 바로 붉어지게 하려고 `tests/contract` 에 둔다.

★웹 소스를 문자열로 읽는다(TypeScript 를 실행하지 않는다). 읽어 낸 것이 0건이거나, 경로 문자열은
  있는데 호출로 읽히지 않은 것이 있으면 **실패한다** — 못 읽은 것을 「맞다」로 넘기지 않는다.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, get_args, get_origin

from app import composition
from app.domains.travel_ops.components.planning.survey import SURVEY_VERSION, TripSurvey

WEB = Path(__file__).resolve().parents[2] / "frontend" / "apps" / "web"
LIVE = WEB / "src" / "lib" / "live"
PAYLOAD = WEB / "src" / "features" / "onboarding" / "payload.ts"

#: `api("/v1/web/…", …)` · `api<T>(`…`, …)` · `openApi(` · `streamApi(` · `send(`${API_BASE}/v1/web/…`, …)` — 첫 인자가 경로인 호출
_CALL = re.compile(r"\b(?:api|openApi|streamApi|send)\s*(?:<[^()]*?>)?\(\s*([`\"])(?:\$\{API_BASE\})?(/v1/web/[^`\"]*)\1")
#: `fetch(`${API_BASE}/v1/web/…`, …)` — 실시간(SSE) 줄기는 `api` 를 거치지 않고 직접 부른다
_FETCH = re.compile(r"\bfetch\(\s*`\$\{API_BASE\}(/v1/web/[^`]*)`")
#: `const base = (id: string) => `/v1/web/trip-intakes/${…}`` 와 `api(`${base(id)}/candidates…`)` — 앞머리를 도우미로 빼 둔 모양
_BASE_DEF = re.compile(r"\bconst base\s*=\s*\(\w+:\s*string\)\s*=>\s*`(/v1/web/[^`]*)`")
_BASE_CALL = re.compile(r"\bapi\s*(?:<[^()]*?>)?\(\s*`\$\{base\([^)]*\)\}([^`]*)`")
#: 호출이든 아니든, 경로로 시작하는 문자열 — 호출로 읽히지 않은 것이 남았는지 세는 데 쓴다
_LITERAL = re.compile(r"[`\"](?:\$\{API_BASE\})?/v1/web/[a-z]")
_METHOD = re.compile(r"method:\s*\"([A-Z]+)\"")

#: 웹은 부르는데 서버에 아직 없는 경로 — **이유와 함께** 적는다. 서버에 생기면 이 시험이 「목록에서 빼라」고 실패한다(목록이 낡지 않게).
#:   `[2026-10-05]` 위치 수집 화면(웹 먼저) — 서버 요청서 「동의 기록 · 위치 수집」 대기. 서버가 만들면 여기서 뺀다.
PENDING_ON_SERVER: dict[tuple[str, str], str] = {
    ("POST", "/v1/web/trips/{}/location"): "위치 수집 — 서버 쪽 대기",
    ("DELETE", "/v1/web/trips/{}/location"): "위치 수집 — 서버 쪽 대기",
    ("GET", "/v1/web/trips/{}/location/stops"): "위치 수집 — 서버 쪽 대기",
}


def _code_lines(text: str) -> str:
    """주석 줄(`//` · `/*` · `*` 로 시작)을 뺀다. 주석에 적힌 경로를 호출로 세지 않게."""
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith(("//", "/*", "*")))


def _call_end(text: str, start: int) -> int:
    """`start` 는 호출 괄호 안. 그 호출을 닫는 `)` 바로 뒤 위치 — 문자열 안의 괄호는 세지 않는다."""
    depth, index, quote = 1, start, None
    while depth:
        char = text[index]
        if quote:
            if char == quote:
                quote = None
        elif char in "`\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        index += 1
    return index


def _shape(path: str) -> str:
    """경로 변수는 `{}` 로 맞추고, 쿼리(`?…` 또는 글자 바로 뒤에 붙은 `${…}`)는 뗀다."""
    path = path.split("?")[0]
    path = re.sub(r"(?<=[a-z-])\$\{[^}]*\}$", "", path)
    return re.sub(r"\$\{[^}]*\}", "{}", path)


def _method(code: str, start: int, end: int) -> str:
    """호출 안의 `method: "…"`. 없고 `json(` 도우미를 쓰면 POST. 요청 설정을 변수로 넘겼으면 메서드를 모르니 `*`(경로만 맞춘다)."""
    found = _METHOD.search(code, start, end)
    if found:
        return found.group(1)
    segment = code[start:end]
    if re.search(r"\bjson\(", segment):
        return "POST"
    return "*" if re.search(r",\s*language\s*,\s*[A-Za-z_]\w*\s*\)$", segment.rstrip()) else "GET"


def _web_calls() -> set[tuple[str, str]]:
    """웹이 부르는 (메서드, 경로). 단위 시험(`*.test.ts`)과 시험용 흉내 도구(`*-kit.ts`)는 뺀다(가짜 주소가 있다)."""
    calls: set[tuple[str, str]] = set()
    unread: list[str] = []
    for path in sorted(LIVE.glob("*.ts")):
        if path.name.endswith((".test.ts", "-kit.ts")):
            continue
        code = _code_lines(path.read_text(encoding="utf-8"))
        seen = len(_BASE_DEF.findall(code))
        for pattern, group in ((_CALL, 2), (_FETCH, 1)):
            for match in pattern.finditer(code):
                seen += 1
                calls.add((_method(code, match.end(), _call_end(code, match.end())), _shape(match.group(group))))
        base = _BASE_DEF.search(code)
        if base:
            for match in _BASE_CALL.finditer(code):
                calls.add((_method(code, match.end(), _call_end(code, match.end())), _shape(base.group(1) + match.group(1))))
        if len(_LITERAL.findall(code)) != seen:
            unread.append(path.name)
    assert not unread, (
        f"경로 문자열은 있는데 호출로 읽지 못한 파일: {unread}. 새 호출 모양이면 이 시험의 `_CALL` · `_FETCH` 를 넓힌다.")
    return calls


def _server_routes() -> set[tuple[str, str]]:
    """조립이 실제로 붙이는 도메인 라우터의 (메서드, 경로)."""
    return {(method, re.sub(r"\{[^}]*\}", "{}", route.path))
            for router in composition.build_domain_routers()
            for route in router.routes
            for method in getattr(route, "methods", None) or ()}


def _on_server(call: tuple[str, str], routes: set[tuple[str, str]]) -> bool:
    method, path = call
    return (method, path) in routes if method != "*" else any(p == path for _, p in routes)


def test_the_server_still_has_every_path_the_web_calls():
    calls = _web_calls()
    assert calls, f"{LIVE} 에서 서버 호출을 하나도 읽지 못했다 — 웹 파일이 옮겨졌는지 본다."
    routes = _server_routes()
    missing = sorted(call for call in calls if not _on_server(call, routes) and call not in PENDING_ON_SERVER)
    assert not missing, (
        f"웹이 부르는데 서버에 없는 경로: {missing}. 서버에서 없앴거나 바꿨다면 웹(`src/lib/live/`)도 함께 고친다. "
        "서버 쪽을 기다리는 중이면 `PENDING_ON_SERVER` 에 이유와 함께 적는다.")


def test_the_pending_list_does_not_go_stale():
    """서버에 이미 생긴 경로가 「대기」 목록에 남아 있으면 실패한다 — 그래야 목록이 거짓으로 남지 않는다."""
    routes = _server_routes()
    done = sorted(call for call in PENDING_ON_SERVER if _on_server(call, routes))
    assert not done, f"서버에 이미 있다 — `PENDING_ON_SERVER` 에서 뺀다: {done}"
    unused = sorted(call for call in PENDING_ON_SERVER if call not in _web_calls())
    assert not unused, f"웹이 더는 부르지 않는다 — `PENDING_ON_SERVER` 에서 뺀다: {unused}"


# ── 설문(`constraints.survey`) ─────────────────────────────────────────────


def _payload() -> str:
    return PAYLOAD.read_text(encoding="utf-8")


def _web_schema_line(field: str) -> str:
    """`tripSurveySchema` 안의 `<field>: z.…` 한 줄."""
    match = re.search(rf"^\s*{field}:\s*z\..*$", _payload(), re.MULTILINE)
    assert match, f"payload.ts 의 tripSurveySchema 에서 `{field}` 를 찾지 못했다"
    return match.group(0)


def _enums(text: str) -> list[set[str]]:
    """`z.enum([...])` 마다 값 묶음 하나."""
    return [set(re.findall(r"\"([^\"]+)\"", body)) for body in re.findall(r"z\.enum\(\[([^\]]*)\]\)", text)]


def _literal(tp) -> set[str]:
    """`Literal[...]` 의 값. `X | None` · `list[X]` 처럼 하나를 감싼 타입이면 안쪽을 본다."""
    if get_origin(tp) is Literal:
        return set(get_args(tp))
    [inner] = [arg for arg in get_args(tp) if arg is not type(None)]
    return _literal(inner)


def _server(field: str):
    return TripSurvey.model_fields[field].annotation


def test_the_web_speaks_the_servers_survey_version():
    [web] = re.findall(r"SURVEY_VERSION\s*=\s*\"([^\"]+)\"", _payload())
    assert {web} == {SURVEY_VERSION} == _literal(_server("version")), (
        f"웹 설문 판 {web!r} · 서버 {SURVEY_VERSION!r} — 판이 다르면 서버가 422 로 거절한다.")


def test_every_survey_field_the_web_can_send_is_one_the_server_accepts():
    """★서버 `TripSurvey` 는 `extra="forbid"` — 모르는 칸이 하나라도 있으면 등록 전체가 422 다."""
    block = re.search(r"tripSurveySchema\s*=\s*z\.strictObject\(\{(.*?)\n\}\)", _payload(), re.DOTALL)
    assert block, "payload.ts 에서 tripSurveySchema 를 찾지 못했다"
    web = set(re.findall(r"^\s*(\w+):", block.group(1), re.MULTILINE))
    assert web, "tripSurveySchema 에서 칸을 하나도 읽지 못했다"
    unknown = sorted(web - set(TripSurvey.model_fields))
    assert not unknown, f"웹은 보낼 수 있는데 서버가 모르는 칸: {unknown}"


def test_every_survey_choice_the_web_can_send_is_one_the_server_accepts():
    """웹이 보낼 수 있는 값 ⊆ 서버가 받는 값. 서버가 값을 더 받는 것은 괜찮다(웹이 아직 안 쓸 뿐)."""
    [area] = _enums(re.search(r"const area\s*=.*$", _payload(), re.MULTILINE).group(0))
    [on_disruption] = _enums(_web_schema_line("on_disruption"))
    [pace] = _enums(_web_schema_line("pace"))
    place, choice = _enums(_web_schema_line("indoor_outdoor"))
    indoor_key, indoor_value = get_args(_server("indoor_outdoor"))
    details_key, _ = get_args(_server("priority_details"))
    pairs = {
        "priority": (area, _literal(_server("priority"))),
        "priority_details 의 키": (area, _literal(details_key)),
        "on_disruption": (on_disruption, _literal(_server("on_disruption"))),
        "pace": (pace, _literal(_server("pace"))),
        "indoor_outdoor 의 키": (place, _literal(indoor_key)),
        "indoor_outdoor 의 값": (choice, _literal(indoor_value)),
    }
    assert all(web for web, _ in pairs.values()), f"payload.ts 에서 값을 읽지 못한 칸이 있다: {pairs}"
    refused = {name: sorted(web - server) for name, (web, server) in pairs.items() if web - server}
    assert not refused, f"웹은 보내는데 서버가 거절하는 값: {refused}"
