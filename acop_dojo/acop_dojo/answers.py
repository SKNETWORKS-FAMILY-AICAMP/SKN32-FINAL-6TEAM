"""답안 내보내기.

서술 채점을 LLM 에 맡기지 않는다. 이유는 두 가지다. LLM 판정을 단독 합격 기준으로
쓰면 학습자가 모델을 설득해 통과하는 길이 열리고, 채점 신뢰도를 따로 검증해야 한다.

대신 세 가지를 한다.
1. 답안을 구조화된 형식으로 모아 둔다.
2. 무엇을 봐야 하는지 루브릭으로 못 박는다.
3. 사람(동료·멘토)이 그 파일 하나만 보면 검토가 끝나게 한다.

구조화된 peer code review 가 대조군보다 성적이 높았다는 통제실험이 있고,
근거를 설명하는 리뷰가 학습을 돕는다는 사례 연구도 있다.
"""
from __future__ import annotations

from pathlib import Path

from . import progress

#: 이 네 가지가 답에 있는지 본다. 코드가 아니라 사람이 판정한다.
RUBRIC = [
    "왜 그 함수가 그 자리에서 불리는지 말했나 (순서가 아니라 이유)",
    "어떤 상태·권한 전제가 그 경로를 열었는지 짚었나",
    "다른 경로가 왜 불가능한지 말했나 — 정답만 대는 것과 다르다",
    "입력이 하나 바뀌면 어디서 갈라지는지 말했나",
]

STAGE_TITLES = {"0": "해설된 완주", "1": "복원", "2": "대조", "3": "결함", "4": "보스전"}


def build() -> str:
    data = progress.load()
    stages = data.get("stages", {})
    lines = [
        "# 도장 답안 — 동료 검토용",
        "",
        "자동 채점하지 않은 서술 답안이다. 아래 루브릭으로 사람이 본다.",
        "",
        "## 루브릭",
        "",
    ]
    lines += [f"{index}. {item}" for index, item in enumerate(RUBRIC, start=1)]
    lines += ["", "네 항목 중 **셋 이상**이면 통과로 본다. 표현이 서툴러도 내용이 있으면 통과다.",
              "반대로 정답 문장을 그대로 옮겨 적었는데 이유가 없으면 통과가 아니다.", ""]

    lines += ["## 답안", ""]
    found = False
    for stage, entry in sorted(stages.items()):
        explanation = entry.get("explanation")
        if not explanation:
            continue
        found = True
        title = STAGE_TITLES.get(stage, stage)
        lines += [f"### {stage}단계 · {title}", ""]
        if "correct" in entry:
            lines.append(f"- 객관 문제: {entry['correct']}/{entry['of']}")
        if "hits" in entry:
            lines.append(f"- 순서 맞춘 자리: {entry['hits']}/{entry['of']}")
        if entry.get("defect"):
            lines.append(f"- 다룬 결함: `{entry['defect']}`")
        lines += ["", "```", explanation, "```", "",
                  "| 루브릭 | 통과 | 검토자 메모 |", "|---|---|---|"]
        lines += [f"| {item} |  |  |" for item in RUBRIC]
        lines.append("")
    if not found:
        lines += ["아직 제출된 서술 답안이 없다.", ""]

    abilities = data.get("abilities", {})
    if abilities:
        lines += ["## 능력 주장", "",
                  "확정은 실행 증거가 있는 것이고, 잠정은 서술만 있는 것이다.",
                  "잠정을 확정으로 올리는 것은 검토자의 판단이다.", "",
                  "| 능력 | 상태 | 근거 |", "|---|---|---|"]
        for name, info in sorted(abilities.items()):
            state = "확정" if info["state"] == "confirmed" else "잠정"
            lines.append(f"| {name} | {state} | `{info['evidence']}` |")
        lines.append("")
    return "\n".join(lines)


def write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(), encoding="utf-8")
    return path
