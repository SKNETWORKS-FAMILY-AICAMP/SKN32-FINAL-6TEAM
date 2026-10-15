"""고정 D3의 동일 문항으로 ARM 캐시 순서 진단을 준비한다. 모델 호출은 없다."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import shutil


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    source = Path('datasets/travel/arm_serving_20261008/d3.json')
    data = source.read_bytes()
    rows = json.loads(data)
    groups = defaultdict(list)
    marker = '\n\n고객 질문:'
    for row in rows:
        if marker not in row['prompt']:
            raise ValueError('일정/질문 경계 불일치')
        groups[sha(row['prompt'].split(marker, 1)[0].encode())].append(row)
    eligible = sorted(key for key, group in groups.items()
                      if sum(r['gold'] is not None for r in group) >= 4
                      and sum(r['gold'] is None for r in group) >= 8)
    if len(eligible) < 5:
        raise ValueError('고정 진단에 필요한 일정 다섯 개 부족')
    chosen, context = [], {}
    for key in eligible[:5]:
        group = sorted(groups[key], key=lambda r: r['i'])
        subset = [r for r in group if r['gold'] is not None][:4]
        subset += [r for r in group if r['gold'] is None][:8]
        for row in sorted(subset, key=lambda r: r['i']):
            chosen.append(row)
            context[str(row['i'])] = key
    assert len(chosen) == len({r['i'] for r in chosen}) == 60
    assert sum(r['gold'] is not None for r in chosen) == 20
    original = {r['i']: r for r in rows}
    assert all(r == original[r['i']] for r in chosen)
    root = Path('datasets/travel/arm_cache_diagnostic_20261009')
    root.mkdir(exist_ok=False)
    (root / 'raw').mkdir()
    (root / 'processed').mkdir()
    (root / 'scripts').mkdir()
    (root / 'raw/d3_source.json').write_bytes(data)
    payload = (json.dumps(chosen, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (root / 'processed/d3_grouped60.json').write_bytes(payload)
    shutil.copy2(__file__, root / 'scripts/prepare.py')
    baseline = Path('program/scripts/plan_qa_bench/results/heartbeat_20261009_0754/arm_completed/e4bt_q4_d3/answers.jsonl')
    answers = {r['i']: r for r in map(json.loads, baseline.read_text(encoding='utf-8').splitlines())}
    record = dict(source=str(source), source_sha256=sha(data), processed_sha256=sha(payload),
                  exact_source_records_preserved=60, expected=60, normal=20, null=40,
                  context_groups=5, context_by_id=context,
                  source_baseline_correct=sum(answers[r['i']]['correct'] for r in chosen),
                  ABBA_cache_flags=[True, False, False, True], repeats=4,
                  repeated_rows_expected=240, independent_unique_questions=60,
                  primary_latency_population='55 non-first requests within the five context groups; also report all 60',
                  pass_criteria={'warm_median_reduction_vs_matched_nocache_min_pct':30,
                                 'new_errors_allowed':0, 'correct_selection_loss_allowed':0},
                  interpretation='Development/cache locality diagnostic; never add repetitions to independent accuracy denominator; not product adoption')
    (root / 'preprocess_stats.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (root / 'REPORT.md').write_text('''# ARM 동일 일정 캐시 진단 자료

기존 자체 작성 여행 D3에서 60문항(정상20·선택 없음40)을 고정 선택했다.
일정 다섯 개당 12문항을 붙여 처리한다. 문항 ID·정보·문구·정답은 원본 그대로다.
원본 전체와 해시는 raw 및 preprocess_stats.json에 보존한다.

캐시 사용/미사용/미사용/사용 네 회를 같은 순서·모델·엔진·시드로 비교한다.
총 호출240은 고유 문항60의 반복이며 독립 정확도240개로 합치지 않는다.
각 일정의 첫 요청5개와 이후55개 지연·실패·캐시 토큰을 따로 보고한다.
입력 예산·성공률 변경 없이 이후 요청의 중간 지연30% 이상 감소를 진단 목표로 고정했다.
실측 전이며 개선 완료·채택·실제 고객 분포를 의미하지 않는다.

자료는 자체 합성 여행 입력이며 외부 소개글·고객 개인정보·쇼핑몰 자료를 쓰지 않았다.
원본을 수정하지 않았다. scripts/prepare.py로 선택 방법을 재현할 수 있다.
''', encoding='utf-8')
    print(json.dumps({k:v for k,v in record.items() if k!='context_by_id'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
