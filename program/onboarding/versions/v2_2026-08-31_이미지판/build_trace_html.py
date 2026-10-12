# -*- coding: utf-8 -*-
"""취소·환불 한 건이 지나는 길. 한 파일로 만든다.

    python program/onboarding/build_trace_html.py

한 파일 안에 둘이 들어간다.

  1. 시뮬레이터. 1번부터 12번까지 진행하면 오른쪽에 값이 쌓인다.
     단계마다 실제 코드와 그 코드의 쉬운 풀이를 오버레이로 본다.
  2. 그림 열아홉 장. base64 로 파일 안에 박는다.

★따로 만들지 않는다. 처음에 시뮬레이터를 별도 파일로 만들었는데, 같은 내용을
  두 파일이 나눠 가지면 한쪽만 고쳐진다. 한 장만 열어도 다 보이는 것이 낫다.

★그림을 링크하지 않고 파일 안에 넣는다. 한 장만 떼어 보내도 안 깨진다.
  대신 5MB 쯤 된다.
"""
import base64
import html
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from trace_data import FILES_NOTE, STEPS  # noqa: E402

SRC = os.path.join(HERE, "trace", "images")
OUT = os.path.join(HERE, "취소환불_케이스_추적_그림.html")

#: (파일 앞머리, 제목, 설명). 순서가 곧 화면 순서다.
SHEETS = [
    ("00_", "전체 지도", "담당 다섯 갈래에 열두 단계를 얹은 것입니다. 가로가 시간입니다."),
    ("01_구조", "큰 구조에서 이 케이스가 건드리는 것",
     "컴포넌트 9, 모듈 6, 인스턴스 6, Port 6 중 이 한 건이 실제로 지나는 것만 채웠습니다."),
    ("01_문", "1. 문 앞에서 신원 확인",
     "API 키를 확인해 Principal 을 만듭니다. 여기서 붙은 tenant_id 가 이후 모든 조회 조건에 붙습니다."),
    ("02_", "2. 같은 요청이 아까 왔었나",
     "재료 넷으로 지문을 만들어 이미 처리했는지 봅니다. 취소 버튼을 두 번 눌러도 Case 는 하나입니다."),
    ("03_", "3. Case 를 만들고 첫 이벤트를 남긴다",
     "행과 이벤트가 한 트랜잭션입니다. new 는 행을 만든 찰나에만 있고 곧 classifying 이 됩니다."),
    ("04_", "4. 의도와 이슈와 감성을 한 번에 분류",
     '"취소" 라고 썼지만 환불을 원하는 문의라 intent 가 return 입니다. 이 한 단어가 팀을 정합니다.'),
    ("05_", "5. 어느 팀 일인지 찾는다",
     "여섯 팀의 자기소개만 보고 고릅니다. 정확히 하나가 아니면 사람에게 넘깁니다."),
    ("06_", "6. 그 팀의 무슨 기능을 쓸지 고른다",
     "intent 로 시작하는 첫 capability 에서 멈춥니다. 목록 순서가 곧 우선순위입니다."),
    ("07_", "7. 근거를 모아 예산 안으로 자른다",
     "12,000 토큰을 넘으면 정해진 순서로 뺍니다. 뺐으면 뺐다고 적습니다."),
    ("08_", "8. Team 이 판단한다",
     "검사를 순서대로 합니다. 환불이 맞다고 판단해도 실행하지 않고 제안만 돌려줍니다."),
    ("09_", "9. 답변 문장을 만들고 톤을 검토한다",
     "지금 이 단계는 꺼져 있습니다. 그래서 고객이 받는 문장은 팀이 코드에 적어 둔 고정 문구입니다."),
    ("10_", "10. 결과를 상태로 반영한다",
     "completed 이벤트를 남기고 종결합니다. 답은 나갔는데 기록이 없는 상황이 안 생깁니다."),
    ("11_", "11. 고객이 답을 받는다",
     "답변에 근거가 같이 나갑니다. 왜 그렇게 판단했는지 되짚을 수 있어야 하기 때문입니다."),
    ("12_", "12. 기록이 남는다",
     "다섯 표에 흔적이 남습니다. 지금 상태는 이벤트를 순서대로 적용한 결과일 뿐입니다."),
    ("13_", "작은 구조에서 본 같은 흐름, 상태 12개",
     "단계 12개와 상태 12개는 다른 축입니다. 둘 다 열둘이라 헷갈리지만 겹치지 않습니다."),
    ("14_", "전달 문서가 바뀌어 가는 모양",
     "같은 문의 하나가 다섯 번 모습을 바꿉니다. 그리고 표로 내려앉습니다."),
    ("15_", "다른 길로 빠지는 경우",
     "앞의 열두 장은 전부 통과한 길입니다. 실제로는 아홉 군데에서 갈립니다."),
    ("16_", "이 흐름이 실제로 만드는 것",
     "앞 장들의 JSON 은 HTTP 몸통이거나 메모리 위의 객체입니다. 새로 생기는 파일은 없고 전부 DB 행입니다."),
    ("17_", "그럼 파일은 어디서 생기나",
     "실제로 있는 파일 이름만 적었습니다. 읽는 것, Composer 가 쓰는 것, 평가가 만드는 것으로 나눴습니다."),
]


def main():
    from page_parts import CSS, JS, PAGE

    if not os.path.isdir(SRC):
        raise SystemExit("그림 폴더가 없다: %s" % SRC)
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".png"))

    used, figures, links = set(), [], []
    for i, (prefix, head, desc) in enumerate(SHEETS, 1):
        match = [f for f in files if f.startswith(prefix)]
        if not match:
            raise SystemExit("그림을 못 찾았다: %s" % prefix)
        name = match[0]
        used.add(name)
        with open(os.path.join(SRC, name), "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        figures.append(
            '<figure id="s%d"><img alt="%s" src="data:image/png;base64,%s">'
            '<figcaption><b>%s</b><span>%s</span></figcaption></figure>'
            % (i, html.escape(head), b64, html.escape(head), html.escape(desc)))
        links.append('<a href="#s%d">%s</a>' % (i, html.escape(head.split(".")[0][:14])))

    left = [f for f in files if f not in used]
    if left:
        # ★조용히 빠뜨리지 않는다. 그림을 늘렸는데 표에 안 적으면 여기서 걸린다.
        raise SystemExit("표에 없는 그림이 있다: %s" % ", ".join(left))

    data = [{"n": s["n"], "title": s["title"], "owner": s["owner"], "why": s["why"],
             "add": [[k, nm, lines] for k, nm, lines in s["add"]],
             "state": list(s["state"]) if s.get("state") else None,
             "code": s["code"]}
            for s in STEPS]

    stations = "".join(
        '<button class="st %s" onclick="go(%d)"><div class="n">%d</div>'
        '<div class="t">%s</div><div class="o">%s</div></button>'
        % (s["color"], i, s["n"], html.escape(s["title"]),
           html.escape(s["owner"].split(" · ")[0]))
        for i, s in enumerate(STEPS))

    note = "".join("<div><b>%s</b> %s</div>" % (h, b) for h, b in FILES_NOTE)

    page = PAGE % {
        "css": CSS, "stations": stations, "files": note,
        "links": "".join(links), "figures": "\n".join(figures),
        "js": JS.replace("__DATA__", json.dumps(data, ensure_ascii=False)),
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("만듦: %s" % OUT)
    print("  %.1f MB · 그림 %d장 · 단계 %d개 · 코드 %d조각"
          % (os.path.getsize(OUT) / 1048576, len(SHEETS), len(STEPS),
             sum(len(s["code"]) for s in STEPS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
