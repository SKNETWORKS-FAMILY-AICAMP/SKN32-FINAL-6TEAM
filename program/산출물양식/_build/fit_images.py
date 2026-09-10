# -*- coding: utf-8 -*-
"""docx 본문 그림이 페이지 아래로 잘리지 않게 맞춘다.
사용 가능한 높이(페이지 높이 - 위아래 여백)의 80% 를 넘는 그림은 비율을 유지한 채 줄인다(캡션 자리 확보)."""
import sys
from docx import Document


def fit(path, ratio=0.80):
    d = Document(path)
    # 양식의 여백 값이 소수(예: 992.12 twip)라 python-docx 가 못 읽는다 — XML 속성을 직접 실수로 읽는다
    from docx.oxml.ns import qn
    sp = d.sections[0]._sectPr
    pg, mar = sp.find(qn("w:pgSz")), sp.find(qn("w:pgMar"))
    tw = lambda el, k, dft: float(el.get(qn("w:" + k), dft)) * 635   # twip -> EMU
    max_h = int((tw(pg, "h", 16838) - tw(mar, "top", 1440) - tw(mar, "bottom", 1440)) * ratio)
    max_w = int(tw(pg, "w", 11906) - tw(mar, "left", 1440) - tw(mar, "right", 1440))
    n = 0
    for sh in d.inline_shapes:
        w, h = sh.width, sh.height
        k = min(1.0, max_h / h if h else 1, max_w / w if w else 1)
        if k < 0.999:
            sh.width, sh.height = int(w * k), int(h * k)
            n += 1
    d.save(path)
    return n, len(d.inline_shapes)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        n, total = fit(p)
        print("  줄임 %d / 그림 %d : %s" % (n, total, p.split("/")[-1][:40]))
