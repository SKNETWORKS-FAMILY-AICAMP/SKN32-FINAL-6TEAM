# -*- coding: utf-8 -*-
"""규칙으로 못 옮긴 정답 조건을 **Codex** 가 규칙 언어로 옮기게 한다(재생 시험 4단계 보조). `[2026-10-19]`

    python -m eval.conversation_replay.compile_model --episodes <episodes_v7.jsonl> --targets <targets_v1.jsonl> \
        --out <datasets/.../replay/conditions_v1> [--batch 25] [--jobs 3] [--model gpt-6.1-sol] [--codex-home ~/.codex-alt]

★왜 Codex 인가: 새 대화 구조(D-026)를 설계한 쪽이 Claude 라, 채점 조건을 옮기는 일도 Claude 가 하면 채점이 설계 쪽에 기울 수 있다
  (재생 시험 계획 「정답 작성과 공정성」 — 표적 에피소드도 같은 이유로 Codex 가 썼다). Claude 는 옮긴 결과의 표본을 검수만 한다.
★옮기는 것은 뜻을 바꾸지 않는 **번역**이다 — 조건을 더하거나 빼지 않는다. 옮길 수 없으면 `manual`.
★결과: `<out>/raw/<묶음>.out`(원래 답) · `<out>/compiled.jsonl`(에피소드 한 줄, 모양 검사 통과 여부 포함). 이미 결과가 있는 묶음은 건너뛴다.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile

from . import compile as C
from . import conditions, episodes
from .state import KST, TripView

CODEX = os.environ.get("REPLAY_CODEX", r"C:\Users\playdata2\AppData\Roaming\npm\codex.cmd")

PROMPT = """너는 여행 일정 채점 조건 번역기다. 한국어로 적힌 「끝 상태 조건」과 「금지」를 아래 규칙 언어(JSON)로 옮긴다.
뜻을 바꾸지 않는다. 조건을 더하거나 빼지 않는다. 옮길 수 없거나 확신이 없으면 {{"op": "manual", "why": "짧은 이유"}}.

## 규칙 언어
{spec}

## 옮기는 법
- 금지 문장은 「그 일이 일어나지 않았다」는 **지켜야 할 조건**으로 옮긴다. 예: 「야외 장소로 교체 금지」 → 바뀐 항목의 indoor 가 false 가 아니다
  = {{"op":"field","match":{{"seq":2}},"field":"indoor","ne":false,"must_exist":false}}. 「다른 식당으로 교체 금지」(빼기 요청) → {{"op":"absent","match":{{"seq":3}}}}.
- 「요청 안 한 일정 변경 금지」 · 「다른 일정 그대로」 → {{"op":"unchanged_except","match": targets}}.
- 「저장된 변경과 완료 답변 일치」 · 「저장 없이 완료 주장 금지」 → {{"op":"no_false_done"}}. 「근거 없는 운영시간 · 날씨 · 가격 문장 금지」 · 「조회 없이 단정 금지」 → {{"op":"no_invented_fact"}}.
- 「답에 X 포함」은 답 글에서 찾을 **짧은 낱말**(장소 이름 · 시각 HH:MM · 숫자)로 옮긴다. 같은 뜻의 다른 표기는 any 에 함께 넣는다(예: ["9분","9 분"]).
  봇 답의 표기: 날짜는 「10월 18일」 「10월 18일(토)」 「1일차」, 시각은 「12:00」 「12:00~13:00」. 「10-18」 같은 표기로 찾지 않는다 — 날짜가 꼭 필요하면 any 에 「10월 18일」 「18일」을 넣고, 아니면 장소 이름 · 시각만 쓴다.
  all 에는 꼭 있어야 하는 것만(장소 이름 하나 + 시각 하나 정도). 낱말을 많이 넣으면 맞는 답도 떨어진다.
- 답의 **뜻**을 봐야 하는 조건(「위약금 기준에 직접 답함」 「오후 일정이 없다는 안내」 「다른 궁 후보 1곳 이상 제시」)은
  {{"op":"answer_judge","criterion":"한 문장 판정 기준"}} 로 옮긴다. 일정 상태로 볼 수 있는 부분은 상태 조건으로 따로 옮기고 any_of / all_of 로 묶는다.
- 일정 상태로도 답으로도 판정할 수 없는 것(바깥 사실 확인이 필요한 것: 「궁이 아닌 장소」 「돈까스 파는 곳」)은 manual 로 두되, 종류(kind) · 이름처럼 볼 수 있는 부분만 옮겨 all_of 로 묶는다.
- 항목은 시작 일정의 seq 로 고른다(가능하면 {{"seq": n}}). 시작 일정에 없는 새 항목은 이름 · 종류 · 날짜 · 시각 근처로 고른다.
- 시각 범위가 「무렵 · 쯤」이면 tol 을 15, 「±10분」이면 10, 정확한 시각이면 0~5.
- 「또는」으로 갈리는 조건은 any_of 로.
- 같은 문장이 여러 조건을 말하면 all_of 로 묶는다.
- targets: 이 에피소드에서 고객이 바꾸라고 한 항목(또는 새로 넣을 자리)의 고르기 목록. 질문 · 잡담이면 [].

## 출력
에피소드마다 JSON 한 줄(JSONL). 다른 글 없이 줄만 낸다. 모양:
{{"episode_id": "...", "targets": [M, ...], "end": [{{"text": "원문 그대로", "dsl": 조건}}], "forbidden": [{{"text": "원문 그대로", "dsl": 조건}}]}}
- end · forbidden 에는 아래 「옮길 것」에 있는 문장만, 원문 글자 그대로 text 에 넣는다.

## 에피소드
{body}
"""


def _spec() -> str:
    doc = conditions.__doc__ or ""
    return doc[doc.index("조건 한 개"):].strip()


def _item_line(item: dict) -> str:
    s = (item.get("start") or "")[5:16].replace("T", " ")
    e = (item.get("end") or "")[11:16]
    flags = []
    if item.get("pinned"):
        flags.append("고정")
    if item.get("indoor") is not None:
        flags.append("실내" if item["indoor"] else "야외")
    place = f" · 장소 {item['place']}" if item.get("place") and item.get("place") != item.get("title") else ""
    return f"  seq={item['seq']} {s}~{e} {item['kind']} 「{item['title']}」{place}{(' · ' + ','.join(flags)) if flags else ''}"


def episode_block(ep: dict, compiled: dict) -> str:
    start = TripView.from_dict(ep["start"])
    lines = [f"### {ep['episode_id']} ({ep['goal_type'] or ''})", f"목표: {ep['goal']}", f"지금 시각: {ep['now']}",
             "대본: " + " / ".join(f"「{s['text']}」({s['role']})" for s in ep["script"]), "시작 일정:"]
    lines += [_item_line(i.as_dict()) for i in start.items] or ["  (없음)"]
    lines.append("옮길 것 — 끝 상태:")
    lines += [f"  - {x['text']}" for x in compiled["end"] if x["by"] == "none"] or ["  (없음)"]
    lines.append("옮길 것 — 금지:")
    lines += [f"  - {x['text']}" for x in compiled["forbidden"] if x["by"] == "none"] or ["  (없음)"]
    done = [x for x in compiled["end"] + compiled["forbidden"] if x["by"] == "rule"]
    if done:
        lines.append("이미 규칙으로 옮긴 것(참고): " + " / ".join(x["text"] for x in done))
    return "\n".join(lines)


def run_batch(name: str, eps: list[dict], out: Path, *, model: str, codex_home: str) -> str:
    raw = out / "raw" / f"{name}.out"
    if raw.exists() and raw.stat().st_size > 0:
        return "skip"
    body = "\n\n".join(episode_block(ep, C.compile_episode(ep)) for ep in eps)
    prompt = PROMPT.format(spec=_spec(), body=body)
    (out / "raw" / f"{name}.prompt.md").write_text(prompt, encoding="utf-8")
    with tempfile.TemporaryDirectory() as ws:
        tmp = Path(ws) / "last.txt"
        res = subprocess.run([CODEX, "exec", "--skip-git-repo-check", "-s", "read-only", "-m", model,
                              "-c", "model_reasoning_effort=medium", "-C", ws, "-o", str(tmp), "-"],
                             input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=1800,
                             env={**os.environ, "CODEX_HOME": codex_home})
        stamp = datetime.now(KST).strftime("%H%M%S")
        (out / "raw" / f"{name}.{stamp}.log").write_text((res.stdout or "")[-4000:] + "\n---\n" + (res.stderr or "")[-4000:],
                                                       encoding="utf-8")
        if res.returncode != 0 or not tmp.exists():
            return f"fail rc={res.returncode}"
        raw.write_text(tmp.read_text(encoding="utf-8"), encoding="utf-8")
    return "ok"


def parse_out(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip().strip("`")
        if not line.startswith("{"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def merge(out: Path, eps: list[dict], *, model: str) -> dict:
    got: dict[str, dict] = {}
    for f in sorted((out / "raw").glob("*.out")):
        for row in parse_out(f.read_text(encoding="utf-8")):
            if row.get("episode_id"):
                got[row["episode_id"]] = {**row, "compiled_by": f"codex-{model}", "src": f.name}
    path = out / "compiled.jsonl"
    stats = {"episodes": len(eps), "with_model_row": 0, "invalid_dsl": 0}
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for ep in eps:
            row = got.get(ep["episode_id"])
            if row:
                stats["with_model_row"] += 1
                for part in ("end", "forbidden"):
                    for x in row.get(part) or []:
                        why = C.validate(x.get("dsl"))
                        if why:
                            x["invalid"] = why
                            stats["invalid_dsl"] += 1
                for m in row.get("targets") or []:
                    if C.validate({"op": "present", "match": m}):
                        row["targets_invalid"] = True
            fh.write(json.dumps(row or {"episode_id": ep["episode_id"], "missing": True}, ensure_ascii=False) + "\n")
    comp = [C.compile_episode(ep, got.get(ep["episode_id"])) for ep in eps]
    stats["coverage"] = C.coverage(comp)
    (out / "compiled_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--episodes", type=Path)
    ap.add_argument("--targets", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch", type=int, default=25)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--model", default="gpt-6.1-sol")
    ap.add_argument("--codex-home", default=str(Path.home() / ".codex-alt"))
    ap.add_argument("--only", help="이 이름으로 시작하는 묶음만(시험)")
    ap.add_argument("--merge-only", action="store_true")
    args = ap.parse_args(argv)
    eps = (episodes.load(args.episodes) if args.episodes else []) + (episodes.load(args.targets) if args.targets else [])
    (args.out / "raw").mkdir(parents=True, exist_ok=True)
    if not args.merge_only:
        need = [ep for ep in eps if any(x["by"] == "none" for c in [C.compile_episode(ep)] for x in c["end"] + c["forbidden"])
                or ep.get("goal_type") not in ("질문", "잡담")]
        batches = [(f"{'T' if b[0]['set'] == 'target' else 'R'}{i:03d}", b) for i, b in
                   enumerate(_chunks(need, args.batch))]
        if args.only:
            batches = [x for x in batches if x[0].startswith(args.only)]
        with cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(run_batch, n, b, args.out, model=args.model, codex_home=args.codex_home): n for n, b in batches}
            for fut in cf.as_completed(futs):
                print(futs[fut], fut.result(), flush=True)
    print(json.dumps(merge(args.out, eps, model=args.model), ensure_ascii=False))


def _chunks(eps: list[dict], size: int):
    real = [e for e in eps if e["set"] == "real"]
    tgt = [e for e in eps if e["set"] == "target"]
    for group in (real, tgt):
        for i in range(0, len(group), size):
            yield group[i:i + size]


if __name__ == "__main__":
    main()
