"""도장 CLI. 정답 판정은 pytest 와 실측 트레이스가 한다."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import answers, ask, boss, build, server, defect_stage, defects, invariants, mapgen, placement, refs, progress, report, review, scenarios, stability, stages, tracer, tracks, validate
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
    print(f"트레이스(실행 기록)를 만든다: {scenario.nodeid}")
    return tracer.capture(scenario.nodeid, target=target_root(), out_path=path)


def cmd_doctor(_: argparse.Namespace) -> int:
    target = target_root()
    print("학습 환경 점검")
    print(SEPARATOR)
    ok = True

    print(f"  대상 저장소            {target}")
    if not (target / "app").is_dir():
        print("    [실패] app/ 폴더가 없다. ACOP_DOJO_TARGET을 확인한다.")
        ok = False
    else:
        print("    [통과] app/ 폴더가 있다.")

    version = sys.version_info
    print(f"  파이썬                 {version.major}.{version.minor}.{version.micro}")
    if version < (3, 12):
        print("    [실패] sys.monitoring을 사용하려면 Python 3.12 이상이 필요하다.")
        ok = False
    else:
        print("    [통과] sys.monitoring을 사용할 수 있다.")

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=target, capture_output=True, text=True, timeout=600, check=False)
    tail = [line for line in proc.stdout.strip().splitlines() if "collected" in line]
    print(f"  테스트 수집            {tail[-1] if tail else '실패'}")
    if not tail:
        ok = False
        print(f"    [실패 원인] {proc.stdout[-400:]}")

    print(SEPARATOR)
    print("모든 환경 점검을 통과했다." if ok else "환경 점검에 실패했다. 위 항목을 고친 뒤 다시 실행한다.")
    return 0 if ok else 1


def cmd_trace(args: argparse.Namespace) -> int:
    scenario = scenarios.get(args.scenario)
    print(f"{scenario.scenario_id} — {scenario.title}")
    first = load_or_capture(scenario.scenario_id, refresh=True)
    print(f"  실행 결과 상태 {first['outcome']['status']} · 실행 지점 {first['summary']['steps']}개 · "
          f"고유 함수 {first['summary']['unique_symbols']}개 · 코드 버전(revision) {first['code_revision']}")
    problems = tracer.audit(first)
    if problems:
        print("  [실패] 트레이스(실행 기록)에 저장하면 안 되는 값이 있다.")
        for problem in problems[:5]:
            print(f"      {problem}")
        return 1
    print("  [통과] 금지 필드와 지나치게 긴 문자열이 없다.")
    if args.verify:
        print("  결정성(같은 입력에서 같은 결과가 나오는 성질)을 검사한다. 한 번 더 실행해 비교한다.")
        second_path = trace_path(scenario.scenario_id).with_suffix(".verify.json")
        second = tracer.capture(scenario.nodeid, target=target_root(), out_path=second_path)
        left = tracer.digest({k: v for k, v in first.items() if k != "code_revision"})
        right = tracer.digest({k: v for k, v in second.items() if k != "code_revision"})
        second_path.unlink(missing_ok=True)
        if left == right:
            print(f"  [통과] 두 번의 트레이스가 같다.  {left[:23]}…")
        else:
            print("  [실패] 두 번의 트레이스가 다르다. 채점 기준으로 사용할 수 없다.")
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


def cmd_level(args: argparse.Namespace) -> int:
    if args.value:
        ask.set_level(args.value)
    now = ask.NAMES.get(ask.level(), ask.level())
    print(f"난이도: {now}")
    print("  쉬움    보기 문제는 처음부터 보기를 보여 준다. 힌트를 사용할 수 있다.")
    print("  보통    먼저 직접 답한다. 모르면 `모르겠다`를 입력해 4지선다로 바꾼다. 힌트를 사용할 수 있다.")
    print("  어려움  힌트와 보기 전환을 제공하지 않는다.")
    print("  문제를 푸는 중 `힌트`를 입력하면 힌트가 한 단계씩 열린다. 힌트는 최대 세 개다.")
    print("  난이도 바꾸기:  python dojo.py level 쉬움")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    data = progress.load()
    titles = {"0": "해설된 완주", "1": "복원", "2": "대조", "3": "결함", "4": "보스전"}
    print("\nA-COP 학습 진행 (passed=통과, partial=일부 통과, in_progress=진행 중)")
    print(SEPARATOR)
    for stage, title in titles.items():
        entry = data["stages"].get(stage)
        if not entry:
            print(f"  {stage}  {title:<12} 시작 전")
            continue
        extra = ""
        if "correct" in entry:
            extra = f"  {entry['correct']}/{entry['of']}"
        elif "hits" in entry:
            extra = f"  {entry['hits']}/{entry['of']}"
        print(f"  {stage}  {title:<12} {entry['status']}  (시도 {entry['attempts']}){extra}")
    print(f"\n  발견한 함수  {len(data['discovered'])}개")
    if data["abilities"]:
        print("  확인한 능력")
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
        print(f"  결함 카탈로그(검증할 결함 목록)  후보 {len(entries)}개 중 출제 가능 {len(playable)}개")
        if survived:
            print(f"    테스트가 발견하지 못하는 결함 {len(survived)}개는 문제로 내지 않는다.")
            for defect_id in sorted(survived):
                print(f"      {defect_id}  {entries[defect_id][chr(112)+chr(97)+chr(116)+chr(104)]}")
    # 처음부터 쌓기는 진행 파일이 따로다(작업 폴더 옆). 한 화면에서 같이 본다.
    build_state = build.load_state()
    if build_state.get("prepared_at") or build_state.get("steps"):
        all_steps = build.steps()
        done = sum(1 for s in all_steps
                   if build_state["steps"].get(str(s.index), {}).get("status") == "passed")
        print("")
        print(f"  처음부터 쌓기  {done}/{len(all_steps)}단계 통과"
              + (f" · 확인한 참고 구현 {len(build_state[chr(114)+chr(101)+chr(118)+chr(101)+chr(97)+chr(108)+chr(101)+chr(100)])}개"
                 if build_state["revealed"] else ""))
        if done < len(all_steps):
            nxt = _next_step(all_steps, build_state)
            print(f"    다음: {nxt}. {build.get(nxt).title}  (python dojo.py build brief {nxt})")
    print(f"\n  진행 파일  {progress.progress_path()}")
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    track = tracks.get(args.track)
    scenario_id = args.scenario or track.scenario
    scenarios.get(scenario_id)
    context = mapgen.snapshot(track.track_id, scenario_id)
    out = Path(args.out) if args.out else WORKSPACE_ROOT / ".acop_dojo" / "map.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(mapgen.build(target_root(), None, progress.load(), track, context=context),
                   encoding="utf-8")
    print(f"웹 지도를 만들었다: {out}")
    return 0


def cmd_defects(args: argparse.Namespace) -> int:
    if args.rebuild:
        for path in defects.write_patches(target_root()):
            print(f"  패치 작성 {path.name}")
    only = args.only.split(",") if args.only else None
    outcome = validate.validate_all(target_root(), only=only)
    if not outcome["entries"]:
        # 검증 결과가 없으면 카탈로그를 건드리지 않는다. 예전에는 빈 결과로
        # 덮어써 검증해 둔 결함 39건의 결과가 지워졌다.
        print("검증 결과가 없어 기존 카탈로그를 유지한다.")
        return 1
    data = defects.load_catalog()
    # 부분 검증이면 기존 결과를 지우지 않고 덮어쓴다.
    merged = dict(data.get("entries", {})) if only else {}
    merged.update(outcome["entries"])
    data["entries"] = merged
    data["baseline"] = outcome["baseline"]
    data["baseline"]["unexpected"] = outcome.get("unexpected_baseline", [])
    print("")
    print(f"카탈로그 저장: {defects.save_catalog(data)}")
    if outcome["collisions"]:
        print("같은 실패 결과를 내는 결함이 있다:", outcome["collisions"])
    if data["baseline"]["unexpected"]:
        # 결과는 저장했다. 다만 모르는 기준선 실패가 있으면 성공으로 끝내지 않는다.
        print(f"\n[실패] 알려진 목록(data/known_baseline.json)에 없는 기준선 실패가 "
              f"{len(data['baseline']['unexpected'])}건 있다. 결함 판정에서는 제외했으므로 원인을 확인한다:")
        for nodeid in data["baseline"]["unexpected"]:
            print(f"    {nodeid}")
        return 1
    return 0


def cmd_defect(args: argparse.Namespace) -> int:
    return defect_stage.play(target_root(), defect_id=args.defect_id,
                             fix=Path(args.fix) if args.fix else None, track=args.track)


def cmd_boss(args: argparse.Namespace) -> int:
    trace = load_or_capture(boss.BOSS_SCENARIO)
    return boss.play(target_root(), trace, fix=Path(args.fix) if args.fix else None,
                     force=args.force, defect_id=args.defect)


def _build_brief(step: build.Step) -> None:
    print("")
    print(f"{step.index}단계 · {step.title}")
    print(SEPARATOR)
    print("  이 단계를 지금 만드는 이유")
    for line in step.why.splitlines():
        print(f"    {line}")
    print("")
    print("  이 단계에서 만들 파일")
    for rel in step.paths():
        info = build.spec(rel)
        done = "[완료]" if rel in build.written(step) else "[미완료]"
        print(f"   {done} {rel}  ({info.get('lines', '?')}줄)  {info.get('summary', '')}")
        for name in info.get("names", []):
            print(f"        {name}")
        if info.get("imports"):
            print(f"        가져와서 사용하는 모듈: {', '.join(info['imports'])}")
    print("")
    print("  이 단계의 통과 여부를 판정하는 테스트")
    for nodeid in step.tests:
        print(f"    {nodeid}")
    for note in step.notes:
        print(f"\n  {note}")
    print("")
    print(f"  통과 기준: 다음 내용을 설명할 수 있어야 한다. {step.claim}")
    print("")
    print(f"  판정:  python dojo.py build check {step.index}")
    print(f"  힌트 확인: python dojo.py build hint {step.index}  (세 단계이며 사용 기록이 남는다.)")
    print(f"  참고 구현 확인: python dojo.py build reveal {step.index} <파일>")


def cmd_build(args: argparse.Namespace) -> int:
    action = args.action
    all_steps = build.steps()
    state = build.load_state()

    if action == "steps":
        print("")
        print(f"처음부터 쌓기 — 총 {len(all_steps)}단계 · 대상 저장소: {build.build_target_root().name}")
        print(SEPARATOR)
        for step in all_steps:
            mark = {"passed": "[통과]", "in_progress": "[진행 중]"}.get(
                state["steps"].get(str(step.index), {}).get("status"), "[시작 전]")
            print(f"  {mark} {step.index:2}. {step.title:22} 파일 {len(step.paths())} · 테스트 {len(step.tests)}")
            print(f"       {step.claim}")
        done = sum(1 for s in all_steps if state["steps"].get(str(s.index), {}).get("status") == "passed")
        print(SEPARATOR)
        print(f"  통과 {done}/{len(all_steps)}")
        if state["revealed"]:
            print(f"  확인한 참고 구현 {len(state['revealed'])}개: {', '.join(state['revealed'])}")
        return 0

    if action == "start":
        workspace, emptied = build.prepare(force=args.force)
        state = build.load_state()
        state["prepared_at"] = datetime.now(UTC).isoformat()
        if args.force:
            # 새 판이다. 앞 판의 통과·꺼내 본 기록을 남기면 이번 판 상태를 못 읽는다.
            state["steps"], state["revealed"] = {}, []
        build.save_state(state)
        print("")
        print(f"코드를 작성할 작업 폴더를 만들었다: {workspace}")
        print(f"  {build.BUILD_PACKAGE}/에서 모듈 {len(emptied)}개를 비웠다. app, tests, config 폴더는 유지했다.")
        print("  원본 저장소는 바꾸지 않는다. 위 작업 폴더에서만 코드를 작성한다.")
        print("")
        _build_brief(all_steps[0])
        return 0

    step = build.get(args.step or _next_step(all_steps, state))
    if action == "brief":
        _build_brief(step)
        return 0
    if action == "hint":
        tier, lines = build.next_hint(step)
        print(f"\n{step.index}단계 · {step.title} — 힌트 {min(tier, build.HINT_TIERS)}/{build.HINT_TIERS}")
        print(SEPARATOR)
        for line in lines:
            print(f"  {line}")
        print("\n  사용한 힌트는 기록에 남는다. 다음 힌트 확인:  python dojo.py build hint "
              f"{step.index}")
        return 0
    if action == "reveal":
        path = build.reveal(step, args.path)
        print(f"참고 구현을 작업 폴더에 복사했다: {path}")
        print("참고 구현을 확인한 사실을 기록했다. 직접 다시 작성하려면 복사한 내용을 지우고 작성한다.")
        return 0

    # 3단계(저장소)부터 DB 를 쓰는 테스트가 섞인다. 꺼져 있으면 테스트마다 오래 기다리다 실패한다.
    if step.index >= 3 and build.database_reachable() is False:
        host, port = build.database_endpoint() or ("?", "?")
        print(f"\nDB({host}:{port})에 연결할 수 없어 코드를 판정하지 않았다.")
        print("  먼저 PostgreSQL이 실행 중인지 확인한다. 이 기계에서는 재부팅 뒤 자동으로 시작되지 않을 수 있다.")
        print("  기동 절차: final_project_sample/wiki/records/manuals/2026-08-12_1520_환경_기동절차.md")
        return 2

    print(f"\n{step.index}단계 · {step.title} — 테스트 {len(step.tests)}개를 실행한다.")
    print(SEPARATOR)
    passed, result = build.check(step)
    build.record(step, passed=passed, result=result)
    print(f"  {result.summary}")
    for nodeid in result.failed[:8]:
        print(f"  FAILED  {nodeid}")
    print(SEPARATOR)
    if passed:
        print("  통과했다. 이 단계까지 작성한 코드로 모든 판정 테스트가 실행된다.")
        nxt = _next_step(all_steps, build.load_state())
        if nxt <= len(all_steps):
            print("")
            _build_brief(build.get(nxt))
        else:
            print("  모든 단계를 통과했다. 베이스먼트(도메인을 모르는 코어)를 완성했다.")
    else:
        print("  아직 통과하지 못했다. 실패한 테스트를 읽고 요구하는 동작을 먼저 정리한다.")
        print(f"  명세 다시 확인: python dojo.py build brief {step.index}")
    return 0 if passed else 1


def _next_step(all_steps: list[build.Step], state: dict) -> int:
    for step in all_steps:
        if state["steps"].get(str(step.index), {}).get("status") != "passed":
            return step.index
    return len(all_steps)


def cmd_report(args: argparse.Namespace) -> int:
    default = WORKSPACE_ROOT / "program" / "research" / "테스트_사각지대_실측.md"
    out = Path(args.out) if args.out else default
    written = report.write(out, tracer.code_revision(target_root()))
    print(f"보고서를 썼다: {written}")
    return 0


def cmd_stability(args: argparse.Namespace) -> int:
    print(f"출제 가능한 결함마다 지정 테스트를 {args.repeats}회씩 실행해 결과가 같은지 확인한다.")
    print(SEPARATOR)
    results = stability.check(target_root(), repeats=args.repeats)
    bad = {d: r for d, r in results.items() if r["verdict"] != "stable"}
    print(SEPARATOR)
    if bad:
        print(f"결과가 일정하지 않은 결함이 {len(bad)}개다. 문제로 내기 전에 수정한다.")
        for defect_id, result in sorted(bad.items()):
            print(f"  {defect_id}  {result['verdict']}")
    else:
        print("모든 결함이 실행할 때마다 같은 결과를 냈다.")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    items = review.due()
    numbers = review.stats()
    if not items:
        print("지금 복습할 항목이 없다.")
        print(f"  예약 {numbers['scheduled']}건 · 다시 온 것 {numbers['visited']}건 · "
              f"아직 안 온 것 {numbers['unobserved']}건")
        print("  아직 복습일이 되지 않은 항목은 실패가 아니라 미관찰로 기록한다.")
        return 0

    print(f"지금 복습할 항목은 {len(items)}건이다.")
    print(SEPARATOR)
    for concept, entry in items:
        other = review.other_defect_for(concept, entry.get("source"))
        print("")
        print(f"  규칙: {concept}")
        if other:
            catalog = defects.load_catalog()
            print("  같은 규칙을 다른 코드에 적용한다. 아래는 실패한 테스트다.")
            for nodeid in catalog["entries"][other]["failed"][:4]:
                print(f"    FAILED  {nodeid}")
            target_defect = defects.by_id(other)
            actual = target_defect.path
            files, index = ask.file_choices(
                actual, [defects.by_id(d).path for d in defect_stage.playable(catalog)])
            guess = ask.free("규칙을 어긴 파일을 쓴다. 경로의 일부만 써도 된다.",
                             hints=[f"그 파일은 {ask.layer_of(actual)}에 있다.",
                                    f"바뀐 줄의 원래 코드는 "
                                    f"{target_defect.old.strip().splitlines()[0][:70]}"],
                             fallback=(files, index))
            ok = (guess.index == index) if guess.via_choices else (
                bool(guess.text) and guess.text.lower() in actual.lower())
            print(f"  {'맞다.' if ok else '아니다.'}  {actual}")
        else:
            source_hint = defects.by_id(entry["source"]).path if entry.get("source") else ""
            ask.free("이 규칙을 한 줄로 설명하고, 규칙을 지키는 파일을 쓴다.",
                     hints=([f"그 파일은 {ask.layer_of(source_hint)}에 있다."] if source_hint else []))
            source = defects.by_id(entry["source"]) if entry.get("source") else None
            if source:
                print(f"  모범답안: {source.lesson}")
                print(f"  지키는 곳: {source.path}")
            ok = ask.yes_no("본인 답에 규칙과 파일이 모두 들어 있는가?").text == "y"
        review.record(concept, recalled=ok)
    print("")
    print(SEPARATOR)
    numbers = review.stats()
    print(f"  예약 {numbers['scheduled']}건 · 회상 시도 {numbers['attempts']}건 중 "
          f"{numbers['recalled']}건 성공")
    print("  다음 복습일은 기본 간격인 1, 3, 7, 21일을 사용한다. 실제 복습 기록이 쌓이면 조정한다.")
    return 0


def cmd_tracks(_: argparse.Namespace) -> int:
    catalog = defects.load_catalog()
    playable = defect_stage.playable(catalog)
    print("")
    print(f"베이스먼트(도메인을 모르는 코어) 학습 트랙은 {len(tracks.TRACKS)}개다.")
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
    print("  학습 시작:  python dojo.py learn 0 --track core1")
    print("            python dojo.py defect --track front")
    print("            python dojo.py map --track core2")
    print("")
    print(f"  중지한 트랙: {', '.join(sorted(tracks.PARKED_TRACK_IDS))} — 커머스 Team(작업 수행 모듈) 트랙이다.")
    print("   도메인이 여행으로 바뀌어 대상 코드가 등록에서 빠졌으므로 이 트랙을 진행할 수 없다.")
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
        print("  --verify-all을 사용하면 모든 시나리오를 두 번씩 실행해 결과가 같은지와 금지 필드가 없는지 검사한다.")
        return 0

    print("")
    print(SEPARATOR)
    print("모든 시나리오를 두 번씩 실행한다. 채점 기준으로 쓰려면 두 결과가 같아야 한다.")
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
        mark = "[통과]" if ok else "[실패]"
        note = "" if not problems else f"  금지 필드 {len(problems)}건"
        print(f"  {mark} {scenario.scenario_id:34} {first['summary']['steps']:4d}단계{note}")
    print(SEPARATOR)
    print("모든 시나리오가 실행할 때마다 같은 결과를 냈다." if not failed else f"결과가 일정하지 않거나 금지 필드가 있는 시나리오: {failed}")
    return 0 if not failed else 1


def cmd_placement(args: argparse.Namespace) -> int:
    track = tracks.get(args.track)
    return placement.run(args.track, load_or_capture(track.scenario))


def cmd_answers(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else WORKSPACE_ROOT / ".acop_dojo" / "answers.md"
    print(f"답안을 모았다: {answers.write(out)}")
    print("  서술 답안은 자동 채점하지 않는다. 동료나 멘토가 루브릭(평가 기준표)으로 검토한다.")
    return 0


def cmd_patches(_: argparse.Namespace) -> int:
    outcome = validate.check_patches(target_root())
    broken = (len(outcome["anchor_broken"]) + len(outcome["apply_broken"])
              + len(outcome["drift"]) + len(outcome["missing"])
              + len(outcome["source_missing"]))
    print(SEPARATOR)
    if broken:
        print(f"{broken}개의 패치가 현재 코드와 맞지 않는다. `python dojo.py defects --rebuild`로 다시 만든다.")
        print("기준 코드가 바뀌어 재생성할 수 없는 항목은 카탈로그의 old/new 값을 수정한다.")
    else:
        print("모든 결함 패치가 유효하다.")
    return 1 if broken else 0


def cmd_invariants(_: argparse.Namespace) -> int:
    return invariants.report(invariants.check(), separator=SEPARATOR)


def cmd_refs(args: argparse.Namespace) -> int:
    outcome = refs.scan(target_root())
    code = refs.report(outcome, separator=SEPARATOR, limit=args.limit)
    if code and args.fix:
        applied = refs.fix(target_root(), outcome)
        print(SEPARATOR)
        print(f"파일 {applied['files']}개에서 참조 {applied['references']}건을 고쳤다.")
        print(f"남은 {len(applied['left'])}건은 옮겨간 자리를 못 찾아 그대로 뒀다.")
        print("주석 문자열만 바꿨지만 테스트로 확인한다.")
        return 0
    if code:
        print(SEPARATOR)
        print("문서를 가리키는 주석에 잘못된 참조가 남아 있다. 위 항목을 확인한다.")
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="acop-dojo", description="A-COP 코드 학습 프로그램")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="환경 점검").set_defaults(func=cmd_doctor)

    trace_cmd = sub.add_parser("trace", help="시나리오의 실행 기록(트레이스)을 만든다")
    # 기본값이 중지한 커머스 시나리오를 가리켜 인자 없이 부르면 죽었다(2026-09-14 codex-alt 지적).
    trace_cmd.add_argument("scenario", nargs="?", default="status-inquiry-untouched-v1")
    trace_cmd.add_argument("--verify", action="store_true", help="두 번 실행해 결과가 같은지 검사한다")
    trace_cmd.set_defaults(func=cmd_trace)

    learn_cmd = sub.add_parser("learn", help="단계를 진행한다")
    learn_cmd.add_argument("stage", choices=["0", "1", "2"])
    learn_cmd.add_argument("--scenario", default=None)
    learn_cmd.add_argument("--track", default="all", choices=list(tracks.TRACKS))
    learn_cmd.set_defaults(func=cmd_learn)

    boss_cmd = sub.add_parser("boss", help="보스전 — 배운 규칙을 새 모듈에 적용한다")
    boss_cmd.add_argument("--fix", default=None, help="직접 만든 패치 파일")
    boss_cmd.add_argument("--force", action="store_true", help="앞 단계를 안 해도 연다")
    boss_cmd.add_argument("--defect", default=None, help="같은 결함을 다시 받는다")
    boss_cmd.set_defaults(func=cmd_boss)

    build_cmd = sub.add_parser("build", help="처음부터 쌓기 — 빈 폴더에서 베이스먼트(도메인을 모르는 코어)를 만든다")
    build_cmd.add_argument("action", choices=["steps", "start", "brief", "check", "hint", "reveal"],
                           nargs="?", default="steps")
    build_cmd.add_argument("step", nargs="?", type=int, default=None, help="단계 번호")
    build_cmd.add_argument("path", nargs="?", default=None, help="reveal 로 꺼낼 파일")
    build_cmd.add_argument("--force", action="store_true", help="작업 폴더를 새로 만든다")
    build_cmd.set_defaults(func=cmd_build)

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

    defects_cmd = sub.add_parser("defects", help="결함 카탈로그(검증할 결함 목록)를 검사한다")
    defects_cmd.add_argument("--rebuild", action="store_true", help="패치를 다시 만든다")
    defects_cmd.add_argument("--only", default=None, help="쉼표로 구분한 결함 id 만 검증한다")
    defects_cmd.set_defaults(func=cmd_defects)

    refs_cmd = sub.add_parser("refs", help="문서를 가리키는 참조가 실재하는지 본다")
    refs_cmd.add_argument("--limit", type=int, default=12)
    refs_cmd.add_argument("--fix", action="store_true",
                          help="옮겨간 자리를 찾은 것만 고친다")
    refs_cmd.set_defaults(func=cmd_refs)

    sub.add_parser("invariants", help="규칙 원장(지켜야 할 규칙 목록)과 결함 카탈로그가 맞는지 검사한다").set_defaults(func=cmd_invariants)

    sub.add_parser("patches", help="결함 패치가 현재 코드에도 적용되는지 빠르게 검사한다").set_defaults(func=cmd_patches)

    sub.add_parser("tracks", help="베이스먼트(도메인을 모르는 코어) 학습 트랙 4개를 본다").set_defaults(func=cmd_tracks)

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

    serve_cmd = sub.add_parser("serve", help="브라우저에서 도장을 돌린다 (로컬 서버)")
    serve_cmd.add_argument("--port", type=int, default=8765)
    serve_cmd.add_argument("--no-open", action="store_true", help="브라우저를 자동으로 열지 않는다")
    serve_cmd.set_defaults(func=lambda args: server.serve(args.port, open_browser=not args.no_open))

    level_cmd = sub.add_parser("level", help="난이도를 보거나 바꾼다 (쉬움 · 보통 · 어려움)")
    level_cmd.add_argument("value", nargs="?", default=None)
    level_cmd.set_defaults(func=cmd_level)

    sub.add_parser("status", help="진행 상황").set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    return args.func(args)
