# -*- coding: utf-8 -*-
"""규정 질문의 **재순위 + 검증 단계** — 후보 N개를 모델이 다시 고르고, 직접 답이 안 되는 줄은 버린다. `[2026-10-15]`

★왜. 채팅 규정 답은 질문 벡터와 가장 가까운 조각 3개를 점수 문턱(0.55)만 넘기면 싣는다. 독립 질문 B 48문제에서 정답 규정이 상위 3개 안에 든 비율이
  30/48 = 62.5% 였고(양식 목표 0.90), 후보를 20개로 넓힌 뒤 모델이 「고객 질문에 **직접 답이 되는** 줄」만 고르게 하면 같은 방식의 보류 세트에서
  63/68 = 92.6% 였다(2026-10-07 보고서 §7-4 · 오응답 보고서 §2). 이 모듈이 그 두 단계를 제품 길에 꽂는다 — **스위치 `travel.question.rerank.mode`**.
★세 가지 방식.
    off     지금과 똑같다(`search_policy` 그대로 · 모델 호출 없음). **기본값.**
    shadow  답은 지금 방식으로 하고, 뒤에서 재순위를 돌려 고른 줄을 로그·세는 값에만 남긴다(고객 응답 시간 0 추가) — 켜기 전 실제 질문으로 확인용.
    on      재순위한 줄만 싣는다. 모델이 아무것도 안 고르면 「규정에서 못 찾았어요」로 답한다(검증 단계).
★후보를 어디서 뽑나(`first_stage`).
    operating      지금 색인(직원용 규정 본문의 벡터)에서 상위 N개. 정답이 상위 20개 안에 있는 비율의 천장이 독립 질문 B 85.4%(41/48)라 목표 0.90 에 못 미친다.
    customer_text  「문서 제목 / 절 제목: 고객용 문장」을 임베딩한 색인(실험의 색인 E)에서 상위 N개 — 같은 천장이 100%(48/48). 이 색인은 **DB 를 안 바꾸고**
                   프로세스 안에서 만든다(규정 절 100여 개 · 첫 사용 전 `warm` 으로 한 번 임베딩). 아직 안 만들어졌으면 지금 색인으로 답하고 이유를 남긴다.
★안전.
    · 모델을 못 부르거나(꺼짐 · 시간 초과 · 형식 오류 · 서킷 열림 · 시간 예산 부족) 후보가 없으면 **지금 방식 결과로 답한다** — 대신 이유를 `info["status"]` 에 남기고
      세어 경고로 올린다(조용히 넘기지 않는다, RULE.md §3.2). 유료 API 로는 넘기지 않는다(질문마다 한 번 더 드는 호출이라 유료 상한을 먹지 않게).
    · 고른 줄도 **점수 문턱**(`min_score`)을 넘어야 보인다. 문턱 점수는 후보를 뽑은 색인의 점수이고, 지금 방식으로 돌아갈 때는 지금 문턱(0.55)을 쓴다 — `info["gate"]`.
    · 고르는 것은 번호뿐이다(문장을 만들지 않는다). 실을 문장은 `question_answer` 가 규정 문서의 고객용 문장에서 꺼낸다.
★시간. 고객 응답 15초 안에서 요청 해석이 쓴 시간(`llm_failover.current_path()["seconds"]`)과 이 모듈이 이미 쓴 시간을 뺀 남은 시간이 `min_remaining_seconds`
  보다 적으면 재순위를 건너뛴다. 모델 호출 제한은 `min(timeout_seconds, 남은 시간)`.
★모델. `rerank.model` 이 비면 요청 해석과 **같은 모델**(`ollama_model`)을 같은 문맥 길이로 부른다 — 12GB GPU 에서 모델을 번갈아 올리는 일(교체 30초)이 없다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

#: 실험(`program/scripts/rag_gate/rag_improve/rerank_lib.py`)과 **같은 지시문** — 지시문이 다르면 재어 둔 값이 이 길을 설명하지 못한다
SYSTEM = ("당신은 여행 서비스의 규정 검색 재순위 담당입니다. 고객 질문과 후보 안내 문장들이 주어집니다. "
          "각 후보는 서비스가 고객에게 그대로 보여 줄 안내 문장입니다. 고객 질문에 **직접 답이 되는** 문장만 골라 가장 알맞은 순서로 번호를 적습니다. "
          "관련 주제여도 질문이 묻는 구체 내용에 답하지 않는 문장은 고르지 않습니다. 직접 답하는 문장이 없으면 빈 목록입니다. 최대 3개. "
          '출력은 JSON 한 줄: {"ranking":[번호,...]}')

MODES = ("off", "shadow", "on")
BACKENDS = ("local", "api")
FIRST_STAGES = ("operating", "customer_text")

#: 실행 중 센 값 — 운영이 「재순위가 쓰이고 있나 · 얼마나 지금 방식으로 돌아가나」를 볼 수 있게(조용한 폴백을 만들지 않는다)
STATS: dict[str, int] = {"calls": 0, "ok": 0, "empty": 0, "failed": 0, "skipped": 0, "plain_fallback": 0, "index_cold": 0,
                         "shadow_runs": 0, "shadow_top1_diff": 0, "shadow_busy": 0}


@dataclass(frozen=True)
class RerankSettings:
    mode: str
    first_stage: str
    candidates: int
    max_picks: int
    min_score: float
    model: str
    timeout_seconds: float
    min_remaining_seconds: float
    total_seconds: float
    failures: int
    open_seconds: float
    embed_timeout_seconds: float
    backend: str = "local"          # local: 요청 해석과 같은 로컬 모델 · api: 서버용 OpenAI 키로 유료 모델(루나급) — 호출 예산 상한 안에서만
    api_model: str = ""              # 비면 `llm_failover_model`
    api_timeout_seconds: float = 6.0


def load_settings(guardrails: Any) -> RerankSettings:
    """가드레일 `travel.question.rerank.*` 을 읽는다. 값이 잘못되면 **기동·호출을 거부**한다(조용히 꺼진 척하지 않는다)."""
    def get(name: str) -> Any:
        return guardrails.get(f"travel.question.rerank.{name}")

    mode, stage = str(get("mode")), str(get("first_stage"))
    if mode not in MODES:
        raise ValueError(f"travel.question.rerank.mode 는 {MODES} 중 하나여야 한다(따옴표 필수 — 맨 off/on 은 YAML 불리언): {mode!r}")
    if stage not in FIRST_STAGES:
        raise ValueError(f"travel.question.rerank.first_stage 는 {FIRST_STAGES} 중 하나여야 한다: {stage!r}")
    backend = str(get("backend"))
    if backend not in BACKENDS:
        raise ValueError(f"travel.question.rerank.backend 는 {BACKENDS} 중 하나여야 한다: {backend!r}")
    return RerankSettings(
        mode=mode, first_stage=stage, candidates=int(get("candidates")), max_picks=int(get("max_picks")),
        min_score=float(get("min_score")), model=str(get("model") or ""), timeout_seconds=float(get("timeout_seconds")),
        min_remaining_seconds=float(get("min_remaining_seconds")), total_seconds=float(get("total_seconds")),
        failures=int(get("failures")), open_seconds=float(get("open_seconds")), embed_timeout_seconds=float(get("embed_timeout_seconds")),
        backend=backend, api_model=str(get("api_model") or ""), api_timeout_seconds=float(get("api_timeout_seconds")))


@dataclass(frozen=True)
class Candidate:
    chunk: Any                 # PolicyChunk — score 는 후보를 뽑은 색인의 점수
    section: str               # 절 제목(프롬프트용)
    line: str                  # 고객용 문장(없으면 본문 앞 120자)


def build_user_prompt(query: str, candidates: list[Candidate]) -> str:
    """실험과 같은 모양 — `고객 질문: …` + 번호 붙인 `[절 제목] 고객용 문장`."""
    lines = "\n".join(f"{k + 1}. [{c.section}] {c.line}" for k, c in enumerate(candidates))
    return f"고객 질문: {query}\n\n후보 안내 문장:\n{lines}"


def parse_ranking(value: Any, count: int, limit: int) -> list[int]:
    """모델 답 `{"ranking":[…]}` → 후보 번호(0부터, 중복·범위 밖 버림, 최대 `limit`). 모양이 틀리면 `ValueError`(빈 목록은 올바른 답이다)."""
    ranking = value.get("ranking") if isinstance(value, dict) else None
    if not isinstance(ranking, list):
        raise ValueError("ranking 이 목록이 아니다")
    picks: list[int] = []
    for n in ranking:
        if isinstance(n, bool) or not isinstance(n, int):
            continue
        if 1 <= n <= count and n - 1 not in picks:
            picks.append(n - 1)
    return picks[:limit]


# ───────────────────────── 고객 문장 색인(실험의 색인 E) ─────────────────────────
class IndexUnavailable(RuntimeError):
    """고객 문장 색인을 못 쓴다 — 이유는 메시지 앞 낱말(`provider_not_ollama` · `index_cold` · `embed_failed` …)."""


class CustomerTextIndex:
    """「문서 제목 / 절 제목: 고객용 문장」의 벡터를 프로세스 안에 두고 질문과의 코사인으로 후보를 뽑는다. DB 는 읽기만 한다(행 목록)."""

    def __init__(self, *, sections: Callable[[], dict[str, dict[str, str]]], fetch_rows: Callable[[str, list[str]], list[tuple[str, int, str, str]]],
                 embed_query: Callable[[str], list[float]], embed_texts: Callable[[list[str]], list[list[float]]],
                 model_key: Callable[[], str], provider_ok: Callable[[], bool], batch: int = 16) -> None:
        self._sections, self._fetch_rows, self._embed_query = sections, fetch_rows, embed_query
        self._embed_texts, self._model_key, self._provider_ok, self._batch = embed_texts, model_key, provider_ok, batch
        self._vectors: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._warming = False

    @staticmethod
    def text_of(entry: dict[str, str]) -> str:
        return f"{entry['doc_title']} / {entry['section']}: {entry['line']}"

    def _key(self, text: str) -> str:
        return hashlib.sha1((self._model_key() + "\n" + text).encode("utf-8")).hexdigest()

    def _missing(self) -> list[str]:
        texts = [self.text_of(e) for e in self._sections().values()]
        with self._lock:
            return [t for t in dict.fromkeys(texts) if self._key(t) not in self._vectors]

    def ready(self) -> bool:
        return not self._missing()

    def warm(self) -> dict[str, Any]:
        """빠진 문장을 임베딩해 둔다(시간이 걸린다 — 요청 길이 아니라 예열·뒤 스레드에서 부른다). 실패는 예외."""
        import numpy as np

        missing = self._missing()
        started = time.monotonic()
        for k in range(0, len(missing), self._batch):
            part = missing[k:k + self._batch]
            vectors = self._embed_texts(part)
            if len(vectors) != len(part):
                raise IndexUnavailable(f"embed_failed: 문장 {len(part)}개에 벡터 {len(vectors)}개가 왔다")
            with self._lock:
                for text, vector in zip(part, vectors):
                    v = np.asarray(vector, dtype=np.float32)
                    self._vectors[self._key(text)] = v / (np.linalg.norm(v) or 1.0)
        return {"embedded": len(missing), "seconds": round(time.monotonic() - started, 2)}

    def warm_in_background(self) -> bool:
        """이미 돌고 있거나 다 만들어져 있으면 아무것도 안 한다. 시작했으면 True."""
        with self._lock:
            if self._warming:
                return False
            self._warming = True

        def run() -> None:
            try:
                logger.info("customer_text index warm: %s", self.warm())
            except Exception as exc:                                   # noqa: BLE001 — 이유를 남기고 끝낸다(다음 요청이 다시 시도한다)
                logger.warning("customer_text index warm failed: %s: %s", type(exc).__name__, str(exc)[:200])
            finally:
                with self._lock:
                    self._warming = False

        threading.Thread(target=run, name="policy-text-index-warm", daemon=True).start()
        return True

    def search(self, tenant_id: str, query: str, scopes: list[str], limit: int) -> list[Candidate]:
        import numpy as np
        from app.core.context import PolicyChunk

        if not self._provider_ok():
            raise IndexUnavailable("provider_not_ollama: 고객 문장 색인은 bge-m3(ollama 제공자)로만 만든다")
        if not self.ready():
            self.warm_in_background()
            raise IndexUnavailable("index_cold: 고객 문장 색인을 만드는 중이다")
        sections = self._sections()
        rows = self._fetch_rows(tenant_id, scopes)
        usable = [(r, sections[f"{r[0]}#c{r[1]}"]) for r in rows if f"{r[0]}#c{r[1]}" in sections]
        if not usable:
            return []
        try:
            q = np.asarray(self._embed_query(query), dtype=np.float32)
        except Exception as exc:                                       # noqa: BLE001 — 질문 임베딩 실패는 지금 색인의 몫(거기서도 같은 오류가 난다)
            raise IndexUnavailable(f"embed_failed: {type(exc).__name__}: {str(exc)[:120]}") from exc
        q = q / (np.linalg.norm(q) or 1.0)
        with self._lock:
            matrix = np.stack([self._vectors[self._key(self.text_of(entry))] for _, entry in usable])
        scores = matrix @ q
        out: list[Candidate] = []
        for i in np.argsort(-scores)[:limit]:
            (document_id, chunk_no, scope, content), entry = usable[int(i)]
            out.append(Candidate(PolicyChunk(document_id=document_id, chunk_no=int(chunk_no), content=content,
                                             score=float(scores[int(i)]), scope=scope), entry["section"], entry["line"]))
        return out


def _default_fetch_rows(tenant_id: str, scopes: list[str]) -> list[tuple[str, int, str, str]]:
    from app.infrastructure.db.session import get_connection

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT kc.content, kc.metadata_json FROM knowledge_chunks kc JOIN knowledge_documents kd USING(document_id) "
                    "WHERE kd.tenant_id = %s AND kd.scope = ANY(%s)", (tenant_id, scopes))
        return [(meta["document_id"], int(meta["chunk_no"]), meta["scope"], content) for content, meta in cur.fetchall()]


def _default_embed_texts(texts: list[str]) -> list[list[float]]:
    import urllib.request

    from app.core.settings import get_settings

    settings = get_settings()
    if not settings.ollama_base_url:
        raise IndexUnavailable("embed_failed: ACOP_OLLAMA_BASE_URL 이 비어 있다")
    request = urllib.request.Request(
        settings.ollama_base_url.rstrip("/") + "/api/embed",
        data=json.dumps({"model": settings.ollama_embedding_model, "input": texts}).encode(), headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=max(30.0, float(settings.ollama_timeout_seconds))) as response:
        payload = json.loads(response.read())
    if payload.get("error"):
        raise IndexUnavailable(f"embed_failed: {payload['error']}")
    return list(payload.get("embeddings") or [])


def _default_index() -> CustomerTextIndex:
    from app.core.settings import get_settings
    from app.domains.travel_ops.instances._shared.itinerary_team import customer_sections
    from app.infrastructure.rag import retriever

    return CustomerTextIndex(
        sections=customer_sections, fetch_rows=_default_fetch_rows, embed_query=retriever._embed_query, embed_texts=_default_embed_texts,
        model_key=lambda: get_settings().ollama_embedding_model, provider_ok=lambda: retriever._provider()[0] == "ollama")


# ───────────────────────── 재순위 + 검증 ─────────────────────────
class PolicyRerank:
    """`search_policy` 와 같은 겉모양(`__call__`)에 `search_detailed` 를 더한 객체. `question_reply` 만 `search_detailed` 를 부른다 —
    규정 질문이 아닌 곳(기능 안내 · 일정 생성기)은 `__call__` 로 지금과 똑같이 검색한다."""

    def __init__(self, *, base_search: Callable[..., list[Any]], settings_loader: Callable[[], RerankSettings],
                 index_factory: Callable[[], CustomerTextIndex] = _default_index,
                 sections: Callable[[], dict[str, dict[str, str]]] | None = None,
                 chat_factory: Callable[[RerankSettings, float], Any] | None = None,
                 prior_seconds: Callable[[], float] | None = None, app_settings: Callable[[], Any] | None = None,
                 budget: Callable[[Any], Callable[[], bool] | None] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._base, self._load, self._index_factory = base_search, settings_loader, index_factory
        self._app_settings = app_settings
        self._budget = budget
        self._sections, self._chat_factory, self._prior_seconds, self._clock = sections, chat_factory, prior_seconds, clock
        self._index: CustomerTextIndex | None = None
        self._shadow_slot = threading.Semaphore(1)

    # ── 지금과 똑같은 검색 ──
    def __call__(self, tenant_id: str, query: str, allowed_scopes: list[str], top_k: int | None = None) -> list[Any]:
        return self._base(tenant_id=tenant_id, query=query, allowed_scopes=allowed_scopes, top_k=top_k)

    def index(self) -> CustomerTextIndex:
        if self._index is None:
            self._index = self._index_factory()
        return self._index

    def warm(self) -> dict[str, Any]:
        """예열 길에서 부른다 — 스위치가 customer_text 를 쓰는 중이면 색인을 미리 만든다(안 쓰면 아무것도 안 한다)."""
        cfg = self._load()
        if cfg.mode == "off" or cfg.first_stage != "customer_text":
            return {"status": "skipped", "reason": "not_used"}
        return {"status": "started" if self.index().warm_in_background() else "running_or_ready"}

    # ── 질문 → (조각, 정보) ──
    def search_detailed(self, tenant_id: str, query: str, allowed_scopes: list[str], top_k: int = 3) -> tuple[list[Any], dict[str, Any] | None]:
        cfg = self._load()
        if cfg.mode == "off":
            return self._base(tenant_id=tenant_id, query=query, allowed_scopes=allowed_scopes, top_k=top_k), None
        if cfg.mode == "shadow":
            plain = self._base(tenant_id=tenant_id, query=query, allowed_scopes=allowed_scopes, top_k=top_k)
            self._shadow(cfg, tenant_id, query, allowed_scopes, plain)
            return plain, None
        return self._run(cfg, tenant_id, query, allowed_scopes, top_k)

    def _shadow(self, cfg: RerankSettings, tenant_id: str, query: str, scopes: list[str], plain: list[Any]) -> None:
        if not self._shadow_slot.acquire(blocking=False):                 # 모델 서버를 막지 않게 한 번에 하나만
            STATS["shadow_busy"] += 1
            return

        def run() -> None:
            try:
                chunks, info = self._run(cfg, tenant_id, query, scopes, cfg.max_picks)
                STATS["shadow_runs"] += 1
                first = lambda items: (items[0].document_id, items[0].chunk_no) if items else None      # noqa: E731
                differs = first(chunks) != first(plain)
                STATS["shadow_top1_diff"] += int(differs)
                logger.info("policy rerank shadow: status=%s top1_differs=%s picked=%s plain=%s", (info or {}).get("status"), differs,
                            [f"{c.document_id}#c{c.chunk_no}" for c in chunks], [f"{c.document_id}#c{c.chunk_no}" for c in plain])
            except Exception as exc:                                       # noqa: BLE001 — 그림자 길은 고객 답에 영향이 없다. 이유만 남긴다
                logger.warning("policy rerank shadow failed: %s: %s", type(exc).__name__, str(exc)[:200])
            finally:
                self._shadow_slot.release()

        threading.Thread(target=run, name="policy-rerank-shadow", daemon=True).start()

    def _run(self, cfg: RerankSettings, tenant_id: str, query: str, scopes: list[str], top_k: int) -> tuple[list[Any], dict[str, Any]]:
        started = self._clock()
        info: dict[str, Any] = {"mode": cfg.mode, "first_stage": cfg.first_stage, "first_stage_used": cfg.first_stage, "candidates": 0,
                                "picked": [], "status": "ok", "gate": cfg.min_score, "llm_seconds": None, "seconds": None}

        operating: list[Candidate] | None = None          # 첫 색인이 지금 색인이면 후보 앞 top_k 개가 곧 지금 방식의 결과다(검색을 다시 하지 않는다)

        def plain_result(reason: str, public: str | None = None) -> tuple[list[Any], dict[str, Any]]:
            """지금 방식(첫 색인 · 문턱 지금 값)으로 돌아간다 — 이유를 남긴다. 로그에는 자세한 이유, Case 근거(`info`)에는 짧은 이유만(접속 주소가 든 오류 문장을 안 싣는다)."""
            STATS["plain_fallback"] += 1
            kind = reason.split(":", 1)[0]
            logger.warning("policy rerank → plain: %s", reason[:200])
            if operating is not None:
                chunks = [c.chunk for c in operating[:top_k]]
            else:
                chunks = self._base(tenant_id=tenant_id, query=query, allowed_scopes=scopes, top_k=top_k)
            info.update(status=f"plain:{kind}", first_stage_used="operating", gate=None, reason=(public or reason)[:160],
                        seconds=round(self._clock() - started, 2))
            return chunks, info

        # 1) 후보
        try:
            candidates = self._candidates(cfg, tenant_id, query, scopes, info)
        except IndexUnavailable as exc:
            if str(exc).startswith("index_cold"):
                STATS["index_cold"] += 1
            return plain_result(str(exc))
        info["candidates"] = len(candidates)
        if cfg.first_stage == "operating":
            operating = candidates
        if not candidates:
            info.update(status="empty_candidates", picked=[], seconds=round(self._clock() - started, 2))
            return [], info
        # 2) 시간 예산 · 서킷
        prior = self._prior()
        remaining = cfg.total_seconds - prior - (self._clock() - started)
        if remaining < cfg.min_remaining_seconds:
            STATS["skipped"] += 1
            return plain_result(f"time_budget: 남은 {remaining:.1f}초 < {cfg.min_remaining_seconds:g}초(해석에 {prior:.1f}초 사용)")
        api = cfg.backend == "api"
        timeout = min(cfg.api_timeout_seconds if api else cfg.timeout_seconds, remaining)
        if api:
            timeout = max(0.5, int(timeout * 2) / 2)                          # 0.5초 단위로 내린다 — 유료 호출 클라이언트가 제한시간마다 하나씩 생기므로 가짓수를 줄인다
        from app.core.settings import get_settings
        from app.infrastructure import llm_failover

        settings = (self._app_settings or get_settings)()
        info["backend"] = cfg.backend
        if api:
            target = "openai"
            if self._chat_factory is None and not llm_failover.server_api_ready(settings):
                STATS["skipped"] += 1
                return plain_result("no_api_key: 서버용 OpenAI 키가 없다")
        else:
            target = (settings.ollama_base_url or "").strip()
            if self._chat_factory is None and not target:
                STATS["skipped"] += 1
                return plain_result("no_model_server: ACOP_OLLAMA_BASE_URL 이 비어 있다")
        breaker = llm_failover.breaker_for(f"rerank-{cfg.backend}@{target}", threshold=cfg.failures, open_seconds=cfg.open_seconds)
        if not breaker.allow():
            STATS["skipped"] += 1
            return plain_result("circuit_open: 재순위 모델 호출이 연속으로 실패해 잠시 건너뛴다")
        if api:
            gate = self._budget(settings) if self._budget is not None else llm_failover.budget_gate(settings)
            if gate is None:                                               # 유료 호출이라 상한을 셀 장치가 없으면 부르지 않는다(실패해도 안전한 쪽)
                breaker.release()
                STATS["skipped"] += 1
                return plain_result("budget_unavailable: 유료 호출 상한을 세는 장치가 없다")
            if not gate():
                breaker.release()
                STATS["skipped"] += 1
                return plain_result("budget_exhausted: 유료 호출 하루 · 한 달 상한을 다 썼다")
        # 3) 모델 호출
        STATS["calls"] += 1
        llm_started = self._clock()
        try:
            if self._chat_factory:
                chat = self._chat_factory(cfg, timeout)
            elif api:
                chat = self._api_chat(cfg, settings, timeout)
            else:
                chat = self._default_chat(cfg, settings, timeout)
            user = build_user_prompt(query, candidates)
            if api:
                from app.core.redaction import masked

                user = masked(user)                                        # 바깥으로 나가는 글은 한 번 더 가린다(전화 · 이메일 같은 것)
            picks = parse_ranking(chat.json(SYSTEM, user), len(candidates), min(cfg.max_picks, top_k))
        except Exception as exc:                                           # noqa: BLE001 — 시간 초과 · 연결 · 형식 모두 지금 방식으로(이유는 남긴다)
            breaker.failure()
            STATS["failed"] += 1
            info["llm_seconds"] = round(self._clock() - llm_started, 2)
            return plain_result(f"llm_failed: {type(exc).__name__}: {str(exc)[:100]}", public=f"llm_failed: {type(exc).__name__}")
        breaker.success()
        info["llm_seconds"] = round(self._clock() - llm_started, 2)
        chosen = [candidates[i].chunk for i in picks]
        info.update(picked=[f"{c.document_id}#c{c.chunk_no}" for c in chosen], seconds=round(self._clock() - started, 2))
        if chosen:
            STATS["ok"] += 1
        else:
            STATS["empty"] += 1
            info["status"] = "empty"                                       # 검증 단계 — 직접 답하는 줄이 없다고 모델이 답했다
        return chosen, info

    def _candidates(self, cfg: RerankSettings, tenant_id: str, query: str, scopes: list[str], info: dict[str, Any]) -> list[Candidate]:
        if cfg.first_stage == "customer_text":
            return self.index().search(tenant_id, query, scopes, cfg.candidates)
        chunks = self._base(tenant_id=tenant_id, query=query, allowed_scopes=scopes, top_k=cfg.candidates) or []
        sections = (self._sections or _shared_sections)()
        out: list[Candidate] = []
        for chunk in chunks:
            entry = sections.get(chunk.source_id)
            out.append(Candidate(chunk, entry["section"] if entry else "", entry["line"] if entry else chunk.content[:120]))
        return out

    def _prior(self) -> float:
        if self._prior_seconds is not None:
            return float(self._prior_seconds())
        from app.infrastructure import llm_failover

        path = llm_failover.current_path()
        return float((path or {}).get("seconds") or 0.0)

    @staticmethod
    def _api_chat(cfg: RerankSettings, settings: Any, timeout: float) -> Any:
        from app.infrastructure.llm_failover import server_api_chat

        model = (cfg.api_model or getattr(settings, "llm_failover_model", "") or getattr(settings, "llm_model", "")).strip()
        return server_api_chat(settings, model=model, timeout=timeout)

    @staticmethod
    def _default_chat(cfg: RerankSettings, settings: Any, timeout: float) -> Any:
        from app.infrastructure.ollama_chat import OllamaChat

        return OllamaChat(base_url=settings.ollama_base_url, model=cfg.model or settings.ollama_model, timeout=timeout,
                          keep_alive=str(getattr(settings, "ollama_keep_alive", "") or ""), num_ctx=int(getattr(settings, "ollama_num_ctx", 0) or 0))


def _shared_sections() -> dict[str, dict[str, str]]:
    from app.domains.travel_ops.instances._shared.itinerary_team import customer_sections

    return customer_sections()


def build_policy_search(base_search: Callable[..., list[Any]] | None = None) -> PolicyRerank:
    """조립 루트가 부른다 — 가드레일을 읽는 재순위 검색. 스위치가 `off` 면 `search_policy` 와 똑같이 움직인다."""
    from app.core.settings import get_guardrails
    from app.infrastructure.rag.retriever import search_policy

    return PolicyRerank(base_search=base_search or search_policy, settings_loader=lambda: load_settings(get_guardrails()))


__all__ = ["Candidate", "CustomerTextIndex", "IndexUnavailable", "PolicyRerank", "RerankSettings", "STATS", "SYSTEM", "build_policy_search",
           "build_user_prompt", "load_settings", "parse_ranking"]
