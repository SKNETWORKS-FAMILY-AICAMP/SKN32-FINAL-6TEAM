# -*- coding: utf-8 -*-
"""A-COP 파트별 학습 가이드 6장을 만든다.

    python program/onboarding/build_guides.py

★파일마다 CSS 를 안에 박는다. 공용 css 파일로 빼면 링크가 깨진 채로 한 장만
  퍼갔을 때 글자만 남는다. 학습 자료는 한 장씩 따로 돌아다니는 물건이다.

★코드 경로와 줄번호는 전부 실제로 확인한 값이다(2026-08-31, final_project_cs).
  줄번호는 코드가 바뀌면 밀린다. 그래서 함수 이름을 같이 적어 두었다 —
  줄이 안 맞으면 이름으로 찾으라는 뜻이다.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

CSS = """
:root{--bg:#f6f7fa;--surface:#fff;--line:#dfe3ec;--text:#161c28;--dim:#5c667a;
--code-bg:#eef1f6;--warn-bg:#fff8e8;--warn-line:#e3c26a;--ok-bg:#eefbf4;--ok-line:#7fcaa6}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#12151c;--surface:#191d26;--line:#2b3240;--text:#e6e9f0;--dim:#98a2b8;
--code-bg:#0f1219;--warn-bg:#2a2415;--warn-line:#7a6420;--ok-bg:#13251d;--ok-line:#2f6b50}}
:root[data-theme=dark]{--bg:#12151c;--surface:#191d26;--line:#2b3240;--text:#e6e9f0;
--dim:#98a2b8;--code-bg:#0f1219;--warn-bg:#2a2415;--warn-line:#7a6420;
--ok-bg:#13251d;--ok-line:#2f6b50}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font-family:"Malgun Gothic","\\B9D1\\C740 \\ACE0\\B515",system-ui,-apple-system,sans-serif;
font-size:16px;line-height:1.75;-webkit-text-size-adjust:100%}
.wrap{max-width:880px;margin:0 auto;padding:0 20px 80px}
code,pre{font-family:"D2Coding",Consolas,"Courier New",monospace}
.top{background:var(--accent);color:#fff;padding:32px 0 26px}
.top .wrap{padding-bottom:0}
.kicker{font-size:13px;letter-spacing:.06em;opacity:.85;margin:0 0 6px}
h1{font-size:29px;line-height:1.3;margin:0 0 10px;font-weight:800;letter-spacing:-.02em}
.top p.sub{margin:0;font-size:15.5px;opacity:.94;max-width:64ch}
.who{margin-top:15px;font-size:13.5px;opacity:.9}
nav.parts{background:var(--surface);border-bottom:1px solid var(--line);
position:sticky;top:0;z-index:5;overflow-x:auto}
nav.parts .wrap{display:flex;gap:2px;padding:0 20px;white-space:nowrap}
nav.parts a{display:block;padding:11px 12px;font-size:13px;color:var(--dim);
text-decoration:none;border-bottom:2px solid transparent}
nav.parts a:hover{color:var(--text)}
nav.parts a[aria-current=page]{color:var(--accent);border-bottom-color:var(--accent);font-weight:700}
h2{font-size:21px;margin:46px 0 4px;letter-spacing:-.01em;padding-left:13px;
border-left:4px solid var(--accent)}
h2+.lede{color:var(--dim);margin:0 0 16px;padding-left:17px;font-size:14.5px}
h3{font-size:16.5px;margin:26px 0 8px}
p{margin:0 0 14px}
ul,ol{margin:0 0 14px;padding-left:22px}
li{margin:5px 0}
a{color:var(--accent)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:11px;
padding:15px 18px;margin:14px 0}
.note{background:var(--warn-bg);border:1px solid var(--warn-line);border-radius:11px;
padding:14px 18px;margin:16px 0}
.note b{display:block;margin-bottom:4px}
.good{background:var(--ok-bg);border:1px solid var(--ok-line);border-radius:11px;
padding:14px 18px;margin:16px 0}
.steps{list-style:none;padding:0;margin:16px 0;counter-reset:s}
.steps>li{counter-increment:s;background:var(--surface);border:1px solid var(--line);
border-radius:11px;padding:13px 18px 13px 56px;position:relative;margin:9px 0}
.steps>li::before{content:counter(s);position:absolute;left:16px;top:14px;width:26px;
height:26px;border-radius:50%;background:var(--accent);color:#fff;display:grid;
place-items:center;font-size:13.5px;font-weight:700}
.steps .path{font-family:"D2Coding",Consolas,monospace;font-size:13.5px;font-weight:700;
display:block;margin-bottom:3px;word-break:break-all}
.steps .why{color:var(--dim);font-size:14.5px}
.tblwrap{overflow-x:auto;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:14.5px;background:var(--surface)}
th,td{text-align:left;padding:9px 11px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12.5px;color:var(--dim);font-weight:700;white-space:nowrap}
td code{font-size:13px}
pre{background:var(--code-bg);border:1px solid var(--line);border-radius:9px;
padding:13px 15px;overflow-x:auto;font-size:13.5px;line-height:1.6;margin:12px 0}
:not(pre)>code{background:var(--code-bg);border-radius:4px;padding:1px 5px;font-size:14px}
.q{margin:16px 0;padding-left:20px;border-left:3px solid var(--line)}
.q li{margin:9px 0}
.foot{margin-top:52px;padding-top:18px;border-top:1px solid var(--line);
color:var(--dim);font-size:13.5px}
.flow{list-style:none;padding:0;margin:20px 0;counter-reset:f}
.flow>li{counter-increment:f;position:relative;padding:0 0 26px 46px;border-left:2px solid var(--line);margin:0}
.flow>li:last-child{border-left-color:transparent;padding-bottom:0}
.flow>li::before{content:counter(f);position:absolute;left:-15px;top:0;width:28px;height:28px;
border-radius:50%;background:var(--accent);color:#fff;display:grid;place-items:center;
font-size:13.5px;font-weight:700}
.flow h3{margin:1px 0 4px;font-size:17px}
.flow .owner{display:inline-block;font-size:11.5px;font-weight:700;border-radius:5px;
padding:1px 8px;margin-left:8px;background:var(--code-bg);color:var(--dim);vertical-align:2px}
.flow .where{font-family:"D2Coding",Consolas,monospace;font-size:13px;color:var(--dim);
display:block;margin:6px 0 0;word-break:break-all}
@media(max-width:600px){h1{font-size:23px}body{font-size:15px}.steps>li{padding-left:50px}
.flow>li{padding-left:34px}}
"""

PARTS = [
    # ★0번은 파트가 아니라 축이 다른 한 장이다. 1~6 은 팀 담당 기준으로 자른 것이고,
    #   0번은 요청 하나가 지나는 순서로 자른 것이다. 같은 코드를 두 방향에서 본다.
    ("00_request_flow.html", "요청이 지나는 길", "#3c4a5e"),
    ("01_case_runtime.html", "Case 런타임", "#2f5bd8"),
    ("02_access_action.html", "진입과 실행", "#b8442f"),
    ("03_agent_team.html", "Agent Team", "#0d7a4d"),
    ("04_context_rag.html", "근거와 RAG", "#6b3fa0"),
    ("05_evaluation.html", "평가 하네스", "#a8720c"),
    ("06_composition_ops.html", "조립과 운영", "#0f7b8a"),
]


def nav(current):
    links = "".join(
        '<a href="%s"%s>%d. %s</a>' % (f, ' aria-current="page"' if f == current else "", i, t)
        for i, (f, t, _) in enumerate(PARTS, 0))
    return '<nav class="parts"><div class="wrap">%s</div></nav>' % links


def steps(rows):
    items = "".join('<li><span class="path">%s</span><span class="why">%s</span></li>'
                    % (p, w) for p, w in rows)
    return '<ol class="steps">%s</ol>' % items


def table(head, rows):
    th = "".join("<th>%s</th>" % h for h in head)
    tr = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r) for r in rows)
    return '<div class="tblwrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (th, tr)


def flow(rows):
    """요청이 지나는 단계 하나를 상자로 만든다. (제목, 담당 파트, 설명, 코드 위치)"""
    out = []
    for title, owner, why, where in rows:
        out.append('<li><h3>%s<span class="owner">%s</span></h3>%s'
                   '<span class="where">%s</span></li>' % (title, owner, why, where))
    return '<ol class="flow">%s</ol>' % "".join(out)


def page(filename, title, accent, kicker, sub, who, body):
    return """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s · A-COP 학습 가이드</title>
<style>:root{--accent:%s}%s</style>
</head>
<body>
<header class="top"><div class="wrap">
<p class="kicker">%s</p>
<h1>%s</h1>
<p class="sub">%s</p>
<p class="who">%s</p>
</div></header>
%s
<main class="wrap">
%s
<div class="foot">
A-COP 학습 가이드 · 기준 저장소 <code>final_project_cs</code> · 확인일 2026-08-31<br>
코드 줄번호는 코드가 바뀌면 밀립니다. 안 맞으면 함께 적힌 함수 이름으로 찾으세요.<br>
이 파일은 <code>program/onboarding/build_guides.py</code> 가 만듭니다. 손으로 고치지 마세요.
</div>
</main>
</body>
</html>
""" % (title, accent, CSS, kicker, title, sub, who, nav(filename), body)


# ══════════════════════════════════════════════════════ 0. 요청이 지나는 길
P0 = """
<h2>이 장은 축이 다릅니다</h2>
<p class="lede">1번부터 6번은 담당별로 잘랐고, 이 장은 요청 하나가 지나는 순서로 잘랐습니다.</p>

<p>담당별로 읽으면 자기 파트는 깊어지는데 "그래서 내 코드가 언제 불리나"가 안 잡힙니다.
이 장은 반대로 갑니다. 고객이 문의를 하나 보낸 순간부터 답이 나갈 때까지를 따라가면서,
각 단계를 <b>어느 파트가 소유하고 어느 파일에 있는지</b>를 붙여 둡니다.</p>

<div class="card">
<p style="margin:0"><b>이 장부터 읽으세요.</b> 전체 지도를 한 번 훑고 나서 자기 파트로 들어가면
훨씬 빨리 붙습니다. 여기 나오는 파일 경로와 줄번호는 실제로 그 코드가 있는 자리입니다.</p>
</div>

<h2>문의 한 건이 지나는 열 단계</h2>
<p class="lede">POST /v1/cases 하나를 끝까지 따라갑니다.</p>
""" + flow([
    ("문 앞에서 신원 확인", "2. 진입과 실행",
     "<p>요청에 붙은 API 키를 확인하고 <code>case:write</code> 권한이 있는지 봅니다. "
     "없으면 여기서 끝납니다. 이 검사를 통과해야 <code>Principal</code>(누구인지)이 만들어지고, "
     "그 안에 담긴 <code>tenant_id</code>가 이후 모든 조회 조건에 붙습니다.</p>",
     "app/presentation/api/cases.py:69 <code>create()</code> · app/presentation/security.py:47 <code>require_scope()</code>"),

    ("같은 요청이 아까 왔었나", "2. 진입과 실행",
     "<p>요청 ID와 고객과 메시지를 재료로 멱등성 키를 만들고, 그 키로 이미 처리한 적이 있는지 "
     "먼저 찾습니다. 있으면 <b>새로 만들지 않고 그때 만든 Case를 그대로 돌려줍니다.</b> "
     "네트워크가 끊겨서 클라이언트가 재시도해도 Case가 두 개 생기지 않는 이유입니다.</p>",
     "app/core/idempotency.py:8 <code>idempotency_key()</code> · cases.py:71~79"),

    ("Case를 만들고 첫 이벤트를 남긴다", "1. Case 런타임",
     "<p><code>customer_cases</code>에 행을 하나 만들고 <code>transition_case()</code>로 "
     "<code>CREATED</code> 이벤트를 남깁니다. 상태는 <code>new</code>입니다. "
     "여기서부터 이 Case에 일어나는 모든 일이 <code>case_events</code>에 쌓입니다.</p>",
     "app/core/transition.py:116 <code>transition_case()</code> · cases.py:81~82"),

    ("의도·이슈·감성을 한 번에 분류", "3. Agent Team",
     "<p>메시지에서 개인정보를 지운 뒤 분류기에 넘깁니다. 성공하면 <code>CLASSIFIED</code>, "
     "실패하면 <code>CLASSIFICATION_FAILED</code> 이벤트가 남고 Case는 사람에게 넘어갑니다. "
     "<b>실패해도 Case는 만들어집니다.</b> 조용히 빈 값으로 두지 않는 것이 핵심입니다.</p>",
     "cases.py:84~92 · app/modules/customer_ops/feedback.py:86 <code>classify()</code>"),

    ("어느 팀 일인지 찾는다", "1. Case 런타임",
     "<p>분류된 의도로 Registry에 물어 담당 Team을 찾습니다. 조건 하나에 Team이 정확히 "
     "하나여야 하고, 없으면 <code>ROUTING_FAILED</code>를 남기고 사람에게 넘깁니다. "
     "찾으면 <code>ROUTED</code> 이벤트에 팀 이름과 capability를 적습니다.</p>",
     "app/application/controller.py:124 <code>registry.resolve()</code> · :126 ROUTED 전이"),

    ("근거를 모아 예산 안으로 자른다", "4. 근거와 RAG",
     "<p>정책 문서를 검색하고 Case 상태를 모아 <code>ContextPack</code>을 만듭니다. "
     "12,000 토큰을 넘으면 정해진 순서로 뺍니다. 검색이 실패하면 빈 결과를 조용히 쓰지 않고 "
     "<code>retrieval_failed</code> 신호를 Context Broker에 넘겨 <code>degraded</code>로 표시하게 합니다.</p>",
     "controller.py:74 <code>_policy()</code> · :89 <code>context_broker.build()</code> · app/core/context.py:90"),

    ("Team이 판단한다", "3. Agent Team",
     "<p><code>TeamTask</code>를 만들어 Team에게 넘기고 결과를 기다립니다. "
     "제한 시간을 넘기면 기다리다 말고 <code>GUARDRAIL_ESCALATED</code>로 사람에게 넘깁니다. "
     "Team은 여기서 <b>제안만</b> 돌려줍니다. 아무것도 실행하지 않습니다.</p>",
     "controller.py:153 <code>_task()</code> · :157 <code>team_executor.execute()</code>"),

    ("제안을 DB 사실과 대조한다", "2. 진입과 실행",
     "<p>Team이 말한 주문번호가 실제로 있는지, 금액과 수량이 맞는지 확인합니다. "
     "안 맞으면 제안을 버리고 사람에게 넘깁니다. 없는 것을 있다고 말하는 답변이 "
     "고객에게 가는 것을 여기서 막습니다.</p>",
     "app/core/verification.py:114 <code>verify_proposal()</code> · controller.py:168 <code>_apply_result(context=task.context)</code>"),

    ("결과를 상태로 반영한다", "1. Case 런타임",
     "<p>Team이 돌려준 다음 행동에 따라 상태가 갈립니다. 바로 답할 수 있으면 "
     "<code>resolved</code>, 사람 결재가 필요하면 <code>waiting_approval</code>, "
     "고객에게 물어야 하면 <code>waiting_input</code>입니다. 기다리는 상태면 "
     "재개용 토큰이 함께 발급됩니다.</p>",
     "controller.py:172 <code>_apply_result()</code> · :258 <code>_event_for_result()</code>"),

    ("사람이 승인하면 그때 실행된다", "2. 진입과 실행",
     "<p>운영자가 승인 버튼을 누르면 <b>실행 직전에 사실을 한 번 더 조회해</b> "
     "그 사이에 바뀐 것이 없는지 봅니다. 통과해야 실제로 실행되고, 무엇을 했는지 "
     "감사 로그에 남습니다.</p>",
     "cases.py:146 <code>approve()</code> · app/application/proposal_guard.py:70 <code>recheck_before_execution()</code>"),
]) + """

<h2>여기서 배울 것 세 가지</h2>
<p class="lede">흐름을 따라가다 보면 눈에 띄는, 설계 의도가 드러나는 자리들입니다.</p>

<h3>분류에 실패해도 Case는 만들어집니다</h3>
<p>4단계에서 분류가 실패하면 그냥 넘어가는 게 아니라 <code>CLASSIFICATION_FAILED</code>
이벤트를 남기고 사람에게 넘깁니다. "모르겠으면 빈칸으로 두고 진행"이 아니라
"모른다는 사실 자체를 기록하고 멈춤"입니다. 빈 <code>intent</code>로 라우팅을 시도하면
엉뚱한 팀에 가거나, 더 나쁘게는 그 빈 값이 답변까지 흘러갑니다.</p>

<h3>대조에 쓰는 근거는 Team이 준 것이 아닙니다</h3>
<p>8단계가 이 시스템에서 제일 미묘한 자리입니다. Team이 돌려준 결과 안에도 근거 꾸러미가
들어 있지만, 대조할 때는 그것을 안 씁니다. <b>Controller가 직접 만들어 넘겼던</b>
<code>task.context</code>를 씁니다.</p>
<p>Team이 준 근거로 Team이 준 제안을 검사하면, 지어낸 근거로 지어낸 제안을 통과시킬 수 있습니다.
검사가 순환합니다. 그래서 위조할 수 없는 쪽으로 잽니다. 코드에도 이 이유가 주석으로 붙어 있습니다.</p>

<h3>멱등성은 말이 아니라 UNIQUE 제약입니다</h3>
<p>2단계의 "이미 처리했나" 조회는 <code>action_requests.idempotency_key</code>의 UNIQUE
제약 위에 얹혀 있습니다. 코드로 "잘 확인하자"가 아니라 DB가 두 번째를 거부합니다.
같은 요청 10회에 부수효과 1회를 <b>테스트로 증명</b>하는 것도 이 때문에 가능합니다.</p>

<h2>단계와 파트 대응표</h2>
<p class="lede">자기 파트가 전체 어디쯤인지 확인하는 표입니다.</p>
""" + table(["파트", "맡는 단계", "한 줄"], [
    ["<a href='01_case_runtime.html'>1. Case 런타임</a>", "3, 5, 9",
     "Case를 만들고, 팀을 찾고, 결과를 상태로 반영합니다"],
    ["<a href='02_access_action.html'>2. 진입과 실행</a>", "1, 2, 8, 10",
     "문을 열고 닫고, 중복을 거르고, 실행 직전에 막습니다"],
    ["<a href='03_agent_team.html'>3. Agent Team</a>", "4, 7",
     "분류하고 판단합니다. 실행은 안 합니다"],
    ["<a href='04_context_rag.html'>4. 근거와 RAG</a>", "6",
     "판단에 쓸 근거를 예산 안에서 고릅니다"],
    ["<a href='05_evaluation.html'>5. 평가 하네스</a>", "흐름 밖",
     "이 흐름 전체를 여러 번 돌려 좋아졌는지 잽니다"],
    ["<a href='06_composition_ops.html'>6. 조립과 운영</a>", "흐름 밖",
     "이 흐름에 어떤 부품이 끼워질지 정하고, 결과를 화면으로 봅니다"],
]) + """
<h2>직접 따라가 보기</h2>
<p class="lede">읽는 것보다 한 건 흘려 보는 게 빠릅니다.</p>

<p>데모 Case 두 건을 만들어 두는 스크립트가 있습니다. 하나는 승인 대기에서 멈추고
하나는 종결까지 갑니다.</p>
<pre>python -m scripts.seed
python -m scripts.seed_demo_cases
python -m uvicorn app.presentation.api.app:app --port 8042</pre>

<p><code>http://127.0.0.1:8042/ui/cases</code>를 열고 Case 하나를 눌러 보세요.
이벤트가 시간순으로 쌓여 있는데, <b>그 목록이 위의 10단계와 그대로 맞습니다.</b>
<code>created</code> → <code>classified</code> → <code>routed</code> → ... 순서입니다.</p>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0">승인 대기에서 멈춰 있는 Case를 골라 승인 버튼을 눌러 보세요.
누르기 전에 <code>proposal_guard.py</code>의 <code>recheck_before_execution()</code>에
중단점을 걸거나 <code>print</code>를 하나 넣어 두면, 실행 직전 재조회가 실제로 일어나는 것을
눈으로 볼 수 있습니다.</p>
</div>

<h2>다 읽었는지 확인하는 질문</h2>
<ol class="q">
<li>같은 문의를 실수로 두 번 보냈습니다. Case는 몇 개 생깁니까? 어느 단계가 막습니까?</li>
<li>분류기가 죽어 있으면 문의를 넣었을 때 어떻게 됩니까? 응답은 500입니까?</li>
<li>Team이 "주문번호 ORD-9999를 환불하자"고 했는데 그런 주문이 없습니다. 어디서 걸립니까?</li>
<li>6단계에서 정책 검색이 실패했습니다. Team은 그 사실을 어떻게 압니까?</li>
<li>승인 버튼을 누른 시점과 제안이 만들어진 시점 사이에 재고가 바뀌었습니다. 무슨 일이 일어납니까?</li>
</ol>
"""


# ══════════════════════════════════════════════════════ 1. Case 런타임
P1 = """
<h2>이 파트가 하는 일</h2>
<p class="lede">문의 하나를 끝까지 책임지는 자리입니다.</p>

<p>고객이 보낸 문의 하나를 <b>Case</b>라는 업무 단위로 바꾸고, 그것이 접수부터 종료까지
어떤 상태를 지나는지 관리합니다. 어느 팀에게 일을 줄지 정하고, 기다려야 하면 멈췄다가
조건이 갖춰지면 다시 이어서 실행합니다.</p>

<p>이 파트가 없으면 문의는 단발 질의응답이 됩니다. "고객 답을 기다리는 중",
"사람 결재를 기다리는 중" 같은 상태를 표현할 수 없어서, 며칠 걸리는 일은 아예
다룰 수가 없습니다.</p>

<h2>먼저 알아야 할 말 세 개</h2>
<p class="lede">이 셋을 모르면 코드가 안 읽힙니다.</p>

<h3>Case</h3>
<p>문의 하나입니다. 상태를 가지고 있고, 그 상태는 12개 중 하나입니다.
<code>new</code>로 시작해서 <code>resolved</code>나 <code>escalated</code>로 끝납니다.
중간에 <code>waiting_approval</code>처럼 멈춰 있는 상태가 있는 것이 핵심입니다.</p>

<h3>이벤트 소싱</h3>
<p>무슨 일이 있었는지를 <code>case_events</code> 표에 <b>추가만</b> 하고 고치지 않습니다.
지금 상태를 담은 <code>customer_cases</code> 표는 그 이벤트들을 순서대로 적용한 결과일 뿐입니다.
그래서 나중에 이벤트만 다시 재생하면 "그때 무슨 일이 있었나"를 되짚을 수 있습니다.</p>

<h3>CAS (비교 후 교체)</h3>
<p>Compare-And-Swap을 줄인 말입니다. 값을 쓸 때 "내가 읽었던 버전이 아직 그대로냐"를 같이
확인하고, 다르면 쓰기를 거부합니다. 두 사람이 같은 Case를 동시에 고쳐도 나중 사람의 쓰기가
앞사람 것을 조용히 덮어쓰지 않습니다.</p>

<h2>코드는 이 순서로 읽습니다</h2>
<p class="lede">어휘 → 규칙 → 실행 루프 순입니다. 반대로 읽으면 헤맵니다.</p>
""" + steps([
    ("app/core/contracts.py:53 <code>CaseStatus</code>, :68 <code>NextAction</code>",
     "먼저 어휘를 외웁니다. 상태 12개와 다음 행동 7개가 이 프로젝트의 기본 단어입니다. "
     "코드 어디를 가도 이 이름들이 나옵니다."),
    ("app/domain/events.py:16 <code>EventType</code>",
     "무슨 일이 일어날 수 있는지의 목록입니다. 상태가 &#39;명사&#39;라면 이건 &#39;동사&#39;입니다."),
    ("app/core/transition.py:116 <code>transition_case()</code>",
     "상태를 바꾸는 <b>유일한</b> 문입니다. 이 함수 하나만 제대로 읽으면 이 파트의 절반을 이해한 겁니다. "
     "여기서 이벤트 기록, 상태 갱신, 발행할 메시지 적재가 한 트랜잭션으로 묶입니다."),
    ("app/core/transition.py:215 <code>replay_case()</code>",
     "이벤트만으로 상태를 다시 만들어 봅니다. 왜 이벤트를 안 고치는지 여기서 납득이 됩니다."),
    ("app/core/registry.py:29 <code>TeamRegistry</code>",
     "&#39;이 문의는 어느 팀 일인가&#39;를 푸는 곳입니다. Team을 이름이 아니라 capability(할 수 있는 일)로 찾습니다."),
    ("app/application/controller.py:30 <code>Controller</code>",
     "위의 것들을 잇는 실행 루프입니다. 분류 → 라우팅 → 근거 조합 → Team 실행 → 결과 반영이 여기서 돕니다. "
     "332줄로 이 파트에서 제일 큽니다. 처음엔 <code>_apply_result</code>와 <code>_transition_with_retry</code>만 보세요."),
    ("app/application/case_service.py:26 <code>CaseService</code>",
     "실행 시작과 재개를 관리합니다. 같은 Case가 동시에 두 번 도는 것을 막습니다."),
]) + """
<h2>직접 돌려 보기</h2>
<p class="lede">읽기만 하면 안 남습니다. 테스트를 돌리고 하나를 일부러 깨 보세요.</p>
<pre>python -m pytest tests/unit/core/test_case_reducer.py -q
python -m pytest tests/contract/test_case_state_table.py -q
python -m pytest tests/integration/controller -q</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0"><code>tests/contract/test_case_state_table.py</code>를 열고 전이표를 봅니다.
그다음 <code>transition.py</code>에서 허용되지 않은 전이를 하나 골라 억지로 시켜 보세요.
어떤 예외가 어디서 나는지 보면 이 파트의 방어선이 어디 있는지 보입니다.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>app/core/case_runtime/ 폴더는 비어 있습니다</b>
<p style="margin:6px 0 0">폴더는 있는데 파일이 하나도 없습니다. <code>docs/handoff/07_모듈화_구조.md</code>이 제안한
폴더 구조만 만들어 두고 실제 코드는 <code>app/core/</code> 바로 아래 평평하게 있습니다.
여기를 뒤지다가 "코드가 어디 있지" 하고 헤매기 쉽습니다. <code>app/core/access_action/</code>도 마찬가지입니다.</p>
</div>

<div class="note">
<b>customer_cases를 직접 UPDATE하면 안 됩니다</b>
<p style="margin:6px 0 0">상태를 바꾸는 문은 <code>transition_case()</code> 하나뿐입니다.
직접 UPDATE하면 이벤트가 안 남아서 재생이 깨집니다. <code>CLAUDE.md</code> §0.3에 있습니다.</p>
</div>

<div class="note">
<b>실제로 났던 결함</b>
<p style="margin:6px 0 0">Controller가 <code>resuming</code>에서 <code>resumed</code> 이벤트를
건너뛰고 바로 종료로 가려다 상태기계에 막힌 적이 있습니다. 기록은
<code>docs/reports/debugs/2026-08-12_2230_Controller가_resuming에서_resumed를_건너뛴다.md</code>에 있습니다.
결함 리포트를 읽는 것이 코드만 읽는 것보다 빠를 때가 많습니다.</p>
</div>

<h2>다 읽었는지 확인하는 질문</h2>
<ol class="q">
<li>고객이 추가 정보를 줘야 해서 사흘 멈춰 있는 Case는 어떤 상태입니까? 그 상태에서 다시 돌 때 어느 노드로 들어갑니까?</li>
<li>두 사람이 같은 Case를 동시에 승인하면 무슨 일이 일어납니까?</li>
<li>DB에서 <code>customer_cases</code> 한 행을 통째로 지웠다면, 복구할 수 있습니까? 무엇으로?</li>
<li>Team을 하나 추가하면 이 파트의 코드 중 무엇을 고쳐야 합니까?</li>
</ol>

<h2>옆 파트와 맞닿는 곳</h2>
""" + table(["맞닿는 파트", "어디서 만나나"], [
    ["<a href='02_access_action.html'>2. 진입과 실행</a>",
     "Case를 만드는 요청이 거기서 들어옵니다. 승인도 거기서 받습니다"],
    ["<a href='03_agent_team.html'>3. Agent Team</a>",
     "Controller가 <code>TeamTask</code>를 만들어 넘기고 <code>TeamResult</code>를 받습니다"],
    ["<a href='04_context_rag.html'>4. 근거와 RAG</a>",
     "Controller가 Team을 부르기 직전에 Context Broker에게 근거를 받아 갑니다"],
])


# ══════════════════════════════════════════════════════ 2. 진입과 실행
P2 = """
<h2>이 파트가 하는 일</h2>
<p class="lede">밖에서 들어오는 문이고, 실제로 무언가를 실행하는 마지막 관문입니다.</p>

<p>두 가지를 맡습니다. 하나는 <b>진입</b>입니다. REST API, 개인 AI가 붙는 MCP, 외부
에이전트가 붙는 A2A 세 갈래로 들어오는 요청을 받아 "누가, 무슨 권한으로" 왔는지 확인합니다.
다른 하나는 <b>실행</b>입니다. 환불처럼 되돌릴 수 없는 일은 사람 승인을 받고, 같은 요청이
여러 번 와도 실제로는 한 번만 처리하고, 무엇을 했는지 남깁니다.</p>

<p>이 파트가 없으면 아무나 무슨 권한으로 들어왔는지 모르고, 네트워크가 한 번 끊겨서
클라이언트가 재시도하면 환불이 두 번 나갑니다.</p>

<h2>먼저 알아야 할 말 세 개</h2>

<h3>scope</h3>
<p>API 키에 붙어 있는 권한 이름입니다. <code>case:read</code>, <code>action:approve</code>처럼
생겼고 지금 10개가 있습니다. 목록의 정본은 코드가 아니라
<code>config/guardrails.yaml</code>의 <code>security.scopes</code>입니다.
코드에 흩어 놓으면 어디가 진짜인지 몰라지기 때문입니다.</p>

<h3>멱등성 (idempotency)</h3>
<p>같은 요청을 열 번 보내도 실제 부수효과는 한 번만 일어나는 성질입니다. 말로 하는 게
아니라 DB의 UNIQUE 제약으로 강제합니다. <code>action_requests.idempotency_key</code>가
그 자리입니다.</p>

<h3>승인 경계</h3>
<p>AI가 만든 것은 <b>제안</b>까지입니다. 돈이 나가거나 되돌릴 수 없는 일은 사람이
승인 버튼을 눌러야 실행됩니다. 이 경계가 이 프로젝트의 안전장치 중 제일 중요한 것입니다.</p>

<h2>코드는 이 순서로 읽습니다</h2>
<p class="lede">들어오는 길 → 막는 장치 → 실행 직전 재검사 순입니다.</p>
""" + steps([
    ("app/presentation/security.py:15 <code>Principal</code>, :47 <code>require_scope()</code>",
     "요청 하나가 &#39;누구&#39;인지를 담는 그릇과, 권한을 요구하는 장치입니다. 40줄 남짓이라 금방 읽힙니다."),
    ("app/presentation/api/app.py:14 <code>create_app()</code>",
     "라우터가 붙는 자리입니다. 이 앱에 무슨 표면이 열려 있는지 한눈에 보입니다. "
     "여기 없는 경로는 이 서버에 없는 겁니다."),
    ("app/presentation/api/cases.py",
     "REST 진입점 본체입니다. Case 생성과 조회, 그리고 :146 <code>approve()</code>가 승인 진입점입니다. "
     "파일 아래쪽 <code>_mcp_</code>로 시작하는 함수 셋이 MCP가 부르는 자리입니다."),
    ("app/core/idempotency.py:8 <code>idempotency_key()</code>",
     "8줄짜리 함수 하나입니다. 무엇을 재료로 키를 만드는지 보세요 — 요청 ID뿐 아니라 "
     "업무 대상까지 넣습니다. 그래야 &#39;다른 요청 ID로 같은 환불&#39;도 걸립니다."),
    ("app/core/verification.py:114 <code>verify_proposal()</code>",
     "AI가 만든 제안의 식별자·금액·수량을 DB 사실과 대조합니다. 없는 주문번호나 "
     "틀린 금액을 여기서 잡습니다. 순수 함수라 DB 없이 테스트됩니다."),
    ("app/application/proposal_guard.py:70 <code>recheck_before_execution()</code>",
     "검증을 <b>두 번</b> 하는 이유가 여기 있습니다. 제안할 때 한 번, 실행 직전에 또 한 번. "
     "그 사이에 사실이 바뀌었을 수 있기 때문입니다."),
    ("app/presentation/api/mcp.py",
     "개인 AI에게 여는 tool 3종입니다. 20줄뿐이고, 실제 일은 전부 <code>cases.py</code>에 위임합니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest tests/security -q
python -m pytest tests/integration/api/test_recheck_before_execution.py -q
python -m pytest tests/integration/api/test_api_runtime.py -q</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0">같은 Case 생성 요청을 같은 <code>request_id</code>로 열 번 보내고
<code>action_requests</code> 표의 행 수를 세어 보세요. 1이어야 합니다.
이걸 확인하는 테스트가 이미 있으니 그 테스트를 먼저 읽고 흉내 내면 됩니다.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>MCP는 읽기 전용입니다</b>
<p style="margin:6px 0 0"><code>open_support_case</code>라는 이름 때문에 쓰기처럼 보이지만,
Case를 만들고 분류를 시작하는 데까지입니다. 결제·환불·구독 변경은 하지 않습니다.
쓰기는 REST와 승인 경로로만 갑니다.</p>
</div>

<div class="note">
<b>타임아웃을 성공으로 추정하지 않습니다</b>
<p style="margin:6px 0 0">결제사를 불렀는데 응답이 안 오면 <code>unknown</code>으로 남기고
자동 재실행하지 않습니다. 돈이 나갔는지 안 나갔는지 모르는 상태를 &#39;모른다&#39;라고 적는 겁니다.
운영 화면에서 이 상태를 제일 센 위험색으로 칠하는 이유도 그래서입니다.</p>
</div>

<div class="note">
<b>MCP 서버는 지금 아무 데서도 서빙되지 않습니다</b>
<p style="margin:6px 0 0"><code>FastMCP</code> 객체는 만들어지는데 그것을 실행하는 코드가
저장소에 없습니다(2026-08-31 확인). tool 정의와 권한 검사는 다 있으니, 실제로 열 때
그 진입점에도 모듈 게이트를 다는 일이 남아 있습니다.</p>
</div>

<h2>다 읽었는지 확인하는 질문</h2>
<ol class="q">
<li>같은 환불 요청이 서로 다른 <code>request_id</code>로 두 번 들어오면 두 번 나갑니까?</li>
<li>제안을 검증하는데 왜 두 번 합니까? 한 번으로 부족한 구체적인 상황을 하나 말해 보세요.</li>
<li>scope 목록을 하나 늘리려면 어느 파일을 고쳐야 합니까?</li>
<li>개인 AI가 환불을 실행하려면 무엇이 필요합니까?</li>
</ol>

<h2>옆 파트와 맞닿는 곳</h2>
""" + table(["맞닿는 파트", "어디서 만나나"], [
    ["<a href='01_case_runtime.html'>1. Case 런타임</a>",
     "여기서 받은 요청이 <code>transition_case()</code>로 들어갑니다"],
    ["<a href='03_agent_team.html'>3. Agent Team</a>",
     "Team이 만든 <code>ActionProposal</code>을 여기서 검증하고 승인받아 실행합니다"],
    ["<a href='06_composition_ops.html'>6. 조립과 운영</a>",
     "승인 버튼이 있는 화면이 거기 있습니다. 감사 기록도 거기서 봅니다"],
])


# ══════════════════════════════════════════════════════ 3. Agent Team
P3 = """
<h2>이 파트가 하는 일</h2>
<p class="lede">실제 업무 판단을 하는 자리입니다. 그리고 <b>실행은 하지 않습니다.</b></p>

<p>"이 반품은 기한 안인가", "이 배송 지연은 어느 단계에서 멈췄나" 같은 판단을 합니다.
지금 6개 팀이 등록돼 있고 각자 자기가 할 수 있는 일(capability)을 선언합니다.</p>

<p>가장 중요한 규칙은 <b>Team은 부수효과를 실행하지 않는다</b>입니다. 환불이 필요하다고
판단하면 환불을 하는 게 아니라 "환불하자"는 제안(<code>ActionProposal</code>)을 돌려줍니다.
실제 실행은 <a href="02_access_action.html">진입과 실행</a> 파트의 승인 경로에서 일어납니다.</p>

<div class="card">
<p style="margin:0"><b>Core는 Team 안을 들여다보지 않습니다.</b> Team이 무슨 프롬프트를 쓰는지,
안에서 LLM을 몇 번 부르는지 Core는 모릅니다. <code>manifest</code>(자기소개)와
<code>execute()</code>(실행) 두 가지만 씁니다. 이 경계는
<code>tests/contract/test_core_isolation.py</code>가 import 검사로 강제합니다.</p>
</div>

<h2>먼저 알아야 할 말 네 개</h2>

<h3>TeamManifest</h3>
<p>Team의 자기소개서입니다. 팀 이름, 할 수 있는 일 목록, 쓸 수 있는 도구 목록,
읽을 수 있는 지식 범위, 최대 몇 단계까지 돌 수 있는지가 들어갑니다.
Registry는 이 자기소개서만 보고 라우팅합니다.</p>

<h3>TeamTask와 TeamResult</h3>
<p>들어가는 것과 나오는 것입니다. <code>TeamTask</code>에는 Case 정보와 근거 묶음이
담겨 오고, <code>TeamResult</code>에는 판단 결과와 다음 행동과 제안이 담겨 나갑니다.</p>

<h3>allowed_tools</h3>
<p>Team이 부를 수 있는 도구의 화이트리스트입니다. 목록 밖의 도구를 부르면
Registry가 아니라 도구함이 거부합니다. "혹시 몰라서 다 열어 두기"를 못 하게 하는 장치입니다.</p>

<h3>Evidence</h3>
<p>모든 주장에 붙는 출처입니다. 어디서 나온 정보인지(<code>source_type</code>,
<code>source_id</code>), 언제 본 것인지(<code>observed_at</code>)가 들어갑니다.
근거 없는 문장은 답변에 넣지 않는 것이 이 프로젝트의 첫 번째 규칙입니다.</p>

<h2>코드는 이 순서로 읽습니다</h2>
<p class="lede">계약 → 제일 짧은 Team 하나 → 도구함 → 나머지 Team 순입니다.</p>
""" + steps([
    ("app/core/contracts.py:303 <code>TeamManifest</code>, :321 <code>TeamModule</code>",
     "Team이 지켜야 할 모양입니다. <code>TeamModule</code>은 Protocol이라 상속할 필요가 없습니다 — "
     "<code>manifest</code> 속성과 <code>execute()</code> 메서드만 있으면 Team입니다."),
    ("app/core/contracts.py:165 <code>TeamTask</code>, :223 <code>TeamResult</code>, :201 <code>ActionProposal</code>",
     "들어가는 것과 나오는 것입니다. 특히 <code>TeamResult</code>의 <code>next_action</code> 필드를 보세요. "
     "&#39;승인 받아라&#39;, &#39;고객에게 물어라&#39;, &#39;사람에게 넘겨라&#39;가 전부 여기서 표현됩니다."),
    ("app/modules/customer_ops/voc_store_manager.py",
     "제일 짧은 Team입니다(약 90줄). 한 Team의 처음부터 끝까지가 여기 다 있습니다. "
     "<code>manifest</code> 선언 → <code>_evidence()</code>로 근거 만들기 → <code>execute()</code>에서 분기."),
    ("app/tools/read_tools.py:38 <code>ReadToolbox</code>, :146 <code>call()</code>",
     "Team이 DB를 읽는 유일한 통로입니다. <code>call()</code>이 <code>allowed_tools</code>를 "
     "검사하고 같은 도구를 계속 부르는 무한 루프도 막습니다."),
    ("app/modules/customer_ops/return_refund.py",
     "두 번째로 읽을 Team입니다. 환불 금액을 계산하고 제안을 만듭니다 — "
     "&#39;제안까지만&#39;이 실제로 어떻게 생겼는지 볼 수 있습니다."),
    ("app/modules/customer_ops/feedback.py:33 <code>INTENTS</code>, :86 <code>classify()</code>",
     "Team은 아니지만 이 파트 소유입니다. 문의가 들어올 때 의도·이슈·감성을 한 번에 분류합니다. "
     "여기서 실패하면 Case가 사람에게 넘어갑니다."),
    ("app/modules/customer_ops/response_review.py",
     "응대 문장을 만들고 톤을 검토하는 Team입니다. 프롬프트를 쓰는 팀이라 "
     "<code>prompts/response/</code> 폴더와 같이 봐야 합니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest tests/unit/teams -q
python -m pytest tests/contract/test_team_contract.py -q
python -m pytest tests/contract/test_core_isolation.py -q</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0"><code>voc_store_manager.py</code>를 복사해서 아무것도 안 하는
Team을 하나 만들고 <code>config/project.yaml</code>의 <code>teams</code> 목록에 추가해 보세요.
서버를 다시 띄우면 운영 콘솔 <code>/ui/admin</code>에 그 팀이 나타납니다.
<b>Core 코드는 한 줄도 안 고쳤다</b>는 것이 이 구조의 핵심입니다.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>실제로 났던 제일 큰 결함</b>
<p style="margin:6px 0 0"><code>feedback.py</code>의 <code>INTENTS</code>가 옛 구독·청구
도메인 어휘(<code>billing</code>, <code>technical</code>)로 남아 있었는데, 이 함수가 운영
API의 기본 분류기였습니다. 쇼핑몰 문의는 전부 분류 실패로 떨어졌을 상태였습니다.
지금은 <code>order</code>, <code>shipping</code>, <code>return</code>, <code>exchange</code>,
<code>other</code>입니다. 재발 방지로 <b>INTENTS가 모든 Team의 처리 가능 유형을 덮는지</b>
검사하는 테스트가 있습니다(<code>tests/unit/voc/test_feedback_intent_alignment.py</code>).</p>
</div>

<div class="note">
<b>프롬프트 키를 등록하지 않으면 팀이 매번 죽습니다</b>
<p style="margin:6px 0 0">Response Review 팀이 감사 기록 경로로 불릴 때마다
<code>no active prompt registered</code>로 죽고 있던 적이 있습니다. 프롬프트 파일을 만들고
<code>python -m scripts.register_prompts</code>로 DB에 등록해야 합니다.
Team이 프롬프트를 쓴다면 이 단계를 빼먹지 마세요.</p>
</div>

<div class="note">
<b>Team이 Core를 import하면 테스트가 붉어집니다</b>
<p style="margin:6px 0 0">반대 방향도 마찬가지입니다. Core가 Team 내부를 import하면
<code>tests/contract/test_core_isolation.py</code>가 잡습니다. 편하다고 질러 놓으면
그 자리에서 붉어지니 놀라지 마세요 — 의도된 것입니다.</p>
</div>

<h2>다 읽었는지 확인하는 질문</h2>
<ol class="q">
<li>Team이 환불이 맞다고 100% 확신해도 환불을 실행할 수 없습니다. 그러면 무엇을 돌려줍니까?</li>
<li>Team을 새로 만들 때 상속해야 할 부모 클래스는 무엇입니까?</li>
<li>Team이 <code>allowed_tools</code>에 없는 도구를 부르면 어디서 막힙니까?</li>
<li>같은 capability를 두 Team이 주장하면 무슨 일이 일어납니까?</li>
</ol>

<h2>옆 파트와 맞닿는 곳</h2>
""" + table(["맞닿는 파트", "어디서 만나나"], [
    ["<a href='01_case_runtime.html'>1. Case 런타임</a>",
     "Registry가 Team을 고르고 Controller가 <code>execute()</code>를 부릅니다"],
    ["<a href='04_context_rag.html'>4. 근거와 RAG</a>",
     "<code>TeamTask</code>에 실려 오는 <code>ContextPack</code>이 거기서 만들어집니다"],
    ["<a href='05_evaluation.html'>5. 평가 하네스</a>",
     "Team의 판단이 좋아졌는지를 거기서 숫자로 잽니다"],
])


# ══════════════════════════════════════════════════════ 4. 근거와 RAG
P4 = """
<h2>이 파트가 하는 일</h2>
<p class="lede">Team에게 줄 근거를 고르고, 예산 안에 안 들어가면 자릅니다. 자르면 잘랐다고 적습니다.</p>

<p>LLM에 한 번에 넣을 수 있는 글의 양에는 한계가 있습니다. 이 프로젝트는 그 한계를
12,000 토큰으로 정해 두었습니다. 그런데 Case 상태, 조회한 사실, 정책 문서, 과거 이력,
비슷한 Case를 다 넣으면 넘칩니다. 그래서 무엇을 넣고 무엇을 뺄지 정하는 자리가 필요합니다.</p>

<p>이 파트에는 <b>절대 어기면 안 되는 규칙</b>이 하나 있습니다. 뺐으면 뺐다고 적어야 합니다.
조용히 줄이고 아무 일 없었던 척하면 그게 폴백이고, 그 위에서 만들어진 답변은
근거가 부족한 줄도 모른 채 고객에게 갑니다.</p>

<h2>먼저 알아야 할 말 네 개</h2>

<h3>토큰</h3>
<p>LLM이 글을 세는 단위입니다. 한글은 대충 한 글자가 1~2토큰입니다. 이 프로젝트는
<code>tiktoken</code>으로 실제로 세어서 자릅니다. 글자 수로 어림잡지 않습니다.</p>

<h3>ContextPack</h3>
<p>Team에게 건네줄 근거를 담은 꾸러미입니다. 안에 어떤 섹션이 얼마씩 들어갔는지,
무엇을 뺐는지가 같이 들어 있습니다.</p>

<h3>degraded와 omissions</h3>
<p><code>degraded</code>는 "이 꾸러미는 온전하지 않다"는 깃발이고,
<code>omissions</code>는 "무엇을 뺐는지"의 이름 목록입니다.
이 둘이 이 파트의 정직성을 담보합니다.</p>

<h3>RAG와 pgvector</h3>
<p>RAG는 모델이 외운 것에 기대지 않고 실제 문서를 찾아 근거로 쓰는 방식입니다.
문서를 조각으로 쪼개 숫자 벡터로 바꿔 두고, 질문도 벡터로 바꿔서 가까운 조각을 찾습니다.
그 벡터를 담는 곳이 pgvector인데, 별도 서버가 아니라 <b>PostgreSQL의 확장 기능</b>입니다.
MySQL이 아니라 PostgreSQL을 쓰는 이유가 이것입니다.</p>

<h2>코드는 이 순서로 읽습니다</h2>
<p class="lede">담는 그릇 → 자르는 규칙 → 찾아오는 곳 → 넣어 두는 곳 순입니다.</p>
""" + steps([
    ("app/core/contracts.py:94 <code>Evidence</code>, :122 <code>ContextPack</code>",
     "그릇의 모양부터 봅니다. <code>ContextPack</code>에 <code>degraded</code>와 "
     "<code>omissions</code> 필드가 있는 것을 확인하세요. 이 두 필드가 이 파트의 존재 이유입니다."),
    ("config/guardrails.yaml 의 <code>context</code> 절",
     "코드보다 이걸 먼저 봅니다. 총예산 12,000과 섹션별 배분, 그리고 <code>eviction_order</code>"
     "(뺄 순서)와 <code>never_evict</code>(절대 안 빼는 것)가 여기 있습니다. "
     "숫자가 코드에 없고 여기 있는 이유는 두 곳에 같은 숫자가 있으면 그 자체가 결함이기 때문입니다."),
    ("app/core/context.py:90 <code>ContextBroker</code>",
     "본체입니다. 각 섹션을 예산에 맞춰 자르고, 넘치면 정해진 순서로 빼고, 뺀 것을 기록합니다. "
     "<code>never_evict</code>에 걸린 것을 빼야 하는 상황이면 자르는 대신 예외를 냅니다."),
    ("app/core/context.py:48 <code>count_tokens()</code>",
     "글자 수가 아니라 실제 토큰을 셉니다. 한 줄짜리지만 이 프로젝트가 어림짐작을 "
     "안 한다는 증거입니다."),
    ("app/infrastructure/rag/retriever.py:30 <code>search_policy()</code>",
     "질문을 벡터로 바꿔 가까운 문서 조각을 찾아옵니다. 여기서 <code>tenant_id</code>와 "
     "지식 범위(scope) 조건이 같이 걸리는 것을 보세요 — 남의 테넌트 문서가 섞이면 안 됩니다."),
    ("app/infrastructure/db/migrations/001_schema.sql 의 knowledge 표 둘",
     "<code>knowledge_documents</code>(문서)와 <code>knowledge_chunks</code>(조각)입니다. "
     "조각마다 원본 문서와 위치를 남겨서 인용을 되짚을 수 있게 해 둔 것을 확인하세요. "
     "<code>vector(1536)</code>이라는 컬럼 타입도 봐 두세요."),
    ("scripts/check_corpus.py",
     "지식 문서가 제대로 들어갔는지 세는 게이트입니다. 지금 25문서 306조각입니다. "
     "&#39;문서에 적힌 숫자&#39;가 아니라 &#39;DB를 세어 나온 숫자&#39;라는 점이 중요합니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest tests/unit/core/test_context_budget.py -q
python -m pytest tests/integration/rag -q
python -m scripts.check_corpus</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0"><code>guardrails.yaml</code>의 <code>token_budget</code>을 12000에서
2000으로 줄이고 <code>test_context_budget.py</code>를 돌려 보세요. 무엇이 먼저 빠지는지,
<code>omissions</code>에 어떤 이름이 남는지 보면 이 파트가 하는 일이 눈에 들어옵니다.
확인했으면 반드시 되돌리세요.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>신호 없는 축소는 폴백입니다</b>
<p style="margin:6px 0 0">RAG가 죽었을 때 조용히 일반 지식으로 메우면 안 됩니다.
<code>degraded=true</code>와 <code>omissions</code>를 남겨야 폴백이 아닙니다.
이건 취향 문제가 아니라 <code>RULE.md</code> §3.2와 <code>CLAUDE.md</code> §0.1이
명시적으로 금지한 것입니다.</p>
</div>

<div class="note">
<b>임베딩 모델을 바꾸면 DDL도 바꿔야 합니다</b>
<p style="margin:6px 0 0">지금은 <code>text-embedding-3-small</code>이고 1536차원입니다.
DB 컬럼도 <code>vector(1536)</code>으로 박혀 있습니다. 모델을 바꾸면 차원이 달라지므로
<b>스키마와 이미 넣어 둔 306조각을 전부</b> 다시 만들어야 합니다. 모델만 바꾸면 조용히 안 맞습니다.</p>
</div>

<div class="note">
<b>지식 코퍼스는 한 번 통째로 다시 쓴 적이 있습니다</b>
<p style="margin:6px 0 0">구독·청구 도메인이던 것을 쇼핑몰 도메인으로 갈아 끼웠습니다.
그때 문서만 바꾸고 평가 데이터셋을 안 바꿔서 예전 측정 수치가 전부 무효가 됐습니다.
지식을 바꾸면 그것으로 잰 숫자도 같이 무효가 된다는 것을 기억하세요.</p>
</div>

<h2>다 읽었는지 확인하는 질문</h2>
<ol class="q">
<li>정책 문서가 예산을 넘게 검색됐습니다. 무엇이 먼저 빠집니까? 그 순서는 어디에 적혀 있습니까?</li>
<li><code>degraded=true</code>인 ContextPack을 받은 Team은 무엇을 다르게 해야 합니까?</li>
<li>왜 벡터 DB를 따로 세우지 않고 PostgreSQL 확장을 씁니까?</li>
<li>답변에 인용된 정책 문장이 어느 문서 몇 번째 조각에서 왔는지 어떻게 되짚습니까?</li>
</ol>

<h2>옆 파트와 맞닿는 곳</h2>
""" + table(["맞닿는 파트", "어디서 만나나"], [
    ["<a href='01_case_runtime.html'>1. Case 런타임</a>",
     "Controller가 Team을 부르기 직전에 Context Broker를 부릅니다"],
    ["<a href='03_agent_team.html'>3. Agent Team</a>",
     "Team이 <code>ContextPack</code>을 받아 <code>Evidence</code>를 만들어 돌려줍니다"],
    ["<a href='05_evaluation.html'>5. 평가 하네스</a>",
     "근거를 제대로 달았는지(grounding)를 거기서 채점합니다"],
])


# ══════════════════════════════════════════════════════ 5. 평가 하네스
P5 = """
<h2>이 파트가 하는 일</h2>
<p class="lede">"좋아졌다"를 느낌이 아니라 숫자로 말하게 만듭니다.</p>

<p>세 가지 방식을 같은 문제에 붙여 놓고 결과를 비교합니다. 그냥 LLM에 물어보는 A군,
검색을 붙인 B군, 우리가 만든 구조인 제안군입니다. 그리고 그 차이가 <b>우연이 아닌지</b>를
통계로 확인합니다.</p>

<p>이게 없으면 "체감상 나아진 것 같다"밖에 말할 수 없습니다. 심사에서든 고객 앞에서든
그건 근거가 아닙니다. 이 파트의 담당자에게 1순위는 화면이 아니라 이 증명입니다.</p>

<h2>먼저 알아야 할 말 다섯 개</h2>

<h3>golden과 holdout</h3>
<p>둘 다 정답이 붙어 있는 문제 묶음입니다. golden 60건은 <b>보면서 고쳐도 되는</b> 문제집이고,
holdout 20건은 <b>절대 보고 고치면 안 되는</b> 문제집입니다. holdout을 보고 프롬프트를
손보는 순간 그건 더 이상 holdout이 아니라 두 번째 golden입니다.</p>

<h3>arm (군)</h3>
<p>비교하는 방식 하나하나를 부르는 말입니다. A, B, Proposed 셋이 있습니다.
<b>run 단위로만 비교합니다.</b> arm이나 데이터셋이나 실행 방식이 다르면 평균을 견줄 수 없습니다.</p>

<h3>bootstrap 95% 신뢰구간</h3>
<p>같은 결과를 수천 번 다시 뽑아 보면서 "이 차이가 어느 범위 안에 있나"를 재는 방법입니다.
평균만 말하면 그 숫자가 얼마나 흔들리는지 알 수 없어서 반드시 같이 냅니다.</p>

<h3>McNemar 검정</h3>
<p>같은 문제를 두 방식에 똑같이 풀렸을 때, "A는 틀리고 B는 맞은 문제"와
"A는 맞고 B는 틀린 문제"의 개수를 비교하는 검정입니다. 짝지어진 비교라 표본이 적어도 쓸 수 있습니다.</p>

<h3>judge와 rubric</h3>
<p>답변의 품질을 LLM에게 채점시키는 것을 judge라고 하고, 그 채점 기준표가 rubric입니다.
judge가 사람과 얼마나 맞는지는 <b>따로 확인해야</b> 합니다. 그게 확인되기 전의 judge 점수는
그냥 또 하나의 LLM 출력일 뿐입니다.</p>

<h2>코드는 이 순서로 읽습니다</h2>
<p class="lede">데이터 한 줄 → 실행기 → 채점 → 통계 순입니다. 통계부터 보면 뭘 재는지 모릅니다.</p>
""" + steps([
    ("eval/datasets/golden.jsonl 의 첫 줄 하나",
     "제일 먼저 할 일입니다. 한 줄만 열어서 무슨 필드가 있는지 보세요. "
     "입력이 무엇이고 정답이 무엇인지 모르면 나머지가 다 추상적입니다."),
    ("eval/runners/common.py",
     "세 군이 공유하는 실행부입니다. :141 <code>run_config()</code>가 실행 조건"
     "(모델, temperature, seed, 프롬프트 버전)을 고정하는 자리입니다. "
     "이 값들이 안 고정되면 재현이 안 돼서 비교 자체가 무의미해집니다."),
    ("eval/runners/baseline_a.py → baseline_b.py → proposed.py",
     "이 순서로 셋을 나란히 읽으세요. 세 파일의 <b>차이</b>가 곧 이 프로젝트가 "
     "무엇을 더 했다고 주장하는지입니다."),
    ("eval/judge/rubric.json",
     "무엇을 몇 점 만점으로 채점하는지의 기준표입니다. 코드가 아니라 데이터입니다."),
    ("eval/check_judge.py",
     "근거 없이 점수를 받은 행이 있는지 세는 검사기입니다. 하나라도 있으면 종료코드 1을 냅니다. "
     "&#39;채점자를 채점하는&#39; 코드라 짧지만 중요합니다."),
    ("eval/stats/make_pairs.py → bootstrap.py → mcnemar.py",
     "짝을 만들고, 신뢰구간을 내고, 검정합니다. 이 셋은 통계 코드라 짧습니다. "
     "무엇을 입력으로 받는지만 보면 충분합니다."),
    ("eval/defense_metrics.py 와 eval/datasets/attack_fixtures.jsonl",
     "일부러 이상한 입력을 넣었을 때 막아 내는지를 재는 부분입니다. "
     "품질 지표와 안전 지표는 따로 잰다는 것을 확인하세요."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest eval/tests -q
python -m pytest tests/unit/eval -q
python -m scripts.verify_eval_datasets</pre>

<p>실제 평가를 돌리는 명령은 이렇습니다. LLM을 실제로 부르므로 비용이 듭니다.
처음에는 <code>--repeats 1</code>로 작게 돌려 보세요.</p>
<pre>python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl</pre>

<h2>함정</h2>

<div class="note">
<b>지금 채점기에 결함이 있습니다 (미해결)</b>
<p style="margin:6px 0 0">A군 정확도가 0.0%로 나온 적이 있는데 모델 문제가 아니었습니다.
채점 코드가 &#39;승인 대기&#39;라는 정상적인 결과를 실패로 세고, 성공 판정을 뒤에서
덮어쓰고 있었습니다. 기록은 <code>program/research/_평가harness_결함_2026-08-29.md</code>에
있고, 수정은 담당자에게 지시서로 넘겨 둔 상태입니다.
<b>평가 수치를 보기 전에 이 문서를 먼저 읽으세요.</b></p>
</div>

<div class="note">
<b>지금 저장소에 있는 옛 수치는 무효입니다</b>
<p style="margin:6px 0 0">A 0/180, B 6/180, Proposed 40/180 같은 숫자가 문서에 남아 있는데,
이건 지식 코퍼스가 구독·청구 도메인이던 시절에 잰 값입니다. 쇼핑몰 도메인으로
갈아 끼운 뒤 재측정하지 않았습니다. 참고용으로만 두고 근거로 쓰지 마세요.</p>
</div>

<div class="note">
<b>holdout 20건은 건드리지 않습니다</b>
<p style="margin:6px 0 0">보고 프롬프트를 고치는 순간 holdout이 아니게 됩니다.
표본이 작아서 유혹이 크지만, 한 번 만지면 되돌릴 방법이 없습니다.</p>
</div>

<div class="note">
<b>분모를 같이 적습니다</b>
<p style="margin:6px 0 0">"정확도 0.85"는 이 저장소에서 금지입니다.
"intent accuracy 0.85 (51/60, golden v1, seed=7, 3회 중 1회차)"로 적습니다.
분모와 실행 조건이 빠진 숫자는 리포트에 싣지 않습니다.</p>
</div>

<h2>다 읽었는지 확인하는 질문</h2>
<ol class="q">
<li>제안군이 B군보다 평균 5%p 높게 나왔습니다. 이걸로 "좋아졌다"고 말할 수 있습니까? 무엇이 더 필요합니까?</li>
<li>golden으로 프롬프트를 손봤습니다. 이제 holdout으로 재도 됩니까? 몇 번까지 됩니까?</li>
<li>judge가 준 grounding 점수 3.98을 근거로 쓰려면 무엇을 먼저 확인해야 합니까?</li>
<li>같은 명령을 내일 다시 돌렸을 때 같은 숫자가 나오게 하려면 무엇이 고정돼야 합니까?</li>
</ol>

<h2>옆 파트와 맞닿는 곳</h2>
""" + table(["맞닿는 파트", "어디서 만나나"], [
    ["<a href='03_agent_team.html'>3. Agent Team</a>",
     "평가 대상이 Team의 판단입니다. Team이 바뀌면 다시 재야 합니다"],
    ["<a href='04_context_rag.html'>4. 근거와 RAG</a>",
     "grounding 점수가 근거를 제대로 달았는지를 잽니다"],
    ["<a href='06_composition_ops.html'>6. 조립과 운영</a>",
     "평가 리포트 목록을 운영 콘솔에서 봅니다. run 단위 비교 경고도 거기 붙어 있습니다"],
])


# ══════════════════════════════════════════════════════ 6. 조립과 운영
P6 = """
<h2>이 파트가 하는 일</h2>
<p class="lede">무엇을 켜고 무엇을 끌지가 선언 한 파일에서 정해지고, 그 결과를 사람이 화면으로 봅니다.</p>

<p>이 프로젝트가 파는 것은 완성된 고객센터가 아니라 <b>고객 응대를 구성하는 플랫폼</b>입니다.
그래서 "무엇을 갈아 끼울 수 있는가"가 곧 제품입니다. 그 갈아 끼우는 일이
<code>config/project.yaml</code> 한 파일에서 일어나고, 그 파일을 화면에서 고치는 것이 Composer입니다.</p>

<p>그리고 굴러가는 것을 보는 화면이 운영 콘솔입니다. 판정, 평가, 승인 대기, 이상 신호를 봅니다.</p>

<h2>먼저 알아야 할 구분 네 개</h2>
<p class="lede">이 네 가지를 섞으면 Composer 화면이 이해가 안 됩니다.</p>

""" + table(["말", "뜻", "화면에서"], [
    ["<b>컴포넌트</b>", "빼면 시스템이 성립하지 않는 것. Case 생명주기, 계약 모델, Registry 등 9개",
     "잠겨 있습니다. 못 끕니다"],
    ["<b>모듈</b>", "켜고 꺼도 나머지가 도는 것. 지금 6개", "토글로 켜고 끕니다"],
    ["<b>Port</b>", "같은 자리에 다른 구현을 끼우는 지점", "구현을 고릅니다"],
    ["<b>인스턴스</b>", "개수가 늘고 줄 수 있는 것. Team이 유일합니다", "추가하고 뺍니다"],
]) + """
<h3>revision</h3>
<p>지금 선언이 몇 번째 판인지를 나타내는 값입니다. 고치려는 사람이 "내가 읽은 판은 이거였다"를
같이 보내고, 그 사이에 다른 사람이 먼저 고쳤으면 거부됩니다. Case의 CAS와 같은 원리입니다.</p>

<h2>코드는 이 순서로 읽습니다</h2>
<p class="lede">선언 파일 → 읽는 코드 → 조립하는 코드 → 고치는 API → 보는 화면 순입니다.</p>
""" + steps([
    ("config/project.yaml",
     "제일 먼저 이 파일을 통째로 읽으세요. 40줄이 안 됩니다. "
     "모듈 6개, Port 3개, Team 6개가 전부 여기 선언돼 있습니다. "
     "<b>이 파일이 이 파트의 주인공입니다.</b>"),
    ("app/core/project_config.py:78 <code>module_enabled()</code>, :84 <code>require_module()</code>",
     "선언을 읽고 &#39;이거 켜져 있나&#39;를 묻는 두 함수입니다. "
     "<code>require_module()</code>은 꺼져 있으면 예외를 냅니다 — 조용히 넘어가지 않는 게 핵심입니다."),
    ("app/composition.py 의 <code>build_</code> 로 시작하는 함수들",
     "조립 경계입니다. <code>build_registry</code>, <code>build_controller</code>, "
     "<code>build_graph_store</code>, <code>build_classifier</code>, <code>build_broker</code>. "
     "Team을 하드코딩 import하지 않고 선언에 적힌 경로를 <code>importlib</code>로 불러오는 것을 보세요."),
    ("app/application/composer_service.py",
     "선언을 고치는 업무 로직입니다. <code>read_current</code> → <code>validate_candidate</code> → "
     "<code>apply_candidate</code> 순서로 읽으면 됩니다. <code>toggle_target</code>은 "
     "&#39;하나만 켜고 끄기&#39;의 지름길입니다."),
    ("app/presentation/api/composer.py",
     "그 로직을 밖에 여는 API입니다. <code>/current</code>, <code>/validate</code>, "
     "<code>/apply</code>, <code>/toggle</code> 네 개뿐입니다. "
     "<code>apply</code>가 <code>reason</code>(사유)을 필수로 받는 것을 확인하세요 — 감사 기록의 근거입니다."),
    ("app/presentation/ui/routes.py",
     "운영 콘솔 본체입니다. 542줄로 저장소에서 제일 큽니다. "
     "<code>_admin_snapshot()</code>부터 보세요 — 지금 무엇으로 조립돼 있는지를 화면에 뿌리는 함수입니다."),
    ("app/introspection/contract.py",
     "밖에서 &#39;너 지금 어떻게 조립돼 있냐&#39;고 물었을 때 답하는 계약입니다. "
     "별도 프로그램인 <code>final_project_ui</code>가 이걸 읽습니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m scripts.verify_module_toggles
python -m pytest tests/contract/test_module_toggles.py -q
python -m pytest tests/unit/test_project_composition.py -q</pre>

<p>화면은 직접 띄워서 봐야 합니다. 이 저장소 규칙(<code>CLAUDE.md</code> §4)이
"백엔드 테스트 통과만으로 구현 완료라 하지 않는다"고 못박고 있습니다.</p>
<pre>python -m uvicorn app.presentation.api.app:app --port 8042</pre>
<p><code>http://127.0.0.1:8042/ui/admin</code>을 열면 지금 조립 상태가 그대로 보입니다.</p>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0"><code>project.yaml</code>에서 <code>graph_store</code>를
<code>false</code>로 바꾸고 서버를 <b>다시 띄운</b> 다음 <code>/ui/admin</code>을 보세요.
Ports 표의 GraphStorePort 줄이 <code>SqlGraphAdapter</code>에서
<code>모듈 꺼짐 (graph_store)</code>으로 바뀝니다. 확인했으면 되돌리세요.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>조립은 기동할 때 딱 한 번 일어납니다</b>
<p style="margin:6px 0 0">선언을 고쳐도 이미 떠 있는 서버는 안 바뀝니다. 재기동해야 합니다.
카탈로그의 모든 항목에 <code>requires_restart: true</code>가 붙어 있는 이유입니다.
"고쳤는데 왜 안 바뀌지"의 90%가 이겁니다.</p>
</div>

<div class="note">
<b>--reload 자식 프로세스가 옛 코드를 서빙합니다</b>
<p style="margin:6px 0 0">uvicorn을 <code>--reload</code>로 띄우면 자식 프로세스가 남아서
고친 코드가 반영 안 된 것처럼 보일 때가 있습니다. 실제로 여기에 한참을 쓴 적이 있습니다.
선언을 바꿔 가며 확인할 때는 <code>--reload</code> 없이 띄우세요.</p>
</div>

<div class="note">
<b>voc 모듈은 끌 수 없습니다</b>
<p style="margin:6px 0 0">2026-08-30 확정입니다. 끄면 앱이 아예 안 뜹니다. 인라인 분류가
Case 생성 경로에 붙어 있고, 그 분류는 선택 기능이 아니기 때문입니다.
계약 문서 <code>docs/handoff/08_모듈_컴포넌트_목록.md</code> §2에 "★끌 수 없다"로 표시돼 있습니다.</p>
</div>

<div class="note">
<b>모듈을 새로 추가하면 게이트도 같이 답니다</b>
<p style="margin:6px 0 0">이름만 늘리고 검사를 안 달면 토글이 아무것도 안 하는 상태가
조용히 만들어집니다. <code>mcp</code>와 <code>voc</code>에서 실제로 일어났던 일입니다.
지금은 <code>tests/contract/test_module_toggles.py</code>가 선언된 모듈 전부에
게이트가 있는지 소스를 훑어 확인합니다.</p>
</div>

<div class="note">
<b>Composer 화면은 이 저장소에 없습니다</b>
<p style="margin:6px 0 0"><code>/ui/composer</code>는 2026-08-18에 삭제됐습니다.
인증이 전혀 없는 채로 고객이 접근할 수 있는 앱에 물려 있었기 때문입니다.
같은 기능은 별도 프로그램 <code>final_project_ui</code>가 인증된 <code>/composer/*</code>
API로만 제공합니다. 이 저장소에는 <b>API 쪽만</b> 있습니다.</p>
</div>

<h2>다 읽었는지 확인하는 질문</h2>
<ol class="q">
<li>Team을 하나 추가할 때 Python 코드를 몇 파일 고쳐야 합니까?</li>
<li>두 사람이 동시에 선언을 고치면 무슨 일이 일어납니까?</li>
<li>선언을 고쳤는데 동작이 안 바뀝니다. 제일 먼저 무엇을 의심합니까?</li>
<li><code>ports.graph_store</code>를 <code>neo4j</code>로 바꾸면 어떻게 됩니까? 왜 그렇게 만들었습니까?</li>
</ol>

<h2>옆 파트와 맞닿는 곳</h2>
""" + table(["맞닿는 파트", "어디서 만나나"], [
    ["<a href='01_case_runtime.html'>1. Case 런타임</a>",
     "<code>build_registry</code>와 <code>build_controller</code>가 그쪽 물건을 조립합니다"],
    ["<a href='02_access_action.html'>2. 진입과 실행</a>",
     "승인 대기 화면과 감사 기록 화면이 여기 있습니다"],
    ["<a href='05_evaluation.html'>5. 평가 하네스</a>",
     "평가 리포트 목록을 운영 콘솔이 읽어 보여 줍니다"],
])


# ══════════════════════════════════════════════════════ 출력
PAGES = [
    (PARTS[0][0], PARTS[0][1], PARTS[0][2], "A-COP 학습 가이드 · 파트 1 · 코어 1",
     "문의 하나를 상태를 가진 업무 단위로 만들고, 어느 팀에 줄지 정하고, 기다렸다 재개하는 자리입니다.",
     "담당 최연우 · 읽는 데 걸리는 시간 대략 2시간 · 코드 약 900줄", P1),
    (PARTS[1][0], PARTS[1][1], PARTS[1][2], "A-COP 학습 가이드 · 파트 2 · 코어 2",
     "밖에서 들어오는 문(REST · MCP · A2A)이고, 되돌릴 수 없는 일을 실제로 실행하는 마지막 관문입니다.",
     "담당 정세환 · 읽는 데 걸리는 시간 대략 2시간 · 코드 약 700줄", P2),
    (PARTS[2][0], PARTS[2][1], PARTS[2][2], "A-COP 학습 가이드 · 파트 3 · 모델",
     "실제 업무 판단을 하는 자리입니다. 그리고 실행은 하지 않고 제안만 돌려줍니다.",
     "담당 송채영(총괄) · 김지혜 · 서유현 · 읽는 데 걸리는 시간 대략 3시간 · Team 6개", P3),
    (PARTS[3][0], PARTS[3][1], PARTS[3][2], "A-COP 학습 가이드 · 파트 4 · 근거 조합",
     "Team에게 줄 근거를 12,000 토큰 예산 안에서 고르고 자릅니다. 자르면 잘랐다고 적습니다.",
     "담당 모델 3인 공동 · 읽는 데 걸리는 시간 대략 2시간 · 코드 약 350줄", P4),
    (PARTS[4][0], PARTS[4][1], PARTS[4][2], "A-COP 학습 가이드 · 파트 5 · 검증",
     "좋아졌다를 느낌이 아니라 숫자로 말하게 만듭니다. 3군 비교와 통계 검정입니다.",
     "담당 최상욱 · 읽는 데 걸리는 시간 대략 3시간 · eval/ 폴더 전체", P5),
    (PARTS[5][0], PARTS[5][1], PARTS[5][2], "A-COP 학습 가이드 · 파트 6 · 조립과 프론트",
     "무엇을 켜고 끌지가 선언 한 파일에서 정해지고, 그 결과를 사람이 화면으로 봅니다.",
     "담당 최상욱 · 읽는 데 걸리는 시간 대략 2시간 · 시작점은 config/project.yaml", P6),
]

for filename, title, accent, kicker, sub, who, body in PAGES:
    out = os.path.join(HERE, filename)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page(filename, title, accent, kicker, sub, who, body))
    print("  %-26s %6d bytes" % (filename, os.path.getsize(out)))
print("\n%d장 생성: %s" % (len(PAGES), HERE))
