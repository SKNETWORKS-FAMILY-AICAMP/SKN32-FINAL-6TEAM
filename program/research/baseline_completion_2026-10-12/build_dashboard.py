"""Generate the dispatch dashboard from verified session assignments."""
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
plan = json.loads((HERE/'coordination.json').read_text(encoding='utf-8'))
started = json.loads((HERE/'start-evidence.json').read_text(encoding='utf-8'))
started_ids = {s['thread_id'] for s in started['sessions'] if s['thread_status']=='active'}
ids = [s['thread_id'] for s in plan['new_sessions']]
assert len(ids)==len(set(ids))==6 and set(ids)==started_ids
covered = set(plan['retained_completed_items'])
for session in plan['new_sessions'] + plan['existing_sessions']:
    covered.update(w for w in session['w_ids'] if w.startswith('W') and len(w)==3)
assert covered=={f'W{i:02}' for i in range(1,26)}

def safe_write(path, text):
    if path.exists():
        backup=HERE/'_backup'/now.strftime('%Y-%m-%d_%H%M%S_dashboard')
        backup.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,backup/path.name)
    path.write_text(text,encoding='utf-8')

phase_labels={'running':'진행 중','waiting_dependency':'선행 결과 대기',
              'ready_for_integration':'통합 검토 요청','blocked':'필수 조건 확인 필요'}
rows=[]
md_rows=[]
for s in plan['new_sessions']:
    status_path=HERE/'tasks'/s['key']/'status.json'
    current=json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
    state=phase_labels.get(current.get('phase'), '실제 착수 확인')
    title=html.escape(s['title'])
    w=', '.join(s['w_ids'])
    deps=', '.join(s['dependencies']) or '독립 작업'
    rel=s['task']
    rows.append(f'<tr><td>{title}</td><td>{html.escape(w)}</td><td>{html.escape(state)}</td><td>{html.escape(deps)}</td><td><a href="{rel}">작업 범위·완료 조건</a></td></tr>')
    md_rows.append(f"| {s['title']} | {w} | {state} | [{s['key']} 작업 명세]({rel}) |")

old_rows=[]
for s in plan['existing_sessions']:
    # A source did not return a short title for the alert session; identify by its work.
    label=s['title'] or '실경보 원문·서울 28건 재현 담당 세션(설명)'
    old_rows.append(f'<tr><td>{html.escape(label)}</td><td>{html.escape(s["scope"])}</td></tr>')

page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>triPilot · 후속 작업 분담·완료 순서</title>
<style>body{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:32px 24px}h1{font-size:30px}h2{font-size:22px;margin-top:36px}p{max-width:960px}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;vertical-align:top;padding:12px;border:1px solid #cbd2df}th{background:#f3efe6}.notice{padding:16px 20px;background:#f7f2e7;border-left:4px solid #a8720c}a{color:#765000}a:focus-visible{outline:3px solid #a8720c;outline-offset:3px}.scroll{overflow:auto}small{color:#586277}li{margin:8px 0}@media(max-width:650px){main{padding:20px 12px}h1{font-size:24px}table{min-width:680px}}</style>
<main><small>triPilot · '''+now.strftime('%Y-%m-%d %H:%M 한국 시간')+'''</small><h1>남은 구현·검증과 최종 문서 작업</h1>
<p class="notice">후속 세션 6/6개의 실제 착수를 확인했습니다. 이것은 기능·시험·최종 문서가 완성됐다는 뜻이 아닙니다. 기존 세션 7개를 읽어 같은 기능의 중복 구현을 제외했습니다.</p>
<h2>새 세션의 담당</h2><div class="scroll"><table><thead><tr><th>세션</th><th>항목</th><th>확인 상태</th><th>선행 결과</th><th>상세</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div>
<h2>기존 담당을 유지하는 작업</h2><div class="scroll"><table><thead><tr><th>기존 세션</th><th>새로 만들지 않는 작업</th></tr></thead><tbody>'''+''.join(old_rows)+'''</tbody></table></div>
<h2>완료 순서</h2><ol><li>각 담당이 현재 wiki와 구현의 차이를 수정하고 자기 범위의 시험·근거를 남깁니다.</li><li>통합 검증 담당이 구현 결과를 기다려 공통·여행 전체 시험과 환경·모델 근거를 대조합니다.</li><li>최종 통합 담당이 공유 접합부·실패한 시험·wiki 정합성을 수정하고 다시 검사합니다.</li><li>검증된 wiki를 바탕으로 v12 안내서와 프로젝트 전체의 하나의 기준선 파일, 각각의 검토용 HTML을 완성합니다.</li></ol>
<p>통합 검증과 최종 문서 세션에는 15분 간격 후속 확인을 설정했습니다. 변화가 없는 동안은 같은 보고를 반복하지 않으며, 끝나면 확인을 종료하도록 지시했습니다. 실제 업무 DB 변경·배포·커밋·푸시는 이번 분담에 포함하지 않습니다.</p>
<p>v12는 wiki를 읽기 쉽게 정리하는 안내서입니다. 최종 베이스라인은 wiki 원본·해시·요구·인터페이스·자료/모델 판본·시험 증거·환경 적용 상태를 연결하는 프로젝트 전체 기준선입니다. 에이전트 구축·파인튜닝의 개별 보고서는 그 근거로 연결합니다.</p>
<p><a href="coordination.json">전체 담당·의존 관계</a> · <a href="common.md">공통 작업 기준</a> · <a href="start-evidence.json">실제 착수·후속 확인 근거</a> · <a href="../review_status_2026-10-12/index.html">25개 이전 현황</a></p>
<small>이 화면은 생성 시점의 현황입니다. 각 담당의 최신 결과는 tasks/&lt;담당&gt;/status.json과 report.md에서 확인합니다. 기존 검토·기준선 파일을 덮어쓰지 않고 별도 분담 자료로 저장했습니다.</small></main></html>'''

safe_write(HERE/'index.html',page)
markdown='# 남은 구현·검증과 최종 문서 작업\n\n새 세션 6개에 실제 작업을 전달하고 착수를 확인했습니다. 구현·검증 완료 보고는 아닙니다.\n\n| 세션 | 항목 | 상태 | 명세 |\n|---|---|---|---|\n'+'\n'.join(md_rows)+'\n\n통합 검증 후 wiki 기준 v12 안내서·프로젝트 전체 기준선·검토용 HTML을 작성합니다. 기존 담당 영역과 완료 조건은 [분담표](coordination.json)와 [공통 기준](common.md)에서 확인합니다.\n'
safe_write(HERE/'README.md',markdown)
links=[s['task'] for s in plan['new_sessions']]+['common.md','coordination.json','start-evidence.json','../review_status_2026-10-12/index.html']
validation={'captured_at_kst':now.isoformat(),'new_sessions':len(ids),'started_sessions':len(started_ids),
            'covered_w_ids':sorted(covered),'missing_links':[p for p in links if not (HERE/p).is_file()],
            'new_session_duplicate_ids':len(ids)-len(set(ids)),
            'dispatch_is_implementation_completion':False}
assert not validation['missing_links']
safe_write(HERE/'dispatch-validation.json',json.dumps(validation,ensure_ascii=False,indent=2))
print(json.dumps(validation,ensure_ascii=False))
