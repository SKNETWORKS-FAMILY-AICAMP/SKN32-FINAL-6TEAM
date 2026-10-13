"""기존 D3의 원문을 바꾸지 않고 연결 검사용 12문항을 고정한다."""
import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
source = ROOT / 'program/scripts/plan_qa_bench/results/empty_probe/all_prompts_d3.json'
rows = json.loads(source.read_text(encoding='utf-8'))
assert len(rows) == 360
positive_types = ['tourist_synth_in', 'nameless_description', 'confusable_name',
                  'ordinal_relative', 'context_pronoun', 'change_request']
selected = [next(x for x in rows if x['type'] == kind and x['gold'] is not None)
            for kind in positive_types]
for kind in ['synth_chat_A', 'synth_chat_B']:
    selected += [x for x in rows if x['type'] == kind and x['gold'] is None][:3]
assert len(selected) == len({x['i'] for x in selected}) == 12
assert sum(x['gold'] is not None for x in selected) == 6
assert all(x in rows for x in selected)
target = HERE / 'smoke_prompts_d3_12.json'
with target.open('x', encoding='utf-8') as f:
    json.dump(selected, f, ensure_ascii=False, indent=2)
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
manifest = {'source': str(source.relative_to(ROOT)).replace('\\', '/'),
            'source_rows': 360, 'source_sha256': digest(source),
            'selected_rows': 12, 'request_rows': 6, 'no_request_rows': 6,
            'selected_ids': [x['i'] for x in selected], 'smoke_sha256': digest(target),
            'prompt_text_unchanged': True, 'source_match_to_GPU_canonical_pending': True,
            'gold_is_metadata_not_model_input': True,
            'selection_rule': 'one item each of six request types and first three items each of two no-request types',
            'not_independent_holdout': True, 'purpose': 'load/template/parser/memory smoke only'}
with (HERE / 'smoke_manifest.json').open('x', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
path = HERE / 'evaluation_plan.json'
plan = json.loads(path.read_text(encoding='utf-8'))
backup = HERE / '_backup' / datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d_%H%M%S_before_smoke_inputs')
backup.mkdir(parents=True, exist_ok=False)
shutil.copy2(path, backup / path.name)
plan['smoke']['status'] = '12_original_inputs_prepared; canonical_prompt_hash_match_and_runtime_pending'
plan['smoke']['input_file'] = str(target.relative_to(ROOT)).replace('\\', '/')
plan['smoke']['input_sha256'] = manifest['smoke_sha256']
plan['smoke']['source_sha256'] = manifest['source_sha256']
plan['execution_gates'].append('Verify full prompt token lengths fit the frozen context without truncation; otherwise isolate a new protocol and matched baselines')
temporary = path.with_name(path.name + '.smoke.tmp')
temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
temporary.replace(path)
print(json.dumps({'request': 6, 'no_request': 6, 'unchanged': 12, 'total': 12,
                  'input_sha256': manifest['smoke_sha256'], 'backup': str(backup)}, ensure_ascii=False))
