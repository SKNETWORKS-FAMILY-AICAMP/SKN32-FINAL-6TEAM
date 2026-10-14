"""Recount saved, error-free HF travel adapters. Never calls inference."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SOURCES = {}


def read(path):
    raw = path.read_bytes()
    SOURCES[path.relative_to(ROOT).as_posix()] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw.decode("utf-8-sig"))


def main():
    gold = read(HERE / "fixtures/gold_sets.json")
    specs = [
        ("Winnow-E4B", "previous", "winnow_e4b", RES / "_pull/distill_eval"),
        ("jevify-gemma4-e4b", "previous", "jevify_e4b", RES / "_pull/distill_eval"),
        ("Spark-S1-4B-v6 (independent Jev-inspired)", "previous", "spark_s1_4b", RES / "_pull/distill_eval"),
        ("Winnow-E4B", "oos B54", "winnow_e4b_oos", RES / "gpu_backlog_20261008/winnow_e4b_oos_training_1308"),
        ("Spark-S1-4B-v6 (independent Jev-inspired)", "oos B54", "spark_s1_4b_oos", RES / "gpu_backlog_20261008/B_completed_20261009_0121"),
    ]
    rows = []
    for name, recipe, tag, folder in specs:
        stats = {k: {"total": 0, "correct": 0, "false_pick": 0} for k in ["request", "no_request", "compound", "single_or_none"]}
        picks, correctness = {}, {}
        errors = saved = 0
        for suite in ["mix8", "mix9", "mix10", "mix11", "mix12"]:
            fixture = read(HERE / f"fixtures/{suite}.json")["sets"][suite]["qs"]
            result = read(folder / f"eval_{tag}_{suite}.json")[tag + "#lora"]
            assert len(result["picks"]) == len(fixture)
            errors += result["_errors"]
            # Older files expose only aggregate errors. These trained rows all
            # have zero errors; otherwise reject rather than credit a failed NONE.
            assert result["_errors"] == 0, "Cannot map aggregate errors to item IDs"
            for i, pick in enumerate(result["picks"]):
                want = set(gold[suite][str(i)])
                got = set() if pick is None else {pick}
                group = "compound" if len(want) > 1 else "request" if want else "no_request"
                correct = got == want
                groups = [group] + (["single_or_none"] if group != "compound" else [])
                for g in groups:
                    stats[g]["total"] += 1
                    stats[g]["correct"] += correct
                    stats[g]["false_pick"] += not want and bool(got)
                key = f"{suite}:{i}"
                picks[key] = pick
                correctness[key] = correct
                saved += 1
        assert saved == 835 and stats["single_or_none"]["total"] == 769
        rows.append(dict(model=name, recipe=recipe, our_training=True, saved=saved,
                         expected=835, errors=errors, stats=stats, exact_correct_by_id=correctness))
    from scipy.stats import binomtest
    pairs = []
    for a, b in [(0, 1), (3, 4), (0, 3), (2, 4)]:
        ca, cb = rows[a]["exact_correct_by_id"], rows[b]["exact_correct_by_id"]
        ao = sum(ca[k] and not cb[k] for k in ca)
        bo = sum(cb[k] and not ca[k] for k in ca)
        pairs.append(dict(a=a, b=b, a_only=ao, b_only=bo,
                          exact_p=binomtest(ao, ao+bo).pvalue if ao+bo else 1.0,
                          scope="Same 835 item IDs; compound exact scores are zero for these single-output runs"))
    out = RES / "jev_training_recount_20261009_v1"
    out.mkdir(exist_ok=False)
    payload = dict(observed_at=datetime.now().astimezone().isoformat(), rows=rows,
                   paired=pairs, source_sha256=SOURCES, final_ranking=False,
                   limitation="Only latest Winnow has full D/D2/D3/H/E; Jevify B54 smoke failed, not scored zero")
    (out / "counts.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    def rat(n, d):
        return f"{n}/{d} = {100*n/d:.2f}%"
    lines = ["# Jev 계열 및 독립 Jev 방식 모델의 여행 추가 학습 비교", "",
             "동일 기본835문항 중 단일 대상583·요청없음186을 합친769개를 비교했습니다. 복합66개는 따로 보존합니다. 모든 행은 우리 여행 자료로 추가 학습한 판이며 호출 오류0/835입니다. Spark는 TypeSafe 제휴 모델이 아닌 독립 Jev 방식 구현입니다.", "",
             "| 모델 | 학습판 | 정상 요청 정답↑ | 요청없음 오지목↓ | 단일·요청없음 합산↑ | 복합 완전선택↑ |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        s = r["stats"]
        lines.append("| " + " | ".join([r["model"], r["recipe"], rat(s["request"]["correct"],583), rat(s["no_request"]["false_pick"],186), rat(s["single_or_none"]["correct"],769), rat(s["compound"]["correct"],66)]) + " |")
    lines += ["", "과거 판에서 Winnow와 Jevify 합산은 동률입니다. 두 모델은 정상 요청과 요청없음에서 서로 다른 실수를 하므로 어느 하나가 전 범위 최고라고 단정하지 않습니다.",
              "B54 Jevify는 학습 가중치 파일 확보 실패로 스모크에서 멈췄습니다. 과거 학습 결과와 최신 실패를 같은 판으로 합치지 않습니다.",
              "단일 번호 출력 경로의 복합 완전선택0/66은 두 대상을 출력할 수 없는 계약 제한도 포함합니다. 복수 출력 실행의 결과와 별도로 봅니다.",
              "속도는 실행 경로·양자화가 다르고 Spark 공식 선택지 로짓 경로와 우리 JSON 생성 경로가 달라 여기서 우열을 매기지 않습니다.", "",
              "[문항별 판정·같은 문항 정확검정·원본 해시](counts.json)"]
    (out / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"output": str(out), "rows": [{k:v for k,v in r.items() if k != "exact_correct_by_id"} for r in rows], "paired": pairs}, ensure_ascii=False))


if __name__ == "__main__":
    main()
