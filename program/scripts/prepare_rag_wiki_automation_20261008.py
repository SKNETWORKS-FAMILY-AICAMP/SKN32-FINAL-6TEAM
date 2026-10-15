"""기존 예약 조건을 보존하고 wiki 작업 의무만 추가할 도구 인자를 준비한다."""
from pathlib import Path
import tomllib, json, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[2]
store=ROOT/'program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/automation_backups'
store.mkdir(parents=True,exist_ok=True)
addition='''
문서 관리 보완(2026-10-08): 작업 전에 wiki/governance/structure-guide.md·document-standard.md·work-loop.md와 해당 프로젝트 RULE·wiki 색인을 따르세요. 연구 개요의 정본은 wiki/research/rag-slm-improvements.md, 모델 비교·추가 학습 기준은 final_project_cs/wiki/quality/slm-model-evaluation.md, GPU 운영 절차는 final_project_cs/wiki/operations/gpu-work-queue.md입니다. program/research/daily_rag_slm/index.md로 날짜별 기록과 후보·대기열 JSON을 찾으세요. 의미 있는 조사·구현·실측·실패가 생긴 작업은 final_project_cs/wiki/records/reports/에 새 날짜의 리포트를 남기고, 지속 사실이 바뀌면 해당 wiki 본문과 log에 결론 한 줄 및 리포트 링크를 연결하세요. 새 개념 문서는 영역 index에 먼저 등록하고, 각 wiki의 소유 경계를 지키며 후보 상태와 실측 수치를 여러 정본에 중복하지 마세요. 기존 산출물은 수정 직전에 백업하고 날짜별 과거 근거 기록은 보존하세요. 일상 진행 숫자만 바뀌면 기존 조용한 알림 원칙을 유지하세요.
'''
updates=[]
for aid in ['rag','rag-strata']:
    src=Path('C:/Users/playdata2/.codex/automations')/aid/'automation.toml'
    backup=store/(aid+'.toml')
    if not backup.exists(): shutil.copy2(src,backup)
    data=tomllib.loads(backup.read_text(encoding='utf-8'))
    prompt=data['prompt']
    if addition.strip() not in prompt: prompt+=addition
    updates.append({'mode':'update','id':aid,'kind':data['kind'],'destination':data.get('destination','thread'),
                    'name':data['name'],'prompt':prompt,'rrule':data['rrule'],'status':data['status'],
                    'targetThreadId':data.get('target_thread_id'), 'notificationPolicy':data.get('notification_policy')})
print(json.dumps(updates,ensure_ascii=False))
