"""채팅 해석 재생 결과 여러 개를 **같은 정답표 · 같은 채점**으로 나란히 비교한다 (2026-10-15, 6주차 발표 점검 후속).

사용(작업 폴더 루트에서):
  python program/scripts/chat_replay_compare/replay_compare.py datasets/core/chat_probe/2026-10-13_x600_web_chat \
      replay/out_recorded_x600.jsonl replay/out_ft_e4b_final.jsonl replay/out_ft_e4b_20261015_current.jsonl \
      [--detail replay/out_ft_e4b_20261015_current.jsonl] [--show 40]

재생 도구(`replay_inputs.py` · `replay_run.py` · `replay_score.py`)는 `datasets/core/chat_probe/…/scripts/`(git 밖, 이 PC 에만 있음)에 있다.
이 도구는 `replay_score.py` 가 보는 「할 일」에 더해 **고객에게 가장 위험한 것 = 요청과 다른 변경이 실행되는가**를 센다.
- 실행 계열 = 해석이 서버의 검사를 거쳐 최종으로 낸 할 일(`action`)이 apply_change · rollback · redo · report_closed 중 하나.
- 잘못 실행 후보 = **대상 일정을 골라** 실행 계열로 갔는데 ① 정답 할 일이 실행 계열이 아니다 ② 정답 할 일이 apply_change · report_closed 이고 정답 대상과 다른 일정을 골랐다.
  (정답이 reply_choice — 앞 되묻기에 대한 답 — 인 줄은 해석기 혼자로 맞힐 수 없어 뺀다.)
- 엉뚱한 되묻기 = 위와 같은데 대상을 못 골라(none) 서버가 「어느 일정을 바꿀까요?」로 되묻게 되는 것 — 일정은 바뀌지 않는다.
- 「목적지를 말한 변경」(정답이 apply_change · propose_alternatives 이고 destination_text 가 있는 줄) 중 말한 곳을 무시하고 근처 후보로 **바로 바꾸는 길** = 실행 계열인데 해석에 destination_text 가 없다.
정답표는 Claude 하위 작업 3개가 썼다(출제자 편향 — 같은 Claude 계열 점수와 견주면 공정 비교가 아니다). 대화 순서 앞 70% = 개발용, 뒤 30% = 보류용.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from collections import Counter

#: 실행 계열. 2026-10-15 원격(fbf00da9)부터 채팅이 시각 옮기기 · 넣기 · 빼기 · 순서 · 고정도 웹 「일정 수정」과 같은 길로 **실행**한다 — 그 전 재생 결과(옛 코드)에는 이 값들이 없어 영향이 없다.
EXEC = {"apply_change", "rollback", "redo", "report_closed", "change_time", "add_item", "remove_item", "swap_order", "lock_item", "unlock_item", "replace_named"}
#: 정답표는 옛 이름을 쓴다(장소 바꾸기 = apply_change, 고정 = other 로 적힌 줄이 있다) — 실행 계열 안에서 같은 뜻으로 보는 묶음
_SAME_KIND = {"replace_named": "apply_change"}
DEV_SPLIT = 0.7


def load_labels(base: pathlib.Path) -> dict[int, dict]:
    labels = {}
    for path in sorted((base / "replay/labels").glob("batch*.jsonl")):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                labels[int(row["turn"])] = row
    return labels


def load_category(base: pathlib.Path) -> dict[int, str]:
    return {int(r["turn"]): r["category"] for r in csv.DictReader(open(base / "graded.tsv", encoding="utf-8"), delimiter="\t")
            if r["turn"].isdigit()}                       # 화면에서 막혀 서버에 안 닿은 질의는 turn 이 「-」


#: 2026-10-15 에 더한 미지원 할 일 — 정답표에는 둘 다 other 로 적혀 있다(고정 · 여행 설정은 일정 변경이 아니다)
_AS_OTHER = {"change_pin": "other", "edit_trip": "other"}


def model_action(row: dict) -> str | None:
    """서버가 해석을 바꾼 경우(`unsupported` · `scope_guard` · `condition_guard` · `named_destination`)는 모델이 원래 고른 할 일로 잰다 — replay_score.py 와 같다."""
    raw = row.get("raw") or {}
    if raw.get("unsupported"):
        return _AS_OTHER.get(raw["unsupported"], raw["unsupported"])
    for key in ("scope_guard", "condition_guard", "named_destination"):
        if raw.get(key):
            return raw[key].get("blocked_action") if key != "scope_guard" else "change_time"
    return raw.get("action") or row.get("action")


def evaluate(out_path: pathlib.Path, labels: dict[int, dict]):
    turns = sorted(labels)
    cut = turns[int(len(turns) * DEV_SPLIT)]
    rows = [json.loads(line) for line in open(out_path, encoding="utf-8")]
    res = {}
    for split, keep in (("전체", lambda t: True), ("개발용", lambda t: t < cut), ("보류용", lambda t: t >= cut)):
        c, wrong, asks, dest_direct, errors = Counter(), [], [], [], []
        for row in rows:
            t = int(row["turn"])
            gold = labels.get(t)
            if gold is None or not keep(t) or gold["action"] == "reply_choice":
                continue
            c["n"] += 1
            if row.get("error"):
                c["error"] += 1
                errors.append(row)
            c["action_ok"] += model_action(row) == gold["action"]
            eff = row.get("action")
            if eff in EXEC:
                c["exec"] += 1
                kind = _SAME_KIND.get(eff, eff)
                bad = gold["action"] not in EXEC or kind != gold["action"] or (
                    gold.get("target", "none") != "none" and (row.get("target") or "none") != gold["target"])
                if bad and (row.get("target") or "none") != "none":
                    c["wrong_exec"] += 1
                    wrong.append(row)
                elif bad:
                    c["wrong_ask"] += 1
                    asks.append(row)
            if gold.get("destination_text") and gold["action"] in ("apply_change", "propose_alternatives"):
                c["dest_n"] += 1
                if eff in EXEC and not (row.get("raw") or {}).get("destination_text"):
                    c["dest_direct"] += 1
                    dest_direct.append(row)
        res[split] = (c, wrong, asks, dest_direct, errors)
    return res


def main() -> None:
    args = sys.argv[1:]
    detail, show = None, 40
    if "--detail" in args:
        i = args.index("--detail"); detail = args[i + 1]; del args[i:i + 2]
    if "--show" in args:
        i = args.index("--show"); show = int(args[i + 1]); del args[i:i + 2]
    base = pathlib.Path(args[0])
    labels, cats = load_labels(base), load_category(base)
    queries = {}
    for line in open(base / "replay/inputs.jsonl", encoding="utf-8"):
        r = json.loads(line)
        queries[int(r["turn"])] = r["query"]
    for name in args[1:]:
        res = evaluate(base / name, labels)
        print(f"\n== {name}")
        for split, (c, wrong, asks, dest_direct, errors) in res.items():
            pct = lambda a, b: f"{c[a]}/{c[b]} = {100 * c[a] / c[b]:.0f}%" if c[b] else "분모 0"  # noqa: E731
            print(f"  [{split}] 할 일 {pct('action_ok', 'n')} · 실행 계열 {c['exec']}건 중 잘못 실행 후보 {c['wrong_exec']} · 엉뚱한 되묻기 {c['wrong_ask']} · "
                  f"목적지를 말한 변경 {c['dest_n']}건 중 말한 곳 무시하고 바로 바꾸는 길 {c['dest_direct']} · 해석 오류 {c['error']}")
        if detail == name:
            _, wrong, asks, dest_direct, errors = res["전체"]
            print(f"\n  -- 잘못 실행 후보 {len(wrong)}건 (전체)")
            for row in wrong[:show]:
                g = labels[int(row["turn"])]
                print(f"   t{row['turn']} [{cats.get(int(row['turn']), '?')}] 「{queries.get(int(row['turn']), '')[:40]}」 → 해석 {row.get('action')}/{row.get('target')} · 정답 {g['action']}/{g.get('target')}")
            print(f"\n  -- 목적지 무시 후 바로 바꾸는 길 {len(dest_direct)}건")
            for row in dest_direct[:show]:
                g = labels[int(row["turn"])]
                print(f"   t{row['turn']} 「{queries.get(int(row['turn']), '')[:40]}」 → {row.get('action')} · 정답 목적지 「{g['destination_text']}」")
            print(f"\n  -- 해석 오류 {len(errors)}건")
            for row in errors[:show]:
                print(f"   t{row['turn']} 「{queries.get(int(row['turn']), '')[:40]}」 {row['error'][:90]}")


if __name__ == "__main__":
    main()
