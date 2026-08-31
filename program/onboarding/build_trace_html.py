# -*- coding: utf-8 -*-
"""그림 17장을 base64 로 박아 넣은 HTML 한 장을 만든다.

    python program/onboarding/build_trace_html.py

★그림을 파일로 링크하지 않고 파일 안에 넣는다. 한 장만 떼어 메일이나 메신저로
  보내도 그림이 깨지지 않는다. 대신 파일이 4MB 쯤 된다.

★캡션은 여기 표에 있다. 그림 파일 이름에서 뽑지 않는다. 이름은 정렬용이라
  사람이 읽는 말이 아니다.
"""
import base64
import html
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "trace", "images")
OUT = os.path.join(HERE, "취소환불_케이스_추적_그림.html")

#: (파일 앞머리, 제목, 설명). 순서가 곧 화면 순서다.
SHEETS = [
    ("00_", "전체 지도", "담당 다섯 갈래에 열두 단계를 얹은 것이다. 가로가 시간이다."),
    ("01_구조", "큰 구조에서 이 케이스가 건드리는 것",
     "컴포넌트 9, 모듈 6, 인스턴스 6, Port 6 중 이 한 건이 실제로 지나는 것만 채웠다."),
    ("01_문", "1. 문 앞에서 신원 확인",
     "API 키를 확인해 Principal 을 만든다. 여기서 붙은 tenant_id 가 이후 모든 조회 조건에 붙는다."),
    ("02_", "2. 같은 요청이 아까 왔었나",
     "재료 넷으로 멱등성 키를 만들어 이미 처리했는지 본다. 취소 버튼을 두 번 눌러도 Case 는 하나다."),
    ("03_", "3. Case 를 만들고 첫 이벤트를 남긴다",
     "행과 이벤트가 한 트랜잭션이다. new 는 행을 만든 찰나에만 있고 곧 classifying 이 된다."),
    ("04_", "4. 의도와 이슈와 감성을 한 번에 분류",
     '"취소" 라고 썼지만 환불을 원하는 문의라 intent 가 return 이다. 이 한 단어가 팀을 정한다.'),
    ("05_", "5. 어느 팀 일인지 찾는다",
     "여섯 팀의 자기소개만 보고 고른다. 정확히 하나가 아니면 사람에게 넘긴다."),
    ("06_", "6. 그 팀의 무슨 기능을 쓸지 고른다",
     "intent 로 시작하는 첫 capability 에서 멈춘다. 목록 순서가 곧 우선순위다."),
    ("07_", "7. 근거를 모아 예산 안으로 자른다",
     "12,000 토큰을 넘으면 정해진 순서로 뺀다. 뺐으면 뺐다고 적는다. 신호 없는 축소는 폴백이다."),
    ("08_", "8. Team 이 판단한다",
     "다섯 가지를 순서대로 검사한다. 환불이 맞다고 판단해도 실행하지 않고 제안만 돌려준다."),
    ("09_", "9. 답변 문장을 만들고 톤을 검토한다",
     "지금 이 단계는 꺼져 있다. 그래서 고객이 받는 문장은 팀이 코드에 적어 둔 고정 문구다."),
    ("10_", "10. 결과를 상태로 반영한다",
     "completed 이벤트를 남기고 종결한다. 답은 나갔는데 기록이 없는 상황이 안 생긴다."),
    ("11_", "11. 고객이 답을 받는다",
     "답변에 근거가 같이 나간다. 왜 그렇게 판단했는지 되짚을 수 있어야 하기 때문이다."),
    ("12_", "12. 기록이 남는다",
     "다섯 표에 흔적이 남는다. 지금 상태는 이벤트를 순서대로 적용한 결과일 뿐이다."),
    ("13_", "작은 구조에서 본 같은 흐름, 상태 12개",
     "단계 12개와 상태 12개는 다른 축이다. 둘 다 열둘이라 헷갈리지만 겹치지 않는다."),
    ("14_", "전달 문서가 바뀌어 가는 모양",
     "같은 문의 하나가 다섯 번 모습을 바꾼다. 그리고 표로 내려앉는다."),
    ("15_", "다른 길로 빠지는 경우",
     "앞의 열두 장은 전부 통과한 길이다. 실제로는 아홉 군데에서 갈린다."),
]

CSS = """
:root{--bg:#f6f7fa;--card:#fff;--line:#dfe3ec;--ink:#161c28;--dim:#5c667a;--accent:#2f5bd8}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#12151c;--card:#191d26;--line:#2b3240;--ink:#e6e9f0;--dim:#98a2b8;--accent:#7ea0f5}}
:root[data-theme=dark]{--bg:#12151c;--card:#191d26;--line:#2b3240;--ink:#e6e9f0;
--dim:#98a2b8;--accent:#7ea0f5}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:"Malgun Gothic","\\B9D1\\C740 \\ACE0\\B515",system-ui,sans-serif;line-height:1.7}
.wrap{max-width:1180px;margin:0 auto;padding:0 20px 90px}
header{padding:44px 0 10px}
h1{font-size:30px;margin:0 0 10px;letter-spacing:-.02em}
header p{margin:0;color:var(--dim);font-size:15px;max-width:70ch}
nav{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);
padding:10px 0;margin:22px 0 0;z-index:5;overflow-x:auto;white-space:nowrap}
nav a{display:inline-block;padding:5px 11px;margin-right:3px;font-size:12.5px;
color:var(--dim);text-decoration:none;border:1px solid var(--line);border-radius:99px}
nav a:hover{color:var(--accent);border-color:var(--accent)}
figure{margin:34px 0 0;background:var(--card);border:1px solid var(--line);
border-radius:14px;overflow:hidden}
figure img{display:block;width:100%;height:auto}
figcaption{padding:15px 20px 18px;border-top:1px solid var(--line)}
figcaption b{display:block;font-size:16px;margin-bottom:4px}
figcaption span{color:var(--dim);font-size:14px}
.foot{margin-top:52px;padding-top:20px;border-top:1px solid var(--line);
color:var(--dim);font-size:13.5px}
code{background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:1px 5px;
font-size:13px;font-family:Consolas,monospace}
@media(max-width:640px){h1{font-size:23px}.wrap{padding:0 14px 60px}}
"""


def main():
    if not os.path.isdir(SRC):
        raise SystemExit("그림 폴더가 없다: %s" % SRC)
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".png"))
    used, parts, links = set(), [], []

    for i, (prefix, head, desc) in enumerate(SHEETS, 1):
        match = [f for f in files if f.startswith(prefix)]
        if not match:
            raise SystemExit("그림을 못 찾았다: %s" % prefix)
        name = match[0]
        used.add(name)
        with open(os.path.join(SRC, name), "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        parts.append(
            '<figure id="s%d"><img alt="%s" src="data:image/png;base64,%s">'
            '<figcaption><b>%s</b><span>%s</span></figcaption></figure>'
            % (i, html.escape(head), b64, html.escape(head), html.escape(desc)))
        links.append('<a href="#s%d">%s</a>' % (i, html.escape(head.split(".")[0][:14])))

    left = [f for f in files if f not in used]
    if left:
        # ★조용히 빠뜨리지 않는다. 그림을 늘렸는데 표에 안 적으면 여기서 걸린다.
        raise SystemExit("표에 없는 그림이 있다: %s" % ", ".join(left))

    page = (
        "<!doctype html>\n<html lang=\"ko\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        "<title>취소·환불 한 건이 지나는 길</title>\n<style>%s</style>\n</head>\n<body>\n"
        "<div class=\"wrap\">\n<header>\n<h1>취소·환불 한 건이 지나는 길</h1>\n"
        "<p>고객이 \"어제 주문한 거 취소하고 환불받고 싶어요\" 를 보낸 순간부터 답이 "
        "돌아갈 때까지, 어떤 코드를 지나 무엇이 어디에 기록되는지 한 건으로 따라갑니다. "
        "각 장 위쪽의 진행바가 지금 어디인지 알려 줍니다.</p>\n</header>\n"
        "<nav>%s</nav>\n%s\n"
        "<div class=\"foot\">근거는 셋입니다. 흐름과 코드 경로는 "
        "<code>program/onboarding/trace_refund_case.html</code>, 구조 분류는 "
        "<code>final_project_cs/docs/handoff/08_모듈_컴포넌트_목록.md</code>, 담당은 "
        "<code>program/plan/A-COP_스프린트_에픽_설계.md</code> 입니다.<br>"
        "이 파일은 <code>program/onboarding/build_trace_html.py</code> 가 만듭니다. "
        "그림을 고치려면 <code>program/onboarding/trace/</code> 의 생성기를 고치고 "
        "다시 돌리세요. 손으로 고치지 마세요.</div>\n</div>\n</body>\n</html>\n"
        % (CSS, "\n".join(links), "\n".join(parts)))

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page)
    print("만듦: %s  (%.1f MB, 그림 %d장)"
          % (OUT, os.path.getsize(OUT) / 1048576, len(SHEETS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
