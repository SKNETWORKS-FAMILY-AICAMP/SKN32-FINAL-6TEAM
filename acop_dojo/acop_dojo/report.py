"""검증 결과를 문서로 낸다.

손으로 쓰면 카탈로그가 바뀔 때 문서가 먼저 낡는다. 실측 결과에서 바로 뽑는다.
"""
from __future__ import annotations

from pathlib import Path

from . import defects as defects_mod


def gap_report(target_revision: str) -> str:
    catalog = defects_mod.load_catalog()
    entries = catalog.get("entries", {})
    if not entries:
        raise SystemExit("카탈로그가 비었다. 먼저 `acop-dojo defects --rebuild` 를 돌린다.")

    by_id = {d.defect_id: d for d in defects_mod.DEFECTS}
    killed, survived, broken = [], [], []
    for defect_id, entry in sorted(entries.items()):
        gates = entry.get("gates", {})
        if not gates.get("applies") or entry.get("error"):
            broken.append(defect_id)
        elif not gates.get("kills_tests"):
            survived.append(defect_id)
        elif not gates.get("not_collection_error", True):
            broken.append(defect_id)
        else:
            killed.append(defect_id)

    lines = [
        "# final_project_cs 테스트 사각지대 (실측 자동 생성)",
        "",
        f"- 대상 revision: `{target_revision}`",
        f"- 기준선: {catalog.get('baseline', {}).get('summary', '?')}",
        "- 방법: 불변식을 어기는 최소 변경을 임시 사본에 적용하고 전체 테스트를 돌렸다.",
        "- 생성: `acop-dojo report` (원본은 `acop_dojo/acop_dojo/defects/catalog.json`)",
        "- 원본 저장소는 건드리지 않았다. 사본에서만 적용하고 되돌렸다.",
        "",
        "## 결론",
        "",
        f"불변식을 어기는 변경 {len(entries)}건을 넣어 봤다. "
        f"{len(killed)}건은 테스트가 잡았고 **{len(survived)}건은 전체 테스트가 전부 통과했다.**",
    ]
    if survived:
        lines += [
            "잡히지 않은 것은 학습 문제로 쓸 수 없어 발견했고, 그 자체가 검증 공백이다.",
            "",
            "## 잡히지 않은 것 — 테스트가 울지 않는다",
            "",
            "| 불변식 | 바꾼 곳 | 무엇을 바꿨나 |",
            "|---|---|---|",
        ]
        for defect_id in survived:
            defect = by_id.get(defect_id)
            if defect is None:
                continue
            lines.append(f"| {defect.invariant} | `{defect.path}` | {defect.title} |")
    else:
        lines += [
            "**지금은 사각지대가 없다.** 넣어 본 변경이 전부 어딘가에서 잡힌다.",
            "",
            "이 상태를 유지하려면 새 규칙을 만들 때 그 규칙을 어기는 변경도 함께 만들어",
            "게이트에 걸어 본다. 규칙만 늘리고 세는 곳을 안 만들면 다시 벌어진다.",
        ]

    excluded = [(d, by_id[d].excluded) for d in killed
                if d in by_id and getattr(by_id[d], "excluded", "")]
    if excluded:
        lines += ["", "## 잡히지만 학습 문제로는 쓰지 않는 것", "",
                  "게이트는 통과하는데 신호가 안정적이지 않은 것들이다.", ""]
        for defect_id, reason in excluded:
            lines.append(f"- **{defect_id}** — {reason}")

    lines += ["", "## 잡힌 것 — 대조군", "",
              "| 바꾼 곳 | 깨지는 테스트 |", "|---|---|"]
    for defect_id in killed:
        defect = by_id.get(defect_id)
        failed = entries[defect_id].get("failed", [])
        shown = failed[0].split("::")[-1] if failed else "?"
        extra = f" 외 {len(failed) - 1}건" if len(failed) > 1 else ""
        lines.append(f"| `{defect.path}` — {defect.title} | `{shown}`{extra} |")

    if broken:
        lines += ["", "## 문제로 쓸 수 없는 것", "",
                  "적용이 안 되거나, 수집 자체를 깨뜨려 '구조를 배우는 문제'가 되지 않는다.", ""]
        for defect_id in broken:
            lines.append(f"- {defect_id}")

    lines += [
        "",
        "## 재현",
        "",
        "```",
        "cd acop_dojo",
        "python -m acop_dojo defects --rebuild",
        "python -m acop_dojo report",
        "```",
        "",
        "## 남기는 판단",
        "",
        "여기서 테스트를 고치지 않았다. 담당 영역의 검증 설계에 관한 것이라 지시서로",
        "넘기는 편이 맞다. 권한 계열(`app/presentation/security.py`)이 있으면 그쪽이 먼저다 —",
        "권한 경로에 구멍이 나도 테스트가 울지 않는다는 뜻이기 때문이다.",
        "",
    ]
    return "\n".join(lines)


def write(path: Path, target_revision: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(gap_report(target_revision), encoding="utf-8")
    return path
