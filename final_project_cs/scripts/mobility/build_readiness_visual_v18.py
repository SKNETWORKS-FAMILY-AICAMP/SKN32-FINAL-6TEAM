"""안내 저장과 재탐색 적용의 순서 검증을 새 판으로 보존한다."""
from collections import Counter
from copy import deepcopy
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v17'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v18'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = proof['created_at']
    catalog['departure_atomicity'] = proof
    for row in catalog['features']:
        if row['name'] in ('실시간 지하철·버스 도착', '도보 소요·역 접근 시간'):
            row['need'] = row['need'].replace('안내 발행 경합 검증', '실제 발송·현재 위치 검증')
            row['need'] += ' 안내 저장/출발 재탐색 적용의 두 순서와 동시 연결 잠금을 로컬 DB에서 검증했습니다. 현재 동행 조건 대조와 실제 탑승은 남았습니다.'
    counts = Counter(row['status'] for row in catalog['features'])
    assert len(catalog['features']) == 21 and dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    (OUT/'readiness-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
    cells = [(48,104,'출발 안내 저장','같은 여행의 현재 판을 잠금',True),
        (528,104,'새 일정 저장','같은 여행의 현재 판을 잠금',True),
        (48,224,'출발 재탐색 적용 대기','잠금이 풀린 뒤 안내 행 재확인',False),
        (528,224,'이전 출발 안내 저장 대기','잠금이 풀린 뒤 최신 판 재확인',False),
        (48,344,'출발 재탐색 적용 거절','안내가 이미 있으면 새 판을 쓰지 않음',False),
        (528,344,'낡은 출발 안내 저장 거절','새 판의 경로는 다음 반복에서 재계산',False)]
    boxes = ''.join(f'<rect x="{x}" y="{y}" width="400" height="72" rx="8" fill="{"#f1f4f8" if focal else "#ffffff"}" stroke="{"#a8720c" if focal else "#6b7488"}"/>'
        f'<text x="{x+200}" y="{y+28}" text-anchor="middle" font-size="20" font-weight="600">{escape(title)}</text>'
        f'<text x="{x+200}" y="{y+56}" text-anchor="middle" font-size="15">{escape(state)}</text>'
        for x,y,title,state,focal in cells)
    arrows = ''.join(f'<path d="M{x} {y} V{y+48}" fill="none" stroke="#6b7488" marker-end="url(#atomic-arrow)"/>'
        for x in (248,728) for y in (176,296))
    svg = f'''<svg viewBox="0 0 976 520" role="img" aria-labelledby="atomic-title atomic-desc">
<title id="atomic-title">안내 저장과 새 일정 저장의 두 순서</title>
<desc id="atomic-desc">안내가 먼저 저장되면 자동 출발 재탐색 적용을 거절합니다. 새 일정이 먼저 저장되면 이전 판 출발 문구를 거절하고 다음 반복에서 현재 경로를 다시 계산합니다.</desc>
<defs><marker id="atomic-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#6b7488"/></marker></defs>
<rect width="976" height="520" fill="#fbfcfd"/><g font-family="Geist, Noto Sans KR, Malgun Gothic, sans-serif" fill="#161c28">
<text x="248" y="56" font-size="24" text-anchor="middle">안내가 먼저 저장될 때</text>
<text x="728" y="56" font-size="24" text-anchor="middle">새 일정이 먼저 저장될 때</text>
{arrows}{boxes}<line x1="48" y1="456" x2="928" y2="456" stroke="#dbe0ea"/>
<text x="48" y="488" font-size="16">DB 저장 순서를 검증했습니다. 실제 발송·고객 출발·탑승을 확인한 것은 아닙니다.</text></g></svg>'''
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[k]))}</td>' for k in
        ('name','status','scope','metric','reason','need'))+'</tr>' for row in catalog['features'])
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v18</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}
main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}
section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:976px}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}th{{background:#f1f4f8}}a{{color:#2f5bd8}}
@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>일정이 바뀌는 동안 이전 출발 안내가 저장되는 문제를 막았습니다</h1>
<p>생성 시각 {escape(proof['created_at'])}. 확대 시험 {proof['regression']['passed']}/{proof['regression']['total']} · 포함 관련 시험 {proof['related_passed']}/{proof['related_total']}.</p>
<section><h2>먼저 저장된 결과를 확인하고 다음 작업을 결정합니다</h2>
<p>출발 안내 저장과 자동 출발 재탐색 적용을 같은 여행에서 순서대로 처리합니다. 낡은 안내는 이미 보낸 안내와 구별해 기록합니다. 고객이 직접 선택한 변경은 기존 계약을 따릅니다.</p>
{svg}<p>로컬 개발 DB 제어 조건 7/7: 두 저장 순서4조건·현재 항목 누락1조건·실제 동시 연결2조건. 두 연결의 잠금 대기를 DB에서 관측했습니다. 자연 발생 빈도는 측정하지 않았습니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·검증 로그·백업</a> · <a href="../2026-10-09_mobility_readiness_v17/mobility-readiness.html">이전 v17</a></p></section>
<section><h2>21개 기능별 비교 수치와 남은 조건</h2><p>조건부 사용 4/21 · 개선 필요 9/21 · 추가 검증 8/21. 기능의 제품 준비율은 아직 판정하지 않았습니다.</p>
<div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>현재 인원·접근 조건 대조, 실제 위치/탑승, 독립 웹 경로 오차, 혼합 운임, 복잡한 회전 제약은 남았습니다. 이번 신규 웹 경로 관측과 실제 이동·결제 측정은 0건입니다.</p>
<p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(로컬 개발 DB 연동): 했음. 배포된 cs 프로젝트 서버 응답: 안 했음.</p>
<p>브라우저의 file: URL 정책 차단으로 화면 렌더 확인은 수행하지 못했습니다. 구조·링크·SVG 접근성 속성만 정적으로 확인했습니다.</p>
</main></body></html>'''
    (OUT/'mobility-readiness.html').write_text(html,encoding='utf8')
    print(json.dumps(dict(features=21,counts=dict(counts)),ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
