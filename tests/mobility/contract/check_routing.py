# -*- coding: utf-8 -*-
"""라우팅 점검 — **팀 코어의 실제 registry** 로 돈다. 가짜 판정기라 시간표는 안 든다.

  python tests/mobility/contract/check_routing.py        (팀 venv — pydantic 필요)

무엇을 잠그나 (2026-09-20 · 24번 방)
  ① 분류기 어휘(INTENTS·ISSUE_CODES)를 **소스에서 읽어** 우리 표와 맞춘다 — import 하지 않는다
     (feedback.py 는 settings·openai 까지 끌고 온다). 어휘가 바뀌면 여기서 깨진다.
  ② intent 5종 × mobility_* issue_code 3종 → 기대 capability
  ③ controller 의 두 호출 자리(input_text 있음/없음)가 **같은 값**을 낸다
  ④ 문구에 사건 표식이 있어도 intent 가 아니면 안 갈린다(문구를 안 본다는 결정의 증거)
  ⑤ select_capability 가 내는 값은 전부 manifest 안이다(밖이면 코어가 RegistryError)
  ⑥ 접두 없는 issue_code('other')는 우리한테 안 온다
"""
import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = next((p for p in HERE.parents
            if (p / "final_project_cs" / "app" / "infrastructure" / "travel" / "mobility").is_dir()), None)
if ROOT is None:
    raise SystemExit(f"final_project_cs/app/infrastructure/travel/mobility 를 못 찾았다 (시작: {HERE})")
CS = ROOT / "final_project_cs"
if not (CS / "app" / "core" / "registry.py").exists():
    raise SystemExit(f"팀 코어가 없다: {CS} — develop 을 받은 뒤 돌린다")
sys.path[:0] = [str(CS), str(ROOT)]

from app.application.routing import case_type_of          # noqa: E402
from app.core.registry import RegistryError, TeamRegistry  # noqa: E402
from modules.mobility import team_mobility as T            # noqa: E402

ok = fail = 0
def chk(name, cond, detail=""):
    global ok, fail
    if cond: ok += 1; print(f"  OK   {name}")
    else: fail += 1; print(f"  FAIL {name}" + (f"\n       {detail}" if detail else ""))


def vocab(name):
    """feedback.py 의 `NAME = frozenset({...})` 를 실행 없이 읽는다."""
    tree = ast.parse((CS / "app/modules/travel_ops/feedback.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return {e.value for e in node.value.args[0].elts}
    raise SystemExit(f"feedback.py 에서 {name} 을 못 찾았다")


class _FakeVerifier:
    timetable_built_at = "check_routing"; rules_version = "fake"
    def verify_case(self, *a, **k): return None


INTENTS, ISSUE_CODES = vocab("INTENTS"), vocab("ISSUE_CODES")
OURS = sorted(c for c in ISSUE_CODES if c.startswith(T.CASE_TYPE + "_"))
EXPECT = {i: T.BY_INTENT.get(i, T.CAPS[0]) for i in INTENTS}

print("① 어휘")
chk("BY_INTENT 의 키가 전부 분류기 INTENTS 안", set(T.BY_INTENT) <= INTENTS, str(set(T.BY_INTENT) - INTENTS))
chk("mobility_* issue_code 가 하나 이상", bool(OURS))
chk("'mobility' 라는 intent 는 없다(네임스페이스 매칭에 기댈 수 없는 이유)", T.NS not in INTENTS)

reg = TeamRegistry()
team = T.MobilityTeam(_FakeVerifier())
reg.register(team)

print("② intent × issue_code → capability")
for intent in sorted(INTENTS):
    got = set()
    for code in OURS:
        entry = reg.resolve(case_type=case_type_of(code, fallback=intent), intent=intent)
        got.add(reg.capability_for(entry, intent, input_text="아무 문장"))
    chk(f"{intent:17s} → {EXPECT[intent]}", got == {EXPECT[intent]}, str(got))

print("③ 두 호출 자리 일치 (controller._capability vs ROUTED 이벤트)")
entry = reg.get("mobility")
chk("input_text 있음 == 없음 (5종 전부)",
    all(reg.capability_for(entry, i, input_text="막차를 놓쳤어요") == reg.capability_for(entry, i) for i in INTENTS))

print("④ 문구를 안 본다")
chk("사건 문구 + itinerary_submit → check_route",
    reg.capability_for(entry, "itinerary_submit", input_text="막차를 놓쳤어요 결항") == T.CAPS[0])

print("⑤ 선언 밖 값 없음")
chk("BY_INTENT 값 ⊆ manifest.capabilities", set(T.BY_INTENT.values()) <= set(team.manifest.capabilities))
chk("default_capability 가 선언돼 있다", team.manifest.default_capability == T.CAPS[0])

print("⑥ 접두 없는 코드는 안 온다")
try:
    reg.resolve(case_type=case_type_of("other", fallback="other"), intent="other"); chk("'other' → RegistryError", False)
except RegistryError:
    chk("'other' → RegistryError", True)

print(f"\n{ok}/{ok + fail} 통과")
sys.exit(1 if fail else 0)
