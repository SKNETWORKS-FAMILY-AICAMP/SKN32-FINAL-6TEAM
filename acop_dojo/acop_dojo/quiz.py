"""문제 생성기. 코드 전체에서 그때그때 문제를 만든다 — 외워서 넘기는 게임이 되지 않게.

고정 문제는 몇 번 풀면 답을 외운다. 여기서는 대상 저장소의 함수 전부(색인)에서
대상을 골라 문제를 만든다. 정답은 늘 구문 트리나 실행 기록에서 기계로 뽑는다.

유형 여섯
  caller      이 함수를 직접 부르는 쪽은?          (풀 수 있는 정적 호출만)
  callee      이 함수가 안에서 직접 부르는 것은?     (풀 수 있는 정적 호출만)
  identify    이름을 가린 코드 — 어느 함수인가?     (구문 트리)
  guard_exc   이 조건이 참이면 어떤 예외가 나나?     (구문 트리의 if … raise)
  guard_cond  가린 검사 조건을 채운다               (구문 트리 + 조건 변형)
  trace_next  실제 실행에서 이 함수 다음은?         (저장된 실행 기록 — 코드보다 새 것만)

난이도가 바꾸는 것
  쉬움    유형 넷. 오답은 다른 층에서 고른다(지우기 쉽다). 보기로 시작한다. 같은 문제가 다시 나올 수 있다.
  보통    유형 여섯. 오답은 뜻이 가까운 함수 스무 개 가운데서 고른다. 본 문제는 되도록 피한다.
  어려움  오답은 뜻이 가장 가까운 셋이다(임베딩). 한 번 나온 문제는 다시 내지 않는다.
          한 판 안에서는 뜻 묶음(군집)이 겹치지 않게 대상을 고른다.

언어 모델은 힌트 문장만 쓴다(`semantic.describe`). 정답·오답은 만들지 않는다.
"""
from __future__ import annotations

import ast
import itertools
import json
import random
import re
import subprocess
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence

from . import ask, progress, semantic
from . import tracks as tracks_mod
from .codeindex import Guard, Index, Unit, build as build_index
from .config import WORKSPACE_ROOT, target_root

SEPARATOR = "─" * 62
FAMILIES = ("caller", "callee", "identify", "guard_exc", "guard_cond", "trace_next")
FAMILY_TITLES = {
    "caller": "누가 부르나",
    "callee": "무엇을 부르나",
    "identify": "이름을 가린 코드",
    "guard_exc": "어떤 예외가 나나",
    "guard_cond": "검사 조건 채우기",
    "trace_next": "실행 순서",
}
LEVEL_FAMILIES = {
    "easy": ("caller", "callee", "guard_exc", "trace_next"),
    "normal": FAMILIES,
    "hard": FAMILIES,
}
MASK = "□□□"
MAX_SHOWN_LINES = 28
SEEN_LIMIT = 5000
MAX_CALLERS = 8


class LazyHint:
    """보여 줄 때 만드는 힌트. 언어 모델을 부르는 힌트는 쓸 때만 부른다."""

    def __init__(self, make: Callable[[], str]):
        self._make = make
        self._text: str | None = None

    def __str__(self) -> str:
        if self._text is None:
            self._text = self._make()
        return self._text

    def __format__(self, spec: str) -> str:
        return format(str(self), spec)


@dataclass
class Question:
    family: str
    target: str                  # 문제의 정체(기록·중복 판정용) — 정답 보기와 무관하다
    prompt: str
    body: list[str]              # 문제 위에 보여 줄 코드 줄
    options: list[str]
    right: int
    accept: set[str] | None      # 직접 쓰기로 받을 답(소문자 qualname). None 이면 보기만
    hints: list[Any]
    evidence: str                # 정답의 근거(파일:줄 또는 실행 기록)
    path: str                    # 기록용 — 어느 파일에서 나온 문제인가
    checks: dict[str, Any] = field(default_factory=dict)  # 자체 검사용

    @property
    def fingerprint(self) -> str:
        # 정답 보기를 넣지 않는다. 같은 질문에 부르는 쪽만 다른 보기가 나와도 같은 문제다.
        return f"{self.family}|{self.target}"


# ── 재료 ─────────────────────────────────────────────────────────────────
@dataclass
class Material:
    index: Index
    vectors: semantic.Vectors
    units: list[Unit]            # 이 트랙에서 문제 대상으로 쓸 함수
    traces: dict[str, list[dict[str, Any]]]
    rng: random.Random
    level: str
    stale_traces: list[str] = field(default_factory=list)


def _trace_is_fresh(trace_file: Path, paths: Sequence[str], root: Path) -> bool:
    """기록을 뜬 뒤 그 기록이 거친 파일이 바뀌었으면 낡은 것이다.

    git 으로 본다 — 기록 파일보다 나중에 커밋됐거나 지금 커밋 안 된 수정이 있으면 낡았다.
    git 을 못 쓰면 파일 수정 시각으로 본다(체크아웃만 해도 낡았다고 보는 쪽으로 틀린다).
    """
    made = trace_file.stat().st_mtime
    try:
        dirty = subprocess.run(["git", "status", "--porcelain", "--", *paths], cwd=root,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=20, check=True).stdout.strip()
        last = subprocess.run(["git", "log", "-1", "--format=%ct", "--", *paths], cwd=root,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=20, check=True).stdout.strip()
        return not dirty and (not last or int(last) <= made)
    except (OSError, subprocess.SubprocessError, ValueError):
        return all((root / p).stat().st_mtime <= made for p in paths if (root / p).exists())


def _def_name(symbol: str) -> str:
    """기록의 함수 이름에서 def 이름. 안쪽 것(`f.<locals>.<genexpr>`)은 품은 함수(f)로 본다."""
    return symbol.split(".<locals>")[0].split(".")[-1]


def load_traces(track: tracks_mod.Track | None,
                index: Index | None = None) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """(쓸 수 있는 실행 기록, 낡아서 뺀 시나리오)."""
    from . import scenarios as scenarios_mod

    folder = WORKSPACE_ROOT / ".acop_dojo" / "traces"
    # 중지한 시나리오(지워진 커머스 코드)의 기록은 쓰지 않는다
    wanted = set(track.scenarios) if track and track.owns else set(scenarios_mod.SCENARIOS)
    root = target_root()
    out: dict[str, list[dict[str, Any]]] = {}
    stale: list[str] = []
    for path in sorted(folder.glob("*.json")):
        if path.stem not in wanted:
            continue
        try:
            steps = json.loads(path.read_text(encoding="utf-8")).get("steps", [])
        except (json.JSONDecodeError, OSError):
            continue
        # 원래 순서를 그대로 둔다. <locals> 호출도 지우지 않는다 — 지우면 「다음 호출」이 바뀐다.
        seq = [s for s in steps if s.get("path", "").startswith("app/")]
        if len(seq) < 6:
            continue
        paths = sorted({s["path"] for s in seq})
        exists = all((root / p).exists() for p in paths) and (
            index is None or all(_def_name(s["symbol"]) in index.defs(s["path"]) for s in seq))
        if exists and _trace_is_fresh(path, paths, root):
            out[path.stem] = seq
        else:
            stale.append(path.stem)
    return out, stale


def material(*, track_id: str = "all", level: str | None = None, seed: int | None = None,
             allow_ollama: bool = True) -> Material:
    index = build_index()
    track = tracks_mod.get(track_id)
    units = [u for u in index.units if tracks_mod.owns(track, u.path)] or index.units
    vecs = semantic.vectors(index.units, allow_ollama=allow_ollama)
    traces, stale = load_traces(track, index)
    return Material(index=index, vectors=vecs, units=units, traces=traces,
                    rng=random.Random(seed), level=level or ask.level(), stale_traces=stale)


# ── 공통 도구 ────────────────────────────────────────────────────────────
def norm(text: str) -> str:
    """직접 쓴 답을 비교할 모양으로. 경로는 떼고 클래스.메서드 는 남긴다."""
    text = text.strip().strip("`'\" ").replace("()", "").split("  (")[0]
    text = text.split("::")[-1].split("/")[-1].strip()
    return text.lower()


def qual_of(option: str) -> str:
    """보기 문자열에서 이름 부분(클래스.메서드)만. 「이름  (경로)」·「파일::이름」 둘 다."""
    return option.split("  (")[0].split("::")[-1].strip().lower()


def accepted(q: Question) -> tuple[set[str], set[str]]:
    """(온전한 이름으로 받는 답, 짧은 이름으로도 받는 답).

    짧은 이름(메서드 이름만)은 다른 보기와 겹치지 않을 때만 받는다 — `Guardrails.get` 과
    `TeamRegistry.get` 이 함께 있으면 `get` 만으로는 어느 쪽인지 모른다.
    """
    full = set(q.accept or ())
    others = {qual_of(o).split(".")[-1] for i, o in enumerate(q.options) if qual_of(o) not in full}
    short = {a.split(".")[-1] for a in full} - others
    return full, short


def judge(q: Question, text: str) -> bool:
    answer = norm(text)
    full, short = accepted(q)
    return answer in full or answer in short


def label(u: Unit) -> str:
    return f"{u.qualname}  ({u.path})"


def distractors(m: Material, anchor: str, pool: Sequence[Unit], k: int = 3) -> list[Unit]:
    """오답 고르기. 난이도가 높을수록 anchor 와 뜻이 가까운 것을 고른다."""
    pool = list(pool)
    if len(pool) < k:
        return []
    if m.level == "hard":
        return m.vectors.nearest(anchor, pool, k)
    if m.level == "normal":
        near = m.vectors.nearest(anchor, pool, 20)
        return m.rng.sample(near, k) if len(near) >= k else []
    # 쉬움 — 다른 층에서 고른다. 층이 다르면 지우기 쉽다
    anchor_unit = m.index.by_uid().get(anchor)
    far = [u for u in pool if anchor_unit is None or u.layer != anchor_unit.layer]
    return m.rng.sample(far, k) if len(far) >= k else m.rng.sample(pool, k)


def shuffled(m: Material, right: str, wrong: Sequence[str]) -> tuple[list[str], int]:
    options = [right, *wrong]
    m.rng.shuffle(options)
    return options, options.index(right)


def window(source: str, focus_line: int | None = None) -> list[str]:
    lines = source.splitlines()
    if len(lines) <= MAX_SHOWN_LINES:
        return lines
    if focus_line is None:
        return lines[:MAX_SHOWN_LINES] + ["    …"]
    start = max(0, focus_line - MAX_SHOWN_LINES // 2)
    end = min(len(lines), start + MAX_SHOWN_LINES)
    return (["    …"] if start else []) + lines[start:end] + (["    …"] if end < len(lines) else [])


def strip_docstring(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    func = tree.body[0] if tree.body else None
    if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)) or not func.body:
        return source
    first = func.body[0]
    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
            and isinstance(first.value.value, str):
        lines = source.splitlines()
        del lines[first.lineno - 1:first.end_lineno]
        return "\n".join(lines)
    return source


def mask_name(text: str, name: str) -> str:
    """이름을 가린다. 네 글자 이상이면 더 긴 이름 속에 든 것도 가린다
    (`_capability_state` 가 남아 `_capability` 를 알려 주던 것 — 2026-09-24 코덱스 재점검)."""
    pattern = re.escape(name) if len(name) >= 4 else rf"\b{re.escape(name)}\b"
    return re.sub(pattern, MASK, text)


def name_visible(text: str, name: str) -> bool:
    pattern = re.escape(name) if len(name) >= 4 else rf"\b{re.escape(name)}\b"
    return re.search(pattern, text) is not None


def describe_hint(u: Unit, also: Sequence[str] = ()) -> LazyHint:
    def make() -> str:
        sentence, source = semantic.describe(u)
        for name in also:                       # 정답 예외 이름 같은 것도 가린다
            sentence = re.sub(re.escape(name), "□□", sentence, flags=re.IGNORECASE)
        return f"이 함수가 하는 일: {sentence}  [{source}가 쓴 설명]"
    return LazyHint(make)


def prefix_hint(name: str) -> str:
    return f"이름은 `{name[:max(2, len(name) // 3)]}`로 시작한다."


# ── 유형별 생성 ──────────────────────────────────────────────────────────
def gen_caller(m: Material, target: Unit) -> Question | None:
    callers = m.index.callers_of(target)
    if not callers or len(callers) > MAX_CALLERS:
        return None
    truth = m.rng.choice(callers)
    caller_ids = {c.uid for c in callers}
    # 이름으로라도 target 을 부르는 함수는 오답에서 뺀다(못 푼 호출일 수 있다)
    caller_names = {c.name for c in callers}
    # 이름으로라도 target 을 부르는 함수, 부르는 쪽과 이름이 같은 함수(직접 쓰기에서 구별 못 함)는 뺀다
    pool = [u for u in m.index.units if u.uid not in caller_ids and u.uid != target.uid
            and target.name not in u.mentions and u.name not in caller_names]
    wrong = distractors(m, truth.uid, pool)
    if len(wrong) < 3:
        return None
    options, right = shuffled(m, label(truth), [label(u) for u in wrong])
    return Question(
        family="caller", target=target.uid, path=target.path,
        prompt=f"`{target.qualname}` 를 직접 부르는 함수를 쓴다.",
        body=[f"  {target.path}:{target.line}", f"    {target.signature}"],
        options=options, right=right, accept={c.qualname.lower() for c in callers},
        hints=[f"부르는 쪽 하나는 {ask.layer_of(truth.path)}에 있다.",
               f"그 파일은 {truth.path}다.", prefix_hint(truth.name)],
        evidence=f"{truth.path}:{truth.line} `{truth.qualname}` 안에서 `{target.name}(…)` 을 부른다."
                 + (f" 부르는 쪽은 모두 {len(callers)}곳이다: "
                    + ", ".join(f"`{c.qualname}`" for c in callers) if len(callers) > 1 else ""),
        checks={"callers": sorted(caller_ids), "wrong": [u.uid for u in wrong],
                "truth": truth.uid, "truth_option": label(truth)})


def gen_callee(m: Material, target: Unit) -> Question | None:
    callees = m.index.callees_of(target)
    if len(callees) < 2:
        return None
    truth = m.rng.choice(callees)
    callee_ids = {c.uid for c in callees}
    pool = [u for u in m.index.units if u.uid not in callee_ids and u.uid != target.uid
            and u.name not in target.mentions]
    wrong = distractors(m, truth.uid, pool)
    if len(wrong) < 3:
        return None
    options, right = shuffled(m, label(truth), [label(u) for u in wrong])
    return Question(
        family="callee", target=target.uid, path=target.path,
        prompt=f"`{target.qualname}` 가 안에서 직접 부르는 저장소 함수를 하나 쓴다.",
        body=[f"  {target.path}:{target.line}", f"    {target.signature}"],
        options=options, right=right, accept={c.qualname.lower() for c in callees},
        hints=[f"하나는 {ask.layer_of(truth.path)}에 있다.", f"그 파일은 {truth.path}다.",
               prefix_hint(truth.name)],
        evidence=f"`{target.qualname}` 본문이 직접 부르는 저장소 함수: "
                 + ", ".join(f"`{c.qualname}`" for c in callees[:6]) + (" …" if len(callees) > 6 else ""),
        checks={"callees": sorted(callee_ids), "wrong": [u.uid for u in wrong],
                "truth": truth.uid, "truth_option": label(truth)})


def gen_identify(m: Material, target: Unit) -> Question | None:
    # `__init__` 같은 특수 메서드는 이름으로 구별되지 않는다
    if len(target.source) < 150 or target.name.startswith("__"):
        return None
    pool = [u for u in m.index.units if u.name != target.name]
    wrong = distractors(m, target.uid, pool)
    if len(wrong) < 3:
        return None
    body = mask_name(strip_docstring(target.source), target.name)
    options, right = shuffled(m, label(target), [label(u) for u in wrong])
    return Question(
        family="identify", target=target.uid, path=target.path,
        prompt=f"이름({MASK})과 설명 글을 가린 코드다. 어느 함수인지 이름을 쓴다.",
        body=["  " + line for line in window(body)],
        options=options, right=right, accept={target.qualname.lower()},
        hints=[f"{ask.layer_of(target.path)}의 {target.path.rsplit('/', 1)[0]}/ 폴더에 있다.",
               describe_hint(target), prefix_hint(target.name)],
        evidence=f"{target.path}:{target.line} `{target.qualname}`",
        checks={"wrong": [u.uid for u in wrong], "truth_option": label(target)})


def _exception_pool(m: Material) -> list[str]:
    return sorted({g.exc for u in m.index.units for g in u.guards})


def gen_guard_exc(m: Material, target: Unit, guard: Guard | None = None) -> Question | None:
    if not target.guards:
        return None
    guard = guard or m.rng.choice(target.guards)
    if len({g.exc for g in target.guards if same_meaning(g.cond, guard.cond)}) > 1:
        return None
    others = [name for name in _exception_pool(m) if name != guard.exc]
    if len(others) < 3:
        return None
    if m.level == "easy":
        wrong = m.rng.sample(others, 3)
    else:
        # 뜻이 가까운 함수들이 던지는 예외를 먼저 쓴다 — 같은 동네의 예외는 헷갈린다
        near = m.vectors.nearest(target.uid, [u for u in m.index.units if u.guards], 25)
        ranked = list(dict.fromkeys(g.exc for u in near for g in u.guards if g.exc != guard.exc))
        ranked += [n for n in others if n not in ranked]
        wrong = ranked[:3] if m.level == "hard" else m.rng.sample(ranked[:8], 3)
    options, right = shuffled(m, guard.exc, wrong)
    rel_line = guard.line - target.line
    return Question(
        family="guard_exc", target=f"{target.uid}#{guard.line}", path=target.path,
        prompt=f"조건 `{guard.cond}` 가 참이면 이 함수는 어떤 예외를 던지나? 예외 이름을 쓴다.",
        body=[f"  {target.path}:{target.line}"] + ["  " + l for l in window(
            re.sub(rf"\b{re.escape(guard.exc)}\b", MASK, target.source), rel_line)],
        options=options, right=right, accept={guard.exc.lower()},
        hints=[describe_hint(target, also=[guard.exc]),
               f"예외 이름은 {len(guard.exc)}글자다.", prefix_hint(guard.exc)],
        evidence=f"{target.path}:{guard.line}  if {guard.cond}: raise {guard.exc}",
        checks={"truth": guard.exc, "wrong": wrong, "truth_option": guard.exc})


# ── 조건 다루기 ──────────────────────────────────────────────────────────
_INVERSE = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In,
            ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.Lt: ast.GtE, ast.GtE: ast.Lt,
            ast.Gt: ast.LtE, ast.LtE: ast.Gt}
_NEIGHBOR = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}
#: 부정 쪽 비교를 긍정 쪽의 not 으로 바꿔 센다 — `a != b` 와 `not a == b` 를 같은 뜻으로 본다
_POSITIVE = {ast.NotEq: ast.Eq, ast.NotIn: ast.In, ast.IsNot: ast.Is, ast.GtE: ast.Lt, ast.LtE: ast.Gt}
MAX_ATOMS = 10


def _truth_table(exprs: Sequence[str]) -> list[tuple[bool, ...]] | None:
    """조건들을 참·거짓 표로. 조건 안의 비교·이름 하나하나를 참/거짓 칸으로 보고 모든 경우를 센다."""
    atoms: dict[str, int] = {}

    def build(n: ast.AST) -> Callable[[tuple[bool, ...]], bool]:
        if isinstance(n, ast.BoolOp):
            parts = [build(v) for v in n.values]
            if isinstance(n.op, ast.And):
                return lambda e: all(p(e) for p in parts)
            return lambda e: any(p(e) for p in parts)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            inner = build(n.operand)
            return lambda e: not inner(e)
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _POSITIVE:
            inner = build(ast.Compare(n.left, [_POSITIVE[type(n.ops[0])]()], n.comparators))
            return lambda e: not inner(e)
        idx = atoms.setdefault(ast.dump(n), len(atoms))
        return lambda e: e[idx]

    try:
        fns = [build(ast.parse(x, mode="eval").body) for x in exprs]
    except SyntaxError:
        return None
    if len(atoms) > MAX_ATOMS:
        return None
    rows = list(itertools.product((False, True), repeat=len(atoms)))
    return [tuple(fn(r) for r in rows) for fn in fns]


def same_meaning(a: str, b: str) -> bool:
    table = _truth_table([a, b])
    if table is None:
        try:
            return ast.dump(ast.parse(a, mode="eval")) == ast.dump(ast.parse(b, mode="eval"))
        except SyntaxError:
            return a == b
    return table[0] == table[1]


def is_constant(cond: str) -> bool:
    """늘 참이거나 늘 거짓인 조건. 보기로 내면 뜻 없는 오답이 된다."""
    table = _truth_table([cond])
    return table is not None and len(set(table[0])) == 1


def mutations(cond: str) -> list[str]:
    """조건을 조금씩 비튼 것들. 뜻이 같거나 늘 참·거짓인 것은 쓰는 쪽(gen)에서 거른다."""
    try:
        tree = ast.parse(cond, mode="eval").body
    except SyntaxError:
        return []
    out: list[str] = []
    if isinstance(tree, ast.UnaryOp) and isinstance(tree.op, ast.Not):
        out.append(ast.unparse(tree.operand))                       # not 을 뗀다
    elif isinstance(tree, ast.Compare) and len(tree.ops) == 1:
        op = type(tree.ops[0])
        if op in _INVERSE:
            out.append(ast.unparse(ast.Compare(tree.left, [_INVERSE[op]()], tree.comparators)))
        if op in _NEIGHBOR:                                         # 경계 하나 차이
            out.append(ast.unparse(ast.Compare(tree.left, [_NEIGHBOR[op]()], tree.comparators)))
    elif isinstance(tree, ast.BoolOp):
        swapped = ast.BoolOp(ast.Or() if isinstance(tree.op, ast.And) else ast.And(), tree.values)
        out.append(ast.unparse(swapped))
        for i, value in enumerate(tree.values):                     # 한 항만 뒤집는다
            flipped = list(tree.values)
            flipped[i] = value.operand if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.Not) \
                else ast.UnaryOp(ast.Not(), value)
            out.append(ast.unparse(ast.BoolOp(tree.op, flipped)))
    else:
        out.append(f"not {cond}" if isinstance(tree, (ast.Name, ast.Attribute, ast.Call, ast.Subscript))
                   else f"not ({cond})")
    return out


def masked_condition(source: str, guard: Guard, first_line: int) -> str | None:
    """소스에서 그 검사의 조건 부분만 가린다. 위치로 바꾸므로 모양이 달라도 정확하다."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    rel = guard.line - first_line + 1
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and node.lineno == rel:
            test = node.test
            lines = source.splitlines(keepends=True)
            offsets = [0]
            for line in lines:
                offsets.append(offsets[-1] + len(line.encode("utf-8")))
            raw = source.encode("utf-8")
            start = offsets[test.lineno - 1] + test.col_offset
            end = offsets[test.end_lineno - 1] + test.end_col_offset
            return (raw[:start] + MASK.encode("utf-8") + raw[end:]).decode("utf-8")
    return None


def _other_tests(source: str, first_line: int, guard_line: int) -> list[str]:
    """같은 함수 안의 다른 조건들(if·while·삼항). 같은 조건이 또 보이면 가려도 소용없다."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    rel = guard_line - first_line + 1
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.IfExp)) and not (isinstance(node, ast.If) and node.lineno == rel):
            out.append(ast.unparse(node.test))
    return out


def _names_in(code: str) -> set[str]:
    try:
        return {n.id for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Name)}
    except SyntaxError:
        return set()


def gen_guard_cond(m: Material, target: Unit, guard: Guard | None = None) -> Question | None:
    if not target.guards:
        return None
    guard = guard or m.rng.choice(target.guards)
    masked = masked_condition(target.source, guard, target.line)
    if masked is None or masked.count(MASK) != 1:
        return None
    if any(same_meaning(t, guard.cond) for t in _other_tests(target.source, target.line, guard.line)):
        return None
    candidates = mutations(guard.cond)
    near = m.vectors.nearest(target.uid, [u for u in m.index.units if u.guards], 15)
    borrowed = [g.cond for u in near for g in u.guards]
    if m.level == "hard":
        # 이 함수에 없는 변수를 쓰는 조건은 이름만 보고 지울 수 있다 — 있는 이름만 쓰는 것을 앞에 둔다
        borrowed.sort(key=lambda c: not _names_in(c) <= _names_in(target.source))
    candidates += borrowed
    wrong: list[str] = []
    for cond in candidates:
        if len(cond) > 90 or is_constant(cond) or same_meaning(cond, guard.cond) \
                or any(same_meaning(cond, w) for w in wrong):
            continue
        wrong.append(cond)
        if len(wrong) == 3:
            break
    if len(wrong) < 3:
        return None
    options, right = shuffled(m, guard.cond, wrong)
    options_shown = [f"if {o}:" for o in options]
    return Question(
        family="guard_cond", target=f"{target.uid}#{guard.line}", path=target.path,
        prompt=f"`{MASK}` 자리에 들어갈 검사 조건을 고른다.",
        body=[f"  {target.path}:{target.line}"] + ["  " + l for l in window(masked, guard.line - target.line)],
        options=options_shown, right=right, accept=None,
        hints=[f"이 검사가 참이면 `{guard.exc}` 를 던진다. 무엇을 막는 검사인지 먼저 읽는다.",
               describe_hint(target)],
        evidence=f"{target.path}:{guard.line}  if {guard.cond}: raise {guard.exc}",
        checks={"truth": guard.cond, "wrong": wrong, "truth_option": f"if {guard.cond}:",
                "masked": masked})


def trace_label(step: dict[str, Any]) -> str:
    return f"{step['path'].rsplit('/', 1)[-1]}::{step['symbol']}"


def trace_spots(seq: list[dict[str, Any]]) -> list[int]:
    """「다음 호출」을 물을 수 있는 자리. 기록 원래 순서를 그대로 쓴다.

    빼는 자리: 안쪽 함수(<locals>)가 끼는 곳, 같은 함수를 연달아 여러 번 부른 곳(repeat) —
    거기서 「다음」은 자기 자신이다 —, 같은 함수가 기록에 두 번 이상 나오는 곳(어느 쪽인지 모른다).
    """
    labels = [trace_label(s) for s in seq]
    spots = []
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        if "<locals>" in a["symbol"] or "<locals>" in b["symbol"]:
            continue
        if a.get("repeat", 1) != 1 or labels.count(labels[i]) != 1 or labels[i + 1] == labels[i]:
            continue
        spots.append(i)
    return spots


def gen_trace_next(m: Material, _: Unit | None = None, *, spot: tuple[str, int] | None = None) -> Question | None:
    if not m.traces:
        return None
    if spot:
        scenario, i = spot
    else:
        scenario = m.rng.choice(sorted(m.traces))
        spots = trace_spots(m.traces[scenario])
        if not spots:
            return None
        i = m.rng.choice(spots)
    seq = m.traces[scenario]
    labels = [trace_label(s) for s in seq]
    truth = labels[i + 1]
    others = [l for l in dict.fromkeys(labels) if l not in (truth, labels[i]) and "<locals>" not in l]
    if len(others) < 3:
        return None
    if m.level == "easy":
        wrong = m.rng.sample(others, 3)
    else:
        # 실행 순서에서 가까운 것일수록 헷갈린다
        by_distance = sorted(others, key=lambda l: min(abs(j - (i + 1)) for j, x in enumerate(labels) if x == l))
        wrong = by_distance[:3] if m.level == "hard" else m.rng.sample(by_distance[:6], 3)
    options, right = shuffled(m, truth, wrong)
    step = seq[i + 1]
    return Question(
        family="trace_next", target=f"trace:{scenario}#{i}", path=seq[i]["path"],
        prompt=f"시나리오 `{scenario}` 를 실제로 돌렸을 때 `{labels[i]}` 다음에 처음 불린 함수를 쓴다.",
        body=[f"  {seq[i]['path']}:{seq[i].get('line', '')}  {seq[i]['symbol']}  (실행 {i + 1}번째)"],
        options=options, right=right, accept={step["symbol"].lower()},
        hints=[f"다음 함수는 {ask.layer_of(step['path'])}에 있다.", f"그 파일은 {step['path']}다.",
               prefix_hint(step["symbol"].split(".")[-1])],
        evidence=f"실행 기록 .acop_dojo/traces/{scenario}.json 의 {i + 2}번째 호출: {step['path']} {step['symbol']}",
        checks={"truth": truth, "scenario": scenario, "at": i, "truth_option": truth,
                "cluster_uid": f"{seq[i]['path']}::{seq[i]['symbol']}"})


GENERATORS: dict[str, Callable[..., Question | None]] = {
    "caller": gen_caller, "callee": gen_callee, "identify": gen_identify,
    "guard_exc": gen_guard_exc, "guard_cond": gen_guard_cond, "trace_next": gen_trace_next,
}


# ── 뽑기 ─────────────────────────────────────────────────────────────────
def _quiz_record() -> dict[str, Any]:
    return progress.load().get("quiz", {})


def draw(m: Material, count: int, *, families: Sequence[str] | None = None,
         seen: set[str] | None = None, attempts: int = 400) -> list[Question]:
    """count 문제를 뽑는다.

    쉬움은 본 문제도 낸다. 보통은 안 본 문제를 먼저 내고 모자라면 본 문제로 채운다.
    어려움은 본 문제를 내지 않고, 한 판 안에서 뜻 묶음이 겹치지 않게 한다.
    """
    families = list(families or LEVEL_FAMILIES[m.level])
    seen = seen if seen is not None else set(_quiz_record().get("seen", []))
    file_counts: dict[str, int] = _quiz_record().get("files", {})
    clusters = m.vectors.clusters(max(4, min(24, len(m.units) // 20))) if m.level != "easy" else {}
    used_clusters: set[int] = set()
    out: list[Question] = []
    fingerprints: set[str] = set()
    passes = (False, True) if m.level == "normal" else ((True,) if m.level == "easy" else (False,))
    for allow_seen in passes:
        for n in range(attempts):
            if len(out) >= count:
                break
            family = families[n % len(families)]
            if family == "trace_next":
                q = gen_trace_next(m)
            else:
                # 아직 적게 나온 파일에서 먼저 고른다
                sample = m.rng.sample(m.units, min(40, len(m.units)))
                sample.sort(key=lambda u: file_counts.get(u.path, 0))
                target = next((u for u in sample if clusters.get(u.uid, -1) not in used_clusters), sample[0])
                q = GENERATORS[family](m, target)
            if q is None or q.fingerprint in fingerprints:
                continue
            if not allow_seen and q.fingerprint in seen:
                continue
            if check(m, q):
                continue
            base = q.checks.get("cluster_uid") or q.target.split("#")[0]
            if base in clusters:
                if m.level == "hard" and clusters[base] in used_clusters:
                    continue
                used_clusters.add(clusters[base])
            fingerprints.add(q.fingerprint)
            out.append(q)
    return out


# ── 자체 검사 ────────────────────────────────────────────────────────────
def _call_pattern(m: Material, caller: Unit, callee: Unit) -> str:
    """caller 소스에서 callee 를 부르는 모양. `import … as 별칭` 으로 가져온 이름도 센다."""
    table = m.index.tables.get(caller.path)
    names = {callee.name} | {local for local, (_, original) in (table.imported.items() if table else [])
                             if original == callee.name}
    return r"\b(" + "|".join(re.escape(n) for n in sorted(names)) + r")\s*\("


def check(m: Material, q: Question) -> list[str]:
    """정답이 정확히 하나인가, 정답이 드러나지 않는가. 문제가 있으면 이유 목록."""
    problems: list[str] = []
    if len(q.options) != 4 or len(set(q.options)) != 4:
        problems.append("보기가 넷이 아니거나 겹친다")
    if not 0 <= q.right < len(q.options):
        return problems + ["정답 번호가 보기 밖이다"]
    if q.options[q.right] != q.checks.get("truth_option"):
        problems.append("정답 번호가 정답 보기를 가리키지 않는다")
    units = m.index.by_uid()
    if q.family == "caller":
        target = units[q.target]
        for uid in q.checks["wrong"]:
            if target.name in units[uid].mentions:
                problems.append(f"오답 {uid} 가 그 이름을 부른다")
        # 따로 확인 — 정답 쪽 소스에 호출 모양이 실제로 있다
        if not re.search(_call_pattern(m, units[q.checks["truth"]], target), units[q.checks["truth"]].source):
            problems.append("정답 쪽 소스에 호출이 보이지 않는다")
    if q.family == "callee":
        target = units[q.target.split("#")[0]]
        for uid in q.checks["wrong"]:
            if uid in q.checks["callees"] or units[uid].name in target.mentions:
                problems.append(f"오답 {uid} 가 실제로 불릴 수 있다")
        if not re.search(_call_pattern(m, target, units[q.checks["truth"]]), target.source):
            problems.append("대상 소스에 정답 호출이 보이지 않는다")
    if q.family == "identify":
        target = units[q.target]
        if any(units[uid].name == target.name for uid in q.checks["wrong"]):
            problems.append("오답에 같은 이름이 있다")
        if any(name_visible(line, target.name) for line in q.body):
            problems.append("가린 코드에 이름이 남았다")
    if q.family == "guard_exc":
        if q.checks["truth"] in q.checks["wrong"]:
            problems.append("오답에 정답 예외가 있다")
        if any(re.search(rf"\b{re.escape(q.checks['truth'])}\b", line) for line in q.body):
            problems.append("코드에 정답 예외가 남았다")
    if q.family == "guard_cond":
        conds = [q.checks["truth"], *q.checks["wrong"]]
        for a in range(len(conds)):
            for b in range(a + 1, len(conds)):
                if same_meaning(conds[a], conds[b]):
                    problems.append("보기 둘이 같은 뜻이다")
        if q.checks["masked"].count(MASK) != 1:
            problems.append("가린 자리가 하나가 아니다")
        if re.search(rf"\b(if|elif|while)\s+{re.escape(q.checks['truth'])}\s*:", q.checks["masked"]):
            problems.append("가린 코드에 같은 조건이 그대로 있다")
    if q.family == "trace_next":
        # 따로 확인 — 디스크의 원래 기록을 다시 읽어 다음 호출을 본다
        raw = json.loads((WORKSPACE_ROOT / ".acop_dojo" / "traces" / f"{q.checks['scenario']}.json")
                         .read_text(encoding="utf-8"))["steps"]
        raw = [s for s in raw if s.get("path", "").startswith("app/")]
        at = q.checks["at"]
        if trace_label(raw[at + 1]) != q.checks["truth"] or raw[at].get("repeat", 1) != 1:
            problems.append("정답이 원래 기록의 다음 호출이 아니다")
    if q.accept is not None:
        full, short = accepted(q)
        for i, option in enumerate(q.options):
            if i != q.right and (qual_of(option) in full or qual_of(option).split(".")[-1] in short):
                problems.append("오답을 직접 쓰면 정답으로 채점된다")
    return problems


def pool_sizes(m: Material) -> dict[str, int]:
    """유형마다 문제를 낼 수 있는 자리 수(분모). 생성기와 같은 조건으로 센다."""
    guards_ok = sum(1 for u in m.units for g in u.guards
                    if len({h.exc for h in u.guards if same_meaning(h.cond, g.cond)}) == 1)
    return {
        "caller": sum(1 for u in m.units if 0 < len(m.index.callers_of(u)) <= MAX_CALLERS),
        "callee": sum(1 for u in m.units if len(m.index.callees_of(u)) >= 2),
        "identify": sum(1 for u in m.units if len(u.source) >= 150 and not u.name.startswith("__")),
        "guard_exc": guards_ok,
        "guard_cond": sum(1 for u in m.units for g in u.guards
                          if not any(same_meaning(t, g.cond) for t in _other_tests(u.source, u.line, g.line))),
        "trace_next": sum(len(trace_spots(seq)) for seq in m.traces.values()),
    }


# ── 묻기 ─────────────────────────────────────────────────────────────────
def pose(q: Question, number: str = "") -> tuple[bool, ask.Answer]:
    """문제 하나를 묻고 맞았는지 돌려준다."""
    print("")
    print(f"  {number}[{FAMILY_TITLES[q.family]}]")
    for line in q.body:
        print(f"  {line}")
    if q.accept is None:
        answer = ask.choice(q.prompt, q.options, hints=q.hints, answer_index=q.right)
        ok = answer.index == q.right
    else:
        answer = ask.free(q.prompt, hints=q.hints, fallback=(q.options, q.right))
        ok = (answer.index == q.right) if answer.via_choices else judge(q, answer.text)
    right = q.options[q.right]
    print(f"  {'맞다.' if ok else '아니다.'}  정답: {right}")
    print(f"  근거: {q.evidence}")
    return ok, answer


def record(results: list[tuple[Question, bool, ask.Answer]], level: str) -> None:
    data = progress.load()
    quiz = data.setdefault("quiz", {})
    seen = quiz.setdefault("seen", [])
    files = quiz.setdefault("files", {})
    fams = quiz.setdefault("families", {})
    for q, ok, answer in results:
        if q.fingerprint not in seen:
            seen.append(q.fingerprint)
        files[q.path] = files.get(q.path, 0) + 1
        f = fams.setdefault(q.family, {"asked": 0, "right_alone": 0, "right_helped": 0})
        f["asked"] += 1
        if ok:
            f["right_helped" if answer.helped else "right_alone"] += 1
    del seen[:-SEEN_LIMIT]
    runs = quiz.setdefault("runs", [])
    runs.append({"at": datetime.now(UTC).isoformat(timespec="seconds"), "level": level,
                 "asked": len(results), "right": sum(ok for _, ok, _ in results),
                 "helped": sum(a.helped for _, _, a in results)})
    del runs[:-50]
    progress.save(data)


def run(*, track_id: str = "all", count: int = 5, family: str | None = None,
        seed: int | None = None) -> int:
    m = material(track_id=track_id, seed=seed)
    track = tracks_mod.get(track_id)
    print("")
    print(f"문제 풀기 · {track.title} · 난이도 {ask.NAMES.get(m.level, m.level)}")
    print("코드 전체에서 그때그때 만든 문제다. 정답은 코드 구문과 실행 기록에서 뽑았다.")
    print(f"  오답 고르기: {m.vectors.source}")
    if m.stale_traces:
        print(f"  코드가 바뀌어 쓰지 않은 실행 기록 {len(m.stale_traces)}개 — 새로 뜨려면 "
              f"python dojo.py quiz refresh")
    print(SEPARATOR)
    questions = draw(m, count, families=[family] if family else None)
    if not questions:
        print("  낼 수 있는 문제가 없다. 어려움에서는 이미 본 문제를 빼므로 다른 트랙이나 난이도로 시도한다.")
        return 1
    tally = ask.Tally()
    results = []
    for i, q in enumerate(questions, 1):
        ok, answer = pose(q, f"{i}/{len(questions)} ")
        tally.add(answer)
        results.append((q, ok, answer))
    record(results, m.level)
    right = sum(ok for _, ok, _ in results)
    alone = sum(ok and not a.helped for _, ok, a in results)
    print("")
    print(SEPARATOR)
    print(f"  {right}/{len(results)} 맞혔다. 도움 없이 맞힌 문제는 {alone}개다.")
    print(f"  {tally.summary()}")
    print("  다시 하면 다른 문제가 나온다.")
    return 0


def refresh(*, track_id: str = "all") -> int:
    """낡은 실행 기록만 골라 다시 뜬다. cs 는 여러 사람이 계속 고치므로 기록은 금방 낡는다.

    DB 가 필요한 시나리오는 DB 가 떠 있어야 뜬다. 실패한 것은 이름과 이유를 적고 넘어간다.
    """
    from . import scenarios as scenarios_mod
    from . import tracer

    index = build_index()
    _, stale = load_traces(tracks_mod.get(track_id), index)
    if not stale:
        print("낡은 실행 기록이 없다. 모든 기록이 지금 코드보다 새것이다.")
        return 0
    print(f"낡은 실행 기록 {len(stale)}개를 다시 뜬다.")
    failed = []
    for sid in stale:
        scenario = scenarios_mod.get(sid)
        out = WORKSPACE_ROOT / ".acop_dojo" / "traces" / f"{sid}.json"
        try:
            trace = tracer.capture(scenario.nodeid, target=target_root(), out_path=out)
            print(f"  [통과] {sid}  실행 지점 {trace['summary']['steps']}개")
        except Exception as exc:  # noqa: BLE001 — 한 시나리오 실패로 나머지를 멈추지 않는다
            failed.append(sid)
            hint = " (DB 가 필요한 시나리오다 — DB 가 떠 있는지 본다)" if scenario.needs_db else ""
            print(f"  [실패] {sid}{hint}: {str(exc).splitlines()[0][:160] if str(exc) else type(exc).__name__}")
    print(f"다시 뜬 기록 {len(stale) - len(failed)}/{len(stale)}개.")
    return 0 if not failed else 1


def selftest(*, per_family: int = 0, track_id: str = "all", allow_ollama: bool = True) -> int:
    """낼 수 있는 자리를 전부(또는 유형마다 per_family 개) 만들어 check() 로 검사한다.

    이 검사가 보는 것: 보기 넷·정답 하나·정답 번호·오답이 정답 조건에 걸리지 않음·가린 것이 새지 않음,
    그리고 정답 쪽 소스에 호출이 실제로 있는지·실행 기록 원본의 다음 호출과 같은지.
    보지 않는 것: 정적으로 못 푸는 호출(동적 호출·상속)로 생기는 관계의 빠짐.
    """
    failed = 0
    base = material(track_id=track_id, seed=0, allow_ollama=allow_ollama)
    print(f"색인: 함수 {len(base.index.units)}개 (대상 트랙 {len(base.units)}개) · "
          f"실행 기록 {len(base.traces)}개 (낡아서 뺀 것 {len(base.stale_traces)}개)")
    print(f"오답 고르기: {base.vectors.source}")
    sizes = pool_sizes(base)
    print("유형별 대상 수(문제를 낼 수 있는 자리):")
    for fam, n in sizes.items():
        print(f"  {fam:<11} {n}")
    for level in ("easy", "normal", "hard"):
        for fam in FAMILIES:
            m = Material(index=base.index, vectors=base.vectors, units=base.units, traces=base.traces,
                         rng=random.Random(zlib.crc32(f"{level}/{fam}".encode())), level=level)
            made, bad = 0, 0
            if fam == "trace_next":
                jobs = [(sc, i) for sc, seq in sorted(m.traces.items()) for i in trace_spots(seq)]
                make = lambda job: gen_trace_next(m, spot=job)          # noqa: E731
            elif fam in ("guard_exc", "guard_cond"):
                # 검사문 하나하나가 문제 자리다 — 함수마다 하나만 보면 나머지는 검사 밖에 남는다
                jobs = [(u, g) for u in m.units for g in u.guards]
                make = lambda job: GENERATORS[fam](m, job[0], job[1])   # noqa: E731
            else:
                jobs = list(m.units)
                make = lambda job: GENERATORS[fam](m, job)              # noqa: E731
            if per_family:
                jobs = m.rng.sample(jobs, min(per_family, len(jobs)))
            for job in jobs:
                q = make(job)
                if q is None:
                    continue
                made += 1
                problems = check(m, q)
                if problems:
                    bad += 1
                    if bad <= 2:
                        print(f"  [실패] {level}/{fam} {q.target}: {problems}")
            failed += bad
            print(f"  {level:<6} {fam:<11} 검사한 문제 {made:>4} · 실패 {bad}")
    print("")
    print("[통과] 만든 문제가 모두 자체 검사를 통과했다(정적으로 못 푸는 호출은 이 검사 밖이다)."
          if not failed else f"[실패] {failed}건")
    return 0 if not failed else 1
