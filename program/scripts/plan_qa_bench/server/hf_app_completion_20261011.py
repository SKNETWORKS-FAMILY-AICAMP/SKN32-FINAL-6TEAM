"""고정 여행 질문의 HF NF4 일반 생성과 유한 안정성을 진단한다.

llama.cpp의 JSON 문법 강제와 다른 경로다. 같은 질문에 스키마를 명시하되
토큰을 강제하지 않는다. 반복 관측을 독립 정확도나 모델 채택으로 쓰지 않는다.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time


def pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('중복 JSON 키')
        result[key] = value
    return result


def validate(value, schema):
    """이 고정 앱 스키마에 실제 등장하는 키워드만 지원하고 나머지는 거부한다."""
    unsupported = set(schema) - {'type', 'properties', 'required', 'enum', 'items', 'maxItems'}
    if unsupported:
        raise ValueError('지원하지 않는 스키마 키워드: ' + str(sorted(unsupported)))
    kind = schema['type']
    accepted = {'object': isinstance(value, dict), 'array': isinstance(value, list),
                'string': isinstance(value, str), 'integer': type(value) is int}
    if kind not in accepted or not accepted[kind]:
        raise ValueError('JSON 타입 불일치')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError('허용 값 불일치')
    if kind == 'object':
        if not set(schema.get('required', [])).issubset(value):
            raise ValueError('필수 항목 누락')
        for key, child in schema.get('properties', {}).items():
            if key in value:
                validate(value[key], child)
    if kind == 'array':
        if len(value) > schema.get('maxItems', len(value)):
            raise ValueError('배열 길이 초과')
        for child in value:
            validate(child, schema['items'])


def inspect(content, finish_reason, gold, schema):
    result = dict(parsed=False, schema_valid=False, correct=False,
                  finish_reason=finish_reason, empty_content=not content.strip())
    try:
        obj = json.loads(content, object_pairs_hook=pairs_no_duplicates,
                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
        result['parsed'] = isinstance(obj, dict)
        validate(obj, schema)
        result['schema_valid'] = True
        result['correct'] = finish_reason == 'stop' and all(obj.get(k) == v for k, v in gold.items())
    except (ValueError, TypeError, KeyError) as error:
        result['validation_error'] = str(error)
    return result


def gate(rows):
    selected = [r for r in rows if r['budget'] == 800]
    ids = {(r['case'], r['history'], r['repeat']) for r in selected}
    return (len(selected) == len(ids) == 24
            and len({(r['case'], r['history']) for r in selected}) == 12
            and {r['repeat'] for r in selected} == {1, 2}
            and all(r['correct'] and not r.get('error') for r in selected))


def save(path, value):
    if path.exists():
        import shutil
        backup = path.parent / '_backup' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup.mkdir(parents=True); shutil.copy2(path, backup / path.name)
    temp = path.with_suffix('.tmp'); temp.write_text(json.dumps(value, indent=2)); temp.replace(path)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--job', required=True, type=Path)
    job = json.loads(parser.parse_args().job.read_text())
    prompt_bytes = Path(job['prompts']).read_bytes()
    assert hashlib.sha256(prompt_bytes).hexdigest() == job['prompt_sha256']
    rows = json.loads(prompt_bytes)
    assert len(rows) == len({r['i'] for r in rows}) == job['expected'] == 48
    assert not Path('answers.jsonl').exists()
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    torch.set_num_threads(8); torch.manual_seed(20261011)
    started = time.monotonic()
    tok = AutoTokenizer.from_pretrained(job['model'], local_files_only=True)
    tok.padding_side = 'left'
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(job['model'], local_files_only=True,
        quantization_config=quant, dtype=torch.bfloat16, device_map={'': 0})
    if job.get('adapter'):
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, job['adapter'], local_files_only=True)
    model.eval()
    Path('contract.json').write_text(json.dumps(dict(job=job, torch=torch.__version__,
        transformers=transformers.__version__, load_seconds=time.monotonic()-started,
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        forced_grammar=False, schema_in_prompt=True, prefix_cache=False,
        independent_accuracy=False, adoption=False), indent=2))

    def generate(selected):
        begin = time.monotonic(); records = []
        try:
            texts = []
            for row in selected:
                messages = [dict(m) for m in row['payload']['messages']]
                schema = row['payload']['response_format']['json_schema']['schema']
                messages[-1]['content'] += '\nReturn exactly one JSON object matching this schema, without commentary:\n' + json.dumps(schema, ensure_ascii=False)
                texts.append(tok.apply_chat_template(messages, add_generation_prompt=True,
                    tokenize=False, enable_thinking=False))
            inputs = tok(texts, padding=True, add_special_tokens=False, return_tensors='pt').to('cuda')
            width = inputs['input_ids'].shape[1]; budget = selected[0]['budget']
            assert all(r['budget'] == budget for r in selected)
            if width + budget > 4096:
                raise ValueError('문맥 한도 초과; 입력을 자르지 않습니다')
            with torch.inference_mode():
                output = model.generate(**inputs, max_new_tokens=budget, do_sample=False)
            eos = model.generation_config.eos_token_id
            eos = {eos} if isinstance(eos, int) else set(eos or [])
            for row, ids in zip(selected, output[:, width:]):
                tokens = ids.tolist(); stop = next((i for i, t in enumerate(tokens) if t in eos), None)
                finish = 'stop' if stop is not None else 'length'
                useful = tokens if stop is None else tokens[:stop]
                content = tok.decode(useful, skip_special_tokens=True)
                schema = row['payload']['response_format']['json_schema']['schema']
                records.append(dict(inspect(content, finish, row['gold'], schema), content=content,
                    raw_tokens=useful, input_tokens=int(inputs['attention_mask'][len(records)].sum()),
                    output_tokens=len(useful)))
        except Exception as error:
            records = [dict(parsed=False, schema_valid=False, correct=False, error=repr(error)) for _ in selected]
        seconds = time.monotonic()-begin
        for row, record in zip(selected, records):
            record.update(i=row['i'], case=row['case'], history=row['history'], repeat=row['repeat'],
                budget=row['budget'], seconds_batch=seconds, batch_size=len(selected),
                observed_at_utc=datetime.now(timezone.utc).isoformat())
        return records

    baseline = []
    with Path('answers.jsonl').open('x') as answers:
        blocked = None
        for row in rows:
            record = (dict(i=row['i'], case=row['case'], history=row['history'], repeat=row['repeat'],
                budget=row['budget'], parsed=False, schema_valid=False, correct=False,
                attempted=False, error='not_attempted_after_runtime_error: ' + blocked)
                if blocked else generate([row])[0])
            if record.get('error'):
                blocked = record['error']
            baseline.append(record)
            answers.write(json.dumps(record, ensure_ascii=False)+'\n'); answers.flush()
    eligible = gate(baseline); stability = []; stop = 'prerequisite_failed'
    if eligible:
        cases = [r for r in rows if r['budget'] == 800 and r['repeat'] == 1]
        begin = time.monotonic(); index = 0; failed_streak = 0; last_resource = -60
        stop = 'duration_completed'
        with Path('observations.jsonl').open('x') as stream:
            while time.monotonic()-begin < job['duration_seconds']:
                if os.statvfs('.').f_bavail*os.statvfs('.').f_frsize < job['minimum_free_bytes']:
                    stop = 'storage_guard'; break
                size = 1 + int((time.monotonic()-begin)//3600) % 2
                selected = [cases[(index+k) % 12] for k in range(size)]
                records = generate(selected)
                for record in records:
                    record['observation'] = index; index += 1; stability.append(record)
                    failed_streak = 0 if record['correct'] else failed_streak+1
                    stream.write(json.dumps(record, ensure_ascii=False)+'\n'); stream.flush()
                if time.monotonic()-begin-last_resource >= 60:
                    resource = dict(observed_at_utc=datetime.now(timezone.utc).isoformat(), batch_size=size,
                        allocated_gpu_bytes=torch.cuda.memory_allocated(), peak_gpu_bytes=torch.cuda.max_memory_allocated(),
                        rss_status=Path('/proc/self/status').read_text().split('VmRSS:')[1].splitlines()[0].strip())
                    with Path('resources.jsonl').open('a') as resource_stream:
                        resource_stream.write(json.dumps(resource)+'\n')
                    last_resource = time.monotonic()-begin
                save(Path('progress.json'), dict(attempted=len(stability), correct=sum(r['correct'] for r in stability),
                    elapsed_seconds=time.monotonic()-begin, batch_size=size))
                if failed_streak >= 3 or any(r.get('error') for r in records):
                    stop = 'runtime_or_consecutive_failure'; break
    summary = dict(expected=48, saved=len(baseline), errors=sum(bool(r.get('error')) for r in baseline),
        unparsed=sum(not r['parsed'] for r in baseline), correct=sum(r['correct'] for r in baseline),
        stability_eligible=eligible, stability_attempted=len(stability),
        stability_correct=sum(r['correct'] for r in stability), stop=stop,
        peak_gpu_bytes=torch.cuda.max_memory_allocated(), independent_holdout=False, model_adoption=False,
        completed_at=datetime.now(timezone.utc).isoformat())
    Path('summary.json').write_text(json.dumps(summary, indent=2)); print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
