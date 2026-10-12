# -*- coding: utf-8 -*-
"""../spec/*.md 의 흐름(YAML)을 ../그림/<id>_<이름>_v1.{svg,html,png} 로 그린다."""
import re
import sys
from pathlib import Path

from flowfig import best, export_png, fig_html
from split_specs import flow_of

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent / "spec"
OUT = HERE.parent / "그림"
BAD = re.compile(r"[^\u0000-ɏᄀ-ᇿ -⯿　-〿㄰-㆏가-힣＀-￯]")


def main(only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    items, report = [], []
    for md_path in sorted(SPEC.glob("*.md")):
        fid = md_path.stem
        if only and fid not in only:
            continue
        md = md_path.read_text(encoding="utf-8")
        head = md.splitlines()[0][3:].strip()
        name = head.split(" ", 1)[1]
        odd = sorted(set(BAD.findall(md)))
        spec = flow_of(md)
        fig = best(spec, f"wf-{fid.lower()}", f"{fid} {name}", f"{name} — 기능별 워크플로")
        stem = f"{fid}_{re.sub(r'[^0-9A-Za-z가-힣]+', '_', name).strip('_')[:24]}_v1"
        (OUT / f"{stem}.svg").write_text(fig.svg(), encoding="utf-8")
        (OUT / f"{stem}.html").write_text(fig_html(fig), encoding="utf-8")
        items.append((OUT / f"{stem}.html", OUT / f"{stem}.png"))
        report.append((fid, len(fig.errors), fig.errors[:4], odd, fig.rule_errors))
    export_png(items)
    for fid, n, errs, odd, rule in report:
        print(fid, "규칙", rule or "통과", "| 그림 검사", n, errs, "| 낯선 글자", odd or "없음")


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
