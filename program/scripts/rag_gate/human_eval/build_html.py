# -*- coding: utf-8 -*-
"""사람 평가 시트를 **한 파일 HTML(v3)** 로 — 한 번에 한 문제씩, 근거 자료와 Claude 의견을 같이 보여 주고 「맞다 / 중간 / 틀리다 / 모름」 하나만 고른다. `[2026-10-06 사용자 지시]`

    python build_html.py            →  human_eval_sheet.html (같은 폴더)

재료(전부 같은 폴더 · 자매 폴더에 있다)
  human_eval_sheet.csv      35행(질문 · 시스템 답)           — build_sheet.py 가 만든다
  human_eval_key.json       행마다 층 · 기계 판정(어느 세트 · 가져온 규정 칸)
  claude_opinion.json       Claude 가 먼저 낸 의견(예상 판정 + 한 줄 이유) — 손으로 쓴 것이다. 사람 점수가 아니다
  ../fixtures/policy_chunks.json      규정 문서 칸(제목 · 고객 안내 문장)
  ../results/rag_live_correct.json    질문마다 유형(정답 있음 / 비슷함 / 규정 밖) · 정답 칸

★이 HTML 은 **근거 자료와 Claude 의견을 보여 준다** — 그래서 사람 판정은 Claude 와 독립이 아니다(보고 정한다). 두 사람이 따로 채워 서로 일치도를 볼 때는 둘 다 같은 조건이다.
★판정은 평가자의 브라우저(localStorage)에만 저장되고 서버로 안 보낸다. 내려받은 CSV 는 score_simple.py 가 읽는다.
"""
import csv
import json
import os
import re
import sys
from html import escape as html_escape

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")
FIX = os.path.join(HERE, "..", "fixtures")
sys.stdout.reconfigure(encoding="utf-8")


def load(*parts):
    return json.load(open(os.path.join(*parts), encoding="utf-8"))


rows = list(csv.DictReader(open(os.path.join(HERE, "human_eval_sheet.csv"), encoding="utf-8-sig")))
key = {k["id"]: k for k in load(HERE, "human_eval_key.json")}
opinion = load(HERE, "claude_opinion.json")
chunks = {c["source"]: c for c in load(FIX, "policy_chunks.json")}
correct = load(RES, "rag_live_correct.json")["correct"]
assert len(rows) == 35, "시트 모양이 다르다"
VERDICTS = ("맞다", "중간", "틀리다")


def question_info(set_name, q):
    """질문 하나의 유형 · 정답 칸을 rag_live_correct.json 에서 찾는다(세트 이름 + 질문 문장으로)."""
    hits = [r for r in correct[set_name] if r["q"] == q]
    assert len(hits) == 1, (set_name, q, len(hits))
    return hits[0]


def chunk_view(source):
    c = chunks[source]
    return {"where": f'{c["doc_title"]} / {c["section"]}', "text": c["line"]}


# ---------- 규정 행의 근거 자료 ----------
def policy_evidence(row_id, q, srcs, set_name):
    info = question_info(set_name, q)
    gold, partial, typ = info["gold"], info["partial"], info["type"]
    blocks = []
    if typ == "answerable":
        for s in gold:
            v = chunk_view(s)
            blocks.append({"label": "이 질문에 맞는 규정", **v})
        used = bool(set(srcs) & set(gold))
        if used:
            check, ok = "시스템 답에 위 규정이 들어 있어요.", True
        elif set(srcs) & set(partial):
            check, ok = "시스템 답에 위 규정은 없고, 일부만 맞는 다른 규정이 들어 있어요.", None
        else:
            check, ok = "시스템 답에 위 규정이 없어요 — 다른 규정을 붙였어요.", False
    elif typ == "near_miss":
        for s in partial:
            blocks.append({"label": "이 질문과 가장 가까운 규정(질문에 딱 맞지는 않아요)", **chunk_view(s)})
        if not partial:
            blocks.append({"label": "규정에 있는 것", "where": "", "text": "비슷한 주제의 규정만 있고, 이 질문이 묻는 정확한 값(오늘의 사실 · 금액 · 개수 같은 것)은 규정에 없어요."})
        used = bool(set(srcs) & set(partial)) if partial else None
        check = ("시스템 답에 위 규정이 들어 있어요." if used else "시스템 답에 위 규정이 없어요." if used is False else
                 (f"시스템이 비슷한 주제의 규정 {len(srcs)}개를 붙여 답했어요." if srcs else "시스템이 「찾지 못했다」고 답했어요."))
        ok = used
    else:  # uncovered · offtopic
        blocks.append({"label": "규정에 있는 것", "where": "", "text": "여행 규정 문서에 이 질문의 답이 없어요(질문을 만들 때 「규정 밖」으로 분류한 질문)."})
        ok = None
        check = (f"시스템이 규정 {len(srcs)}개를 붙여 답했어요 — 질문과 상관있는 규정인지 살펴보세요." if srcs
                 else "시스템이 「찾지 못했다」고 답했어요(지어내지 않았어요).")
    return {"blocks": blocks, "checks": [{"ok": ok, "t": check}], "type": typ}


# ---------- 번역 행의 근거 자료(원문과 번역을 기계로 대조한 사실) ----------
NUM = re.compile(r"\d[\d,.:]*\d|\d")
WON_AMOUNT = re.compile(r"\d[\d,.]*\s*(?:만\s*)?원")
WON_MARK = re.compile(r"원|\bwon\b|\bKRW\b|₩|ウォン|韩元|韓元|韩币|วอน|вон|وون", re.I)
OTHER_MONEY = re.compile(r"円|엔|\byen\b|JPY|¥|(?<![韩韓])元|人民币|RMB|CNY|NT\$|HK\$|\$|USD|€|EUR|baht|THB|บาท")


def numbers(text):
    return [n.replace(",", "") for n in NUM.findall(text)]


def significant(n):
    """시각(10:30) · 소수(4.6) · 두 자리 이상 숫자만 값 비교 대상으로 본다. 한 자리 숫자는 「1인 → 每人」 · 「두 곳 → 2か所」처럼 말과 숫자가 오가서 사람이 뜻을 봐야 한다."""
    return ":" in n or "." in n or len(n) >= 2


def translation_evidence(src, out):
    a, b = numbers(src), numbers(out)
    sa, sb = [n for n in a if significant(n)], [n for n in b if significant(n)]
    same = sorted(sa) == sorted(sb)
    checks = [{"ok": same,
               "t": f'시각 · 금액 · 큰 숫자 — 원문 {" · ".join(sa) or "(없음)"} / 번역 {" · ".join(sb) or "(없음)"} → ' + ("같아요." if same else "다르거나 빠졌어요.")}]
    ea = [n for n in a if not significant(n)]
    eb = [n for n in b if not significant(n)]
    if sorted(ea) != sorted(eb):
        checks.append({"ok": None, "t": f'한 자리 숫자 — 원문 {" · ".join(ea) or "(없음)"} / 번역 {" · ".join(eb) or "(없음)"} — 「1인 → 每人」 · 「두 곳 → 2か所」처럼 말과 숫자가 오간 걸 수 있어요. 뜻을 보고 판단하세요.'})
    if WON_AMOUNT.search(src):
        keeps = bool(WON_MARK.search(out))
        other = OTHER_MONEY.search(out)
        if other:
            checks.append({"ok": False, "t": f"금액 단위 — 원문 「원」 → 번역에 「{other.group(0)}」가 있어요. 단위가 바뀐 거예요."})
        else:
            checks.append({"ok": keeps, "t": "금액 단위 — 원문 「원」 → " + ("번역에도 원(won)이 남아 있어요." if keeps else "번역에 원 표기가 없어요.")})
    return {"blocks": [], "checks": checks, "type": "translation"}


data, claude_agree = [], {}
for r in rows:
    rid = r["id"]
    k = key[rid]
    op = opinion[rid]
    assert op["verdict"] in VERDICTS and op["why"], rid
    item = {"id": rid, "claude": op["verdict"], "why": op["why"], "a": r["시스템 답"], "q": r["고객 입력"]}
    if r["종류"] == "알림 번역":
        m = re.match(r"^\[원문 한국어 알림 → ([\w-]+)\] (.*)$", r["고객 입력"], re.S)
        assert m, rid
        item.update(kind="번역", lang=m.group(1), q=m.group(2), ev=translation_evidence(m.group(2), r["시스템 답"]))
    else:
        item.update(kind="규정", ev=policy_evidence(rid, r["고객 입력"], k["기계 판정"]["출처"], k["기계 판정"]["세트"]))
    data.append(item)
assert all(d["q"] and d["a"] for d in data)
html = open(os.path.join(HERE, "human_eval_template.html"), encoding="utf-8").read()
LANG = {"en": "영어", "ja": "일본어", "zh-CN": "중국어(간체)"}
tone = {"맞다": "ok", "중간": "mid", "틀리다": "bad"}


def static_rows():
    """★스크립트가 안 도는 곳(파일 미리보기 · 메일 · 일부 앱 안의 보기)에서도 내용이 보이게 35행을 글자로 적어 둔다. 스크립트가 돌면 숨고 한 문제씩 보는 화면이 대신 나온다."""
    out = ['<div class="nojs"><div class="banner"><b>이 화면은 누를 수 없는 미리보기입니다.</b> 판정을 고르려면 이 파일을 <b>크롬 · 엣지 · 사파리 같은 브라우저로 직접 여세요</b>'
           '(파일 더블클릭 또는 브라우저로 끌어다 놓기). 아래는 35개 내용이고, 인쇄해서 □ 에 표시해도 됩니다.</div>']
    for n, d in enumerate(data, start=1):
        is_tr = d["kind"] == "번역"
        label_q = f'원문(한국어) → {LANG.get(d["lang"], d["lang"])}' if is_tr else "고객이 한 말"
        label_a = "번역 결과" if is_tr else "시스템 답"
        ev = "".join(f'<div class="evi"><b>{html_escape(b["label"])}</b>' + (f'<small>{html_escape(b["where"])}</small>' if b["where"] else "")
                     + f'<div>{html_escape(b["text"])}</div></div>' for b in d["ev"]["blocks"])
        ev += "".join(f'<div class="chk {"y" if c["ok"] else "n" if c["ok"] is False else ""}">{html_escape(c["t"])}</div>' for c in d["ev"]["checks"])
        out.append(
            f'<div class="card"><div class="row"><span class="pill">{d["id"]} · {n}/35 · {"알림 번역" if is_tr else "규정 질문 답"}</span></div>'
            f'<div class="lab">{label_q}</div><div class="box">{html_escape(d["q"])}</div>'
            f'<div class="lab">{label_a}</div><div class="box">{html_escape(d["a"])}</div>'
            f'<div class="lab">확인 자료</div>{ev}'
            f'<div class="claude {tone[d["claude"]]}"><b>Claude 예상: {d["claude"]}</b> — {html_escape(d["why"])}</div>'
            f'<div class="pick">내 판정: □ 맞다 &nbsp; □ 중간 &nbsp; □ 틀리다 &nbsp; □ 모름</div></div>')
    out.append("</div>")
    return "\n".join(out)


# `</script>` 가 글 안에 있어도 깨지지 않게
payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
out = os.path.join(HERE, "human_eval_sheet.html")
open(out, "w", encoding="utf-8").write(html.replace("__DATA__", payload).replace("<!--STATIC-->", static_rows()))
dist = {v: sum(1 for d in data if d["claude"] == v) for v in VERDICTS}
print(f"만들었다 — {len(data)}행 · {os.path.getsize(out):,}바이트 · Claude 예상 분포 {dist} · {out}")
