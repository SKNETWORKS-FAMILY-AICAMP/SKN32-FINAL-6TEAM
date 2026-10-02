# -*- coding: utf-8 -*-
"""대체 식당 유사도 — 메뉴 문장 임베딩을 식당 데이터로 더 학습하고, 규칙 방식과 견준다.

왜 하는가.
    대체 장소의 「비슷한 곳」은 지금 조리 형태 태그(면·국물·고기 …)가 겹치는지로 고른다
    (027 cuisine_similarity). 태그가 없는 가게(원장의 약 20%)는 비교 자체가 안 되고,
    「참다랑어회」와 「초밥」처럼 태그가 달라도 가까운 집을 놓친다.
    메뉴 문장을 임베딩하면 태그 없이도 가깝고 먼 것을 잴 수 있다.

무엇을 학습하는가 — 정답 라벨 없이.
    「대체 가능한가」를 사람이 표시한 쌍이 아직 없다. 그래서 가게 하나의 두 모습을 짝으로 쓴다.
        보기 A  상호 + 대표메뉴(firstmenu)   가게가 스스로 내세운 것
        보기 B  취급메뉴(treatmenu)           실제로 파는 것
    같은 가게의 A 와 B 는 가깝게, 다른 가게와는 멀게(배치 안 대조 학습, InfoNCE).
    그러면 「이 대표메뉴를 내는 집은 이런 메뉴를 판다」는 식당 도메인의 감을 배운다.
    기반 모델은 intfloat/multilingual-e5-small (한국어 포함, CPU 에서 돈다).

어떻게 재는가.
    가게를 8:2 로 나눠 학습에 쓰지 않은 20% 로만 잰다.
      1  보기 맞추기   시험 가게의 A 로 B 를 찾는다. hit@1 · hit@5 · MRR
      2  분류 일치     이웃 3곳이 같은 대표 분류(한식·중식 …)인 비율. 미상·기타는 뺀다.
                       문장에 분류 낱말은 넣지 않는다 — 넣으면 답을 보고 푸는 것이다.
      3  태그 없는 가게  규칙은 이웃을 못 고르는 가게에서 임베딩이 고르는가
    세 방법을 같은 자리에서 잰다: 규칙(태그 자카드) · e5 그대로 · e5 학습.
    2 는 대리 지표다 — 분류도 메뉴에서 규칙으로 뽑았다. 진짜 답은 사람 판정이다(sheet).

    python -m ml.dining_similarity prepare        원장에서 가게 문장을 뽑는다
    python -m ml.dining_similarity train          학습 (CPU 몇 분)
    python -m ml.dining_similarity evaluate       세 방법을 잰다 → metrics.json
    python -m ml.dining_similarity sheet          사람 판정 시트를 만든다(방법 이름은 가린다)
    python -m ml.dining_similarity score-sheet    채운 시트로 방법별 적합률을 낸다

모델·중간 산출물은 저장소 밖 datasets/ml/dining_sim/ 에 쓴다(ml/__init__.py).
판정 시트와 지표(metrics.json · train_info.json 사본)는 data/dining/similarity/ 에 둔다.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ml import artifact_dir  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "dining"))
import core_db  # noqa: E402  ★`[2026-09-28 cs]` 기본은 코어 DB(`core_db.py`)

DSN = core_db.dsn()
BASE_MODEL = "intfloat/multilingual-e5-small"
SEED = 42
TEST_SHARE = 0.2
MAX_LEN = 96
EXCLUDE_CATEGORY = {"미상", "기타", None}


def out_dir() -> Path:
    return artifact_dir("dining_sim")


def sheet_dir() -> Path:
    """사람이 채우는 판정 시트는 저장소 안에 둔다 — 팀이 같이 채운다."""
    path = Path(__file__).resolve().parents[1] / "data" / "dining" / "similarity"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ──────────────────────────────────────────────────────────────
# 데이터
# ──────────────────────────────────────────────────────────────

def prepare() -> None:
    import psycopg
    with psycopg.connect(DSN, connect_timeout=5) as conn:
        rows = conn.execute("""
            SELECT p.place_uid::text, p.name_ko, p.category,
                   coalesce(sr.raw_json->>'firstmenu', ''), coalesce(sr.raw_json->>'treatmenu', ''),
                   dining.cuisine_tags(p.place_uid)
            FROM dining.dn_source_record sr JOIN dining.dn_place p USING (place_uid)
            WHERE sr.source_code = 'tourapi_kor_food'
              AND (nullif(sr.raw_json->>'firstmenu', '') IS NOT NULL
                   OR nullif(sr.raw_json->>'treatmenu', '') IS NOT NULL)
            ORDER BY p.place_uid""").fetchall()
    rng = random.Random(SEED)
    items = []
    for uid, name, cat, first, treat, tags in rows:
        items.append({"id": uid, "name": name, "category": cat, "first": first.strip(),
                      "treat": treat.strip(), "tags": list(tags or []),
                      "split": "test" if rng.random() < TEST_SHARE else "train"})
    path = out_dir() / "places.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    n_test = sum(it["split"] == "test" for it in items)
    print(f"가게 {len(items)}곳 (학습 {len(items) - n_test} · 시험 {n_test}) → {path}")


def load_places() -> list[dict]:
    path = out_dir() / "places.jsonl"
    if not path.exists():
        sys.exit("places.jsonl 이 없다 — 먼저 prepare")
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def view_a(p: dict) -> str:
    return f"{p['name']} · 대표메뉴 {p['first'] or '없음'}"


def view_b(p: dict) -> str:
    return f"메뉴 {p['treat'] or p['first']}"


def full_text(p: dict) -> str:
    """이웃 찾기에 쓰는 문장. 대표 분류 낱말은 넣지 않는다(분류 일치를 재므로)."""
    return f"{p['name']} · 대표메뉴 {p['first'] or '없음'} · 메뉴 {p['treat'] or '없음'}"


# ──────────────────────────────────────────────────────────────
# 임베딩
# ──────────────────────────────────────────────────────────────

def load_encoder(path: str):
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModel.from_pretrained(path)
    return tok, model


def encode(tok, model, texts: list[str], prefix: str = "query: ", batch: int = 64, grad: bool = False):
    """e5 의 평균 풀링 + 정규화. e5 는 앞에 query:/passage: 를 붙여 학습됐다."""
    import torch
    import torch.nn.functional as F
    outs = []
    ctx = torch.enable_grad() if grad else torch.no_grad()
    with ctx:
        for i in range(0, len(texts), batch):
            enc = tok([prefix + t for t in texts[i:i + batch]], padding=True, truncation=True,
                      max_length=MAX_LEN, return_tensors="pt")
            hidden = model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            outs.append(F.normalize(pooled, dim=-1))
    return torch.cat(outs)


# ──────────────────────────────────────────────────────────────
# 학습
# ──────────────────────────────────────────────────────────────

def train(epochs: int, batch: int, lr: float, temperature: float) -> None:
    import torch
    import torch.nn.functional as F
    torch.manual_seed(SEED)
    places = [p for p in load_places() if p["split"] == "train" and p["first"] and p["treat"]]
    tok, model = load_encoder(BASE_MODEL)
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    rng = random.Random(SEED)
    log = []
    started = time.time()
    for epoch in range(epochs):
        rng.shuffle(places)
        losses = []
        for i in range(0, len(places) - 1, batch):
            chunk = places[i:i + batch]
            if len(chunk) < 2:
                continue
            a = encode(tok, model, [view_a(p) for p in chunk], "query: ", grad=True)
            b = encode(tok, model, [view_b(p) for p in chunk], "query: ", grad=True)
            logits = a @ b.T / temperature
            target = torch.arange(len(chunk))
            loss = (F.cross_entropy(logits, target) + F.cross_entropy(logits.T, target)) / 2
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(loss.item())
        mean = sum(losses) / len(losses)
        log.append({"epoch": epoch + 1, "loss": round(mean, 4)})
        print(f"  epoch {epoch + 1}/{epochs}  loss {mean:.4f}  ({time.time() - started:.0f}초)")
    path = out_dir() / "model"
    model.save_pretrained(path)
    tok.save_pretrained(path)
    info = {"base": BASE_MODEL, "train_places": len(places), "epochs": epochs, "batch": batch,
            "lr": lr, "temperature": temperature, "seconds": round(time.time() - started),
            "loss": log}
    json.dump(info, open(out_dir() / "train_info.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"→ {path}")


# ──────────────────────────────────────────────────────────────
# 평가
# ──────────────────────────────────────────────────────────────

def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def rule_neighbors(places: list[dict], q: dict, k: int, rng: random.Random) -> list[dict]:
    """규칙 방식(027 과 같은 뜻): 태그 자카드가 높은 순. 태그가 없으면 고르지 못한다."""
    if not q["tags"]:
        return []
    scored = [(jaccard(q["tags"], p["tags"]), rng.random(), p) for p in places if p["id"] != q["id"]]
    scored = [s for s in scored if s[0] > 0]
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [s[2] for s in scored[:k]]


def embed_neighbors(emb, index: dict[str, int], places: list[dict], q: dict, k: int) -> list[dict]:
    sims = emb @ emb[index[q["id"]]]
    order = sims.argsort(descending=True).tolist()
    return [places[j] for j in order if places[j]["id"] != q["id"]][:k]


def evaluate(k: int = 3) -> dict:
    import torch
    places = load_places()
    test = [p for p in places if p["split"] == "test"]
    index = {p["id"]: i for i, p in enumerate(places)}
    methods = {"e5 그대로": BASE_MODEL}
    trained = out_dir() / "model"
    if trained.exists():
        methods["e5 학습"] = str(trained)

    result: dict = {"시험 가게": len(test), "이웃 후보": len(places), "k": k, "방법": {}}
    rng = random.Random(SEED)

    # 규칙
    agree, total, blind = 0, 0, 0
    for q in test:
        if q["category"] in EXCLUDE_CATEGORY:
            continue
        nb = rule_neighbors(places, q, k, rng)
        if not nb:
            blind += 1
            continue
        agree += sum(p["category"] == q["category"] for p in nb)
        total += len(nb)
    scored = [q for q in test if q["category"] not in EXCLUDE_CATEGORY]
    result["방법"]["규칙(태그)"] = {
        "분류 일치@3": round(agree / total, 3) if total else None,
        "이웃을 못 고른 가게": f"{blind}/{len(scored)}"}

    for label, path in methods.items():
        tok, model = load_encoder(path)
        model.eval()
        emb = encode(tok, model, [full_text(p) for p in places])
        agree = total = 0
        for q in scored:
            nb = embed_neighbors(emb, index, places, q, k)
            agree += sum(p["category"] == q["category"] for p in nb)
            total += len(nb)
        # 태그 없는 가게에서의 분류 일치 — 규칙이 못 하는 곳
        tagless = [q for q in scored if not q["tags"]]
        t_agree = sum(p["category"] == q["category"]
                      for q in tagless for p in embed_neighbors(emb, index, places, q, k))
        # 보기 맞추기 — 시험 가게끼리
        pair = [p for p in test if p["first"] and p["treat"]]
        a = encode(tok, model, [view_a(p) for p in pair])
        b = encode(tok, model, [view_b(p) for p in pair])
        ranks = (a @ b.T).argsort(dim=1, descending=True)
        pos = [(ranks[i] == i).nonzero().item() + 1 for i in range(len(pair))]
        result["방법"][label] = {
            "분류 일치@3": round(agree / total, 3),
            "이웃을 못 고른 가게": f"0/{len(scored)}",
            "태그 없는 가게 분류 일치@3": (round(t_agree / (len(tagless) * k), 3) if tagless else None),
            "보기 맞추기 hit@1": round(sum(r == 1 for r in pos) / len(pos), 3),
            "보기 맞추기 hit@5": round(sum(r <= 5 for r in pos) / len(pos), 3),
            "보기 맞추기 MRR": round(sum(1 / r for r in pos) / len(pos), 3)}
        del model
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
    result["태그 없는 시험 가게"] = sum(1 for q in scored if not q["tags"])
    path = out_dir() / "metrics.json"
    json.dump(result, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"→ {path}")
    return result


# ──────────────────────────────────────────────────────────────
# 사람 판정 시트
# ──────────────────────────────────────────────────────────────

def sheet(n: int, k: int = 3) -> None:
    """시험 가게 n 곳마다 규칙과 학습 모델의 이웃 k 곳을 섞어 적는다. 어느 방법인지는 가린다."""
    places = load_places()
    index = {p["id"]: i for i, p in enumerate(places)}
    rng = random.Random(SEED)
    test = [p for p in places if p["split"] == "test" and p["category"] not in EXCLUDE_CATEGORY]
    pick = rng.sample(test, min(n, len(test)))
    tok, model = load_encoder(str(out_dir() / "model"))
    model.eval()
    emb = encode(tok, model, [full_text(p) for p in places])
    rows, key = [], []
    for q in pick:
        cands: dict[str, set[str]] = {}
        for p in rule_neighbors(places, q, k, rng):
            cands.setdefault(p["id"], set()).add("rule")
        for p in embed_neighbors(emb, index, places, q, k):
            cands.setdefault(p["id"], set()).add("model")
        order = list(cands)
        rng.shuffle(order)
        for cid in order:
            c = places[index[cid]]
            row_id = f"{q['id'][:8]}-{cid[:8]}"
            rows.append({"번호": row_id, "원래 가게": q["name"], "원래 대표메뉴": q["first"],
                         "원래 메뉴": q["treat"], "후보 가게": c["name"], "후보 대표메뉴": c["first"],
                         "후보 메뉴": c["treat"], "[판정] 대체 가능 O/X": ""})
            key.append({"번호": row_id, "방법": "+".join(sorted(cands[cid]))})
    path = sheet_dir() / "판정시트.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json.dump(key, open(sheet_dir() / "판정시트_정답키.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"원래 가게 {len(pick)}곳 · 후보 {len(rows)}행 → {path}")


def score_sheet() -> None:
    rows = list(csv.DictReader(open(sheet_dir() / "판정시트.csv", encoding="utf-8-sig")))
    key = {k["번호"]: k["방법"] for k in json.load(open(sheet_dir() / "판정시트_정답키.json", encoding="utf-8"))}
    tally: dict[str, list[int]] = {"rule": [0, 0], "model": [0, 0]}
    for r in rows:
        mark = r["[판정] 대체 가능 O/X"].strip().upper()
        if mark not in ("O", "X"):
            continue
        for m in key[r["번호"]].split("+"):
            tally[m][1] += 1
            tally[m][0] += mark == "O"
    for m, (ok, n) in tally.items():
        name = {"rule": "규칙(태그)", "model": "e5 학습"}[m]
        print(f"{name}: 적합 {ok}/{n}" + (f" = {ok / n:.1%}" if n else " (판정 없음)"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="대체 식당 유사도")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    t = sub.add_parser("train")
    t.add_argument("--epochs", type=int, default=3)
    t.add_argument("--batch", type=int, default=32)
    t.add_argument("--lr", type=float, default=2e-5)
    t.add_argument("--temperature", type=float, default=0.05)
    sub.add_parser("evaluate")
    s = sub.add_parser("sheet")
    s.add_argument("--n", type=int, default=40)
    sub.add_parser("score-sheet")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.cmd == "prepare":
        prepare()
    elif args.cmd == "train":
        train(args.epochs, args.batch, args.lr, args.temperature)
    elif args.cmd == "evaluate":
        evaluate()
    elif args.cmd == "sheet":
        sheet(args.n)
    else:
        score_sheet()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
