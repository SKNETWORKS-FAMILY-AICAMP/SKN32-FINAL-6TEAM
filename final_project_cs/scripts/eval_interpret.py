"""숙소 · 항공 팀의 **해석 단계(모델 1번)** 정확도를 잰다 — 정해 둔 문장마다 모델이 낸 구조를 서버 검증(parse · ground · needs)까지
돌린 뒤, 사람이 정한 정답(`scripts/interpret_cases.json`)과 칸별로 맞춰 본다. `[2026-10-10]`

- 모델 호출 · 프롬프트는 `try_lodging_team.FilePromptLLM` 과 같다(프롬프트 파일을 바로 읽고, 설정의 OpenAI 모델 · temperature · seed).
  문장 하나 = 모델 1번. 검색 · 마이리얼트립 · 구글은 부르지 않는다(우리 쪽 데이터 소스에 부하 없음).
- 기준일은 파일의 `today`(2026-10-10)로 고정한다 — 상대 날짜(「다음 달 6일」)의 정답이 바뀌지 않게.
- 모델 응답 원문은 저장하지 않는다. 틀린 칸만 「정답 / 받은 값」과 모델이 적은 근거 조각(`*_text`)을 출력한다.
- `[2026-10-10]` 팀과 같게 `model_context`(달력) · `settle_years`(연도) 를 거친 값을 본다.
- `--repeat N` 은 같은 문장을 N번 돌려 흔들림을 본다(같은 seed 라도 결과가 달라질 수 있다).

실행 위치: final_project_cs
  python -m scripts.eval_interpret                 # 숙소 + 항공 전체(모델 호출 40번 안팎)
  python -m scripts.eval_interpret lodging --repeat 3
  python -m scripts.eval_interpret flight --only F04,F05
  python -m scripts.eval_interpret --rules             # `[2026-10-14]` 항공 규칙 해석(모델 호출 0)
  python -m scripts.eval_interpret --compare           # `[2026-10-14]` 규칙 ↔ 모델 칸별 대조(모델 호출 50번)
"""
import asyncio
from argparse import ArgumentParser
from collections import Counter, defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import platform
import time
from zoneinfo import ZoneInfo

CASES = Path(__file__).with_name("interpret_cases.json")
PLAIN = False
UNORDERED = {"needs", "depart_times"}


def matches(want, got, field):
    if want == "*":
        return got not in (None, "", [])
    if isinstance(want, dict) and "one_of" in want:
        return any(matches(option, got, field) for option in want["one_of"])
    if field in UNORDERED and isinstance(want, list):
        return isinstance(got, list) and sorted(want) == sorted(got)
    if isinstance(want, float) or isinstance(got, float):
        return isinstance(got, (int, float)) and isinstance(want, (int, float)) and abs(float(want) - float(got)) < 1e-6
    return want == got


def team_parts(team):
    if team == "lodging":
        from app.domains.travel_ops.instances.lodging import interpret
        from app.domains.travel_ops.instances.lodging.team import PROMPT_KEY
    else:
        from app.domains.travel_ops.instances.booking import interpret
        from app.domains.travel_ops.instances.booking.team import PROMPT_KEY
    return PROMPT_KEY, interpret


async def run_case(llm, team, case, today, trip):
    key, interpret = team_parts(team)
    context = interpret.model_context(today, trip if case.get("trip") else None)   # 팀과 같은 context(달력 포함)
    if PLAIN:                                         # 비교용 — 달력 없이 오늘 · 여행만(2026-10-10 1차 측정 때 모양)
        context = {key: value for key, value in context.items() if key in ("today", "trip")}
    started = time.perf_counter()
    if llm is None:                                   # `[2026-10-14]` 규칙 해석(항공 예약 모듈) — 모델 호출 없음
        from app.domains.travel_ops.instances.booking.interpret_rules import interpret as rules
        raw = rules(case["text"], today=today, trip=trip if case.get("trip") else None)
    else:
        try:
            raw = await llm.complete(key, case["text"], context)
        except Exception as exc:                      # noqa: BLE001 — 모델 호출 실패도 한 줄로 센다
            return {"error": f"model {type(exc).__name__}"}, time.perf_counter() - started
    took = time.perf_counter() - started
    try:
        found, cleared = interpret.ground(interpret.parse(raw), case["text"], has_trip=bool(case.get("trip")),
                                          trip=trip if case.get("trip") else None)
        found, fixed = interpret.settle_years(found, today=today, text=case["text"])   # 팀과 같은 순서
    except interpret.InterpretationInvalid as exc:
        return {"error": f"invalid {str(exc)[:120]}"}, took
    values = found.model_dump(mode="json")
    values["needs"] = interpret.needs(found, today=today)
    values["_cleared"] = cleared
    values["_fixed"] = fixed
    values["_missing"] = list(found.missing)
    values["_quotes"] = {key: value for key, value in found.model_dump(mode="json").items() if key.endswith("_text") and value}
    return values, took


def main():
    from scripts.try_lodging_team import FilePromptLLM

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("teams", nargs="*", help="lodging · flight (없으면 둘 다)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--only", default="", help="쉼표로 나눈 문장 id(L01,F04 …)")
    parser.add_argument("--plain-context", action="store_true", help="달력 없이(1차 측정 때 context) — 달력의 효과를 따로 본다")
    parser.add_argument("--set", dest="case_set", default="", help="base(처음 40문장) · hard(10-10 밤 추가) · user(사용자가 쓴 20문장) · real(실제 문장) — 없으면 전부")
    parser.add_argument("--rules", action="store_true", help="`[2026-10-14]` 항공을 규칙 해석으로(모델 호출 0) — flight 만")
    parser.add_argument("--compare", action="store_true", help="`[2026-10-14]` 항공 50문장을 규칙과 모델 둘 다 돌려 칸마다 대조(모델 호출 문장 수만큼)")
    args = parser.parse_args()
    if (args.rules or args.compare) and (args.teams or ["flight"]) != ["flight"]:
        parser.error("--rules · --compare 는 flight 만")
    if args.compare:
        return compare(args)
    global PLAIN
    PLAIN = args.plain_context
    if any(team not in ("lodging", "flight") for team in args.teams):
        parser.error("teams 는 lodging · flight 만")
    data = json.loads(CASES.read_text(encoding="utf-8"))
    today, trip = date.fromisoformat(data["today"]), data["trip"]
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    llm = None if args.rules else FilePromptLLM()
    from app.core.settings import get_settings
    settings = get_settings()
    model = "규칙(interpret_rules · 모델 없음)" if args.rules else f"{settings.llm_model} · temperature {settings.llm_temperature} · seed {settings.llm_seed}"
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')} · "
          f"모델 {model} · 기준일 {today} · 반복 {args.repeat}"
          + (" · 달력 없이" if PLAIN else ""))
    for team in args.teams or (["flight"] if args.rules else ["lodging", "flight"]):
        cases = [case for case in data[team] if (not only or case["id"] in only)
                 and (not args.case_set or case.get("set", "base") == args.case_set)]
        field_total, field_ok = Counter(), Counter()
        case_ok, case_total, seconds, unstable = 0, 0, [], []
        print(f"\n== {team} · {len(cases)}문장 · 프롬프트 {sorted(Path('prompts', team).glob('interpret.v*.md'))[0].name}")
        for case in cases:
            runs = []
            for _ in range(args.repeat):
                values, took = asyncio.run(run_case(llm, team, case, today, trip))
                seconds.append(took)
                runs.append(values)
            seen = defaultdict(set)
            for values in runs:
                case_total += 1
                if "error" in values:
                    for field in case["expect"]:
                        field_total[field] += 1
                    print(f"  ✗ {case['id']} {case['text']} — {values['error']}")
                    continue
                wrong = []
                for field, want in case["expect"].items():
                    field_total[field] += 1
                    got = values.get(field)
                    seen[field].add(json.dumps(got, ensure_ascii=False, sort_keys=True))
                    if matches(want, got, field):
                        field_ok[field] += 1
                    else:
                        wrong.append(f"{field} 정답 {json.dumps(want, ensure_ascii=False)} / 받은 {json.dumps(got, ensure_ascii=False)}")
                if wrong:
                    cleared = f" · 근거 없어 비운 칸 {values['_cleared']}" if values["_cleared"] else ""
                    fixed = f" · 서버가 연도 고친 칸 {values['_fixed']}" if values["_fixed"] else ""
                    quotes = (f"\n      모델이 적은 근거 {json.dumps(values['_quotes'], ensure_ascii=False)} · 모델이 적은 missing "
                              f"{json.dumps(values['_missing'], ensure_ascii=False)}")
                    print(f"  ✗ {case['id']} {case['text']}\n      " + "\n      ".join(wrong) + cleared + fixed + quotes)
                else:
                    case_ok += 1
            if args.repeat > 1 and any(len(options) > 1 for options in seen.values()):
                unstable.append(case["id"])
        print(f"-- {team}: 문장 {case_ok}/{case_total} 모두 맞음 · 평균 {sum(seconds) / max(len(seconds), 1):.1f}초 · "
              f"최대 {max(seconds, default=0):.1f}초" + (f" · 반복마다 달랐던 문장 {unstable}" if unstable else ""))
        print("   칸별: " + " · ".join(f"{field} {field_ok[field]}/{field_total[field]}" for field in field_total))


def compare(args):
    """규칙 해석 ↔ 모델 해석 대조 — 문장마다 둘 다 돌려 정답 칸마다 (규칙, 모델, 정답) 을 본다. 규칙만 맞은 것 · 모델만 맞은 것 · 둘 다 틀린 것을
    따로 센다. 모델 응답 원문은 저장하지 않는다."""
    from scripts.try_lodging_team import FilePromptLLM
    from app.core.settings import get_settings
    settings = get_settings()
    data = json.loads(CASES.read_text(encoding="utf-8"))
    today, trip = date.fromisoformat(data["today"]), data["trip"]
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    cases = [case for case in data["flight"] if (not only or case["id"] in only)
             and (not args.case_set or case.get("set", "base") == args.case_set)]
    llm = FilePromptLLM()
    print(f"기기 {platform.node()} · 시각 {datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')} · 규칙(interpret_rules) ↔ "
          f"모델 {settings.llm_model} · temperature {settings.llm_temperature} · seed {settings.llm_seed} · 기준일 {today} · flight {len(cases)}문장")
    both = rules_only = model_only = neither = 0
    agree = disagree = 0
    model_seconds = []
    for case in cases:
        got_rules, _ = asyncio.run(run_case(None, "flight", case, today, trip))
        got_model, took = asyncio.run(run_case(llm, "flight", case, today, trip))
        model_seconds.append(took)
        lines = []
        for field, want in case["expect"].items():
            r_value, m_value = got_rules.get(field), got_model.get(field)
            r_ok, m_ok = matches(want, r_value, field), matches(want, m_value, field)
            same = json.dumps(r_value, ensure_ascii=False, sort_keys=True) == json.dumps(m_value, ensure_ascii=False, sort_keys=True)
            agree += same
            disagree += not same
            if r_ok and m_ok:
                both += 1
            elif r_ok:
                rules_only += 1
            elif m_ok:
                model_only += 1
            else:
                neither += 1
            if not (r_ok and m_ok):
                tag = "둘 다 맞음" if r_ok and m_ok else "규칙만 맞음" if r_ok else "모델만 맞음" if m_ok else "둘 다 틀림"
                lines.append(f"{field}: 규칙 {json.dumps(r_value, ensure_ascii=False)} · 모델 {json.dumps(m_value, ensure_ascii=False)} · "
                             f"정답 {json.dumps(want, ensure_ascii=False)} → {tag}")
        if "error" in got_model:
            lines.append(f"모델 오류 {got_model['error']}")
        if lines:
            print(f"  ✗ {case['id']} {case['text'][:60]}\n      " + "\n      ".join(lines))
    total = both + rules_only + model_only + neither
    print(f"-- 칸 {total}개: 둘 다 맞음 {both} · 규칙만 맞음 {rules_only} · 모델만 맞음 {model_only} · 둘 다 틀림 {neither} · "
          f"규칙 ↔ 모델 값 일치 {agree}/{agree + disagree} · 모델 평균 {sum(model_seconds) / max(len(model_seconds), 1):.1f}초 · 규칙 0.0초")


if __name__ == "__main__":
    main()
