# -*- coding: utf-8 -*-
"""요식 판정 에이전트 평가 자료 v2 — 표본을 늘리고 묶음(slice) · 필수/선호 정답 · 합성 bad 를 넣는다. `[2026-10-18]`

    python -m scripts.dining.make_agent_eval_v2 --source-db dining_rebuild --eval-db dining_eval_v2

★v1(`make_agent_eval.py`, 24건)은 그대로 둔다 — 그때의 기록이다. v1 이 못 재던 것:
  ①표본(필수 체크 63개 — 1건이 2.4%p) ②필수/선호(`required`) 정답 ③식이 · 아이 bad(원장에 「no」가 없다)
★평가 전용 DB(`--eval-db`)를 원본 원장의 **복사본**으로 새로 만들고, 거기에만 합성 「no」 속성을 넣는다
  (`source_code='synthetic_scenario'` · `extract_method='synthetic'` · 문장 「평가용 합성 값 — 실제 아님」). 원본 원장은 읽기만 한다.
★기대 판정은 규칙 도구(`agent_tools.DiningTools`)가 평가 DB 로 낸 값을 얼린다(v1 과 같다). 「골라야 할 체크」와 필수/선호 정답은
  문장 틀을 사람이 정했다 — 필수(「꼭 · 반드시 · 안 되면 못 가요」) · 선호(「가능하면 · 되면 좋겠어요 · 아니어도 괜찮아요」) ·
  부정(「상관없어요」 — 그 조건은 고르면 안 될 체크).
★dev 와 holdout 은 **가게가 겹치지 않는다**. holdout 은 프롬프트를 고칠 때 보지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "eval" / "datasets"
DEV_FILE, HOLDOUT_FILE, MANIFEST = "dining_agent_v2.jsonl", "dining_agent_holdout_v2.jsonl", "dining_agent_v2_manifest.json"
STATE_VERDICT = {"yes": "ok", "limited": "ok", "no": "bad", "unknown": "unknown"}
CONDS = ("dietary", "kids", "payment")
#: 조건 → (에이전트 도구 말, 원장 속성 코드)
ATTR = {"halal": ("halal", "halal"), "vegetarian": ("vegetarian", "vegetarian_menu"),
        "kids": ("kids", "kids_allowed"), "payment": ("card", "card_payment")}
CHECK_OF = {"halal": "dietary", "vegetarian": "dietary", "kids": "kids", "payment": "payment"}
SYNTHETIC_TEXT = "평가용 합성 값 — 실제 아님(eval v2)"

REQUIRED = {
    "halal": ["무슬림이라 반드시 할랄 식당이어야 해요.", "할랄이 아니면 먹을 수 없어요. 꼭 지켜 주세요."],
    "vegetarian": ["채식주의자라 고기는 절대 못 먹어요. 채식 메뉴가 꼭 있어야 해요.", "비건이라 채식 메뉴가 없으면 안 돼요."],
    "kids": ["5살 아이가 같이 가서 아이 입장이 꼭 돼야 해요.", "아이 동반은 필수예요. 노키즈존이면 못 가요."],
    "payment": ["현금이 하나도 없어서 카드 결제가 꼭 돼야 해요.", "카드로만 낼 수 있어요. 카드 안 되면 못 가요."],
}
PREFERRED = {
    "halal": ["가능하면 할랄 식당이면 좋겠어요.", "할랄이면 더 좋고, 아니어도 괜찮아요."],
    "vegetarian": ["채식 메뉴가 있으면 좋겠어요. 없어도 괜찮아요.", "되도록 채식 메뉴가 있는 곳이면 좋아요."],
    "kids": ["아이랑 갈 수도 있어요. 아이 입장이 되면 좋겠어요.", "가능하면 아이 동반이 되는 곳이면 좋아요."],
    "payment": ["카드 되면 편하겠어요. 현금도 조금 있어요.", "웬만하면 카드 결제가 되는 곳이 좋아요."],
}
NEGATED = {
    "halal": "할랄은 상관없어요. 아무거나 잘 먹어요.",
    "vegetarian": "고기 다 잘 먹어요. 채식은 신경 안 써도 돼요.",
    "kids": "이번엔 어른 둘만 가요.",
    "payment": "현금도 넉넉히 챙겨 가요. 결제는 상관없어요.",
}
NOISE = ["매운 거 좋아해요.", "사진 찍기 좋은 곳이면 좋겠어요.", "웨이팅은 길어도 괜찮아요.", ""]
TIMES = [("08:00", "09:00"), ("11:30", "12:30"), ("12:00", "13:00"), ("15:00", "16:00"), ("15:30", "16:30"),
         ("18:00", "19:00"), ("19:30", "21:00"), ("21:30", "22:30"), ("23:00", "23:50")]
#: (묶음, dev 건수, holdout 건수)
#: ☆폐업 묶음은 없다 — 폐업 가게는 원장 이름 찾기(`find_place_by_name`)가 일부러 빼서 found=bad 로 끝나고, 평가 실행기에는
#:   지도 검색이 없어 「폐업 판정」까지 가지 못한다. 제품 경로(접수가 지도로 이은 좌표를 넘김)에서 따로 잰다
PLAN = [("plain_time", 36, 18), ("cond_required", 20, 10), ("cond_preference", 12, 6), ("cond_negated", 6, 3),
        ("multi_meal", 6, 3)]
#: 합성 「no」를 넣을 가게 수(조건마다) — 원장에 「no」가 없는 조건만
SYNTHETIC_NO = {"halal": 10, "vegetarian": 10, "kids": 10}


def recreate_eval_db(admin_dsn: str, source: str, target: str) -> None:
    import psycopg

    if source == target:
        raise SystemExit("평가 DB 이름이 원본과 같다 — 원본 원장에 합성 값을 넣지 않는다")
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{target}"')
        conn.execute(f'CREATE DATABASE "{target}" TEMPLATE "{source}"')


def pools(conn) -> dict[str, list[dict[str, Any]]]:
    """후보 가게 — 실제(합성 아님) · 원장 이름이 하나뿐(이름으로 찾으면 그 가게) · 운영시간 규칙이 있는 곳."""
    rows = conn.execute("""
        SELECT p.place_uid::text, p.name_ko, p.record_status,
               coalesce((SELECT jsonb_object_agg(a.attr_code, a.value_state) FROM dining.v_attribute_active a
                         WHERE a.place_uid = p.place_uid), '{}'::jsonb)
          FROM dining.dn_place p
         WHERE NOT p.is_synthetic
           AND EXISTS (SELECT 1 FROM dining.dn_hours_rule h WHERE h.place_uid = p.place_uid)
           AND (SELECT count(*) FROM dining.dn_place q WHERE q.name_ko = p.name_ko) = 1
         ORDER BY p.place_uid""").fetchall()
    places = [{"uid": uid, "name": name, "status": status, "attrs": attrs} for uid, name, status, attrs in rows]
    return {"all": places, "closed": [p for p in places if p["status"] == "closed"],
            "open": [p for p in places if p["status"] != "closed"]}


def inject_synthetic(conn, places: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    """원장에 「no」가 없는 조건(할랄 · 채식 · 아이)에 합성 「no」를 넣는다 — 그 속성이 비어 있는 가게에만."""
    injected = []
    for cond, count in SYNTHETIC_NO.items():
        code = ATTR[cond][1]
        empty = [p for p in places if code not in p["attrs"] and not p.get("synthetic")]
        for place in rng.sample(empty, count):
            conn.execute("""INSERT INTO dining.dn_attribute (place_uid, source_code, entered_by, verified_at, attr_code,
                                                             value_state, source_text, extract_method, valid_from)
                            VALUES (%s::uuid, 'synthetic_scenario', 'eval_v2', now(), %s, 'no', %s, 'synthetic', current_date)""",
                         (place["uid"], code, SYNTHETIC_TEXT))
            place["attrs"] = {**place["attrs"], code: "no"}
            place["synthetic"] = True
            injected.append({"place_uid": place["uid"], "name": place["name"], "attr_code": code, "value_state": "no"})
    return injected


class Builder:
    def __init__(self, tools_factory, rng: random.Random, first_day: date):
        self.tools_factory, self.rng, self.first_day = tools_factory, rng, first_day

    def day(self) -> str:
        return (self.first_day + timedelta(days=self.rng.randrange(14))).isoformat()

    def meal(self, tools, item_id: str, seq: int, place: dict[str, Any], day: str, times: tuple[str, str],
             conds: dict[str, bool], extra_must: tuple[str, ...] = ()) -> tuple[dict[str, Any], dict[str, Any]]:
        """식사 하나 — 일정 항목과 기대. `conds` = {조건: 필수 여부}."""
        start, end = times
        found = tools.call("find_place", {"name": place["name"]})
        if found.get("place_uid") != place["uid"]:
            raise LookupError(f"{place['name']}: 이름으로 찾은 가게가 다르다 — {found.get('place_uid')}")
        verdicts = {"found": found["verdict"]}
        verdicts["open_at"] = tools.call("check_open_at", {"place_uid": place["uid"], "start": f"{day}T{start}",
                                                          "end": f"{day}T{end}"})["verdict"]
        must, required = ["found", "open_at"], {}
        for cond, is_required in conds.items():
            word = ATTR[cond][0]
            state = tools.call("check_attributes", {"place_uid": place["uid"], "wanted": [word]})["attributes"][word]["state"]
            check = CHECK_OF[cond]
            verdicts[check] = STATE_VERDICT[state]
            must.append(check)
            required[check] = is_required
        for check in extra_must:
            verdicts[check] = tools.call("check_business", {"place_uid": place["uid"]})["verdict"]
            must.append(check)
        item = {"item_id": item_id, "seq": seq, "kind": "dining", "title": f"{place['name']} 식사",
                "start": f"{day}T{start}", "end": f"{day}T{end}", "place": {"name": place["name"]}}
        expect = {"place_uid": place["uid"], "must": must, "must_not": [c for c in CONDS if c not in must],
                  "verdicts": verdicts}
        if required:
            expect["required"] = required
        if place.get("synthetic"):
            expect["synthetic"] = True
        return item, expect

    def case(self, cid: str, slice_name: str, meals: list[tuple[dict[str, Any], tuple[str, str], dict[str, bool]]],
             note: str, extra_must: tuple[str, ...] = ()) -> dict[str, Any]:
        tools = self.tools_factory()
        day = self.day()
        items = [{"item_id": "a1", "seq": 1, "kind": "activity", "title": "오전 관광", "start": f"{day}T10:00",
                  "end": f"{day}T11:00", "place": {"name": "경복궁"}}]
        expect = {}
        for n, (place, times, conds) in enumerate(meals, start=1):
            item, exp = self.meal(tools, f"m{n}", n + 1, place, day, times, conds, extra_must)
            items.append(item)
            expect[item["item_id"]] = exp
        return {"id": cid, "slice": slice_name, "plan": {"date": day, "customer_notes": note, "items": items}, "expect": expect}


def condition_places(pool: list[dict[str, Any]], cond: str) -> dict[str, list[dict[str, Any]]]:
    code = ATTR[cond][1]
    by = {"yes": [], "no": [], "unknown": []}
    for p in pool:
        state = p["attrs"].get(code, "unknown")
        by["yes" if state in ("yes", "limited") else state if state in by else "unknown"].append(p)
    return by


def build_split(builder: Builder, pool: dict[str, list[dict[str, Any]]], prefix: str, counts: dict[str, int]) -> list[dict]:
    rng, used, cases = builder.rng, set(), []

    def take(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        free = [p for p in candidates if p["uid"] not in used]
        if not free:
            raise LookupError("후보 가게가 모자란다")
        place = rng.choice(free)
        used.add(place["uid"])
        return place

    def add(slice_name: str, make) -> None:
        for _ in range(counts[slice_name]):
            for _attempt in range(20):                      # 이름으로 다른 가게가 나오는 후보는 버리고 다시 뽑는다
                try:
                    cases.append(make(f"{prefix}-{len(cases) + 1:03d}"))
                    break
                except LookupError:
                    continue
            else:
                raise SystemExit(f"{slice_name}: 20번 뽑아도 쓸 만한 가게가 없다")

    conds = list(ATTR)
    add("plain_time", lambda cid: builder.case(cid, "plain_time", [(take(pool["open"]), rng.choice(TIMES), {})],
                                                rng.choice(NOISE)))

    def conditioned(slice_name: str, is_required: bool):
        def make(cid):
            cond = conds[len(cases) % len(conds)]
            by = condition_places(pool["open"], cond)
            # 상태가 고루 나오게 yes · no · unknown 을 돌아가며 — 「no」가 없는 조건은 합성 값이 들어간 가게
            state = ("yes", "no", "unknown")[(len(cases) // len(conds)) % 3]
            place = take(by[state] or by["unknown"])
            text = rng.choice((REQUIRED if is_required else PREFERRED)[cond])
            return builder.case(cid, slice_name, [(place, rng.choice(TIMES[1:7]), {cond: is_required})],
                                f"{text} {rng.choice(NOISE)}".strip())
        return make

    add("cond_required", conditioned("cond_required", True))
    add("cond_preference", conditioned("cond_preference", False))
    add("cond_negated", lambda cid: builder.case(cid, "cond_negated", [(take(pool["open"]), rng.choice(TIMES[1:7]), {})],
                                                  NEGATED[conds[len(cases) % len(conds)]]))

    def multi(cid):
        cond = conds[len(cases) % len(conds)]
        is_required = len(cases) % 2 == 0
        text = rng.choice((REQUIRED if is_required else PREFERRED)[cond])
        meals = [(take(pool["open"]), ("12:00", "13:00"), {cond: is_required}),
                 (take(pool["open"]), ("18:30", "19:30"), {cond: is_required})]
        if len(cases) % 3 == 0:
            meals.append((take(pool["open"]), ("21:30", "22:30"), {cond: is_required}))
        return builder.case(cid, "multi_meal", meals, text)

    add("multi_meal", multi)
    return cases


def main(argv: list[str] | None = None) -> int:
    import psycopg

    from app.domains.travel_ops.instances.dining.agent_tools import DiningTools

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--host", default="postgresql://postgres@127.0.0.1:5433")
    parser.add_argument("--source-db", default="dining_rebuild")
    parser.add_argument("--eval-db", default="dining_eval_v2")
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument("--first-day", default="2026-11-02", help="일정 날짜 범위의 첫날(14일)")
    args = parser.parse_args(argv)

    recreate_eval_db(f"{args.host}/postgres", args.source_db, args.eval_db)
    eval_dsn = f"{args.host}/{args.eval_db}"
    rng = random.Random(args.seed)
    with psycopg.connect(eval_dsn, autocommit=True) as conn:
        pool = pools(conn)
        injected = inject_synthetic(conn, pool["open"], rng)

    @contextmanager
    def connect():
        with psycopg.connect(eval_dsn, autocommit=True) as conn:
            yield conn

    # dev 와 holdout 은 가게가 겹치지 않게 후보를 반으로 나눈다(합성 값이 든 가게 · 폐업 가게도 각각 반씩)
    def halves(places):
        shuffled = places[:]
        rng.shuffle(shuffled)
        return shuffled[: len(shuffled) // 2], shuffled[len(shuffled) // 2:]

    split = {"dev": {}, "holdout": {}}
    for key in ("open", "closed"):
        a, b = halves(pool[key])
        split["dev"][key], split["holdout"][key] = a, b
    builder = Builder(lambda: DiningTools(connect, max_calls=1000), rng, date.fromisoformat(args.first_day))
    out = {}
    for name, prefix, file, column in (("dev", "DG2", DEV_FILE, 1), ("holdout", "DGH2", HOLDOUT_FILE, 2)):
        cases = build_split(builder, split[name], prefix, {s[0]: s[column] for s in PLAN})
        built = {"on": date.today().isoformat(), "ledger": args.eval_db, "source_ledger": args.source_db, "seed": args.seed}
        text = "".join(json.dumps({**case, "built": built}, ensure_ascii=False) + "\n" for case in cases)
        (OUT / file).write_text(text, encoding="utf-8", newline="\n")
        verdicts = [(check, v) for c in cases for e in c["expect"].values() for check, v in e["verdicts"].items()
                    if check in e["must"]]
        out[name] = {"file": file, "sha": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], "cases": len(cases),
                     "must_checks": len(verdicts),
                     "by_slice": {s: sum(c["slice"] == s for c in cases) for s, *_ in PLAN},
                     "by_verdict": {f"{k}={v}": verdicts.count((k, v)) for k, v in sorted(set(verdicts))},
                     "required_labels": sum(len(e.get("required", {})) for c in cases for e in c["expect"].values())}
        print(name, json.dumps(out[name], ensure_ascii=False))
    manifest = {"made": date.today().isoformat(), "seed": args.seed, "source_ledger": args.source_db,
                "eval_ledger": args.eval_db, "synthetic_attributes": injected, "splits": out,
                "plan": [{"slice": s, "dev": d, "holdout": h} for s, d, h in PLAN]}
    (OUT / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
