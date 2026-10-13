"""고정 여행 입력을 기존 HF 가중치의 NF4 추론으로 측정한다.

llama.cpp와 같은 입력/16토큰/값 파싱 규칙을 유지한다. 엔진과 양자화가
함께 달라지는 진단이며 단일 원인 효과나 다른 기계 사이 속도 비교가 아니다.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time


def parse_value(text):
    match = re.search(r'"item"\s*:\s*(null|\d+)', text)
    return (False, None) if match is None else (True, None if match[1] == 'null' else int(match[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True, type=Path)
    args = parser.parse_args()
    job = json.loads(args.job.read_text())
    prompts = Path(job['prompts'])
    assert hashlib.sha256(prompts.read_bytes()).hexdigest() == job['prompt_sha256']
    rows = sorted(json.loads(prompts.read_text()), key=lambda r: (r['set'], r['qi']))
    assert len(rows) == len({r['i'] for r in rows}) == job['expected']
    output = Path('answers.jsonl')
    assert not output.exists(), 'Preserve previous attempt; do not resume automatically'
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    torch.set_num_threads(8)
    torch.manual_seed(0)
    start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(job['model'], local_files_only=True)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(job['model'], local_files_only=True,
        quantization_config=quant, dtype=torch.bfloat16, device_map={'': 0})
    if job.get('adapter'):
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, job['adapter'], local_files_only=True)
    model.eval()
    contract = dict(job=job, execution='HF transformers + bitsandbytes NF4',
        torch_version=torch.__version__, transformers_version=transformers.__version__,
        bitsandbytes_version=__import__('bitsandbytes').__version__,
        max_new_tokens=16, temperature=0, do_sample=False, seed=0,
        enable_thinking=False, prompt_context_limit=4096, truncation=False,
        cross_request_prefix_cache=False, load_seconds=time.perf_counter()-start,
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        speed_comparable_across_machines=False, failures_retained=True)
    Path('contract.json').write_text(json.dumps(contract, indent=2))
    with output.open('x', encoding='utf8') as stream:
        for row in rows:
            record = {k: row[k] for k in ('i', 'set', 'qi', 'type', 'gold')}
            begin = time.perf_counter()
            try:
                text = tokenizer.apply_chat_template([dict(role='user', content=row['prompt'])],
                    add_generation_prompt=True, tokenize=False, enable_thinking=False)
                inputs = tokenizer(text, add_special_tokens=False, return_tensors='pt').to('cuda')
                tokens = inputs['input_ids'].shape[1]
                if tokens + 16 > 4096:
                    raise ValueError(f'Context exceeds matched limit: {tokens}+16 > 4096')
                with torch.inference_mode():
                    generated = model.generate(**inputs, max_new_tokens=16, do_sample=False)
                content = tokenizer.decode(generated[0, tokens:], skip_special_tokens=True)
                parsed, value = parse_value(content)
                record.update(parsed=parsed, pick=value, content=content, input_tokens=tokens,
                    output_tokens=generated.shape[1]-tokens)
            except Exception as exc:
                record.update(parsed=False, pick=None, error=repr(exc))
            record['ms'] = round(1000*(time.perf_counter()-begin))
            stream.write(json.dumps(record, ensure_ascii=False)+'\n'); stream.flush()
    answers = [json.loads(line) for line in output.read_text().splitlines()]
    errors = sum('error' in r for r in answers)
    unparsed = sum(not r.get('parsed') for r in answers)
    summary = dict(expected=len(rows), saved=len(answers), errors=errors, unparsed=unparsed,
        correct=sum(bool(r.get('parsed')) and r['pick'] == r['gold'] for r in answers),
        completed_at=datetime.now(timezone.utc).isoformat(), peak_gpu_bytes=torch.cuda.max_memory_allocated(),
        model_adoption=False, independent_holdout=False)
    Path('summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
