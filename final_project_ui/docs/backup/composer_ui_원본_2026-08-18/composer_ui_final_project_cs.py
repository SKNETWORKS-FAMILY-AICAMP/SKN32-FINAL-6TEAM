from __future__ import annotations

from pathlib import Path
from typing import Any, get_args, get_type_hints

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.project_config import (
    DEFAULT_PROJECT_CONFIG,
    PortConfig,
    ProjectConfigError,
    load_project_config,
)
from app.presentation.ui import theme


router = APIRouter(prefix="/ui/composer", tags=["composer-ui"])

# Components are contract infrastructure, not configurable modules.  Keep the
# explanation visible so this page cannot accidentally turn them into toggles.
COMPONENTS = (
    ("Case lifecycle · transition_case()", "상태 변경의 단일 진입점"),
    ("Contract models", "TeamTask/TeamResult 등 Team 계약"),
    ("Team Registry", "capability 해석과 라우팅"),
    ("Context Broker", "컨텍스트 예산과 degraded 신호"),
    ("DB repository / session", "Source of Truth"),
    ("Outbox publisher", "트랜잭션과 이벤트 발행"),
    ("Case service", "run/resume와 중복 실행 방지"),
    ("Controller", "전체 실행 루프"),
    ("Settings / guardrails", "설정과 가드레일의 단일 출처"),
)


#: ★어댑터가 아직 없는 선택지. 여기 있는 것만 고를 수 없다.
#:   `a2a` 는 **여기 없다** — `A2ATeamExecutor` 가 구현돼 있고 테스트를 통과한다.
#:   전에는 a2a 를 이 집합에 넣어 두고 화면에 "a2a (미구현)" 이라고 적었는데,
#:   ★**라벨이 사실과 달랐다.** 운영자가 쓸 수 있는 것을 못 쓰는 것으로 읽는다
#:   (설계 원칙 §3 — 오류 메시지가 사실을 잘못 전하지 않게 한다).
UNIMPLEMENTED_PORTS = frozenset({"redis_streams", "age", "neo4j"})


def _port_selectable(port_name: str, value: str, config: Any) -> bool:
    """고를 수 있는 선택지인가.

    ★`a2a` 는 구현돼 있지만 `a2a_executor` 모듈이 꺼져 있으면 고를 수 없다.
      모듈을 끈 채 port 만 a2a 로 두면 조립이 깨지기 때문이다 — 순서가 있다.
    """
    if value in UNIMPLEMENTED_PORTS:
        return False
    if port_name == "team_executor" and value == "a2a":
        module = config.modules.get("a2a_executor")
        return bool(module and module.enabled)
    return True


def _structure(config: Any) -> str:
    """컴포넌트·모듈 구조도를 **Case 가 실제로 지나가는 순서대로** 그린다.

    ★정적인 그림이 아니라 현재 선언의 투영이다 — 꺼진 모듈은 꺼진 채로 그려진다.
      구조도와 실제 조립이 어긋나면 그림이 거짓말을 한다.
    """
    def on(name: str) -> bool:
        module = config.modules.get(name)
        return bool(module and module.enabled)

    def module(name: str, hint: str = "") -> dict:
        return {"name": name, "kind": "module", "enabled": on(name), "hint": hint}

    def component(name: str, hint: str = "") -> dict:
        return {"name": name, "kind": "component", "enabled": None, "hint": hint}

    active_teams = [t for t in config.teams if t.active]
    team_nodes = [
        {"name": t.team_id, "kind": "instance", "enabled": t.active,
         "hint": "라우팅됨" if t.active else "등록만 됨"}
        for t in config.teams
    ] or [{"name": "Team 없음", "kind": "instance", "enabled": False, "hint": "라우팅 대상이 없다"}]

    executor = config.ports.team_executor
    stages = [
        {"n": "1", "title": "입력", "note": "고객 메시지가 들어온다",
         "nodes": [component("REST /v1", "쓰기 경로"),
                   module("mcp", "개인 AI 접속 · read-only")]},
        {"n": "2", "title": "Case 생성 · 상태 전이",
         "note": "customer_cases 를 직접 UPDATE 하지 않는다 — 여기가 유일한 문이다",
         "nodes": [component("transition_case()", "단일 진입점"),
                   component("case_events", "append-only"),
                   component("Contract models", "extra='forbid'")]},
        {"n": "3", "title": "분류",
         "note": "실패하면 classification_failed 를 남기고 escalated 로 간다",
         "nodes": [component("인라인 분류", "intent · issue · sentiment"),
                   module("voc", "일일 집계 · 급증 탐지")]},
        {"n": "4", "title": "컨텍스트 조립",
         "note": "12,000 토큰 예산. 축소하면 degraded 와 omissions 를 남긴다",
         "nodes": [component("Context Broker", "예산 · 제거 순서"),
                   module("vector_rag", "정책 검색 — 빼면 grounding 0"),
                   module("graph_store", "관계 조회")]},
        {"n": "5", "title": "라우팅",
         "note": "capability 로 Team 을 고른다",
         "nodes": [component("Team Registry", "allowed_tools 강제")]},
        {"n": "6", "title": "실행",
         "note": f"현재 team_executor = {executor}",
         "nodes": [component("TeamExecutorPort", "교체점"),
                   {"name": "LocalTeamExecutor", "kind": "component",
                    "enabled": executor == "local", "hint": "같은 프로세스"},
                   module("a2a_executor", "원격 Team 실행")]},
        {"n": "7", "title": "Agent Team",
         "note": f"개수가 바뀌는 유일한 자리 — 지금 {len(active_teams)}개 라우팅",
         "nodes": team_nodes},
        {"n": "8", "title": "제안 · 승인",
         "note": "Team 은 side effect 를 실행하지 않는다. 제안까지다",
         "nodes": [component("Controller", "실행 루프 · WAIT/RESUME"),
                   component("Case service", "중복 실행 방지"),
                   component("Human Approval", "action:approve scope 필요")]},
        {"n": "9", "title": "발행",
         "note": "전이와 같은 트랜잭션에서 쌓고, 워커가 따로 보낸다",
         "nodes": [component("Outbox", "원자성 · dedupe"),
                   component("Settings / guardrails", "수치의 단일 출처")]},
        {"n": "10", "title": "관측",
         "note": "돌아가는 것을 본다 / 무엇을 조립할지 정한다",
         "nodes": [module("ops_ui", "cases · approvals · voc · admin"),
                   module("composer_ui", "이 화면")]},
    ]
    legend = ("<p class='muted'>"
              "<b>고정</b> = 컴포넌트, 끌 수 없다 · "
              "<b>모듈</b> = 선택, 위에서 켜고 끈다 · "
              "<b>인스턴스</b> = 개수가 바뀐다"
              "</p>")
    return legend + theme.flow(stages)


def _port_help(config: Any) -> str:
    """왜 선택지가 없는지 화면이 말해 준다.

    ★`a2a` 는 모듈을 먼저 켜야 나타난다. 그 순서를 안 적으면
      "구현했다는데 왜 못 고르지" 로 막힌다 — 선택지가 없는 이유가 안 보인다.
    """
    lines = ["어댑터가 있는 선택지만 보여 줍니다. "
             f"아직 없는 것: {', '.join(sorted(UNIMPLEMENTED_PORTS))}."]
    a2a = config.modules.get("a2a_executor")
    if not (a2a and a2a.enabled):
        lines.append("team_executor 의 <code>a2a</code> 는 구현돼 있지만 "
                     "<b>a2a_executor 모듈을 먼저 켜고 저장해야</b> 선택지에 나타납니다.")
    return "".join(f"<p class='muted'>{line}</p>" for line in lines)


def _path(request: Request) -> Path:
    selected = getattr(request.app.state, "project_config_path", DEFAULT_PROJECT_CONFIG)
    return Path(selected)


def _choices() -> dict[str, tuple[str, ...]]:
    hints = get_type_hints(PortConfig)
    return {name: tuple(get_args(hints[name])) for name in hints}


def _read(request: Request):
    return load_project_config(_path(request))


def _form_config(form: Any, module_names: list[str], team_count: int) -> dict[str, Any]:
    modules = {name: {"enabled": form.get(f"module_{name}") == "on"} for name in module_names}
    ports = {name: str(form.get(f"port_{name}", "")) for name in _choices()}
    teams = []
    for index in range(team_count):
        team_id = str(form.get(f"team_id_{index}", "")).strip()
        ref = str(form.get(f"implementation_ref_{index}", "")).strip()
        teams.append({"team_id": team_id, "active": form.get(f"active_{index}") == "on", "implementation_ref": ref})
    return {"modules": modules, "ports": ports, "teams": teams}


def _render(request: Request, config: Any, *, errors: list[str] | None = None, notice: str | None = None) -> HTMLResponse:
    errors = errors or []
    choices = _choices()
    module_rows = "".join(
        f"<label class='choice'><input type='checkbox' name='module_{theme.esc(name)}' "
        f"{'checked' if item.enabled else ''}> {theme.esc(name)}"
        # ★자기 자신을 끄는 체크박스다. 끄면 이 화면이 404 가 되고
        #   **다시 켜려면 config/project.yaml 을 손으로 고쳐야 한다.**
        #   끌 수 있는 것은 의도한 설계지만, 돌아올 길이 없다는 건 적어 줘야 한다.
        + ("<span class='hint'>끄면 이 화면이 404 가 됩니다. 다시 켜려면 "
           "config/project.yaml 을 직접 수정해야 합니다.</span>"
           if name == "composer_ui" else "")
        + "</label>"
        for name, item in config.modules.items()
    )
    port_rows = "".join(
        "<label class='field'>" + theme.esc(name) + " <select name='port_" + theme.esc(name) + "'>" +
        "".join(
            f"<option value='{theme.esc(value)}' "
            f"{'selected' if getattr(config.ports, name) == value else ''}>{theme.esc(value)}</option>"
            for value in values if _port_selectable(name, value, config)) +
        "</select></label>"
        for name, values in choices.items()
    )
    team_rows = "".join(
        f"<tr><td><input name='team_id_{i}' value='{theme.esc(team.team_id)}'></td>"
        f"<td><input name='implementation_ref_{i}' value='{theme.esc(team.implementation_ref)}' size='48'></td>"
        f"<td><input type='checkbox' name='active_{i}' {'checked' if team.active else ''}></td>"
        f"<td>{'운영 라우팅됨' if team.active else '미구현 — 등록되지만 라우팅되지 않음'}</td>"
        f"<td><button name='remove_team' value='{i}' class='danger'>제거</button></td></tr>"
        for i, team in enumerate(config.teams)
    )
    component_rows = "".join(f"<li><b>{theme.esc(name)}</b> — {theme.esc(reason)}. 구성기에서 제거할 수 없습니다.</li>" for name, reason in COMPONENTS)
    messages = ("".join(f"<li>{theme.esc(error)}</li>" for error in errors))
    feedback = theme.card("검증 실패", f"<ul>{messages}</ul><p>검증에 실패한 선언은 저장하지 않았습니다.</p>", tone="critical") if errors else ""
    if notice:
        feedback += theme.card("저장 결과", f"<p>{theme.esc(notice)}</p>", tone="done")
    body = f"""
    {feedback}
    <p class='muted'>제작 단계 구성기. 저장 후 적용하려면 재기동이 필요합니다.</p>
    <form method='post'>
      {theme.collapsible_card('모듈', module_rows, subtitle=f'{len(config.modules)}종')}
      {theme.collapsible_card('Port', port_rows + _port_help(config), subtitle='교체점 3종')}
      {theme.collapsible_card('Team',
          theme.table(('team_id', 'implementation_ref', 'active', '상태', ''), [team_rows])
          + "<p><button name='add_team' value='1'>Team 추가</button></p>",
          subtitle=f'{len(config.teams)}개 등록 · {sum(1 for t in config.teams if t.active)}개 라우팅')}
      <div class='actions'><button name='save' value='1'>검증 후 저장</button></div>
    </form>
    {theme.collapsible_card('구조 — 실행 순서', _structure(config),
        subtitle='지금 선언대로 그린 그림입니다. 꺼진 모듈은 꺼진 채로 표시됩니다')}
    {theme.collapsible_card('컴포넌트 (읽기 전용)', f'<ul>{component_rows}</ul>',
        subtitle=f'{len(COMPONENTS)}종 — 끌 수 없습니다', open_=False)}"""
    return HTMLResponse(theme.page("Project Composer", body, current="/ui/composer",
                                    lede="선언을 검증하고 저장하는 제작 단계 구성기입니다."))


@router.get("", response_class=HTMLResponse)
def composer(request: Request) -> HTMLResponse:
    try:
        config = _read(request)
    except ProjectConfigError as exc:
        return HTMLResponse(theme.page("Project Composer", theme.card("구성 오류", f"<p>{theme.esc(exc)}</p>", tone="critical"), current="/ui/composer"))
    if not config.module_enabled("composer_ui"):
        return HTMLResponse("Not Found", status_code=404)
    return _render(request, config)


@router.post("", response_class=HTMLResponse)
async def composer_post(request: Request) -> HTMLResponse:
    try:
        current = _read(request)
    except ProjectConfigError as exc:
        return HTMLResponse(theme.page("Project Composer", theme.card("구성 오류", f"<p>{theme.esc(exc)}</p>", tone="critical"), current="/ui/composer"))
    if not current.module_enabled("composer_ui"):
        return HTMLResponse("Not Found", status_code=404)
    form = await request.form()
    indexes = [int(key.removeprefix("team_id_")) for key in form if key.startswith("team_id_") and key.removeprefix("team_id_").isdigit()]
    team_count = max(indexes, default=len(current.teams) - 1) + 1
    raw = _form_config(form, list(current.modules), team_count)
    if form.get("remove_team") is not None:
        index = int(form.get("remove_team"))
        raw["teams"].pop(index)
        candidate = current.model_validate({**raw})
        return _render(request, candidate)
    if form.get("add_team") is not None:
        raw["teams"].append({"team_id": "new_team", "active": False, "implementation_ref": "app.modules.placeholder:PlaceholderTeam"})
        candidate = current.model_validate(raw)
        return _render(request, candidate, notice="새 Team은 기본 active=false입니다. 미구현 상태로 등록되지만 라우팅되지 않습니다.")
    try:
        # Write a temporary declaration and use the canonical loader, including
        # schema, duplicate-id, port, and active-team import validation.
        candidate_path = _path(request).with_suffix(".composer.validation.yaml")
        candidate_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
        candidate = load_project_config(candidate_path)
        backup = _path(request).with_suffix(_path(request).suffix + ".bak")
        source = _path(request).read_bytes()
        backup.write_bytes(source)
        _path(request).write_bytes(candidate_path.read_bytes())
        candidate_path.unlink(missing_ok=True)
        return _render(request, candidate, notice="저장했습니다. 변경 사항을 적용하려면 애플리케이션을 재기동하세요.")
    except (ProjectConfigError, OSError, yaml.YAMLError, ValueError) as exc:
        candidate_path = _path(request).with_suffix(".composer.validation.yaml")
        candidate_path.unlink(missing_ok=True)
        return _render(request, current, errors=[str(exc)])
