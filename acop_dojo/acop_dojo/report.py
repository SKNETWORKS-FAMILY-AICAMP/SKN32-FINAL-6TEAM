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
    # 분모에서 뺀 것은 잡혔든 아니든 따로 센다. 섞으면 숫자가 모순된다 —
    # 제외한 결함이 "잡히지 않은 것" 과 "잡히지만 안 쓰는 것" 에 동시에 나온다.
    killed, survived, broken, excluded = [], [], [], []
    for defect_id, entry in sorted(entries.items()):
        gates = entry.get("gates", {})
        reason = getattr(by_id.get(defect_id), "excluded", "")
        if reason:
            excluded.append((defect_id, reason))
        elif not gates.get("applies") or entry.get("error"):
            broken.append(defect_id)
        elif not gates.get("kills_tests"):
            survived.append(defect_id)
        elif not gates.get("not_collection_error", True):
            broken.append(defect_id)
        else:
            killed.append(defect_id)
    counted = len(entries) - len(excluded)

    lines = [
        "# final_project_cs — 등록된 결함의 검출 상태 (실측 자동 생성)",
        "",
        f"- 대상 revision: `{target_revision}`",
        f"- 기준선: {catalog.get('baseline', {}).get('summary', '?')}",
        "- 방법: 불변식을 어기는 최소 변경을 임시 사본에 적용하고 전체 테스트를 돌렸다.",
        "- 생성: `acop-dojo report` (원본은 `acop_dojo/acop_dojo/defects/catalog.json`)",
        "- 원본 저장소는 건드리지 않았다. 사본에서만 적용하고 되돌렸다.",
        "",
        "## 결론",
        "",
        f"불변식을 어기는 변경 {len(entries)}건 중 {counted}건을 셌다"
        f"({len(excluded)}건은 분모에서 뺐다 — 아래 참고). "
        f"{len(killed)}건은 테스트가 잡았고 **{len(survived)}건은 전체 테스트가 전부 통과했다.**",
        "",
        "★**이 숫자는 저장소의 테스트 커버리지가 아니다.** 사람이 고른 "
        f"{counted}개 가설에 대한 검출률이다. 카탈로그에 없는 규칙은 여전히 보이지 않는다.",
        "무엇을 말할 수 있고 무엇은 못 하는지는 문서 끝에 적었다.",
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
            "**등록된 활성 결함 중 생존한 것이 없다.** 넣어 본 변경이 전부 어딘가에서 잡힌다.",
            "",
            "이 상태를 유지하려면 새 규칙을 만들 때 그 규칙을 어기는 변경도 함께 만들어",
            "게이트에 걸어 본다. 규칙만 늘리고 세는 곳을 안 만들면 다시 벌어진다.",
        ]

    if excluded:
        lines += ["", "## 분모에서 뺀 것", "",
                  "신호가 안정적이지 않아 세지 않는다. **뺀 것을 밝히지 않으면 0 이라는 수치가",
                  "무엇에 대한 0 인지 알 수 없다.**", ""]
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
        "## 이 숫자로 말할 수 있는 것",
        "",
        "- 등록된 결함이 현재 환경의 전체 테스트에서 적어도 하나의 실패 신호를 낸다.",
        "- 과거에 메운 사례가 다시 무방비로 돌아가는지 감시한다.",
        "- 문서에 적힌 일부 불변식과 테스트 사이에 실행 가능한 추적 관계가 있다.",
        "",
        "## 말할 수 없는 것",
        "",
        "- 등록하지 않은 불변식이 테스트된다는 보장은 없다. **분모는 우리가 고른 것이다.**",
        "- 모든 입력·상태 조합·실행 경로가 검증됐다는 뜻이 아니다.",
        "- 결함을 잡은 테스트가 **올바른 이유로** 실패했다는 보장은 없다.",
        "  무관한 예외나 fixture 실패도 잡은 것으로 집계된다.",
        "- 카탈로그를 사람이 고르는 이상 선택 편향이 남는다. 경계 조건·동시성·상태 조합처럼",
        "  patch 하나로 표현하기 어려운 위험은 분모에 잘 들어오지 않는다.",
        "",
        "그래서 지표를 \"사각지대 0\" 이 아니라 **\"등록된 활성 결함 생존 0건\"** 으로 읽는다.",
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
