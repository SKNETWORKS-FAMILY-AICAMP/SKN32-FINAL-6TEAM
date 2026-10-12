"""ARM에 이미 있는 모델과 고정 여행 시험 자료로 새 대기열을 만든다."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess

root = Path.home()/'bench'/'continuous-travel-20261008'
bench = root.parent
manifest_path = root/'manifest.json'
if manifest_path.exists():
    print('MANIFEST_ALREADY_EXISTS: 변경하려면 백업 후 명시적으로 갱신하세요')
    raise SystemExit(0)
engine = bench/'llama.cpp/build/bin/llama-server'
assert engine.is_file()
assert len(__import__('os').sched_getaffinity(0)) == 2
assert shutil.disk_usage(root).free >= 3*1024**3
port = 8312
with socket.socket() as test:
    test.bind(('127.0.0.1', port))
sources = {}
for suite in ('d3', 'mx'):
    p = root/(suite+'.json')
    rows = json.loads(p.read_text(encoding='utf-8'))
    assert len({r['i'] for r in rows}) == len(rows)
    assert all(r['prompt'].count('\ufffd') == 0 for r in rows)
    sources[suite] = dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), n=len(rows))
profiles = [
    ('e4bt_q4_d3', 'e4bt-Q4_K_M.gguf', 'd3', 1, 1, True, 'existing_trained_e4b_recipe_not_yet_matched'),
    ('e4bt_q8_d3', 'e4bt-Q8_0.gguf', 'd3', 1, 1, True, 'existing_trained_e4b_recipe_not_yet_matched'),
    ('e4bt_q4_d3_concurrent2', 'e4bt-Q4_K_M.gguf', 'd3', 2, 2, True, 'existing_trained_e4b_recipe_not_yet_matched'),
    ('e4bt_q4_d3_nocache', 'e4bt-Q4_K_M.gguf', 'd3', 1, 1, False, 'existing_trained_e4b_recipe_not_yet_matched'),
    ('e4bt_q4_mx', 'e4bt-Q4_K_M.gguf', 'mx', 1, 1, True, 'existing_trained_e4b_recipe_not_yet_matched'),
    ('e4b_qat_original_d3', 'models/e4b_qat_q40.gguf', 'd3', 1, 1, True, 'publisher_instruct_no_our_training'),
    ('e2b_qat_original_d3', 'models/e2b_qat_q40.gguf', 'd3', 1, 1, True, 'publisher_instruct_no_our_training'),
    ('kanana_original_d3', 'models/kanana2_3b_q8.gguf', 'd3', 1, 1, True, 'publisher_instruct_no_our_training'),
    ('exaone_original_d3', 'models/exaone40_12b_q8.gguf', 'd3', 1, 1, True, 'publisher_instruct_no_our_training'),
    ('frog_original_d3', 'models/frog4b_q8.gguf', 'd3', 1, 1, True, 'publisher_coding_rl_no_our_training'),
]
jobs = []
for ident, model, suite, slots, clients, cache, training in profiles:
    model_path = bench/model
    assert model_path.is_file() and model_path.stat().st_size > 100000000
    jobs.append(dict(id=ident, model=str(model_path), model_size_bytes=model_path.stat().st_size,
                     prompts=sources[suite]['path'], prompt_sha256=sources[suite]['sha256'],
                     expected=sources[suite]['n'], slots=slots, clients=clients, cache_prompt=cache,
                     context_per_slot=4096, seed=20261008, request_timeout_s=900,
                     training=training, purpose='ARM serving development and regression; no product adoption'))
manifest = dict(created=datetime.now(timezone.utc).isoformat(), engine=str(engine), port=port,
                cpu_count=2, cpu_target_percent_of_two_cores=20, memory_service_max_bytes=10*1024**3,
                min_free_bytes=3*1024**3, continuous_soak=True, sources=sources, jobs=jobs,
                soak_interpretation='same fixed inputs repeated for stability; correlated, not independent accuracy samples')
with manifest_path.open('x', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(json.dumps(dict(prepared=len(jobs), questions=sum(j['expected'] for j in jobs),
                     engine_version=subprocess.check_output([str(engine),'--version'], text=True, stderr=subprocess.STDOUT).strip(),
                     sources=sources)))
