# -*- coding: utf-8 -*-
"""코덱스 결과를 바로 적용한다.

python run_vis.py style            # 기획서 문체 원고(plan_style.md) 검사 후 기획서 재빌드
python run_vis.py <plan|req|wbs|data|db>   # 시각화 스크립트 실행 후 문서에 삽입(해당되는 것만)
"""
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
FORMS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(FORMS))
SP = r"C:/Users/PLAYDA~1/AppData/Local/Temp/claude/C--Users-playdata2-Documents-final-workspace/1ef5bc3d-bf83-4e90-9137-41837cf34747/scratchpad"
CX = os.path.join(FORMS, "w2", "표와시각자료", "코덱스")
SUB = os.path.join(FORMS, "w2", "제출본")
PLAN = "[기획] 프로젝트 기획서_2차_여행.docx"
EMBED = {
    "data": [("3.2 데이터 양", "수집데이터_소스별수량_코덱스.png", "그림. 소스별 수집·필터링 수량")],
    "db": [("2.1 엔터티 목록", "DB_적용상태_코덱스.png", "그림. 영역별 테이블 적용 상태"),
           ("2.3 ERD", "DB_ERD_여행핵심_코덱스.png", "그림. 여행 핵심 테이블 ERD")],
}
DOC = {"data": "[데이터 수집 및 저장] 수집 데이터 보고서_2차_여행.docx",
       "db": "[데이터 수집 및 저장] 데이터베이스저장소 설계 문서_2차_여행.docx"}


def strip(t):
    t = t.strip()
    t = re.sub(r"^```[a-zA-Z]*\n", "", t)
    return re.sub(r"\n```\s*$", "", t)


def rebuild_plan(src):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PLAN_SRC=src)
    r = subprocess.run([sys.executable, "build_기획서_v3.py"], cwd=HERE, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    print("  빌드", r.returncode, (r.stdout + r.stderr).strip()[-200:])
    if r.returncode == 0:
        shutil.copy(os.path.join(FORMS, PLAN), os.path.join(SUB, PLAN))
        print("  w2 반영:", PLAN)
    return r.returncode == 0


def style():
    raw = open(os.path.join(SP, "plan_style.md"), encoding="utf-8").read()
    diag, _, body = raw.partition("=====원고=====")
    body = strip(body)
    body = body[body.find("## 프로젝트 주제"):] if "## 프로젝트 주제" in body else ""
    print(diag.replace("=====진단=====", "").strip()[:1500])
    cur = open(os.path.join(FORMS, "w2", "기획서", "기획서_실무본.md"), encoding="utf-8").read()
    nums = lambda s: re.findall(r"\d[\d,]*\.?\d*", s)
    need = ["49,000", "22,749", "14,249", "7,913", "12,633", "16,746", "7,574,800", "43,209", "20,460"]
    miss = [k for k in need if k in cur and k not in body]
    secs = len(re.findall(r"^## ", body, re.M))
    bad = sorted(set(re.findall(r"코덱스|클로드|Claude|Codex|\[실측|\[추정|\[미확보|확인 필요", body)))
    lost = sorted(set(nums(cur)) - set(nums(body)))
    print("원고 %d자(현재 %d자) | 절 %d | 빠진 핵심 숫자 %s | 금지어 %s | 사라진 숫자 %d개 %s"
          % (len(body), len(cur), secs, miss or 0, bad or 0, len(lost), lost[:12]))
    if secs != 7 or miss or bad or len(body) < 8000:
        print("  검사 실패 — 적용 안 함")
        return
    out = os.path.join(FORMS, "w2", "기획서", "기획서_실무본_문체.md")
    open(out, "w", encoding="utf-8").write(body)
    rebuild_plan(out)


def vis(key):
    src = os.path.join(SP, "vis_%s.py" % key)
    code = strip(open(src, encoding="utf-8").read())
    dst = os.path.join(CX, "make_vis_%s_코덱스.py" % key)
    open(dst, "w", encoding="utf-8").write(code)
    before = set(os.listdir(CX))
    r = subprocess.run([sys.executable, dst], cwd=ROOT, env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    made = sorted(set(os.listdir(CX)) - before) + [f for f in before if f.endswith(".png") and os.path.getmtime(os.path.join(CX, f)) > os.path.getmtime(dst)]
    print("  실행", r.returncode, "| 새 그림", [f for f in made if f.endswith(".png")], "|", (r.stderr or "").strip()[-200:])
    if key == "plan":
        cur = os.path.join(FORMS, "w2", "기획서", "기획서_실무본_문체.md")
        rebuild_plan(cur if os.path.exists(cur) else os.path.join(FORMS, "w2", "기획서", "기획서_실무본.md"))
    for anchor, png, cap in EMBED.get(key, []):
        p = os.path.join(CX, png)
        if os.path.exists(p):
            r2 = subprocess.run([sys.executable, "embed_fig.py", DOC[key], anchor, p, cap], cwd=HERE,
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            print("  ", (r2.stdout + r2.stderr).strip()[-150:])


if __name__ == "__main__":
    style() if sys.argv[1] == "style" else vis(sys.argv[1])
