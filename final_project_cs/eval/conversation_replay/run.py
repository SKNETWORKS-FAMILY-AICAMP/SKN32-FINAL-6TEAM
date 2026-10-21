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


def _free_commit_mb() -> int | None:
    """Windows 에서 지금 더 약속할 수 있는 메모리(MB, 실제 + 가상) — 다른 세션의 시험과 한 PC 를 나눠 쓰므로 바닥나기 전에 쉬는 데 쓴다."""
    try:
        import ctypes

        class _Mem(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

        m = _Mem()
        m.dwLength = ctypes.sizeof(_Mem)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return int(m.ullAvailPageFile // (1 << 20))
    except Exception:          # noqa: BLE001 — Windows 가 아니면 보호 없이 돈다
        return None


def _wait_for_memory(min_free_mb: int, max_wait_s: int = 7200) -> int:
    """남은 메모리가 `min_free_mb` 밑이면 30초씩 쉰다 — 바닥나 다른 세션 · 시험 DB 가 죽는 것을 막는다. 쉰 시간(초)을 돌려준다."""
    waited = 0
    while True:
        free = _free_commit_mb()
        if free is None or free >= min_free_mb or waited >= max_wait_s:
            return waited
        if waited % 300 == 0:
            print(f"메모리 부족 대기 — 남은 {free}MB < {min_free_mb}MB ({waited}초째)", flush=True)
        time.sleep(30)
        waited += 30


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
    ap.add_argument("--min-free-mb", type=int, default=700, help="남은 메모리가 이 값 밑이면 에피소드 사이에서 쉰다(다른 세션 보호)")
    ap.add_argument("--threads", type=int, default=1, help="한 실행기 안에서 동시에 도는 에피소드 수(앱 · 도로 그래프는 한 벌만 올린다 — 메모리 절약)")
    ap.add_argument("--reset-paid-counters", action="store_true",
                    help="시작 전에 시험 DB 의 유료 대체 호출 사용량(openai_failover)을 0 으로 되돌린다(하루 상한이 차 있으면 회차가 무효가 된다). 되돌리기 전 값은 meta.json 에 남긴다")
    ap.add_argument("--shard", help="K/N — 에피소드 목록을 N 등분해 K 번째(0부터)만 돈다(여러 실행기를 나눠 돌릴 때, 실행기마다 `--out` · `--db` · `--cassette` 를 따로 쓴다)")
    ap.add_argument("--skip-done-from", type=Path, action="append", default=[],
                    help="이 결과 폴더에서 이미 끝난 에피소드는 건너뛴다(실행기를 둘로 나눠 돌릴 때, 앞 실행이 끝낸 것 제외)")
    ap.add_argument("--label", default="검수 전 기준선")
    args = ap.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    import logging

    logging.getLogger("httpx").setLevel(logging.WARNING)     # 요청마다 INFO 줄이 쌓여 로그가 수십 MB 가 된다(2026-10-20 C: 가득 참 사건)
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
    if args.shard:
        shard_k, shard_n = (int(x) for x in args.shard.split("/"))
        eps = [e for i, e in enumerate(eps) if i % shard_n == shard_k]
    if args.limit:
        eps = eps[: args.limit]
    compiled = runner.load_compiled(args.compiled, eps)
    args.out.mkdir(parents=True, exist_ok=True)
    results_path, scores_path = args.out / "results.jsonl", args.out / "scores.jsonl"
    done_ids = set()
    if results_path.exists():
        # ★실행기가 죽어 남은 「오류로 끝난 에피소드」(crash)는 끝난 것으로 세지 않고 다시 돈다 — 파일에는 뒤 줄이 앞 줄을 대신한다(report 가 에피소드별 마지막 줄을 씀)
        done_ids = {r["episode_id"] for r in (json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip())
                    if "crash" not in r}

    for other in args.skip_done_from:
        other_results = other / "results.jsonl"
        if other_results.exists():
            for line in other_results.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    if "crash" not in row:
                        done_ids.add(row["episode_id"])

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
    # ★준비 호출 — 모델이 GPU 에 안 올라와 있으면 첫 턴이 적재 시간(약 26초) 때문에 9초 제한을 넘겨 유료 대체로 샌다(2026-10-20 점검에서 확인).
    #   운영 x600 서버는 모델이 늘 올라와 있으므로 시험도 올려 둔 상태에서 시작한다. 준비 호출은 녹화 · 예산에서 뺀다.
    warm = R.pause()
    try:
        import httpx

        t_warm = time.monotonic()
        httpx.post(args.ollama.rstrip("/") + "/api/chat", timeout=180,
                   json={"model": runner.X600_LIKE["ACOP_OLLAMA_MODEL"], "messages": [{"role": "user", "content": "준비"}],
                         "stream": False, "keep_alive": "30m", "options": {"num_ctx": 8192, "num_predict": 1}})
        warm_seconds = round(time.monotonic() - t_warm, 2)
    except Exception as exc:          # noqa: BLE001 — 준비 실패는 기록만(본 재생에서 다시 드러난다)
        warm_seconds = f"실패 {type(exc).__name__}"
    finally:
        R.resume(warm)
    paid_counters_before = None
    if args.reset_paid_counters:
        from .seed import reset_paid_counters

        paid_counters_before = reset_paid_counters(args.db)
    meta = {"label": args.label, "started_at": datetime.now().isoformat(timespec="seconds"), "argv": [str(a) for a in (argv or sys.argv[1:])
                                                                                                     if "key" not in str(a).lower()],
            "code": _code_hash(), "model": _model_info(args.ollama), "settings": runner.X600_LIKE, "settings_adjusted_vs_x600": runner.HARDWARE_ADJUST, "keys_loaded": names,
            "episodes": len(eps), "turn_cap": cap, "customer_model": args.customer_model, "judge_model": args.judge_model,
            "seed": args.seed, "mode": args.mode, "closed": args.closed, "shard": args.shard, "threads": args.threads,
            "data": {"episodes": _sha(args.episodes) if args.episodes else None, "targets": _sha(args.targets) if args.targets else None,
                     "compiled": _sha(args.compiled) if args.compiled else None, "cassette_before": _sha(args.cassette)},
            "paid_budget": args.paid_budget, "warmup_seconds": warm_seconds, "paid_counters_reset_before": paid_counters_before}
    (args.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    t0 = time.time()
    stopped = None
    mem_paused = 0
    import queue
    import threading
    from concurrent.futures import ThreadPoolExecutor

    # ★스레드 여럿이 한 앱 · 한 모델 서버를 나눠 쓴다 — 모델 서버가 놀고 있는 시간을 채워 빠르게 하려는 것(실행기를 여러 개 띄우면 메모리가 모자란다)
    pool_h: "queue.Queue" = queue.Queue()
    pool_h.put(h)
    for _ in range(max(1, args.threads) - 1):
        hx = runner.Harness(rec=rec, customer=customer, turn_cap=cap, judge=judge)
        hx.raw = h.raw
        hx.start(app=h.app)
        pool_h.put(hx)
    write_lock = threading.Lock()
    stop_flag = threading.Event()
    counter = {"done": 0}

    def process(i: int, ep: dict) -> None:
        nonlocal stopped
        hh = pool_h.get()
        try:
            comp = compiled[ep["episode_id"]]
            tag = f"r{args.rep}{'s' + args.shard.split('/')[0] if args.shard else ''}-{i}"
            try:
                res = hh.run_episode(ep, comp, tag=tag)
                runs = [res]
                if res.get("diverged_at") is not None and customer is not None and args.b_reps > 1:
                    s1 = score_episode(res, comp, ep, judge=judge)
                    res2 = hh.run_episode(ep, comp, tag=tag + "b2", b_from=res["diverged_at"])
                    s2 = score_episode(res2, comp, ep, judge=judge)
                    runs.append(res2)
                    if _outcome(s1) != _outcome(s2):
                        res3 = hh.run_episode(ep, comp, tag=tag + "b3", b_from=res["diverged_at"])
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
                with write_lock:
                    stopped = str(exc)
                stop_flag.set()
                print("멈춤:", stopped, flush=True)
                return
            except Exception as exc:          # noqa: BLE001 — 에피소드 하나의 실패는 기록하고 다음으로
                res = {"episode_id": ep["episode_id"], "tag": tag, "crash": f"{type(exc).__name__}: {exc}"[:500]}
            score = score_episode(res, comp, ep, judge=judge) if "crash" not in res else {"episode_id": ep["episode_id"], "crash": res["crash"]}
            with write_lock:
                with results_path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(res, ensure_ascii=False, default=str) + "\n")
                with scores_path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(score, ensure_ascii=False, default=str) + "\n")
                counter["done"] += 1
                el = time.time() - t0
                print(f"[{i + 1}/{len(eps)}] {ep['episode_id']} done={score.get('done', {}).get('verdict')} "
                      f"turns={score.get('turns')} 이번 실행 {counter['done']}개 {el / 60:.1f}분", flush=True)
        finally:
            pool_h.put(hh)

    try:
        with ThreadPoolExecutor(max_workers=max(1, args.threads)) as ex:
            inflight = threading.Semaphore(max(1, args.threads))
            for i, ep in enumerate(eps):
                if ep["episode_id"] in done_ids:
                    continue
                if stop_flag.is_set():
                    break
                inflight.acquire()          # 돌고 있는 에피소드가 스레드 수만큼이면 자리가 날 때까지 기다린다
                paused_s = _wait_for_memory(args.min_free_mb)
                if paused_s:
                    mem_paused += paused_s
                fut = ex.submit(process, i, ep)
                fut.add_done_callback(lambda _f: inflight.release())
    finally:
        rec.uninstall()
        summary = rec.summary()
        summary["stopped"] = stopped
        summary["cassette_after"] = _sha(args.cassette)
        (args.out / "lookups.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
        meta["stopped"] = stopped
        meta["memory_paused_seconds"] = mem_paused
        (args.out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if stopped is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
