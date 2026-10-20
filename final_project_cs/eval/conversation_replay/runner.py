# -*- coding: utf-8 -*-
"""재생 실행기 — 에피소드 하나를 시험 DB 에 넣고 **제품의 웹 채팅 입구 그대로** 돌린다. `[2026-10-19]`

  시작 상태 넣기 → 대본 재생(A) → [일찍 끝남 · 갈림 판정] → 갈리면 고객 역할 모델로 잇기(B) → 끝 판 읽기

★제품 코드는 고치지 않는다. 운영과 같은 조립(`create_app()` — `build_domain_routers` + `wire_optional_features`)으로 앱을 띄우고
  `POST /v1/web/trips/{id}/messages` 에 원래 대화 시각(`at`)을 실어 보낸다 — 대화 기록(`_log_turn`)까지 운영과 같은 길이다.
  바꾼 것은 둘뿐: 웹 사용량 제한을 끄고(세기만) 개발 모드를 켠다(답에 해석 결과 · 근거가 실린다 — 처리는 같다).
★갈림 처리(재생 시험 계획 「갈림 처리」):
  1. 일찍 끝남 — 대본이 남았는데 끝 상태 조건을 이미 모두 만족하면 그 자리에서 성공, 남은 원문은 보내지 않는다.
  2. 갈림 — 다음 원문의 역할과 봇의 지금 상태가 어긋나면 그 지점부터 B 로 잇는다. 어긋남 셋:
     a) 봇이 원래 대화에 없던 열린 질문을 냈는데 다음 원문이 그 질문의 답 모양이 아니다
     b) 다음 원문은 「직전 봇 질문의 답」인데 봇이 이번에는 질문을 내지 않았다
     c) 다음 원문은 「같은 요청 반복 · 항의」인데 그 요청이 이미 반영돼 있다(저장이 있었고 상태 조건에 위반이 없다)
  3. 그 밖은 대본 끝까지 보낸다.
★B: 고객 역할 모델(평가 대상과 다른 모델 · 온도 0 · 시드 고정)이 목표와 원문 대본을 보고 다음 고객 말을 쓴다.
  턴 상한(실제 고객 턴 수 95번째 백분위 + 2)에 닿도록 끝나지 않으면 「일 끝남 실패」. B 는 2회 — 같으면 끝, 다르면 1회 더 다수결.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import time
from typing import Any, Callable

from . import recorder as R
from .conditions import FAIL, PASS, evaluate, overall
from .patterns import answer_shape, claims_done, fail_types, is_open_question
from .state import KST, TripView, parse_dt

#: x600 서버 운영 설정과 같게 맞추는 값(2026-10-19 x600 서버 `.env` 의 이름 · 비밀 아닌 값을 읽어 확인)
X600_LIKE = {
    "ACOP_OLLAMA_MODEL": "tripilot-pointer:e4b-ft", "ACOP_OLLAMA_POINTER_MODEL": "tripilot-pointer:e4b-ft",
    "ACOP_OLLAMA_NUM_CTX": "8192", "ACOP_OLLAMA_TIMEOUT_SECONDS": "150",
    "ACOP_LLM_FAILOVER_ENABLED": "true", "ACOP_LLM_FAILOVER_MODEL": "gpt-6-luna", "ACOP_LLM_FAILOVER_PRIMARY_TIMEOUT_SECONDS": "9",
    "ACOP_EMBEDDING_PROVIDER": "ollama", "ACOP_OLLAMA_EMBEDDING_MODEL": "bge-m3:latest", "ACOP_EMBEDDING_MODEL": "text-embedding-3-small",
    "ACOP_LLM_PROVIDER": "openai", "ACOP_LLM_MODEL": "gpt-4o-mini", "ACOP_WEATHER_PROVIDER": "open_meteo",
    "ACOP_MOBILITY_LOCAL_ROUTER": "true", "ACOP_MOBILITY_GH_URL": "",
}


def prepare_env(*, db_url: str, ollama_url: str, keys_files: list[Path], extra: dict[str, str] | None = None) -> list[str]:
    """앱을 import 하기 **전에** 부른다(설정은 처음 읽을 때 고정). 비밀 값은 화면에 내지 않는다 — 넣은 이름만 돌려준다."""
    from .seed import assert_test_db

    assert_test_db(db_url)
    names = []
    for path in keys_files:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k.startswith("ACOP_") and k not in ("ACOP_DATABASE_URL", "ACOP_OLLAMA_BASE_URL", "ACOP_ENV") and k not in X600_LIKE:
                os.environ[k] = v.strip().strip('"').strip("'")
                names.append(k)
    os.environ.update(X600_LIKE)
    os.environ.update({"ACOP_DATABASE_URL": db_url, "ACOP_OLLAMA_BASE_URL": ollama_url, "ACOP_TENANT_ID": "demo",
                       "TZ": "Asia/Seoul", "PGTZ": "Asia/Seoul"})
    os.environ.update(extra or {})
    return sorted(names)


class Harness:
    def __init__(self, *, rec: R.Recorder, customer: Callable[..., dict[str, Any]] | None, turn_cap: int,
                 judge: Callable[[str, list[str]], str] | None = None, log: Callable[[str], None] = print):
        self.rec = rec
        self.customer = customer
        self.turn_cap = turn_cap
        self.judge = judge
        self.log = log
        self.client = None
        self.raw = None
        import uuid as _uuid

        self.run_id = _uuid.uuid4().hex[:8]       # 같은 시험 DB 에서 여러 회차를 돌려도 id 가 겹치지 않게
        self._catalog: dict[str, dict] | None = None

    def catalog_find(self, name: str) -> dict | None:
        """표적 에피소드의 장소 이름 → 시험 DB 의 장소(공용 `places`) 또는 장소 목록(`place_catalog`) 한 행. 정규화 이름이 같을 때만."""
        from app.infrastructure.db.session import get_connection

        from .patterns import norm

        if self._catalog is None:
            self._catalog = {}
            kinds = {"39": "dining", "32": "lodging"}
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("SELECT title, source, content_id, content_type_id, latitude, longitude FROM place_catalog")
                for title, source, cid, ctype, lat, lon in cur.fetchall():
                    self._catalog.setdefault(norm(title), {"name": title, "kind": kinds.get(str(ctype), "activity"), "latitude": lat,
                                                           "longitude": lon, "source_name": source, "source_content_id": cid,
                                                           "source_content_type_id": ctype, "attributes": {"replay_from": "place_catalog"}})
                cur.execute("SELECT place_id, name, kind, latitude, longitude, source_name, source_content_id, source_content_type_id, "
                            "attributes FROM places WHERE trip_scope IS NULL")
                for pid, name_, kind, lat, lon, sn, sc, st, attrs in cur.fetchall():
                    self._catalog[norm(name_)] = {"place_id": str(pid), "name": name_, "kind": kind, "latitude": lat, "longitude": lon, "source_name": sn,
                                                  "source_content_id": sc, "source_content_type_id": st, "attributes": attrs or {}}
        return self._catalog.get(norm(name))

    # ── 앱 ─────────────────────────────────────────────────────
    def start(self) -> None:
        from fastapi.testclient import TestClient

        from app.domains.travel_ops.modules.web_account import web_guard
        from app.presentation.api.app import create_app

        real = web_guard.values
        web_guard.values = lambda tenant: {**real(tenant), "web.dev_mode": "on", "web.limits_enabled": False}
        # ★제품 안의 예외는 운영처럼 500 답으로 받는다(시험 도구가 멈추지 않게) — 그 턴은 오류 턴으로 센다
        app = create_app()
        self.last_exc = None

        async def _record_exc(request, exc):          # 500 의 원인(예외 종류 · 위치)을 결과에 남긴다 — 답은 운영처럼 500
            import traceback

            from starlette.responses import JSONResponse

            tb = traceback.extract_tb(exc.__traceback__)
            where = f" @ {tb[-1].filename.split('final_project_cs')[-1]}:{tb[-1].lineno}" if tb else ""
            self.last_exc = f"{type(exc).__name__}: {str(exc)[:200]}{where}"
            return JSONResponse({"error": {"code": "internal_error"}}, status_code=500)

        app.add_exception_handler(Exception, _record_exc)
        self.client = TestClient(app, raise_server_exceptions=False)

    def _post(self, seeded, text: str, at: datetime, rid: str) -> tuple[int, dict[str, Any], float]:
        t0 = time.monotonic()
        resp = self.client.post(f"/v1/web/trips/{seeded.trip_id}/messages", headers={"X-User-Key": seeded.user_key},
                                json={"request_id": rid, "message": text, "at": at.isoformat()})
        secs = time.monotonic() - t0
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text[:500]}
        return resp.status_code, body, secs

    # ── 한 턴 ───────────────────────────────────────────────────
    def turn(self, ep: dict, seeded, *, k: int, text: str, role: str, at: datetime, mode: str, tag: str) -> dict[str, Any]:
        from app.infrastructure.db.session import get_connection

        from .seed import read_view

        rev = {v: k_ for k_, v in seeded.item_map.items()}
        R.set_turn(f"{tag}:{ep['episode_id']}#{k}")
        mark = len(self.rec.calls)
        with get_connection() as conn:
            before = read_view(conn, seeded.trip_id, rev)
        self.last_exc = None
        status, body, secs = self._post(seeded, text, at, f"rp-{tag}-{k}")
        with get_connection() as conn:
            after = read_view(conn, seeded.trip_id, rev)
            model_path, evidence_db = _case_extras(conn, body.get("case_id"), after, before)
        calls = self.rec.calls[mark:]
        answer = str(body.get("answer") or "")
        evidence = "\n".join([evidence_db, json.dumps(body.get("basis") or {}, ensure_ascii=False, default=str),
                              *[(self.rec._store.get(c.get("key") or "", {}) or {}).get("text", "")[:20000] for c in calls]])
        choices = body.get("choices") or []
        return {"k": k, "mode": mode, "customer": text, "role": role, "at": at.isoformat(), "http": status,
                "answer": answer, "status": body.get("status"), "reason": body.get("reason"), "choices": choices,
                "open_question": is_open_question(answer, choices) and after.version == before.version,
                "saved": after.version != before.version, "version_before": before.version, "version_after": after.version,
                "view_after": after.as_dict(), "seconds": round(secs, 3), "model_path": model_path,
                "fail_types": fail_types(answer), "claims_done": claims_done(answer),
                "lookups": [{"rule": c["rule"], "how": c["how"], "host": c.get("host"), "path": c.get("path")} for c in calls],
                "live_lookups": sum(1 for c in calls if c["how"] == "live"), "evidence": evidence[:60000],
                "error": None if status == 200 else f"http {status}: {json.dumps(body, ensure_ascii=False)[:300]}",
                "exception": self.last_exc}

    # ── 에피소드 ─────────────────────────────────────────────────
    def run_episode(self, ep: dict, compiled: dict, *, tag: str, b_from: int | None = None) -> dict[str, Any]:
        """A 재생. 갈리면 그 자리에서 B 로 잇는다. `b_from` 이 주어지면(B 반복) 그 턴부터 B — 앞부분은 A 로 다시 보낸다."""
        from app.infrastructure.db.session import get_connection

        from .seed import read_view, seed_episode

        with get_connection() as conn:
            seeded = seed_episode(conn, ep, self.raw, run_tag=f"{self.run_id}:{tag}", catalog_find=self.catalog_find)
            rev = {v: k_ for k_, v in seeded.item_map.items()}
            start = read_view(conn, seeded.trip_id, rev)
        now = parse_dt(ep["now"]) or datetime.now(KST)
        turns: list[dict[str, Any]] = []
        script = ep["script"]
        res: dict[str, Any] = {"episode_id": ep["episode_id"], "tag": tag, "start": start.as_dict(), "seed_notes": seeded.notes,
                               "diverged_at": None, "divergence": None, "early_finish": False, "cap_hit": False}
        k = 0
        while k < len(script):
            line = script[k]
            if turns:
                if self._finished(start, turns, compiled):
                    res["early_finish"] = True
                    break
                if b_from is not None:
                    why = "B 반복(첫 회와 같은 갈림 지점)" if k == b_from else None
                else:
                    why = self._diverges(ep, k, turns[-1], start, turns, compiled)
                if why:
                    res["diverged_at"], res["divergence"] = k, why
                    break
            at = _when(line, now, k)
            turns.append(self.turn(ep, seeded, k=k, text=line["text"], role=line["role"], at=at, mode="A", tag=tag))
            k += 1
        if res["diverged_at"] is not None:
            self._continue_b(ep, seeded, start, turns, compiled, now=now, tag=tag, res=res)
        with get_connection() as conn:
            res["end"] = read_view(conn, seeded.trip_id, rev).as_dict()
        res["turns"] = turns
        return res

    def _cond_state(self, start: TripView, turns: list[dict], compiled: dict) -> tuple[list[str], list[str]]:
        end = TripView.from_dict(turns[-1]["view_after"])
        answers = [t["answer"] for t in turns]
        saves = sum(1 for t in turns if t["saved"])
        e = [evaluate(x["dsl"], start=start, end=end, answers=answers, saves=saves, judge=self.judge) for x in compiled["end"]]
        f = [evaluate(x["dsl"], start=start, end=end, answers=answers, saves=saves) for x in compiled["forbidden"]
             if x["dsl"].get("op") not in ("no_false_done", "no_invented_fact")]
        return e, f

    def _finished(self, start: TripView, turns: list[dict], compiled: dict) -> bool:
        e, f = self._cond_state(start, turns, compiled)
        return bool(e) and overall(e + f) == PASS

    def _diverges(self, ep: dict, k: int, last: dict, start: TripView, turns: list[dict], compiled: dict) -> str | None:
        line = ep["script"][k]
        role = line.get("role") or "새 요청"
        if role == "직전 봇 질문의 답" and not last.get("open_question"):
            return "b) 원문은 직전 봇 질문의 답인데 봇이 이번에는 질문을 내지 않음"
        if last.get("open_question") and role != "직전 봇 질문의 답":
            orig_q = _orig_question_after(ep, k - 1)
            shape = answer_shape(line["text"], len(last.get("choices") or []),
                                 [str(c.get("label") or c.get("text") or c) for c in last.get("choices") or []])
            if not orig_q and shape is None:
                return "a) 원래 대화에 없던 열린 질문 — 다음 원문이 그 답 모양이 아님"
        if role in ("같은 요청 반복", "항의") and any(t["saved"] for t in turns):
            e, f = self._cond_state(start, turns, compiled)
            state_e = [g for x, g in zip(compiled["end"], e) if x["dsl"].get("op") not in ("answer", "answer_judge", "manual")]
            if state_e and FAIL not in state_e and FAIL not in f and PASS in state_e:
                return "c) 반복 · 항의인데 그 요청이 이미 반영됨"
        return None

    def _continue_b(self, ep, seeded, start, turns, compiled, *, now, tag, res) -> None:
        if self.customer is None:
            res["b"] = "고객 역할 모델 없음 — B 를 잇지 않음(갈림 지점에서 멈춤)"
            return
        k = len(turns)
        while True:
            if turns and self._finished(start, turns, compiled):
                res["early_finish"] = True
                return
            if k >= self.turn_cap:
                res["cap_hit"] = True
                return
            nxt = self.customer(ep=ep, turns=turns, k=k)
            if nxt.get("stop"):
                res["b_stop"] = nxt.get("why") or "고객 역할 모델이 멈춤"
                return
            at = (parse_dt(turns[-1]["at"]) if turns else now) + timedelta(seconds=40)
            turns.append(self.turn(ep, seeded, k=k, text=nxt["text"], role=nxt.get("role") or "새 요청", at=at, mode="B", tag=tag))
            k += 1


def _when(line: dict, now: datetime, k: int) -> datetime:
    at = parse_dt(line.get("at"))
    return at or (now + timedelta(seconds=40 * k))


def _orig_question_after(ep: dict, k: int) -> bool:
    """원래 대화에서 고객 줄 k 바로 뒤 봇 답이 열린 질문이었나."""
    script, bots = ep["script"], ep.get("orig_bot") or []
    if not (0 <= k < len(script)) or script[k].get("n") is None:
        return False
    n = script[k]["n"]
    nxt = script[k + 1]["n"] if k + 1 < len(script) and script[k + 1].get("n") is not None else 10 ** 9
    for b in bots:
        if b.get("n") is not None and n < b["n"] < nxt:
            return is_open_question(b.get("text"))
    return False


def _case_extras(conn, case_id: Any, after: TripView, before: TripView) -> tuple[dict | None, str]:
    """그 턴 Case 의 모델 경로(로컬 · 유료 대체) · 근거 글(장소 자료 · 일정 시각)."""
    path = None
    if case_id:
        with conn.cursor() as cur:
            cur.execute("SELECT state_json->'decision'->'model_path', state_json->'decision_shadow'->'model_path' FROM customer_cases "
                        "WHERE case_id=%s", (str(case_id),))
            row = cur.fetchone()
            if row:
                path = row[0] or row[1]
    ids = {i.place_id for i in after.items + before.items if i.place_id}
    texts = [f"{i.title} {i.place or ''} {i.start} {i.end}" for i in after.items + before.items]
    if ids:
        with conn.cursor() as cur:
            cur.execute("SELECT name, attributes::text FROM places WHERE place_id = ANY(%s::uuid[])", (list(ids),))
            texts += [f"{n} {a}" for n, a in cur.fetchall()]
    return path, "\n".join(texts)


def openai_customer(*, model: str, seed: int, api_key: str) -> Callable[..., dict[str, Any]]:
    """B 고객 역할 — OpenAI 모델(평가 대상인 해석 모델 · 대체 모델 · 팀 답 모델과 다른 모델), 온도 0 · 시드 고정."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    system = ("너는 여행 비서 앱을 쓰는 한국인 고객이다. 목표를 이루려고 짧게 말한다. 원래 고객이 쓴 문장을 먼저 쓰되, "
              "봇이 물으면 원래 말투로 짧게 답한다(번호 · 네/아니요 · 장소 이름). 새 사실을 지어내지 않는다. "
              "목표가 이미 이뤄졌으면 stop 을 true 로 한다. JSON 한 줄: {\"text\": 고객 말, \"role\": 새 요청|직전 봇 질문의 답|같은 요청 반복|항의|잡담, "
              "\"stop\": true|false, \"why\": 멈춘 이유}")

    def call(*, ep: dict, turns: list[dict], k: int) -> dict[str, Any]:
        convo = "\n".join(f"고객: {t['customer']}\n봇: {t['answer'][:700]}" for t in turns)
        left = " / ".join(f"「{s['text']}」({s['role']})" for s in ep["script"][k:]) or "(남은 원문 없음)"
        user = (f"목표: {ep['goal']}\n원래 대본 전체: " + " / ".join(f"「{s['text']}」" for s in ep["script"]) +
                f"\n아직 안 보낸 원문: {left}\n지금까지 대화:\n{convo}\n다음 고객 말을 JSON 한 줄로.")
        token = R.pause()
        try:
            resp = client.chat.completions.create(model=model, temperature=0, seed=seed, response_format={"type": "json_object"},
                                                  messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        finally:
            R.resume(token)
        try:
            out = json.loads(resp.choices[0].message.content or "{}")
        except ValueError:
            out = {"stop": True, "why": "고객 역할 모델 답 형식 오류"}
        out["model"] = f"{model}@{getattr(resp, 'system_fingerprint', None)}"
        if not out.get("stop") and not str(out.get("text") or "").strip():
            out = {"stop": True, "why": "빈 고객 말"}
        return out

    return call


def openai_judge(*, model: str, seed: int, api_key: str) -> Callable[[str, list[str]], str]:
    """뜻을 봐야 하는 답 조건(`answer_judge`)의 판정 모델 — 평가 대상과 다른 모델. pass · fail · unknown."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    cache: dict[tuple, str] = {}

    def call(criterion: str, answers: list[str]) -> str:
        key = (criterion, tuple(answers))
        if key in cache:
            return cache[key]
        token = R.pause()
        try:
            resp = client.chat.completions.create(
                model=model, temperature=0, seed=seed, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": "여행 비서 답이 판정 기준을 만족하는지 본다. 기준 밖의 것은 보지 않는다. "
                                                        "JSON: {\"verdict\": \"pass\"|\"fail\"|\"unknown\", \"why\": 짧게}"},
                          {"role": "user", "content": f"판정 기준: {criterion}\n봇 답들:\n" + "\n---\n".join(a[:1500] for a in answers)}])
        finally:
            R.resume(token)
        try:
            v = json.loads(resp.choices[0].message.content or "{}").get("verdict")
        except ValueError:
            v = "unknown"
        cache[key] = v if v in ("pass", "fail", "unknown") else "unknown"
        return cache[key]

    return call


def load_compiled(path: Path | None, eps: list[dict]) -> dict[str, dict]:
    from . import compile as C

    model_rows: dict[str, dict] = {}
    if path and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if not row.get("missing"):
                    model_rows[row["episode_id"]] = row
    return {ep["episode_id"]: C.compile_episode(ep, model_rows.get(ep["episode_id"])) for ep in eps}

