"""조사용(격리 사본 전용, 커밋하지 않음) — 2026-10-19 알려진 시험 실패 원인 조사. 실패 당시 값을 찍는다."""
import json

from tests.e2e.test_intake_catalog_names import *  # noqa: F401,F403
from tests.e2e.test_intake_catalog_names import _plan
from tests.e2e import test_intake_experience_tiers as tiers
from tests.e2e.test_intake_experience_tiers import park_world  # noqa: F401


def _dump(tag, value):
    print(f"\n[PROBE {tag}] " + json.dumps(value, ensure_ascii=False, default=str)[:3000])


def test_probe_bracketed_alias(hotels):
    view, _tour, _kakao = _plan("시험 기념관")
    spot = next(i for i in view["review"]["items"] if "기념관" in i["title"])
    _dump("alias_spot", {k: spot.get(k) for k in ("title", "kind", "place_state", "place", "note", "notes", "evidence", "reason")})


from tests.e2e.test_decision_unit_web import decided  # noqa: E402,F401
from tests.e2e.test_web_api import api, _fresh_limit_cache  # noqa: E402,F401


def test_probe_named_destination_at_trip_time(decided):  # noqa: F811 — 픽스처를 인자로 받는다
    from tests.e2e import test_decision_destination_condition_web as dest

    dest._answer_with(decided, destination_text="통인시장")
    before = dest._versions(decided)
    for tag, at in (("at_2030", "2030-01-01T09:00:00+09:00"), ("at_trip_day", "2026-09-23T09:00:00+09:00")):
        body = dest._say(decided, "점심 통인시장으로 바꿔", "probe-" + tag, at=at)
        _dump("dest_" + tag, {"status": body.get("status"), "action": (body.get("decision") or {}).get("action"),
                              "answer": body.get("answer"), "versions_changed": dest._versions(decided) != before,
                              "pick": body.get("pick")})


def test_probe_named_hotel_ready():
    from tests.e2e.test_intake_stay_lines import _client as stay_client, _StayKakao, _key as stay_key, _send as stay_send
    from tests.helpers.plugin_bindings import publish_fixed_mobility

    client, _tour, _kakao = stay_client(kakao=_StayKakao())
    publish_fixed_mobility(client.app, source="stay_lines_probe")
    view = stay_send(client, stay_key(client), "2026-12-06\n15:00 더 플라자 호텔 서울 체크인\n17:00 경복궁\n2026-12-07\n09:30 N서울타워\n11:00 체크아웃")
    review = view["review"]
    _dump("stay_needs", review.get("needs"))
    _dump("stay_rows", [{"title": i["title"], "status": i.get("status"),
                         "bad": [r for r in i.get("rows") or [] if r.get("result") not in ("ok", "unknown")]}
                        for i in review["items"]])


def test_probe_same_kind_first(park_world):  # noqa: F811 — 픽스처를 인자로 받는다
    tiers._row(park_world, "960006", "12", "창덕궁", 37.5794, 126.9910, "HS", "HS01", "HS010100")
    review, item = tiers._palace_review()
    got = tiers._alternatives(park_world, review, item)
    _dump("tiers", [{k: c.get(k) for k in ("basis", "distance_m", "similarity", "team_rank", "reason", "experience")}
                    | {"name": c["place"]["name"], "hours": (c["place"].get("attributes") or {}).get("hours_read")}
                    for c in got["candidates"]])
    _dump("tiers_notes", got.get("notes"))
    _dump("tiers_rows", [{"name": c["place"]["name"], "fits": c.get("fits"), "status": c.get("status"),
                          "rows": [r for r in c.get("rows") or [] if r.get("result") != "ok"]}
                         for c in got["candidates"]])
