# -*- coding: utf-8 -*-
"""안내 문구의 **언어별 생성 캐시 재사용률**을 운영 경로로 재본다 — v11 §6-B · 결정 14.

    python -m scripts.measure_notice_phrases
    python -m scripts.measure_notice_phrases --days 1,3,7 --locales zh-TW,en,ja
    python -m scripts.measure_notice_phrases --days 3 --keep       # 시험 테넌트 남기기

★`[2026-09-22]` 캐시를 넣을 때 효과를 **시험 안에서만** 쟀다(「같은 언어 안내 4건 중 1건만
  모델을 탄다」). 이 스크립트는 같은 것을 **운영 경로**로 잰다 —

    ① 여러 날짜·여러 항목을 가진 여행을 언어마다 하나씩 만든다(확정 시나리오 하루를
       날짜를 밀어 여러 날로 늘린다)
    ② 안내 되잡기 작업(`TripReminders.tick`)을 **시각을 옮겨 가며** 여러 번 돌려
       바깥함(`outbox`)에 안내를 쌓는다 — 운영에서 안내가 만들어지는 바로 그 경로다
    ③ 쌓인 안내를 디스코드 발송기(`DiscordWebhook`)에 흘리고 **모델 호출 수 / 안내 수**를 센다

★★**실제 디스코드로 보내지 않는다.** 전송기(`transport`)도 번역기(`translator`)도 가짜다.
  웹훅 주소는 쓰지 않는다 — 발송기가 빈 주소를 거부하므로(`NoticeNotConfigured`) **가짜
  자리표시 주소**를 넣는다. 가짜 전송기가 받으므로 밖으로 나가는 요청은 없다.

★**가짜 번역기가 하는 일**은 모델의 *계약*만 흉내 낸다 — 자리(`{leave}`)를 그대로 두고
  언어 표시를 붙인다. 번역 *품질*은 재지 않는다(이 측정이 보는 것은 호출 수다).

★**값이 섞이지 않는지도 여기서 본다**(§4). 쌓인 안내마다 캐시를 탄 문장과, 캐시를 안 쓰고
  그 안내만 따로 채운 문장을 **글자까지 대조**한다. 하나라도 어긋나면 그 자체가 결함이므로
  결과에 `mismatches` 로 싣고 종료 코드 1 로 끝낸다.

★**이 수치가 말하지 못하는 것**은 리포트 §6 에 적는다 — 한 줄로: 이것은 **재생**이지
  실제 운영 트래픽이 아니다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

# ★`python scripts/…` 로 바로 불러도 돌게 저장소 뿌리를 얹는다 — `-m` 으로만 되면
#   쓰는 사람이 `ModuleNotFoundError` 를 먼저 만난다(실제로 만났다).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "app" / "modules" / "travel_ops" / "scenarios" / "seoul_day_taiwan_friends.json"
DEFAULT_OUT = ROOT / "wiki" / "records" / "evidence" / "notice_phrase_reuse.json"
KST = ZoneInfo("Asia/Seoul")

#: ★보낼 곳. **가짜다** — 가짜 전송기가 받아서 밖으로 나가지 않는다. 진짜 주소는 어디에도 적지 않는다.
FAKE_WEBHOOK = "https://webhook.invalid/none"

HHMM = re.compile(r"\b\d{2}:\d{2}\b")


class Clock:
    """되잡기 작업에 주는 시계 — 옮겨 가며 여러 번 돌린다."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class CalmRouteEvents:
    """경로 사건 소스 대역 — **사건이 없는 평상시**.

    ★`None` 을 돌려주면 「못 읽었다」(결정 15 의 치명)가 되어 출발 안내가 아예 안 만들어진다.
      평상시는 **빈 매핑**이다 — 그래야 계획한 수단으로 「가는 방법」이 붙은 안내가 나간다.
    """

    def affecting(self, targets: list[str]) -> dict[str, Any]:
        return {}


class FakeTranslator:
    """모델 자리. **부른 횟수를 센다.**

    ★계약만 흉내 낸다 — 자리(`{name}`)를 그대로 두고 개수도 안 바꾼다. 앞에 언어 표시를
      붙여 **어느 언어의 틀을 썼는지**가 결과 문장에 남게 한다(언어가 섞이면 바로 보인다).
    """

    def __init__(self) -> None:
        self.calls = 0
        self.seen: list[tuple[str, str]] = []

    def __call__(self, template: str, locale: str) -> str:
        self.calls += 1
        self.seen.append((locale, template))
        return translated_form(template, locale)


def translated_form(template: str, locale: str) -> str:
    """가짜 번역의 **결과 모양** — 캐시를 안 타는 대조군도 같은 것을 써야 비교가 된다."""
    return f"[{locale}] " + template


def fake_transport(sent: list[dict[str, str]]):
    """가짜 전송기 — 보내는 대신 받아 둔다. ★밖으로 나가는 요청이 없다."""
    import httpx

    def post(url: str, json: dict[str, Any]) -> httpx.Response:
        sent.append({"url": url, "content": json["content"]})
        return httpx.Response(204)

    return post


# ── 여행 만들기 ────────────────────────────────────────────────────────────
def _seed(tenant: str, data: dict[str, Any], *, locales: list[str], days: int):
    """확정 시나리오의 장소·하루 일정을 이 테넌트에 넣고, **하루를 `days` 일로 늘린다.**

    ★날짜만 미는 것이 아니라 **하루마다 시각을 조금 옮기고 제목에 몇일차인지 붙인다.**
      안 그러면 1일차 10:50 과 2일차 10:50 이 글자까지 같아져서 **값이 섞여도 안 보인다** —
      §4 의 대조가 아무것도 증명하지 못하게 된다.
    """
    from app.infrastructure.db.session import get_connection
    from app.modules.travel_ops.itinerary import Item, TripStore

    day0 = date.fromisoformat(str(data["trip"]["date"]))

    def at(offset_days: int, hhmm: str) -> datetime:
        hour, minute = (int(part) for part in hhmm.split(":"))
        moment = datetime.combine(day0 + timedelta(days=offset_days), time(hour, minute), tzinfo=KST)
        return moment + timedelta(minutes=7 * offset_days)      # 하루마다 7분씩 민다

    with get_connection() as conn:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO tenants (tenant_id,name) VALUES (%s,%s)",
                        (tenant, "notice phrase measurement"))
            cur.execute("INSERT INTO customers (tenant_id,external_id) VALUES (%s,%s) "
                        "RETURNING customer_id", (tenant, "measure"))
            customer = cur.fetchone()[0]
            place_ids = {}
            for place in data["places"]:
                cur.execute(
                    "INSERT INTO places (tenant_id,name,kind,latitude,longitude,weather_sensitive,"
                    "attributes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING place_id",
                    (tenant, place["name"], place["kind"], place["lat"], place["lon"],
                     place["weather_sensitive"], json.dumps(place["attributes"], ensure_ascii=False)))
                place_ids[place["key"]] = cur.fetchone()[0]

        store = TripStore(tenant)
        trips: dict[str, Any] = {}
        for locale in locales:
            items, seq = [], 0
            for offset in range(days):
                for spec in data["items"]:
                    seq += 1
                    detail = dict(spec.get("detail", {}))
                    if "route" in spec:
                        detail |= {"route": spec["route"], "route_def": data["routes"][spec["route"]]}
                    items.append(Item(item_id=uuid4(), seq=seq, kind=spec["kind"],
                                      title=f"{spec['title']} · {offset + 1}일차",
                                      place_id=place_ids.get(spec.get("place")),
                                      starts_at=at(offset, spec["start"]),
                                      ends_at=at(offset, spec["end"]), detail=detail))
            with conn.transaction():
                trip_id, _ = store.create_trip(
                    conn, customer_id=customer, title=f"{data['trip']['title']} ({days}일 · {locale})",
                    locale=locale, party_size=data["trip"]["party_size"], items=items,
                    constraints=dict(data["trip"].get("constraints") or {}))
            trips[locale] = {"trip_id": trip_id, "items": items}
    return store, trips


def _tick_moments(items, rules) -> list[datetime]:
    """되잡기 작업을 돌릴 시각 — 안내가 나가야 하는 바로 그 순간들.

    ★5분 격자로 하루를 다 훑는 것과 결과가 같고 훨씬 싸다. 시각은 `plan_reminders` 의
      조건 그대로 계산한다(전날 저녁 · 하루 시작 · 이동 항목마다 출발).
    """
    by_day: dict[date, list] = {}
    for item in sorted(items, key=lambda i: (i.starts_at, i.seq)):
        by_day.setdefault(item.starts_at.astimezone(KST).date(), []).append(item)
    moments: list[datetime] = []
    for day, day_items in by_day.items():
        first = day_items[0]
        if rules.eve_hour is not None:
            moments.append(datetime.combine(day - timedelta(days=1), time(rules.eve_hour), tzinfo=KST))
        moments.append(first.starts_at - rules.day_start_lead)
        moments += [move.starts_at
                    for move in day_items if move.kind == "mobility"]
    return sorted(moments)


def _collect_notices(tenant: str) -> list[dict[str, Any]]:
    """바깥함에 쌓인 안내 — 배달 루프가 읽는 것과 같은 줄이다."""
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT dedupe_key, payload_json FROM outbox WHERE tenant_id=%s "
                    "AND topic='trip.notice' ORDER BY available_at, dedupe_key", (tenant,))
        return [{"dedupe_key": key, "payload": payload} for key, payload in cur.fetchall()]


# ── 흘려보내며 세기 ────────────────────────────────────────────────────────
def broken_cache():
    """★**일부러 깨뜨린 캐시** — 틀이 아니라 **완성 문장**을 담는다.

    제품 코드는 한 줄도 안 고친다. 발송기가 캐시를 주입받으므로(`phrases=`) 여기서만 바꿔 끼운다.
    이것을 흘렸을 때 §4 의 대조가 **울어야** 그 대조가 무엇을 증명하는 것이 된다 —
    안 울면 「값이 안 섞였다」는 말이 아무 근거가 없다(`CLAUDE.md` §1).
    """
    from app.infrastructure.notify.phrase import PhraseCache

    class FilledSentenceCache(PhraseCache):
        def localize(self, phrase, locale, translate):
            key = (phrase.template, locale)
            cached = self._entries.get(key) if phrase.cacheable else None
            if cached is not None:
                self.hits += 1
                return cached                       # ← 앞 알림의 시각·장소가 딸려 온다
            self.misses += 1
            filled = phrase.with_translation(translate(phrase.template, locale))
            if phrase.cacheable:
                self._put(key, filled)
            return filled

    return FilledSentenceCache()


def _deliver(notices: list[dict[str, Any]], *, cache_path: Path | None = None,
             preload: bool = False, cache: Any = None) -> dict[str, Any]:
    """쌓인 안내를 발송기에 흘리고 **모델 호출 수 / 안내 수**를 센다.

    ★발송기는 하나다 — 운영에서도 배달 루프 한 프로세스가 모든 언어의 안내를 보낸다.
      캐시 열쇠가 `(틀, 언어)` 라 언어가 섞여도 서로를 밀어내지 않는다.

    `preload=True` 면 **앞 실행이 남긴 파일을 읽고 시작한다** — 프로세스가 죽었다 다시 뜬 자리다.
    """
    from app.infrastructure.notify.discord import DiscordWebhook, phrase_of
    from app.infrastructure.notify.phrase import PhraseCache
    from app.infrastructure.notify.translate import is_korean

    cache = cache if cache is not None else PhraseCache(path=cache_path)
    preloaded = cache.load() if preload else 0
    translator, sent = FakeTranslator(), []
    webhook = DiscordWebhook(FAKE_WEBHOOK, transport=fake_transport(sent), translator=translator,
                             phrases=cache)

    per_locale: dict[str, dict[str, int]] = {}
    per_kind: dict[str, dict[str, int]] = {}
    mismatches: list[dict[str, Any]] = []
    for notice in notices:
        payload = notice["payload"]
        locale, kind = str(payload.get("locale")), str(payload.get("kind"))
        before = translator.calls
        webhook({"topic": "trip.notice", "payload": payload})
        called = translator.calls - before
        for table, key in ((per_locale, locale), (per_kind, kind)):
            row = table.setdefault(key, {"notices": 0, "model_calls": 0})
            row["notices"] += 1
            row["model_calls"] += called
        # ★§4 — 캐시를 탄 문장과 「이 안내만 따로 채운 문장」을 글자까지 대조한다.
        phrase = phrase_of(payload)
        # ★한국어는 옮기지 않는다(`translate.is_korean`) — 원문 그대로가 정답이다.
        expected = (phrase.render() if is_korean(locale)
                    else phrase.with_translation(translated_form(phrase.template, locale)))
        content = sent[-1]["content"]
        if content != expected:
            mismatches.append({"dedupe_key": notice["dedupe_key"], "kind": kind, "locale": locale,
                               "expected": _masked(expected), "got": _masked(content)})
        elif set(HHMM.findall(content)) != set(HHMM.findall(phrase.render())):
            mismatches.append({"dedupe_key": notice["dedupe_key"], "kind": kind, "locale": locale,
                               "reason": "시각이 한국어 원문과 다르다", "got": _masked(content)})
    if cache_path is not None and not preload:
        cache.save()
    stats = cache.stats()
    total = stats["hits"] + stats["misses"]
    return {"notices": len(notices), "model_calls": stats["misses"], "reused": stats["hits"],
            "denominator": total, "reuse_rate": (stats["hits"] / total) if total else None,
            "cache_entries": stats["entries"], "preloaded_entries": preloaded,
            "rejected_translations": stats["rejected"],
            "translation_failures": webhook.translation_failures,
            "per_locale": per_locale, "per_kind": per_kind, "mismatches": mismatches,
            "longest_content": max((len(row["content"]) for row in sent), default=0),
            "sample": _masked(sent[0]["content"]) if sent else None}


def _masked(content: str) -> str:
    """보기용 표본에서 **계획서 토큰을 지운다** — 기록에 남길 값이 아니다."""
    return re.sub(r"\?t=[0-9a-f]+", "?t=…", content)


def _change_notice_contrast(notices: list[dict[str, Any]], *, locales: list[str]) -> dict[str, Any]:
    """대조군 — **①변경 통지**(`text` 만 있는 통지)는 담아 두지 않는다(`cacheable=False`).

    ★합성이다. 안내에서 나온 문장을 `text` 한 칸에 담아 ①의 모양으로 만든 것이고,
      실제 변경 통지를 재생한 것이 아니다. 여기서 보려는 것은 **호출 수**뿐이다.
    """
    from app.infrastructure.notify.discord import DiscordWebhook
    from app.infrastructure.notify.phrase import PhraseCache

    translator, sent = FakeTranslator(), []
    webhook = DiscordWebhook(FAKE_WEBHOOK, transport=fake_transport(sent), translator=translator,
                             phrases=PhraseCache())
    made = 0
    for notice in notices:
        payload = notice["payload"]
        if str(payload.get("locale")) not in locales:
            continue
        webhook({"topic": "trip.notice",
                 "payload": {"locale": payload["locale"], "text": str(payload["text"]),
                             "version": payload.get("version")}})
        made += 1
    return {"notices": made, "model_calls": translator.calls,
            "reuse_rate": 0.0 if made else None}


def run(*, days: int, locales: list[str], keep: bool, workdir: Path) -> dict[str, Any]:
    from app.modules.travel_ops.case_engine import cleanup_tenant
    from app.infrastructure.db.session import get_connection
    from app.modules.travel_ops.plan_link import plan_url
    from app.modules.travel_ops.trip_reminders import ReminderRules, TripReminders

    data = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    tenant = "phrase_" + uuid4().hex[:10]
    rules = ReminderRules.from_guardrails()
    out: dict[str, Any] = {"days": days, "locales": list(locales), "tenant": tenant,
                           "rules": {"day_start_lead_min": rules.day_start_lead.total_seconds() / 60,
                                     "eve_hour": rules.eve_hour}}
    try:
        store, trips = _seed(tenant, data, locales=locales, days=days)
        out["items_per_trip"] = len(trips[locales[0]]["items"])
        clock = Clock(datetime.now(tz=KST))
        reminders = TripReminders(store=store, connection_factory=get_connection, clock=clock,
                                  route_events=CalmRouteEvents(), rules=rules,
                                  link=lambda trip_id: plan_url(tenant, trip_id))
        moments = _tick_moments(trips[locales[0]]["items"], rules)
        ticks = {"count": len(moments), "sent": 0, "already": 0, "held": 0, "fatal": 0, "no_route": 0}
        for moment in moments:
            clock.now = moment
            result = reminders.tick()
            ticks["sent"] += len(result.sent)
            ticks["already"] += result.already
            ticks["held"] += len(result.held)
            ticks["fatal"] += len(result.fatal)
            ticks["no_route"] += result.no_route
        out["ticks"] = ticks

        notices = _collect_notices(tenant)
        phrasebook = workdir / f"phrasebook_{days}d_{tenant}.json"
        phrasebook.unlink(missing_ok=True)                 # ★찬 캐시로 시작한다
        out["cold"] = _deliver(notices, cache_path=phrasebook)
        # ★프로세스가 죽었다 다시 뜬 자리 — 파일로 이어 쓰면 모델을 한 번도 안 부르는지 본다.
        out["warm"] = _deliver(notices, cache_path=phrasebook, preload=True)
        out["change_notice_contrast"] = _change_notice_contrast(notices, locales=locales)
        # ★대조가 무엇을 증명하는지 보이기 — 일부러 완성 문장을 담는 캐시로 같은 안내를 흘린다.
        broken = _deliver(notices, cache=broken_cache())
        out["self_check"] = {"what": "완성 문장을 담는 캐시로 같은 안내를 흘렸을 때",
                             "notices": broken["notices"],
                             "mismatches": len(broken["mismatches"]),
                             "example": broken["mismatches"][0] if broken["mismatches"] else None}
    finally:
        if not keep:
            cleanup_tenant(tenant)
            out["cleaned_up"] = True
        else:
            out["cleaned_up"] = False
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="안내 문구 캐시 재사용률 실측(가짜 전송기·가짜 번역기)")
    parser.add_argument("--days", default="1,3,7", help="여행 일수들. 쉼표로 (기본 1,3,7)")
    parser.add_argument("--locales", default="zh-TW,en,ja", help="언어들. 쉼표로 (기본 zh-TW,en,ja)")
    parser.add_argument("--keep", action="store_true", help="시험 테넌트를 지우지 않는다")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="결과 JSON 경로")
    args = parser.parse_args(argv)

    locales = [value.strip() for value in args.locales.split(",") if value.strip()]
    day_list = [int(value) for value in args.days.split(",") if value.strip()]
    workdir = ROOT / "var" / "measure"
    workdir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {"measured_at": datetime.now(tz=KST).isoformat(),
                              "scenario": SCENARIO_PATH.relative_to(ROOT).as_posix(),
                              "locales": locales, "runs": []}
    for days in day_list:
        outcome = run(days=days, locales=locales, keep=args.keep, workdir=workdir)
        report["runs"].append(outcome)
        cold = outcome["cold"]
        rate = "해당 없음(모델을 한 번도 안 부른다)" if cold["reuse_rate"] is None \
            else f"{cold['reuse_rate'] * 100:.1f}%"
        print(f"[{days}일 · 언어 {len(locales)}] 안내 {cold['notices']}건 · 모델 호출 "
              f"{cold['model_calls']}회 · 재사용 {cold['reused']}/{cold['denominator']} = "
              f"{rate} · 담긴 틀 {cold['cache_entries']}개 · "
              f"값 어긋남 {len(cold['mismatches'])}건", flush=True)

    mismatches = sum(len(row["cold"]["mismatches"]) + len(row["warm"]["mismatches"])
                     for row in report["runs"])
    report["mismatches_total"] = mismatches
    # ★대조가 실제로 우는지 — 안 울면 위 0건은 아무것도 증명하지 못한다.
    toothless = [row["days"] for row in report["runs"]
                 if row["self_check"]["mismatches"] == 0 and row["cold"]["reused"] > 0]
    report["self_check_toothless_days"] = toothless
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {out_path}")
    if mismatches:
        print(f"★★값이 섞였다 — 어긋난 안내 {mismatches}건. 이것은 결함이다.", file=sys.stderr)
        return 1
    if toothless:
        print(f"★대조가 울지 않는다({toothless}일) — 「값이 안 섞였다」를 말할 수 없다.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
