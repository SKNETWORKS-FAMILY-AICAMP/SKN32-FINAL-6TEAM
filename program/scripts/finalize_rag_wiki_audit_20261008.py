"""원본을 보존하고 실측 검증 근거로 문서 점검을 마무리한다."""
from pathlib import Path
import json, tomllib, shutil, subprocess
ROOT=Path(__file__).resolve().parents[2]
out=ROOT/'program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008'
backup=out/'_backup/2026-10-08_1020_before_final_validation'
backup.mkdir(parents=True,exist_ok=True)
for name in ['validation.json','before.txt','after.txt']:
    src=out/name
    if src.exists() and not (backup/name).exists(): shutil.copy2(src,backup/name)
log=ROOT/'final_project_cs/wiki/log.md'
text=log.read_text(encoding='utf-8')
entry='\n## 2026-10-08 — RAG 연구·모델 평가·GPU 운영의 wiki 정본 연결\n\n최근 연구 문서의 정본·색인·작업 리포트 연결 누락을 보완했다. [문서 점검과 검증](records/reports/2026-10-08_rag-wiki-document-audit.md).\n'
assert text.count(entry)==1
b=log.parent/'_backup/2026-10-08_1020_rag_wiki_log_order'
b.mkdir(parents=True,exist_ok=True)
if not (b/log.name).exists(): shutil.copy2(log,b/log.name)
text=text.replace(entry,'',1).replace('# 문서 변경 이력 (cs)\n','# 문서 변경 이력 (cs)\n'+entry,1)
log.write_text(text,encoding='utf-8')

checks=[]
for aid in ['rag','rag-strata']:
    old=tomllib.loads((out/'automation_backups'/f'{aid}.toml').read_text(encoding='utf-8'))
    now=tomllib.loads((Path('C:/Users/playdata2/.codex/automations')/aid/'automation.toml').read_text(encoding='utf-8'))
    fields=['kind','name','rrule','status','destination','target_thread_id','notification_policy']
    unchanged={k:old.get(k)==now.get(k) for k in fields}
    good=now['prompt'].startswith(old['prompt']) and '문서 관리 보완(2026-10-08)' in now['prompt'] and all(unchanged.values())
    checks.append({'id':aid,'passed':good,'preserved_fields':unchanged})
assert all(x['passed'] for x in checks), checks
(out/'automation_validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
report=ROOT/'final_project_cs/wiki/records/reports/2026-10-08_rag-wiki-document-audit.md'
rb=report.parent/'_backup/2026-10-08_1020_rag_wiki_report_completion'
rb.mkdir(parents=True,exist_ok=True)
shutil.copy2(report,rb/report.name)
with report.open('a',encoding='utf-8') as f:
    f.write('''
## 후속 검증과 예약 작업 반영

일일 연구와 GPU 대기열 확인의 두 예약 작업에 wiki 정본 우선·영역 색인 등록·작업 리포트·본문 및 log 연결 의무를 추가했다. 기존 프롬프트, 실행 주기, 활성 상태, 대상 대화, 알림 정책을 보존했는지 원본과 재대조해 2/2 통과했다. [예약 원본 백업](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/automation_backups/) · [검증 출력](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/automation_validation.json).

기존 wiki 검사기를 수정 전 내용을 읽게 한 검사와 수정 후 검사에 똑같이 적용했다. 이번 백업 사본은 문서 위치에 따라 깨진 상대 링크로 오탐될 수 있어 두 검사에서만 제외했다. 수정 전후 기존 지적은 각각 271건이며 새 문제는 추가하지 않았다. 전체 wiki 통과를 뜻하지 않는다. 기존 장문 로그의 줄 수 변화는 같은 지적으로 대조했다.

변경한 13개 문서의 파일 링크, 새 정본 3개 색인 등록, 수정 전 원본 8개 보관 여부를 검사했다. 정확한 최종 분자/분모와 전체 지적은 [검증 JSON](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/validation.json) · [수정 전 출력](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/before.txt) · [수정 후 출력](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/after.txt)에서 확인한다.

후속 문서 조정 전 판도 보존했다: [연구 정본](../../../../wiki/research/_backup/2026-10-08_1017_rag_wiki_final/) · [cs 변경 이력](../../_backup/2026-10-08_1020_rag_wiki_log_order/) · [점검 리포트](../../records/reports/_backup/2026-10-08_1020_rag_wiki_report_completion/) · [검증 도구](../../../../program/scripts/_backup/2026-10-08_1020_rag_wiki_validation/) · [중간 검증 출력](../../../../program/scripts/plan_qa_bench/results/rag_wiki_audit_20261008/_backup/2026-10-08_1020_before_final_validation/).

기존 모델 학습·평가 프로세스와 데이터는 변경하지 않았다. 실서비스 배포·커밋·푸시는 수행하지 않았다. sample·datasets·dojo를 포함한 전체 과거 wiki 지적 해결은 이번 범위 밖이며 별도 점검이 필요하다.
''')
subprocess.run(['C:/Users/playdata2/anaconda3/python',str(ROOT/'program/scripts/verify_rag_wiki_20261008.py')],check=True,cwd=ROOT)
