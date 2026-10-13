"""Generate the two self-contained review documents. Preserve every prior output."""
from pathlib import Path
import ast, datetime, hashlib, html, json, shutil

HERE=Path(__file__).resolve().parent
WORK=HERE.parents[2]
P=json.loads((HERE/'project-manifest-v2.json').read_text(encoding='utf-8'))
S=json.loads((HERE/'source-manifest.json').read_text(encoding='utf-8'))['sources']
C=json.loads((HERE/'checks/project-checks-v2.json').read_text(encoding='utf-8'))
E=html.escape

def local(path,label=None):
    return f'<a href="../../../{E(path,quote=True)}">{E(label or path)}</a>'
def table(heads,rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+h+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'
def section(ident,title,body): return f'<section id="{ident}"><h2>{title}</h2>{body}</section>'
def sha(value): return '<code class="hash">'+E(value)+'</code>'
def source_ref(sid): return f'<a href="#ref-{sid}">[{sid}]</a>'
def svg_open(slug,title,desc,w=960,h=600):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="{slug}-title {slug}-desc"><title id="{slug}-title">{title}</title><desc id="{slug}-desc">{desc}</desc><defs><marker id="{slug}-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0 L8 3 L0 6 Z" fill="#6b7488"/></marker><marker id="{slug}-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0 L8 3 L0 6 Z" fill="#a8720c"/></marker><marker id="{slug}-link" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><path d="M0 0 L8 3 L0 6 Z" fill="#2f5bd8"/></marker></defs>'
def text(x,y,t,size=20): return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="middle">{E(t)}</text>'
def rect(x,y,w,h,t,focal=False):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{"#fbf5e8" if focal else "#fff"}" stroke="{"#a8720c" if focal else "#161c28"}"/>'+text(x+w/2,y+h/2+8,t)
def oval(x,y,w,h,t): return f'<ellipse cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}" fill="#f1f4f8" stroke="#161c28"/>'+text(x+w/2,y+h/2+8,t)

def hierarchy():
    s=svg_open('baseline-scope','프로젝트 기준선과 세부 기준의 관계','프로젝트 공통 기준 안에 담당 기능의 구현 기준이 있고 모델 학습 비교는 각 작업에 연결됩니다.')
    s+='<rect x="40" y="40" width="880" height="492" rx="8" fill="#f1f4f8" stroke="#6b7488"/>'
    s+=text(480,88,'프로젝트 공통 기준선 1개',28)+text(480,124,'범위 · 공통 계약 · 검증 · 채택한 버전',20)
    s+='<rect x="72" y="160" width="816" height="164" rx="8" fill="#fff" stroke="#161c28"/>'
    s+=text(480,196,'기능 구현 기준 — 이 파일의 하위 절',20)
    s+=rect(96,220,232,64,'Activity')+rect(364,220,232,64,'Dining')+rect(632,220,232,64,'Mobility')
    s+='<rect x="72" y="356" width="816" height="140" rx="8" fill="#fbf5e8" stroke="#a8720c"/>'
    s+=text(480,396,'모델 작업별 비교 기준',24)+text(480,436,'추가 학습 없는 원본 + 고정 시험 + 실행 조건',20)+text(480,472,'학습판은 별도 후보 · 통과 후에만 제품 버전에 연결',20)
    s+='<line x1="40" y1="552" x2="920" y2="552" stroke="#dbe0ea"/>'+text(480,580,'사람 수와 파일 수는 같을 필요가 없습니다.',16)+'</svg>'
    return '<figure>'+s+'<figcaption>구조도입니다. 좁은 화면에서는 그림을 좌우로 밀어 볼 수 있습니다.</figcaption></figure>'

def workflow():
    s=svg_open('adopt-flow','기준선 채택과 수정 절차','후보를 검토하고 미충족 사항이 있으면 고친 뒤 다시 검사합니다. 팀 채택을 기록한 버전에서 작업을 시작합니다.',960,800)
    # Draw every connector before nodes. Labels sit in the open canvas, off their strokes.
    for path in ['M480 104 V140','M480 204 V244','M480 308 V348','M480 492 V544','M480 608 V652']:
        s+=f'<path d="{path}" fill="none" stroke="#6b7488" marker-end="url(#adopt-flow-arrow)"/>'
    s+='<path d="M620 420 H784 Q792 420 792 412 V180 Q792 172 784 172 H644" fill="none" stroke="#6b7488" marker-end="url(#adopt-flow-arrow)"/>'
    s+='<rect x="644" y="388" width="112" height="24" fill="#fbfcfd"/>'+text(700,408,'아니요 · 수정',16)
    s+='<rect x="492" y="500" width="192" height="28" fill="#fbfcfd"/>'+text(588,520,'예 · 검토·채택 기록 있음',16)
    s+=oval(360,40,240,64,'검토 회차 시작')+rect(320,140,320,64,'범위·버전·실측 작성')+rect(320,244,320,64,'근거·재현·영향 검사')
    s+='<path d="M480 348 L620 420 L480 492 L340 420 Z" fill="#fbf5e8" stroke="#a8720c"/>'+text(480,416,'채택 조건',20)+text(480,444,'충족?',20)
    s+=rect(320,544,320,64,'채택한 판에서 작업')+oval(320,652,320,64,'이번 기준선 수립 종료')
    s+='<line x1="40" y1="736" x2="920" y2="736" stroke="#dbe0ea"/>'+text(480,768,'다음 회차: 계약·범위·채택 모델 등 공통 기준이 바뀔 때 새 후보를 만듭니다.',16)+'</svg>'
    return '<figure>'+s+'<figcaption>흐름도 · 타원은 시작/종료, 사각형은 처리, 마름모는 판단입니다. 팀 검토 대기는 채택 전에 머뭅니다. 좁은 화면에서는 좌우로 밀어 볼 수 있습니다.</figcaption></figure>'

CSS='''
:root{--paper:#fbfcfd;--ink:#161c28;--muted:#586277;--rule:#dbe0ea;--accent:#a8720c;--link:#2f5bd8}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);word-break:keep-all;font:16px/1.85 'Geist','Noto Sans KR','Malgun Gothic',sans-serif}
a{color:var(--link);text-underline-offset:3px;overflow-wrap:anywhere}a:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:5px}
.skip{position:absolute;left:12px;top:-100px;background:white;padding:12px}.skip:focus{top:12px;z-index:10}
.layout{max-width:1280px;margin:auto;display:grid;grid-template-columns:228px minmax(0,1fr);gap:48px;padding:48px 36px 80px}
nav{position:sticky;top:28px;align-self:start;max-height:calc(100vh - 56px);overflow:auto;border-top:3px solid var(--ink);padding-top:16px}nav strong{display:block;margin-bottom:12px}nav a{display:block;padding:6px 0;font-size:14px;text-decoration:none}
main{min-width:0}header{padding:0 0 32px;border-bottom:1px solid var(--rule)}.eyebrow{font-size:13px;letter-spacing:.1em;color:var(--muted);margin:0 0 12px}
h1{font:400 clamp(30px,4vw,44px)/1.45 'Instrument Serif','Noto Serif KR','Batang',serif;letter-spacing:-.025em;margin:0 0 20px}h2{font-size:25px;line-height:1.5;letter-spacing:-.02em;margin:0 0 20px}h3{font-size:19px;margin:28px 0 12px}p{margin:0 0 16px}strong{font-weight:650}
section{padding:40px 0;border-bottom:1px solid var(--rule);scroll-margin-top:24px}.lead{font-size:20px;line-height:1.8}.note{border-left:4px solid var(--accent);background:#fbf5e8;padding:16px 20px;margin:24px 0}.status{display:inline-block;border:1px solid var(--accent);padding:2px 10px;margin-bottom:16px;color:#7d5408;font-size:14px}
.table-wrap{overflow-x:auto;margin:20px 0}table{width:100%;border-collapse:collapse;font-size:15px}th,td{text-align:left;vertical-align:top;padding:12px 14px;border-bottom:1px solid var(--rule);min-width:80px;overflow-wrap:anywhere}th{background:#f1f4f8;font-weight:650}tbody tr:last-child td{border-bottom:1px solid #aab4c5}
code,pre{font:14px/1.7 'Geist Mono','Consolas',monospace}code{background:#edf0f5;padding:2px 4px;overflow-wrap:anywhere}.hash{word-break:break-all;font-size:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f8;border:1px solid var(--rule);padding:20px;margin:20px 0}
ul,ol{padding-left:24px;margin:16px 0}li{padding:3px 0}details{border:1px solid var(--rule);padding:16px 20px;margin:20px 0}summary{cursor:pointer;font-weight:600}details[open] summary{margin-bottom:20px}
figure{margin:28px 0}svg{display:block;width:100%;height:auto;max-height:none}svg text{font-family:'Geist','Noto Sans KR','Malgun Gothic',sans-serif;fill:var(--ink)}figcaption{font-size:14px;color:var(--muted);margin-top:8px}.small{font-size:14px;color:var(--muted)}.facts{border-top:2px solid var(--ink);margin-top:28px}footer{padding-top:28px;font-size:13px;color:var(--muted)}.ref{padding:16px 0;border-bottom:1px solid var(--rule)}.ref p{margin-bottom:6px}
@media(max-width:900px){.layout{display:block;padding:24px 20px 60px}nav{position:static;max-height:none;margin-bottom:32px;display:flex;flex-wrap:wrap;gap:4px 16px}nav strong{width:100%;margin:0}nav a{font-size:14px}h2{font-size:23px}section{padding:32px 0}th,td{padding:10px}figure{overflow-x:auto}svg{min-width:640px}.lead{font-size:18px}}
@media print{.layout{display:block;padding:0;max-width:none}nav,.skip{display:none}body{font-size:11pt;background:white}h1{font-size:25pt}h2{font-size:17pt}a{color:#161c28}section{break-inside:auto;padding:20px 0}tr,figure,.note{break-inside:avoid}svg{min-width:0;max-height:22cm}details{border:0}details>*{display:block}header{break-after:avoid}.table-wrap{overflow:visible}footer{font-size:9pt}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
'''

def page(title,subtitle,sections,other,other_label):
    toc=''.join(f'<a href="#{sid}">{E(name)}</a>' for sid,name,_ in sections)
    body=''.join(section(sid,name,content) for sid,name,content in sections)
    return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>'+E(title)+'</title><style>'+CSS+'</style></head><body><a class="skip" href="#main">본문으로 이동</a><div class="layout"><nav aria-label="문서 목차"><strong>triPilot · A-COPilot</strong>'+toc+f'<a href="{other}">{other_label} ↗</a></nav><main id="main"><header><p class="eyebrow">2026-10-10 · 팀 검토 자료</p><h1>'+E(title)+'</h1><p class="lead">'+subtitle+'</p></header>'+body+'<footer>문서 형식: 단일 HTML · 외부 스크립트·이미지·폰트 요청 없음 · 오프라인 글꼴은 맑은 고딕과 바탕체를 사용합니다.<br>다른 문서·참고 자료를 함께 보려면 이 폴더 구조를 유지하십시오. 작성·검수 기록은 <a href="review-report-v2.html">검수 보고서</a>에 있습니다.</footer></main></div></body></html>'

REF_NOTES={
'S01':('v4.0a · 표지 2026-08','8장 §2.1~2.4, PDF 190~191쪽. 기준선의 식별·합의·고정·변경 통제와 관리 대상 범위. 전문 PDF를 확보했으며 관련 절을 읽었습니다. IEEE 828 원문 자체를 읽었다는 뜻은 아닙니다.'),
'S02':('1991-03 · 역사 자료','Peter H. Feiler, CMU/SEI-91-TR-7. 인쇄 40쪽, PDF 42쪽 그림 5-3. 기준 구성과 변경 묶음의 관계. 현재 팀 절차를 그대로 명령하는 문서가 아닙니다.'),
'S03':('2002 · 역사 자료','Stephen B. Johnson, Air Force History and Museums Program. 인쇄 99~100·202~203쪽, PDF 113~114·216~217쪽. 1958~1962년 제도화 계보. 역사 해석 자료이며 단독 발명자를 확정하지 않습니다.'),
'S04':('출간 2002-11-04 · 역사·실무 참고','Steve Berczuk·Brad Appleton, Addison-Wesley Professional. 공개 소개·목차·서문만 확보했습니다. Mainline·Private Workspace·Integration Build 등 협업 패턴의 참고이며 유료 책 전문을 받지 않았습니다.'),
'S05':('갱신일 미표시 · 본문 확인 2026-10-10','GitHub 공식 문서. 브랜치에서 변경하고 PR로 검토한 뒤 합치는 흐름. 보호 규칙과 자동 검사는 저장소에 설정해야 효력이 생깁니다.'),
'S06':('갱신 2026-01-12 · 본문 확인 2026-10-10','DORA. 코드 외 설정·도구·시험·자료·문서까지 식별해 이전 상태를 재현하고 추적하는 원칙. 비밀값을 공용 Git에 넣으라는 의미가 아닙니다.'),
'S07':('갱신일 미표시 · 본문 확인 2026-10-10','DORA. 자주 통합하고 자동 빌드·시험으로 기준 흐름의 상태를 확인하는 실무. 새 코드가 합쳐질 때마다 무조건 새 기준선 이름을 만들 필요는 없습니다.'),
'S08':('갱신 2025-08-25 · 1년 이상 지난 자료','Google Rules of ML, Rule #4. 단순한 첫 모델로 성능·동작의 비교 기준을 만드는 근거. 우리 모델의 실제 성능·학습 성공을 증명하지 않습니다.'),
'S09':('갱신일 미표시 · 본문 확인 2026-10-10','Pro Git, 2.6 Tagging. 특정 커밋에 이름을 붙이는 방법. 태그 이동을 금지하는 운영 규칙은 팀이 별도로 정해야 합니다.'),
'S10':('판의 기준: NASA Systems Engineering Handbook · 역사적 원칙','§6.5.1.2.2. 합의한 특정 시점의 속성과 이후 변경의 기준. 기능·할당·제품 등 여러 종류가 있으며 개발 단계에 따라 기준선이 달라질 수 있습니다.'),
'S11':('갱신 2024-01-18 · 1년 이상 지난 자료','Martin Fowler Continuous Integration. 통합·자체 빌드·시험 관행의 추가 참고. 기준선의 최초 발명자 근거로 쓰지 않습니다.')}
def refs():
    result='<p>공개 PDF 3개와 웹 원문 8개를 보관했습니다. 웹 원문은 외부 스크립트를 포함할 수 있어 읽을 때는 아래의 텍스트 사본을 권합니다. PDF는 페이지 수와 해시까지 확인했습니다. <a href="source-manifest.json">전체 주소·바이트·SHA-256 목록</a>.</p>'
    for r in S:
        date,note=REF_NOTES[r['id']]
        filelink=f'<a href="{E(r["file"],quote=True)}">원문 사본</a>'
        result+=f'<div class="ref" id="ref-{r["id"]}"><p><strong>{r["id"]} · {E(r["title"])}</strong></p><p class="small">{date}</p><p>{note}</p><p><a href="{E(r["url"],quote=True)}">공식 출처</a> · {filelink} · <a href="source-text/{r["id"]}.txt">읽은 절의 텍스트</a></p></div>'
    return result

def manifests():
    rows=[]
    for slug in ['activity','dining','mobility']:
        path=WORK/f'final_project_cs/app/domains/travel_ops/instances/{slug}/team.py'
        tree=ast.parse(path.read_text(encoding='utf-8'))
        call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='TeamManifest')
        vals={k.arg:ast.literal_eval(k.value) for k in call.keywords if k.arg in ['capabilities','default_capability','max_steps','policy_optional_capabilities']}
        rows.append((slug,vals))
    return rows

contract_path='final_project_cs/wiki/teams/team-contract/index.md'
plan_path='program/plan/A-COP_구현계획서_v11.md'
slm_path='final_project_cs/wiki/quality/slm-model-evaluation.md'
f_path='final_project_cs/wiki/quality/selection-grounded-answer-evaluation.md'
train_path='program/research/daily_rag_slm/saluki_finetune_plan_2026-10-09.md'
counts=C['selected_tests']

baseline=[]
baseline.append(('read-first','먼저 읽을 결론',f'''
<span class="status">검토용 기준선 후보 · 팀 채택 대기</span>
<p><strong>서울 여행 일정을 검증하고 변경을 관리하는 제품의 공통 기준을 이 파일 하나에 모았습니다.</strong> 팀별 구현과 모델 학습은 아래 세부 절에서 관리하며, 함께 쓸 버전·계약·시험이 바뀌면 공통 기준선도 검토합니다.</p>
<div class="note"><strong>현재 버전을 반영한 v2 검토 후보입니다.</strong> 팀 검토 기록은 아직 없고 미커밋 변경이 있습니다. 이번 백엔드 선택 시험은 317/319 통과·실패 2건, 웹 단위 시험은 52/52 통과입니다. DB·외부 API·실제 제품 화면·전체 MVP 판정은 이번 갱신에서 확인하지 않았습니다.</div>
{table(['항목','이 후보의 값'],[
['기준선 ID','<code>triPilot-BL-2026-10-10-v2</code>'],['관측 시각',E(P['captured_at_kst'])+' · KST'],
['종류','프로젝트 통합 기준선 후보. 요구·구현 구성·평가 규칙을 연결한 검토 자료'],
['기존 계획 기준','v11 유지. 이 파일은 계획서 판올림이나 팀 결정의 대체물이 아닙니다.'],
['작성 / 검수','Codex 작성 및 자체 검수. 팀원 독립 검토로 세지 않습니다.'],
['채택 권한 / 기록','프로젝트 책임자와 영향받는 담당자의 검토 후 PR 또는 회의 기록에 채택자·날짜·정확한 버전을 남깁니다. 현재 채택자·채택일은 미기록입니다.'],
['제품 출시 판정','미판정. MVP 완료 기준 전체·실제 외부 소스·고객 경로를 이번 작업에서 통과시킨 것이 아닙니다.']])}
<p class="small">식별·합의·고정·변경 통제라는 개념은 {source_ref('S01')} {source_ref('S10')}에 근거합니다. 이 파일의 절 구성과 ID는 우리 팀에 맞춘 관리안입니다.</p>'''))

baseline.append(('revision','이전 판에서 이번 판으로 바뀐 것',f'''
<p><a href="triPilot-baseline-v1.html">이전 v1</a>을 보존하고 현재 코드·문서·설정을 다시 읽어 v2를 작성했습니다. v11 요구 범위와 MVP 18항목은 바꾸지 않았습니다. 첫 차이 확인에서 기존 수집 범위의 29개 경로가 달라졌으며, 새 명세에는 운영 문서·학습 계획·웹 의존성 잠금 파일도 추가했습니다. 수집 범위에 새로 넣은 파일을 전부 새로 작성된 코드로 세지 않습니다.</p>
{table(['변경 묶음','v2에 반영한 내용','이번 확인'],[
['서비스 개선 자료','새 선택 동의·약관 판·제한된 합성 자료·사람 검토 후 내보내기. 현재 학습판과 별도 경로','새 백엔드 단위 시험과 동의·약관 웹 단위 시험. DB/운영 추출 미확인'],
['이동 경로','자동차 회전 제한 자료를 내용 해시로 비교하고 손상·교체를 재검사','크기·수정시각을 보존한 내용 교체의 5개 회귀 시험 포함'],
['고객 화면','화면 밖 일정 표시·지도 핀·동의 동기화·일정 전체 잠금 해제/복원 동작','웹 6파일 52개 단위 시험. 실제 고객 화면의 종단 검증 아님'],
['버전과 증거',f'현재 {P["file_count"]:,}개 파일과 관측 시각을 다시 기록하고 v1 결과를 현재 결과와 분리','새 명세와 최종 대조. 기존 v1 DB 오류는 이번 실행 결과에 합산하지 않음']])}
<p>학습 모델·학습 자료·레시피는 기존 정본과 다시 대조했으며 이번 작업에서 GPU 학습을 시작하거나 제품 모델을 교체하지 않았습니다.</p>'''))

baseline.append(('scope','제품 범위와 우선하는 근거',f'''
{table(['구분','고정할 기준','근거'],[
['제품·팀','제품 triPilot · 팀 A-COPilot',local('README.md','프로젝트 소개')],
['하는 일','외부가 만든 일정을 받아 성립 여부를 확인하고 여행 종료까지 변경을 감지·재검증·반영·통지합니다.',local(plan_path,'v11 §0·§4-A')],
['대상','서울 1도시 · 최대 7일 · 최대 4인',local(plan_path,'v11 §1·§9-A')],
['MVP','Activity · Dining · Mobility',local(plan_path,'v11 §5·결정 16')],
['MVP 밖','Booking Handoff는 후속 단계. Lodging·Flight는 등록·잠긴 예약 취급. 등록됐다는 이유로 지원 완료로 읽지 않습니다.',local(plan_path,'v11 §5')],
['제품 경계','새 여행 계획 생성은 외부 소유. 우리 DB 안의 일정 조정과 실제 업체 예약 변경을 구분하며 업체 건에는 승인 경계를 지킵니다.',local(plan_path,'v11 §4-A·§4-C')],
['상태와 언어','최신 여행계획서 링크가 상태의 정본. 에이전트 API는 한국어, 링크·알림은 고객 언어. 시각·금액·이름·예약번호는 출처 원값입니다.',local(plan_path,'v11 §6·결정 14')],
['데이터 경계','여행 자료만 현행 판단·시험·평가·시연에 사용합니다. 옛 쇼핑몰 자료는 기록 구역에 남깁니다.',local('wiki/decisions/D-023-no-commerce-assets-in-use.md','D-023')]])}
<p><strong>근거를 읽는 순서:</strong> 현재 사용자 지시와 확인된 후속 결정 → v11의 범위·요구 → 현행 wiki 계약 → 실제 코드·시험의 관측 → 날짜가 붙은 과거 기록입니다. 코드가 요구와 다르면 ‘구현 사실’과 ‘요구’를 나란히 남기고, 임의로 요구를 낮추지 않습니다. 후속 결정이 <code>draft</code>이면 합의된 규칙으로 승격하지 않습니다.</p>
<p>예를 들어 값 조회가 실패했을 때의 ‘멈춤’은 v11에 광범위하게 적혀 있습니다. {local('wiki/decisions/D-018-decision15-stop-paths.md','D-018')}은 현재 구현을 기동 거부·요청별 사람 인계·배치 실패로 설명하지만 아직 draft이며 팀 확인 전에는 현행 동작 기록으로 읽으라고 명시합니다. 이 차이는 아래 채택 전 검토 항목으로 유지합니다.</p>'''))

baseline.append(('layers','공통 기준과 팀별 기준의 관계',hierarchy()+f'''
{table(['관리 단위','이 파일의 절 / ID','공통 기준을 갱신하는 때'],[
['프로젝트 공통','<code>triPilot-BL-2026-10-10-v2</code>','제품 범위·공통 계약·합격 기준·채택 구성·승인 경계 변경'],
['기능 구현','<code>ACT-v1</code> · <code>DIN-v1</code> · <code>MOB-v2</code> · <code>DATA-CONSENT-v1</code>','다른 담당에게 전달되는 입출력·도구·자료 형식·공유 동작 변경'],
['모델 작업 비교','<code>MODEL-SELECT-v1</code> · <code>FT-SALUKI-v1</code>','모델·자료·프롬프트·채점·실행 조건 변경. 제품에 채택할 때 공통 구성에 연결']])}
<p>에이전트 하나가 여러 모델을 쓸 수 있고 모델 하나를 여러 에이전트가 공유할 수도 있습니다. 따라서 ‘에이전트 구축 문서 하나 + 파인튜닝 문서 하나’로 항상 끝나는 구조는 아닙니다. 현재는 이 한 파일의 절로 유지하고, 내용이 커지거나 독립 승인·배포가 필요해지면 해당 절만 별도 파일로 분리해 공통 기준선에 정확한 버전을 연결하는 안을 권합니다.</p>
<p class="small">하나 이상의 관련 관리 대상을 기준선으로 묶을 수 있다는 근거는 {source_ref('S01')}입니다. 여기서 제안한 파일 수·ID·분리 시점은 보편 표준의 강제 형식이 아닙니다.</p>'''))

baseline.append(('versions','현재 버전과 재현 범위',f'''
<p><strong>이 후보는 {E(P['captured_at_kst'])}에 관측한 로컬 작업 상태를 식별합니다.</strong> 커밋만 받으면 같은 제품이 복구된다는 보장은 아직 없습니다. 미커밋 파일·외부 모델·DB·Git 밖 자료도 실행에 영향을 주기 때문입니다.</p>
{table(['대상','확인한 값','고정 범위 / 한계'],[
['Git HEAD',sha(P['git_head']),'작업 브랜치 '+E(P['branch'])+'. HEAD 이후 로컬 변경을 포함하는 관측이며 원격 배포 버전이 아닙니다.'],
['관리 파일',f'{P["file_count"]:,}개 · <a href="project-manifest-v2.json">파일별 해시 명세</a>','앱·시험·설정·프롬프트·여행 지식·여행 분류 평가·웹 소스 및 지정 문서. 전체 작업 폴더 복제본이 아닙니다.'],
['선택 파일 집합 해시',sha(P['tree_sha256']),'경로 + 파일 SHA-256으로 계산. 제외 범위와 경로는 명세에 있습니다.'],
['Python·주요 설치판',E(P['python'])+' · pytest '+E(P['packages']['pytest'])+' · Pydantic '+E(P['packages']['pydantic'])+' · FastAPI '+E(P['packages']['fastapi']),'이번 검사 환경의 설치판. 의존성 파일만으로 완전 잠금됐다는 보장은 아닙니다.'],
['웹 검사 실행 환경','Node '+E(P['node'])+' · Vitest 5.0.1','웹 잠금 파일도 명세에 포함. 최종 검사는 threads 작업자 1개로 실행했습니다.'],
['분류 개발 자료','72건 · '+sha(P['datasets']['travel_golden.jsonl']['sha256']),'AI 작성 초안. 사람 검수 전입니다.'],
['분류 보류 자료','24건 · '+sha(P['datasets']['travel_holdout.jsonl']['sha256']),'AI 작성 초안. 문구·프롬프트 조정에 사용하지 않습니다.'],
['첫 학습 자료',str(C['training_data'].get('rows','미확인'))+'행 · '+sha(C['training_data'].get('sha256','미확인')),'Git 밖 자료. 기존 학습 계획의 해시와 현재 로컬 파일이 일치합니다. 재배포물에 원문을 포함하지 않습니다.'],
['조립 설정',local('final_project_cs/config/project.yaml','현재 프로젝트 선언'),'여행 Team 6개 등록·active. executor=local, broker=outbox, graph=sql, response_review=false. MVP 지원은 그중 3개입니다.'],
['미포함 실행 상태','비밀 환경값·DB 내용·GPU 가중치·실제 배포 revision','담당자가 통제된 경로로 확보해야 합니다. 공용 문서에는 키·접속값을 쓰지 않습니다.']])}
<div class="note"><strong>시점과 현재 상태를 구분합니다.</strong> v1의 1,302개 명세를 덮어쓰지 않고 이번 판의 새 명세를 만들었습니다. 수집 이후 동일성은 <a href="checks/document-audit-v2.json">최종 대조 기록</a>에서 확인합니다. 나중에 코드가 바뀌면 이번 시험이 그 변경까지 검증한 것으로 읽지 않습니다.</div>
<p>채택할 때는 담당자가 검토한 코드·설정·프롬프트를 정확한 커밋에 묶고, Git 밖 자료·모델의 접근 위치와 해시를 비공개 인수 경로에 기록해야 합니다. 깨끗한 임시 사본에서 설치·기동·대표 시험을 다시 실행해 재현 기록을 남깁니다. 태그는 그 커밋을 가리키는 이름으로 쓰며 채택한 태그를 이동시키지 않는 규칙을 둡니다. {source_ref('S06')} {source_ref('S09')}</p>'''))

baseline.append(('contracts','팀 사이의 공통 계약과 책임',f'''
<p>팀 내부 구현을 바꾸더라도 다른 팀이 받는 입력과 결과는 유지해야 합니다. 아래는 현재 계약의 핵심이며 필드 전체는 {local(contract_path,'Team 계약')}과 {local('final_project_cs/app/core/contracts.py','계약 구현')}을 함께 확인합니다.</p>
{table(['항목','현재 기준'],[
['입력','<code>TeamTask</code>, contract_version <code>1.0</code>. 작업·Case·팀·capability·입력 문장·ContextPack·허용 도구·마감·Case 버전을 전달합니다.'],
['출력','<code>TeamResult</code>, contract_version <code>1.0</code>. 결과 상태·답·근거·결정·ActionProposal·다음 행동·실패 코드를 반환합니다.'],
['라우팅','객체 종류 case_type과 요청 종류 intent를 분리합니다. Team의 accepted_case_types로 대상에 도달하고 capability는 Team이 고릅니다.'],
['읽기','현행 여행 Team은 허용 목록·단계 예산을 받는 도구 게이트로 읽습니다. ‘어떠한 직접 읽기도 금지’라는 옛 문장을 현행 구현 사실로 쓰지 않습니다. 관련 불변식 정합성은 채택 전에 검토합니다.'],
['쓰기','Team은 제안만 반환합니다. Core/Action 경로가 소유·근거·대상 객체·멱등성·승인 조건을 확인하고 실행·감사를 남깁니다.'],
['실패·재시도','실패를 성공·사건 없음으로 바꾸지 않습니다. 근거 조회 실패·분류 실패·상태 충돌을 구분하고 중복 반영을 막습니다.'],
['데이터 격리','다른 고객·여행 자료에 접근하지 않으며 LLM 입력과 로그의 개인정보를 가립니다. 이번 판에서는 DB/API 개인정보 통합 검사를 실행하지 않았으며 단위 시험만으로 전체 보장을 선언하지 않습니다.']])}
{table(['담당 역할','공통 기준에 책임질 것','현재 배정 상태'],[
['매니저 / Core','접수·분류 실행·상태 전이·라우팅·통합 구성','README의 Core Runtime 담당을 따릅니다. Access/Action 세부 소유는 아래 미결 항목입니다.'],
['Activity 담당 2명','활동 구현·활동 입력 자료·개별 검증·공유 계약 영향','README의 Activity 배정 유지'],
['Dining / Mobility 담당 각 1명','해당 판정·자료 형식·시간·대체 소스·실행 한계','README의 배정 유지'],
['UI & 검증 담당','고정 평가 자료·채점·회귀·고객 화면과 최신 버전 확인','README의 배정 유지'],
['모델 학습 실험 담당','정확한 학습 대상·자료·레시피·원본 비교·채택 제안','기능별 담당과 연결하되 개인 책임자 확정 기록은 채택 전에 추가']])}
<p>이 배정은 {local('README.md','현재 팀 소개')}를 기준으로 하고 옛 2명 Core·3명 모델 배치를 되살리지 않습니다. {local('wiki/delivery/roles.md','역할 문서')}에도 현재 배치와 옛 배치를 구분하며 Access/Action 담당 공백을 기록했습니다.</p>'''))

teamrows=[]
for slug,v in manifests():
    purpose={'activity':'활동 운영·기상·예약 조건과 대체 일정','dining':'방문 시각의 식사·영업·브레이크·예약 조건','mobility':'이동 가능 시간·경로·환승·출발 안내'}[slug]
    teamrows.append([slug.upper()+'-v1' if slug!='activity' else 'ACT-v1',E(purpose),'<br>'.join('<code>'+E(x)+'</code>' for x in v['capabilities']),local(f'final_project_cs/app/domains/travel_ops/instances/{slug}/team.py','현재 Team 구현')])
# Use concise, stable section IDs rather than spelling the whole team name in the ID.
teamrows[1][0]='DIN-v1';teamrows[2][0]='MOB-v2'
baseline.append(('agents','에이전트 구현 기준 ACT DIN MOB',f'''
<p>세 Team은 공통 계약 1.0을 구현하고 현재 manifest의 단계 예산은 각각 <strong>12</strong>입니다. 규칙·시간·금액처럼 계산 가능한 판정은 코드가 맡고, 모델을 쓴다는 이유로 계산 결과를 지어내지 않습니다. Team 수가 곧 LLM 수나 학습 모델 수를 뜻하지 않습니다.</p>
{table(['세부 기준 ID','담당 범위','현재 선언된 capability','코드 근거'],teamrows)}
<p>세 Team 모두 case_state·policy·db_facts·history를 요구하며 일정 관리 capability인 <code>activity.itinerary</code>·<code>dining.itinerary</code>·<code>mobility.itinerary</code>는 정책 RAG 예외로 선언돼 있습니다. 규정 질문 capability까지 임의로 예외에 넣지 않습니다.</p>
{table(['고정 시험의 예','기대 행동','검사 목적'],[
['15:00 식사 / 브레이크 15:00~17:00','그 시각 식사를 성립으로 확정하지 않고, 근거로 재검증한 시간 또는 장소 변경을 제안','Dining 계산 경계. 설명용 통제 입력이며 실제 식당 관측이 아닙니다.'],
['실내 관람 / 야외 기상 악화','활동 속성에 맞는 소스와 규칙만 적용','Activity의 범위를 레저·예약 활동만으로 좁히지 않음'],
['앞 일정 종료 / 다음 장소 시작 사이 이동 시간 부족','충돌을 표시하고 전체 일정 재검증을 통과한 변경만 반영','Mobility와 다른 Team의 공유 일정 영향'],
['동일 사건 재접수 / 다른 대상 제안 2개','같은 변경은 중복 적용하지 않으며 다른 대상의 정당한 제안은 각각 보존','Core·Team 통합 경계'],
['임시휴무 식당이 있던 옛 일정으로 되돌림','현 상태를 다시 확인하고 복원 가능성을 판정','과거 버전을 그대로 복사해 현실과 어긋나지 않음']])}
<p class="small">위 예는 기준을 이해하기 위한 시험 계약입니다. 이번 작업에서 해당 다섯 시나리오를 새로 실행했다는 뜻은 아닙니다. 실제 실행 결과와 도구·외부 자료의 버전은 시험 보고서로 연결해야 합니다.</p>'''))

baseline.append(('data-consent','서비스 개선 자료와 고객 화면의 현재 기준',f'''
<p><strong>DATA-CONSENT-v1:</strong> 서비스 개선용 합성 자료는 현재 여행 질의 학습판과 다른 자료 경로입니다. 선택 동의 하나를 추가했다고 기존 고객 대화·위치·건강 정보를 학습에 사용할 수 있게 된 것은 아닙니다.</p>
{table(['항목','v2가 고정하는 현재 구현','확인 근거'],[
['동의 판과 항목','기본 약관 버전 2026-10-10.1. 총 6항목 중 필수는 service_terms·privacy, 선택은 sensitive·location·alert_channel·service_improvement. 새 개선 동의 기본값 false. 이전 동의를 새 항목 동의로 간주하지 않음',local('final_project_cs/frontend/apps/web/src/features/consent/consent-model.ts','웹 항목 선언')+' · '+local('final_project_cs/config/guardrails.yaml','기본 설정')],
['추출 조건','현재 판의 필수 둘과 개선 동의를 모두 확인. 일반 동의 게이트가 꺼져 있어도 이 검사는 생략하지 않음. 최근 이용·보유기간 안의 사용자별 최신 여행 한 개',local('final_project_cs/app/domains/travel_ops/components/customer/service_improvement.py','현재 개선 자료 구현')],
['읽고 내보내는 값','인원 수·일정 날짜 수·하루당 일정 개수의 구간 값만 합성. 이용자/여행 ID·질문/답변·제목·장소·좌표·예약번호·날짜 원값·건강/종교/식사 제한을 합성 출력에 넣지 않음','단위 시험의 출력 스키마·금지 필드 검사. 실제 운영 DB 추출은 미실행'],
['생성과 검토','tenant별 최대 생성 4회·합성 500행·잡음 처리 표본량 하한 50. 후보 7일, 승인본 1,825일 상한, 재검토 365일. 승인 전 내보내기·학습 사용 금지. 실제 이용 근거·재식별·유용성 검토 증빙과 후보 해시 필요',local('final_project_cs/wiki/operations/service-improvement.md','운영 계약')],
['철회와 파기','필수 또는 개선 동의 철회 시 대기 후보 폐기·다음 추출 제외. 연결표 없는 승인 합성본은 개인별 회수 불가. 개선 동의가 원본 보유기한을 늘리거나 파기를 미루지 않음','동의/개선 코드의 계약. 실제 철회 트랜잭션·정리 작업의 이번 DB 검증은 미실행'],
['배포·효력 한계','로컬 코드/마이그레이션 구현. 기본 consent.gate_enabled=false, retention.purge_mode=dry_run. 새 약관·DB 변경의 운영 반영을 이 문서에서 확인하지 않음','코드 존재·단위 시험과 실제 운영 상태를 분리'],
['약관 표시의 의미','웹 TERMS_STATUS=reviewed는 사용자 결정으로 초안 안내를 내린 상태를 포함. 변호사 검토 완료나 법률상 익명성 판정을 뜻하지 않음',local('final_project_cs/frontend/apps/web/src/features/consent/terms-content.ts','약관 판·표시 주석')]])}
<h3>MOB-v2와 웹 검토 동작</h3>
<p>자동차 회전 제한 파일은 요청마다 읽은 바이트의 SHA-256으로 내용 판을 비교합니다. 크기·수정시각이 같아도 내용이 바뀌면 그래프 결합과 방향 관계를 다시 검사하며 삭제·손상·읽기 오류는 RouterDown으로 드러냅니다. 같은 내용은 적재한 표를 재사용합니다. 도보·자전거 및 기존 정적 단순 제약 범위는 유지하며 도로 그래프 자체의 같은 메타데이터 교체·탐색 도중 변경·실제 운행 정확도까지 보장하지 않습니다. {local('final_project_cs/wiki/teams/mobility.md','Mobility의 2026-10-10 내용 갱신 계약')}</p>
<p>웹 검토에서는 잠긴 일정 전체를 한 번의 수정 요청으로 해제하고, 전체 복원은 당시 판과 현재 판을 확인하는 요청으로 처리합니다. 거절 시 현재 값을 보존하며 오래된 판은 다시 읽습니다. 지도 바깥 일정 표시와 핀의 단위 시험도 재실행했습니다. 함수 대역과 정적 렌더링을 사용하는 이 시험을 실제 브라우저·DB·API 전체 경로의 통과로 세지 않습니다.</p>'''))

baseline.append(('models','모델 비교와 파인튜닝 기준',f'''
<h3>MODEL-SELECT-v1 — 무엇과 비교할지 고정</h3>
<p>고객 질문이 가리키는 일정 항목을 고르는 작업에서는 <strong>우리 자료 추가 학습 없는 정확한 원본 모델</strong>을 먼저 보존합니다. 그 원본과 우리 학습판을 같은 문항·정보·출력 계약·채점·엔진 조건에서 비교합니다. 에이전트 전체 개선과 학습 자체의 효과를 별도로 봅니다. {source_ref('S08')}</p>
{table(['고정 항목','우리 기준'],[
['모델','저장소 ID·revision·가중치 해시·Base/Instruct 구분·개발사 학습 여부·우리 추가 학습 여부'],
['조건','양자화·엔진 버전·프롬프트/도구 계약 해시·토큰 제한·temperature·seed·판정 문턱'],
['자료','개발 / 학습 / 독립 최종 보류를 분리하고 ID·해시·일정군·정답 검수 상태를 기록'],
['비교','원본 vs 같은 원본의 학습판. 다른 모델·다른 양자화·다른 검색기를 함께 바꾸면 학습 효과 단독 비교로 쓰지 않음'],
['지표','정상 요청 정답 수/전체, 요청 없음 오지목 수/전체, 복합·혼합 부류, 형식 실패·오류·지연·메모리'],
['불확실성','같은 문항 짝의 차이, 반복 시드·편차·구간. 모든 실패·미완료를 계획 분모에 보존'],
['현행 혼합 평가 기준','선택 ≥95%, 오지목 ≤1%, 선택 손실 ≤2%p, 오지목 증가 ≤1%p, 지정 부류 ≤3%. 현행 모델 평가 문서의 개발·회귀 기준이며 제품 채택을 단독 보장하지 않음']])}
<p>근거: {local(slm_path,'모델 평가 정본')}. Jev 계열 모델을 비교하면 Winnow-E4B 등 정확한 이름과 우리 학습 여부를 함께 적습니다. ‘학습 없는 원본’과 ‘가르친 모델’의 점수를 같은 상태처럼 섞지 않습니다.</p>
<h3>FT-SALUKI-v1 — 현재 첫 학습 실험의 기준</h3>
{table(['항목','현재 기록과 고정 범위'],[
['정확한 대상','<code>ConwayResearch/Underdog-Saluki-27B-1.0</code>, revision <code>1336c0b5d74dfe6ad7f793577092f5effd9f97c6</code>. 2026-10-09 학습 준비 기록에 고정된 대상이며 현재 GPU 상태를 다시 확인한 값은 아닙니다.'],
['학습 자료','기존 train_oos2 2,613행. 현재 로컬 건수·해시 일치. 추가 900행은 두 AI 합의 기록이며 사람 900행 검수로 표시하지 않습니다.'],
['첫 레시피','rank 8 · 최대 학습률 2e-5 · 1 epoch · cosine 제안. 구현·지원·메모리 검증 뒤 실행할 계획값입니다. 학습 실측 결과가 아닙니다.'],
['대조군','동일 Saluki 원본 보존. 학습 전후 비교 뒤 배포 양자화의 영향을 별도 확인'],
['실험 진입','동일 가중치의 학습 표현·CUDA 역전파·실제 메모리/공간·기존 작업 잠금 조건을 확인. 다른 Underdog나 Qwen 모델로 몰래 대체하지 않습니다.'],
['새 평가와 관계','새 F 시험·독립 보류 완성은 기존 자료로 첫 연결 검사·학습을 하는 선행조건이 아닙니다. 제품 채택 전에 사람 검수·독립 보류는 필요합니다.'],
['Saluki 계획의 별도 제안 목표','정상 요청 차이의 신뢰구간 하한 ≥−1%p, 독립 보류 오지목 ≤2%. 일반 혼합 시험의 ≤1%와 서로 다르므로 제품 채택 규칙을 사전 합의하기 전 완화된 값으로 대체하지 않습니다.'],
['현재 지위','학습 준비 계획. 이 문서 작업은 GPU 학습·평가·제품 모델 교체를 실행하지 않았습니다.']])}
<p>근거: {local(train_path,'Saluki 첫 학습 계획')} · {local('final_project_cs/wiki/records/reports/2026-10-09_1208_saluki-reviewed-set-baseline.md','기존 검토 자료를 사용하는 실험 기록')}.</p>
<h3>새 통합 답변 시험의 지위</h3>
<p>{local(f_path,'대상 선택·근거·답변 시험 F-v1')}은 제안 계약입니다. 개발 480개·독립 보류 720개는 계획 수량이며 완료된 정답 자료가 아닙니다. 기존 D/E의 채점이나 제품 intent를 바꾸지 않습니다. 선택 전용 모델의 능력과 근거를 찾고 답하는 전체 파이프라인의 능력을 구분합니다.</p>'''))

dod_rows=[
('1','접수·최신 버전 반환','자동'),('2','시간·이동·예산·동행 조건 검증','자동'),('3','불가능한 일정의 이유·완화 조건','자동'),('4','판정 근거의 출처·확인 시각','자동'),('5','1차·대체 조회와 실패 처리','자동 / 멈춤 범위 합의 필요'),('6','다음 확인 시점의 Case 생성','자동'),('7','변경 감지·재계획·재검증 뒤 통지','자동'),('8','고객 재요청으로 복원·교체','자동'),('9','복원 후에도 이력 보존','자동'),('10','한계에서 근거를 붙여 사람 인계','자동'),('11','다른 여행의 상태 접근 차단','자동'),('12','중복 변경의 중복 적용 방지','자동'),('13','Team의 직접 실행 차단','아키텍처'),('22','시나리오 필수 조건 위반 0건','측정'),('23','등록된 모든 Team의 라우팅 도달','아키텍처'),('24','같은 Case의 다른 대상 제안 분리','자동'),('25','알림 유실에도 링크의 최신 일정·변경 이유','자동'),('26','목적지·출발시각·경로 안내 및 중복 발행 방지','자동')]
baseline.append(('acceptance','MVP 완료 판정과 이번 검사 결과',f'''
<p>v11은 전체 26항목 중 Booking Handoff 몫 14~21을 뺀 <strong>18항목</strong>으로 MVP를 판정합니다. 이 문서가 그 항목을 갖췄다는 것과 제품이 모두 통과했다는 것은 다릅니다. 아래 18개를 이번 문서 검수의 합격 개수로 세지 않습니다.</p>
{table(['v11 번호','검사할 동작','판정 방식'],dod_rows)}
<p>연결된 실제 시험 목록은 {local('final_project_cs/scripts/verify_dod_v11.py','v11 검증기')}의 18개 MVP 대상에서 확인합니다. 문서·코드의 필수 조건 위반 0건, 재검증·출처 시각 표시 100% 목표는 {local(plan_path,'v11 §8·§12')}를 따르며, 실제 분모와 실행 조건 없이 통과 수치를 만들지 않습니다.</p>
{table(['이번 실행','결과','증명 범위'],[
['여행 분류 자료 검사','96/96행 형식·어휘 검사 통과','golden 72·holdout 24, 전부 claude-draft. 모델 정확도·사람 검수·독립성 증명 아님'],
['백엔드 선택 시험',f'{counts["passed"]}/{C["selected_total"]} = {counts["passed"]/C["selected_total"]*100:.2f}% 통과 · 실패 2 · 오류 0','공통 계약·구조 236/238 + 변경 기능 단위 81/81. 총 6파일. 전체 제품 시험의 통과율이 아님'],
['관련 웹 단위 시험','52/52 = 100% 통과','동의 동기화·약관/본문 해시·지도 바깥 일정·핀·전체 복원. 6파일의 단위 시험이며 실제 제품 화면 종단 검증 아님'],
['DB·전체 MVP·넓은 시험','이번 갱신에서는 실행하지 않음','v1의 중단·DB 오류 기록은 보존하지만 v2의 새 결과에 합산하지 않음'],
['실제 제품·소스 응답','실서버 확인(서버 응답): 안 했음','x600 서버의 cs 프로젝트 서버, 외부 API, GPU 모델 품질은 이번 작업에서 재측정하지 않음'],
['화면 반응 대역 시험','mock 서버 시험: 이번 작업에서는 실행하지 않음','문서 HTML 렌더링 검사와 제품 화면 반응 검사를 혼동하지 않음']])}
<p><a href="checks/project-checks-v2.json">이번 제품 확인의 기계 판독 결과와 명령</a>을 보존했습니다. 직접 import 실패 중 1건은 백업 폴더, 1건은 현행 이동 코드입니다. 따라서 ‘백업만 제외하면 모두 해결’이라고 결론 내리지 않습니다. 새 시험의 첫 실행에서 임시 폴더/SSR 파일 오류가 있었으나, 쓰기 가능한 시험 폴더 및 단일 threads 작업자를 지정한 재실행은 통과했습니다. 첫 오류 기록도 보존했습니다. 이전 개인정보 DB 시험에는 쇼핑몰 분류 fixture가 있어 현행 여행 검사에서 제외했고 DB/API 개인정보 검증은 미확인으로 남겼습니다.</p>
<div class="expanded"><h3>재실행 명령과 예상 결과</h3><p>작업 폴더는 {local('final_project_cs','릴리스 대상 앱 폴더')}입니다. 의존성 설치와 시험용 DB 준비는 기존 운영 문서를 따르고 운영 DB를 시험용으로 쓰지 않습니다.</p><pre>python -m scripts.verify_travel_eval_datasets
python -m pytest tests/contract/test_team_contract.py tests/contract/test_core_isolation.py tests/contract/test_team_tool_discipline.py tests/architecture/test_basement_is_domain_free.py -q -m "not live"
python -m pytest tests/unit/test_service_improvement.py tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py -q --basetemp=&lt;새로 만든 쓰기 가능한 시험 폴더&gt;

# 아래는 채택 검증 단계에서 실행할 명령입니다. 이번 작업의 통과 결과가 아닙니다.
python -m scripts.verify_dod_v11
python -m pytest tests/contract tests/security -q -m "not live"</pre><p>자료 검사는 첫 줄에 72·24건과 라벨 출처를 표시하고 마지막에 ‘통과’를 내야 합니다. 제품 시험은 실패·오류·건너뜀을 모두 기록하며, DB 시험이 연결되지 않으면 채택 검증을 완료한 것으로 세지 않습니다.</p></div>'''))

baseline.append(('gaps','채택 전에 닫을 항목과 담당',table(['항목','현재 근거','닫는 방법 / 담당'],[
['채택 기록','검토자·채택자·날짜 미기록','프로젝트 책임자와 영향 담당이 이 판·예외·적용 범위를 검토하고 PR/회의 기록으로 채택'],
['정확한 재현 버전','미커밋 코드와 Git 밖 자료가 있어 HEAD만으로 재현 불가','통합 담당: 승인된 커밋 + 자료·모델 해시 + 비공개 접근 경로 + 깨끗한 사본 재현 기록'],
['Team 경계 실패','이동 현행 코드의 ports 직접 import와 백업 검사 실패','Mobility + Core + 검증: 해당 의존이 순수 공유 계약인지 실제 외부 접근인지 검토 후 계약 또는 구조를 수정하고 회귀 시험'],
['개인정보 DB 확인','v2에서는 DB/API 개인정보 통합 검사 미실행','API/보안 소유 담당 + 검증: 격리된 시험 DB로 실제 저장·조회·감사 마스킹 검사'],
['조회 실패의 멈춤 범위','v11 문구와 draft D-018 설명 사이의 승인 지위 차이','프로젝트 책임자 + Core + Team: 기동·요청·배치별 필수 소스와 실패 동작을 명시적으로 확정'],
['평가 정답과 독립성','분류 96건 AI 초안·F-v1 계획·추가 학습 자료의 AI 검토 범위','검증 + 도메인 담당: 사람 정답 검수, 일정군·의미 중복 확인, 최종 보류 해시 잠금'],
['파인튜닝 채택 문턱','일반 혼합 기준과 Saluki 별도 제안 목표가 다름','모델 담당 + 검증 + 책임자: 목적·세트·지표별 문턱을 최종 답안 확인 전에 고정'],
['개선 자료의 운영 적용','새 선택 동의·합성/검토 경로는 로컬 구현. 운영 약관·DB 반영과 실제 자료 검토 미확인','개인정보/운영 담당 + 검증: 동의·철회·검토·내보내기·만료의 DB 검증과 실제 검토 증빙. 원본 정리 dry_run 및 배포 상태 확인'],
['실행과 출시','외부 소스·최신 링크·출발 안내·MVP 18항목의 이번 전체 재검증 없음','통합 + 각 Team + 검증: 시험·실제 소스·화면을 분리해 기록하고 전체 판정'],
['책임 공백','현행 역할 문서의 Access/Action 소유자 미확정','책임자: 인증·승인·멱등성·감사의 검토/수정 책임자를 기록']])+'<p>이 목록은 문서의 빈칸을 숨긴 것이 아니라 채택 관문입니다. 알려진 결함이 있는 개발 기준을 팀이 제한된 범위에서 합의할 수는 있지만, 그 경우 예외·소유자·종료 조건을 기록하고 출시 합격으로 표시하지 않습니다.</p>'))

baseline.append(('changes','이 기준선에서 작업하고 갱신하는 법',workflow()+f'''
<ol><li><strong>작업 시작:</strong> 팀원이 같은 기준선 ID·코드 커밋·자료 해시를 확인하고 자기 기능 브랜치에서 작업합니다. 공통 계약을 먼저 읽습니다.</li>
<li><strong>변경 검토:</strong> 목적·영향받는 Team·변경 전후·재현 명령·실측·되돌릴 판을 PR에 적습니다. 평가 자료나 문턱을 바꾸면 새 결과를 옛 결과와 같은 조건처럼 비교하지 않습니다.</li>
<li><strong>통합:</strong> 영향받는 계약·회귀 시험을 실행하고 담당자가 검토합니다. 기능 내부 수정은 일상 통합으로 처리하고 공통 기준이 바뀌는 시점에 새 기준선 후보를 만듭니다.</li>
<li><strong>새 기준선 채택:</strong> 다음 v3 후보에 새 커밋·구성·시험·채택 기록을 넣고 이번 v2를 보존합니다. 이전 기준선·실험 원본·실패 결과를 덮어쓰지 않습니다.</li></ol>
<p>PR 검토 흐름은 {source_ref('S05')}, 자주 통합하고 자동으로 상태를 확인하는 원칙은 {source_ref('S07')} {source_ref('S11')}, 기준 구성과 변경 묶음을 구분하는 개념은 {source_ref('S02')}를 참고했습니다. 모든 팀에 동일한 승인 인원·파일 수를 강제하는 규칙은 아닙니다.</p>
<div class="expanded"><h3>팀이 남길 채택 기록 예시</h3><pre>기준선 ID: triPilot-BL-2026-10-10-v2
적용 범위: [개발 공통 기준 / 출시 후보 중 정확한 범위]
채택 코드: [실제 검토한 전체 커밋]
자료·모델 명세: [접근 가능한 버전·해시 기록]
검토 기록: [PR 또는 회의 기록]
채택자·날짜: [실제 합의 후 기입]
허용한 예외·담당·종료 조건: [있으면 기록]
다음 기준선으로 바꿀 조건: [공통 계약·범위·채택 구성 변경 등]</pre><p>위 양식은 아직 채워지지 않은 채택 기록의 예시입니다. 예시를 실제 채택 증거로 사용하지 않습니다.</p></div>'''))
baseline.append(('references','공식 자료와 적용 범위',refs()))

guide=[]
guide.append(('answer','무엇을 몇 개 만들어야 하나',f'''
<p><strong>지금은 프로젝트 공통 기준선 한 파일 안에 기능 구현 기준과 모델 비교 기준을 넣으시면 됩니다.</strong> 팀원마다 문서 한 개씩 만드는 방식은 권하지 않습니다. 사람이 바뀌어도 기능의 계약과 비교 조건은 남아야 하기 때문입니다.</p>
{table(['질문','지금 우리 팀에 맞는 답'],[
['프로젝트당 하나인가요?','현재 함께 채택할 통합 구성은 공통 기준선 하나로 연결합니다. 과거 판·여러 릴리스·여러 제품 구성은 각각 존재할 수 있습니다.'],
['기능·에이전트별로도 있나요?','독립해서 버전과 책임을 관리할 대상이면 세부 기준을 둡니다. 현재는 Activity·Dining·Mobility 절로 충분하며 각자 별도 파일일 필요는 없습니다.'],
['구축과 파인튜닝은 따로인가요?','목적이 달라 기록을 나눕니다. 구축은 시스템의 입력·출력·권한·실패 동작을, 학습은 고정 대조군과 개선 실험을 관리합니다.'],
['몇 개·비용·시간인가요?','지금 전달한 파일은 공통 기준선 1개와 이 작성법 1개입니다. 파일 열람·검토 자체는 별도 유료 도구가 필요 없습니다. 첫 검토 회의 30~60분은 예상이며, 학습·실제 소스 재검증 시간과 비용은 별도입니다.']])}
{hierarchy()}
<p>표준에서 말하는 기준선은 팀이 특정 시점에 식별·합의해 둔 관리 대상입니다. ML에서 말하는 baseline은 개선을 견줄 모델·방법과 점수라는 뜻으로도 씁니다. <strong>학습 전 모델을 정했다고 팀 협업 기준선이 완성되는 것도, 문서를 썼다고 모델 비교가 끝나는 것도 아닙니다.</strong> {source_ref('S01')} {source_ref('S08')}</p>
<p><a href="triPilot-baseline-v2.html">우리 프로젝트에 실제로 작성한 기준선 열기 →</a></p>'''))

guide.append(('prepare','작성 전에 네 가지를 모으기',f'''
<ol><li><strong>범위와 결정:</strong> 무엇을 제공하고 무엇을 제외하는지 v11·후속 결정에서 확인합니다.</li><li><strong>정확한 대상:</strong> 코드 커밋, 설정·프롬프트·데이터·모델 버전과 해시를 모읍니다. 최신이라는 말만 쓰지 않습니다.</li><li><strong>기대 결과와 실측:</strong> 동일 입력의 기대 동작, 실행 명령, 실제 통과·실패·오류를 함께 모읍니다.</li><li><strong>책임과 변경:</strong> 누가 검토·채택하는지, 무엇이 바뀔 때 다시 검토할지 정합니다.</li></ol>
<p>우리 팀은 이미 계획서 v11, Team 계약, 모델 평가 절차를 갖고 있습니다. 새 기준선은 이를 복사해 서로 다른 규칙을 만들기보다 정확한 판을 연결하는 역할을 합니다. {source_ref('S01')} {source_ref('S06')}</p>
<p>이번 v2처럼 코드가 바뀌면 해시 명세와 시험을 다시 확인하고, 적용 범위가 다른 자료는 목적별로 나눕니다. 서비스 개선용 합성 자료를 만들 수 있다는 것과 고객 질문으로 모델을 학습할 수 있다는 것을 같은 허가로 읽지 않습니다. 동의 판·읽는 항목·사람 검토·보관 조건까지 연결해야 합니다.</p>
{table(['가져올 것','실제 위치','열었을 때 확인할 것'],[
['제품 범위',local(plan_path,'v11 계획서'),'서울·7일·4인, MVP 3팀, MVP 판정 18항목'],
['팀 입출력',local(contract_path,'Team 계약'),'입력/결과 1.0, 제안과 실행의 분리'],
['모델 비교',local(slm_path,'현재 모델 평가 절차'),'원본·우리 학습판·개발·최종 보류의 분리'],
['작성한 통합 후보','<a href="triPilot-baseline-v2.html#versions">이번 기준선의 버전 절</a>','실제 커밋·선택 파일 해시·미커밋 한계'],
['자료와 실행 근거','<a href="source-manifest.json">외부 자료 명세</a> · <a href="checks/project-checks-v2.json">현재 검사 결과</a>','출처 URL·확보일·해시, 성공과 실패의 분모']])}'''))

guide.append(('write','기준선을 작성하는 네 단계',f'''
<h3>1. 첫 문장에서 대상과 지위를 정합니다</h3><p>‘무슨 문서인지’보다 ‘팀이 무엇을 같이 쓸지’를 적습니다. 합의 전이면 검토 후보, 합의 후면 채택 기록을 붙입니다.</p><pre>서울 여행 일정 검증·변경 관리의 공통 개발 기준입니다.
ID: triPilot-BL-2026-10-10-v2
지위: 팀 검토 후보
적용 범위: Activity·Dining·Mobility와 공통 Core·UI
기존 계획: v11 유지</pre><p><strong>끝나면 보일 것:</strong> 팀원이 범위와 아직 합의 전이라는 사실을 첫 화면에서 알 수 있어야 합니다.</p>
<h3>2. 함께 고정할 구성을 적습니다</h3><p>공통 계약·코드·설정·자료·모델·도구를 버전으로 묶습니다. 모델 가중치나 비밀값까지 HTML 안에 넣을 필요는 없습니다. 통제된 보관 위치와 해시로 연결합니다.</p><pre>공통 계약: TeamTask / TeamResult 1.0
코드: 검토한 정확한 커밋 + 미커밋 변경 유무
설정·프롬프트: 파일 또는 활성판 ID + SHA-256
자료: 판 이름·행 수·SHA-256·정답 검수 상태
모델: 정확한 ID·revision·가중치 해시·우리 학습 여부</pre><p><strong>끝나면 보일 것:</strong> 두 팀원이 같은 대상을 확인할 수 있고, 아직 재현할 수 없는 부분은 원인과 담당이 표시돼야 합니다.</p>
<h3>3. 기대 동작과 현재 결과를 나란히 적습니다</h3><p>예를 들어 15시 식사인데 브레이크가 15~17시면 성립으로 확정하지 않는다고 적습니다. 이어 그 기대를 검사하는 명령과 실제 결과를 적습니다. 설명용 예를 실제 식당 관측이나 통과 기록으로 바꾸지 않습니다.</p><pre>기대: 방문 시각과 브레이크가 겹치면 근거를 붙여 변경을 검토
실행: 실제 시험 파일·명령·입력 자료 판
결과: 통과/실패/오류·분자/분모·실행일·조건
남은 것: 외부 소스·화면·독립 평가 중 무엇을 아직 확인하지 않았나</pre><p><strong>끝나면 보일 것:</strong> 목표와 현황을 혼동하지 않고, 실패도 같은 분모 안에서 읽을 수 있어야 합니다.</p>
<h3>4. 채택과 변경의 절차를 붙입니다</h3><p>담당 검토, 합의 기록, 적용할 정확한 판, 이전 판 보존 방법을 적습니다. 모든 코드 변경에 새 기준선 파일을 만들기보다 공통 기준이나 채택 구성이 달라질 때 새 판을 수립합니다.</p><p><strong>끝나면 보일 것:</strong> 팀원이 지금 어디서 작업을 시작하고 어떤 변경을 누구에게 검토받을지 알 수 있어야 합니다.</p>
{workflow()}'''))

guide.append(('agent-vs-ft','에이전트 구축과 학습을 구분하는 예',f'''
{table(['비교','에이전트 구현 기준','파인튜닝 비교 기준'],[
['질문','이 에이전트가 어떤 입력으로 무엇을 하고 어디서 멈추는가?','같은 작업에서 우리 학습이 원본보다 무엇을 개선했는가?'],
['대상','Team 계약·도구·자료·권한·검색·실행·실패 처리','원본 모델·학습 자료·레시피·어댑터·고정 평가·실행 조건'],
['우리 예','Dining: 방문 시간과 영업·브레이크를 대조하고 제안만 반환','일정 항목 선택: 같은 원본 vs 우리 여행 자료 학습판의 정답·오지목 비교'],
['학습을 안 하면','구현 기준은 그대로 필요','규칙·임베딩·학습 없는 모델을 비교 기준으로 둘 수 있음'],
['한 사람이 둘을 하면','각 목적의 정보를 같은 담당이 적음','그래도 평가의 의미와 버전은 구분'],
['프로젝트에 반영','공통 계약을 지켜 합친 구성으로 검사','개발 개선·독립 검증·제품 채택을 거쳐 실제 채택 모델을 공통 기준에 연결']])}
<div class="note">예: Activity 담당자가 두 명이어도 Activity 기준을 두 벌 만들 필요는 없습니다. 한 분이 검색, 다른 분이 후보 판정을 맡으면 같은 Activity 절 안에 하위 작업과 소유 경계를 적습니다. 검색 모델과 항목 선택 모델을 각각 학습한다면 서로 다른 작업이므로 비교 기준도 각각 기록합니다.</div>
<p>반대로 모든 에이전트가 동일한 항목 선택 모델을 사용한다면 모델 기준을 한 번 관리하고 각 기능에서 그 버전을 참조하면 됩니다. 사람·에이전트·모델은 서로 일대일로 대응하지 않습니다.</p>'''))

guide.append(('review','검사하고 수정하는 기준',f'''
<p>완료 조건은 ‘읽어 보니 좋아 보임’이 아니라 아래 검사를 만족하는 것입니다. 다만 문서 검수를 통과해도 팀 합의·외부 실측·제품 출시가 자동으로 완료되지는 않습니다.</p>
{table(['검사','통과 조건','걸리면 고치는 방법'],[
['대상·지위','범위·ID·판·채택 여부가 첫 화면에 있음','합의가 없으면 후보로 바꾸고 실제 채택 기록을 관문으로 남김'],
['원문 대조','요구·구현·과거 기록·제안이 구분되고 링크가 실제로 열림','날짜가 오래된 성과를 빼고 현행 코드·자료·결정으로 연결'],
['재현','커밋·자료·모델·프롬프트·환경을 식별 가능','미커밋·비공개 의존·자료 누락을 밝히고 확보 책임을 기록'],
['공정한 모델 비교','동일 작업·자료·계약·채점, 원본/학습판 구분','같이 바뀐 검색기·양자화·엔진을 고정하거나 별도 실험으로 분리'],
['수치','분자·분모·반복·조건·오류·검수 수준이 보임','실패·누락을 분모에 복원하고 AI 라벨을 사람 검수로 적지 않음'],
['책임과 변경','검토자·채택자·영향 담당·판올림·이전 판 보존이 정의됨','빈 책임을 임의 배정하지 말고 실제 팀 합의 항목으로 남김'],
['HTML 화면','목차·본문·링크·그림이 읽히고 인쇄·좁은 화면에서도 내용에 접근 가능','잘림·겹침·대비·접근성·모바일 가로 접근을 수정 후 재확인']])}
<p>이 후보에서는 이미 실제 검사 실패를 기록했습니다. 이를 지워서 ‘완벽한 기준선’으로 보이게 만들지 않습니다. <a href="triPilot-baseline-v2.html#gaps">현재 채택 전 항목</a>과 <a href="review-report-v2.html">문서 검수 기록</a>을 확인하시면 됩니다.</p>
<h3>자주 잘못 쓰는 문장</h3>
{table(['문제 문장','고친 문장'],[
['팀원별로 baseline 파일 하나씩 작성','관리 대상별로 기준을 두고 담당자를 연결. 공통 기준에 정확한 판을 모음'],
['최신 코드로 실행','검토한 커밋과 로컬 변경을 식별하고 자료·모델·프롬프트 해시 기록'],
['학습했으니 성능 향상','고정된 같은 문항에서 원본/학습판 차이·오지목·손실·구간 보고'],
['96건 검수 완료','96건 형식 검사 통과, AI 작성 정답 초안(claude-draft), 사람 검수 전'],
['시험 317개 통과로 제품 완료','백엔드 선택 시험 319개 중 317통과·2실패. 웹 52/52는 별도 단위 시험. 전체 제품 완료는 미판정'],
['문서 만들었으니 팀 기준선 확정','검토 후보 작성 완료. 실제 채택 기록이 생긴 뒤 팀 기준선으로 적용']])}'''))

guide.append(('history','참고 자료를 어떻게 해석했나',f'''
<p>기준선은 한 회사가 최근 만든 협업 양식이 아닙니다. 미 공군 공식 역사는 1958~1960년 Minuteman의 기술 변경·비용·일정 통제를 연결한 과정과 1962년 관리 절차 확산을 다룹니다. 같은 역사는 Boeing과 공군 중 어느 쪽이 최초였는지 확정할 수 없다고 밝힙니다. 따라서 최초 발명자 한 명을 단정하지 않습니다. {source_ref('S03')}</p>
<p>소프트웨어 쪽에서는 SEI의 1991년 보고서가 기준 구성에 변경 묶음을 더해 구성 판을 만드는 모습을 설명합니다. 현재 용어의 주 근거는 SWEBOK의 구성 관리 장이고, 현대 협업 절차는 GitHub·DORA, ML 비교의 출발점은 Google의 자료를 사용했습니다. {source_ref('S02')} {source_ref('S01')} {source_ref('S05')} {source_ref('S06')} {source_ref('S08')}</p>
<p><strong>근거가 말하는 원칙</strong>은 식별·합의·변경 통제·재현·비교입니다. <strong>우리 팀에 적용한 형식</strong>은 ‘공통 한 파일 + 기능별 절 + 모델 작업별 절’입니다. 이 파일 형식을 IEEE가 의무화했다고 읽지 않으시면 됩니다.</p>'''))
guide.append(('references','내려받은 자료와 읽은 범위',refs()))

def save(name,content):
    target=HERE/name
    if target.exists():
        backup=HERE/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_documents')
        backup.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup/name)
    target.write_text(content,encoding='utf-8')
    print(name,len(content.encode('utf-8')),'bytes')

if __name__=='__main__':
    save('triPilot-baseline-v2.html',page('triPilot 프로젝트 기준선 검토 후보 v2','현재 코드·동의 정책·이동·웹 변경을 반영한 공통 기준입니다.',baseline,'baseline-writing-guide-v2.html','베이스라인 작성법'))
    save('baseline-writing-guide-v2.html',page('우리 팀의 베이스라인 작성법 v2','무엇을 하나로 묶고 무엇을 따로 비교하는지, 현재 기준선을 보며 작성·검토하는 방법입니다.',guide,'triPilot-baseline-v2.html','프로젝트 기준선'))
