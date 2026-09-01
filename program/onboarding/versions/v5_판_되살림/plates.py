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


def _cols(cards, split):
    """카드를 두 기둥으로 세운다.

    ★그냥 2열 격자에 흘리면 순서가 가로로 꺾인다. 원본 그림에서 왼쪽 기둥은
      위아래가 짝이었다. 컴포넌트 아래 모듈, 인스턴스 아래 Port 다. 가로로
      꺾이면 컴포넌트 옆에 모듈이 서고 그 짝이 사라진다.
    """
    return ('<div class="twocol"><div class="col2">%s</div>'
            '<div class="col2">%s</div></div>'
            % ("".join(cards[:split]), "".join(cards[split:])))


def _plate(anchor, head, sub, body, foot=""):
    return ('<section class="plate" id="%s"><h3>%s</h3><p class="sub2">%s</p>%s%s</section>'
            % (anchor, e(head), e(sub), body,
               '<div class="foot2">%s</div>' % e(foot) if foot else ""))


def lane_map():
    """전체 지도. 어느 단계가 어느 갈래인지는 단계 색에서 뽑는다.

    ★이어진 단계는 붙여 그린다. 1-2 처럼 같은 갈래가 연달아 오면 원래 그림에서
      한 덩어리로 보였다. 칸마다 따로 떼면 그 정보가 사라진다.

    ★빈 칸은 상자가 아니라 가는 선이다. 상자로 그리면 안 지나는 자리가
      지나는 자리만큼 눈에 띈다.
    """
    rows = []
    for label, color in F.LANES:
        mine = [s["color"] == RAW[color] for s in SHEETS]
        cells = ['<div class="name" style="color:%s;border-color:%s">%s</div>'
                 % (HUE[color], HUE[color], e(label))]
        for i, s in enumerate(SHEETS):
            if not mine[i]:
                cells.append('<div class="cell"><i></i></div>')
                continue
            # 앞뒤가 같은 갈래면 그쪽 모서리를 펴서 한 덩어리로 보이게 한다.
            edge = ("" if i > 0 and mine[i - 1] else " l")                  + ("" if i + 1 < len(mine) and mine[i + 1] else " r")
            cells.append('<div class="cell on%s" style="background:%s">'
                         '<b>%d</b><span>%s</span></div>'
                         % (edge, HUE[color], s["n"], e(s["head"])))
        rows.append("".join(cells))
    return _plate("p-map", "전체 지도",
                  '고객이 "어제 주문한 거 취소하고 환불받고 싶어요" 를 보낸 순간부터 '
                  "답이 돌아갈 때까지의 열두 단계",
                  '<div class="lanes">%s</div>' % "".join(rows), F.LANES_FOOT)


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
                  _cols(cards, F.STRUCTURE_SPLIT)
                  + '<div class="warn" style="margin:14px 0 0">%s</div>'
                    % e(F.STRUCTURE_FOOT))


def lifecycle():
    """상태 열두 개.

    ★원본 그림에는 화살표가 있었다. 주 흐름은 왼쪽에서 오른쪽으로 이어졌고,
      대기 세 상태에서 running 으로 되돌아가는 곡선이 있었다. 칩만 늘어놓으면
      "이어진다" 와 "되돌아온다" 가 사라진다. 그게 이 장의 요점이다.
    """
    def chip(x, color, cls=""):
        return ('<div class="s3%s" style="color:%s;border-color:%s">'
                '<b>%s</b><span>%s</span></div>'
                % (cls, color, color, e(x[0]), e(x[1])))

    chain = []
    for i, x in enumerate(F.LIFECYCLE_MAIN):
        if i:
            chain.append('<span class="ar">&#10142;</span>')
        done = x[0] == "resolved"
        # ★원본에서 resolved 만 상자가 넓었다. 끝나는 자리라는 표시다.
        chain.append(chip(x, HUE["green"] if done else HUE["blue"],
                          " wide" if done else ""))

    body = (
        '<div class="rowhead">이 환불 건이 실제로 지난 길</div>'
        '<div class="states3 flow">%s</div>' % "".join(chain)
        + '<div class="rowhead">멈췄다가 조건이 갖춰지면 다시 이어서 돈다</div>'
        + '<div class="loop"><div class="states3">%s</div>'
          '<div class="back"><span class="ar up">&#10142;</span>'
          '<span>넷 다 <b>running</b> 으로 되돌아간다. 끝난 것이 아니라 멈춘 것이다</span>'
          '</div></div>'
          % "".join(chip(x, HUE["amber"], " wait") for x in F.LIFECYCLE_WAIT)
        + '<div class="rowhead">끝나는 다른 방법 (이 건에서는 안 나왔다)</div>'
        + '<div class="states3">%s</div>'
          % "".join(chip(x, HUE[x[2]]) for x in F.LIFECYCLE_END)
        + '<div class="card why2b">'
          '<h4>%s</h4><p class="cs">%s</p></div>'
          % (e(F.LIFECYCLE_WHY[0]), e(F.LIFECYCLE_WHY[1])))
    return _plate("p-life", F.LIFECYCLE_HEAD[0], F.LIFECYCLE_HEAD[1], body)


def contracts():
    """전달 문서 다섯.

    ★원본은 화살표로 이어져 "같은 것이 모습을 바꾼다" 를 보여 줬다. 나란히
      늘어놓기만 하면 다섯 개의 서로 다른 문서로 읽힌다. 뜻이 반대가 된다.
    """
    cols = []
    for i, (name, color, at, fields, note) in enumerate(F.CONTRACTS):
        if i:
            cols.append('<span class="ar mid">&#10142;</span>')
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
            '<div class="downto"><span class="ar down">&#10142;</span>'
            '<span>그리고 이것들이 표로 내려앉는다</span></div>'
            '<div class="card" style="border-color:var(--blue)">%s'
            '<p class="cs" style="margin:10px 0 0">%s</p></div>'
            '<div class="warn soft"><b>%s</b>%s</div>'
            % ("".join(cols), tables, e(F.CONTRACTS_TABLES_NOTE),
               e(F.CONTRACTS_WHY[0]),
               "".join('<span>%s</span>' % e(x) for x in F.CONTRACTS_WHY[1])))
    return _plate("p-contract", F.CONTRACTS_HEAD[0], F.CONTRACTS_HEAD[1], body)


def branches():
    rows = []
    for at, when, then, why, color in F.BRANCHES:
        rows.append('<tr><td class="at2" style="color:%s">%s</td><td>%s</td>'
                    '<td class="then" style="color:%s">%s</td><td class="why2">%s</td></tr>'
                    % (HUE[color], ("%d번" % at) if at else "언제든",
                       e(when), HUE[color], e(then), e(why)))
    body = ('<div class="scroll"><table class="br"><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table></div>'
            % ("".join("<th>%s</th>" % e(c) for c in F.BRANCHES_COLS), "".join(rows)))
    body += '<div class="warn" style="margin:14px 0 0">%s</div>' % e(F.BRANCHES_FOOT)
    return _plate("p-branch", F.BRANCHES_HEAD[0], F.BRANCHES_HEAD[1], body)


def artifacts():
    cards = []
    for name, sub, color, cols, note in F.ARTIFACTS:
        cards.append('<div class="card" style="border-color:%s">'
                     '<h4 style="color:%s">%s</h4><p class="cs">%s</p><pre>%s</pre>%s</div>'
                     % (HUE[color], HUE[color], e(name), e(sub), e("\n".join(cols)),
                        '<p class="cs" style="margin:9px 0 0">%s</p>' % e(note)
                        if note else ""))
    body = ('<div class="warn"><b>%s</b></div>%s'
            % (e(F.ARTIFACTS_BANNER), _cols(cards, F.ARTIFACTS_SPLIT)))
    return _plate("p-rows", F.ARTIFACTS_HEAD[0], F.ARTIFACTS_HEAD[1], body,
                  F.ARTIFACTS_FOOT)


def filenames():
    cards = []
    for head, color, rows in F.FILENAMES:
        items = "".join(
            '<div class="it"><span class="nm2 mono">%s</span>'
            '<span class="no2 wrap">%s</span></div>' % (e(n), e(w)) for n, w in rows)
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
            '<div class="it"><span class="nm2 mono narrow">%s</span>'
            '<span class="no2 wrap">%s</span></div>' % (e(a), e(b)) for a, b in rows)
        cards.append('<div class="card" style="border-color:%s;grid-column:1/-1">'
                     '<h4 style="color:%s">%d. %s</h4><p class="cs">%s</p>%s</div>'
                     % (HUE[color], HUE[color], n, e(head),
                        "지금 됩니다" if works else "아직 안 됩니다. 제작 중입니다", items))
    return _plate("p-trace", F.TRACEBACK_HEAD[0], F.TRACEBACK_HEAD[1],
                  '<div class="cards">%s</div>' % "".join(cards), F.TRACEBACK_FOOT)


def all_plates():
    """여덟 판을 순서대로. 그림 파일을 하나도 안 쓴다."""
    return "\n".join([lane_map(), structure(), lifecycle(), contracts(),
                      branches(), artifacts(), filenames(), traceback_ways()])
