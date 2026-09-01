# -*- coding: utf-8 -*-
"""낱장 말고 나머지 판들을 HTML 로 그린다.

★그림(PNG)으로 붙이지 않는다. 글자를 긁을 수 없고 검색도 안 되고 화면 크기에
  맞지도 않기 때문이다. 낱장에 한 것과 같다.

★내용은 `figures.py` 하나에서 온다. 그리는 코드(`trace/`)도 같은 데서 읽으므로
  둘이 갈라질 수 없다.
"""
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import figures as F  # noqa: E402
from sheet_data import SHEETS  # noqa: E402

#: figures.py 는 색을 이름으로 둔다. 브라우저 쪽 값으로 옮긴다.
HUE = {"red": "var(--red)", "blue": "var(--blue)", "green": "var(--green)",
       "purple": "var(--purple)", "grey": "var(--grey)", "amber": "var(--amber)"}
#: 갈래를 고를 때는 실제 색 값으로 맞춰야 한다.
RAW = {"red": "#b8442f", "blue": "#2f5bd8", "green": "#0d7a4d",
       "purple": "#6b3fa0", "grey": "#6b7488"}

e = html.escape


def _plate(anchor, head, sub, body, foot=""):
    return ('<section class="plate" id="%s"><h3>%s</h3><p class="sub2">%s</p>%s%s</section>'
            % (anchor, e(head), e(sub), body,
               '<div class="foot2">%s</div>' % e(foot) if foot else ""))


def lane_map():
    """전체 지도. 어느 단계가 어느 갈래인지는 단계 색에서 뽑는다."""
    cells = []
    for label, color in F.LANES:
        cells.append('<div class="name" style="color:%s;border-color:%s">%s</div>'
                     % (HUE[color], HUE[color], e(label)))
        for s in SHEETS:
            if s["color"] == RAW[color]:
                cells.append('<div class="cell on" style="background:%s">'
                             '<b>%d</b><span>%s</span></div>'
                             % (HUE[color], s["n"], e(s["head"][:10])))
            else:
                cells.append('<div class="cell"></div>')
    return _plate("p-map", "전체 지도",
                  '고객이 "어제 주문한 거 취소하고 환불받고 싶어요" 를 보낸 순간부터 '
                  "답이 돌아갈 때까지의 열두 단계",
                  '<div class="lanes">%s</div>' % "".join(cells), F.LANES_FOOT)


def structure():
    cards = []
    for head, sub, color, items in F.STRUCTURE:
        rows = []
        for name, used, note in items:
            rows.append('<div class="it%s"><span class="dot" style="color:%s">%s</span>'
                        '<span class="nm2">%s</span><span class="no2" style="color:%s">%s</span>'
                        '</div>'
                        % ("" if used else " off", HUE[color] if used else "var(--faint)",
                           "&#9679;" if used else "&#9675;", e(name),
                           HUE[color] if used else "var(--faint)", e(note)))
        cards.append('<div class="card" style="border-color:%s"><h4 style="color:%s">%s</h4>'
                     '<p class="cs">%s</p>%s</div>'
                     % (HUE[color], HUE[color], e(head), e(sub), "".join(rows)))
    return _plate("p-struct", F.STRUCTURE_HEAD[0], F.STRUCTURE_HEAD[1],
                  '<div class="cards">%s</div>' % "".join(cards))


def lifecycle():
    def chips(items, color_of):
        return '<div class="states3">%s</div>' % "".join(
            '<div class="s3" style="color:%s;border-color:%s"><b>%s</b><span>%s</span></div>'
            % (color_of(x), color_of(x), e(x[0]), e(x[1])) for x in items)

    body = (
        '<div class="rowhead">이 환불 건이 실제로 지난 길</div>'
        + chips(F.LIFECYCLE_MAIN,
                lambda x: HUE["green"] if x[0] == "resolved" else HUE["blue"])
        + '<div class="rowhead">멈췄다가 조건이 갖춰지면 다시 이어서 도는 상태</div>'
        + chips(F.LIFECYCLE_WAIT, lambda _x: HUE["amber"])
        + '<div class="rowhead">끝나는 다른 방법</div>'
        + chips(F.LIFECYCLE_END, lambda x: HUE[x[2]])
        + '<div class="card" style="border-color:var(--line);margin-top:14px">'
          '<h4>%s</h4><p class="cs">%s</p></div>'
          % (e(F.LIFECYCLE_WHY[0]), e(F.LIFECYCLE_WHY[1])))
    return _plate("p-life", F.LIFECYCLE_HEAD[0], F.LIFECYCLE_HEAD[1], body)


def contracts():
    cols = []
    for name, color, at, fields, note in F.CONTRACTS:
        cols.append('<div class="d5" style="border-color:%s"><b style="color:%s">%s</b>'
                    '<span class="at">%d번 단계</span>%s%s</div>'
                    % (HUE[color], HUE[color], e(name), at,
                       "".join('<div class="f">%s</div>' % e(f) for f in fields),
                       '<div class="note2">%s</div>' % e(note) if note else ""))
    tables = "".join(
        '<div class="it"><span class="nm2"><b>%s</b></span>'
        '<span class="no2" style="color:var(--dim)">%s</span></div>' % (e(t), e(w))
        for t, w in F.CONTRACTS_TABLES)
    body = ('<div class="docs5">%s</div>'
            '<div class="card" style="border-color:var(--blue);margin-top:14px">'
            '<h4 style="color:var(--blue)">그리고 이것들이 표로 내려앉는다</h4>%s</div>'
            % ("".join(cols), tables))
    return _plate("p-contract", F.CONTRACTS_HEAD[0], F.CONTRACTS_HEAD[1], body)


def branches():
    rows = []
    for at, when, then, why, color in F.BRANCHES:
        rows.append('<tr><td class="at2" style="color:%s">%s</td><td>%s</td>'
                    '<td class="then" style="color:%s">%s</td><td class="why2">%s</td></tr>'
                    % (HUE[color], ("%d번" % at) if at else "언제든",
                       e(when), HUE[color], e(then), e(why)))
    body = ('<table class="br"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            % ("".join("<th>%s</th>" % e(c) for c in F.BRANCHES_COLS), "".join(rows)))
    return _plate("p-branch", F.BRANCHES_HEAD[0], F.BRANCHES_HEAD[1], body)


def artifacts():
    cards = []
    for name, sub, color, cols, note in F.ARTIFACTS:
        cards.append('<div class="card" style="border-color:%s">'
                     '<h4 style="color:%s">%s</h4><p class="cs">%s</p><pre>%s</pre>%s</div>'
                     % (HUE[color], HUE[color], e(name), e(sub), e("\n".join(cols)),
                        '<p class="cs" style="margin:9px 0 0">%s</p>' % e(note)
                        if note else ""))
    body = ('<div class="warn">%s</div><div class="cards">%s</div>'
            % (e(F.ARTIFACTS_BANNER), "".join(cards)))
    return _plate("p-rows", F.ARTIFACTS_HEAD[0], F.ARTIFACTS_HEAD[1], body,
                  F.ARTIFACTS_FOOT)


def filenames():
    cards = []
    for head, color, rows in F.FILENAMES:
        items = "".join(
            '<div class="it"><span class="nm2" style="font-family:Consolas,monospace">'
            '%s</span><span class="no2" style="color:var(--dim);white-space:normal;'
            'flex:1.2">%s</span></div>' % (e(n), e(w)) for n, w in rows)
        cards.append('<div class="card" style="border-color:%s;grid-column:1/-1">'
                     '<h4 style="color:%s">%s</h4>%s</div>'
                     % (HUE[color], HUE[color], e(head), items))
    body = ('<div class="cards">%s</div><div class="warn" style="margin:14px 0 0">%s</div>'
            % ("".join(cards), e(F.FILENAMES_FOOT)))
    return _plate("p-files", F.FILENAMES_HEAD[0], F.FILENAMES_HEAD[1], body)


def traceback_ways():
    """되짚는 세 방법. 되는 것과 안 되는 것을 나눠 적는다."""
    cards = []
    for n, head, color, works, rows in F.TRACEBACK:
        items = "".join(
            '<div class="it"><span class="nm2" style="font-family:Consolas,monospace;'
            'flex:0 0 42%%">%s</span>'
            '<span class="no2" style="color:var(--dim);white-space:normal;text-align:left;'
            'flex:1">%s</span></div>' % (e(a), e(b)) for a, b in rows)
        cards.append('<div class="card" style="border-color:%s;grid-column:1/-1">'
                     '<h4 style="color:%s">%d. %s</h4><p class="cs">%s</p>%s</div>'
                     % (HUE[color], HUE[color], n, e(head),
                        "지금 됩니다" if works else "지금은 안 됩니다", items))
    return _plate("p-trace", F.TRACEBACK_HEAD[0], F.TRACEBACK_HEAD[1],
                  '<div class="cards">%s</div>' % "".join(cards), F.TRACEBACK_FOOT)


def all_plates():
    """여덟 판을 순서대로. 그림 파일을 하나도 안 쓴다."""
    return "\n".join([lane_map(), structure(), lifecycle(), contracts(),
                      branches(), artifacts(), filenames(), traceback_ways()])
