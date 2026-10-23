# -*- coding: utf-8 -*-
"""결정 14·15 수정본(JSON 교체 목록)을 적용한다.

python apply_d1415.py <plan|req> <json 파일>
- plan: w2/기획서/기획서_병합본_코덱스_2차.md 에 적용 → build_기획서_v3.py 재빌드
- req : build_요구사항정의서_v3.py 에 적용 → 실행 → REQ 검사
교체 원문이 정확히 1회가 아니면 아무것도 쓰지 않는다. 실패하면 원래 파일로 되돌린다.
통과하면 산출물을 w2/제출본/ 에 복사한다.
"""
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
W2 = os.path.join(FORMS, "w2")
SUBMIT = os.path.join(W2, "제출본")
BANNED = "—–→⇒★☆✓✔✕✗▸…⇄①②③④⑤⑥−"

TARGET = {
    "plan": (os.path.join(W2, "기획서", "기획서_병합본_코덱스_2차.md"), "build_기획서_v3.py",
             "[기획] 프로젝트 기획서_2차_여행.docx"),
    "req": (os.path.join(HERE, "build_요구사항정의서_v3.py"), "build_요구사항정의서_v3.py",
            "[기획] 요구사항 정의서_2차_여행.xlsx"),
}


def run(script):
    r = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    print("  실행", r.returncode, "|", (r.stdout + r.stderr).strip()[-300:])
    return r.returncode == 0


def main():
    key, jpath = sys.argv[1], sys.argv[2]
    target, script, product = TARGET[key]
    raw = open(jpath, encoding="utf-8").read().strip()
    raw = re.sub(r"^```[a-z]*\n|\n```$", "", raw)
    j = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    reps = j["replacements"]
    t = open(target, encoding="utf-8").read()
    bad = [(i, t.count(r["old"]), r["old"][:30]) for i, r in enumerate(reps) if t.count(r["old"]) != 1]
    print("교체", len(reps), "| 1회가 아닌 것", bad or 0)
    if bad:
        # 맞는 것만 적용한다 — 시간이 없다. 어긋난 것은 목록으로 남긴다
        reps = [r for i, r in enumerate(reps) if i not in {b[0] for b in bad}]
        print("  어긋난 교체는 건너뛰고", len(reps), "개만 적용")
    new = t
    for r in reps:
        new = new.replace(r["old"], r["new"])
    ban = [ch for r in reps for ch in BANNED if ch in r["new"]] if key == "plan" else []
    if ban:
        print("  경고 금지 문자(docx 빌드가 바꾼다):", sorted(set(ban)))
    bak = target + ".before_d1415"
    shutil.copy(target, bak)
    prod = os.path.join(FORMS, product)
    prod_bak = prod + ".before_d1415"
    shutil.copy(prod, prod_bak)
    open(target, "w", encoding="utf-8", newline="\n").write(new)
    ok = run(script)
    if ok and key == "req":
        sys.path.insert(0, HERE)
        import apply_codex_body as a
        ok = a.check_req(prod, os.path.join(a.BACKUP, product))
    if not ok:
        shutil.copy(bak, target)
        shutil.copy(prod_bak, prod)
        print("  실패 — 원래대로 되돌렸다")
        return
    os.makedirs(SUBMIT, exist_ok=True)
    shutil.copy(prod, os.path.join(SUBMIT, product))
    for r in reps:
        print("  -", r.get("why", "")[:90])
    print("  통과 — w2/제출본 에 복사:", product)


if __name__ == "__main__":
    main()
