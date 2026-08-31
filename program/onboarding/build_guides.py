# -*- coding: utf-8 -*-
"""A-COP 담당자별 학습 가이드 6장을 만든다.

    python program/onboarding/build_guides.py

★파일마다 CSS 를 안에 박는다. 공용 css 파일로 빼면 링크가 깨진 채로 한 장만
  퍼갔을 때 글자만 남는다. 학습 자료는 한 장씩 따로 돌아다니는 물건이다.

★파트는 팀의 실제 담당 구분 그대로다. 코어 2명, Agent Team Module 3명, 검증·프론트 1명.
  근거는 `program/plan/A-COP_구현계획서_v8.md` §16 과
  `program/plan/A-COP_스프린트_에픽_설계.md` 의 담당표다.
  ★2026-08-31 1차본은 내가 임의로 자른 축(런타임/진입/Team/RAG/평가/조립)이라 버렸다.
    담당자가 자기 장을 펴서 자기 일을 못 찾으면 학습 자료가 아니다.
    1차본은 `_backup_2026-08-31/` 에 있다.

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
.scope{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:18px 0}
.scope__col{border:1px solid var(--line);border-radius:11px;padding:13px 17px;background:var(--surface)}
.scope__col h4{margin:0 0 7px;font-size:14px}
.scope__col ul{margin:0;padding-left:19px;font-size:14.5px}
.scope__col li{margin:4px 0}
.scope__col--yes{border-left:4px solid var(--accent)}
.scope__col--yes h4{color:var(--accent)}
.scope__col--no{opacity:.82}
.scope__col--no h4{color:var(--dim)}
nav.parts a em{font-style:normal;display:block;font-size:11px;opacity:.72;margin-top:-3px}
@media(max-width:640px){.scope{grid-template-columns:1fr}}
@media(max-width:600px){h1{font-size:23px}body{font-size:15px}.steps>li{padding-left:50px}
.flow>li{padding-left:34px}}
"""


PARTS = [
    ("01_core1_case_runtime.html", "코어 1", "최연우", "#2f5bd8"),
    ("02_core2_access_action.html", "코어 2", "정세환", "#b8442f"),
    ("03_team_voc_response.html", "VOC · 응대", "송채영", "#0d7a4d"),
    ("04_team_order_payment.html", "주문 · 결제", "김지혜", "#0f7b8a"),
    ("05_team_fulfillment_return.html", "배송 · 반품", "서유현", "#6b3fa0"),
    ("06_eval_frontend.html", "검증 · 프론트", "최상욱", "#a8720c"),
]


def nav(current):
    links = "".join(
        '<a href="%s"%s>%d. %s<em>%s</em></a>'
        % (f, ' aria-current="page"' if f == current else "", i, t, who)
        for i, (f, t, who, _) in enumerate(PARTS, 1))
    return '<nav class="parts"><div class="wrap">%s</div></nav>' % links


def steps(rows):
    items = "".join('<li><span class="path">%s</span><span class="why">%s</span></li>'
                    % (p, w) for p, w in rows)
    return '<ol class="steps">%s</ol>' % items


def table(head, rows):
    th = "".join("<th>%s</th>" % h for h in head)
    tr = "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r) for r in rows)
    return ('<div class="tblwrap"><table><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table></div>' % (th, tr))


def scope(mine, not_mine):
    """소유 경계. 구현계획서 §16 이 담당하지 않는 것까지 적어 둔 이유가 있다 —
    경계를 안 적으면 남의 파일을 고치고 그쪽 작업을 덮는다."""
    a = "".join("<li>%s</li>" % x for x in mine)
    b = "".join("<li>%s</li>" % x for x in not_mine)
    return ('<div class="scope"><div class="scope__col scope__col--yes">'
            '<h4>내가 소유합니다</h4><ul>%s</ul></div>'
            '<div class="scope__col scope__col--no">'
            '<h4>내가 소유하지 않습니다</h4><ul>%s</ul></div></div>' % (a, b))


def page(filename, title, who, accent, kicker, sub, meta, body):
    return """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s · %s · A-COP 학습 가이드</title>
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
A-COP 담당자별 학습 가이드 · 기준 저장소 <code>final_project_cs</code> · 확인일 2026-08-31<br>
담당 구분의 근거는 <code>A-COP_구현계획서_v8.md</code> §16 과 <code>A-COP_스프린트_에픽_설계.md</code> 입니다.<br>
줄번호는 코드가 바뀌면 밀립니다. 안 맞으면 함께 적힌 이름으로 찾으세요.
이 파일은 <code>program/onboarding/build_guides.py</code> 가 만듭니다.
</div>
</main>
</body>
</html>
""" % (who, title, accent, CSS, kicker, title, sub, meta, nav(filename), body)


# ═══════════════════════════════════════════ Agent Team Module 3인 공통 기초
# ★같은 글을 세 장에 넣는다. 세 사람이 서로 다른 장을 펴 놓고 같은 계약을 봐야 하는데,
#   "3번 장 가서 읽어라"로 넘기면 자기 장만 열어 둔 사람이 그냥 건너뛴다.
TEAM_BASE = """
<h2>Agent Team 세 사람의 공통 기초</h2>
<p class="lede">담당 Team이 달라도 지켜야 할 계약은 같습니다. 이 절은 세 장에 똑같이 들어 있습니다.</p>

<div class="note">
<b>가장 중요한 규칙 하나</b>
<p style="margin:6px 0 0">Team은 <b>부수효과를 실행하지 않습니다.</b> 환불이 맞다고 100퍼센트
확신해도 환불을 하는 게 아니라 "환불하자"는 제안(<code>ActionProposal</code>)을 돌려줍니다.
실제 실행은 <a href="02_core2_access_action.html">코어 2</a>의 승인 경로에서 일어납니다.
이 경계를 넘는 코드는 리뷰에서 되돌려집니다.</p>
</div>

<h3>Team 하나는 이렇게 생겼습니다</h3>
<p>상속할 부모 클래스가 없습니다. <code>manifest</code> 속성과 <code>execute()</code> 메서드
두 개만 있으면 Team입니다. Core는 그 둘만 씁니다.</p>
<pre>class 내Team:
    manifest = TeamManifest(
        team_id="...",              # config/project.yaml 의 team_id 와 같아야 한다
        capabilities=[...],         # 내가 할 수 있는 일. 다른 팀과 겹치면 조립이 실패한다
        allowed_tools=[...],        # 내가 부를 수 있는 도구. 목록 밖은 도구함이 거부한다
        knowledge_scope=[...],      # 내가 읽을 수 있는 지식 범위
    )
    async def execute(self, task: TeamTask) -> TeamResult: ...</pre>

<h3>계약 네 개를 먼저 읽습니다</h3>
""" + steps([
    ("app/core/contracts.py:303 <code>TeamManifest</code>, :321 <code>TeamModule</code>",
     "자기소개서의 모양입니다. Registry는 이것만 보고 라우팅합니다."),
    ("app/core/contracts.py:165 <code>TeamTask</code>",
     "들어오는 것입니다. <code>context</code>(근거 꾸러미), <code>allowed_tools</code>, "
     "<code>deadline_at</code>, <code>resume</code>가 핵심 필드입니다."),
    ("app/core/contracts.py:223 <code>TeamResult</code>, :201 <code>ActionProposal</code>",
     "나가는 것입니다. <code>next_action</code>이 &#39;승인 받아라&#39;·&#39;고객에게 물어라&#39;·"
     "&#39;사람에게 넘겨라&#39;를 전부 표현합니다."),
    ("app/core/contracts.py:94 <code>Evidence</code>",
     "모든 주장에 붙는 출처입니다. <code>source_type</code>·<code>source_id</code>·"
     "<code>observed_at</code>. 근거 없는 문장은 답변에 넣지 않습니다."),
    ("app/tools/read_tools.py:38 <code>ReadToolbox</code>, :146 <code>call()</code>",
     "DB를 읽는 유일한 통로입니다. <code>call()</code>이 <code>allowed_tools</code>를 검사하고 "
     "같은 도구를 반복해 부르는 루프도 막습니다. 직접 SQL을 쓰면 안 됩니다."),
]) + """
<h3>ContextPack — 받은 근거가 온전하지 않을 수 있습니다</h3>
<p><code>task.context</code>에 근거가 실려 옵니다. 그런데 12,000 토큰 예산을 넘으면
일부가 잘려 나갑니다. 그때 <code>degraded=true</code>가 붙고 <code>omissions</code>에
무엇을 뺐는지가 적힙니다.</p>
<p><b>이 깃발을 무시하면 안 됩니다.</b> 근거가 잘린 채로 확정 답변을 만들면
그게 바로 이 프로젝트가 막으려는 상황입니다. 정책 근거를 못 대면
<code>escalate</code>나 <code>wait_for_input</code>이 정답입니다.</p>

<h3>세 사람의 Team 배분</h3>
""" + table(["담당", "Team", "파일"], [
    ["송채영 (총괄)", "VOC &amp; Store Manager · Response Generation &amp; Review",
     "<code>voc_store_manager.py</code>, <code>response_review.py</code>"],
    ["김지혜", "Procurement + Order &amp; Payment",
     "<code>procurement_order_payment.py</code>"],
    ["서유현", "Fulfillment &amp; Logistics · Return &amp; Refund",
     "<code>fulfillment_logistics.py</code>, <code>return_refund.py</code>"],
    ["셋이 함께 (총괄 송채영)", "Catalog &amp; Verification (A2A Remote)",
     "<code>catalog_verification.py</code>"],
]) + """
<p>Core나 검증 쪽에서 Agent Team Module에 연락할 일이 있으면 송채영에게 합니다.
셋이 각자 받으면 같은 결정을 세 번 하게 됩니다.</p>
"""

TEAM_TRAPS = """
<div class="note">
<b>이 파트에서 실제로 났던 제일 큰 결함</b>
<p style="margin:6px 0 0"><code>feedback.py</code>의 <code>INTENTS</code>가 옛 구독·청구
도메인 어휘(<code>billing</code>, <code>technical</code>)로 남아 있었는데, 이 함수가 운영
API의 기본 분류기였습니다. 쇼핑몰 문의는 <b>전부 분류 실패로 떨어졌을</b> 상태였습니다.
지금은 <code>order</code>, <code>shipping</code>, <code>return</code>, <code>exchange</code>,
<code>other</code>입니다.</p>
<p style="margin:8px 0 0">재발 방지로 <b>INTENTS가 모든 Team의 <code>accepted_case_types</code>를
덮는지</b> 검사하는 테스트가 있습니다. Team을 새로 만들면서 새 유형을 받겠다고 선언하면
이 테스트가 먼저 붉어집니다 — <code>tests/unit/voc/test_feedback_intent_alignment.py</code>.</p>
</div>

<div class="note">
<b>프롬프트를 쓰면 DB에 등록해야 합니다</b>
<p style="margin:6px 0 0">프롬프트 파일만 만들어 두고 등록을 안 하면, 감사 기록 경로로 불릴 때마다
<code>no active prompt registered</code>로 죽습니다. Response Review 팀이 실제로 이 상태로
한동안 있었습니다. <code>python -m scripts.register_prompts</code>를 잊지 마세요.</p>
</div>

<div class="note">
<b>Core를 import하면 테스트가 붉어집니다</b>
<p style="margin:6px 0 0">Team은 <code>app/core/contracts.py</code>와 <code>app/tools/</code>만
씁니다. Controller나 transition을 직접 부르면 <code>tests/contract/test_core_isolation.py</code>가
import 검사로 잡습니다. 의도된 것이니 놀라지 마세요.</p>
</div>
"""


# ══════════════════════════════════════════ 1. 코어 1 · 최연우
P1 = """
<h2>맡은 자리</h2>
<p class="lede">문의 하나를 접수부터 종료까지 책임지는 실행 축입니다.</p>

<p>고객 문의를 <b>Case</b>라는 상태를 가진 업무 단위로 바꾸고, 그것이 어떤 상태를 지나는지
관리합니다. 어느 Team에게 일을 줄지 정하고, 기다려야 하면 멈췄다가 조건이 갖춰지면
다시 이어 실행합니다.</p>

<p>이 자리가 없으면 문의는 단발 질의응답이 됩니다. "고객 답을 기다리는 중",
"사람 결재를 기다리는 중" 같은 상태를 표현할 수 없어서 며칠 걸리는 일은 아예 다룰 수 없습니다.
경쟁 제품과 갈리는 지점이 정확히 여기입니다.</p>

<h2>소유 경계</h2>
<p class="lede">구현계획서 §16이 담당하지 않는 것까지 적어 둔 이유가 있습니다. 경계를 모르면 남의 작업을 덮습니다.</p>
""" + scope(
    ["Case와 생명주기, 상태 전이표",
     "Shared State와 CAS(비교 후 교체)",
     "Agentic Controller와 최상위 LangGraph",
     "Team Registry와 <code>TeamExecutorPort</code>",
     "Message Broker 정책과 Outbox"],
    ["외부 인증과 권한 검사 (코어 2)",
     "Tool 실행과 승인 (코어 2)",
     "Team 내부 로직과 프롬프트 (모델 3인)"]) + """

<h2>먼저 알아야 할 말 세 개</h2>

<h3>Case</h3>
<p>문의 하나입니다. 상태 12개 중 하나를 가지고 있습니다. <code>new</code>로 시작해
<code>resolved</code>나 <code>escalated</code>로 끝나는데, 중간에 <code>waiting_approval</code>처럼
<b>멈춰 있는 상태</b>가 있는 것이 핵심입니다.</p>

<h3>이벤트 소싱</h3>
<p>무슨 일이 있었는지를 <code>case_events</code>에 <b>추가만</b> 하고 고치지 않습니다.
지금 상태를 담은 <code>customer_cases</code>는 그 이벤트를 순서대로 적용한 결과일 뿐입니다.
그래서 나중에 이벤트만 재생하면 그때 무슨 일이 있었는지 되짚을 수 있습니다.</p>

<h3>CAS (비교 후 교체)</h3>
<p>Compare-And-Swap입니다. 쓸 때 "내가 읽었던 버전이 아직 그대로냐"를 같이 확인하고
다르면 거부합니다. 두 사람이 같은 Case를 동시에 고쳐도 나중 쓰기가 앞 쓰기를 조용히
덮지 않습니다.</p>

<h2>코드 읽는 순서</h2>
<p class="lede">어휘 → 규칙 → 실행 루프입니다. 반대로 읽으면 헤맵니다.</p>
""" + steps([
    ("app/core/contracts.py:53 <code>CaseStatus</code>, :68 <code>NextAction</code>",
     "어휘부터 외웁니다. 상태 12개와 다음 행동 7개가 이 프로젝트의 기본 단어입니다. "
     "어디를 가도 이 이름들이 나옵니다."),
    ("app/domain/events.py:16 <code>EventType</code>",
     "무슨 일이 일어날 수 있는지의 목록입니다. 상태가 명사라면 이건 동사입니다."),
    ("app/core/transition.py:116 <code>transition_case()</code>",
     "<b>상태를 바꾸는 유일한 문입니다.</b> 이 함수 하나만 제대로 읽으면 이 파트의 절반을 "
     "이해한 겁니다. 이벤트 기록·상태 갱신·발행할 메시지 적재가 한 트랜잭션으로 묶입니다."),
    ("app/core/transition.py:215 <code>replay_case()</code>",
     "이벤트만으로 상태를 다시 만듭니다. 왜 이벤트를 안 고치는지 여기서 납득이 됩니다."),
    ("app/core/registry.py:29 <code>TeamRegistry</code>",
     "&#39;이 문의는 어느 팀 일인가&#39;를 푸는 곳입니다. Team을 이름이 아니라 "
     "capability로 찾습니다. 같은 capability를 두 팀이 주장하면 조립 자체가 실패합니다."),
    ("app/application/controller.py:113 <code>run_case()</code>",
     "실행 루프의 본체입니다. 라우팅 → 근거 조합 → Team 실행 → 결과 반영이 한 함수에 있습니다. "
     ":146의 전체 시간 가드레일과 :157의 Team 제한 시간을 같이 보세요."),
    ("app/application/controller.py:291 <code>resume()</code>",
     "멈춰 있던 Case를 다시 돌리는 자리입니다. 재개 토큰을 검사하고, 만료됐으면 "
     "<code>WAIT_EXPIRED</code>를 남기고 사람에게 넘깁니다."),
    ("app/application/case_service.py:26 <code>CaseService</code>",
     "실행 시작·종료와 재개 토큰을 관리합니다. 같은 Case가 동시에 두 번 도는 것을 막습니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest tests/unit/core/test_case_reducer.py -q
python -m pytest tests/contract/test_case_state_table.py -q
python -m pytest tests/integration/controller -q</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0"><code>tests/contract/test_case_state_table.py</code>에서 전이표를 봅니다.
그다음 허용되지 않은 전이를 하나 골라 억지로 시켜 보세요. 어떤 예외가 어디서 나는지 보면
이 파트의 방어선 위치가 눈에 들어옵니다.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>app/core/case_runtime/ 폴더는 비어 있습니다</b>
<p style="margin:6px 0 0">폴더는 있는데 파일이 하나도 없습니다. <code>docs/handoff/07_모듈화_구조.md</code>가
제안한 구조만 만들어 두고 실제 코드는 <code>app/core/</code> 바로 아래 평평하게 있습니다.
여기를 뒤지다 헤매기 쉽습니다.</p>
</div>

<div class="note">
<b>customer_cases를 직접 UPDATE하지 않습니다</b>
<p style="margin:6px 0 0"><code>transition_case()</code>가 유일한 진입점입니다. 직접 UPDATE하면
이벤트가 안 남아 재생이 깨집니다. <code>CLAUDE.md</code> §0.3입니다.</p>
</div>

<div class="note">
<b>실제로 났던 결함</b>
<p style="margin:6px 0 0">Controller가 <code>resuming</code>에서 <code>resumed</code> 이벤트를
건너뛰고 바로 종료로 가려다 상태기계에 막힌 적이 있습니다. 기록은
<code>docs/reports/debugs/2026-08-12_2230_Controller가_resuming에서_resumed를_건너뛴다.md</code>입니다.
결함 리포트를 읽는 게 코드만 읽는 것보다 빠를 때가 많습니다.</p>
</div>

<h2>확인 질문</h2>
<ol class="q">
<li>고객이 추가 정보를 줘야 해서 사흘 멈춘 Case는 어떤 상태입니까? 다시 돌 때 어느 노드로 들어갑니까?</li>
<li>두 사람이 같은 Case를 동시에 승인하면 무슨 일이 일어납니까?</li>
<li><code>customer_cases</code> 한 행을 통째로 지웠습니다. 복구할 수 있습니까? 무엇으로?</li>
<li>Team을 하나 추가하면 이 파트 코드 중 무엇을 고쳐야 합니까?</li>
</ol>

<h2>옆 담당과 맞닿는 곳</h2>
""" + table(["담당", "어디서 만나나"], [
    ["<a href='02_core2_access_action.html'>정세환 · 코어 2</a>",
     "Case를 만드는 요청과 승인 요청이 거기서 들어옵니다. <code>transition_case()</code>를 부르는 쪽입니다"],
    ["<a href='03_team_voc_response.html'>송채영 외 2인 · Agent Team</a>",
     "Controller가 <code>TeamTask</code>를 만들어 넘기고 <code>TeamResult</code>를 받습니다. "
     "계약이 바뀌면 양쪽이 같이 바뀝니다"],
    ["<a href='06_eval_frontend.html'>최상욱 · 검증과 프론트</a>",
     "Case 상태와 이벤트를 화면에 뿌립니다. 조립도 그쪽 소유입니다"],
])


# ══════════════════════════════════════════ 2. 코어 2 · 정세환
P2 = """
<h2>맡은 자리</h2>
<p class="lede">밖에서 들어오는 문이고, 되돌릴 수 없는 일을 실제로 실행하는 마지막 관문입니다.</p>

<p>두 가지를 맡습니다. <b>진입</b>은 REST, 개인 AI가 붙는 MCP, 외부 에이전트가 붙는 A2A
세 갈래로 들어오는 요청을 받아 누가 무슨 권한으로 왔는지 확인하는 일입니다.
<b>실행</b>은 환불처럼 되돌릴 수 없는 일에 사람 승인을 받고, 같은 요청이 여러 번 와도
한 번만 처리하고, 무엇을 했는지 남기는 일입니다.</p>

<p>이 자리가 없으면 아무나 무슨 권한으로 들어왔는지 모르고, 네트워크가 한 번 끊겨
클라이언트가 재시도하면 환불이 두 번 나갑니다.</p>

<h2>소유 경계</h2>
""" + scope(
    ["Gateway와 REST/OpenAPI 표면",
     "MCP Server와 A2A Adapter",
     "Tool과 Action 실행 계층",
     "승인(approval)과 멱등성(idempotency)",
     "감사 로그(audit)와 외부 인증"],
    ["Case 라우팅 판단 (코어 1)",
     "상태 전이 규칙 (코어 1)",
     "Team 내부 로직 (모델 3인)"]) + """

<h2>먼저 알아야 할 말 세 개</h2>

<h3>scope</h3>
<p>API 키에 붙는 권한 이름입니다. <code>case:read</code>, <code>action:approve</code>처럼
생겼고 지금 10개입니다. 목록의 정본은 코드가 아니라 <code>config/guardrails.yaml</code>의
<code>security.scopes</code>입니다. 코드에 흩어 놓으면 어디가 진짜인지 몰라지기 때문입니다.</p>

<h3>멱등성</h3>
<p>같은 요청을 열 번 보내도 실제 부수효과는 한 번만 일어나는 성질입니다. 말로 하는 게 아니라
DB의 UNIQUE 제약으로 강제합니다. <code>action_requests.idempotency_key</code>가 그 자리입니다.</p>

<h3>승인 경계</h3>
<p>AI가 만든 것은 <b>제안</b>까지입니다. 돈이 나가거나 되돌릴 수 없는 일은 사람이 승인 버튼을
눌러야 실행됩니다. 이 프로젝트의 안전장치 중 제일 중요한 것이고, 그 경계가 이 파트에 있습니다.</p>

<h2>코드 읽는 순서</h2>
<p class="lede">들어오는 길 → 막는 장치 → 실행 직전 재검사 순입니다.</p>
""" + steps([
    ("app/presentation/security.py:15 <code>Principal</code>, :47 <code>require_scope()</code>",
     "요청 하나가 &#39;누구&#39;인지 담는 그릇과 권한을 요구하는 장치입니다. 50줄 남짓이라 금방 읽힙니다. "
     "<code>Principal</code> 안의 <code>tenant_id</code>가 이후 모든 조회 조건에 붙습니다."),
    ("app/presentation/api/app.py:14 <code>create_app()</code>",
     "라우터가 붙는 자리입니다. 이 앱에 무슨 표면이 열려 있는지 한눈에 보입니다. "
     "여기 없는 경로는 이 서버에 없는 겁니다."),
    ("app/presentation/api/cases.py:69 <code>create()</code>",
     "Case 생성 진입점입니다. 권한 확인 → 멱등성 조회 → Case 생성 → 인라인 분류 → "
     "Controller 호출이 한 함수 안에 순서대로 있습니다. 이 흐름을 외우면 편합니다."),
    ("app/core/idempotency.py:8 <code>idempotency_key()</code>",
     "8줄짜리 함수입니다. 무엇을 재료로 키를 만드는지 보세요 — 요청 ID뿐 아니라 "
     "업무 대상까지 넣습니다. 그래야 다른 요청 ID로 온 같은 환불도 걸립니다."),
    ("app/core/verification.py:114 <code>verify_proposal()</code>",
     "Team이 만든 제안의 식별자·금액·수량을 DB 사실과 대조합니다. 없는 주문번호나 틀린 금액을 "
     "여기서 잡습니다. 순수 함수라 DB 없이 테스트됩니다."),
    ("app/application/proposal_guard.py:70 <code>recheck_before_execution()</code>",
     "검증을 <b>두 번</b> 하는 이유가 여기 있습니다. 제안할 때 한 번, 실행 직전에 또 한 번. "
     "그 사이에 재고나 주문 상태가 바뀌었을 수 있기 때문입니다."),
    ("app/presentation/api/cases.py:146 <code>approve()</code>",
     "승인 진입점입니다. <code>action:approve</code> 권한을 요구하고, 재조회를 거쳐 실행합니다."),
    ("app/presentation/api/mcp.py + cases.py 의 <code>_mcp_</code> 함수 셋",
     "개인 AI에게 여는 tool 3종입니다. <code>mcp.py</code>는 20줄뿐이고 실제 일은 전부 "
     "<code>cases.py</code>에 위임합니다. <code>_mcp_principal()</code>이 세 tool의 공통 관문입니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest tests/security -q
python -m pytest tests/integration/api/test_recheck_before_execution.py -q
python -m pytest tests/integration/api/test_api_runtime.py -q</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0">같은 Case 생성 요청을 같은 <code>request_id</code>로 열 번 보내고
<code>action_requests</code> 표의 행 수를 세어 보세요. 1이어야 합니다.
이걸 확인하는 테스트가 이미 있으니 먼저 읽고 흉내 내면 됩니다.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>MCP는 읽기 전용입니다</b>
<p style="margin:6px 0 0"><code>open_support_case</code>라는 이름 때문에 쓰기처럼 보이지만
Case를 만들고 분류를 시작하는 데까지입니다. 결제·환불·구독 변경은 하지 않습니다.
쓰기는 REST와 승인 경로로만 갑니다.</p>
</div>

<div class="note">
<b>타임아웃을 성공으로 추정하지 않습니다</b>
<p style="margin:6px 0 0">결제사를 불렀는데 응답이 안 오면 <code>unknown</code>으로 남기고
자동 재실행하지 않습니다. 돈이 나갔는지 모르는 상태를 &#39;모른다&#39;라고 적는 겁니다.
운영 화면이 이 상태를 제일 센 위험색으로 칠하는 이유이기도 합니다.</p>
</div>

<div class="note">
<b>승인 큐에 유령 항목이 쌓인 적이 있습니다</b>
<p style="margin:6px 0 0">Case를 만들 때 남기는 멱등성 감사 기록 행의 상태를 기본값
(<code>proposed</code>)으로 뒀더니, <code>/ui/approvals</code> 대기 큐에 근거 없는 항목이
Case마다 하나씩 쌓였습니다. 지금은 종결 상태로 남깁니다. <code>cases.py</code>에 그 경위가
주석으로 붙어 있습니다.</p>
</div>

<div class="note">
<b>MCP 서버는 지금 아무 데서도 서빙되지 않습니다</b>
<p style="margin:6px 0 0"><code>FastMCP</code> 객체는 만들어지는데 그것을 실행하는 코드가
저장소에 없습니다(2026-08-31 확인). tool 정의와 권한 검사는 다 있으니, 실제로 열 때
그 진입점에 모듈 게이트를 다는 일이 남아 있습니다. <b>이 파트의 미완 항목입니다.</b></p>
</div>

<h2>확인 질문</h2>
<ol class="q">
<li>같은 환불 요청이 서로 다른 <code>request_id</code>로 두 번 들어오면 두 번 나갑니까?</li>
<li>제안 검증을 왜 두 번 합니까? 한 번으로 부족한 구체적 상황을 하나 말해 보세요.</li>
<li>scope를 하나 늘리려면 어느 파일을 고쳐야 합니까?</li>
<li>개인 AI가 환불을 실행하려면 무엇이 필요합니까?</li>
</ol>

<h2>옆 담당과 맞닿는 곳</h2>
""" + table(["담당", "어디서 만나나"], [
    ["<a href='01_core1_case_runtime.html'>최연우 · 코어 1</a>",
     "여기서 받은 요청이 <code>transition_case()</code>와 <code>Controller.run_case()</code>로 들어갑니다"],
    ["<a href='03_team_voc_response.html'>송채영 외 2인 · Agent Team</a>",
     "Team이 만든 <code>ActionProposal</code>을 여기서 검증하고 승인받아 실행합니다"],
    ["<a href='06_eval_frontend.html'>최상욱 · 검증과 프론트</a>",
     "승인 버튼이 있는 화면과 감사 기록 화면이 그쪽에 있습니다"],
])


# ══════════════════════════════════════════ 3. VOC · 응대 · 송채영
P3 = TEAM_BASE + """
<h2>내 Team 둘</h2>
<p class="lede">문의를 모아 보는 팀과, 답변 문장을 만들고 검토하는 팀입니다.</p>

<p>CS Pack의 고정 축 두 개를 맡습니다. 이번 기간에 확실히 여는 범위라
다른 Team보다 완성도 요구가 높습니다. 그리고 Agent Team Module 세 사람의 총괄이라,
Core나 검증 쪽에서 오는 연락을 받는 창구이기도 합니다.</p>

<h3>VOC &amp; Store Manager</h3>
<p>문의를 유형별로 모으고, 급증 신호가 있으면 알립니다. 개별 문의에 답하는 팀이 아니라
<b>전체를 보는</b> 팀입니다. 도구는 <code>read.policy</code> 하나만 쓰고 지식 범위는
주문·배송·반품·교환 넷입니다.</p>

<h3>Response Generation &amp; Review</h3>
<p>답변 문장을 만들고 톤을 검토합니다. 이 팀만 특별한 점이 둘 있습니다.
첫째, <b>도구를 안 쓰고 LLM만</b> 씁니다(<code>__init__</code>이 <code>llm</code>만 받습니다).
둘째, 만든 문장이 사실과 맞는지 <b>결정적으로</b> 한 번 더 검사합니다 —
LLM에게 검토를 시키는 것과 별개로 코드가 직접 대조합니다.</p>

<h2>코드 읽는 순서</h2>
<p class="lede">짧은 것부터 읽습니다. VOC 97줄, Response Review 154줄입니다.</p>
""" + steps([
    ("app/modules/customer_ops/voc_store_manager.py:13 <code>manifest</code>",
     "가장 짧은 Team입니다. manifest 선언 → <code>_evidence()</code>로 근거 만들기 → "
     "<code>execute()</code>에서 분기까지 한 팀의 전부가 97줄 안에 있습니다. "
     "<b>Team이 어떻게 생겼는지 보려면 이 파일 하나면 됩니다.</b>"),
    ("app/modules/customer_ops/response_review.py:19 <code>ResponseGenerationReviewTeam</code>",
     "두 번째로 읽습니다. :35 <code>__init__</code>이 <code>tools</code>를 안 받는 것을 "
     "먼저 확인하세요 — 이 팀은 DB를 안 읽고 받은 근거만 씁니다."),
    ("response_review.py:84 <code>_deterministic()</code>",
     "★이 파트에서 제일 중요한 함수입니다. LLM이 쓴 문장에서 주장을 뽑아 "
     "<code>Facts</code>와 코드로 대조합니다. LLM에게 &#39;네 답 검토해&#39;라고 시키는 것만으로는 "
     "부족하기 때문입니다. 검토자도 같은 모델이면 같은 착각을 합니다."),
    ("response_review.py:96 <code>_generate()</code>, :106 <code>execute()</code>",
     "생성하고, 검사하고, 실패하면 재시도하고, 그래도 안 되면 사람에게 넘기는 흐름입니다. "
     "<code>retry</code> 횟수가 어디서 오는지 따라가 보세요."),
    ("app/modules/customer_ops/response_review_policy.py",
     "톤 프로필과 검토 기준이 든 파일입니다. 코드와 정책을 분리해 둔 자리입니다."),
    ("prompts/response/generate.v2.md, review_tone.v1.md",
     "실제로 쓰는 프롬프트입니다. 버전이 파일명에 박혀 있고 DB에 등록해야 활성화됩니다."),
    ("app/modules/customer_ops/feedback.py:33 <code>INTENTS</code>, :86 <code>classify()</code>",
     "Team은 아니지만 VOC 소유입니다. 문의가 들어올 때 의도·이슈·감성을 한 번에 분류합니다. "
     "실패하면 Case가 사람에게 넘어갑니다."),
    ("app/application/feedback_job.py:30 <code>run_daily_feedback()</code>",
     "일일 집계 배치입니다. 급증 판정식(:25 <code>is_surge</code>)이 계획서 조문 그대로인지 "
     "확인하고 넘어가세요."),
    ("app/modules/customer_ops/catalog_verification.py",
     "셋이 함께 구현하고 총괄이 송채영입니다. A2A로 원격 위임되는 유일한 Team이라 "
     "나중에 볼 것이 더 있습니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest tests/unit/teams/test_voc_store_manager.py -q
python -m pytest tests/unit/teams/test_response_review.py tests/unit/teams/test_response_review_team.py -q
python -m pytest tests/unit/voc -q
python -m scripts.register_prompts</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0"><code>_deterministic()</code>에 일부러 틀린 주장이 든 문장을 넣어
보세요. 예를 들어 실제 주문 금액이 30,000원인데 "50,000원 환불" 문장을 만들어 넘기면
어떤 값이 돌아오는지. 이 함수가 무엇을 잡고 무엇을 못 잡는지가 곧 이 팀의 방어 범위입니다.</p>
</div>

<h2>함정</h2>
""" + TEAM_TRAPS + """
<div class="note">
<b>총괄이라 오는 연락이 있습니다</b>
<p style="margin:6px 0 0">Core나 검증 쪽에서 Agent Team Module에 물어볼 일이 있으면
송채영에게 옵니다. 계약 변경 요청이 오면 <b>혼자 답하지 말고</b> 세 사람이 같이 정하세요.
<code>TeamTask</code>·<code>TeamResult</code>가 바뀌면 세 사람 코드가 전부 바뀝니다.</p>
</div>

<h2>확인 질문</h2>
<ol class="q">
<li>Response Review 팀은 왜 <code>ReadToolbox</code>를 안 받습니까?</li>
<li>LLM에게 검토를 시키는데 왜 코드로 또 검사합니까?</li>
<li>분류가 실패한 문의는 어떻게 됩니까? 빈 <code>intent</code>로 라우팅됩니까?</li>
<li>새 프롬프트 파일을 만들었는데 팀이 계속 죽습니다. 무엇을 빼먹었습니까?</li>
</ol>

<h2>옆 담당과 맞닿는 곳</h2>
""" + table(["담당", "어디서 만나나"], [
    ["<a href='04_team_order_payment.html'>김지혜 · 주문과 결제</a>",
     "같은 계약을 씁니다. 계약을 바꾸려면 같이 정합니다"],
    ["<a href='05_team_fulfillment_return.html'>서유현 · 배송과 반품</a>",
     "동. Catalog &amp; Verification은 셋이 함께 만듭니다"],
    ["<a href='01_core1_case_runtime.html'>최연우 · 코어 1</a>",
     "Controller가 <code>execute()</code>를 부릅니다. 분류 결과로 라우팅합니다"],
    ["<a href='06_eval_frontend.html'>최상욱 · 검증과 프론트</a>",
     "답변 품질을 golden/holdout으로 잽니다. VOC 화면도 그쪽입니다"],
])


# ══════════════════════════════════════════ 4. 주문 · 결제 · 김지혜
P4 = TEAM_BASE + """
<h2>내 Team 하나</h2>
<p class="lede">Team 하나인데 저장소에서 가장 큰 Team입니다. 273줄로 다음 것의 두 배 가까이 됩니다.</p>

<p>조달과 주문과 결제를 한 팀이 맡습니다. capability가 여섯 개(<code>procurement.quote</code>,
<code>order.verify</code>, <code>order.create</code>, <code>order.modify</code>,
<code>order.cancel</code>, <code>payment.status</code>)로 다른 팀의 두세 배입니다.</p>

<p><b>돈이 걸려 있어서 위험도가 제일 높은 팀입니다.</b> 주문을 만들고 고치고 취소하는 일은
전부 되돌리기 어렵습니다. 그래서 이 팀이 만드는 제안은 기본 위험도가
<code>high</code>이고, 사람 승인 없이는 실행되지 않습니다.</p>

<h2>이 팀만의 특징 셋</h2>

<h3>도구를 네 개나 씁니다</h3>
<p><code>read.order</code>, <code>read.account</code>, <code>read.policy</code>,
<code>read.catalog</code>입니다. 다른 팀이 하나에서 셋을 쓰는 것과 비교됩니다.
주문 하나를 판단하려면 주문과 계정과 정책과 상품을 다 봐야 하기 때문입니다.</p>

<h3>배송 전인지 후인지가 갈림길입니다</h3>
<p><code>_is_pre_shipment()</code>가 이 팀 로직의 중심입니다. 배송 전이면 취소와 변경이
되고, 배송이 나갔으면 반품 절차로 넘어갑니다. 이 판정을 틀리면 고객에게
"취소됩니다"라고 잘못 말하게 됩니다.</p>

<h3>제안 만드는 함수가 따로 있습니다</h3>
<p><code>_proposal()</code>이 위험도까지 붙여서 제안을 만듭니다. 기본값이
<code>high</code>인 것을 확인하세요. 다른 팀은 이렇게까지 안 합니다.</p>

<h2>코드 읽는 순서</h2>
<p class="lede">273줄이라 한 번에 안 읽힙니다. 도우미 함수부터 보고 <code>execute()</code>로 갑니다.</p>
""" + steps([
    ("app/modules/customer_ops/voc_store_manager.py <b>(내 팀 아님, 먼저 읽기)</b>",
     "★내 파일부터 열지 마세요. 97줄짜리 가장 짧은 Team을 먼저 통째로 읽고 "
     "&#39;Team 하나가 어떻게 생겼는지&#39;를 잡은 다음 내 273줄로 오면 훨씬 빠릅니다."),
    ("procurement_order_payment.py:24~40 <code>manifest</code>",
     "내 팀의 자기소개서입니다. capability 여섯 개와 도구 네 개, 지식 범위 다섯 개를 "
     "먼저 외우세요. 이 목록이 내가 할 수 있는 일의 전부입니다."),
    ("procurement_order_payment.py:46 <code>_result()</code>, :55 <code>_evidence()</code>, :72 <code>_escalate()</code>",
     "결과·근거·에스컬레이션을 만드는 도우미 셋입니다. <code>execute()</code>가 이걸 계속 "
     "부르므로 먼저 알고 가야 본체가 읽힙니다."),
    ("procurement_order_payment.py:82 <code>_read()</code>",
     "도구를 부르는 자리입니다. <code>seen</code> 집합을 넘기는 것을 보세요 — "
     "같은 도구를 반복해 부르는 루프를 막습니다."),
    ("procurement_order_payment.py:85 <code>_proposal()</code>",
     "제안을 만드는 함수입니다. <code>risk</code> 기본값이 <code>&quot;high&quot;</code>인 것을 "
     "확인하세요. 돈이 걸린 팀이라 그렇습니다."),
    ("procurement_order_payment.py:103 <code>_order_status()</code>, :113 <code>_is_pre_shipment()</code>",
     "★이 팀 로직의 중심입니다. 배송 전인지 후인지로 취소·변경 가능 여부가 갈립니다. "
     "<code>None</code>을 돌려줄 수 있게 만든 이유(모르면 모른다고 함)를 확인하세요."),
    ("procurement_order_payment.py:124 <code>execute()</code>",
     "본체입니다. 위를 다 읽고 오면 capability별 분기가 그냥 읽힙니다. "
     "각 갈래가 어떤 근거를 붙여 무엇을 돌려주는지 따라가세요."),
    ("app/tools/read_tools.py:56 <code>order()</code>, :76 <code>catalog()</code>, :138 <code>account()</code>",
     "내가 쓰는 도구 넷의 실제 구현입니다. 무슨 컬럼을 읽어 오는지 알아야 "
     "제안에 넣을 수 있는 값의 범위를 압니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest tests/unit/teams/test_procurement_order_payment.py -q
python -m pytest tests/integration/db/test_procurement_catalog.py -q
python -m pytest tests/unit/teams -q</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0">배송이 이미 나간 주문에 <code>order.cancel</code>을 요청해 보세요.
<code>_is_pre_shipment()</code>가 <code>False</code>를 돌려주고 그다음 무엇이 일어나는지
따라가면 이 팀의 핵심 분기를 한 번에 이해할 수 있습니다.</p>
<p style="margin:8px 0 0">그다음 주문 상태가 아예 조회 안 되는 경우를 만들어 보세요.
<code>None</code>일 때 어떻게 되는지가 &#39;모르면 모른다고 한다&#39;가 코드에서
어떻게 생겼는지 보여 줍니다.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>돈이 걸린 값은 반드시 근거를 붙입니다</b>
<p style="margin:6px 0 0">금액이나 수량을 제안에 넣을 때 그 값이 어디서 왔는지
<code>Evidence</code>로 남겨야 합니다. 안 남기면 코어 2의
<code>verify_proposal()</code>이 대조할 것이 없어서 막지 못합니다.
<b>내가 근거를 안 붙이면 방어선이 하나 사라집니다.</b></p>
</div>

<div class="note">
<b>자릿수가 큰 식별자는 문자열입니다</b>
<p style="margin:6px 0 0">주문번호나 결제 식별자를 숫자로 다루면 자릿수가 잘립니다.
데이터 정의서에 명시돼 있고, 이 팀이 제일 자주 마주치는 자리입니다.</p>
</div>
""" + TEAM_TRAPS + """
<h2>확인 질문</h2>
<ol class="q">
<li>배송이 나간 주문을 고객이 취소해 달라고 합니다. 이 팀은 무엇을 돌려줍니까?</li>
<li>주문 상태를 조회했는데 값이 없습니다. 배송 전으로 봅니까, 후로 봅니까?</li>
<li>제안에 환불 금액 30,000원을 넣었습니다. 이 값의 근거를 안 붙이면 어디서 문제가 됩니까?</li>
<li>내 팀이 <code>read.shipment</code> 도구를 부르면 어떻게 됩니까? 왜 그렇게 막혀 있습니까?</li>
</ol>

<h2>옆 담당과 맞닿는 곳</h2>
""" + table(["담당", "어디서 만나나"], [
    ["<a href='05_team_fulfillment_return.html'>서유현 · 배송과 반품</a>",
     "★제일 자주 부딪힙니다. 배송 전이면 내가, 배송 후면 서유현이 받습니다. "
     "그 경계선을 둘이 같은 기준으로 잡아야 합니다"],
    ["<a href='03_team_voc_response.html'>송채영 · VOC와 응대</a>",
     "같은 계약을 씁니다. 계약 변경은 송채영이 창구입니다"],
    ["<a href='02_core2_access_action.html'>정세환 · 코어 2</a>",
     "내 제안이 거기서 검증되고 승인받아 실행됩니다. 근거를 안 붙이면 그쪽이 막을 수 없습니다"],
])


# ══════════════════════════════════════════ 5. 배송 · 반품 · 서유현
P5 = TEAM_BASE + """
<h2>내 Team 둘</h2>
<p class="lede">배송이 어디서 멈췄는지 보는 팀과, 반품이 되는지 판정하는 팀입니다.</p>

<p>둘 다 <b>주문이 나간 뒤</b>를 다룹니다. 김지혜의 팀이 배송 전을 맡고, 배송이 나간 순간부터
이쪽으로 넘어옵니다. 그 경계선을 두 사람이 같은 기준으로 잡아야 문의가 사이에 빠지지 않습니다.</p>

<h3>Fulfillment &amp; Logistics (110줄)</h3>
<p>배송 추적, 배송 상태, 배송 예외를 다룹니다. 도구는 <code>read.order</code>,
<code>read.shipment</code>, <code>read.policy</code> 셋입니다. 지식 범위에
<code>delivery_exception</code>이 따로 있는 것을 눈여겨보세요 — 정상 배송보다
<b>예외 상황이 이 팀의 본업</b>이라는 뜻입니다.</p>

<h3>Return &amp; Refund (161줄)</h3>
<p>반품 가능 여부, 반품 접수, 환불 금액 계산을 합니다. 이 팀의 중심은 <b>날짜 계산</b>입니다.
반품 기한이 며칠인지가 사유마다 다르고, 그 값을 정책 문서에서 읽어 옵니다.
지금은 Mock 단계이며 실제 반품 시스템 연동은 검증 쇼핑몰 일정에 따라 붙습니다.</p>

<h2>이 두 팀의 공통 어려움 — 날짜와 시간</h2>
<p>배송일, 수령일, 반품 기한, 환불 처리일이 전부 시간 계산입니다. 그리고 시간 계산은
조용히 틀리기 쉽습니다. 하루 차이로 "반품 됩니다"가 "반품 안 됩니다"로 바뀌는데,
고객에게 잘못 말하면 되돌리기 어렵습니다.</p>
<p><code>return_refund.py:68</code>의 <code>_date()</code>가 값을 날짜로 바꾸는 유일한 자리입니다.
파싱에 실패하면 <code>None</code>을 돌려주고, 그때 이 팀은 <b>추정하지 않고 사람에게 넘깁니다.</b></p>

<h2>코드 읽는 순서</h2>
<p class="lede">짧은 배송 팀부터 읽고 반품 팀으로 갑니다.</p>
""" + steps([
    ("app/modules/customer_ops/voc_store_manager.py <b>(내 팀 아님, 먼저 읽기)</b>",
     "★97줄짜리 가장 짧은 Team을 먼저 통째로 읽으세요. Team 하나의 뼈대를 잡은 다음 "
     "내 파일로 오면 훨씬 빠릅니다."),
    ("app/modules/customer_ops/fulfillment_logistics.py:13~22 <code>manifest</code>",
     "capability 셋, 도구 셋, 지식 범위 넷입니다. <code>delivery_exception</code>이 "
     "지식 범위에 있는 것을 확인하세요."),
    ("fulfillment_logistics.py:33 <code>_read()</code>, :41 <code>_escalate()</code>, :46 <code>execute()</code>",
     "110줄이라 한 번에 읽힙니다. 조회해서 → 없으면 넘기고 → 있으면 상태를 붙여 돌려주는 "
     "단순한 구조입니다. Team의 기본형에 가깝습니다."),
    ("app/modules/customer_ops/return_refund.py:16~30 <code>manifest</code>",
     "capability 셋(<code>check_eligibility</code>, <code>request</code>, "
     "<code>refund.calculate</code>)이 반품 흐름의 세 단계와 그대로 대응합니다."),
    ("return_refund.py:54 <code>_policy_days()</code>",
     "★이 팀의 핵심입니다. 반품 사유별 기한 일수를 정책에서 읽습니다. "
     "정책을 못 읽었을 때 무슨 값이 나오는지 반드시 확인하세요 — 여기서 기본값을 "
     "함부로 두면 잘못된 확답이 나갑니다."),
    ("return_refund.py:68 <code>_date()</code>",
     "값을 날짜로 바꾸는 유일한 자리입니다. 실패하면 <code>None</code>입니다. "
     "&#39;모르면 추정하지 않는다&#39;가 코드에서 이렇게 생겼습니다."),
    ("return_refund.py:40 <code>_evidence()</code>, :79 <code>execute()</code>",
     "본체입니다. 주문·반품이력·정책 셋을 근거로 묶어 판정합니다. "
     "기한 계산 결과가 근거에 같이 실리는지 확인하세요."),
    ("app/tools/read_tools.py:64 <code>shipment()</code>, :126 <code>return_request()</code>",
     "내가 쓰는 도구 둘의 실제 구현입니다. 어떤 컬럼이 오는지 알아야 판정에 쓸 수 있습니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest tests/unit/teams/test_fulfillment_logistics.py -q
python -m pytest tests/unit/teams/test_return_refund.py -q
python -m pytest tests/unit/teams -q</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0">반품 기한이 딱 경계인 주문을 만들어 보세요. 기한이 7일이고
수령일로부터 정확히 7일째인 건입니다. 되는지 안 되는지, 그리고 그 판정 근거가
<code>Evidence</code>에 어떻게 적히는지 보세요.</p>
<p style="margin:8px 0 0">그다음 수령일이 <code>NULL</code>인 주문으로 같은 걸 해 보세요.
<code>_date()</code>가 <code>None</code>을 돌려줄 때 이 팀이 확답을 만들지 않고
넘기는 것을 확인할 수 있습니다.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>기한 판정에 기본값을 함부로 두지 않습니다</b>
<p style="margin:6px 0 0">정책을 못 읽었는데 "보통 7일이니까 7일로 하자"고 두면,
그게 바로 <code>RULE.md</code> §3.2가 금지한 폴백입니다. 고객이 그 답을 믿고
반품을 포기하거나 헛걸음합니다. 모르면 <code>escalate</code>가 정답입니다.</p>
</div>

<div class="note">
<b>배송 전과 후의 경계는 김지혜와 같이 정합니다</b>
<p style="margin:6px 0 0">같은 주문을 두고 &#39;배송 전&#39;이라고 보는 기준이 두 팀에서
다르면 문의가 사이에 빠지거나 두 팀이 서로 다른 답을 냅니다.
<code>procurement_order_payment.py:113</code>의 <code>_is_pre_shipment()</code>를
한 번 같이 읽어 두세요.</p>
</div>

<div class="note">
<b>Return &amp; Refund는 지금 Mock입니다</b>
<p style="margin:6px 0 0">실제 반품 시스템 연동은 검증 쇼핑몰 일정에 달려 있습니다.
"이미 연동됐다"고 발표에서 말하면 안 됩니다. 지금 검증된 것은 판정 로직까지입니다.</p>
</div>
""" + TEAM_TRAPS + """
<h2>확인 질문</h2>
<ol class="q">
<li>수령일이 DB에 없는 주문의 반품 가능 여부를 묻습니다. 무엇을 돌려줍니까?</li>
<li>정책 문서 검색이 실패해서 반품 기한을 모릅니다. 7일로 가정해도 됩니까?</li>
<li>배송이 나갔는지 아닌지 애매한 주문은 누가 받습니까? 그 기준은 어느 파일에 있습니까?</li>
<li>Fulfillment 팀의 지식 범위에 <code>delivery_exception</code>이 따로 있는 이유는 무엇입니까?</li>
</ol>

<h2>옆 담당과 맞닿는 곳</h2>
""" + table(["담당", "어디서 만나나"], [
    ["<a href='04_team_order_payment.html'>김지혜 · 주문과 결제</a>",
     "★제일 자주 부딪힙니다. 배송 전이면 김지혜, 배송 후면 나입니다. 경계 기준을 같이 잡으세요"],
    ["<a href='03_team_voc_response.html'>송채영 · VOC와 응대</a>",
     "내 판정 결과가 응대 문장으로 만들어집니다. 계약 변경은 송채영이 창구입니다"],
    ["<a href='02_core2_access_action.html'>정세환 · 코어 2</a>",
     "환불 제안이 거기서 검증되고 승인받아 실행됩니다"],
])


# ══════════════════════════════════════════ 6. 검증 · 프론트 · 최상욱
P6 = """
<h2>맡은 자리</h2>
<p class="lede">1순위는 화면이 아니라 좋아졌다를 숫자로 증명하는 것입니다.</p>

<div class="note">
<b>구현계획서 §16이 이 자리를 이렇게 못박아 뒀습니다</b>
<p style="margin:6px 0 0"><b>검증이 앞이고 프론트가 뒤입니다.</b> UI는 그 증명을 사람이 볼 수
있게 만드는 수단입니다. <b>화면을 먼저 만들고 평가를 뒤로 미루지 않습니다.</b>
혼자 두 축을 맡고 있어 순서가 흔들리기 쉬운데, 흔들리면 발표에서 보여 줄 숫자가 없습니다.</p>
</div>

<p>구체적으로는 넷입니다. 평가 하네스와 golden/holdout 관리, 지표와 통계, 회귀와 계약 테스트
실행, 그리고 운영 콘솔과 조립입니다.</p>

<h2>소유 경계</h2>
""" + scope(
    ["평가 harness와 golden/holdout 관리",
     "지표·통계와 회귀·contract test 실행",
     "운영 콘솔 UI와 observability",
     "조립 선언(<code>project.yaml</code>)과 Composer API",
     "통합 데모"],
    ["업무 로직 구현 (모델 3인)",
     "상태 전이 규칙 (코어 1)",
     "승인과 감사 구현 (코어 2)"]) + """

<h2>A. 평가 — 먼저 할 일</h2>

<h3>알아야 할 말 다섯 개</h3>
<p><b>golden과 holdout</b>은 정답이 붙은 문제 묶음입니다. golden 60건은 보면서 고쳐도 되고,
holdout 20건은 <b>절대 보고 고치면 안 됩니다.</b> 보고 프롬프트를 손보는 순간
그건 두 번째 golden입니다.</p>
<p><b>arm(군)</b>은 비교하는 방식 하나입니다. A, B, Proposed 셋이 있고
<b>run 단위로만</b> 비교합니다. arm이나 데이터셋이나 실행 방식이 다르면 평균을 견줄 수 없습니다.</p>
<p><b>bootstrap 95% 신뢰구간</b>은 같은 결과를 수천 번 다시 뽑아 차이가 어느 범위에 있는지
재는 방법입니다. 평균만 말하면 그 숫자가 얼마나 흔들리는지 알 수 없습니다.</p>
<p><b>McNemar 검정</b>은 같은 문제를 두 방식에 똑같이 풀렸을 때 A는 틀리고 B는 맞은 건수와
그 반대 건수를 비교합니다. 짝지어진 비교라 표본이 적어도 씁니다.</p>
<p><b>judge와 rubric</b>은 답변 품질을 LLM에게 채점시키는 것과 그 기준표입니다.
judge가 사람과 얼마나 맞는지는 <b>따로 확인해야</b> 합니다.</p>

<h3>코드 읽는 순서</h3>
""" + steps([
    ("eval/datasets/golden.jsonl 의 첫 줄 하나",
     "제일 먼저 할 일입니다. 한 줄만 열어 무슨 필드가 있는지 보세요. "
     "입력과 정답이 뭔지 모르면 나머지가 다 추상적입니다."),
    ("eval/runners/common.py:141 <code>run_config()</code>",
     "세 군이 공유하는 실행부입니다. 모델·temperature·seed·프롬프트 버전을 고정하는 자리입니다. "
     "이 값들이 안 고정되면 재현이 안 돼서 비교 자체가 무의미해집니다."),
    ("eval/runners/baseline_a.py → baseline_b.py → proposed.py",
     "이 순서로 셋을 나란히 읽으세요. <b>세 파일의 차이가 곧 우리가 무엇을 더 했다고 "
     "주장하는지</b>입니다."),
    ("eval/judge/rubric.json 과 eval/check_judge.py",
     "채점 기준표와, 근거 없이 점수를 받은 행이 있는지 세는 검사기입니다. "
     "하나라도 있으면 종료코드 1입니다. 채점자를 채점하는 코드입니다."),
    ("eval/stats/make_pairs.py → bootstrap.py → mcnemar.py",
     "짝을 만들고 신뢰구간을 내고 검정합니다. 짧으니 입력이 무엇인지만 보면 충분합니다."),
    ("eval/defense_metrics.py 와 eval/datasets/attack_fixtures.jsonl",
     "일부러 이상한 입력을 넣었을 때 막아 내는지 재는 부분입니다. "
     "품질 지표와 안전 지표를 따로 잰다는 것을 확인하세요."),
]) + """
<div class="note">
<b>★지금 채점기에 결함이 있습니다 (미해결)</b>
<p style="margin:6px 0 0">A군 정확도가 0.0%로 나온 적이 있는데 모델 문제가 아니었습니다.
채점 코드가 승인 대기라는 정상 결과를 실패로 세고, 성공 판정을 뒤에서 덮어쓰고
있었습니다. 실측은 A 0.0% · B 98.6% · Proposed 27.8%였습니다.</p>
<p style="margin:8px 0 0">기록은 <code>program/research/_평가harness_결함_2026-08-29.md</code>,
수정 지시서는 <code>docs/handoff/_prompts/S-EVAL-SCORING-FIX.md</code>입니다.
<b>이게 이 담당의 첫 번째 할 일입니다.</b> 고치기 전의 수치는 아무 의미가 없습니다.</p>
</div>

<div class="note">
<b>저장소에 남아 있는 옛 수치는 무효입니다</b>
<p style="margin:6px 0 0">A 0/180, B 6/180, Proposed 40/180 같은 숫자가 문서에 있는데
지식 코퍼스가 구독·청구 도메인이던 시절 값입니다. 쇼핑몰로 갈아 끼운 뒤 재측정하지
않았습니다. 참고용으로만 두고 근거로 쓰지 마세요.</p>
</div>

<h2>B. 조립과 운영 콘솔</h2>

<h3>네 가지 구분을 먼저 잡습니다</h3>
""" + table(["말", "뜻", "화면에서"], [
    ["<b>컴포넌트</b>", "빼면 시스템이 성립하지 않는 것. 9개", "잠겨 있습니다"],
    ["<b>모듈</b>", "켜고 꺼도 나머지가 도는 것. 6개", "토글로 켜고 끕니다"],
    ["<b>Port</b>", "같은 자리에 다른 구현을 끼우는 지점", "구현을 고릅니다"],
    ["<b>인스턴스</b>", "개수가 늘고 주는 것. Team이 유일", "추가하고 뺍니다"],
]) + """
<h3>코드 읽는 순서</h3>
""" + steps([
    ("config/project.yaml",
     "40줄이 안 됩니다. 모듈 6개, Port 3개, Team 6개가 전부 여기 선언돼 있습니다. "
     "<b>이 파일이 이 절의 주인공입니다.</b>"),
    ("app/core/project_config.py:78 <code>module_enabled()</code>, :84 <code>require_module()</code>",
     "선언을 읽고 켜져 있나를 묻습니다. <code>require_module()</code>은 꺼져 있으면 "
     "예외를 냅니다 — 조용히 넘어가지 않는 게 핵심입니다."),
    ("app/composition.py 의 <code>build_</code> 함수들",
     "조립 경계입니다. Team을 하드코딩 import하지 않고 선언에 적힌 경로를 "
     "<code>importlib</code>로 불러옵니다. 그래서 Team을 늘려도 Core가 안 바뀝니다."),
    ("app/application/composer_service.py",
     "선언을 고치는 로직입니다. <code>read_current</code> → <code>validate_candidate</code> → "
     "<code>apply_candidate</code> 순으로 읽으세요."),
    ("app/presentation/api/composer.py",
     "그 로직을 여는 API 넷입니다. <code>apply</code>가 사유(<code>reason</code>)를 필수로 "
     "받는 것을 확인하세요 — 감사 기록의 근거입니다."),
    ("app/presentation/ui/routes.py 의 <code>_admin_snapshot()</code>",
     "542줄로 저장소에서 제일 큰 파일이지만 여기부터 보면 됩니다. "
     "지금 무엇으로 조립돼 있는지를 화면에 뿌리는 함수입니다."),
    ("app/presentation/ui/theme.py",
     "디자인 시스템입니다. 색을 컴포넌트에 하드코딩하지 않고 토큰으로만 씁니다. "
     "<code>unknown</code>을 가장 센 위험색으로 칠한 이유도 여기서 보입니다."),
    ("app/introspection/contract.py",
     "밖에서 지금 어떻게 조립돼 있냐고 물었을 때 답하는 계약입니다. "
     "별도 프로그램 <code>final_project_ui</code>가 이걸 읽습니다."),
]) + """
<h2>직접 돌려 보기</h2>
<pre>python -m pytest eval/tests -q
python -m scripts.verify_eval_datasets
python -m scripts.verify_module_toggles
python -m pytest tests/contract -q
python -m uvicorn app.presentation.api.app:app --port 8042</pre>

<div class="good">
<b>추천 연습</b>
<p style="margin:6px 0 0"><code>project.yaml</code>에서 <code>graph_store</code>를
<code>false</code>로 바꾸고 서버를 <b>다시 띄운</b> 다음 <code>/ui/admin</code>을 보세요.
Ports 표의 GraphStorePort 줄이 <code>SqlGraphAdapter</code>에서
<code>모듈 꺼짐 (graph_store)</code>으로 바뀝니다. 확인했으면 되돌리세요.</p>
</div>

<h2>함정</h2>

<div class="note">
<b>조립은 기동할 때 한 번만 일어납니다</b>
<p style="margin:6px 0 0">선언을 고쳐도 떠 있는 서버는 안 바뀝니다. 재기동해야 합니다.
고쳤는데 왜 안 바뀌지의 대부분이 이겁니다.</p>
</div>

<div class="note">
<b>--reload 자식 프로세스가 옛 코드를 서빙합니다</b>
<p style="margin:6px 0 0">uvicorn을 <code>--reload</code>로 띄우면 자식 프로세스가 남아
고친 코드가 반영 안 된 것처럼 보일 때가 있습니다. 실제로 여기에 한참 쓴 적이 있습니다.
선언을 바꿔 가며 확인할 때는 <code>--reload</code> 없이 띄우세요.</p>
</div>

<div class="note">
<b>voc 모듈은 끌 수 없습니다</b>
<p style="margin:6px 0 0">2026-08-30 확정입니다. 끄면 앱이 아예 안 뜹니다. 인라인 분류가
Case 생성 경로에 붙어 있고 그건 선택 기능이 아니기 때문입니다.
계약 문서 <code>docs/handoff/08_모듈_컴포넌트_목록.md</code> §2에 표시돼 있습니다.</p>
</div>

<div class="note">
<b>Composer 화면은 이 저장소에 없습니다</b>
<p style="margin:6px 0 0"><code>/ui/composer</code>는 2026-08-18에 삭제됐습니다.
인증이 전혀 없이 고객 접근 가능한 앱에 물려 있었기 때문입니다. 같은 기능은 별도 프로그램
<code>final_project_ui</code>가 인증된 <code>/composer/*</code> API로만 제공합니다.
이 저장소에는 <b>API 쪽만</b> 있습니다.</p>
</div>

<div class="note">
<b>화면을 열어서 확인하지 않으면 완료가 아닙니다</b>
<p style="margin:6px 0 0">이 저장소 규칙(<code>CLAUDE.md</code> §4)입니다. 실제로 브라우저에서
승인 버튼을 눌러 보다가 결함 두 건을 찾은 적이 있습니다. 테스트만으로는 안 나왔습니다.</p>
</div>

<h2>확인 질문</h2>
<ol class="q">
<li>제안군이 B군보다 평균 5%p 높습니다. 좋아졌다고 말해도 됩니까? 무엇이 더 필요합니까?</li>
<li>golden으로 프롬프트를 손봤습니다. 이제 holdout으로 재도 됩니까? 몇 번까지 됩니까?</li>
<li>judge가 준 grounding 3.98을 근거로 쓰려면 무엇을 먼저 확인해야 합니까?</li>
<li>Team을 하나 추가할 때 Python 코드를 몇 파일 고쳐야 합니까?</li>
<li>선언을 고쳤는데 동작이 안 바뀝니다. 제일 먼저 무엇을 의심합니까?</li>
</ol>

<h2>옆 담당과 맞닿는 곳</h2>
""" + table(["담당", "어디서 만나나"], [
    ["<a href='03_team_voc_response.html'>송채영 외 2인 · Agent Team</a>",
     "평가 대상이 이들의 판단입니다. Team이 바뀌면 다시 재야 합니다"],
    ["<a href='01_core1_case_runtime.html'>최연우 · 코어 1</a>",
     "Case 상태와 이벤트를 화면에 뿌립니다. 조립이 Registry와 Controller를 만듭니다"],
    ["<a href='02_core2_access_action.html'>정세환 · 코어 2</a>",
     "승인 화면과 감사 기록 화면이 이 파트입니다. 승인 API는 그쪽입니다"],
])


# ══════════════════════════════════════════════════════ 출력
PAGES = [
    (PARTS[0][0], "Case 런타임", "최연우", PARTS[0][3],
     "A-COP 담당자별 학습 가이드 · 코어 1",
     "문의 하나를 상태를 가진 업무 단위로 만들고, 어느 팀에 줄지 정하고, 기다렸다 재개하는 자리입니다.",
     "담당 최연우 · 코드 약 900줄 · 시작점은 app/core/contracts.py", P1),
    (PARTS[1][0], "진입과 실행", "정세환", PARTS[1][3],
     "A-COP 담당자별 학습 가이드 · 코어 2",
     "밖에서 들어오는 문(REST · MCP · A2A)이고, 되돌릴 수 없는 일을 실제로 실행하는 마지막 관문입니다.",
     "담당 정세환 · 코드 약 700줄 · 시작점은 app/presentation/security.py", P2),
    (PARTS[2][0], "VOC와 응대 생성", "송채영", PARTS[2][3],
     "A-COP 담당자별 학습 가이드 · Agent Team Module (총괄)",
     "문의를 모아 보는 팀과 답변 문장을 만들고 검토하는 팀입니다. CS Pack의 고정 축 둘입니다.",
     "담당 송채영 (Agent Team Module 총괄) · Team 2개 + 분류기 · 251줄", P3),
    (PARTS[3][0], "조달·주문·결제", "김지혜", PARTS[3][3],
     "A-COP 담당자별 학습 가이드 · Agent Team Module",
     "주문을 만들고 고치고 취소합니다. 돈이 걸려 있어 위험도가 가장 높은 팀입니다.",
     "담당 김지혜 · Team 1개 · 273줄로 저장소에서 가장 큰 Team", P4),
    (PARTS[4][0], "배송과 반품", "서유현", PARTS[4][3],
     "A-COP 담당자별 학습 가이드 · Agent Team Module",
     "배송이 어디서 멈췄는지 보는 팀과, 반품이 되는지 판정하는 팀입니다. 주문이 나간 뒤를 맡습니다.",
     "담당 서유현 · Team 2개 · 271줄 · 중심은 날짜 계산", P5),
    (PARTS[5][0], "검증과 프론트", "최상욱", PARTS[5][3],
     "A-COP 담당자별 학습 가이드 · 검증 &amp; 프론트",
     "1순위는 화면이 아니라 좋아졌다를 숫자로 증명하는 것입니다. 그다음이 그 증명을 보여 주는 화면입니다.",
     "담당 최상욱 · eval/ 전체 + 운영 콘솔 + 조립 · 혼자 두 축", P6),
]

for filename, title, who, accent, kicker, sub, meta, body in PAGES:
    out = os.path.join(HERE, filename)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page(filename, title, who, accent, kicker, sub, meta, body))
    print("  %-34s %-4s %6d bytes" % (filename, who, os.path.getsize(out)))
print("\n%d장 생성: %s" % (len(PAGES), HERE))
