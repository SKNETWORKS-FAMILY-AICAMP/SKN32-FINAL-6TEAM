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
from sheet_data import BAR, SHEETS  # noqa: E402

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

    ★칸을 붙이지 않는다. 원본 그림(`trace/make_trace_images.py::sheet_map`)은
      칸마다 따로 떼고 사이를 벌렸다. 한때 같은 갈래가 연달아 오면 한 덩어리로
      붙여 봤는데, 3·4·5·6 이 한 칸처럼 읽혀 몇 번 단계가 어디까지인지
      알 수 없었다. 갈래가 같다는 것은 색이 말해 주면 된다.

    ★칸 안에는 짧은 이름을 쓴다. 원본도 진행바와 같은 `신원` `중복` `분류` 였다.
      긴 제목을 넣었더니 좁은 화면에서 글자가 한 자씩 세로로 섰다.
      긴 제목은 덮어쓰기 설명으로만 남긴다.

    ★빈 칸은 상자가 아니라 가는 선이다. 상자로 그리면 안 지나는 자리가
      지나는 자리만큼 눈에 띈다.
    """
    rows = []
    for label, color in F.LANES:
        cells = ['<div class="name" style="color:%s;border-color:%s">%s</div>'
                 % (HUE[color], HUE[color], e(label))]
        for i, s in enumerate(SHEETS):
            if s["color"] != RAW[color]:
                cells.append('<div class="cell"><i></i></div>')
                continue
            cells.append('<div class="cell on" style="background:%s" title="%s">'
                         '<b>%d</b><span>%s</span></div>'
                         % (HUE[color], e(s["head"]), s["n"], e(BAR[i]["name"])))
        rows.append("".join(cells))
    return _plate("p-map", "전체 지도",
                  '고객이 "어제 주문한 거 취소하고 환불받고 싶어요" 를 보낸 순간부터 '
                  "답이 돌아갈 때까지의 열두 단계",
                  '<div class="scroll"><div class="lanes">%s</div></div>'
                  % "".join(rows), F.LANES_FOOT)


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
    """상태 열두 개를 상태 기계 그림으로 그린다.

    ★칩만 늘어놓으면 "이어진다" 와 "되돌아온다" 가 사라진다. 그게 이 장의
      요점이다. 계획서 19절에 mermaid 원본이 있어서 그 모양을 따라 그린다.

    ★그림 파일이 아니라 SVG 다. 글자를 긁을 수 있고 검색도 되고 화면 크기에
      맞는다. 낱장과 다른 판에 한 것과 같은 이유다.

    ★자리(좌표)는 여기 있고 내용은 figures.py 에 있다. 전이 이름은 계획서에서
      온 것이라 여기서 지어내면 안 된다.
    """
    W, H = 1000, 596
    o = []

    def box(x, y, w, h, cls, name, sub):
        o.append('<rect class="bx %s" x="%d" y="%d" width="%d" height="%d" rx="10"/>'
                 % (cls, x, y, w, h))
        o.append('<text class="nm %s" x="%d" y="%d">%s</text>'
                 % (cls, x + w // 2, y + (23 if sub else 34), e(name)))
        if sub:
            o.append('<text class="sb" x="%d" y="%d">%s</text>'
                     % (x + w // 2, y + 41, e(sub)))

    def line(cls, pts, arrow=True):
        d = " ".join(("M" if i == 0 else "L") + "%d %d" % p for i, p in enumerate(pts))
        o.append('<path class="ln %s" d="%s"%s/>'
                 % (cls, d, ' marker-end="url(#h-%s)"' % cls if arrow else ""))

    def tag(x, y, text, cls="ed", anchor="middle"):
        o.append('<text class="%s" x="%d" y="%d" text-anchor="%s">%s</text>'
                 % (cls, x, y, anchor, e(text)))

    # ── 주 흐름. 이 환불 건이 실제로 지난 길이다.
    BW, BH, BY = 128, 56, 76
    xs = [36, 220, 404, 588, 808]
    for i, (name, sub) in enumerate(F.LIFECYCLE_MAIN):
        box(xs[i], BY, BW, BH, "gr" if name == "resolved" else "bl", name, sub)
    for i, ed in enumerate(F.LIFECYCLE_MAIN_EDGE):
        x0, x1 = xs[i] + BW, xs[i + 1]
        line("bl", [(x0, BY + BH // 2), (x1 - 7, BY + BH // 2)])
        tag((x0 + x1) // 2, BY + BH // 2 - 9, ed)
    tag(xs[4] + BW // 2, BY + BH + 22, "이 환불 건은 이 길로만 갔다", "ok")

    # ── 대기 셋과 resuming. 원본에서 이 넷만 노란 바탕이었다.
    waits = F.LIFECYCLE_WAIT[:F.LIFECYCLE_WAIT_SPLIT]
    WX, WW, WH2 = 560, 196, 54
    wys = [228, 302, 376]
    for i, (name, sub) in enumerate(waits):
        box(WX, wys[i], WW, WH2, "am", name, sub)
    RX2, RY, RW2, RH = 280, 302, 180, 58
    rname, rsub = F.LIFECYCLE_WAIT[F.LIFECYCLE_WAIT_SPLIT]
    box(RX2, RY, RW2, RH, "am", rname, rsub)

    # ── running 에서 대기로 나가는 길. 오른쪽 세로줄 하나로 모은다.
    BUS, RUN = 904, xs[3]
    line("am", [(RUN + 112, BY + BH), (RUN + 112, 164), (BUS, 164),
                (BUS, wys[0] + 27), (WX + WW + 7, wys[0] + 27)])
    for i in (1, 2):
        line("am", [(BUS, 164), (BUS, wys[i] + 27), (WX + WW + 7, wys[i] + 27)])
    for i, ed in enumerate(F.LIFECYCLE_HOLD_EDGE):
        tag(BUS - 8, wys[i] + 20, ed, "ed", "end")

    # ── 대기에서 resuming 으로 돌아오는 길.
    back = F.LIFECYCLE_BACK_EDGE
    line("am", [(WX, wys[0] + 27), (500, wys[0] + 27), (500, 290),
                (RX2 + RW2 // 2, 290), (RX2 + RW2 // 2, RY - 7)])
    tag(WX - 8, wys[0] + 20, back[0], "ed", "end")
    line("am", [(WX, wys[1] + 27), (RX2 + RW2 + 7, wys[1] + 27)])
    tag(510, wys[1] - 6, back[1])
    line("am", [(WX, wys[2] + 27), (500, wys[2] + 27), (500, 372),
                (RX2 + RW2 // 2, 372), (RX2 + RW2 // 2, RY + RH + 7)])
    tag(WX - 8, wys[2] + 20, back[2], "ed", "end")

    # ── resuming 에서 running 으로. 멈춘 것이지 끝난 것이 아니다.
    line("am", [(RX2, RY + RH // 2), (236, RY + RH // 2), (236, 150),
                (RUN + 16, 150), (RUN + 16, BY + BH + 7)])
    for i, ln in enumerate(F.LIFECYCLE_RESUME_NOTE):
        tag(250, 214 + i * 17, ln, "no", "start")

    # ── 끝나는 다른 방법. 원본에서 회색 바탕 상자였다.
    o.append('<rect class="note" x="36" y="452" width="900" height="82" rx="11"/>')
    for i, ln in enumerate(F.LIFECYCLE_END_NOTE):
        tag(486, 484 + i * 23, ln, "nt")
    tag(36, 574, F.LIFECYCLE_SRC, "src", "start")

    heads = "".join(
        '<marker id="h-%s" class="%s" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0 0 L10 5 L0 10 z"/></marker>' % (c, c)
        for c in ("bl", "am"))

    svg = ('<svg class="sd" viewBox="0 0 %d %d" role="img" '
           'aria-label="%s"><defs>%s</defs>%s</svg>'
           % (W, H, e("Case 상태 전이 그림. " + F.LIFECYCLE_HEAD[1]),
              heads, "".join(o)))
    body = ('<div class="scroll">%s</div>'
            '<div class="card why2b"><h4>%s</h4><p class="cs">%s</p></div>'
            % (svg, e(F.LIFECYCLE_WHY[0]), e(F.LIFECYCLE_WHY[1])))
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
            '<div class="it line"><span class="nm2 mono">%s</span>'
            '<span class="no2 free">%s</span></div>' % (e(n), e(w)) for n, w in rows)
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
            '<div class="it line"><span class="nm2 mono narrow">%s</span>'
            '<span class="no2 free">%s</span></div>' % (e(a), e(b)) for a, b in rows)
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
