"""실경보 수집·점검용 접수의 대체안 화면 보관. 고객 여행을 등록하지 않는다.

연결 정보는 git 밖 var/alert-snapshots/config.json에서 읽는다.
python -m scripts.capture_alert_scenarios --collect-only
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
DEFAULT_DIR = ROOT / "var" / "alert-snapshots"
SCHEMA_VERSION = 1


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def save(path: Path, value: Any) -> None:
    """기존 산출물은 백업 뒤 교체. 새 회차는 별도 폴더다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.parent / "_backup" / (datetime.now(KST).strftime("%Y-%m-%d_%H%M%S") + "_" + uuid4().hex[:8])
        backup.mkdir(parents=True)
        shutil.copy2(path, backup / path.name)
    temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(temp, path)


@contextmanager
def locked(folder: Path):
    """겹친 회차는 수집·쓰기를 하지 않는다. 비정상 종료의 잠금은 사람이 확인한다."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "run.lock"
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "at": datetime.now(KST).isoformat()}).encode())
        os.close(fd)
        yield
    finally:
        path.unlink()


def snapshot_policy(config: dict[str, Any]) -> dict[str, Any]:
    """상한을 모르면 수집을 시작하지 않는다. 값은 개인 연결 설정 한 곳에 둔다."""
    policy = config.get("budget_policy")
    if not isinstance(policy, dict):
        raise ValueError("원본 수집 budget_policy 설정이 필요합니다")
    ratio = policy.get("shared_stop_ratio")
    day, month = policy.get("source_daily_attempts"), policy.get("source_monthly_attempts")
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 < ratio < 1:
        raise ValueError("수집 몫은 0 초과·1 미만이어야 합니다")
    if type(day) is not int or type(month) is not int or not 0 < day <= month:
        raise ValueError("수집용 하루·월 호출 시도 상한은 양의 정수여야 합니다")
    return {"shared_stop_ratio": float(ratio), "source_daily_attempts": day, "source_monthly_attempts": month}


class SnapshotLimiter:
    """캐시 뒤·실제 호출 앞에 수집 전용 DB 상한을 적용한다. 기존 예산도 통과해야 한다."""

    def __init__(self, inner: Any, policy: dict[str, Any]) -> None:
        from app.domains.travel_ops.ports.data_sources.call_budget import CallBudget, UNLIMITED
        self.inner = inner
        shared = getattr(inner, "_budget", None)
        self.meters = {name for name in getattr(inner, "meters", ())
                       if shared is not None and 0 < int(shared.caps.get(name, {}).get("day", 0)) < UNLIMITED}
        self.budget = None if shared is None else CallBudget(
            connection_factory=shared._connect, tz=KST,
            caps={"alert_snapshot:" + name: {"day": policy["source_daily_attempts"],
                                            "month": policy["source_monthly_attempts"]} for name in self.meters})
        self.refused: dict[str, str] = {}

    def acquire(self, source: str) -> None:
        from app.domains.travel_ops.ports.data_sources.ratelimit import RateLimited
        reason = None
        wait = 0.0
        if self.budget is None or source not in self.meters:
            reason = "snapshot_budget_unknown"
        else:
            wait = self.budget.seconds_to_day_end()
            try:
                if not self.budget.try_reserve("alert_snapshot:" + source):
                    reason = "snapshot_budget_exhausted"
            except Exception:
                reason = "snapshot_budget_unavailable"
        if reason:
            self.refused[source] = reason
            error = RateLimited(source, wait)
            error.reason = reason
            raise error
        # 수집 시도가 먼저 차감되므로 기존 공용 예산 거절·통신 실패도 보수적으로 한 시도다.
        self.inner.acquire(source)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def collect_local(run: Path, at: datetime, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """기존 어댑터·공유 예산을 사용한다. CSV·실패를 실경보로 승격하지 않는다."""
    from app.core.settings import get_settings, get_guardrails
    from app.domains.travel_ops.ports.data_sources import build_travel_sources

    guard = get_guardrails()
    policy = snapshot_policy({"budget_policy": policy})
    # 기존 제한이 더 엄격하면 그쪽을 유지한다. 수집은 일반 호출 예산을 올리지 않는다.
    share = min(policy["shared_stop_ratio"], float(guard.get("travel.mcp.risk_check.fresh_share")))
    sources = build_travel_sources(get_settings(), low_priority_share=share)
    results: dict[str, Any] = {}
    jobs = {"weather_warning": sources.warning, "disaster_msg": sources.disaster, "earthquake": sources.earthquake}
    # 기존 합집합 소스의 자식 어댑터를 찾아 각각의 성공·실패와 원문을 보관한다.
    seen = set()
    def walk(source):
        if source is None or id(source) in seen:
            return
        seen.add(id(source))
        if hasattr(source, "records") and hasattr(source, "_get"):
            jobs[source.name] = source
        for attr in ("sources", "parts", "source", "notices", "primary", "secondary"):
            child = getattr(source, attr, None)
            for item in child if isinstance(child, (list, tuple)) else [child]:
                if item is not None:
                    walk(item)
    walk(sources.traffic)
    walk(sources.route_events)
    for name, source in jobs.items():
        raw: list[dict[str, Any]] = []
        if source is None or not hasattr(source, "_get"):
            results[name] = {"status": "not_connected", "live": False,
                             "reason": "실시간 API 어댑터가 연결되지 않음"}
            continue
        original = source._get
        original_limiter = getattr(source, "_limiter", None)
        source._limiter = SnapshotLimiter(original_limiter, policy)
        fetches = {name: getattr(source, name) for name in ("_fetch_json", "_fetch_xml") if hasattr(source, name)}

        def capture(url, params, *, call=original):
            response = call(url, params)
            # 인증 쿼리·헤더·URL 원문은 남기지 않는다. 공급자 본문만 보관한다.
            raw.append({"kind": "http_body", "received_at": datetime.now(KST).isoformat(), "http_status": response.status_code,
                        "body": response.text, "sha256": hashlib.sha256(response.content).hexdigest()})
            return response

        source._get = capture
        for fetch_name, fetch in fetches.items():
            def capture_value(url, params, *, call=fetch, adapter=source, format=fetch_name):
                payload = call(url, params)
                if payload is not None:
                    state = adapter._fetch_state
                    raw.append({"kind": "provider_xml" if format == "_fetch_xml" else "decoded_provider_body",
                                "from_cache": bool(getattr(state, "from_cache", False)),
                                "confirmed_at": getattr(state, "fetched_at", None), "body": payload, "sha256": digest(payload)})
                return payload
            setattr(source, fetch_name, capture_value)
        try:
            if name == "weather_warning":
                value = source.active(region="서울")
            elif name == "disaster_msg":
                # 당일 전체 수집. active()의 몇 시간 창을 당일 전체로 오해하지 않는다.
                value = source._rows_since("서울", at.replace(hour=0, minute=0, second=0, microsecond=0))
            elif name == "earthquake":
                value = source.recent(since=at.replace(hour=0, minute=0, second=0, microsecond=0), until=at)
            else:
                value = source.records()
            results[name] = {"status": "ok" if value is not None else "failed", "live": True,
                             "value": value, "misses": dict(source.misses), "raw_responses": sum(r["kind"] == "http_body" for r in raw),
                             "provider_bodies": len(raw), "raw_file": f"{name}-raw.json"}
        except Exception as exc:
            results[name] = {"status": "failed", "live": True, "error_type": type(exc).__name__}
        finally:
            source._limiter = original_limiter
            source._get = original
            for fetch_name, fetch in fetches.items():
                setattr(source, fetch_name, fetch)
            save(run / f"{name}-raw.json", raw)
    return {"scope": "서울 기상특보 현황·당일 재난문자·당일 지진·교통 돌발 현황·지하철 공지", "at": at.isoformat(), "sources": results,
            "budget_policy": {**policy, "effective_shared_stop_ratio": share,
                              "unknown_budget": "새 호출 금지; 기존 유효 캐시만 사용", "period_timezone": "Asia/Seoul"},
            "limits": "교통·특보는 조회 시점 현황, 재난문자·지진은 당일 범위. 회차 사이에 발생·해제된 사건을 전부 수집했다고 보장하지 않음. 예보·대기질은 매칭 API의 장소별 점검 근거로 보관"}


def local_inventory() -> dict[str, Any]:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True)
    return {"local_commit": out.stdout.strip(), "working_tree": "여러 세션의 미커밋 변경 포함",
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "python": sys.version.split()[0]}


def browser_capture(run: Path, config: dict[str, Any], manifest: dict[str, Any]) -> int:
    web = ROOT / "frontend" / "apps" / "web"
    node = config.get("node") or shutil.which("node")
    if not node:
        raise RuntimeError("Node.js 실행 경로가 필요합니다")
    package = web / "node_modules" / "@playwright" / "test"
    if not (package / "cli.js").exists():
        raise RuntimeError("웹 프로젝트의 Playwright 설치를 찾지 못했습니다")
    save(run / "browser-input.json", manifest)
    # 이 설정은 회차별 산출물이다. 기존 mock 서버 설정을 실서버 시험에 쓰지 않는다.
    generated = run / "playwright.config.cjs"
    generated.write_text("const {defineConfig}=require(" + json.dumps(str(package)) + ");\nmodule.exports=defineConfig(" + json.dumps({
        "testDir": str(web / "tests" / "live"), "testMatch": "alert-snapshots.spec.ts", "workers": 1,
        "fullyParallel": False, "timeout": config.get("browser_timeout_ms", 300000),
        "expect": {"timeout": 20000}, "reporter": [["json", {"outputFile": str(run / "playwright-result.json")}]],
        "outputDir": str(run / "browser-artifacts"),
        "use": {"baseURL": config["web_url"], "channel": config.get("browser_channel", "chromium"),
                "viewport": {"width": 1440, "height": 1000}, "trace": "off", "screenshot": "off"}
    }) + ");\n", encoding="utf-8")
    env = {**os.environ, "ALERT_SNAPSHOT_INPUT": str(run / "browser-input.json"), "ALERT_SNAPSHOT_OUTPUT": str(run)}
    result = subprocess.run([node, str(package / "cli.js"), "test", "--config", str(generated)], cwd=web,
                            env=env, capture_output=True, text=True, timeout=config.get("browser_timeout_ms", 300000) / 1000 + 60)
    # 로그에 주소·세션·키를 넣지 않도록 브라우저 시험도 제한한다. 원문은 git 밖에만 보관.
    (run / "browser-stdout.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    return result.returncode


def run_once(args) -> dict[str, Any]:
    folder = args.output.resolve()
    config_path = args.config or folder / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    at = datetime.now(KST)
    run = folder / args.mode / (at.strftime("%Y-%m-%d_%H%M%S") + "_" + uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": SCHEMA_VERSION, "mode": args.mode, "run_id": run.name,
              "at": at.isoformat(), "conditions": local_inventory(), "snapshots": 0}
    try:
        if args.collect_only:
            collection = collect_local(run, at, config.get("budget_policy"))
            save(run / "collection.json", collection)
            failed = [k for k,v in collection["sources"].items() if v["status"] != "ok"]
            report.update(status="collection_failed" if failed else "collection_only", collection=collection,
                          reason="수집만 실행; 대체안·실제 cs 프로젝트 서버 화면 확인 안 함")
        else:
            report.update(check_api(config, run, at, args.mode, args.force, args.archive_only))
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__)
        # 오류 문자열에는 인증 URL이 들어갈 수 있어 공개 요약에는 형식만 적는다.
        (run / "private-error.txt").write_text(str(exc), encoding="utf-8")
        failure_state = folder / args.mode / "failure-state.json"
        previous = json.loads(failure_state.read_text(encoding="utf-8")) if failure_state.exists() else {}
        signature = digest({"type": type(exc).__name__, "detail": str(exc)})
        report["should_notify"] = previous.get("signature") != signature
        save(failure_state, {"signature": signature, "run_id": run.name})
    else:
        failure_state = folder / args.mode / "failure-state.json"
        if failure_state.exists():
            save(failure_state, {"signature": None, "run_id": run.name})
    save(run / "report.json", report)
    return report


def check_api(config: dict[str, Any], run: Path, at: datetime, mode: str, force: bool, archive_only: bool = False) -> dict[str, Any]:
    """계약된 목록 API와 rt 접수 화면에 연결한다. 쓰기는 빈 브라우저에서만 한다."""
    import httpx

    if archive_only and mode != "real":
        raise ValueError("원본 보관 모드는 실제 소스에만 사용합니다")

    if not config.get("api_base"):
        return {"status": "configuration_required", "reason": "git 밖 config.json의 api_base 필요", "snapshots": 0}
    if mode == "mock":
        if config.get("environment") != "mock":
            raise ValueError("mock 서버 연결 설정에 environment=mock이 필요합니다")
        manifest = {"mode": "mock", "api_base": config["api_base"], "scenarios": []}
        exit_code = browser_capture(run, config, manifest)
        verdict = json.loads((run / "browser-verdict.json").read_text()) if (run / "browser-verdict.json").exists() else {}
        return {"status": "mock_passed" if exit_code == 0 and verdict.get("status") == "passed" else "failed",
                "snapshots": verdict.get("snapshots", 0), "browser_exit": exit_code, "real_alert_verified": False}
    collection_command = config.get("collection_command")
    if collection_command:
        result = subprocess.run(collection_command, capture_output=True, text=True, encoding="utf-8", timeout=config.get("collection_timeout_seconds", 120))
        if result.returncode:
            raise RuntimeError("설정된 경보 수집 명령이 실패했습니다")
        collected = json.loads(result.stdout)
        collection = collected["collection"]
        for name, raw in collected.get("raw_files", {}).items():
            if Path(name).name != name or not name.endswith("-raw.json"):
                raise ValueError("수집 원본 파일명 오류")
            save(run / name, raw)
        save(run / "runtime.json", collected.get("runtime", {}))
    else:
        collection = collect_local(run, at, config.get("budget_policy"))
    save(run / "collection.json", collection)
    body = collection.get("sources", {})
    # 호출·확인 시각은 변경 감지 대상이 아니다. 공급자 사건 목록만 비교한다.
    facts = {k: v.get("value") for k,v in body.items()}
    def stable(value):
        if isinstance(value, dict):
            return {k: stable(v) for k,v in value.items() if k not in {"confirmed_at", "from_cache", "window", "at", "checked_at"}}
        if isinstance(value, list):
            return sorted((stable(v) for v in value), key=lambda v: json.dumps(v,sort_keys=True,default=str))
        return value
    fingerprint = digest(stable(facts))
    failures = [name for name, value in body.items() if value.get("status") != "ok"]
    state_path = run.parent / ("state-archive.json" if archive_only else "state.json")
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    summary = {"sources_read": sum(v.get("status") == "ok" for v in body.values()), "sources_total": len(body),
               "source_failures": failures, "fingerprint": fingerprint, "snapshots": 0}
    response = None if archive_only else httpx.get(config["api_base"].rstrip("/") + "/v1/web/test-scenarios", timeout=config.get("api_timeout_seconds", 20))
    if archive_only:
        summary.update(status="archived_partial" if failures else "archived", reason="원본 보관만 실행; 점검용 사용자·접수·화면 생성 안 함")
    elif response.status_code == 404:
        summary.update(status="awaiting_api", reason="실제 cs 프로젝트 서버의 시험 API 응답은 404")
    elif response.status_code != 200:
        summary.update(status="catalog_failed")
    else:
        catalog = response.json()
        save(run / "catalog.json", catalog)
        if not isinstance(catalog, dict):
            summary.update(status="contract_mismatch")
        elif catalog.get("enabled") is False or catalog.get("realtime_enabled") is False:
            summary.update(status="test_scenarios_disabled")
        elif not config.get("web_url"):
            summary.update(status="web_configuration_required")
        elif not force and state.get("last_day") == at.date().isoformat() and state.get("fingerprint") == fingerprint and state.get("status") in ("passed", "no_live_alert"):
            summary.update(status="unchanged")
        else:
            codes = config.get("scenario_codes", ["test1rt"])
            if not codes or not all(isinstance(code, str) and code.startswith("test") and code.endswith("rt") for code in codes):
                raise ValueError("실시간 시험 코드만 설정해 주세요")
            manifest = {"mode": "real", "api_base": config["api_base"],
                        "scenarios": [{"code": code, "evidence": {"collection_run": run.name}} for code in codes],
                        "server_evidence": {"collection": collection, "catalog": catalog}}
            exit_code = browser_capture(run, config, manifest)
            verdict = json.loads((run / "browser-verdict.json").read_text()) if (run / "browser-verdict.json").exists() else {}
            summary.update(status=verdict.get("status", "failed") if exit_code == 0 else "failed", browser_exit=exit_code,
                           snapshots=verdict.get("snapshots", 0), verdict=verdict)
            if summary["status"] == "passed":
                # 대체안이 화면에 보인 것과 실제 경보를 피한 것을 따로 판정한다.
                verify_command = config.get("verification_command")
                if not verify_command:
                    summary.update(status="alternative_recheck_unconfigured")
                else:
                    result = subprocess.run(verify_command, input=(run / "alternatives.json").read_text(encoding="utf-8"),
                                            capture_output=True, text=True, encoding="utf-8", timeout=config.get("verification_timeout_seconds", 180))
                    verified = json.loads(result.stdout) if result.returncode == 0 else {"status": "alternative_recheck_failed", "exit_code": result.returncode}
                    save(run / "alternative-verification.json", verified)
                    summary.update(status=verified["status"], alternative_recheck=verified)
            if summary["status"] == "no_live_alert" and failures:
                summary.update(status="no_live_alert_incomplete", reason="API는 매칭 없음이나 일부 경보 소스를 못 읽음")
    if response is not None:
        summary["catalog_http"] = response.status_code
    signal = digest({"status": summary["status"], "failures": {name: {key: body[name].get(key) for key in ("status", "misses", "error_type")} for name in failures},
                     "fingerprint": fingerprint if "browser_exit" in summary else None})
    summary["should_notify"] = bool(summary["snapshots"]) or (signal != state.get("signal") and summary["status"] not in ("unchanged", "no_live_alert"))
    save(state_path, {"last_day": at.date().isoformat(), "fingerprint": fingerprint, "status": summary["status"], "signal": signal, "run_id": run.name})
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--mode", choices=("real", "mock"), default="real")
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--archive-only", action="store_true", help="설정된 실제 경보 원본만 보관. API 접수·브라우저 실행 안 함")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        with locked(args.output.resolve()):
            report = run_once(args)
    except FileExistsError:
        print(json.dumps({"status": "already_running"}))
        return 0
    print(json.dumps({k: report[k] for k in ("run_id", "status", "snapshots", "should_notify") if k in report}, ensure_ascii=True))
    return 0 if report["status"] in ("passed", "mock_passed", "no_live_alert", "unchanged", "collection_only", "archived") else 1


if __name__ == "__main__":
    raise SystemExit(main())
