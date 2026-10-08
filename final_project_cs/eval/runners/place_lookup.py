# -*- coding: utf-8 -*-
"""장소 찾기 평가 — 고정 시험지(`eval/datasets/place_lookup_v1.jsonl`)로 접수의 장소 찾기를 잰다. `[2026-10-07]`

    python -m eval.runners.place_lookup --label v0-develop [--kakao live|off] [--out REPORT.json]

★무엇을 재나
    입력은 일정 글(「2026-10-21 서울 하루」 + 시험지의 줄들), 결과는 접수가 낸 `items[n].place` 줄이다.
    develop · role-manager 의 접수가 **같은 모양의 줄**을 내므로 같은 시험지로 두 판을 잰다(판마다 조립만 다르다 — `ADAPTERS`).
    채점 대상은 항목 하나(`target`)다. 앞 항목은 위치 단서일 뿐 채점하지 않는다.

★판정(케이스마다 하나)
    correct_confirmed   맞는 곳을 확정(확인 표시 없음)
    correct_review      맞는 곳을 골랐고 확인 필요로 표시
    correct_abstain     고르지 않아야 하는 경우(이름이 아닌 말 · 서울 밖)에 고르지 않음
    wrong_review        틀린 곳 — 그래도 확인 필요로 표시했다(고객이 고칠 기회가 있다)
    wrong_confirmed     ★틀린 곳을 확정 · 또는 확인이 꼭 필요한 곳(위치 단서 없는 체인)을 확인 없이 확정 — **가장 나쁘다. 목표 0**
    not_found           고르지 못함
    blocked             외부 조회가 막혀 고르지 못함(없는 곳이라는 뜻이 아니다 — 점수에서 따로 센다)

★맞는 곳인가(`expect`)
    accept      정규화한 이름에 이 조각 중 하나가 들어 있다(「토속촌삼계탕」 ⊂ 「토속촌삼계탕 본점」)
    brand       정규화한 이름에 이 조각이 들어 있다 — 체인 · 메뉴(「스타벅스」 · 「국밥」)
    near        고른 곳이 `point`(시험지에 고정한 기준 좌표)에서 `max_km` 안. 앞 항목이 무엇으로 찾혔는지와 무관하다
    kind        항목 종류(`items[n].kind` 줄 → 없으면 장소의 kind)가 이것이어야 한다
    must_review 맞는 곳이어도 확인 표시가 없으면 wrong_confirmed(어느 지점인지 원문이 말하지 않는다)
    no_pick     고르지 않는 것이 정답 · or_no_pick 고르지 않아도 정답(골랐다면 accept 로 본다)

★카카오는 **실제로 부른다**(`--kakao live`). 응답은 저장하지 않는다 — 어댑터 약관(`kakao_local.py` 「응답을 담아 두지 않는다」).
  그래서 같은 코드라도 날이 바뀌면 카카오 결과가 바뀔 수 있다. 보고서의 `env` 에 날짜 · 판 · DB 를 남겨 비교할 때 본다.
  `--kakao off` 는 카카오 없이 잰다(카카오가 빠졌을 때 얼마나 버티는지).
★보고서에는 고른 곳의 이름 · 좌표(소수 넷째 자리)만 남긴다 — 접수가 여행에 싣는 것과 같은 범위다. 카카오 후보 목록은 남기지 않는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "datasets" / "place_lookup_v1.jsonl"
HEADER = "2026-10-21 서울 하루"
TODAY = date(2026, 10, 7)

LABELS = ("correct_confirmed", "correct_review", "correct_abstain",
          "wrong_review", "wrong_confirmed", "not_found", "blocked", "error")
#: ★`[2026-10-08]` `error` — 접수 조립이 죽은 케이스. 전에는 not_found 로 셌다 — 부품 이름이 바뀌어 34건이 전부 죽었는데
#:   「34건 못 찾음」으로 보였다(조용한 실패). 하나라도 있으면 실행이 실패로 끝난다(`main`).
CORRECT = frozenset({"correct_confirmed", "correct_review", "correct_abstain"})


# ── 시험지 ─────────────────────────────────────────────────────
def load_cases(path: Path = DATASET) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def case_text(case: dict[str, Any]) -> str:
    return "\n".join([HEADER, *case["lines"]])


def dataset_digest(path: Path = DATASET) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ── 채점 ───────────────────────────────────────────────────────
def normalize(name: str | None) -> str:
    return re.sub(r"[^가-힣a-z0-9]", "", (name or "").lower())


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    p = math.pi / 180
    h = (math.sin((b[0] - a[0]) * p / 2) ** 2
         + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def items_from_rows(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """접수 줄 → 항목별 {title, place, review, note, evidence, kind}."""
    items: dict[int, dict[str, Any]] = defaultdict(dict)
    for row in rows:
        field = row.get("field") or ""
        match = re.match(r"items\[(\d+)\]\.(\w+)$", field)
        if not match:
            continue
        index, name = int(match.group(1)), match.group(2)
        if name == "title":
            items[index]["title"] = row.get("value")
        elif name == "kind":
            items[index]["kind"] = row.get("value")
        elif name == "place":
            items[index].update({"place": row.get("value"), "review": bool(row.get("needs_review")),
                                 "note": row.get("note"), "evidence": row.get("evidence") or {}})
    return dict(items)


def score_case(case: dict[str, Any], items: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """케이스 하나의 판정. 접수 결과에서 `target` 항목만 본다."""
    expect = case["expect"]
    item = items.get(case["target"], {})
    place = item.get("place") or None
    review = bool(item.get("review"))
    evidence = item.get("evidence") or {}
    out: dict[str, Any] = {"id": case["id"], "group": case["group"], "input": case["lines"][case["target"]],
                           "place": None, "source": evidence.get("source"), "method": evidence.get("method"),
                           "kind": item.get("kind") or (place or {}).get("kind"), "review": review,
                           "km": None, "note": item.get("note"), "blocked": evidence.get("blocked") or [],
                           "checks": {}}
    if not place or not place.get("name"):
        # ★막혀서 못 고른 것은 「고르지 않음」이 아니다 — or_no_pick 이어도 blocked. no_pick 은 막혔어도 고르지 않은 것이 정답이다
        if expect.get("no_pick"):
            out["label"] = "correct_abstain"
        elif out["blocked"]:
            out["label"] = "blocked"
        elif expect.get("or_no_pick"):
            out["label"] = "correct_abstain"
        else:
            out["label"] = "not_found"
        return out

    name = place["name"]
    out["place"] = name
    lat, lng = place.get("latitude"), place.get("longitude")
    point = (float(lat), float(lng)) if lat is not None and lng is not None else None
    if point:
        out["at"] = [round(point[0], 4), round(point[1], 4)]

    key, checks = normalize(name), {}
    if expect.get("no_pick"):
        checks["no_pick"] = False
    if "accept" in expect:
        checks["accept"] = any(normalize(a) in key for a in expect["accept"])
    if "brand" in expect:
        checks["brand"] = normalize(expect["brand"]) in key
    if "near" in expect:
        ref = tuple(expect["near"]["point"])
        if point is None:
            checks["near"] = False
        else:
            out["km"] = round(km(ref, point), 2)
            checks["near"] = out["km"] <= expect["near"]["max_km"]
    if "kind" in expect:
        checks["kind"] = out["kind"] == expect["kind"]
    out["checks"] = checks

    right = all(checks.values()) if checks else False
    if right:
        if expect.get("must_review") and not review:
            out["label"] = "wrong_confirmed"
            out["why_wrong"] = "확인이 필요한 곳(어느 지점인지 원문에 없음)을 확인 없이 확정"
        else:
            out["label"] = "correct_review" if review else "correct_confirmed"
    else:
        out["label"] = "wrong_review" if review else "wrong_confirmed"
        out["why_wrong"] = ", ".join(k for k, ok in checks.items() if not ok)
    return out


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def ratio(num: int, den: int) -> dict[str, Any]:
        return {"num": num, "den": den, "rate": round(num / den, 3) if den else None}

    total = len(results)
    counts = Counter(r["label"] for r in results)
    by_group: dict[str, Any] = {}
    for group in sorted({r["group"] for r in results}):
        rows = [r for r in results if r["group"] == group]
        by_group[group] = ratio(sum(r["label"] in CORRECT for r in rows), len(rows))
    return {
        "accuracy": ratio(sum(counts[l] for l in CORRECT), total),
        "wrong_confirmed": ratio(counts["wrong_confirmed"], total),
        "wrong_review": ratio(counts["wrong_review"], total),
        "not_found": ratio(counts["not_found"], total),
        "blocked": ratio(counts["blocked"], total),
        "labels": {label: counts.get(label, 0) for label in LABELS},
        "by_group": by_group,
    }


# ── 판마다 조립 ────────────────────────────────────────────────
def _develop_reader(kakao_mode: str, tour_mode: str = "off") -> Callable[[str], list[dict[str, Any]]]:
    """develop 의 접수 조립을 그대로 쓴다 — `trip_api` 의 읽기 경로와 같은 부품.
    ★`[2026-10-08]` develop 이 `app/domains/travel_ops` 로 옮겼다(통합 0bf4331). 바뀐 조립 — `trip_api.web_intake_start` 와 같다:
      관광지 CSV 대체(`_CsvFallbackTour`)가 빠지고 관광공사는 `place_factory`(실제 호출 — `--tour live` 일 때만),
      카카오 근처 힌트 감싸개(`_KakaoNearHint`)가 빠지고 근처 기준은 접수가 직접 고른다(`pipeline._near_hint`),
      이름 없는 줄 판정에 지명 사전(`areas`)을 넘긴다."""
    from app.core.settings import get_settings
    from app.infrastructure.db.session import get_connection
    from app.domains.travel_ops.entry import trip_api
    from app.domains.travel_ops.components.intake.areas import areas_for
    from app.domains.travel_ops.components.intake.pipeline import _our_places, load_aliases, read_source

    tenant = get_settings().tenant_id
    with get_connection() as conn:
        our_places = _our_places(conn, tenant)
        aliases = load_aliases(conn, tenant, None)          # 기본 별칭만 — 고객이 고친 별칭은 그 고객에게만 쓴다
        areas = areas_for(conn, tenant)                     # 지명 사전 — 이름 없는 줄(「성수 식당」) 판정에 쓴다
    kakao_raw = None
    if kakao_mode == "live":
        from app.composition import build_kakao_local
        kakao_raw = build_kakao_local()
        if kakao_raw is None:
            raise SystemExit("카카오 키가 없다 — --kakao off 로 재거나 .env.apikeys 를 확인한다")

    tour = None
    if tour_mode == "live":
        from app.domains.travel_ops.ports.data_sources.base import build_travel_sources
        tour = build_travel_sources(get_settings()).place
        if tour is None:
            raise SystemExit("관광공사 키가 없다 — --tour off 로 잰다")

    def read(text: str) -> list[dict[str, Any]]:
        ctx = trip_api._PlaceCtx()                         # 케이스마다 새로 — 앞 케이스의 좌표가 넘어오지 않게
        return read_source(text, chat=None, today=TODAY, our_places=our_places, aliases=aliases, areas=areas,
                           tour=tour, kakao=kakao_raw, dining=trip_api._dining_lookup(ctx))
    read.fingerprint = {"tour": tour_mode, "places": len(our_places), "aliases": len(aliases),
                        "areas": len(getattr(areas, "_by_key", {}))}   # type: ignore[attr-defined]
    return read


ADAPTERS: dict[str, Callable[..., Callable[[str], list[dict[str, Any]]]]] = {"domains": _develop_reader}


def _detect_layout() -> str:
    # ★`[2026-10-08]` 판 이름은 폴더 구조 — 10-07 보고서의 「develop」은 옛 구조(`app/modules/travel_ops`)다
    if (ROOT / "app" / "domains" / "travel_ops" / "components" / "intake" / "pipeline.py").exists():
        return "domains"
    raise SystemExit("이 판의 접수 조립을 모른다 — ADAPTERS 에 판을 더한다")


def _env(layout: str, kakao_mode: str, reader: Any) -> dict[str, Any]:
    def git(*args: str) -> str | None:
        try:
            return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:   # noqa: BLE001
            return None

    db = os.environ.get("ACOP_DATABASE_URL", "")
    ledger = None
    try:
        from app.infrastructure.db.session import get_connection
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('dining.dn_place') IS NOT NULL")
            if cur.fetchone()[0]:
                cur.execute("SELECT count(*) FROM dining.dn_place WHERE record_status <> 'closed'")
                ledger = cur.fetchone()[0]
    except Exception:   # noqa: BLE001
        pass
    return {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "today": TODAY.isoformat(),
            "layout": layout, "kakao": kakao_mode, "llm": "off",
            "git_commit": git("rev-parse", "--short", "HEAD"), "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "git_dirty": bool(git("status", "--porcelain", "--", "app")),
            "db": db.rsplit("/", 1)[-1] if db else None, "ledger_open_places": ledger,
            **getattr(reader, "fingerprint", {})}


def run(*, label: str, kakao_mode: str, tour_mode: str = "off", dataset: Path = DATASET) -> dict[str, Any]:
    cases = load_cases(dataset)
    layout = _detect_layout()
    reader = ADAPTERS[layout](kakao_mode, tour_mode)
    results = []
    for case in cases:
        try:
            rows = reader(case_text(case))
            results.append(score_case(case, items_from_rows(rows)))
        except Exception as exc:   # noqa: BLE001 — 한 케이스가 죽어도 나머지는 잰다. 죽은 것은 error 로 따로 센다
            results.append({"id": case["id"], "group": case["group"], "input": case["lines"][case["target"]],
                            "label": "error", "error": f"{type(exc).__name__}: {exc}"[:200]})
        print(f"{results[-1]['id']} {results[-1]['label']:<18} {results[-1].get('input')} → {results[-1].get('place')}",
              file=sys.stderr)
    return {"eval": "place_lookup", "dataset": dataset.name, "dataset_sha": dataset_digest(dataset), "label": label,
            "env": _env(layout, kakao_mode, reader), "summary": summarize(results), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--label", required=True, help="이 실행의 이름(예: v0-develop)")
    parser.add_argument("--kakao", choices=("live", "off"), default="live")
    parser.add_argument("--tour", choices=("live", "off"), default="off",
                        help="관광공사 실제 호출 — 운영과 같은 조립. 기본은 끔(호출 한도 · 같은 결과)")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = run(label=args.label, kakao_mode=args.kakao, tour_mode=args.tour, dataset=args.dataset)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))
    errors = report["summary"]["labels"].get("error", 0)
    if errors:
        print(f"조립이 죽은 케이스 {errors}건 — 점수로 쓰지 않는다(results[].error)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
