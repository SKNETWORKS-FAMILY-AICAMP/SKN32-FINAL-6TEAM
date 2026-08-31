# -*- coding: utf-8 -*-
"""취소·환불 한 건이 지나는 길. 한 파일로 만든다.

    python program/onboarding/build_trace_html.py

한 파일 안에 둘이 들어간다.

  1. 낱장 열두 장. 그림이 아니라 HTML 이다. 진행바를 따라 한 장씩 바뀌고
     오른쪽 칸에 지금까지 만들어진 것이 쌓인다. 단계마다 실제 코드와
     그 코드의 쉬운 풀이를 덮어 띄운다.
  2. 낱장으로 담을 수 없는 그림 일곱 장. base64 로 파일 안에 박는다.

★낱장을 PNG 로 붙이지 않는다. 그림으로 붙이면 글자를 긁을 수 없고 검색도 안 되고
  화면 크기에 맞지도 않는다. 같은 내용을 HTML 로 다시 그린다. 내용은 그림을 그리는
  `trace/steps.py` 에서 그대로 가져오므로 그림과 화면이 어긋날 수 없다.

★열두 낱장의 PNG 는 화면에 넣지 않는다. HTML 로 같은 것이 이미 있는데 그림까지
  넣으면 같은 내용이 두 벌이 되고 파일이 4MB 넘게 무거워진다. 그림 파일 자체는
  `trace/images/` 에 그대로 있고 영상이 그것을 쓴다.

★남는 그림은 파일 안에 넣는다. 링크하지 않는다. 한 장만 떼어 보내도 안 깨진다.
"""
import base64
import html
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sheet_data import BAR, SHEETS  # noqa: E402
from trace_data import FILES_NOTE, STEPS  # noqa: E402

SRC = os.path.join(HERE, "trace", "images")
OUT = os.path.join(HERE, "취소환불_케이스_추적_그림.html")

#: (파일 앞머리, 제목, 설명). 순서가 곧 화면 순서다.
FIGURES = [
    ("00_", "전체 지도", "담당 다섯 갈래에 열두 단계를 얹은 것입니다. 가로가 시간입니다."),
    ("01_구조", "큰 구조에서 이 케이스가 건드리는 것",
     "컴포넌트 9, 모듈 6, 인스턴스 6, Port 6 중 이 한 건이 실제로 지나는 것만 채웠습니다."),
    ("13_", "작은 구조에서 본 같은 흐름, 상태 12개",
     "단계 12개와 상태 12개는 다른 축입니다. 둘 다 열둘이라 헷갈리지만 겹치지 않습니다."),
    ("14_", "전달 문서가 바뀌어 가는 모양",
     "같은 문의 하나가 다섯 번 모습을 바꿉니다. 그리고 표로 내려앉습니다."),
    ("15_", "다른 길로 빠지는 경우",
     "위 열두 단계는 전부 통과한 길입니다. 실제로는 아홉 군데에서 갈립니다."),
    ("16_", "이 흐름이 실제로 만드는 것",
     "낱장의 JSON 은 HTTP 몸통이거나 메모리 위의 객체입니다. 새로 생기는 파일은 없고 전부 DB 행입니다."),
    ("17_", "그럼 파일은 어디서 생기나",
     "실제로 있는 파일 이름만 적었습니다. 읽는 것, Composer 가 쓰는 것, 평가가 만드는 것으로 나눴습니다."),
]

#: 낱장 열두 장의 PNG. HTML 로 같은 것을 그리므로 화면에 넣지 않는다.
#: 목록에 적어 두는 이유는, 표에 없는 그림이 있으면 빌드를 멈추기 때문이다.
SKIP = ("01_문", "02_", "03_", "04_", "05_", "06_", "07_", "08_", "09_",
        "10_", "11_", "12_")


#: trace_data 는 색을 이름으로, steps.py 는 16진수로 쓴다. 짝을 여기서 못 박는다.
HUE = {"red": "#b8442f", "blue": "#2f5bd8", "green": "#0d7a4d",
       "purple": "#6b3fa0", "grey": "#6b7488"}


def png_size(raw):
    """PNG 머리에서 가로세로를 읽는다. IHDR 은 늘 8바이트 뒤에 온다."""
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        raise SystemExit("PNG 가 아니다")
    return (int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big"))


def dump(value):
    """<script> 안에 넣어도 안전한 JSON.

    ★json.dumps 는 `<` 를 그대로 둔다. 실제 코드 조각이나 설명에 `</script>` 가
      한 번이라도 들어오면 브라우저가 거기서 스크립트를 끊어 파일이 통째로
      깨진다. 지금은 그런 글자가 없지만, 없다는 사실에 기대면 안 된다.
    """
    out = json.dumps(value, ensure_ascii=False)
    for cp in (0x3c, 0x3e, 0x2028, 0x2029):
        out = out.replace(chr(cp), "%su%04x" % (chr(92), cp))
    return out


def check(pack):
    """두 출처가 같은 12단계를 말하는지 대조한다.

    ★개수만 세면 안 된다. 실제로 4번 단계 제목이 한쪽은 "의도·이슈·감성",
      다른 쪽은 "의도와 이슈와 감성" 으로 갈라져 있었는데 개수 검사는
      그것을 그대로 통과시켰다. 번호와 제목과 색을 전부 맞춰 본다.
    """
    if len(pack) != len(SHEETS):
        raise SystemExit("낱장 %d 개인데 누적 패킷은 %d 개다" % (len(SHEETS), len(pack)))
    if len(BAR) != len(SHEETS):
        raise SystemExit("진행바 %d 칸인데 낱장은 %d 장이다" % (len(BAR), len(SHEETS)))
    bad = []
    if [s["n"] for s in SHEETS] != list(range(1, len(SHEETS) + 1)):
        bad.append("낱장 번호가 1..%d 가 아니다: %s"
                   % (len(SHEETS), [s["n"] for s in SHEETS]))
    for a, b in zip(SHEETS, pack):
        if a["n"] != b["n"]:
            bad.append("번호가 다르다: 낱장 %s, 누적 %s" % (a["n"], b["n"]))
        if a["head"] != b["title"]:
            bad.append("%d번 제목이 다르다\n    낱장  %s\n    누적  %s"
                       % (a["n"], a["head"], b["title"]))
        want = HUE.get(b["color"])
        if want is None:
            bad.append("%d번 색 이름을 모른다: %s" % (a["n"], b["color"]))
        elif want != a["color"]:
            bad.append("%d번 색이 다르다: 낱장 %s, 누적 %s(%s)"
                       % (a["n"], a["color"], b["color"], want))
    for i, (a, b) in enumerate(zip(SHEETS, BAR)):
        if a["color"] != b["color"]:
            bad.append("%d번 진행바 색이 낱장과 다르다: %s vs %s"
                       % (a["n"], b["color"], a["color"]))
    if bad:
        raise SystemExit("두 출처가 어긋났다. trace/steps.py 가 원본이다.\n  "
                         + "\n  ".join(bad))


def main():
    from page_parts import CSS, JS, PAGE

    if not os.path.isdir(SRC):
        raise SystemExit("그림 폴더가 없다: %s" % SRC)
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".png"))

    used, figures, links = set(), [], []
    for i, (prefix, head, desc) in enumerate(FIGURES, 1):
        match = [f for f in files if f.startswith(prefix)]
        if not match:
            raise SystemExit("그림을 못 찾았다: %s" % prefix)
        name = match[0]
        used.add(name)
        path = os.path.join(SRC, name)
        with open(path, "rb") as fh:
            raw = fh.read()
        b64 = base64.b64encode(raw).decode("ascii")
        w, h = png_size(raw)
        # ★width/height 를 적어야 그림이 뜨기 전에도 자리를 잡는다. 없으면
        #   아래 내용이 그림 개수만큼 덜컥거리며 밀린다. 일곱 장을 한꺼번에
        #   디코딩하면 메모리가 80MB 쯤 되므로 보일 때 읽게 미룬다.
        figures.append(
            '<figure id="s%d"><img alt="%s" width="%d" height="%d"'
            ' loading="lazy" decoding="async" src="data:image/png;base64,%s">'
            '<figcaption><b>%s</b><span>%s</span></figcaption></figure>'
            % (i, html.escape("%s. %s" % (head, desc)), w, h, b64,
               html.escape(head), html.escape(desc)))
        links.append('<a href="#s%d">%s</a>' % (i, html.escape(head[:18])))

    used |= {f for f in files if f.startswith(SKIP)}
    left = [f for f in files if f not in used]
    if left:
        # ★조용히 빠뜨리지 않는다. 그림을 늘렸는데 표에 안 적으면 여기서 걸린다.
        raise SystemExit("표에 없는 그림이 있다: %s" % ", ".join(left))

    pack = [{"n": s["n"], "title": s["title"], "owner": s["owner"],
             "color": s["color"],
             "add": [[k, nm, lines] for k, nm, lines in s["add"]],
             "state": list(s["state"]) if s.get("state") else None,
             "code": s["code"]}
            for s in STEPS]

    check(pack)

    js = (JS
          .replace("__BAR__", dump(BAR))
          .replace("__SHEETS__", dump(SHEETS))
          .replace("__PACK__", dump(pack))
          .replace("__NOTE__", dump(FILES_NOTE)))

    page = PAGE % {
        "css": CSS, "links": "".join(links),
        "figures": "\n".join(figures), "js": js,
    }
    # ★최종 경로에 바로 쓰지 않는다. 쓰다가 죽으면 반쪽짜리 HTML 이 남고,
    #   그것이 멀쩡한 파일인 줄 알고 전달된다.
    tmp = OUT + ".part"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    os.replace(tmp, OUT)
    print("만듦: %s" % OUT)
    print("  %.1f MB · 낱장 %d장(HTML) · 그림 %d장(PNG) · 코드 %d조각"
          % (os.path.getsize(OUT) / 1048576, len(SHEETS), len(FIGURES),
             sum(len(s["code"]) for s in STEPS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
