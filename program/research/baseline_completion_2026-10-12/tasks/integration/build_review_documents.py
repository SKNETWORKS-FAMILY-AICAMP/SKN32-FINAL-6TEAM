"""검토본 두 문서와 시작·끝·조건이 있는 오프라인 SVG를 생성한다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, html, json, re, shutil
import markdown

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
stamp=datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d_%H%M%S')
def backup(p):
    if p.exists():
        target=p.parent/'_backup'/(stamp+'_review_documents')/p.name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)

def svg(title,desc,nodes,edges,height=700):
    output=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 {height}" role="img" aria-labelledby="title-{height} desc-{height}">',
       f'<title id="title-{height}">{title}</title><desc id="desc-{height}">{desc}</desc>',
       '<defs>'+''.join(f'<marker id="{key}-{height}" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="{color}"/></marker>' for key,color in [('arrow','#6b7488'),('arrow-accent','#a8720c'),('arrow-link','#2f5bd8')])+'</defs>',
       '<style>text{font-family:Geist,"Noto Sans KR","Malgun Gothic",sans-serif;fill:#161c28;text-anchor:middle;font-size:18px}.label{font-size:15px}rect,ellipse,polygon{stroke:#6b7488;stroke-width:1.5;fill:#fbfcfd}</style>',
       '<rect width="940" height="'+str(height)+'" fill="#fbfcfd" stroke="none"/>']
    for path,label,x,y in edges:
        output.append(f'<path d="{path}" fill="none" stroke="#6b7488" stroke-width="1.8" marker-end="url(#arrow-{height})"/>')
        if label:
            output.append(f'<rect x="{x-60}" y="{y-18}" width="120" height="24" style="stroke:none"/><text x="{x}" y="{y}" class="label">{label}</text>')
    for kind,x,y,text in nodes:
        if kind=='end':shape=f'<ellipse cx="{x}" cy="{y}" rx="140" ry="28"/>'
        elif kind=='decision':shape=f'<polygon points="{x},{y-60} {x+110},{y} {x},{y+60} {x-110},{y}"/>'
        else:shape=f'<rect x="{x-140}" y="{y-33}" width="280" height="66" rx="6"/>'
        output.append(shape)
        rows=text.split('|')
        output.append(f'<text x="{x}" y="{y-(len(rows)-1)*11+6}">'+''.join(f'<tspan x="{x}" dy="{0 if i==0 else 24}">{v}</tspan>' for i,v in enumerate(rows))+'</text>')
    output.append('</svg>');return '\n'.join(output)

figures={
'travel-check-flow.svg':svg('작업 한 건의 자료 확인','자료가 유효하면 팀 계산 후 적용 판단으로, 아니면 해당 작업만 보류하고 회차를 끝냅니다.',
 [('end',300,50,'작업 한 건 시작'),('step',300,140,'필요한 자료 조회'),('decision',300,270,'자료 유효?'),('step',300,410,'분류·해당 팀 계산'),('end',300,540,'다음: 적용 판단'),('step',715,360,'해당 작업 보류·안내'),('end',715,490,'이 작업 회차 종료')],
 [('M300 78V107',None,0,0),('M300 173V210',None,0,0),('M300 330V377','예',345,355),
  ('M410 270H707Q715 270 715 278V327','아니요',535,252),('M300 443V512',None,0,0),('M715 393V462',None,0,0)],620),
'travel-apply-flow.svg':svg('변경 제안 이후의 적용 판단','전체 검증 실패는 적용하지 않고 종료합니다. 자동 변경이 허용되지 않으면 고객 선택 대기로 종료하며, 허용될 때 저장하고 통지합니다.',
 [('end',300,50,'변경 제안 수신'),('decision',300,200,'전체 검증|통과?'),('end',715,200,'적용하지 않고 종료'),('decision',300,370,'자동 변경|허용?'),('step',300,510,'새 판 저장·변경 통지'),('end',300,650,'이 회차 종료'),('step',715,470,'고객 선택 요청'),('end',715,600,'대기·이 회차 종료')],
 [('M300 78V140',None,0,0),('M410 200H575','아니요',490,181),('M300 260V310','예',345,288),
 ('M300 430V477','예',345,454),('M410 370H707Q715 370 715 378V437','아니요',535,351),
 ('M300 543V622',None,0,0),('M715 503V572',None,0,0)],730)}
for name,raw in figures.items():
    p=HERE/name;backup(p);p.write_text(raw,encoding='utf-8')

v12=ROOT/'program/plan/triPilot_구현계획서_v12.md'
baseline=ROOT/'program/baseline/triPilot-baseline-2026-10-12.md'
for p in (v12,baseline):
    text=p.read_text(encoding='utf-8')
    revised=text.replace('初기 진단','초기 진단')
    if p==v12 and '![자료 확인 흐름]' not in revised:
        revised=revised.replace('## 항로 지킴이와 고객 선택',
         '## 자료 확인과 적용의 흐름\n\n![자료 확인 흐름](../research/baseline_completion_2026-10-12/tasks/integration/travel-check-flow.svg)\n\n자료 확인은 작업 한 건의 흐름입니다. 보류한 작업의 다음 시작 조건은 다음 예약 회차 또는 명시적 재시도입니다. 독립 작업은 계속 확인합니다.\n\n![일정 적용 흐름](../research/baseline_completion_2026-10-12/tasks/integration/travel-apply-flow.svg)\n\n위 그림은 변경 제안 이후입니다. 변경이 필요 없는 조회는 기존 상태로 끝납니다. 자동 변경 허용은 지킴이 설정·고정·안전을 함께 확인합니다. 고객 선택이 오면 최신 상태에서 새 회차를 시작합니다. 업체 거래의 별도 승인 절차는 그림 밖의 계약입니다.\n\n## 항로 지킴이와 고객 선택')
    if p==baseline:
        revised=revised.replace('실경보의 방향 판정 실패18건, 실제 택시 미터 오차 표본의2/4 기준 충족·평균 과소1,125원은 별도 미해결 검토 대상입니다.',
         '[실경보의 방향 판정 실패18건](../../final_project_cs/wiki/records/reports/2026-10-12_서울28건_도로구간과방향_추가대조.md), [실제 택시 미터 오차 표본의2/4 기준 충족·평균 과소1,125원](../../final_project_cs/wiki/records/reports/2026-10-12_taxi_pretrip_web/REPORT.md)은 별도 미해결 검토 대상입니다.')
    if text!=revised:backup(p);p.write_text(revised,encoding='utf-8')

css='''*{box-sizing:border-box}body{margin:0;background:#fbfcfd;color:#161c28;font-family:Geist,"Noto Sans KR","Malgun Gothic",sans-serif;font-size:16px;line-height:1.8}main{max-width:1080px;margin:auto;padding:40px 32px}h1{font-family:"Instrument Serif","Noto Serif KR","Malgun Gothic",serif;font-size:30px;line-height:1.4}h2{font-size:23px;margin-top:44px}a{color:#2f5bd8;overflow-wrap:anywhere}code{font-size:.88em;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:14px;margin:24px 0}th,td{border:1px solid #dbe0ea;padding:10px;vertical-align:top;text-align:left;overflow-wrap:anywhere}th{background:#f1f4f8}.table-scroll{overflow:auto}figure{margin:32px 0;overflow:auto}svg{display:block;width:100%;min-width:740px;height:auto}img{max-width:100%}figcaption,.meta{font-size:13px;color:#6b7488;overflow-wrap:anywhere}.notice{border-left:4px solid #a8720c;padding:12px 20px;background:rgba(168,114,12,.1)}@media(max-width:600px){main{padding:24px 16px}h1{font-size:26px}h2{font-size:21px}table{min-width:650px}td,th{padding:8px}}@media print{main{padding:0;max-width:none}svg{min-width:0}table{min-width:0;font-size:10px}tr,figure{break-inside:avoid}a{color:inherit}}'''
summary=[]
for p in (v12,baseline):
    raw=p.read_text(encoding='utf-8');body=raw.split('---\n',2)[2] if raw.startswith('---\n') else raw
    rendered=markdown.markdown(body,extensions=['tables','fenced_code','toc'])
    rendered=re.sub(r'<table>(.*?)</table>',r'<div class="table-scroll"><table>\1</table></div>',rendered,flags=re.S)
    def inline(match):
        source=(p.parent/html.unescape(match[2])).resolve()
        if source.suffix=='.svg' and source.is_relative_to(ROOT) and source.is_file():
            return '<figure>'+source.read_text(encoding='utf-8')+f'<figcaption>{html.escape(match[1])}</figcaption></figure>'
        return match[0]
    rendered=re.sub(r'<img alt="([^"]*)" src="([^"]*)"\s*/?>',inline,rendered)
    target=p.with_suffix('.html');backup(target)
    title=next(line[2:] for line in body.splitlines() if line.startswith('# '))
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    target.write_text(f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · 검토본</title><style>{css}</style></head><body><main><p class="notice">최종 인수 전 검토본 — 제품 완료·출시 승인이 아닙니다.</p><p class="meta">Markdown SHA-256: {digest}</p>{rendered}</main></body></html>',encoding='utf-8')
    summary.append(dict(markdown=p.relative_to(ROOT).as_posix(),html=target.relative_to(ROOT).as_posix(),markdown_sha256=digest,html_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),status='draft_unaccepted'))
out=HERE/'checks'/('review-documents-'+stamp+'.json')
out.write_text(json.dumps(dict(documents=summary,figures=list(figures),status='draft_unaccepted'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(out.relative_to(ROOT).as_posix())
