"""뜻이 가까운 코드 찾기(임베딩)와 풀어 쓴 설명(언어 모델). 둘 다 로컬 Ollama 를 쓴다.

어디에 쓰나
  · 임베딩 — 오답 고르기. 정답과 뜻이 가장 가까운 다른 함수를 보기로 넣으면
    이름을 외워서는 못 푼다. 코드 전체를 뜻 묶음으로 나눠 아직 안 나온 묶음에서
    문제를 뽑는 데도 쓴다.
  · 언어 모델 — 힌트 문장(이 함수가 하는 일)만 쓴다. 정답은 만들지 않는다.

값을 모를 때(결정 15): Ollama 가 꺼져 있으면 멈추지 않고 대체로 넘어간다.
  임베딩 → 단어 빈도 유사도(TF-IDF). 설명 → 코드의 설명 첫 줄에서 이름을 가린 것.
  어느 쪽을 썼는지는 `source` 로 늘 밝힌다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Sequence

import numpy as np

from .codeindex import Unit, cache_dir

OLLAMA = os.environ.get("ACOP_DOJO_OLLAMA", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("ACOP_DOJO_EMBED_MODEL", "bge-m3:latest")
LLM_MODEL = os.environ.get("ACOP_DOJO_LLM_MODEL", "qwen3.5:9b")
BATCH = 32


def _post(path: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def ollama_up(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=timeout) as resp:
            names = {m["name"] for m in json.load(resp).get("models", [])}
        return EMBED_MODEL in names
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return False


def _key(text: str, model: str) -> str:
    return hashlib.sha1(f"{model}\n{text}".encode("utf-8")).hexdigest()


class Vectors:
    """함수마다 벡터 하나. 정규화해 두어 내적이 곧 코사인 유사도다."""

    def __init__(self, units: Sequence[Unit], matrix: np.ndarray, source: str):
        self.units = list(units)
        self.matrix = matrix
        self.source = source
        self.pos = {u.uid: i for i, u in enumerate(self.units)}

    def nearest(self, uid: str, candidates: Sequence[Unit], k: int) -> list[Unit]:
        """uid 와 뜻이 가까운 순서로 candidates 에서 k 개. 자기 자신은 뺀다."""
        if uid not in self.pos:
            return list(candidates)[:k]
        me = self.matrix[self.pos[uid]]
        scored = [(float(self.matrix[self.pos[c.uid]] @ me), c) for c in candidates
                  if c.uid != uid and c.uid in self.pos]
        scored.sort(key=lambda t: (-t[0], t[1].uid))
        return [c for _, c in scored[:k]]

    def clusters(self, k: int, seed: int = 0) -> dict[str, int]:
        # 윈도우에서 KMeans 가 물리 코어 수를 세다 실패하고 경고를 쏟아내 문제 화면을 덮는다.
        # 논리 코어 수보다 작은 값을 주어야 세는 단계를 건너뛴다(같으면 그대로 센다).
        os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(max(1, (os.cpu_count() or 2) - 1)))
        import warnings

        from sklearn.cluster import KMeans

        k = max(1, min(k, len(self.units)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            labels = KMeans(n_clusters=k, n_init=4, random_state=seed).fit_predict(self.matrix)
        return {u.uid: int(labels[i]) for i, u in enumerate(self.units)}


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


def _ollama_vectors(units: Sequence[Unit]) -> np.ndarray:
    cache = cache_dir() / f"embed_{re.sub(r'[^a-z0-9]+', '_', EMBED_MODEL.lower())}.npz"
    stored: dict[str, np.ndarray] = {}
    if cache.exists():
        with np.load(cache) as data:
            stored = {k: data[k] for k in data.files}
    texts = [u.text_for_embedding() for u in units]
    keys = [_key(t, EMBED_MODEL) for t in texts]
    missing = [i for i, k in enumerate(keys) if k not in stored]
    for start in range(0, len(missing), BATCH):
        chunk = missing[start:start + BATCH]
        # 서버가 살아 있는데 멎은 경우 너무 오래 기다리지 않는다(첫 모델 적재는 수십 초 걸린다)
        out = _post("/api/embed", {"model": EMBED_MODEL, "input": [texts[i] for i in chunk]}, timeout=90)
        for i, vec in zip(chunk, out["embeddings"]):
            stored[keys[i]] = np.asarray(vec, dtype=np.float32)
    if missing:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, **stored)
    return np.stack([stored[k] for k in keys])


def _tfidf_vectors(units: Sequence[Unit]) -> np.ndarray:
    from sklearn.feature_extraction.text import TfidfVectorizer

    def words(u: Unit) -> str:
        ident = re.sub(r"([a-z])([A-Z])", r"\1 \2", u.source).replace("_", " ")
        return f"{u.path} {u.doc} {ident}"

    matrix = TfidfVectorizer(token_pattern=r"[A-Za-z가-힣]{2,}", max_features=20000,
                             sublinear_tf=True).fit_transform([words(u) for u in units])
    return matrix.toarray().astype(np.float32)


def vectors(units: Sequence[Unit], *, allow_ollama: bool = True) -> Vectors:
    if allow_ollama and ollama_up():
        try:
            return Vectors(units, _normalize(_ollama_vectors(units)), f"임베딩 {EMBED_MODEL}")
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            pass
    why = "Ollama 를 못 써서 대체" if allow_ollama else "직접 고른 대체"
    return Vectors(units, _normalize(_tfidf_vectors(units)), f"단어 빈도(TF-IDF) — {why}")


# ── 풀어 쓴 설명 ─────────────────────────────────────────────────────────
def _llm_cache() -> Path:
    return cache_dir() / f"describe_{re.sub(r'[^a-z0-9]+', '_', LLM_MODEL.lower())}.json"


def mask_name(text: str, unit: Unit) -> str:
    """설명에 이름이 새면 가린다. 이름과 이름 조각(4자 이상)을 모두 본다."""
    parts = {unit.name} | {p for p in unit.name.split("_") if len(p) >= 4}
    for part in sorted(parts, key=len, reverse=True):
        text = re.sub(re.escape(part), "□□", text, flags=re.IGNORECASE)
    return text


def describe(unit: Unit, *, timeout: float = 45.0) -> tuple[str, str]:
    """이 함수가 하는 일 한 문장. (문장, 출처). 모델이 안 되면 설명 첫 줄로 대신한다."""
    cache = _llm_cache()
    stored: dict[str, str] = {}
    if cache.exists():
        try:
            stored = json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stored = {}
    key = _key(unit.source, LLM_MODEL)
    if key in stored:
        return mask_name(stored[key], unit), f"언어 모델 {LLM_MODEL}"
    prompt = ("다음 파이썬 함수가 하는 일을 한국어 한 문장으로 설명하라. 함수 이름은 쓰지 마라. "
              "무엇을 받아 무엇을 확인하고 무엇을 돌려주거나 바꾸는지만 말하라.\n\n" + unit.source[:2500])
    try:
        out = _post("/api/generate", {"model": LLM_MODEL, "prompt": prompt, "stream": False,
                                      "think": False, "keep_alive": "15m",
                                      "options": {"num_predict": 120, "temperature": 0.2}},
                    timeout=timeout)
        sentence = out.get("response", "").strip().split("\n")[0]
        if sentence:
            stored[key] = sentence
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(stored, ensure_ascii=False, indent=0), encoding="utf-8")
            return mask_name(sentence, unit), f"언어 모델 {LLM_MODEL}"
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        pass
    fallback = unit.doc.split("\n")[0] if unit.doc else "설명 글이 없는 함수다. 본문의 반환값을 본다."
    return mask_name(fallback, unit), "코드의 설명 첫 줄 — 언어 모델을 못 써서 대체"
