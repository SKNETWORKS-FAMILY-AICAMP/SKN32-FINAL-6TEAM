"""묻기. 모든 문제가 여기를 거친다 — 난이도·힌트·보기 전환을 한곳에서 다룬다.

난이도 셋
  쉬움    보기가 있는 문제는 처음부터 보기로 낸다. 힌트를 쓸 수 있다.
  보통    먼저 직접 답한다. 막히면 `모르겠다` 로 보기(4지선다)로 바꾼다. 힌트를 쓸 수 있다.
  어려움  힌트도 보기 전환도 없다.

어느 질문에서든 `힌트` 를 치면 힌트가 한 단계씩 열린다(최대 셋: 방향 → 좁히기 → 거의 답).
보기 문제의 마지막 힌트는 오답 둘을 지운다.

도움을 받은 사실은 남긴다. 힌트를 보고 맞힌 것과 혼자 맞힌 것을 한 숫자로 섞으면
기록을 보고 자기가 어디쯤인지 알 수 없다. 그래서 문제마다 힌트 수와 보기 전환 여부를 적고,
단계 기록에 합계를 싣는다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Sequence

from . import progress

LEVELS = {"쉬움": "easy", "보통": "normal", "어려움": "hard"}
NAMES = {v: k for k, v in LEVELS.items()}
HINT_WORDS = {"?", "힌트", "hint", "h", "ㅎ"}
GIVEUP_WORDS = {"모르겠다", "모름", "몰라", "보기", "pass", "모르겠어"}


def level() -> str:
    """지금 난이도(easy · normal · hard). 환경변수가 진행 파일보다 앞선다."""
    override = os.environ.get("ACOP_DOJO_LEVEL", "").strip()
    if override:
        return LEVELS.get(override, override)
    return progress.load().get("settings", {}).get("level", "normal")


def set_level(name: str) -> str:
    value = LEVELS.get(name, name)
    if value not in NAMES:
        raise SystemExit(f"난이도는 {', '.join(LEVELS)} 중 하나다. 받은 값: {name}")
    data = progress.load()
    data.setdefault("settings", {})["level"] = value
    progress.save(data)
    return value


@dataclass
class Answer:
    text: str = ""
    index: int | None = None
    hints: int = 0
    via_choices: bool = False

    @property
    def helped(self) -> bool:
        return self.hints > 0 or self.via_choices


@dataclass
class Tally:
    """한 판(단계) 동안 받은 도움을 센다. 단계 기록에 그대로 싣는다."""

    asked: int = 0
    hints: int = 0
    via_choices: int = 0
    answers: list[Answer] = field(default_factory=list)

    def add(self, answer: Answer) -> Answer:
        self.asked += 1
        self.hints += answer.hints
        self.via_choices += int(answer.via_choices)
        self.answers.append(answer)
        return answer

    def detail(self) -> dict[str, object]:
        return {"level": level(), "asked": self.asked, "hints_used": self.hints,
                "answered_with_choices": self.via_choices}

    def summary(self) -> str:
        if not self.hints and not self.via_choices:
            return f"도움 없이 답했다. (난이도: {NAMES.get(level(), level())})"
        return (f"힌트를 {self.hints}번 썼고, {self.via_choices}개 문제를 보기로 바꿨다. "
                f"(난이도 {NAMES.get(level(), level())})")


def _read(prompt: str) -> str:
    return input(prompt).strip()


def _show_hint(hints: Sequence[str], used: int, total: int | None = None) -> int:
    """다음 힌트를 연다. total 은 이 문제에 있는 힌트 전체 수다(오답 지우기까지 센다)."""
    if level() == "hard":
        print("  어려움 난이도에서는 힌트를 제공하지 않는다.")
        return used
    if used >= len(hints):
        print("  모든 힌트를 확인했다." if hints else "  이 문제에는 힌트가 없다.")
        return used
    print(f"  힌트 {used + 1}/{total or len(hints)}  {hints[used]}")
    return used + 1


def _guide() -> str:
    if level() == "hard":
        return ""
    return "  (막히면 `힌트`를 입력한다.)"


def choice(prompt: str, options: Sequence[str], *, hints: Sequence[str] = (),
           answer_index: int | None = None, letters: bool = False) -> Answer:
    """보기에서 고른다. answer_index 를 주면 마지막 힌트로 오답 둘을 지울 수 있다."""
    shown = list(range(len(options)))
    tiers = list(hints)
    can_eliminate = answer_index is not None and len(options) >= 4 and level() != "hard"
    if can_eliminate:
        tiers.append("__eliminate__")

    def render() -> None:
        for position, index in enumerate(shown):
            mark = chr(97 + position) if letters else str(position + 1)
            print(f"    {mark}  {options[index]}")

    print(f"\n  {prompt}{_guide()}")
    render()
    used = 0
    while True:
        raw = _read("  > ")
        lowered = raw.lower()
        if lowered in HINT_WORDS:
            if used < len(tiers) and tiers[used] == "__eliminate__" and level() != "hard":
                wrong = [i for i in shown if i != answer_index]
                keep = wrong[:1] + [answer_index]
                shown = [i for i in shown if i in keep]
                used += 1
                print(f"  힌트 {used}/{len(tiers)}  오답 두 개를 제외했다.")
                render()
            else:
                used = _show_hint([t for t in tiers if t != "__eliminate__"], used, len(tiers))
            continue
        if letters and raw[:1].isalpha() and 0 <= ord(lowered[0]) - 97 < len(shown):
            index = shown[ord(lowered[0]) - 97]
        elif raw.isdigit() and 1 <= int(raw) <= len(shown):
            index = shown[int(raw) - 1]
        else:
            print("  보기 번호를 입력한다." + ("" if level() == "hard" else " 막히면 `힌트`를 입력한다."))
            continue
        return Answer(text=options[index], index=index, hints=used)


def free(prompt: str, *, hints: Sequence[str] = (),
         fallback: tuple[Sequence[str], int] | None = None) -> Answer:
    """직접 쓴다. 보기(fallback)가 있으면 쉬움에서는 처음부터, 보통에서는 `모르겠다` 로 바꾼다."""
    if fallback and level() == "easy":
        options, right = fallback
        answer = choice(prompt, options, hints=hints, answer_index=right)
        answer.via_choices = True
        return answer
    tip = ""
    if level() != "hard":
        tip = "  (막히면 `힌트`를 입력한다" + (", 답을 모르면 `모르겠다`를 입력한다" if fallback else "") + ".)"
    print(f"\n  {prompt}{tip}")
    used = 0
    while True:
        raw = _read("  > ")
        if raw.lower() in HINT_WORDS:
            used = _show_hint(hints, used)
            continue
        if raw.lower() in GIVEUP_WORDS and fallback and level() != "hard":
            options, right = fallback
            print("  보기 중에서 답을 고른다. 이 문제는 보기를 사용했다고 기록한다.")
            answer = choice("답을 고른다.", options, hints=hints[used:], answer_index=right)
            answer.hints += used
            answer.via_choices = True
            return answer
        return Answer(text=raw, hints=used)


def yes_no(prompt: str, *, hints: Sequence[str] = ()) -> Answer:
    print(f"\n  {prompt} (y/n){_guide()}")
    used = 0
    while True:
        raw = _read("  > ").lower()
        if raw in HINT_WORDS:
            used = _show_hint(hints, used)
            continue
        if raw[:1] in {"y", "n", "예", "아", "ㅇ", "ㄴ"}:
            return Answer(text="y" if raw[:1] in {"y", "예", "ㅇ"} else "n", hints=used)
        print("  y 또는 n을 입력한다.")


# ── 힌트 재료 — 이미 검증된 데이터에서만 뽑는다 ─────────────────────────
LAYER_NAMES = {
    "app/presentation": "입구(presentation: 외부 요청을 받는 영역) 층",
    "app/application": "응용(application: 처리 흐름을 구성하는 영역) 층",
    "app/core": "코어(core: 규칙과 계약을 담는 영역) 층",
    "app/domain": "도메인(domain: 상태와 이벤트를 담는 영역) 층",
    "app/infrastructure": "인프라(infrastructure: DB·메시지·외부 시스템을 연결하는 영역) 층",
    "app/modules": "Team(작업을 수행하는 모듈) 층",
    "app/tools": "도구(tools: Team이 데이터를 읽을 때 거치는 영역) 층",
}


def layer_of(path: str) -> str:
    """경로가 어느 층인지. 경로에 폴더가 없으면(짧은 이름) 파일 이름을 그대로 말한다."""
    for prefix, name in LAYER_NAMES.items():
        if path.startswith(prefix):
            return name
    return f"{path} 파일"


def file_choices(right: str, pool: Sequence[str]) -> tuple[list[str], int]:
    """정답 경로 하나와 다른 실제 경로 셋으로 4지선다를 만든다. 순서는 정답 경로로 정한다(결정적)."""
    others = [p for p in dict.fromkeys(pool) if p != right][:3]
    options = sorted(others + [right])
    return options, options.index(right)
