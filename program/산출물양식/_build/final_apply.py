# -*- coding: utf-8 -*-
"""코덱스 최종 점검 결과(JSON)를 걸러서 제출본에 적용한다.

python final_apply.py <plan|req|wbs|data|db> <json>
걸러 내는 것: 새 문장에 숫자가 달라진 교체, 금지 문자·대괄호 표시·도구 이름·「확인 필요」가 들어간 교체,
old 가 문서 어디에도 없는 교체. 남은 교체만 적용하고, 적용 전 파일은 _backup/2026-09-10_최종점검전/ 에 둔다.
"""
import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
SUB = os.path.join(FORMS, "w2", "제출본")
# 실행마다 다른 백업 폴더 — 앞 회차 백업(비교 기준)을 덮지 않는다
import time as _t
BK = os.path.join(FORMS, "_backup", "2026-09-10_적용전_" + _t.strftime("%H%M%S"))
NAMES = {
    "plan": "[기획] 프로젝트 기획서_2차_여행.docx",
    "req": "[기획] 요구사항 정의서_2차_여행.xlsx",
    "wbs": "[기획] WBS_2차_여행.xlsx",
    "data": "[데이터 수집 및 저장] 수집 데이터 보고서_2차_여행.docx",
    "db": "[데이터 수집 및 저장] 데이터베이스저장소 설계 문서_2차_여행.docx",
}
BAN = re.compile("[—–→⇒★☆✓✔✕✗▸…⇄①②③④⑤⑥−]|\\[(실측|외부|추정|미확보|결정|제안|미구현|구현)[^\\]]*\\]|확인 필요|코덱스|클로드|Claude|Codex|아스트라")
NUM = re.compile("\\d[\\d,.]*")


def load(p):
    raw = open(p, encoding="utf-8").read().strip()
    raw = re.sub("^```[a-z]*\\n|\\n```$", "", raw)
    try:
        return json.loads(raw[raw.find("{"):raw.rfind("}") + 1]).get("replacements", [])
    except Exception as e:
        print("  JSON 읽기 실패:", e)
        return []


def texts(path):
    if path.endswith(".docx"):
        from docx import Document
        d = Document(path)
        return d, [p for p in d.paragraphs] + [p for t in d.tables for r in t.rows for c in r.cells for p in c.paragraphs]
    import openpyxl
    wb = openpyxl.load_workbook(path)
    return wb, [c for row in wb.worksheets[0].iter_rows() for c in row if isinstance(c.value, str)]


def main():
    key, jp = sys.argv[1], sys.argv[2]
    # 셋째 인자: 새로 들어와도 되는 숫자 목록(쉼표) — 결정 16 의 18·14·21 처럼 결정이 정한 숫자만
    allow = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else set()
    name = NAMES[key]
    path = os.path.join(SUB, name)
    reps = load(jp)
    doc, items = texts(path)
    alltext = "\n".join((x.text if hasattr(x, "text") else x.value) for x in items)
    ok, bad = [], []
    for r in reps:
        o, n = r.get("old", ""), r.get("new", "")
        why = ""
        if not o or o not in alltext:
            why = "원문 없음"
        elif sorted(x for x in NUM.findall(o) if x not in allow) != sorted(x for x in NUM.findall(n) if x not in allow):
            why = "숫자 변경"
        elif BAN.search(n) and not BAN.search(o):
            why = "금지 표현"
        (bad if why else ok).append((r, why))
    os.makedirs(BK, exist_ok=True)
    shutil.copy(path, os.path.join(BK, name))
    n_hit = 0
    seen = set()
    for x in items:
        if id(x) in seen:
            continue
        seen.add(id(x))
        t0 = x.text if hasattr(x, "text") else x.value
        t = t0
        for r, _ in ok:
            t = t.replace(r["old"], r["new"])
        if t != t0:
            n_hit += 1
            if hasattr(x, "runs"):
                if x.runs:
                    x.runs[0].text = t
                    for rr in x.runs[1:]:
                        rr.text = ""
            else:
                x.value = t
    doc.save(path)
    shutil.copy(path, os.path.join(FORMS, name))
    print("[%s] 제안 %d | 적용 %d (바뀐 칸 %d) | 거름 %d" % (key, len(reps), len(ok), n_hit, len(bad)))
    for r, why in bad:
        print("   거름(%s): %s" % (why, r.get("old", "")[:50]))
    for r, _ in ok[:40]:
        print("   - %s" % r.get("why", "")[:70])


if __name__ == "__main__":
    main()
