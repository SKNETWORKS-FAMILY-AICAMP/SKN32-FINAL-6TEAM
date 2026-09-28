"""구성 revision — 추적성의 뿌리.

★이게 없으면 "마지막 실행 결과" 가 **어느 조립 상태에서 나온 것인지** 알 수 없다.
  검증·평가·샘플 실행이 서로 연결되지 않아 재현성이 사라진다.
  (Codex 교차검증 지적 — `docs/reports/2026-08-17_S-CONSOLE-IA-REVIEW_리포트.md`)

★revision 은 **선언 내용**에서 나온다. 파일 mtime 도 git 커밋도 아니다 —
  같은 내용이면 어느 기계에서 읽어도 같은 값이어야 재현이 성립한다.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import yaml

from acop_basement.core.project_config import load_project_config


@pytest.fixture()
def workdir():
    path = Path(".revision-" + uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


def _write(tmp: Path, mutate=None, *, name="project.yaml") -> Path:
    data = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    if mutate:
        mutate(data)
    path = tmp / name
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_revision_is_present_and_short(workdir):
    config = load_project_config(_write(workdir))
    assert config.revision
    assert len(config.revision) == 12
    assert config.revision.isalnum()


def test_same_content_gives_the_same_revision(workdir):
    a = load_project_config(_write(workdir, name="a.yaml"))
    b = load_project_config(_write(workdir, name="b.yaml"))
    assert a.revision == b.revision, "같은 내용인데 revision 이 다르다"


def test_changing_the_declaration_changes_the_revision(workdir):
    before = load_project_config(_write(workdir, name="before.yaml"))
    after = load_project_config(_write(
        workdir, lambda d: d["modules"]["a2a_executor"].__setitem__("enabled", True),
        name="after.yaml"))
    assert before.revision != after.revision, "선언이 바뀌었는데 revision 이 그대로다"


def test_key_order_does_not_change_the_revision(workdir):
    """★형식만 바꾼 저장이 revision 을 흔들면 안 된다.

    Composer 가 저장하면 yaml 이 재직렬화된다 — 그때마다 revision 이 바뀌면
    "구성이 바뀌었다" 는 신호가 거짓이 된다.
    """
    plain = load_project_config(_write(workdir, name="plain.yaml"))

    data = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    reordered = {"teams": data["teams"], "ports": data["ports"], "modules": data["modules"]}
    path = workdir / "reordered.yaml"
    path.write_text(yaml.safe_dump(reordered, sort_keys=True, allow_unicode=True), encoding="utf-8")

    assert load_project_config(path).revision == plain.revision


def test_team_order_does_change_the_revision(workdir):
    """★반대로 **의미가 있는** 차이는 잡아야 한다.

    Team 순서는 라우팅 우선순위가 될 수 있으므로 다른 구성으로 본다.
    (순서를 무시하고 싶다면 그건 의도적인 결정이어야 하고, 여기서 뒤집힌다.)
    """
    def add_fixture(data):
        data["teams"].append({
            "team_id": "demo_team",
            "active": True,
            "implementation_ref": "tests.unit.test_composition_root:ExtraTeam",
        })

    before = load_project_config(_write(workdir, add_fixture, name="before.yaml"))
    after = load_project_config(_write(
        workdir, lambda d: (add_fixture(d), d.__setitem__("teams", list(reversed(d["teams"]))),),
        name="after.yaml"))
    assert before.revision != after.revision


def test_revision_is_computed_not_taken_from_the_file(workdir):
    """★선언에 적힌 revision 을 믿지 않는다.

    사람이 손으로 적게 두면 내용과 어긋나도 아무도 모른다.
    """
    path = _write(workdir)
    text = path.read_text(encoding="utf-8")
    path.write_text("revision: deadbeefcafe\n" + text, encoding="utf-8")
    # extra='forbid' 라 애초에 거부되거나, 받아들이더라도 계산값이 이긴다
    try:
        config = load_project_config(path)
    except Exception:
        return  # 거부하는 것도 옳은 동작이다
    assert config.revision != "deadbeefcafe"
