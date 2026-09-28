"""캐치테이블 조회를 사람·에이전트에게 넘기고 답을 받아 온다. 제휴 전제 시험 구현.

왜 파일로 주고받는가.
    캐치테이블은 공식 접근 경로가 없고 로그인한 화면 안에서만 값이 보인다.
    그래서 조회하는 쪽은 브라우저를 모는 무언가여야 하고, 그것은 이 스크립트
    안에 들어올 수 없다. 대신 「무엇을 봐 달라」를 파일로 내놓고, 본 것을
    파일로 돌려받는다. 미는 쪽과 읽는 쪽이 서로를 몰라도 된다.

        run_check --backend catchtable
              ↓  ask 파일을 놓는다
        브라우저를 모는 쪽 (사람이든 MCP 가 깔린 우리 PC 든)
              ↓  answer 파일을 놓는다
        run_check --backend catchtable   다시
              ↓  DB 에 적는다  (출처 catchtable_trial)

    제휴가 되어 API 가 열리면 이 다리를 걷어내고 그 자리에 호출을 넣으면 된다.
    DB 도 run_check 도 캐치테이블이 무엇인지 모르는 채로 남는다.

무엇을 지키는가.
    1  여기서 온 값은 판정에 쓰지 않는다. 출처가 catchtable_trial 이고
       production_allowed 가 false 라 v_live_check_fresh 에서 빠진다.
    2  본 시각이 없거나 오래된 답은 모름이다. 빈자리와 웨이팅은 몇 분이면
       바뀌므로 낡은 값을 「지금」으로 적으면 없느니만 못하다.
    3  읽을 수 없었던 것은 아니라고 적지 않는다. 모름으로 적는다.
    4  무인 자동화로 읽지 않는다. 2026-09-22 에 robots.txt 를 직접 확인했다.
       검색엔진 봇 아홉 개만 이름을 대고 허용되고, 나머지는 User-agent: *
       Disallow: / 다. 우리 스크립트는 * 에 해당한다.
       그래서 이 다리의 읽는 쪽은 사람이 부르는 것이어야 하며, 스케줄러가
       무인으로 도는 구현을 여기에 넣지 않는다. 자동화는 제휴 뒤 API 로 한다.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

#: 이 안의 답만 받는다. 그 밖의 것은 전부 모름으로 떨어뜨린다.
STATES = ("yes", "no", "unknown")

#: 답이 얼마나 신선해야 하는가. 주제마다 다르다.
#: 빈자리·웨이팅은 몇 분이면 바뀌고, 영업시간·휴무는 그날 안이면 된다.
#:
#: 빈자리·웨이팅은 DB 의 live_ttl 과 같은 5분이어야 한다. 예전에는 15분이었는데,
#: DB 는 본 시각이 아니라 적은 시각부터 기한을 세므로 10분 된 값이 5분 더
#: 「지금」 행세를 했다. 여기서 더 짧게 끊어야 그 틈이 없다.
FRESH_SECONDS = {
    "vacancy": 5 * 60,
    "waiting": 5 * 60,
    "hours":   12 * 60 * 60,
    "closure": 12 * 60 * 60,
}

#: 무엇을 봐 달라고 적을 것인가. 화면에서 실제로 읽히던 자리다.
WHAT_TO_READ = {
    "vacancy": "예약 가능한 시간 칸이 남아 있는지. 전부 회색이면 아니다.",
    "waiting": "「현재 웨이팅 N팀」 표시. 숫자를 그대로 적는다.",
    "hours":   "매장 정보의 영업시간. 라스트오더가 적혀 있으면 함께.",
    "closure": "휴무일 표기와 「소식」 탭의 명절 공지.",
}

#: /ct/search?keyword= 는 껍데기만 오는 죽은 경로다 (2026-09-22 확인).
#: 홈에서 검색창에 쳐야 결과가 나온다. 그래서 홈을 준다.
SEARCH_URL = "https://app.catchtable.co.kr/  (검색창에 「{q}」)"


def _build_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))          # final_project_cs
    path = os.path.join(root, "data", "dining", "_build", "catchtable")
    os.makedirs(path, exist_ok=True)
    return path


def ask_path(place_uid: str) -> str:
    return os.path.join(_build_dir(), f"{place_uid}.ask.json")


def answer_path(place_uid: str) -> str:
    return os.path.join(_build_dir(), f"{place_uid}.answer.json")


def write_ask(place_uid: str, prompt: dict, topics: list[str]) -> str:
    """무엇을 봐 달라를 파일로 놓는다.

    prompt 는 DB 의 check_prompt() 가 만든 것이다. 여기서 말을 새로 짓지 않고
    그대로 실어 보낸다. 무엇을 물을지 정하는 곳은 DB 한 곳이어야 한다.
    """
    name = prompt.get("name") or ""
    ask = {
        "place_uid": place_uid,
        "name": name,
        "target_at": prompt.get("target_at"),
        "sentence": prompt.get("sentence"),
        "search_url": SEARCH_URL.format(q=name),
        "topics": [{"topic": t, "read": WHAT_TO_READ.get(t, "")} for t in topics],
        "asked_at": datetime.now(KST).isoformat(timespec="seconds"),
        "how_to_answer": {
            "file": os.path.basename(answer_path(place_uid)),
            "shape": {
                "observed_at": "2026-09-25T12:03:00+09:00  (본 시각. 없으면 모름으로 떨어진다)",
                "url": "실제로 본 화면 주소",
                "answers": {
                    "waiting": {"state": "yes|no|unknown", "num": 41,
                                "detail": "본 대로 한 줄"},
                },
            },
        },
        "rules": [
            "로그인하지 않으면 값이 비어 보인다. 비어 보이는 것은 아니다가 아니라 모름이다.",
            "예약 버튼을 누르지 않는다. 읽기만 한다.",
            "한 곳만 본다. 목록을 훑지 않는다.",
            "사람이 불러서 본다. robots.txt 가 User-agent:* Disallow:/ 이므로 "
            "무인 자동화로 돌리지 않는다.",
        ],
    }
    path = ask_path(place_uid)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(ask, fp, ensure_ascii=False, indent=2)
    return path


def _parse_observed(raw) -> datetime | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    # 「2026-09-25T12:03:00+09:00」 뒤에 사람이 덧붙인 설명이 있어도 앞부분만 읽는다.
    got = re.match(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?([+-]\d{2}:?\d{2}|Z)?", text)
    if not got:
        return None
    try:
        stamp = datetime.fromisoformat(got.group(0).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=KST)


def read_answer(place_uid: str, topic: str, now: datetime | None = None) -> dict:
    """답 파일에서 이 주제의 답 하나를 꺼낸다.

    파일이 없으면 「아직 답이 없다」이지 「아니다」가 아니다. blocked 로 돌려준다.
    그래야 026 의 fail_is_unknown 제약이 값을 모름으로 붙든다.
    """
    now = now or datetime.now(KST)
    path = answer_path(place_uid)
    if not os.path.isfile(path):
        return dict(outcome="blocked", value_state="unknown",
                    value_detail="아직 답이 없다", evidence="catchtable:asked")
    try:
        with open(path, encoding="utf-8") as fp:
            got = json.load(fp)
    except (OSError, ValueError) as exc:
        return dict(outcome="error", value_state="unknown",
                    value_detail=f"답 파일을 읽지 못했다: {exc}"[:200],
                    evidence="catchtable:bad_file")

    observed = _parse_observed(got.get("observed_at"))
    if observed is None:
        # 언제 본 것인지 모르면 지금 값으로 쓸 수 없다.
        return dict(outcome="blocked", value_state="unknown",
                    value_detail="본 시각이 없다", evidence="catchtable:no_timestamp")

    age = (now - observed).total_seconds()
    limit = FRESH_SECONDS.get(topic, 15 * 60)
    if age > limit:
        return dict(outcome="blocked", value_state="unknown",
                    value_detail=f"{int(age // 60)}분 전에 본 값이라 지금으로 쓰지 않는다",
                    evidence="catchtable:stale")

    one = (got.get("answers") or {}).get(topic)
    if not isinstance(one, dict):
        return dict(outcome="blocked", value_state="unknown",
                    value_detail="그 주제의 답이 없다", evidence="catchtable:missing_topic")

    state = one.get("state")
    if state not in STATES:
        state = "unknown"
    num = one.get("num")
    if not isinstance(num, int) or isinstance(num, bool):
        num = None

    detail = one.get("detail")
    if isinstance(detail, str):
        detail = detail.strip()[:200] or None
    else:
        detail = None

    url = got.get("url")
    evidence = "catchtable:" + (url[:160] if isinstance(url, str) and url else "no_url")
    return dict(outcome="ok", value_state=state, value_num=num,
                value_detail=detail, evidence=evidence)


def write_answer(place_uid: str, url: str, seen: dict,
                 observed_at: datetime | None = None) -> str:
    """본 것을 답 파일로 놓는다.

    본 시각은 받지 않고 여기서 찍는다. 손으로 적게 하면 화면을 본 시각이 아니라
    파일을 쓴 시각이 들어가고, 그러면 신선도 판정이 거짓말이 된다.
    브라우저에서 읽은 직후에 부르는 것이 전제다.

    seen 은 {주제: {"state": ..., "num": ..., "detail": ...}} 다.
    모르는 주제는 넣지 않는다. 빈 칸과 「아니다」는 다르다.
    """
    body = {
        "observed_at": (observed_at or datetime.now(KST)).isoformat(timespec="seconds"),
        "url": url,
        "answers": seen,
    }
    path = answer_path(place_uid)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(body, fp, ensure_ascii=False, indent=2)
    return path


def pending() -> list[dict]:
    """답을 기다리는 의뢰 목록. 답 파일이 생기면 빠진다."""
    out = []
    folder = _build_dir()
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".ask.json"):
            continue
        uid = name[: -len(".ask.json")]
        if os.path.isfile(answer_path(uid)):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as fp:
                out.append(json.load(fp))
        except (OSError, ValueError):
            continue
    return out
