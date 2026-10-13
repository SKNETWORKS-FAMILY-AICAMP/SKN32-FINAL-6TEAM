"""공식 원본 확인을 후보 목록에 연결한다. 가중치 다운로드·GPU 실행은 하지 않는다."""
import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
EVIDENCE = Path(__file__).resolve().parent
DAY = ROOT / 'program/research/daily_rag_slm'
now = datetime.now(timezone(timedelta(hours=9)))
stamp = now.strftime('%Y-%m-%d_%H%M%S_saluki_review')
metadata = json.loads((EVIDENCE / 'model_metadata.json').read_text(encoding='utf-8'))
revision = metadata['sha']
filename = 'Underdog-Saluki-27B-1.0-IQ2-mix.gguf'
weight = next(x for x in metadata['siblings'] if x['rfilename'] == filename)
sources = {name: {'bytes': (EVIDENCE / name).stat().st_size,
                  'sha256': hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest()}
           for name in ['model_metadata.json', 'README.md', 'LICENSE', 'NOTICE']}
candidate = {
    'repo_id': metadata['id'], 'version': '1.0', 'checked_date': '2026-10-09',
    'source_url': 'https://huggingface.co/' + metadata['id'],
    'revision_sha': revision, 'repository_created_at': metadata['createdAt'],
    'repository_last_modified': metadata['lastModified'],
    'public_release_announcement_date_verified': False,
    'our_finetuning': False,
    'publisher_training': 'Qwen3.8 instruction release derivative; GGUF mixed 2-bit quantization; exact additional training recipe not disclosed in inspected card',
    'base_model': metadata['cardData']['base_model'],
    'model_role': 'text generation / tool calling, optional vision',
    'language_parameters_nominal': 27000000000, 'language_parameters_exact': None,
    'total_parameters_exact': None, 'active_parameters_exact': None,
    'declared_languages': metadata['cardData']['language'], 'korean_travel_measured': False,
    'weights_file': filename, 'weights_bytes': weight['size'],
    'weights_sha256': weight['lfs']['sha256'], 'quantization': 'IQ2-mix',
    'license': 'Apache-2.0', 'license_body_verified': True,
    'license_sha256': sources['LICENSE']['sha256'], 'license_notice_preserved': True,
    'evidence': 'program/scripts/plan_qa_bench/results/saluki_preflight_20261009',
    'official_evidence_files': sources,
    'publisher_benchmarks_not_project_measurements': {
        'tool_calling': {'correct': 88, 'total': 120, 'full_base_correct': 84},
        'parallel_tool_calling': {'correct': 42, 'total': 100, 'full_base_correct': 35},
        'repeat_count_verified': None, 'publisher_notes_small_sample_variation': True,
    },
    'status': 'official_revision_license_verified; conditional_download_and_runner_smoke_pending',
    'original_benchmark_completed': False, 'upper_tier': None,
    'finetune_eligibility': 'outside_current_approximately_8B_language_parameter_SLM_scope; compressed_file_does_not_change_parameter_count',
    'weights_downloaded': False, 'gpu_runner_compatibility_verified': False,
    'space_observation': {
        'observed_at_kst': '2026-10-09T01:10:00+09:00',
        'gpu_A_free_GiB_approx': 8.15, 'gpu_B_free_GiB_approx': 20.98,
        'gpu_A_weight_download_blocked_by_3GiB_reserve': True,
        'gpu_B_training_active': True,
        'gpu_B_download_requires_recheck_of_training_outputs_and_quota': True,
        'filesystem_free_space_is_not_quota_proof': True,
    },
    'required_next_action': 'Reserve existing space including queued training outputs; download only text GGUF at fixed revision; verify SHA; wait for existing GPU work; isolate runner smoke before matched D3/H/E and D/D2; keep conditional work separate from ready queue counts',
}
plan = {
    'schema_version': 1, 'created_at_kst': now.isoformat(),
    'candidate_revision': revision, 'repo_id': candidate['repo_id'],
    'weight_file': filename, 'weight_bytes': weight['size'],
    'weight_sha256': weight['lfs']['sha256'], 'weights_downloaded': False,
    'status': 'conditional_preparation_not_a_running_or_ready_GPU_job',
    'download_gates': ['existing GPU resources only', 'no identical revision/SHA duplicate',
                       'file bytes + queued training growth + outputs + 3GiB reserve fit',
                       'quota and writable directory probe pass', 'preserve partial files and existing models'],
    'execution_gates': ['no concurrent GPU task or duplicate worker',
                        'stock llama.cpp installed-version GGUF architecture load verified',
                        'same item/null JSON contract; no gold in request',
                        'freeze prompt hashes, IDs, runner hash, engine version, settings before score run'],
    'settings': {'jinja': True, 'enable_thinking': False, 'temperature': 0,
                 'context_tokens': 4096, 'max_output_tokens': 16, 'parallel_slots': 1,
                 'precision': 'publisher IQ2-mix; differs from other releases and is explicitly recorded'},
    'local_runner_reference': 'program/scripts/plan_qa_bench/server/d_test_llama.py',
    'runtime_runner_sha256': None, 'engine_commit': None,
    'smoke': {'rows': 12, 'request': 6, 'no_request': 6,
              'status': 'pending_input_selection_and_execution',
              'purpose': 'load/template/parser/memory check, not accuracy improvement evidence'},
    'matched_suites': [{'name': n, 'expected_rows': count, 'prompt_sha256': None,
                       'completed': 0, 'status': 'not_started'}
                      for n, count in [('D3', 360), ('H', 1316), ('E/MX', 4014), ('D', 2735), ('D2', 1000)]],
    'planned_total': 9425, 'completed_total': 0,
    'BC_multi_item_contract': 'separate baseline 835-row multi-selection runner adaptation pending; do not treat single item D runner as exact multi-set C',
    'comparison': 'matched publisher originals only; developer training and our training distinguished; failures and missing answers stay in denominator',
    'latency_and_memory': 'record actual engine/quantization/context/cache, per-row ms and peak memory; no engine speed conclusion from changing model',
    'adoption': 'development/regression diagnostics first; no adoption before independent holdout/repetition criteria',
    'ARM': 'not queued; 7.9GB weight size alone does not establish 12GB runtime memory or acceptable CPU latency',
    'fine_tuning': 'not automatically eligible as approximately 27B exceeds project SLM scope; distributed GGUF is not proof of additional training fit',
}
with (EVIDENCE / 'evaluation_plan.json').open('x', encoding='utf-8') as f:
    json.dump(plan, f, ensure_ascii=False, indent=2)
watch = DAY / 'model_release_watchlist.json'
data = json.loads(watch.read_text(encoding='utf-8'))
assert not any(x['repo_id'] == candidate['repo_id'] and x.get('revision_sha') == revision for x in data['candidates'])
backup = DAY / '_backup' / stamp
backup.mkdir(parents=True, exist_ok=False)
shutil.copy2(watch, backup / watch.name)
data['candidates'].append(candidate)
data['last_checked_date'] = '2026-10-09'
data['latest_check_scope'] = 'User-requested Saluki official review; not a completed daily global release or paper survey'
temporary = watch.with_name(watch.name + '.saluki.tmp')
temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
temporary.replace(watch)
print(json.dumps({'candidate_count': len(data['candidates']), 'weight_bytes': weight['size'],
                  'revision': revision, 'backup': str(backup), 'plan': str(EVIDENCE / 'evaluation_plan.json')}, ensure_ascii=False))
