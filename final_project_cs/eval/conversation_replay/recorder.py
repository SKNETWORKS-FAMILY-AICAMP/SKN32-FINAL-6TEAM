# -*- coding: utf-8 -*-
"""바깥 응답 녹화 · 재생 — 재생 시험의 mock 서버 역할. `[2026-10-19]` (재생 시험 계획 「실행 환경」 · 5단계)

제품 코드가 바깥으로 내보내는 HTTP 요청(관광공사 · 카카오 · 구글 · 날씨 · 공지 · 임베딩)을 한 곳에서 가로챈다.
  - `record` : 실제로 보내고 응답을 녹화 파일에 적는다(실조회 — 호출 수를 센다)
  - `replay` : 녹화에서 꺼내 돌려준다. 녹화에 없으면 **실제로 보내고 「실조회」로 표시**한다(`live_on_miss=True`, 기본)
               — `live_on_miss=False` 면 녹화에 없는 조회는 연결 오류로 돌려준다(완전히 닫힌 재생)
평가 대상(해석 모델 · 유료 대체 모델 · 팀 답 모델)은 녹화하지 않고 그대로 보낸다(`passthrough`) — 그것이 재는 대상이다. 호출 수 · 예산은 센다.

가로채는 곳: `httpx.HTTPTransport.handle_request`(httpx · openai SDK 모두 이 길) · `urllib.request.urlopen`(임베딩).
열쇠: 방법 + 주소(경로) + 정렬한 질의(비밀 값 이름은 뺀다) + 본문 해시. 비밀 키 · 인증 머리글은 녹화하지 않는다.
"""
from __future__ import annotations

import base64
import contextvars
from dataclasses import dataclass, field
import hashlib
import io
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit

SECRET_PARAMS = {"servicekey", "key", "apikey", "api_key", "appkey", "authkey", "auth_key", "serviceKey".lower(), "crtfc_key",
                 "access_token", "client_secret", "token", "cert_key", "certkey"}
VOLATILE_BODY_KEYS = {"keep_alive", "stream"}

_turn = contextvars.ContextVar("replay_turn", default=None)
_paused = contextvars.ContextVar("replay_paused", default=False)


def pause():
    """고객 역할 · 판정 모델 호출처럼 **시험 도구 자신의** 호출 — 녹화 · 예산 세기에서 뺀다(따로 센다)."""
    return _paused.set(True)


def resume(token) -> None:
    _paused.reset(token)


def set_turn(tag: str | None) -> None:
    """지금 처리 중인 에피소드 · 턴 이름 — 녹화 줄과 실조회 기록에 붙는다."""
    _turn.set(tag)


@dataclass
class Rule:
    """요청을 어떻게 다루나 — `record`(녹화 대상) · `pass`(평가 대상, 그대로 보냄) · `block`(보내지 않음)."""
    name: str
    match: Callable[[str, str, str], bool]     # (method, host, path) → bool
    action: str
    budget: int | None = None                 # 실제로 보낼 수 있는 최대 횟수(None = 제한 없음)
    unit_cost_usd: float = 0.0                # 한 번 어림 비용(보고용 — 예상)


def default_rules(*, llm_hosts: set[str], embed_redirect: str | None = None) -> list[Rule]:
    """기본 규칙 — `llm_hosts` 는 평가 대상 모델 주소(해석 모델 Ollama 터널 등)의 host:port."""
    def host_in(hosts):
        return lambda m, h, p: h in hosts

    rules = [
        # 임베딩(규정 검색) — 조회로 보고 녹화한다. 평가 대상 Ollama 와 같은 주소라도 /api/embed 는 녹화
        Rule("embed", lambda m, h, p: p.endswith("/api/embed") or p.endswith("/api/embeddings") or p.endswith("/v1/embeddings"),
             "record", budget=None),
        Rule("llm_local", lambda m, h, p: h in llm_hosts and p.startswith("/api/"), "pass"),
        Rule("llm_paid", lambda m, h, p: h == "api.openai.com", "pass", budget=600, unit_cost_usd=0.003),
        Rule("google", lambda m, h, p: h.endswith("googleapis.com"), "record", budget=60, unit_cost_usd=0.032),
        Rule("kakao", lambda m, h, p: h.endswith("kakao.com"), "record", budget=2000),
        Rule("public", lambda m, h, p: True, "record", budget=5000),
    ]
    return rules


@dataclass
class Recorder:
    cassette: Path                        # 녹화 파일(JSONL, 한 줄 = 한 응답)
    mode: str = "replay"                  # record | replay
    rules: list[Rule] = field(default_factory=list)
    live_on_miss: bool = True
    embed_url: str | None = None          # /api/embed 를 보낼 다른 주소(해석 모델 서버에 임베딩 모델이 없을 때)
    calls: list[dict[str, Any]] = field(default_factory=list)
    _store: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _live_count: dict[str, int] = field(default_factory=dict)
    _orig: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cassette.exists():
            with self.cassette.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        row = json.loads(line)
                        self._store.setdefault(row["key"], row)

    # ── 열쇠 ───────────────────────────────────────────────────
    @staticmethod
    def key_of(method: str, url: str, body: bytes | None) -> tuple[str, str, str, str]:
        parts = urlsplit(url)
        host = parts.netloc.lower()
        query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in SECRET_PARAMS)
        body_norm = b""
        if body:
            try:
                obj = json.loads(body)
                if isinstance(obj, dict):
                    obj = {k: v for k, v in obj.items() if k not in VOLATILE_BODY_KEYS}
                body_norm = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()
            except (ValueError, UnicodeDecodeError):
                body_norm = body
        raw = json.dumps([method.upper(), host, parts.path, query, hashlib.sha256(body_norm).hexdigest()], ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:32], host, parts.path, json.dumps(query, ensure_ascii=False)

    def rule_for(self, method: str, host: str, path: str) -> Rule:
        for r in self.rules:
            if r.match(method, host, path):
                return r
        return Rule("other", lambda *a: True, "record")

    # ── 기록 ───────────────────────────────────────────────────
    def _log(self, **row: Any) -> None:
        with self._lock:
            self.calls.append({"turn": _turn.get(), "at": time.time(), **row})

    def _save(self, row: dict[str, Any]) -> None:
        with self._lock:
            if row["key"] in self._store:
                return
            self._store[row["key"]] = row
            self.cassette.parent.mkdir(parents=True, exist_ok=True)
            with self.cassette.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _spend(self, rule: Rule) -> bool:
        with self._lock:
            n = self._live_count.get(rule.name, 0)
            if rule.budget is not None and n >= rule.budget:
                return False
            self._live_count[rule.name] = n + 1
            return True

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {"by_rule": {}, "cassette_rows": len(self._store)}
        for c in self.calls:
            g = out["by_rule"].setdefault(c["rule"], {"replayed": 0, "live": 0, "refused": 0, "passthrough": 0, "errors": 0})
            g[c["how"]] = g.get(c["how"], 0) + 1
        cost = 0.0
        for r in self.rules:
            g = out["by_rule"].get(r.name)
            if g and r.unit_cost_usd:
                n = g.get("live", 0) + g.get("passthrough", 0)
                g["est_cost_usd"] = round(n * r.unit_cost_usd, 3)
                cost += n * r.unit_cost_usd
        out["est_cost_usd_total"] = round(cost, 3)
        out["budgets"] = {r.name: r.budget for r in self.rules if r.budget is not None}
        return out

    # ── 한 요청 처리(전송 함수와 상관없는 부분) ─────────────────────────
    def handle(self, method: str, url: str, body: bytes | None, send: Callable[[str], tuple[int, dict[str, str], bytes]]):
        """`send(url)` — 실제로 보내는 함수. (상태, 머리글, 본문, 어떻게) 를 돌려준다."""
        key, host, path, query = self.key_of(method, url, body)
        if _paused.get():
            status, headers, content = send(url)
            self._log(rule="tool_model", how="passthrough", host=host, path=path, status=status)
            return status, headers, content
        rule = self.rule_for(method, host, path)
        if rule.action == "pass":
            if not self._spend(rule):
                self._log(rule=rule.name, how="refused", host=host, path=path)
                raise BudgetExceeded(f"{rule.name} 예산 {rule.budget}회 초과 — 멈춤")
            started = time.monotonic()
            try:
                status, headers, content = send(url)
            except Exception as exc:
                self._log(rule=rule.name, how="errors", host=host, path=path, error=type(exc).__name__)
                raise
            self._log(rule=rule.name, how="passthrough", host=host, path=path, status=status,
                      seconds=round(time.monotonic() - started, 3))
            return status, headers, content
        if rule.action == "block":
            self._log(rule=rule.name, how="refused", host=host, path=path)
            raise ConnectionError(f"재생 시험: {host}{path} 는 막힌 조회")
        if self.mode == "replay" and key in self._store:
            row = self._store[key]
            self._log(rule=rule.name, how="replayed", host=host, path=path, key=key)
            return row["status"], row.get("headers") or {}, _decode(row)
        if self.mode == "replay" and not self.live_on_miss:
            self._log(rule=rule.name, how="refused", host=host, path=path, key=key, miss=True)
            raise ConnectionError(f"재생 시험: 녹화에 없는 조회 {host}{path}")
        if not self._spend(rule):
            self._log(rule=rule.name, how="refused", host=host, path=path, key=key)
            raise BudgetExceeded(f"{rule.name} 실조회 예산 {rule.budget}회 초과 — 멈춤")
        target = url
        if rule.name == "embed" and self.embed_url:
            target = self.embed_url.rstrip("/") + path
        try:
            status, headers, content = send(target)
        except Exception as exc:
            self._log(rule=rule.name, how="errors", host=host, path=path, key=key, error=type(exc).__name__)
            raise
        self._log(rule=rule.name, how="live", host=host, path=path, key=key, status=status)
        if 200 <= status < 300:
            self._save({"key": key, "host": host, "path": path, "query": query, "status": status,
                        "headers": {k: v for k, v in headers.items() if k.lower() in ("content-type",)},
                        **_encode(content), "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "turn": _turn.get()})
        return status, headers, content

    # ── 설치 ───────────────────────────────────────────────────
    def install(self) -> "Recorder":
        import httpx
        import urllib.request

        if self._orig:
            return self
        rec = self
        orig_handle = httpx.HTTPTransport.handle_request
        orig_urlopen = urllib.request.urlopen
        self._orig = {"handle": orig_handle, "urlopen": orig_urlopen}

        def handle_request(transport, request):
            body = request.read() if request.stream is not None else b""

            def send(target: str):
                req = request if target == str(request.url) else httpx.Request(request.method, target, headers=request.headers,
                                                                                content=body)
                resp = orig_handle(transport, req)
                content = resp.read()
                return resp.status_code, dict(resp.headers), content

            status, headers, content = rec.handle(request.method, str(request.url), body, send)
            headers = {k: v for k, v in headers.items() if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")}
            return httpx.Response(status, headers=headers, content=content, request=request)

        def urlopen(req, *args, **kwargs):
            if isinstance(req, str):
                url, method, data, hdrs = req, "GET", None, {}
            else:
                url, method, data, hdrs = req.full_url, req.get_method(), req.data, dict(req.header_items())

            def send(target: str):
                r2 = urllib.request.Request(target, data=data, headers=hdrs, method=method)
                with orig_urlopen(r2, *args, **kwargs) as resp:
                    return resp.status, dict(resp.headers), resp.read()

            status, headers, content = rec.handle(method, url, data, send)
            return _FakeResponse(status, headers, content)

        httpx.HTTPTransport.handle_request = handle_request
        urllib.request.urlopen = urlopen
        return self

    def uninstall(self) -> None:
        import httpx
        import urllib.request

        if not self._orig:
            return
        httpx.HTTPTransport.handle_request = self._orig["handle"]
        urllib.request.urlopen = self._orig["urlopen"]
        self._orig = {}


class BudgetExceeded(RuntimeError):
    """예산을 넘을 실조회 · 유료 호출 — 시험을 멈추고 보고한다(재생 시험 5단계 「상한을 먼저 정하고, 넘을 것 같으면 멈춤」)."""


class _FakeResponse(io.BytesIO):
    def __init__(self, status: int, headers: dict[str, str], content: bytes):
        super().__init__(content)
        self.status = status
        self.headers = headers

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _encode(content: bytes) -> dict[str, str]:
    try:
        return {"text": content.decode("utf-8")}
    except UnicodeDecodeError:
        return {"b64": base64.b64encode(content).decode()}


def _decode(row: dict[str, Any]) -> bytes:
    if "text" in row:
        return row["text"].encode("utf-8")
    return base64.b64decode(row.get("b64") or "")
