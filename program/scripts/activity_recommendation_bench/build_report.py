"""Write a fresh report from saved actual results, without any provider calls."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'datasets/travel/activity_recommendation_bench_20261009'
RESEARCH = ROOT / 'program/research/activity_recommendation_20261009'
SUMMARY = DATA / 'analysis/main-20261009-v1-final/summary.json'
NAMES = {'rule':'규칙 추천', 'nano_direct':'nano 직접', 'luna_direct':'Luna 직접',
         'jev_code':'Jev API(유료)+코드', 'jev_nano':'Jev API(유료) 선별+nano', 'jev_luna':'Jev API(유료) 선별+Luna'}


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def fresh(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(text)


def run():
    s = json.loads(SUMMARY.read_text(encoding='utf-8'))
    if not s['complete']:
        raise RuntimeError('main_run_incomplete')
    main_rows = rows(DATA / 'runs/main-20261009-v1/results.jsonl')
    diagnostic = rows(DATA / 'runs/output-limit-4096-20261009-v1/results.jsonl')
    ledger = rows(DATA / 'ledger.jsonl')
    reserved = {r['call_id']:r for r in ledger if r['event']=='reserved'}
    finished = {r['call_id']:r for r in ledger if r['event']=='finished'}
    known = sum(r['cost_usd'] for r in finished.values() if r['usage_known'])
    unknown = sum(finished.get(k,v)['cost_usd'] for k,v in reserved.items() if not finished.get(k,{}).get('usage_known'))
    total = known + unknown
    completed = len(finished)
    checked = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
    line = []
    add = line.append
    add('# Activity 대체 추천 구조와 모델 실제 비교')
    add('')
    add('**이번 가상 추천 시험에서는 Luna 직접 추천이 nano 직접 추천보다 정확하고 저렴했습니다. Jev API(유료) 선별을 추가한 Luna 경로는 비용이 늘었고 순위 품질 개선은 확인되지 않았습니다.** 방문 조건을 코드로 확인하고 모델에 취향 의미 판단을 맡기는 방향은 타당하지만, 모든 요청에 두 모델을 붙이는 설계는 이번 결과로 지지되지 않습니다. 실제 고객 만족을 검증한 결과는 아닙니다.')
    add('')
    add('| 할 일 | 상태 | 진행 |\n|---|---|---|')
    add('| 문헌·공식 자료 | 완료 | 43/43 = 100% |')
    add('| 실행·분석 단위 검사 | 통과 | 71/71 = 100% |')
    add(f"| 본 비교 결과 기록 | 완료 | {s['observed_rows']}/{s['scheduled_rows']} = 100% |")
    add(f'| 출력 한도 추가 진단 | 기록 | {len(diagnostic)}/10 = {len(diagnostic)/10:.0%} |')
    add('')
    add(f'보고 시각: {checked}. 문헌 확인 경계: **2026-10-09 KST**. 운영 앱·DB·배포 설정은 변경하지 않았습니다. 지정된 OpenAI API용 키와 TypeSafe API 키로 실제 호출했습니다. 개인용 OpenAI 키로 대체하지 않았습니다.')
    add('')
    add('## 실제 비교 결과')
    add('')
    add('본 비교는 **24개 가상 문제 × 3회 = 구성별 72시도**입니다. 각각 후보 14개 중 방문 조건을 통과한 9개를 평가합니다. 처음 두 회는 같은 후보 순서, 셋째는 순서 변형입니다. 모델 순서는 교대로 배치했습니다. 출력·호출 실패를 0점으로 포함했으며 실패 비용도 포함합니다.')
    add('')
    add('| 구성 | 정상 출력 | 1위 적중 | 순위 점수 nDCG@3 | 정답 상위3 회수율 | 1회 평균 비용 USD | 지연 p50 / p95 초 |')
    add('|---|---:|---:|---:|---:|---:|---:|')
    for arm,a in s['arms'].items():
        m=a['all_scheduled_means'];n=a['scheduled_attempts']
        add(f"| {NAMES[arm]} | {a['successful_outputs']}/{n} | {round(m['top1_correct']*n)}/{n} = {m['top1_correct']:.1%} | {m['ndcg3']:.4f} | {m['recall3']:.1%} | {a['path_cost_sum_usd']/n:.7f} | {a['path_latency_p50_ms']/1000:.3f} / {a['path_latency_p95_ms']/1000:.3f} |")
    add('')
    add('nDCG는 상위 3개 효용을 순서에 따라 할인한 합을 최선의 합으로 나눈 점수입니다. 이득 함수는 선형 효용입니다. 회수율의 분모는 미리 계산한 정답 상위 3개이며, 모든 관련 장소의 비율이 아닙니다. 규칙 구성의 지연 0은 외부 요청 지연이며 코드 연산 시간을 따로 계측하지 않았습니다.')
    nano_cost=s['arms']['nano_direct']['path_cost_sum_usd']/72
    luna_cost=s['arms']['luna_direct']['path_cost_sum_usd']/72
    cascade_cost=s['arms']['jev_luna']['path_cost_sum_usd']/72
    add('')
    add(f'Luna 직접 경로의 평균 비용은 nano 직접 경로보다 {(1-luna_cost/nano_cost):.2%} 낮았습니다. Jev API(유료) 선별+Luna는 Luna 직접 경로보다 {(cascade_cost/luna_cost-1):.2%} 비쌌습니다. 각 비율의 기준은 해당 경로 72시도의 사용량 기반 평균 비용입니다. 선별+Luna의 중앙 지연은 더 짧았으므로 모든 지표에서 열등하다는 뜻은 아닙니다.')
    add('')
    add('| 비교 | 1위 적중 차이·95% 구간 | nDCG 차이·95% 구간 |')
    add('|---|---:|---:|')
    for key,label in [('luna_direct_minus_nano_direct','Luna 직접 − nano 직접'),('jev_luna_minus_luna_direct','선별+Luna − Luna 직접'),('jev_nano_minus_nano_direct','선별+nano − nano 직접'),('jev_luna_minus_jev_code','선별+Luna − Jev API+코드')]:
        c=s['paired_case_bootstrap'][key];t=c['top1_correct'];d=c['ndcg3']
        add(f"| {label} | {t['mean_difference']*100:+.1f}%p [{t['ci95'][0]*100:+.1f}, {t['ci95'][1]*100:+.1f}] | {d['mean_difference']:+.4f} [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}] |")
    mc=s['mcnemar_nano_vs_luna_first_repeat']
    add('')
    add(f"각 문제의 반복 평균 차이를 문제 단위로 5,000회 재표집했습니다. nano/Luna 첫 회만 사용한 McNemar: nano만 맞음 {mc['nano_only_correct']}, Luna만 맞음 {mc['luna_only_correct']}, 양측 p={mc['exact_two_sided_p']:.5f}, 문제 쌍 {mc['scheduled_pairs']}개입니다. 구간이 0을 포함하면 그 지표의 우열이 구분되지 않습니다. 여러 비교는 탐색적이며 다중 비교 보정을 하지 않았습니다. 공유 서술 틀이 있으므로 이 구간은 실제 고객 모집단의 구간이 아닙니다.")
    add('')
    add('## 선별의 효과와 위험')
    add('')
    f=s['arms']['jev_luna']['filter'];n=f['scheduled_denominator']
    add(f"Jev API(유료)가 낸 특성 확률과 코드 가중합으로 상위 4개만 남기면 최고 정답 보존은 {round(f['jev_only_top1_preserved_all_scheduled']*n)}/{n} = {f['jev_only_top1_preserved_all_scheduled']:.1%}, 정답 상위3 회수는 {f['jev_only_top3_recall_all_scheduled']:.1%}입니다. 이번 연쇄는 규칙 상위 2개를 추가 보호하여 최고 정답 보존 {round(f['top1_preserved_all_scheduled']*n)}/{n} = {f['top1_preserved_all_scheduled']:.1%}, 정답 상위3 회수 {f['top3_recall_all_scheduled']:.1%}였습니다. 따라서 연쇄 결과를 선별 모델 단독 성능이라고 부르지 않습니다. Noul 확률을 이 자료에서 따로 보정하지 않고 기대 취향 점수로 결합했습니다. 이 결합 방식의 성능과 다른 Score·임계값·추가 학습 구성은 구분해야 합니다.")
    add('')
    add('후속 모델은 선별 단계에서 사라진 후보를 회복할 수 없습니다. 선별 비용은 후속 입력 절감보다 작아야 하고, 출력·추론 토큰 감소까지 실제로 확인해야 합니다. 이 시험은 후보 수를 9개로 고정했으므로 더 큰 후보 목록에서의 비용 손익을 직접 측정하지 않았습니다.')
    add('')
    add('| 구성 | 동일 입력 상위3 일치 | 순서 변형 상위3 일치 |')
    add('|---|---:|---:|')
    for arm,c in s['consistency'].items():
        x=c['same_input'];y=c['permuted_input']
        add(f"| {NAMES[arm]} | {x['identical_top3_pairs']}/{x['scheduled_pairs']} = {x['agreement_all_scheduled']:.1%} | {y['identical_top3_pairs']}/{y['scheduled_pairs']} = {y['agreement_all_scheduled']:.1%} |")
    add('')
    add('빈 실패 응답끼리는 일치로 계산하지 않았습니다. 순서 변형 비교에는 모델의 통상 변동도 섞이므로 순서 편향만의 인과 효과를 확정하지 않습니다.')
    add('')
    add('## 비용·토큰·실패')
    add('')
    add('2026-10-09 공식 표준 단가는 100만 토큰당 nano 입력$0.20·캐시 읽기$0.02·출력$1.25, Luna 입력$0.10·캐시 읽기$0.01·캐시 쓰기$0.125·출력$0.50입니다. Jev API(유료)는 입력$0.042·출력 무료입니다. 따라서 이 두 모델의 현재 토큰 단가 기준으로 nano가 가장 저렴하다는 말은 맞지 않습니다. [nano 공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-5.4-nano) · [OpenAI 가격표](https://developers.openai.com/api/docs/pricing) · [TypeSafe 가격 소개](https://typesafe.ai/blog/introducing-system-one-models-and-jev).')
    add('')
    add(f'예비·본 비교·추가 진단 전체 기록은 **{completed}/{len(reserved)}개 호출 종료**, 사용량 기반 예상 과금 **${known:.6f}**, 사용량 미확인 예약 상한 **${unknown:.6f}**, 합계 **${total:.6f} / $0.50**입니다. 결제 명세서와 계정 잔액을 조회한 값은 아닙니다. 계정 측 별도 지출 상한은 확인하지 못했으므로 이 실행기에 독립 상한을 두었습니다.')
    add('')
    add('표의 선별 경로 비용에는 Jev API(유료) 비용이 각각 포함됩니다. 본 시험에서는 같은 선별 응답을 두 재정렬 경로가 공유하므로 표의 경로 비용을 모두 더하면 실험 총지출을 과대계산합니다. 전체 지출은 비용 기록의 요청 ID를 중복 제거해 계산했습니다. 자동 재시도와 웹 검색은 0회입니다.')
    add('')
    add('| 구성의 직접 호출 단계 | 입력 | 캐시 읽기 | 캐시 쓰기 | 출력 전체 | 그중 추론 |')
    add('|---|---:|---:|---:|---:|---:|')
    for arm,a in s['arms'].items():
        u=a['own_ranker_usage']
        add(f"| {NAMES[arm]} | {u['input_tokens']} | {u['cached_read_tokens']} | {u['cache_write_tokens']} | {u['output_tokens']} | {u['reasoning_output_tokens']} |")
    add('')
    add('선별+nano/Luna 행의 토큰은 후속 순위 모델 자체 사용량이며 선별 사용량은 Jev API+코드 행에 따로 있습니다. 입력 전체에는 캐시 토큰이 포함되어 있으므로 다시 더하지 않습니다. 출력 전체에는 추론 토큰이 포함됩니다. 캐시 쓰기 단가는 해당 입력의 대체 단가입니다.')
    add('')
    for arm,a in s['arms'].items():
        if arm=='rule':continue
        add(f"- {NAMES[arm]}: 반환 모델 {', '.join(a['returned_models'])}; 출력 상태 {a['status_counts']}; 검증 실패 {a['validation_failure_counts']}; HTTP 실패 {a['http_failure_counts']}.")
    add('')
    add('이번에는 nano와 Luna 모두 `low`, 출력 상한 1,536, 동일 JSON 계약을 사용했습니다. nano의 기본 `none` 등 모델별 최적 설정을 모두 탐색한 시험이 아닙니다. 별칭으로 호출하고 실제 반환 이름을 저장했으나, 공급자가 고정 스냅샷을 노출하지 않는 모델의 미래 재현을 완전히 보장하지 않습니다.')
    add('')
    add('## 출력 한도 4,096 추가 진단')
    add('')
    add('nano에서 추론 토큰이 한도를 소진하는 실패를 확인해 추가한 별도 진단입니다. 정답 결과로 문제를 고르지 않고 ID 순 첫 5개를 두 모델에 같은 한도로 한 번씩 호출했습니다. 본 72시도 점수와 합치지 않습니다. [사전 진단 기준](../../../../program/scripts/activity_recommendation_bench/diagnostic-plan.md).')
    add('')
    add('| 모델 | 관측/예정·상태 | 정상/관측 | 1위 적중/관측 | 관측 nDCG | 관측 평균 비용 USD | 관측 지연 평균 초 |')
    add('|---|---:|---:|---:|---:|---:|---:|')
    for arm in ('nano_direct','luna_direct'):
        r=[x for x in diagnostic if x['arm']==arm]
        if r:
            add(f"| {NAMES[arm]} | {len(r)}/5·{'완료' if len(r)==5 else '부분 실행'} | {sum(x['status']=='ok' for x in r)}/{len(r)} | {sum(x['metrics']['top1_correct'] for x in r)}/{len(r)} | {mean(x['metrics']['ndcg3'] for x in r):.4f} | {mean(x['cost_usd'] for x in r):.7f} | {mean(x['latency_ms'] for x in r)/1000:.3f} |")
        else:
            add(f"| {NAMES[arm]} | 0/5·미실행 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 |")
    add('')
    add('5개·1회이므로 모델 일반 성능 우위의 근거가 아닙니다. 한도를 높여도 취향 판단 오답이 남는지와 끝까지 답하는 데 필요한 비용·지연을 확인하는 용도입니다.')
    add('')
    add('## 이전 Activity 담당자 시험을 어떻게 평가할 것인가')
    add('')
    add('**“장점이 전혀 없다”는 판단은 과합니다. “그 시험으로 추천 모델 채택을 정당화할 수 없다”는 지적은 맞습니다.** 비정형 공지를 정리하는 능력과 고객 취향의 대체 추천은 다른 문제입니다.')
    add('')
    add('| 확인 항목 | 실제 확인한 내용 | 해석 |\n|---|---|---|')
    add('| 0.987 | 첫 실행180관측 중 정답 있는 오프라인52문제×3회=156판정에서 허용 정답154개, 98.7179%. 실시간24실패는 그 분모 밖 | 저장 결과로 재현한 채점 값이지만 추천·전체 경로 정확도 아님 |')
    add('| 정답 작성 | Claude가 문제·정답 초안을 작성, 사람 검수 미확인 | 자체 합성 자료의 대표성과 정답 독립성 제한 |')
    add('| 모름 허용 | 52문제 중11개는 원래 기대값 외에 모름도 허용. 모름만 정답인3개를 합치면 총14개. 단일 기대값 일치는140/156 | 89.7%는 다른 채점 기준이며 곧바로 진짜 정확도라고 부를 수 없음 |')
    add('| 비교 규칙 | 보고서의 구판 규칙 24/52, 현재 시험 브랜치 규칙 재생 33/52 | 개선량 판단에 기준판 고정 필요 |')
    add('| 실시간 조회 | 두 번째 24요청 중 정상 응답16·429실패8, 사람 정답 없음 | 정상 응답 비율과 정확도 구분 필요 |')
    add('| 고객 경로 | 시험 브랜치 기본 shadow, 고객에게는 규칙 답을 반환 | 위험을 낮추는 병행 검증으로서 장점; 고객 적용 완료 증거 아님 |')
    add('')
    add('원문 해석 시험은 복잡한 휴일 예외·비정형 문구를 정리하고 모델 SDK·스키마·실패·비용을 점검하는 데 유용합니다. 저장된 응답 덕분에 숫자도 다시 계산할 수 있었습니다. 반면 취향 적용, 후보 순위, 선별 누락, 중요도 변화, 실제 고객의 만족은 측정하지 않았습니다. 위험 오판 2/156도 허용 정확도 하나에 가려지면 안 됩니다.')
    add('')
    add('검색 비용 때문에 모델만 바꿔도 큰 절감이 없다는 설명에는 제한적으로 근거가 있습니다. 저장된 두 번째 실시간 시험은 검색45회가 포함되어 nano 환산$0.516535, **동일 사용량·검색 횟수 가정의 Luna 예상**$0.481462로 차이$0.035073·약6.79%입니다. 실제 Luna를 호출한 비교가 아니므로 Luna의 응답 품질·검색 횟수·토큰 사용량 차이는 알 수 없습니다. 원문 오프라인 시험의 동일 사용량 환산 절감55.66%와도 범위가 다릅니다. 이번 새 추천 시험은 사실 조회와 추천 순위를 분리하여 웹 검색0회로 실제 비용을 비교했습니다.')
    add('')
    add('예를 들어 이미 `월요일 휴무`가 요일 칸으로 정리되어 있다면 날짜 비교는 코드가 합니다. 원문이 “월요일 휴무, 공휴일에는 영업하고 다음 날 쉼”이라면 먼저 예외 조건을 정확히 정리하는 작업이 필요합니다. 모델을 쓰더라도 근거 문장과 구조화된 사실을 추출한 뒤 최종 방문 가능 판정은 코드로 확인하는 편이 책임 경계가 명확합니다.')
    add('')
    add('확인한 원격 기준판: `role-activity` 662485c23aeae2a6016fb645f5c51da237c1d9f0, `role-activity-test` bbc750d4582cb8727798f808cf3c040b3060f102, `develop` 210b020067a1e42f2622262adeb60d1f3d371668. nano 실험은 시험 브랜치에서 확인했습니다. [저장 응답 재계산](../../../../scratch/activity-review-audit-20261008.json) · [검수 스크립트](../../../../scratch/activity-review-audit-20261008.py). 원격 이후 변경과 사람 정답 검수 기록은 이 확인 범위에 포함하지 않습니다.')
    add('')
    add('## 실제 서비스 연구에 적용할 구조')
    add('')
    add('[추천 흐름 그림](../../../../program/research/activity_recommendation_20261009/recommendation-flow.html)은 연구 제안입니다. 고객 분석 기능이 취향·기피·동행자 요구·중요도·원문 근거를 정리하고, 코어는 공통 계약으로 전달하며, Activity가 후보 회수와 분야별 점수를 적용합니다. 코어에 장소 분류와 취향 계산을 넣으면 도메인 독립 경계가 흐려집니다.')
    add('')
    add('모델에 맡길 부분은 “차분하게 앉아서 만들 수 있는 곳”과 후보의 경험을 연결하는 의미 판단입니다. 이동시간·가격·가중합 계산과 현재 사실 검증은 코드가 합니다. Jev API(유료) 등으로 의미 점수를 얻은 뒤 코드만으로 순위가 충분하면 Luna를 생략할 수 있습니다. 복합 취향 충돌·맥락·다양성에서 추가 효과가 검증된 요청만 재정렬합니다. 최종 고객 적용은 한 안을 고르되 대조용 상위3과 규칙·모델 제안은 기록에 보존할 수 있습니다.')
    add('')
    add('최신 근거 43개는 [연구 보고서](../../../../program/research/activity_recommendation_20261009/research.md), [논문·문서·기술 글 목록](../../../../program/research/activity_recommendation_20261009/source_catalog.md), [핵심 본문 대조](../../../../program/research/activity_recommendation_20261009/key_evidence_audit.md)에 있습니다. 논문17·공식문서15·직접기술글11이며 초록만 확인한 자료의 범위를 표시했습니다. 분야 전체를 망라한 전수 조사라고 주장하지 않습니다.')
    add('')
    add('- [COMPASS v2](https://arxiv.org/html/2510.07043v2): 방문 가능 집합과 효용 최적값을 구분합니다. 이번 고정 후보 시험은 재정렬을 보며 후보 검색의 누락은 따로 시험해야 합니다.')
    add('- [2026 순서 편향 연구](https://arxiv.org/html/2608.03091v1): 관련도와 일관성은 다른 축입니다. 동일 입력 변동과 순서만의 효과를 분리하는 후속 시험이 필요합니다.')
    add('- [TREK v2](https://arxiv.org/html/2607.26977v2): 정답 자체의 실행 가능성을 먼저 검증합니다. 정답 계획의 사람 검수가 고객 만족 검증을 대신하지 않습니다.')
    add('- [LinkedIn 검색](https://www.linkedin.com/blog/engineering/search/reimagining-linkedins-search-stack), [Spotify](https://research.atspotify.com/2026/8/from-models-to-products-llms-for-recommendation-at-spotify-scale), [Netflix GenRec](https://arxiv.org/html/2608.10257v2): 실제 후보 연결·학습과 검수·입력 압축·비용 제어를 함께 사용합니다. 전용 추천 모델의 개선을 범용 API 교체의 예상 이득으로 옮기지 않습니다.')
    add('')
    add('후속 검증은 고객 원문을 사람이 블라인드로 검수한 문제, 후보 검색 규모 16·64·256개, 해법 없음·동점·오래된 사실·여러 일정 연결을 포함해야 합니다. 고객 표현을 만드는 사람과 정답 판단하는 사람을 분리하고, 조정 자료와 최종 미사용 평가 자료를 나눕니다. 선별 보정도 조정 자료에서만 하며 미사용 자료로 다시 확인합니다. 최종 관문은 필수 조건 위반·설명 근거·최고 후보 보존·품질 차이·전체 비용·p95 지연입니다. 이 후속 시험은 이번에 실행한 것과 구분합니다.')
    add('')
    add('## 증거·재현·한계')
    add('')
    add('- [실제 응답·조건·사용량](../../../../datasets/travel/activity_recommendation_bench_20261009/runs/) · [집계 JSON](../../../../datasets/travel/activity_recommendation_bench_20261009/analysis/main-20261009-v1-final/summary.json) · [가상 자료 명세](../../../../datasets/travel/activity_recommendation_bench_20261009/raw/specification.md).')
    add('- [실행기·설정·사전 분석 계획](../../../../program/scripts/activity_recommendation_bench/README.md). 원문 답과 설정·자료·프롬프트 해시를 보존했습니다. 시험 완료 뒤 프롬프트나 정답을 수정하지 않았습니다.')
    add('- 정답 표기의 의미는 AI 작성·다른 에이전트 검수입니다. 사람 검수가 아니며 같은 설명 틀의 반복은 독립성을 낮춥니다. 후보 ID와 설명 구조의 반복도 일반화 한계입니다. 실제 고객 만족·추천 이유의 모든 사실·운영 코드 적용은 미검증입니다.')
    add('- 필수 조건 위반은 코드 선별 이후 제출 ID의 검증입니다. 모델 자체가 방문 가능성을 잘 판단했다는 증거가 아닙니다. 공지 조회나 웹 검색 품질도 이번 추천 시험에서 측정하지 않았습니다.')
    add('- 실행·분석 단위 시험 71/71 통과는 모델 응답 대역의 계약 검사입니다. mock 서버의 화면 시험은 하지 않았습니다. 실제 OpenAI API·TypeSafe API 호출 결과는 위의 호출 기록과 별도입니다.')
    add('- [실행기 수정 전 백업](../../../../program/scripts/activity_recommendation_bench/_backup/) · [연구 문서 백업](../../../../program/research/activity_recommendation_20261009/_backup/) · [평가 자료 초안 백업](../../../../datasets/travel/activity_recommendation_bench_20261009/raw/_backup/). 프롬프트 최초 초안은 덮어쓰기 직전 백업을 하지 못했습니다. 본 시험에 사용한 고정판과 해시·응답은 보존했습니다.')
    report = ROOT / 'final_project_cs/wiki/records/reports/2026-10-09_Activity_추천구조_모델비교_실측.md'
    fresh(report, '\n'.join(line)+'\n')
    dataset_report = f'''# 서울 활동 추천 비교 자료

자체 생성한 가상 자료로 추천 구조의 품질·비용·지연을 실제 API에서 비교했습니다. 사람 고객 만족의 정답표가 아닙니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 본 자료 | 검수 | 24/24 = 100% |
| 예비 자료 | 검수 | 2/2 = 100% |
| 본 비교 결과 | 기록 | {s['observed_rows']}/{s['scheduled_rows']} = 100% |

- 출처: 이번 작업의 AI 작성 문제·서술과 별도 에이전트 검수. 외부 고객 자료·쇼핑몰 자료·장소 소개글을 가져오지 않았습니다.
- 외부 라이선스 대상 자료를 재배포하는 데이터셋이 아닙니다. 평가 자료와 실제 응답은 `datasets/`의 로컬 보관·git 제외 규칙을 따릅니다.
- 원본: [raw/](raw/), 24개 본 문제·2개 예비, 문제당14후보, 본336후보. 각각 방문 조건 통과9개입니다. v1 초안도 보존하고 v2만 실행했습니다.
- 검수: [원문 명세](raw/specification.md), [작성기 검사](raw/validate_scenarios.py), [루트 독립 검수](root_fixture_review.json). AI 독립 검수는 사람 검수가 아닙니다.
- 실행: [실제 응답](runs/), [본 분석](analysis/main-20261009-v1-final/summary.json), [비용 기록](ledger.jsonl). 예비·본 비교·진단 총 비용 기록 ${total:.6f}, 상한 $0.50, 결제 명세서 값 아님.
- 최종 설명: [실측 보고서](../../../final_project_cs/wiki/records/reports/2026-10-09_Activity_추천구조_모델비교_실측.md), [문헌 연구](../../../program/research/activity_recommendation_20261009/research.md).
- 재현 코드: [실행기 안내](../../../program/scripts/activity_recommendation_bench/README.md). 원본 결과 덮어쓰기를 거부하며 새 실행도 기존 비용 기록의 상한을 공유합니다.
- 한계: 공유 설명 틀, 작은 가상 표본, 사람 정답 미검수. 후보 검색과 실제 고객 만족·운영 조회·배포 적용은 이번 실측 범위가 아닙니다.
'''
    fresh(DATA / 'REPORT.md', dataset_report)
    print(json.dumps({'report':str(report),'ledger_usd':total,'paid_calls':len(reserved)},ensure_ascii=True))


if __name__ == '__main__':
    run()
