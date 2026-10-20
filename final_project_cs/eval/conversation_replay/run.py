# -*- coding: utf-8 -*-
"""재생 시험 실행 — 에피소드 묶음을 돌려 결과 · 채점을 쓴다. `[2026-10-19]`

    python -m eval.conversation_replay.run --episodes <episodes_v7.jsonl> --targets <targets_v1.jsonl> \
        --compiled <conditions_v1/compiled.jsonl> --raw-dir <raw/20261019_more> --out <replay/runs/<이름>> \
        --db postgresql+psycopg://…/acop_replay --ollama http://127.0.0.1:<터널> --keys-file <.env.apikeys> \
        --cassette <replay/cassettes/v1.jsonl> --mode record|replay [--customer-model gpt-4.1-mini] [--judge-model gpt-4.1-mini] \
        [--limit 20] [--only <에피소드 id,…>] [--rep 1]

★시험 DB 에만 쓴다(주소에 'replay'). 결과는 `--out` 아래 새 파일 — `results.jsonl`(에피소드 한 줄, 이어 돌리기 가능) · `scores.jsonl` ·
  `lookups.json`(실조회 · 녹화 재생 수 · 예산) · `meta.json`(코드 · 모델 · 설정 · 자료 해시). 정답이 바뀌면(사람 검수 뒤) 같은 명령을 새 `--out` 으로.
★B 반복: 갈린 에피소드는 B 를 2회 돌려 결과(일 끝남 · ① 위반 여부)가 같으면 첫 회를, 다르면 1회 더 돌려 다수결로 고른다.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent


def _sha(path: Path) -> str | None:
    if not path or not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _code_hash() -> dict:
    root = HERE.parents[2]          # 격리 사본 뿌리(BASE_COMMIT.txt 가 있으면 원격 판 해시)
    base = (root / "BASE_COMMIT.txt").read_text().strip() if (root / "BASE_COMMIT.txt").exists() else None
    h = hashlib.sha256()
    for p in sorted(HERE.glob("*.py")):
        h.update(p.read_bytes())
    return {"base_commit": base, "replay_tool_sha": h.hexdigest()[:16]}


def _model_info(ollama: str) -> dict:
    import httpx

    out = {}
    try:
        tags = httpx.get(ollama.rstrip("/") + "/api/tags", timeout=10).json()
        out["tags"] = [{"name": m["name"], "digest": m.get("digest", "")[:16]} for m in tags.get("models", [])]
        out["version"] = httpx.get(ollama.rstrip("/") + "/api/version", timeout=10).json().get("version")
    except Exception as exc:          # noqa: BLE001 — 기록용
        out["error"] = type(exc).__name__
    return out


def _outcome(score: dict) -> tuple:
    return (score["done"]["verdict"], score["wrong_save"]["fail"] > 0, score["false_done"]["fail"] > 0,
            (score.get("condition") or {}).get("verdict") == "fail", score["invented"]["fail"] > 0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--episodes", type=Path)
    ap.add_argument("--targets", type=Path)
    ap.add_argument("--compiled", type=Path)
    ap.add_argument("--raw-dir", type=Path)
    ap.add_argument("--places-file", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--ollama", required=True)
    ap.add_argument("--embed-url")
    ap.add_argument("--mobility-dir", help="이동 계산 자료 폴더(x600 서버는 datasets/mobility/processed) — 절대 경로")
    ap.add_argument("--keys-file", type=Path, action="append", default=[])
    ap.add_argument("--cassette", type=Path, required=True)
    ap.add_argument("--mode", choices=("record", "replay"), default="replay")
    ap.add_argument("--closed", action="store_true", help="녹화에 없는 조회를 실제로 보내지 않는다(완전히 닫힌 재생)")
    ap.add_argument("--customer-model", default="gpt-4.1-mini")
    ap.add_argument("--judge-model")
    ap.add_argument("--seed", type=int, default=20261019)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only")
    ap.add_argument("--set", choices=("real", "target", "all"), default="all")
    ap.add_argument("--rep", default="1")
    ap.add_argument("--b-reps", type=int, default=2)
    ap.add_argument("--paid-budget", type=int, default=600, help="유료 모델(대체 · 팀 답) 호출 상한 — 넘으면 멈춤")
    ap.add_argument("--label", default="검수 전 기준선")
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    from . import runner

    names = runner.prepare_env(db_url=args.db, ollama_url=args.ollama, keys_files=args.keys_file,
                               extra={"ACOP_MOBILITY_DATA_DIR": args.mobility_dir} if args.mobility_dir else None)
    from . import episodes as E
    from . import recorder as R
    from .score import score_episode
    from .seed import RawIndex

    eps = (E.load(args.episodes) if args.episodes else []) + (E.load(args.targets) if args.targets else [])
    cap = E.turn_cap(eps)
    if args.set != "all":
        eps = [e for e in eps if e["set"] == args.set]
    if args.only:
        want = set(args.only.split(","))
        eps = [e for e in eps if e["episode_id"] in want]
    if args.limit:
        eps = eps[: args.limit]
    compiled = runner.load_compiled(args.compiled, eps)
    args.out.mkdir(parents=True, exist_ok=True)
    results_path, scores_path = args.out / "results.jsonl", args.out / "scores.jsonl"
    done_ids = set()
    if results_path.exists():
        done_ids = {json.loads(line)["episode_id"] for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip()}

    from urllib.parse import urlsplit

    llm_host = urlsplit(args.ollama).netloc.lower()
    rules = R.default_rules(llm_hosts={llm_host})
    for r in rules:
        if r.name == "llm_paid":
            r.budget = args.paid_budget
    rec = R.Recorder(cassette=args.cassette, mode=args.mode, rules=rules, live_on_miss=not args.closed,
                     embed_url=args.embed_url).install()
    api_key = os.environ.get("ACOP_OPENAI_API_KEY", "")
    customer = runner.openai_customer(model=args.customer_model, seed=args.seed, api_key=api_key) if args.customer_model else None
    judge = runner.openai_judge(model=args.judge_model, seed=args.seed, api_key=api_key) if args.judge_model else None
    trip_ids = {str(e.get("trip_id")) for e in eps if e.get("trip_id")}
    h = runner.Harness(rec=rec, customer=customer, turn_cap=cap, judge=judge)
    h.raw = RawIndex.load(args.raw_dir, trip_ids, places_file=args.places_file) if args.raw_dir else None
    h.start()
    meta = {"label": args.label, "started_at": datetime.now().isoformat(timespec="seconds"), "argv": [str(a) for a in (argv or sys.argv[1:])
                                                                                                     if "key" not in str(a).lower()],
            "code": _code_hash(), "model": _model_info(args.ollama), "settings": runner.X600_LIKE, "keys_loaded": names,
            "episodes": len(eps), "turn_cap": cap, "customer_model": args.customer_model, "judge_model": args.judge_model,
            "seed": args.seed, "mode": args.mode, "closed": args.closed,
            "data": {"episodes": _sha(args.episodes) if args.episodes else None, "targets": _sha(args.targets) if args.targets else None,
                     "compiled": _sha(args.compiled) if args.compiled else None, "cassette_before": _sha(args.cassette)},
            "paid_budget": args.paid_budget}
    (args.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    t0 = time.time()
    stopped = None
    try:
        for i, ep in enumerate(eps):
            if ep["episode_id"] in done_ids:
                continue
            comp = compiled[ep["episode_id"]]
            tag = f"r{args.rep}-{i}"
            try:
                res = h.run_episode(ep, comp, tag=tag)
                runs = [res]
                if res.get("diverged_at") is not None and customer is not None and args.b_reps > 1:
                    s1 = score_episode(res, comp, ep, judge=judge)
                    res2 = h.run_episode(ep, comp, tag=tag + "b2", b_from=res["diverged_at"])
                    s2 = score_episode(res2, comp, ep, judge=judge)
                    runs.append(res2)
                    if _outcome(s1) != _outcome(s2):
                        res3 = h.run_episode(ep, comp, tag=tag + "b3", b_from=res["diverged_at"])
                        s3 = score_episode(res3, comp, ep, judge=judge)
                        runs.append(res3)
                        outs = [_outcome(s1), _outcome(s2), _outcome(s3)]
                        pick = max(range(3), key=lambda j: outs.count(outs[j]))
                        res = {**runs[pick], "b_majority": {"outcomes": [list(o) for o in outs], "picked": pick}}
                    else:
                        res = {**res, "b_majority": {"outcomes": [list(_outcome(s1)), list(_outcome(s2))], "picked": 0}}
                    res["b_runs"] = [{"tag": r["tag"], "turns": [(t["customer"], t["role"]) for t in r["turns"] if t["mode"] == "B"]}
                                     for r in runs]
            except R.BudgetExceeded as exc:
                stopped = str(exc)
                print("멈춤:", stopped, flush=True)
                break
            except Exception as exc:          # noqa: BLE001 — 에피소드 하나의 실패는 기록하고 다음으로
                res = {"episode_id": ep["episode_id"], "tag": tag, "crash": f"{type(exc).__name__}: {exc}"[:500]}
            score = score_episode(res, comp, ep, judge=judge) if "crash" not in res else {"episode_id": ep["episode_id"], "crash": res["crash"]}
            with results_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(res, ensure_ascii=False, default=str) + "\n")
            with scores_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(score, ensure_ascii=False, default=str) + "\n")
            el = time.time() - t0
            print(f"[{i + 1}/{len(eps)}] {ep['episode_id']} done={score.get('done', {}).get('verdict')} "
                  f"turns={score.get('turns')} {el / 60:.1f}분", flush=True)
    finally:
        rec.uninstall()
        summary = rec.summary()
        summary["stopped"] = stopped
        summary["cassette_after"] = _sha(args.cassette)
        (args.out / "lookups.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
        meta["stopped"] = stopped
        (args.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if stopped is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
