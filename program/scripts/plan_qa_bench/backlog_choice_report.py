"""고정 D/D2/D3 답안을 원문 그대로 집계하고 실패를 분모에 남긴다."""
import hashlib
import json
import sys
from pathlib import Path
from backlog_mx_report import summarize, valid

HERE = Path(__file__).resolve().parent
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
sys.stdout.reconfigure(encoding='utf-8')


def main():
    job, suite = sys.argv[1:3]
    assert suite in {'D', 'D2', 'D3'}
    folder = HERE / 'results/gpu_backlog_20261008' / job
    execution = json.loads((folder / 'started.json').read_text(encoding='utf-8'))
    name = {'D': 'all_prompts.json', 'D2': 'all_prompts_d2.json', 'D3': 'all_prompts_d3.json'}[suite]
    gold_path = Path(fixture(name))
    gold_hash = hashlib.sha256(gold_path.read_bytes()).hexdigest()
    assert gold_hash == execution['prompt_sha256'], 'Frozen prompt hash mismatch'
    gold = json.loads(gold_path.read_text(encoding='utf-8'))
    answer = folder / f"d_test_{execution['job']['tag']}.jsonl"
    rows = [json.loads(line) for line in answer.read_text(encoding='utf-8').splitlines()]
    run, ref = {r['i']: r for r in rows}, {r['i']: r for r in gold}
    assert len(rows) == len(run) and len(gold) == len(ref), 'Duplicate IDs'
    assert set(run) <= set(ref), 'Unexpected IDs'
    assert all(r['gold'] == ref[i]['gold'] and r['type'] == ref[i]['type'] for i, r in run.items())
    single = [r for r in gold if r['type'] != 'compound_intent']
    positive = summarize([r for r in single if r['gold'] is not None], run)
    negative = summarize([r for r in single if r['gold'] is None], run)
    failed = [r for r in rows if not valid(r)]
    result = {
        'model': execution['job']['label'], 'our_training': execution['job']['our_training'],
        'publisher_training': execution['job'].get('publisher_training') or ('Instruct release' if execution['job']['label'].startswith('Gemma') else 'See publisher model card; exact training method not verified in this run'),
        'suite': suite, 'saved': len(rows), 'expected': len(gold), 'missing': len(set(ref) - set(run)),
        'failed_or_unparsed': len(failed), 'single_choice_expected': len(single),
        'compound_diagnostic_total': len(gold) - len(single),
        'positive': positive, 'negative': negative,
        'subtypes': {t: summarize([r for r in gold if r['type'] == t], run) for t in sorted({r['type'] for r in gold})},
        'failed_records': failed, 'answer_sha256': hashlib.sha256(answer.read_bytes()).hexdigest(),
        'gold_sha256': gold_hash, 'execution': execution, 'repetitions': 1, 'final_ranking': False,
    }
    with (folder / 'choice_counts.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    display_model = ('Jev 계열 모델 중 ' if 'Winnow' in result['model'] else '') + result['model']
    model_role = '우리 여행 학습판' if result['our_training'] else '우리 여행 학습 없음 원본'
    lines = [f"# {display_model} — {suite} 평가 ({model_role})", '',
             f"우리 자료 추가 학습 여부: {result['our_training']}. 개발사 학습: {result['publisher_training']}.", '',
             '| 할 일 | 상태 | 진행 |', '|---|---|---|',
             f"| 답안 보관 | 완료 | {len(rows)}/{len(gold)} = {100*len(rows)/len(gold):.2f}% |"]
    for label, data, key in [('정상 요청 정답', positive, 'correct'), ('요청 없음 오지목', negative, 'false_pick')]:
        if data['total']:
            lines.append(f"| {label} | 실측 | {data[key]}/{data['total']} = {100*data[key]/data['total']:.2f}% |")
    lines += [f"| 실패·해석 불가 | 실측 | {len(failed)}/{len(gold)} = {100*len(failed)/len(gold):.2f}% |", '',
              f"전체 {len(gold)}개 중 단일 선택 집계는 {len(single)}개입니다. 복합 요청 {len(gold)-len(single)}개는 유형별 진단에 별도로 남기며 단일 선택 정확도로 해석하지 않습니다.", '',
              '누락·실패를 해당 문항 유형의 분모에서 빼지 않습니다. 실패한 배열·문자열 출력을 번호나 null로 고쳐 정답 처리하지 않습니다. 실패는 실제 오지목과 별도로 기록하고 정확도에서는 오답입니다.', '',
              '[집계·실패 원문·고정 입력 해시·실행 조건](choice_counts.json). 고정 입력 SHA256과 실행 당시 해시를 대조했고 문항 ID·정답·유형을 확인했습니다. 기존 개발/회귀 자료의 모델 실행 1회이며 전체 비교군과 독립 보류·반복 검증 전 순위를 확정하지 않습니다.']
    with (folder / 'choice_report.md').open('x', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(json.dumps({k: result[k] for k in ['suite', 'saved', 'expected', 'missing', 'failed_or_unparsed', 'positive', 'negative', 'answer_sha256']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
