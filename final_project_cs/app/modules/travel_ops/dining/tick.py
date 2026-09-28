"""깨어났을 때 할 일. 언제 깨울지는 여기서 정하지 않는다.

무엇인가.
    감시 틱이 한 번 돌 때 요식이 하는 일 전부다. 방문이 다가온 식당마다
    지금이 물을 때인지 보고, 물을 때면 한 번 묻고, 말할 것이 있으면
    「이 말을 보내라」를 돌려준다.

왜 깨우는 쪽이 아닌가.
    깨우는 쪽은 코어 몫이다. watch.py 일 수도, 1분 크론일 수도, 시연 때
    누르는 버튼일 수도 있다. 그것이 무엇으로 바뀌든 이 파일은 고치지 않는다.
    부르는 쪽은 한 줄이다.

        from app.modules.travel_ops.dining.tick import tick_once
        notices = [r["notice"] for r in tick_once(conn, now, items) if r["notice"]]

    이것이 되도록 네 가지를 지킨다.

    1  안에 반복도 sleep 도 스케줄러도 없다. 한 번 불리면 한 번 돌고 끝난다.
    2  시계를 보지 않는다. now 를 받는다. 그래서 시험에서 「방문 18분 전」을
       바로 만들 수 있다.
    3  여러 번 불러도 같다. 1분마다 불러도, 같은 틱에 두 번 불러도 한 번만
       묻고 한 번만 말한다. 새 장치를 만들지 않고 이미 있는 것에 기댄다.
           물을 때인가       watch_window      방문 60분·20분 전의 5분 창
           또 묻는가         v_live_check_asked 031 의 재질문 억제
           또 말하는가       dn_notice UNIQUE   032 의 같은 방문 같은 종류 한 번
    4  보내지 않는다. 보낼 말을 돌려줄 뿐이다. 알림 창구가 바뀌어도 그대로다.

일정은 받는다.
    일정 표는 코어 것이다. 여기서 읽으면 코어 표가 바뀔 때마다 깨진다.
    그래서 부르는 쪽이 (place_uid, 방문 시각) 목록을 넘긴다. ledger.py 와
    같은 경계다. 코어를 import 하지 않는다.

누가 읽는가.
    fetch 로 받는다. 이 파일은 캐치테이블을 모른다.

        fetch(place_uid, name, sentence) -> (url, {주제: {state, num, detail}})

    사람이 본 것이든 브라우저를 몬 것이든 제휴 API 든, 모양만 맞으면 된다.
    fetch 가 없으면 묻지 않고 「물을 때다」만 돌려준다.

알림을 적는 때.
    말하기로 정하면 그 자리에서 dn_notice 에 적는다. 그래서 같은 말은 두 번
    나가지 않는다. 대신 부르는 쪽이 보내다 실패하면 그 말은 다시 오지 않는다.
    두 번 가는 것과 한 번도 안 가는 것 중 앞의 것을 막기로 했다. 알림은
    사용자의 주의를 쓰는 일이라 가장 좁게 잡는다는 기준을 따른 것이다.
    이 선택은 바꿀 수 있다. 바꾸려면 record_notice 부르는 줄을 부르는 쪽으로
    옮기면 된다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Iterable

#: 자동으로 묻는 것은 이 둘뿐이다. ambient_prompt 의 문장과 같다.
#: 「웨이팅 몇 팀」과 「영업 중인지」. 그 이상 묻지 않는다.
AMBIENT_TOPICS = ("closure", "waiting")

#: 붐빈다는 말은 20분 전에만 한다. 웨이팅은 5분이면 바뀌므로 60분 전 숫자는
#: 도착할 때 이미 낡았다. 쉰다는 말은 이를수록 좋으므로 60분 전에도 한다.
SAY_AT = {
    "closed":  ("T-60", "T-20"),
    "crowded": ("T-20",),
}

_STATES = ("yes", "no", "unknown")

Item = tuple[str, datetime]
Fetch = Callable[[str, str, str], "tuple[str, dict[str, dict[str, Any]]]"]


def _clean(one: Any) -> tuple[str, int | None, str | None]:
    """받은 값 한 줄을 다듬는다. 모양이 틀리면 모름이다.

    True 는 파이썬에서 int 다. 그대로 받으면 대기 1팀이 된다.
    """
    if not isinstance(one, dict):
        return "unknown", None, None
    state = one.get("state") if one.get("state") in _STATES else "unknown"
    num = one.get("num")
    if not isinstance(num, int) or isinstance(num, bool):
        num = None
    detail = one.get("detail")
    detail = detail.strip()[:200] or None if isinstance(detail, str) else None
    return state, num, detail


def _topics_to_ask(cur, place_uid: str) -> list[str]:
    """최근에 물어본 것은 빼고 남은 주제. 답이 무엇이었든 또 묻지 않는다."""
    cur.execute(
        "SELECT topic FROM dining.v_live_check_asked WHERE place_uid = %s",
        (place_uid,))
    asked = {row[0] for row in cur.fetchall()}
    return [t for t in AMBIENT_TOPICS if t not in asked]


def tick_one(conn, now: datetime, place_uid: str, starts_at: datetime, *,
             fetch: Fetch | None = None, trial: bool = False,
             source: str = "catchtable_trial") -> dict[str, Any]:
    """식당 하나. 돌려주는 것은 무엇을 했고 왜 했는지다. 안 했을 때도 이유가 있다."""
    out: dict[str, Any] = {"place_uid": place_uid, "starts_at": starts_at,
                           "window": None, "asked": [], "recorded": [],
                           "notice": None, "reason": None}
    with conn.cursor() as cur:
        cur.execute("SELECT dining.watch_window(%s, %s)", (starts_at, now))
        window = cur.fetchone()[0]
        out["window"] = window
        if window is None:
            out["reason"] = "물을 때가 아니다"
            return out

        cur.execute("SELECT name_ko FROM dining.dn_place WHERE place_uid = %s",
                    (place_uid,))
        row = cur.fetchone()
        if row is None:
            out["reason"] = "모르는 장소"
            return out
        name = row[0]

        # ── 묻기 ──────────────────────────────────────────────
        topics = _topics_to_ask(cur, place_uid)
        out["asked"] = topics
        if topics and fetch is not None:
            cur.execute("SELECT dining.ambient_prompt(%s)", (place_uid,))
            sentence = cur.fetchone()[0]
            try:
                url, seen = fetch(place_uid, name, sentence)
                failed = None
            except Exception as exc:                  # noqa: BLE001
                # 읽는 쪽이 터져도 틱은 계속 돈다. 터진 것을 터진 대로 적는다.
                url, seen, failed = None, {}, str(exc)[:200]

            for topic in topics:
                if failed is not None:
                    outcome, state, num, detail = "error", "unknown", None, failed
                elif topic in (seen or {}):
                    state, num, detail = _clean(seen[topic])
                    outcome = "ok"
                else:
                    # 읽는 쪽이 이 주제를 못 봤다. 아니다가 아니라 모름이다.
                    outcome, state, num, detail = "blocked", "unknown", None, "화면에 없었다"
                cur.execute(
                    "SELECT dining.record_live_check(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (place_uid, source, topic, outcome, state, num, detail,
                     f"tick:{url}" if url else "tick", starts_at, "tick_once"))
                out["recorded"].append({"topic": topic, "outcome": outcome,
                                        "state": state, "num": num})
            conn.commit()

        # ── 말하기 ────────────────────────────────────────────
        cur.execute("SELECT dining.notice_decision(%s, %s, %s)",
                    (place_uid, starts_at, trial))
        decision = cur.fetchone()[0] or {}
        out["reason"] = decision.get("reason")
        if not decision.get("send"):
            return out

        kind = decision.get("kind")
        if window not in SAY_AT.get(kind, ()):
            out["reason"] = f"{kind} 은 {window} 에 말하지 않는다"
            return out

        cur.execute("SELECT dining.record_notice(%s, %s, %s, %s, %s)",
                    (place_uid, starts_at, kind, decision["body"],
                     decision.get("based_on")))
        notice_id = cur.fetchone()[0]
        conn.commit()
        if notice_id is None:
            # 같은 틱이 겹쳐 돌아 다른 쪽이 먼저 적었다. 두 번 보내지 않는다.
            out["reason"] = "이미 말했다"
            return out

        out["notice"] = {"notice_id": str(notice_id), "place_uid": place_uid,
                         "starts_at": starts_at, "kind": kind,
                         "body": decision["body"], "window": window}
    return out


def tick_once(conn, now: datetime, items: Iterable[Item], *,
              fetch: Fetch | None = None, trial: bool = False) -> list[dict[str, Any]]:
    """틱 한 번. 방문이 다가온 식당마다 tick_one 을 부른다.

    items 는 (place_uid, 방문 시각) 목록이다. 부르는 쪽이 일정에서 꺼내 준다.
    물을 때가 아닌 곳은 DB 한 번 보고 지나간다. 순회처럼 보이지만 실제로
    묻는 곳은 창 안에 든 곳뿐이고, 그것도 한 곳에 한 번이다.

    trial 이 거짓이면 캐치테이블에서 온 값으로는 말하지 않는다. 본 갈래의
    판정은 시험 출처를 보지 않기 때문이다. 시연에서만 참으로 준다.
    """
    return [tick_one(conn, now, uid, at, fetch=fetch, trial=trial)
            for uid, at in items]
