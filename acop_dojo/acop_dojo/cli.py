"""도장 CLI. 정답 판정은 pytest 와 실측 트레이스가 한다."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import answers, boss, defect_stage, defects, mapgen, placement, progress, report, review, scenarios, stability, stages, tracer, tracks, validate
from .config import WORKSPACE_ROOT, target_root

SEPARATOR = "─" * 62


def trace_path(scenario_id: str) -> Path:
    return WORKSPACE_ROOT / ".acop_dojo" / "traces" / f"{scenario_id}.json"


def load_or_capture(scenario_id: str, *, refresh: bool = False) -> dict:
    scenario = scenarios.get(scenario_id)
    path = trace_path(scenario_id)
    if path.exists() and not refresh:
        cached = json.loads(path.read_text(encoding="utf-8"))
        cached.setdefault("code_revision", tracer.code_revision(target_root()))
        return cached
    print(f"트레이스를 뜬다: {scenario.nodeid}")
    return tracer.capture(scenario.nodeid, target=target_root(), out_path=path)


def cmd_doctor(_: argparse.Namespace) -> int:
    target = target_root()
    print("도장 점검")
    print(SEPARATOR)
    ok = True

    print(f"  대상 저장소            {target}")
    if not (target / "app").is_dir():
        print("    ✗ app/ 이 없다. ACOP_DOJO_TARGET 을 확인한다.")
        ok = False
    else:
        print("    ✓ 있다")

    version = sys.version_info
    print(f"  파이썬                 {version.major}.{version.minor}.{version.micro}")
    if version < (3, 12):
        print("    ✗ sys.monitoring 이 필요하다. 3.12 이상이어야 한다.")
        ok = False
    else:
        print("    ✓ sys.monitoring 쓸 수 있다")

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=target, capture_output=True, text=True, timeout=600, check=False)
    tail = [line for line in proc.stdout.strip().splitlines() if "collected" in line]
    print(f"  테스트 수집            {tail[-1] if tail else '실패'}")
    if not tail:
        ok = False
        print(f"    ✗ {proc.stdout[-400:]}")

    print(SEPARATOR)
    print("점검 통과." if ok else "점검 실패. 위 항목을 고친 뒤 다시 돌린다.")
    return 0 if ok else 1


def cmd_trace(args: argparse.Namespace) -> int:
    scenario = scenarios.get(args.scenario)
    print(f"{scenario.scenario_id} — {scenario.title}")
    first = load_or_capture(scenario.scenario_id, refresh=True)
    print(f"  결과 {first['outcome']['status']} · 단계 {first['summary']['steps']} · "
          f"고유 함수 {first['summary']['unique_symbols']} · revision {first['code_revision']}")
    problems = tracer.audit(first)
    if problems:
        print("  ✗ 트레이스에 넣으면 안 되는 값이 있다")
        for problem in problems[:5]:
            print(f"      {problem}")
        return 1
    print("  ✓ 금지 필드·긴 문자열 없음")
    if args.verify:
        print("  결정성 검사 — 한 번 더 돌려 비교한다")
        second_path = trace_path(scenario.scenario_id).with_suffix(".verify.json")
        second = tracer.capture(scenario.nodeid, target=target_root(), out_path=second_path)
        left = tracer.digest({k: v for k, v in first.items() if k != "code_revision"})
        right = tracer.digest({k: v for k, v in second.items() if k != "code_revision"})
        second_path.unlink(missing_ok=True)
        if left == right:
            print(f"  ✓ 두 번의 트레이스가 같다  {left[:23]}…")
        else:
            print("  ✗ 두 번의 트레이스가 다르다. 채점 오라클로 쓸 수 없다.")
            return 1
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    track = tracks.get(args.track)
    scenario_id = args.scenario or track.scenario
    if args.track != "all":
        print(f"[{track.title}]  핵심: {track.focus}")
    trace = load_or_capture(scenario_id)
    handler = {"0": stages.stage0_worked_example,
               "1": stages.stage1_reconstruct,
               "2": stages.stage2_contrast}[args.stage]
    handler(trace)
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    data = progress.load()
    titles = {"0": "해설된 완주", "1": "복원", "2": "대조", "3": "결함", "4": "보스전"}
    print("\nA-COP 도장 · 진행")
    print(SEPARATOR)
    for stage, title in titles.items():
        entry = data["stages"].get(stage)
        if not entry:
            print(f"  {stage}  {title:<12} 아직")
            continue
        extra = ""
        if "correct" in entry:
            extra = f"  {entry['correct']}/{entry['of']}"
        elif "hits" in entry:
            extra = f"  {entry['hits']}/{entry['of']}"
        print(f"  {stage}  {title:<12} {entry['status']}  (시도 {entry['attempts']}){extra}")
    print(f"\n  발견한 함수  {len(data['discovered'])}개")
    if data["abilities"]:
        print("  능력")
        for name, info in sorted(data["abilities"].items()):
            mark = "확정" if info["state"] == "confirmed" else "잠정"
            print(f"    {name:<16} {mark}   근거 {info['evidence']}")
    catalog = defects.load_catalog()
    entries = catalog.get("entries", {})
    playable = defect_stage.playable(catalog)
    if entries:
        survived = [d for d, e in entries.items()
                    if not e.get("gates", {}).get("kills_tests")]
        print("")
        print(f"  결함 카탈로그  후보 {len(entries)}개 중 낼 수 있는 것 {len(playable)}개")
        if survived:
            print(f"    테스트가 못 잡는 것 {len(survived)}개 — 문제로 쓰지 않는다")
            for defect_id in sorted(survived):
                print(f"      {defect_id}  {entries[defect_id][chr(112)+chr(97)+chr(116)+chr(104)]}")
    print(f"\n  진행 파일  {progress.progress_path()}")
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    track = tracks.get(args.track)
    trace = None
    path = trace_path(args.scenario or track.scenario)
    if path.exists():
        trace = json.loads(path.read_text(encoding="utf-8"))
    else:
        print("트레이스가 없다. 실측 호출 간선 없이 import 만 그린다. (acop-dojo trace 를 먼저 돌린다)")
    out = Path(args.out) if args.out else WORKSPACE_ROOT / ".acop_dojo" / "map.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(mapgen.build(target_root(), trace, progress.load(), track),
                   encoding="utf-8")
    print(f"지도를 그렸다: {out}")
    return 0


def cmd_defects(args: argparse.Namespace) -> int:
    if args.rebuild:
        for path in defects.write_patches(target_root()):
            print(f"  패치 작성 {path.name}")
    only = args.only.split(",") if args.only else None
    outcome = validate.validate_all(target_root(), only=only)
    data = defects.load_catalog()
    # 부분 검증이면 기존 결과를 지우지 않고 덮어쓴다.
    merged = dict(data.get("entries", {})) if only else {}
    merged.update(outcome["entries"])
    data["entries"] = merged
    data["baseline"] = outcome["baseline"]
    print("")
    print(f"카탈로그 저장: {defects.save_catalog(data)}")
    if outcome["collisions"]:
        print("겹침 경고:", outcome["collisions"])
    return 0


def cmd_defect(args: argparse.Namespace) -> int:
    return defect_stage.play(target_root(), defect_id=args.defect_id,
                             fix=Path(args.fix) if args.fix else None, track=args.track)


def cmd_boss(args: argparse.Namespace) -> int:
    trace = load_or_capture(boss.BOSS_SCENARIO)
    return boss.play(target_root(), trace, fix=Path(args.fix) if args.fix else None,
                     force=args.force, defect_id=args.defect)


def cmd_report(args: argparse.Namespace) -> int:
    default = WORKSPACE_ROOT / "program" / "research" / "테스트_사각지대_실측.md"
    out = Path(args.out) if args.out else default
    written = report.write(out, tracer.code_revision(target_root()))
    print(f"보고서를 썼다: {written}")
    return 0


def cmd_stability(args: argparse.Namespace) -> int:
    print(f"낼 수 있는 결함마다 지정 테스트를 {args.repeats}회씩 다시 돌린다")
    print(SEPARATOR)
    results = stability.check(target_root(), repeats=args.repeats)
    bad = {d: r for d, r in results.items() if r["verdict"] != "stable"}
    print(SEPARATOR)
    if bad:
        print(f"안정적이지 않은 결함 {len(bad)}개 — 문제로 내기 전에 손봐야 한다")
        for defect_id, result in sorted(bad.items()):
            print(f"  {defect_id}  {result['verdict']}")
    else:
        print("전부 안정적이다.")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    items = review.due()
    numbers = review.stats()
    if not items:
        print("지금 복습할 것이 없다.")
        print(f"  예약 {numbers['scheduled']}건 · 다시 온 것 {numbers['visited']}건 · "
              f"아직 안 온 것 {numbers['unobserved']}건")
        print("  안 온 것은 실패가 아니라 미관찰이다. 사람이 안 온 것과 틀린 것은 다르다.")
        return 0

    print(f"복습할 것 {len(items)}건")
    print(SEPARATOR)
    for concept, entry in items:
        other = review.other_defect_for(concept, entry.get("source"))
        print("")
        print(f"  규칙: {concept}")
        if other:
            catalog = defects.load_catalog()
            print(f"  같은 규칙이 다른 코드에서도 깨진다. 깨진 테스트만 보여준다.")
            for nodeid in catalog["entries"][other]["failed"][:4]:
                print(f"    FAILED  {nodeid}")
            print("  어느 파일인가?")
            guess = input("  > ").strip()
            actual = defects.by_id(other).path
            ok = bool(guess) and guess.lower() in actual.lower()
            print(f"  {'맞다.' if ok else '아니다.'}  {actual}")
        else:
            print("  이 규칙을 한 줄로 쓰고, 어느 파일이 지키는지 대라.")
            input("  > ")
            source = defects.by_id(entry["source"]) if entry.get("source") else None
            if source:
                print(f"  모범답안: {source.lesson}")
                print(f"  지키는 곳: {source.path}")
            print("  스스로 대조한다. 맞았나? (y/n)")
            ok = input("  > ").strip().lower().startswith("y")
        review.record(concept, recalled=ok)
    print("")
    print(SEPARATOR)
    numbers = review.stats()
    print(f"  예약 {numbers['scheduled']}건 · 회상 시도 {numbers['attempts']}건 중 "
          f"{numbers['recalled']}건 성공")
    print("  1·3·7·21일은 기본값일 뿐이다. 실제 재방문이 쌓이면 그때 조정한다.")
    return 0


def cmd_tracks(_: argparse.Namespace) -> int:
    catalog = defects.load_catalog()
    playable = defect_stage.playable(catalog)
    print("")
    print("학습 트랙 — 전체 1개 + 파트 6개")
    print(SEPARATOR)
    for track in tracks.TRACKS.values():
        mine = [d for d in playable
                if tracks.owns(track, defects.by_id(d).path)]
        print("")
        print(f"  {track.track_id:<14} {track.title}")
        print(f"  {'':<14} 담당 {track.owner_hint} · 결함 {len(mine)}개 · 시나리오 {len(track.scenarios)}개")
        for scenario_id in track.scenarios:
            print(f"  {'':<16} {scenario_id}  {scenarios.get(scenario_id).title}")
        print(f"  {'':<14} 핵심: {track.focus}")
    print("")
    print(SEPARATOR)
    print("  쓰는 법:  python dojo.py learn 0 --track core1")
    print("            python dojo.py defect --track front")
    print("            python dojo.py map --track team-review")
    print("")
    print("  ★팀 모듈 3분할은 저장소에 사람 배정 문서가 없어 모듈 성격으로 나눈 추정이다.")
    print("   담당이 다르면 acop_dojo/acop_dojo/tracks.py 의 owns 만 고치면 된다.")
    return 0


def cmd_scenarios(args: argparse.Namespace) -> int:
    print("")
    print(f"시나리오 {len(scenarios.SCENARIOS)}개")
    print(SEPARATOR)
    for scenario in scenarios.SCENARIOS.values():
        mark = "DB" if scenario.needs_db else "  "
        print(f"  [{mark}] {scenario.scenario_id:34} {scenario.title}")
    if not args.verify_all:
        print("")
        print("  --verify-all 을 주면 전부 두 번씩 떠서 같은지, 금지 필드가 없는지 본다.")
        return 0

    print("")
    print(SEPARATOR)
    print("전부 두 번씩 뜬다. 채점 오라클로 쓰려면 같아야 한다.")
    failed = []
    for scenario in scenarios.SCENARIOS.values():
        first = tracer.capture(scenario.nodeid, target=target_root(),
                               out_path=trace_path(scenario.scenario_id))
        problems = tracer.audit(first)
        second_path = trace_path(scenario.scenario_id).with_suffix(".verify.json")
        second = tracer.capture(scenario.nodeid, target=target_root(), out_path=second_path)
        second_path.unlink(missing_ok=True)
        left = tracer.digest({k: v for k, v in first.items() if k != "code_revision"})
        right = tracer.digest({k: v for k, v in second.items() if k != "code_revision"})
        ok = left == right and not problems
        if not ok:
            failed.append(scenario.scenario_id)
        mark = "✓" if ok else "✗"
        note = "" if not problems else f"  금지 필드 {len(problems)}건"
        print(f"  {mark} {scenario.scenario_id:34} {first['summary']['steps']:4d}단계{note}")
    print(SEPARATOR)
    print("전부 결정적이다." if not failed else f"문제 있는 시나리오: {failed}")
    return 0 if not failed else 1


def cmd_placement(args: argparse.Namespace) -> int:
    track = tracks.get(args.track)
    return placement.run(args.track, load_or_capture(track.scenario))


def cmd_answers(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else WORKSPACE_ROOT / ".acop_dojo" / "answers.md"
    print(f"답안을 모았다: {answers.write(out)}")
    print("  자동 채점하지 않는다. 동료나 멘토가 루브릭으로 본다.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acop-dojo", description="A-COP 도장")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="환경 점검").set_defaults(func=cmd_doctor)

    trace_cmd = sub.add_parser("trace", help="시나리오 트레이스를 뜬다")
    trace_cmd.add_argument("scenario", nargs="?", default="shipping-status-resolved-v1")
    trace_cmd.add_argument("--verify", action="store_true", help="두 번 돌려 같은지 본다")
    trace_cmd.set_defaults(func=cmd_trace)

    learn_cmd = sub.add_parser("learn", help="단계를 진행한다")
    learn_cmd.add_argument("stage", choices=["0", "1", "2"])
    learn_cmd.add_argument("--scenario", default=None)
    learn_cmd.add_argument("--track", default="all", choices=list(tracks.TRACKS))
    learn_cmd.set_defaults(func=cmd_learn)

    boss_cmd = sub.add_parser("boss", help="보스전 — 안 배운 모듈로 전이")
    boss_cmd.add_argument("--fix", default=None, help="직접 만든 패치 파일")
    boss_cmd.add_argument("--force", action="store_true", help="앞 단계를 안 해도 연다")
    boss_cmd.add_argument("--defect", default=None, help="같은 결함을 다시 받는다")
    boss_cmd.set_defaults(func=cmd_boss)

    map_cmd = sub.add_parser("map", help="웹 지도를 그린다")
    map_cmd.add_argument("--scenario", default=None)
    map_cmd.add_argument("--track", default="all", choices=list(tracks.TRACKS))
    map_cmd.add_argument("--out", default=None)
    map_cmd.set_defaults(func=cmd_map)

    defect_cmd = sub.add_parser("defect", help="결함 문제를 푼다")
    defect_cmd.add_argument("defect_id", nargs="?", default=None)
    defect_cmd.add_argument("--fix", default=None, help="직접 만든 패치 파일")
    defect_cmd.add_argument("--track", default="all", choices=list(tracks.TRACKS))
    defect_cmd.set_defaults(func=cmd_defect)

    defects_cmd = sub.add_parser("defects", help="결함 카탈로그를 검증한다")
    defects_cmd.add_argument("--rebuild", action="store_true", help="패치를 다시 만든다")
    defects_cmd.add_argument("--only", default=None, help="쉼표로 구분한 결함 id 만 검증한다")
    defects_cmd.set_defaults(func=cmd_defects)

    sub.add_parser("tracks", help="학습 트랙 7개를 본다").set_defaults(func=cmd_tracks)

    placement_cmd = sub.add_parser("placement", help="어디부터 시작할지 재 본다")
    placement_cmd.add_argument("--track", default="all", choices=list(tracks.TRACKS))
    placement_cmd.set_defaults(func=cmd_placement)

    scenarios_cmd = sub.add_parser("scenarios", help="시나리오 목록과 결정성 검사")
    scenarios_cmd.add_argument("--verify-all", action="store_true")
    scenarios_cmd.set_defaults(func=cmd_scenarios)

    sub.add_parser("review", help="예약된 복습을 꺼낸다").set_defaults(func=cmd_review)

    answers_cmd = sub.add_parser("answers", help="서술 답안을 동료 검토용으로 내보낸다")
    answers_cmd.add_argument("--out", default=None)
    answers_cmd.set_defaults(func=cmd_answers)

    stability_cmd = sub.add_parser("stability", help="결함이 매번 같은 신호를 내는지 본다")
    stability_cmd.add_argument("--repeats", type=int, default=3)
    stability_cmd.set_defaults(func=cmd_stability)

    report_cmd = sub.add_parser("report", help="검증 결과로 사각지대 보고서를 쓴다")
    report_cmd.add_argument("--out", default=None)
    report_cmd.set_defaults(func=cmd_report)

    sub.add_parser("status", help="진행 상황").set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    return args.func(args)
