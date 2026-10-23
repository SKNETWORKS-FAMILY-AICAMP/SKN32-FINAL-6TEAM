"""완료된 원본/우리 학습판 D3 답안을 같은 문항으로 비교하고 근거를 남긴다."""
from datetime import datetime
from pathlib import Path
import hashlib
import json
import math
import shutil

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
DAILY = ROOT / 'program/research/daily_rag_slm'


def main():
    now = datetime.now()
    stamp = now.strftime('%Y-%m-%d_%H%M%S')
    originals = []
    for job in ['winnow_original_d3', 'winnow_oos_d3']:
        folder = BASE / job
        stats = json.loads((folder / 'choice_counts.json').read_text(encoding='utf-8'))
        proof = json.loads((folder / 'verification.json').read_text(encoding='utf-8'))
        answer = folder / f"d_test_{stats['execution']['job']['tag']}.jsonl"
        rows = [json.loads(s) for s in answer.read_text(encoding='utf-8').splitlines()]
        assert len(rows) == len({r['i'] for r in rows}) == 360
        assert proof['remote_hash_match'] and proof['exact_id_gold_type_match']
        assert hashlib.sha256(answer.read_bytes()).hexdigest() == stats['answer_sha256']
        originals.append((stats, {r['i']: r for r in rows}))
    (original, before), (trained, after) = originals
    assert not original['our_training'] and trained['our_training']
    assert before.keys() == after.keys()
    assert all(before[i]['gold'] == after[i]['gold'] and before[i]['type'] == after[i]['type'] for i in before)
    for key in ['prompt_sha256', 'script_sha256', 'engine_version']:
        assert original['execution'][key] == trained['execution'][key]
    assert original['execution']['job']['model'] == trained['execution']['job']['model']
    assert trained['execution']['job']['adapter_sha256'] == '3a4f2646ed55ce3758bc0c6e66b6ee005840886c499da4189e2503b2301ef963'
    correct = lambda r: bool(r.get('parsed')) and not r.get('error') and r['pick'] == r['gold']
    paired = {}
    for name, positive in [('request', True), ('no_request', False)]:
        ids = [i for i, r in before.items() if (r['gold'] is not None) == positive]
        original_only = sum(correct(before[i]) and not correct(after[i]) for i in ids)
        trained_only = sum(correct(after[i]) and not correct(before[i]) for i in ids)
        n = original_only + trained_only
        p = min(1, 2 * sum(math.comb(n, k) for k in range(min(original_only, trained_only) + 1)) / 2 ** n) if n else 1
        paired[name] = {'total': len(ids), 'original_only_correct': original_only,
                        'trained_only_correct': trained_only, 'exact_two_sided_p': p}
    result = {'model': 'Winnow-E4B (Jev family)', 'suite': 'D3', 'saved_each': 360,
              'original_our_training': False, 'trained_our_training': True,
              'original': {k: original[k] for k in ['positive', 'negative', 'failed_or_unparsed', 'answer_sha256']},
              'trained': {k: trained[k] for k in ['positive', 'negative', 'failed_or_unparsed', 'answer_sha256']},
              'paired': paired, 'matching_prompt_script_engine_and_q8_base': True,
              'missing_each': 0, 'repetitions': 1, 'heldout_validation_complete': False,
              'final_ranking': False, 'product_adoption': False, 'speed_comparison': False}
    day = json.loads((DAILY / '2026-10-08.json').read_text(encoding='utf-8'))
    comparisons = day.setdefault('new_completed_comparisons', [])
    previous = [x for x in comparisons if x.get('model') == result['model'] and x.get('suite') == 'D3']
    if previous:
        assert len(previous) == 1 and not (ROOT / previous[0]['report']).exists(), 'Comparison already recorded'
        output, rel = ROOT / previous[0]['stats'], previous[0]['report']
        assert json.loads(output.read_text(encoding='utf-8')) == result
    else:
        output = BASE / f'winnow_original_vs_oos_d3_{stamp}.json'
        with output.open('x', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        rel = f'final_project_cs/wiki/records/reports/{stamp}_winnow_d3_training_comparison.md'
        comparisons.append({'model': result['model'], 'suite': 'D3', 'stats': output.relative_to(ROOT).as_posix(),
                            'report': rel, 'repetitions': 1, 'product_adoption': False})
    backups = []

    def save(path, text):
        p = ROOT / path
        if p.exists():
            b = p.parent / '_backup' / (stamp + '_winnow_d3_comparison') / p.name
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, b)
            backups.append(b.relative_to(ROOT).as_posix())
        p.write_text(text, encoding='utf-8')

    save('program/research/daily_rag_slm/2026-10-08.json', json.dumps(day, ensure_ascii=False, indent=2) + '\n')
    state = json.loads((DAILY / 'gpu_backlog_2026-10-08.json').read_text(encoding='utf-8'))
    state['gpu_B']['winnow_training_completion']['engine_smoke_complete'] = True
    state['gpu_B']['winnow_training_completion']['engine_smoke_evidence'] = {
        'suite': 'D3', 'saved': 360, 'expected': 360, 'failed_or_unparsed': 0,
        'verification': (BASE / 'winnow_oos_d3/verification.json').relative_to(ROOT).as_posix(),
        'adapter_argument': 'started.json records adapter; running engine command inspected with --lora',
        'report': rel}
    state['recorded_at'] = now.isoformat()
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json', json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    conclusion = 'Jev 계열 모델 중 Winnow-E4B의 동일 D3에서 우리 여행 학습판은 원본보다 정상 요청 정답이 95/120에서 109/120으로 늘고 잡담 오지목이 27/240에서 0/240으로 줄었다. 형식 실패는 13/360에서 0/360이다. 한 번의 개발/회귀 시험이며 나머지 세트·반복·독립 보류 자료 검증 전 제품 채택을 확정하지 않는다.'
    save('program/research/daily_rag_slm/2026-10-08.md', (DAILY / '2026-10-08.md').read_text(encoding='utf-8') +
         f'\n## {now:%H시%M분} — Winnow-E4B 원본/우리 학습판 D3 비교\n\n{conclusion}\n\n[비교 근거](../../../{rel}).\n')
    for path, link in [('final_project_cs/wiki/quality/slm-model-evaluation.md', '../records/reports/'),
                       ('final_project_cs/wiki/log.md', 'records/reports/')]:
        save(path, (ROOT / path).read_text(encoding='utf-8') +
             f'\n`[실측 {now:%Y-%m-%d}]` Jev 계열 모델 중 Winnow-E4B 원본/우리 여행 학습판의 동일 D3 비교를 완료했다. 전체 평가와 독립 보류 검증은 계속한다. [비교 근거]({link}{Path(rel).name}).\n')
    rows = [
        '# Winnow-E4B (Jev 계열) — 원본과 우리 여행 학습판 D3 비교', '', conclusion, '',
        '| 할 일 | 상태 | 진행 |', '|---|---|---|',
        '| 동일 문항·정답·입력·실행 조건 검증 | 완료 | 360/360 = 100% |',
        '| 우리 학습판 추가 시험 5종 | 진행 | 1/5 = 20% |', '',
        '| 지표 | 우리 여행 학습 없음 원본 | 우리 여행 학습판 |', '|---|---|---|',
        '| 정상 요청 정답 | 95/120 = 79.17% | 109/120 = 90.83% |',
        '| 잡담 오지목 | 27/240 = 11.25% | 0/240 = 0.00% |',
        '| 잡담 정답(null), 실패 포함 | 203/240 = 84.58% | 240/240 = 100% |',
        '| 형식 실패 | 13/360 = 3.61% | 0/360 = 0.00% |', '',
        '## 조건·통계·한계', '',
        '같은 Q8_0 기반 가중치, 입력 문항·정답·평가 코드 해시, llama.cpp 4ebdf2c를 확인했다. 우리 학습판의 시작 기록에는 보관한 어댑터 SHA256이 있고 실제 실행 명령의 --lora 지정을 확인했다. 360개 응답·해석이 완료됐으므로 이전 구조 검사만 통과한 상태에서 실제 엔진 평가 완료로 변경했다. 원본 오류13개(정상3·잡담10)는 오답으로 처리하며 분모에서 빼지 않았다. 오지목27개와 잡담 형식 실패10개를 혼동하지 않는다.', '',
        f"같은 문항에서 정상 요청 원본만 정답{paired['request']['original_only_correct']}, 학습판만 정답{paired['request']['trained_only_correct']}; 양측 정확검정 p={paired['request']['exact_two_sided_p']:.8g}. 잡담 원본만 정답{paired['no_request']['original_only_correct']}, 학습판만 정답{paired['no_request']['trained_only_correct']}; p={paired['no_request']['exact_two_sided_p']:.8g}. 이는 고정된 개발 자료의 같은 문항 비교이며 일반 질의 전체의 우열이나 독립 보류 성능을 뜻하지 않는다.", '',
        '다른 개발 세트·어려운 함정·혼합 문장과 독립 보류 자료, 반복 검증이 남아 있다. 원본 보존·별도 어댑터 학습은 완료했고 제품 채택은 보류한다. 모델 정확도 비교이며 엔진 속도 비교는 하지 않았다.', '',
        f'[분자·분모·같은 문항 검정 JSON](../../../../{output.relative_to(ROOT).as_posix()}) · [원본 답안 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_d3/verification.json) · [학습판 답안 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_oos_d3/verification.json).', '',
        'GPU 서버 A는 다음 D 평가 실행, 준비된 D2/H/MX 세 작업 대기를 확인했다. GPU 서버 B는 Spark 학습 실행과 기존 두 학습 예약 및 다운로드 준비 후보 한 개를 유지한다. 다운로드 준비 후보의 공간은 직전에 재확인한다. 실행기를 추가하거나 작업을 중단하지 않았다.', '',
        '## 수정 직전 백업', '']
    rows += [f'- [{p}](../../../../{p})' for p in backups]
    save(rel, '\n'.join(rows) + '\n')
    print(json.dumps({'report': rel, 'stats': output.relative_to(ROOT).as_posix(), 'paired': paired,
                      'backup': stamp + '_winnow_d3_comparison'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
