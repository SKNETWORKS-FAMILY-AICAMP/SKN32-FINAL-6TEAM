"""Connect the dated E audit after backing up each existing document."""
import json
import shutil
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[3]
stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_e_maturity_audit'
report = '2026-10-09_0214_e-testset-maturity-audit.md'


def update(relative, transform):
    path = root / relative
    old = path.read_text(encoding='utf-8')
    new = transform(old)
    if old == new:
        return
    backup = path.parent / '_backup' / stamp
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup / path.name)
    path.write_text(new, encoding='utf-8')
    print((backup / path.name).relative_to(root).as_posix())


quality_line = f'`[실측 2026-10-09]` E는 혼합 평문과 대조 짝을 통한 참조 인식 진단을 고도화했지만, 사람 검수와 독립 최종 검증까지 완성된 상용화 관문은 아니다. [구성·검수 감사](../records/reports/{report}).'
update('final_project_cs/wiki/quality/slm-model-evaluation.md',
       lambda s: s if report in s else s.replace('## ', quality_line + '\n\n## ', 1))
log_line = f'## 2026-10-09 — E 평가셋의 검수 완성도 감사\n\n混합·대조 짝과 저장된 사람 판정 칸을 다시 확인하고 고도화된 설계와 검수 완료를 구분했다. [현재 평가 기준](quality/slm-model-evaluation.md) · [원본 감사](records/reports/{report}).\n\n'.replace('混', '혼')
update('final_project_cs/wiki/log.md', lambda s: s if report in s else s.replace('## ', log_line + '## ', 1))
day_line = f'\n## E 평가셋의 검수 상태 확인\n\n혼합 자유 입력 진단의 고도화 범위와 사람 검수 상태를 원본에서 다시 확인했다. 수치와 한계는 [E 감사 리포트](../../../final_project_cs/wiki/records/reports/{report})와 [구조화 근거](../../scripts/plan_qa_bench/results/e_maturity_audit_20261009.json)에 보관했다. 데이터와 과거 모델 점수는 변경하지 않았다.\n'
update('program/research/daily_rag_slm/2026-10-09.md', lambda s: s if report in s else s.rstrip() + '\n' + day_line)


def day_json(s):
    obj = json.loads(s)
    obj['E_corpus_audit'] = {
        'structure_audit_completed': True,
        'human_gold_review_completed': False,
        'evidence': 'program/scripts/plan_qa_bench/results/e_maturity_audit_20261009.json',
        'scope': 'Stored corpus and review-state audit; no model evaluation or human adjudication',
    }
    link = 'final_project_cs/wiki/records/reports/' + report
    if link not in obj['reports']:
        obj['reports'].append(link)
    return json.dumps(obj, ensure_ascii=False, indent=2) + '\n'


update('program/research/daily_rag_slm/2026-10-09.json', day_json)
print('BACKUP_STAMP=' + stamp)
