"""회수한 두 기계의 상태를 새 요약과 일일 기록에 보관한다."""
import datetime
import json
from pathlib import Path

workspace = Path(__file__).resolve().parents[5]
research = workspace / 'program/research/daily_rag_slm'
results = workspace / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
a = json.loads((results / 'A_snapshot_0953.json').read_text(encoding='utf-8-sig'))
b = json.loads((results / 'B_snapshot_0953.json').read_text(encoding='utf-8-sig'))
jobs = a['manifest']['jobs']
summary = {
    'recorded_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
    'registration_is_not_completion': True,
    'gpu_A': {
        'queue_root': '/tmp/tripilot-a-backlog-20261008',
        'worker_pid': a['worker_pid'],
        'jobs_registered': len(jobs),
        'planned_answers': sum(j['expected'] for j in jobs),
        'answers_saved_at_snapshot': a['answers'],
        'state': a['state'],
        'snapshot': str((results / 'A_snapshot_0953.json').relative_to(workspace)),
        'instant_gpu_memory_and_utilization': a['gpu_snapshot'],
    },
    'gpu_B': {
        'full_training_variants_registered': 5,
        'current': 'winnow_e4b_oos full training',
        'current_our_training': True,
        'train_choice': b['choice'].strip(),
        'queue_order': ['winnow_e4b_oos', 'spark_s1_4b_oos', 'jevify_e4b_oos',
                        'oos2r_cosine_5e5_20261008', 'oos2r_finch_20261008'],
        'existing_queues': ['B54', 'B56_daily_20261008'],
        'snapshot': str((results / 'B_snapshot_0953.json').relative_to(workspace)),
        'instant_gpu_memory_and_utilization': b['gpu_snapshot'],
    },
    'automatic_refill': {
        'automation_id': 'rag-strata',
        'interval_minutes': 10,
        'ready_jobs_per_machine_refill_threshold': 3,
        'research_automation_id': 'rag',
        'research_daily_time': '10:00 Asia/Seoul',
        'continuous_until_user_changes_instruction': True,
        'collect_completed_results_before_leaving_temporary_storage': True,
        'no_duplicate_or_interrupt_running_jobs': True,
        'no_new_payment_rental_or_existing_model_deletion': True,
    },
    'queue_checks': {'passed': 4, 'total': 4},
}
target = research / 'gpu_backlog_2026-10-08.json'
with target.open('x', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
    f.write('\n')
daily = research / '2026-10-08.json'
backup = research / '_backup/2026-10-08_gpu_backlog_before/2026-10-08.json'
if not backup.exists():
    raise RuntimeError('Required pre-update backup not found')
record = json.loads(daily.read_text(encoding='utf-8'))
record['gpu_queue'] = {'record': target.name, 'registered_evaluations': len(jobs),
                       'registered_full_training_variants': 5,
                       'refill_interval_minutes': 10, 'both_machines_running_verified': True}
daily.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'registered_A_jobs': len(jobs), 'planned_A_answers': summary['gpu_A']['planned_answers'],
                  'saved_A_answers': a['answers'], 'registered_B_training': 5,
                  'B_latest_train_log': b['logs'].get('/root/qlora_train_winnow_e4b_oos.log', '')[-600:]}, ensure_ascii=True))
