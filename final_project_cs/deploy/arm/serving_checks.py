"""실제 여행 HTTP 계약 검사. 중도 실패·미실행도 고정 분모에 보존한다."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
import serving_probe as probe

BASE = Path(os.environ["DEPLOY_BASE"])
API = probe.API
PROFILES = {
    "context_cache": ("첫 일정은 몇 시에 시작해요?", "점심은 몇 시예요?", "고마워요", "첫 일정은 몇 시에 시작해요?"),
    "mixed_travel": ("안녕하세요. 내일 날씨도 궁금하지만 우선 첫 일정 시작 시간을 알려 주세요.", "점심 시간만 알려 주세요.", "서울 여행 기대되네요", "관람 시작 시간과 점심 시간을 함께 알려 주세요."),
    "language_style": ("When does my first activity start?", "점심 몇시였지요?", "Thanks!", "請告訴我第一個行程的開始時間。"),
}
PLANNED = ("api_health", "without_user_key", "session_owner", "session_other", "prepare_synthetic_trip",
           "own_trip", "other_user_denied", "travel_message_1", "travel_message_2", "travel_message_3", "travel_message_4")
PRIVATE_FIELDS = {"user_key", "csrf_token", "plan_url", "plan_token"}
VALIDATION_VERSION = "travel-answer-v4-session-soak"
EXPECTED_TIMES = {
    "context_cache": (("10:00",), ("12:00",), (), ("10:00",)),
    "mixed_travel": (("10:00",), ("12:00",), (), ("10:00", "12:00")),
    "language_style": (("10:00",), ("12:00",), (), ("10:00",)),
}


def valid_travel_answer(value, profile, index):
    """HTTP 200인 해석 오류도 실패다. 합성 일정의 정해진 시각까지 확인한다."""
    if value.get("status") != "answered" or value.get("failure") or "error" in value:
        return False
    expected_reason = "decision_other" if index == 2 else "decision_answer_fact"
    if value.get("reason") != expected_reason:
        return False
    answer = value.get("answer")
    return (isinstance(answer, str) and bool(answer.strip())
            and all(moment in answer for moment in EXPECTED_TIMES[profile][index]))


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k not in PRIVATE_FIELDS}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def test_identities(check):
    """기존 시험 계정 둘을 재사용한다. 계정 발급 한도는 변경하지 않는다."""
    private = BASE / "probe_identity.json"
    if private.exists():
        identity = json.loads(private.read_text())
        existing_trips = []
        for name, field in (("session_owner", "key"), ("session_other", "other")):
            value = check(name, "/v1/web/trips", key=identity[field],
                          validate=lambda v: isinstance(v.get("trips"), list))
            if not isinstance(value.get("trips"), list):
                raise RuntimeError("stored_test_identity_unavailable")
            if field == "key":
                existing_trips = value["trips"]
        return identity["key"], identity["other"], "reused_existing_probe_identity", existing_trips
    owner = check("session_owner", "/v1/web/session", {}, expect=201, validate=lambda v: bool(v.get("user_key")))
    other = check("session_other", "/v1/web/session", {}, expect=201, validate=lambda v: bool(v.get("user_key")))
    if not owner.get("user_key") or not other.get("user_key"):
        raise RuntimeError("session_setup_failed")
    # 배포 잠금 아래 최초 한 번만 발급·보관한다. 키는 결과 로그에서 제거한다.
    with os.fdopen(os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
        json.dump({"key": owner["user_key"], "other": other["user_key"]}, handle)
    return owner["user_key"], other["user_key"], "issued_once_and_cached", []


def valid_test_fixture(value):
    """전용 합성 여행만 재사용한다. 변경·과거 일정이면 조용히 이어가지 않는다."""
    if value.get("title") != "ARM 서빙 시험용 서울 여행" or value.get("version") != 1:
        return False
    items = sorted(value.get("items", []), key=lambda item: item.get("seq", 0))
    expected = ((1, "activity", "경복궁 관람", "10:00", "11:00"),
                (2, "dining", "점심 식사", "12:00", "13:00"))
    if len(items) != len(expected):
        return False
    dates = []
    try:
        for item, (seq, kind, title, start, end) in zip(items, expected):
            begin = datetime.fromisoformat(item["starts_at"])
            finish = datetime.fromisoformat(item["ends_at"])
            if begin.utcoffset() != timedelta(hours=9) or finish.utcoffset() != timedelta(hours=9):
                return False
            if (item.get("seq"), item.get("kind"), item.get("title"), begin.strftime("%H:%M"),
                    finish.strftime("%H:%M")) != (seq, kind, title, start, end):
                return False
            if begin.date() != finish.date():
                return False
            dates.append(begin.date())
    except (KeyError, ValueError, TypeError):
        return False
    return dates[0] == dates[1] and dates[0] >= datetime.now(timezone(timedelta(hours=9))).date()


def prepare_test_trip(check, key, body, existing_trips):
    if existing_trips:
        if (len(existing_trips) != 1 or existing_trips[0].get("title") != body["title"]
                or not existing_trips[0].get("trip_id")):
            raise RuntimeError("unexpected_test_account_trips")
        trip = check("prepare_synthetic_trip", f"/v1/web/trips/{existing_trips[0]['trip_id']}",
                     key=key, validate=valid_test_fixture)
        if not valid_test_fixture(trip):
            raise RuntimeError("stored_test_fixture_changed_or_stale")
        return trip, "reused_same_synthetic_trip_with_history"
    trip = check("prepare_synthetic_trip", "/v1/web/trips", body, key, expect=201,
                 validate=lambda value: bool(value.get("trip_id")))
    if not trip.get("trip_id"):
        raise RuntimeError("trip_setup_failed")
    return trip, "created_fresh_synthetic_trip"


def run(profile, out):
    """호출자가 배포 잠금을 소유한다. 기존 계정 인증도 매번 실제 HTTP로 확인한다."""
    texts = PROFILES[profile]
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    state = json.loads((BASE / "state.json").read_text())
    started = time.monotonic()

    def check(name, path, payload=None, key=None, expect=200, validate=lambda value: True):
        check_started = time.monotonic()
        try:
            status, result, seconds = probe.call(path, payload, key)
            row = {"name": name, "status": status, "seconds": seconds,
                   "passed": status == expect and validate(result), "result": redact(result), "attempted": True}
        except Exception as exc:
            result = {}
            row = {"name": name, "passed": False, "error": type(exc).__name__, "attempted": True,
                   "seconds": time.monotonic() - check_started}
        rows.append(row)
        (out / "answers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        return result

    failure = None
    identity_mode = None
    fixture_mode = None
    try:
        check("api_health", "/health")
        check("without_user_key", "/v1/web/trips", expect=401)
        key, other_key, identity_mode, existing_trips = test_identities(check)
        day = (datetime.now(timezone(timedelta(hours=9))) + timedelta(days=7)).strftime("%Y-%m-%d")
        body = {"request_id": out.name + "-create", "title": "ARM 서빙 시험용 서울 여행", "locale": "ko", "party_size": 1,
                "constraints": {}, "places": [], "routes": {},
                "items": [{"seq": 1, "kind": "activity", "title": "경복궁 관람", "starts_at": day+"T10:00:00+09:00",
                           "ends_at": day+"T11:00:00+09:00", "detail": {}},
                          {"seq": 2, "kind": "dining", "title": "점심 식사", "starts_at": day+"T12:00:00+09:00",
                           "ends_at": day+"T13:00:00+09:00", "detail": {}}]}
        trip, fixture_mode = prepare_test_trip(check, key, body, existing_trips)
        trip_id = trip["trip_id"]
        check("own_trip", f"/v1/web/trips/{trip_id}", key=key)
        check("other_user_denied", f"/v1/web/trips/{trip_id}", key=other_key, expect=404)
        for i, text in enumerate(texts):
            check(f"travel_message_{i+1}", f"/v1/web/trips/{trip_id}/messages",
                  {"request_id": out.name + f"-{i}", "message": text}, key,
                  validate=lambda v, i=i: valid_travel_answer(v, profile, i))
    except Exception as exc:
        failure = str(exc)
    finally:
        names = {row["name"] for row in rows}
        rows.extend({"name": name, "attempted": False, "passed": False, "error": "unattempted_after_failure"}
                    for name in PLANNED if name not in names)
        summary = {"sha": state.get("current"), "profile": profile, "observed_at": datetime.now(timezone.utc).isoformat(),
                   "passed": sum(row["passed"] for row in rows), "total": len(PLANNED),
                   "attempted": sum(row["attempted"] for row in rows), "seconds": time.monotonic()-started,
                   "failure": failure, "scope": "real_http_contract_and_synthetic_answer_not_independent_accuracy",
                   "validation_version": VALIDATION_VERSION,
                   "identity_mode": identity_mode,
                   "fixture_mode": fixture_mode,
                   "repeated_soak_not_independent_accuracy": True, "co_running_inference_benchmark": True}
        (out / "answers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary
