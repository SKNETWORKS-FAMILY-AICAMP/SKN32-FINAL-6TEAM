"""차량 탐색의 조건을 유지한 시간 대조와 전체 준비 상태를 새 판에 보존한다."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v20'
OUT = ROOT / 'wiki/records/reports/assets/2026-10-09_mobility_readiness_v21'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    bench = proof['benchmark']
    catalog = deepcopy(json.loads((OLD / 'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = proof['created_at']
    catalog['turn_search_performance_validation'] = proof
    assert len(catalog['features']) == 21
    for row in catalog['features']:
        if row['name'] == '자동차 경로 거리':
            row['need'] += ' 회전 탐색의 요청 안 거리 재사용은 고정 개발 표본6쌍에서 결과를 보존하며 개선했습니다. 최초 적재·다양한 경로·실제 요청 지연은 남았습니다.'
    rows = ''.join('<tr>' + ''.join(f'<td>{escape(str(row[k]))}</td>' for k in
        ('name', 'status', 'scope', 'metric', 'reason', 'need')) + '</tr>' for row in catalog['features'])
    pairs = ''.join(f"<tr><td>{i+1}</td><td>{bench['rows'][i*2]['seconds']:.3f}</td>"
        f"<td>{bench['rows'][i*2+1]['seconds']:.3f}</td><td>일치</td></tr>" for i in range(bench['pairs']))
    marks = []
    for index, (variant, label) in enumerate([('baseline', '수정 전'), ('optimized', '수정 후')]):
        value = bench[variant]['mean']
        y = 80 + index * 88
        width = value / 5 * 640
        marks.append(f'<text x="32" y="{y+28}" font-size="20">{label}</text>'
            f'<rect x="240" y="{y}" width="{width:.3f}" height="40" fill="{"#a8720c" if index else "#6b7488"}"/>'
            f'<text x="{240+width+16:.3f}" y="{y+28}" font-size="20">{value:.3f}초</text>')
    ticks = ''.join(f'<line x1="{240+i*128}" y1="64" x2="{240+i*128}" y2="224" stroke="#dbe0ea"/>'
        f'<text x="{240+i*128}" y="248" font-size="16" text-anchor="middle">{i}</text>' for i in range(6))
    svg = f'''<svg viewBox="0 0 1024 320" role="img" aria-labelledby="turn-cache-title turn-cache-desc">
<title id="turn-cache-title">준비된 자료에서 택시 계획 계산 시간의 전후 평균</title>
<desc id="turn-cache-desc">북촌에서 석관동으로 가는 한 개발 입력을 전후 교대로 여섯 번씩 계산했습니다. 수정 전 평균 {bench['baseline']['mean']:.3f}초, 수정 후 {bench['optimized']['mean']:.3f}초입니다. 최초 적재와 실제 웹 요청 시간은 포함하지 않습니다.</desc>
<g fill="#161c28" font-family="Geist, Malgun Gothic, sans-serif">{ticks}{''.join(marks)}
<text x="32" y="288" font-size="16">가로축: 초 · 각6회 평균 · 전후 교대 · 실행 시각 두 항목을 제외한 결과12/12 일치</text></g></svg>'''
    ci = bench['paired_bootstrap_95_percent_ci']
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v21</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}
main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}
section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:1024px}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%}}.features{{min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}th{{background:#f1f4f8}}a{{color:#2f5bd8}}
@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>같은 위치의 목표 거리를 재사용해 차량 탐색의 반복 계산을 줄였습니다</h1>
<p>생성 시각 {escape(proof['created_at'])}. 회전 조건·경로 후보·속도 상수를 유지했습니다. 계산 값은 한 요청 안에서만 재사용합니다.</p>
<section><h2>첫 자료 적재와 반복 계획 계산을 구분합니다</h2>{svg}
<p>자료 준비 후 계획 계산6/6쌍. 평균 시간 감소 {bench['reduction_percent']:.1f}% · 쌍별 재표집95% 구간 {ci[0]:.1f}~{ci[1]:.1f}%. 한 경로의 개발 표본이며 서울 전체 성능이나 실제 HTTP 응답 보장이 아닙니다.</p>
<p>표준편차: 전 {bench['baseline']['stdev']:.3f}초 / 후 {bench['optimized']['stdev']:.3f}초. 모든 회차를 포함했습니다. 최초 런타임 구성 {bench['runtime_construction_seconds']:.3f}초, 수정 전 첫 계획 {bench['cold_baseline_plan_seconds']:.3f}초는 별도 단회 진단이며 수정 후 최초 적재와 비교한 수치가 아닙니다.</p>
<table><thead><tr><th>대조 쌍</th><th>수정 전(초)</th><th>수정 후(초)</th><th>경로·요금 결과</th></tr></thead><tbody>{pairs}</tbody></table>
<p>실행 시각인 decided_at와 captured_at 두 항목만 대조에서 제외했습니다. 전체 계획과 각 탐색의 좌표·유향 간선·비용·출발/도착 연결점을 대조했습니다. 시각 제외는 경로 출발·도착 예정 시각을 제외한다는 뜻이 아닙니다.</p>
<p>관련 회귀 {proof['tests']['passed']}/{proof['tests']['total']} · 독립 구현 합성 그래프 대조480/480(기존 시험2조건 안의 경로 쌍). 새 웹 경로 관측0건 · 실제 탑승/결제0건.</p>
<p><a href="../../{escape(proof['report'])}">보고서·원본 근거·백업</a> · <a href="../2026-10-09_mobility_readiness_v20/mobility-readiness.html">이전 v20</a></p></section>
<section><h2>21개 기능의 판단과 비교 수치</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 이번 성능 개선으로 준비 상태를 승격하지 않았습니다. 아래 기능별 수치는 이전 판의 관측 범위를 이어받습니다.</p>
<div class="table"><table class="features"><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>자료 최초 적재·실제 요청 시간·전체 환승 재계산·복잡한 회전 조건·혼합 운임·1.2km 정책 안 독립 웹 표본이 남았습니다.</p>
<p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(서버 응답): 안 했음 — 이번에는 로컬 이동 계산과 회귀 시험을 실행했습니다.</p>
<p>브라우저의 file: URL 정책 차단으로 실제 렌더를 확인하지 않았습니다. HTML·SVG·JSON·링크를 정적으로 검사합니다. 브랜드 폰트는 설치 상태에 따라 한국어 시스템 폰트로 대체됩니다.</p>
</main></body></html>'''
    OUT.mkdir(exist_ok=False)
    (OUT / 'readiness-catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf8')
    (OUT / 'mobility-readiness.html').write_text(html, encoding='utf8')
    print(json.dumps(dict(features=21, counts=catalog['counts']), ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
