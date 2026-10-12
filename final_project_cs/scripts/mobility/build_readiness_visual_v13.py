"""차량 회전 조건 적용 근거를 새 시각화에 보존한다. 기존 판은 덮지 않는다."""
from collections import Counter
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v12'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v13'


def main(proof_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    probe = proof['pinned_probe']
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = datetime.now().astimezone().isoformat()
    catalog['car_turns'] = proof
    for index in (2, 3):
        catalog['features'][index]['need'] += (
            ' 정적 단순 회전 2,487관계의 탐색 연결을 확인했다. 복잡한 유턴·시간/차종 예외·'
            '회전 적용 후 도로 연결·출입점·새 웹 오차 검증은 남음.')
    counts = Counter(row['status'] for row in catalog['features'])
    assert len(catalog['features']) == 21 and dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    with (OUT/'readiness-catalog.json').open('x', encoding='utf8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    plt.rcParams['font.family'] = 'Malgun Gothic'
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(11, 7))
    for index, row in enumerate(probe['observations']):
        pair = row['repeats'][0]
        before = pair['before']['distance_m']
        after = pair['after'].get('distance_m')
        ax.scatter(before, index, color='#8b9299', marker='x', s=55,
                   label='수정 전: 금지 회전 사용' if index == 0 else None)
        if after is not None:
            ax.plot([before, after], [index, index], color='#9cb6c5', linewidth=1.5)
            ax.scatter(after, index, color='#12678e', s=45,
                       label='수정 후: 적용 관계 준수' if index == 0 else None)
        else:
            ax.annotate('수정 후 경로 미확보', (before, index), xytext=(14, -4),
                        textcoords='offset points', color='#a73932')
    ax.set_yticks(range(probe['queries']), [f'검사 {n+1}' for n in range(probe['queries'])])
    ax.invert_yaxis()
    ax.set_xscale('log')
    ax.set_xlabel('모델 경로 거리(m, 로그 눈금) — 실제 주행 거리 측정 아님')
    ax.set_title('진입·진출 도로 고정: 금지 회전 경로 12개 중 우회 11개, 미확보 1개', pad=18)
    ax.grid(axis='x', alpha=.2)
    ax.legend(loc='upper left')
    fig.text(.02, .015, '개발 검사 · 각 조건 3회 교대 · 새 웹 정확도/독립 검증 아님 · 미확보를 0m로 표시하지 않음', fontsize=10)
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(OUT/'car-turn-distances.png', dpi=160)
    plt.close(fig)
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[key]))}</td>'
        for key in ('name', 'status', 'scope', 'metric', 'reason', 'need'))+'</tr>'
        for row in catalog['features'])
    status = ' · '.join(f'{name} {count}/21' for name, count in counts.items())
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>서울 이동 검증 v13</title>
<style>body{{font:16px/1.65 system-ui,sans-serif;margin:0;background:#f5f6f8;color:#19242e}}
main{{max-width:1320px;margin:auto;padding:28px}}section{{background:white;border:1px solid #d7dce1;padding:24px;margin:20px 0}}
h1{{font-size:30px}}h2{{font-size:23px}}.flow{{display:flex;gap:12px;flex-wrap:wrap}}
.flow span{{padding:12px;border:1px solid #b5c6cf;background:#eef4f7}}img{{max-width:100%;height:auto}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}
th,td{{text-align:left;padding:12px;border-bottom:1px solid #d7dce1;vertical-align:top}}th{{background:#edf1f3}}
a{{color:#065b88}}@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>금지 회전을 경로 탐색에서 검사하도록 바꿨습니다</h1>
<p>확대 회귀 {proof['regression_passed']}/{proof['regression_total']} 통과. 전체 21개 기능은 계속 검증 중입니다.</p>
<section><h2>이번 변경과 적용 범위</h2><div class="flow"><span>진입 도로까지 구분</span>
<span>→ 회전 허용·금지 확인</span><span>→ 허용 연결로 경로 탐색</span><span>→ 부분 출발·도착까지 확인</span></div>
<p>자료의 그래프 관련 6,258관계 중 명확한 정적 단순 2,487관계(39.7%)를 연결했습니다.
이 비율은 서울 도로 법규 완전성이나 정확도가 아닙니다. 모호한 단순 후보 6개와 복잡한 관계는 적용하지 않았습니다.</p>
<p>일반 스냅 개발 검사 12/12에서 적용 관계 위반은 없었지만 수정 전후 거리가 바뀐 것은 0/12입니다.
진입·진출 도로를 고정한 별도 개발 검사에서는 기존 12/12가 금지 회전을 썼고, 수정 후 11/12가 우회했습니다.
나머지 1/12는 경로 미확보입니다. 탐색 방식 대조는 12/12 일치했습니다.</p>
<img src="car-turn-distances.png" alt="금지 회전 검사별 수정 전후 모델 경로 거리. 11개 우회, 1개 경로 미확보">
<p>미확보 사례는 현재 그래프의 출구 1개가 금지되어 발생합니다. 독립 도달성 검사도 진입 상태 1개만 도달하고 목표 진입은 0개였습니다.
현실의 도로가 막혀 있다는 판정은 아니며 원자료·연결 조사와 대체 경로 확보가 남았습니다.</p>
<p>그래프와 회전 파일 해시를 결합하고 파일 손상·적재 후 삭제는 명시적 오류로 처리합니다.
처음부터 자료가 없는 환경은 미가용 표시가 남으므로 배포 자료 동봉 여부도 별도 확인해야 합니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·검증 원문·백업</a> ·
<a href="../2026-10-09_mobility_readiness_v12/mobility-readiness.html">이전 판</a></p></section>
<section><h2>21개 기능의 판단과 남은 근거</h2><p>{escape(status)}</p>
<p>기존 판단을 승격하지 않았습니다. 아래 비교 수치는 과거 개발 표본이며 이번 변경으로 다시 측정한 값이 아닙니다.
각 기능의 제품 경로·대체 소스·허용 오차·새 표본을 확인하기 전에는 전체 완료를 선언하지 않습니다.</p>
<div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>
<p>mock 서버 시험: 이번 단계에서 사용하지 않았습니다. 실제 로컬 그래프 계산을 검사했습니다.
실서버 확인(배포된 cs 프로젝트 서버 응답): 안 했음. 실제 탑승·결제 측정: 안 했음. 지도 개발자 API 직접 호출 0회.</p>
</main></body></html>'''
    with (OUT/'mobility-readiness.html').open('x', encoding='utf8') as f:
        f.write(html)
    print(json.dumps(dict(features=len(catalog['features']), counts=dict(counts)), ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
