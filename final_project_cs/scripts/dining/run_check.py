"""현장 확인 한 번을 돌린다.

DB 는 무엇을 물을지 알고, 이 스크립트는 그 물음을 밖으로 내보내 답을 받아온다.
조회 수단은 백엔드로 갈아끼운다. DB 도 이 스크립트도 캐치테이블이 무엇인지 모른다.

    물음 만들기            답 받기              답 적기
    check_prompt()   →   백엔드   →   record_live_check()

백엔드
    stub        정해둔 답을 돌려준다. 파이프라인이 도는지 볼 때 쓴다.
    manual      물음을 띄우고 사람이 보고 답을 적어 넣는다.
    catchtable  파일로 넘기고 파일로 받는다. 브라우저를 모는 쪽은 밖에 있다.
                제휴 전제 시험 구현. catchtable.py 의 머리말을 보라.

사용법
    python scripts/dining/run_check.py ask  --place 대돈집 --at "2026-09-25 12:00"
    python scripts/dining/run_check.py run  --place 대돈집 --at "2026-09-25 12:00" --backend stub
    python scripts/dining/run_check.py run  --place 대돈집 --at "2026-09-25 12:00" --backend manual --vacancy
    python scripts/dining/run_check.py show --place 대돈집
    python scripts/dining/run_check.py run  --place 대돈집 --at "2026-09-25 12:00" --vacancy --backend catchtable
    python scripts/dining/run_check.py pending

접속
    DINING_DSN 이 있으면 그것을 쓰고, 없으면 코어 설정을 따른다.
    예) set DINING_DSN=postgresql://postgres@localhost:5433/dining_dev
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

#: 조회에 걸 상한. check_prompt 가 돌려주는 값과 같아야 한다.
DEFAULT_TIMEOUT = 8

TOPIC_LABEL = {
    "hours":   "영업시간",
    "closure": "휴무 여부",
    "vacancy": "지금 빈자리",
    "waiting": "현장 웨이팅",
}


# ──────────────────────────────────────────────────────────────
# 접속
# ──────────────────────────────────────────────────────────────

def connect():
    """psycopg 연결 하나. 코어 설정이 있으면 그것을 먼저 쓴다."""
    import psycopg

    dsn = os.environ.get("DINING_DSN")
    if not dsn:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))))
            from app.infrastructure.db.session import database_dsn
            dsn = database_dsn()
        except Exception as exc:                       # noqa: BLE001
            raise SystemExit(
                "접속 주소를 찾지 못했다. DINING_DSN 을 정해 주거나 코어 설정을 갖춰라.\n"
                f"  원인: {exc}") from exc
    return psycopg.connect(dsn)


def resolve_place(cur, name_or_uid: str) -> tuple[str, str]:
    """이름이나 uid 로 장소 하나를 찾는다. 여럿이면 고르라고 세워 둔다."""
    if len(name_or_uid) == 36 and name_or_uid.count("-") == 4:
        cur.execute("SELECT place_uid, name_ko FROM dining.dn_place WHERE place_uid = %s",
                    (name_or_uid,))
    else:
        cur.execute("SELECT place_uid, name_ko FROM dining.dn_place WHERE name_ko = %s",
                    (name_or_uid,))
    rows = cur.fetchall()
    if not rows:
        raise SystemExit(f"그런 장소가 없다: {name_or_uid}")
    if len(rows) > 1:
        # 같은 상호가 여럿이면 임의로 고르지 않는다. 엉뚱한 집을 확인해 적으면 되돌리기 어렵다.
        print(f"「{name_or_uid}」 이 여럿이다. uid 로 다시 불러라.", file=sys.stderr)
        for uid, nm in rows:
            print(f"  {uid}  {nm}", file=sys.stderr)
        raise SystemExit(2)
    return rows[0]


def parse_at(text: str) -> datetime:
    """「2026-09-25 12:00」 처럼 적은 것을 한국 시각으로 읽는다."""
    from datetime import timedelta, timezone
    kst = timezone(timedelta(hours=9))
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=kst)
        except ValueError:
            continue
    raise SystemExit(f"시각을 읽지 못했다: {text}  (예: 2026-09-25 12:00)")


# ──────────────────────────────────────────────────────────────
# 백엔드
# ──────────────────────────────────────────────────────────────
#
# 돌려주는 모양은 하나다.
#   outcome      ok | not_found | blocked | timeout | error
#   value_state  yes | no | unknown        ok 가 아니면 DB 가 unknown 으로 덮는다
#   value_num    웨이팅 팀 수처럼 수로 답하는 것만
#   value_detail 사람이 읽을 한 줄
#   evidence     어디서 봤는지

def backend_stub(topic: str, prompt: dict) -> dict:
    """정해둔 답. 조회를 하지 않으므로 운영에 쓰지 않는다."""
    canned = {
        "hours":   dict(outcome="ok", value_state="yes",
                        value_detail="11:00~21:00 (시험용 값)"),
        "closure": dict(outcome="ok", value_state="no",
                        value_detail="정상영업 (시험용 값)"),
        "vacancy": dict(outcome="ok", value_state="yes",
                        value_detail="빈자리 있음 (시험용 값)"),
        "waiting": dict(outcome="ok", value_state="yes", value_num=3,
                        value_detail="대기 3팀 (시험용 값)"),
    }
    answer = dict(canned[topic])
    answer["evidence"] = "stub"
    return answer


def backend_manual(topic: str, prompt: dict) -> dict:
    """사람이 열어 보고 적는다. 네이버로 대조하던 일을 그대로 옮긴 것이다."""
    question = {
        "hours":   "적힌 영업시간이 실제와 같은가",
        "closure": "그날 쉬는가",
        "vacancy": "지금 빈자리가 있는가",
        "waiting": "현장 대기가 있는가",
    }[topic]
    print()
    print(f"  ── {TOPIC_LABEL[topic]} ── {question}?")
    print("     y=그렇다  n=아니다  ?=모르겠다  x=못 열었다   (Enter 는 ?)")
    try:
        raw = input("  > ").strip().lower()
    except EOFError:
        raw = ""

    if raw.startswith("x"):
        return dict(outcome="blocked", value_state="unknown",
                    value_detail=None, evidence="manual")
    if raw.startswith("y"):
        state = "yes"
    elif raw.startswith("n"):
        state = "no"
    else:
        # 모르겠다도 답이다. 억지로 정하지 않는다.
        return dict(outcome="ok", value_state="unknown",
                    value_detail=None, evidence="manual")

    try:
        detail = input("  본 대로 한 줄 (Enter 로 건너뜀): ").strip() or None
    except EOFError:
        detail = None

    num = None
    if topic == "waiting":
        try:
            got = input("  대기 팀 수 (모르면 Enter): ").strip()
        except EOFError:
            got = ""
        if got.isdigit():
            num = int(got)

    return dict(outcome="ok", value_state=state, value_num=num,
                value_detail=detail, evidence="manual")


def backend_catchtable(topic: str, prompt: dict) -> dict:
    """답 파일이 와 있으면 그것을 읽고, 없으면 의뢰를 놓는다.

    조회하는 쪽이 브라우저를 몰아야 해서 이 함수 안에서 끝나지 않는다.
    한 번 돌리면 「무엇을 봐 달라」가 놓이고, 답이 놓인 뒤 다시 돌리면 적힌다.
    답이 오기 전의 결과는 blocked 이며 값은 모름이다. 아니다가 아니다.
    """
    import catchtable

    uid = prompt["place_uid"]
    got = catchtable.read_answer(uid, topic)
    if got["evidence"] == "catchtable:asked":
        # 아직 답이 없다. 무엇을 봐 달라를 놓아 둔다.
        catchtable.write_ask(uid, prompt, list(prompt.get("topics") or [topic]))
    return got


BACKENDS = {
    "stub": backend_stub,
    "manual": backend_manual,
    "catchtable": backend_catchtable,
}


def default_source(backend: str, topic: str) -> str:
    """어느 출처로 적을 것인가.

    사람이 눈으로 본 것은 operator_check 다. 기계가 지도를 읽은 것은 그 아래다.
    빈자리와 웨이팅은 출처가 캐치테이블이라 운영 판정에 쓰지 않는다.
    """
    if topic in ("vacancy", "waiting"):
        return "catchtable_trial"
    if backend == "manual":
        return "operator_check"
    return "auto_map_check"


# ──────────────────────────────────────────────────────────────
# 명령
# ──────────────────────────────────────────────────────────────

def get_prompt(cur, place_uid: str, at: datetime, vacancy: bool):
    cur.execute("SELECT dining.check_prompt(%s, %s, %s)", (place_uid, at, vacancy))
    return cur.fetchone()[0]


def cmd_ask(args) -> int:
    with connect() as conn, conn.cursor() as cur:
        uid, name = resolve_place(cur, args.place)
        prompt = get_prompt(cur, uid, parse_at(args.at), args.vacancy)
    if prompt is None:
        print(f"{name}: 물을 것이 없다. DB 로 답이 되거나 이미 확인했다.")
        return 0
    print(json.dumps(prompt, ensure_ascii=False, indent=2))
    return 0


def cmd_run(args) -> int:
    fetch = BACKENDS[args.backend]
    with connect() as conn, conn.cursor() as cur:
        uid, name = resolve_place(cur, args.place)
        at = parse_at(args.at)
        prompt = get_prompt(cur, uid, at, args.vacancy)
        if prompt is None:
            print(f"{name}: 물을 것이 없다. 조회하지 않는다.")
            return 0

        print(f"{name} — 물을 것 {len(prompt['topics'])}가지 "
              f"({', '.join(TOPIC_LABEL[t] for t in prompt['topics'])})")
        if args.backend == "manual":
            # 확인할 곳은 한 번만 보인다. 주제마다 되풀이하면 읽히지 않는다.
            print(f"  {prompt['sentence']}")
            for key in ("naver", "google", "phone"):
                if prompt.get(key):
                    print(f"  {key:6s} {prompt[key]}")

        for topic in prompt["topics"]:
            source = args.source or default_source(args.backend, topic)
            try:
                answer = fetch(topic, prompt)
            except Exception as exc:                   # noqa: BLE001
                # 확인기가 터져도 이 스크립트는 계속 돈다. 터진 것을 터진 대로 적는다.
                answer = dict(outcome="error", value_state="unknown",
                              value_detail=str(exc)[:200], evidence=args.backend)

            cur.execute(
                "SELECT dining.record_live_check(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (uid, source, topic,
                 answer.get("outcome", "error"),
                 answer.get("value_state", "unknown"),
                 answer.get("value_num"),
                 answer.get("value_detail"),
                 answer.get("evidence"),
                 at, f"run_check:{args.backend}"))
            conn.commit()

            mark = "OK " if answer.get("outcome") == "ok" else "실패"
            state = answer.get("value_state", "unknown") if answer.get("outcome") == "ok" else "unknown"
            print(f"  {mark} {TOPIC_LABEL[topic]:8s} {state:8s} [{source}] "
                  f"{answer.get('value_detail') or ''}")

        left = get_prompt(cur, uid, at, args.vacancy)
        if left is None:
            print("  남은 물음 없음")
        else:
            print(f"  남은 물음: {', '.join(TOPIC_LABEL[t] for t in left['topics'])}")
    return 0


def cmd_pending(args) -> int:
    """답을 기다리는 캐치테이블 의뢰를 보인다. 브라우저를 모는 쪽이 읽을 목록이다."""
    import catchtable

    rows = catchtable.pending()
    if not rows:
        print("기다리는 의뢰 없다.")
        return 0
    for one in rows:
        print(f"{one.get('name')}  ({one.get('asked_at')})")
        print(f"  {one.get('sentence')}")
        print(f"  {one.get('search_url')}")
        for t in one.get("topics") or []:
            print(f"    {TOPIC_LABEL.get(t['topic'], t['topic']):8s} {t['read']}")
        print(f"  답은 여기에: {one['how_to_answer']['file']}")
    return 0


def cmd_show(args) -> int:
    with connect() as conn, conn.cursor() as cur:
        uid, name = resolve_place(cur, args.place)
        print(f"{name}")
        for topic in TOPIC_LABEL:
            cur.execute("SELECT dining.live_state(%s, %s)", (uid, topic))
            got = cur.fetchone()[0]
            if got is None:
                # 기한이 지났거나 확인한 적이 없다. 닫혔다는 뜻이 아니다.
                print(f"  {TOPIC_LABEL[topic]:8s} 모름")
            else:
                print(f"  {TOPIC_LABEL[topic]:8s} {got['state']:8s} "
                      f"[{got['source']}] {got.get('detail') or ''}")
        cur.execute(
            "SELECT topic, outcome, value_state, source_code, asked_at "
            "FROM dining.dn_live_check WHERE place_uid = %s "
            "ORDER BY asked_at DESC LIMIT 10", (uid,))
        rows = cur.fetchall()
        if rows:
            print("  최근 조회")
            for topic, outcome, state, src, asked in rows:
                print(f"    {asked:%m-%d %H:%M}  {TOPIC_LABEL[topic]:8s} "
                      f"{outcome:9s} {state:8s} {src}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="현장 확인 한 번을 돌린다.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--place", required=True, help="상호명 또는 place_uid")

    p_ask = sub.add_parser("ask", help="무엇을 물을지만 본다")
    common(p_ask)
    p_ask.add_argument("--at", required=True, help="방문 시각. 2026-09-25 12:00")
    p_ask.add_argument("--vacancy", action="store_true", help="빈자리와 웨이팅까지")
    p_ask.set_defaults(func=cmd_ask)

    p_run = sub.add_parser("run", help="묻고 답을 받아 적는다")
    common(p_run)
    p_run.add_argument("--at", required=True, help="방문 시각. 2026-09-25 12:00")
    p_run.add_argument("--vacancy", action="store_true", help="빈자리와 웨이팅까지")
    p_run.add_argument("--backend", default="manual", choices=sorted(BACKENDS))
    p_run.add_argument("--source", help="출처를 직접 고를 때만")
    p_run.set_defaults(func=cmd_run)

    p_pending = sub.add_parser("pending", help="답을 기다리는 캐치테이블 의뢰")
    p_pending.set_defaults(func=cmd_pending)

    p_show = sub.add_parser("show", help="확인한 것을 본다")
    common(p_show)
    p_show.set_defaults(func=cmd_show)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
