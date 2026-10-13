"""현재 동행 조건 대조의 검증과 기존 21개 기능 수치를 새 판으로 보존한다."""
from collections import Counter
from copy import deepcopy
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v18'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v19'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = proof['created_at']
    catalog['current_party_validation'] = proof
    current_need = {
        '실시간 지하철·버스 도착': '버스 첫 탑승의 현재 도착 관측, 옛 문맥 재경로, 안내 보류의 사건 처리·새 일정·재안내, 일정 판 저장 경합과 지원 인원·휴식·첫 방문 대조를 통제 시험에서 확인했습니다. 실제 차량 도착 오차·모든 환승 재계산·지하철 실시간 연결·현재 위치/탑승 입력·조건 쓰기 시점 경합·선호 수단 변경·지원 밖 접근성·새 독립 웹 검증이 남았습니다.',
        '도보 소요·역 접근 시간': '직접 도보의 현재 보행망·계단 시간, 옛 문맥 재경로, 안내 보류의 사건 처리·새 일정·재안내, 일정 판 저장 경합과 지원 인원·휴식·첫 방문 대조를 통제 시험에서 확인했습니다. 1.2km 정책 안의 출입구·시각·추천 경로가 맞는 웹 표본, 보행망/횡단/고도 품질, 실제 보행 오차·현재 위치/탑승 입력·조건 쓰기 시점 경합·선호 수단 변경·지원 밖 접근성이 남았습니다. 장거리 원시 진단은 제품 제공률로 쓰지 않습니다.',
    }
    for row in catalog['features']:
        if row['name'] in current_need:
            row['need'] = current_need[row['name']]
    counts = Counter(row['status'] for row in catalog['features'])
    assert len(catalog['features']) == 21 and dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    (OUT/'readiness-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
    cells = [(48,104,'저장 당시 조건만 사용','현재 인원·휴식 조건을 받지 않음',True),
        (528,104,'현재 여행 조건도 전달','생성과 같은 규칙으로 조건 정규화',True),
        (48,224,'저장 조건으로 재검증','장소·시간표가 맞으면 예전 조건 유지',False),
        (528,224,'현재 조건과 저장 조건 대조','변경이면 안내 보류·새 경로 요청',False),
        (48,344,'이전 조건의 안내 저장','변경된 인원·휴식 필요를 놓침',False),
        (528,344,'새 조건의 경로·문맥·안내','무관한 예산 변경은 재탐색하지 않음',False)]
    boxes = ''.join(f'<rect x="{x}" y="{y}" width="400" height="72" rx="8" fill="{"#f1f4f8" if focal else "#ffffff"}" stroke="{"#a8720c" if focal else "#6b7488"}"/>'
        f'<text x="{x+200}" y="{y+28}" text-anchor="middle" font-size="20" font-weight="600">{escape(title)}</text>'
        f'<text x="{x+200}" y="{y+56}" text-anchor="middle" font-size="15">{escape(state)}</text>'
        for x,y,title,state,focal in cells)
    arrows = ''.join(f'<path d="M{x} {y} V{y+48}" fill="none" stroke="#6b7488" marker-end="url(#party-arrow)"/>'
        for x in (248,728) for y in (176,296))
    svg = f'''<svg viewBox="0 0 976 520" role="img" aria-labelledby="party-title party-desc">
<title id="party-title">현재 여행 조건을 출발 재검증에 전달하는 변경</title>
<desc id="party-desc">수정 전은 저장 당시 조건만으로 안내했습니다. 수정 후는 현재 여행 조건을 대조해 변경이면 안내 보류와 새 경로 계산으로 연결합니다.</desc>
<defs><marker id="party-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#6b7488"/></marker></defs>
<rect width="976" height="520" fill="#fbfcfd"/><g font-family="Geist, Noto Sans KR, Malgun Gothic, sans-serif" fill="#161c28">
<text x="248" y="56" font-size="24" text-anchor="middle">수정 전</text><text x="728" y="56" font-size="24" text-anchor="middle">수정 후</text>
{arrows}{boxes}<line x1="48" y1="456" x2="928" y2="456" stroke="#dbe0ea"/>
<text x="48" y="488" font-size="16">현재 인원·휴식·첫 방문 입력을 대조합니다. 실제 위치·탑승·접근성 측정은 아닙니다.</text></g></svg>'''
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[k]))}</td>' for k in
        ('name','status','scope','metric','reason','need'))+'</tr>' for row in catalog['features'])
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v19</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}
main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}
section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:976px}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}th{{background:#f1f4f8}}a{{color:#2f5bd8}}
@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>여행 인원이나 휴식 조건이 바뀌면 새 조건으로 경로를 다시 계산합니다</h1>
<p>생성 시각 {escape(proof['created_at'])}. 확대 {proof['regression']['passed']}/{proof['regression']['total']} · 포함 관련 {proof['related_passed']}/{proof['related_total']} · 신규 로컬 개발 DB 2/2.</p>
<section><h2>저장 문맥과 최신 여행 정보를 함께 검사합니다</h2>
<p>버스·도보 재검증은 현재 인원과 생성 때 사용하는 휴식 조건·첫 방문 여부를 대조합니다. 변경이면 현재 버스 도착 조회 전에 안내를 보류합니다. 최신 조건의 새 경로와 문맥을 저장한 뒤 다시 안내합니다.</p>
{svg}<p>단위 시험15/15에는 정상·인원·휴식·첫 방문·무관한 예산 조건, 잘못된 입력과 호환 호출이 있습니다. DB2/2는 인원/휴식 변경을 각각10회 반복해 Case1·적용1·새 출발 안내1을 확인한 통제 시험입니다. 실운행 오차 자료가 아닙니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·근거·백업</a> · <a href="../2026-10-09_mobility_readiness_v18/mobility-readiness.html">이전 v18</a></p></section>
<section><h2>21개 기능의 판단과 비교 수치</h2><p>조건부 사용4/21 · 개선 필요9/21 · 추가 검증8/21. 이번에는 준비 상태를 승격하지 않았습니다.</p>
<div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>실제 위치/탑승·선호 수단 변경·지원하지 않는 접근성 입력·혼합 운임·복잡한 회전·독립 웹 오차 검증은 남았습니다. 새 웹 경로 관측0건, 실제 이동/결제 측정0건입니다.</p>
<p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(로컬 개발 DB): 했음. 배포된 cs 프로젝트 서버 응답: 안 했음.</p>
<p>브라우저의 file: URL 정책 차단으로 실제 렌더를 확인하지 않았습니다. HTML·SVG·JSON·링크를 정적으로 검사했습니다.</p>
</main></body></html>'''
    (OUT/'mobility-readiness.html').write_text(html,encoding='utf8')
    print(json.dumps(dict(features=21,counts=dict(counts)),ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
