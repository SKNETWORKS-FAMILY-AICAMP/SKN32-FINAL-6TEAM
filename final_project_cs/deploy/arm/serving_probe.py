"""배포된 실제 HTTP 경로의 여행 질의·격리 검사를 별도 회차로 보관한다."""
import fcntl
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import uuid4

BASE = Path(os.environ["DEPLOY_BASE"])
API = "http://127.0.0.1:8043"


def call(path, payload=None, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-User-Key"] = key
    request = urllib.request.Request(API + path, data=None if payload is None else json.dumps(payload).encode(), headers=headers)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read()
    try:
        result = json.loads(raw)
    except ValueError:
        result = {"body": raw.decode(errors="replace")}
    return status, result, time.monotonic() - started


def main():
    with (BASE / "deploy.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("배포 또는 검사 실행 중: 이번 접수 보류")
            return
        state = json.loads((BASE / "state.json").read_text())
        if "current" not in state:
            print("검증된 배포 대기")
            return
        out = BASE / "probes" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
        out.mkdir(parents=True)
        rows = []

        def check(name, path, payload=None, key=None, expect=200, validate=lambda value: True):
            try:
                status, result, seconds = call(path, payload, key)
                passed = status == expect and validate(result)
                # 발급 키·여행 링크 토큰은 근거 파일에 쓰지 않는다.
                redacted = {k: v for k, v in result.items() if k not in ("user_key", "csrf_token", "plan_url", "plan_token")}
                row = {"name": name, "status": status, "seconds": seconds, "passed": passed, "result": redacted}
            except Exception as exc:
                result = {}
                row = {"name": name, "passed": False, "error": type(exc).__name__}
            rows.append(row)
            (out / "answers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
            return result

        check("api_health", "/health")
        check("without_user_key", "/v1/web/trips", expect=401)
        private = BASE / "probe_identity.json"
        if private.exists():
            identity = json.loads(private.read_text())
        else:
            status, owner, _ = call("/v1/web/session", {})
            status2, other, _ = call("/v1/web/session", {})
            if status != 201 or status2 != 201:
                raise RuntimeError("시험용 사용자 발급 실패")
            identity = {"key": owner["user_key"], "other": other["user_key"]}
            private.write_text(json.dumps(identity))
            private.chmod(0o600)
        key = identity["key"]
        if "trip_id" not in identity:
            day = (datetime.now(timezone(timedelta(hours=9))) + timedelta(days=7)).strftime("%Y-%m-%d")
            body = {"request_id": "arm-serving-create-v1", "title": "ARM 서빙 시험용 서울 여행", "locale": "ko", "party_size": 1,
                    "constraints": {}, "places": [], "routes": {},
                    "items": [{"seq": 1, "kind": "activity", "title": "경복궁 관람", "starts_at": day+"T10:00:00+09:00",
                               "ends_at": day+"T11:00:00+09:00", "detail": {}},
                              {"seq": 2, "kind": "dining", "title": "점심 식사", "starts_at": day+"T12:00:00+09:00",
                               "ends_at": day+"T13:00:00+09:00", "detail": {}}]}
            trip = check("create_synthetic_trip", "/v1/web/trips", body, key, expect=201)
            if "trip_id" not in trip:
                raise RuntimeError("여행 등록 실패; answers.json 보존")
            identity["trip_id"] = trip["trip_id"]
            private.write_text(json.dumps(identity))
        trip_id = identity["trip_id"]
        check("own_trip", f"/v1/web/trips/{trip_id}", key=key)
        check("other_user_denied", f"/v1/web/trips/{trip_id}", key=identity["other"], expect=404)
        for i, text in enumerate(("첫 일정은 몇 시에 시작해요?", "점심은 몇 시예요?", "고마워요", "첫 일정은 몇 시에 시작해요?")):
            check(f"travel_message_{i+1}", f"/v1/web/trips/{trip_id}/messages",
                  {"request_id": out.name + f"-{i}", "message": text}, key,
                  validate=lambda value: bool(value.get("answer")) and "error" not in value)
        summary = {"sha": state["current"], "observed_at": datetime.now(timezone.utc).isoformat(),
                   "passed": sum(row["passed"] for row in rows), "total": len(rows),
                   "scope": "real_http_contract_not_independent_accuracy", "co_running_inference_benchmark": True}
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
