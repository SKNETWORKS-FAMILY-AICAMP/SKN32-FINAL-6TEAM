"""출발 안내 계산과 저장 사이 입력 대조의 검증을 새 판으로 보존한다."""
from collections import Counter
from copy import deepcopy
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v19'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v20'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = proof['created_at']
    catalog['departure_input_race_validation'] = proof
    current_need = {
        '실시간 지하철·버스 도착': '버스 첫 탑승의 현재 도착 관측, 옛 문맥 재경로, 안내 보류의 사건 처리·새 일정·재안내, 일정 판 저장 경합과 지원 인원·휴식·첫 방문 대조를 통제 시험에서 확인했습니다. 실제 차량 도착 오차·모든 환승 재계산·지하철 실시간 연결·현재 위치/탑승 입력·선호 수단 변경·지원 밖 접근성·새 독립 웹 검증이 남았습니다.',
        '도보 소요·역 접근 시간': '직접 도보의 현재 보행망·계단 시간, 옛 문맥 재경로, 안내 보류의 사건 처리·새 일정·재안내, 일정 판 저장 경합과 지원 인원·휴식·첫 방문 대조를 통제 시험에서 확인했습니다. 1.2km 정책 안의 출입구·시각·추천 경로가 맞는 웹 표본, 보행망/횡단/고도 품질, 실제 보행 오차·현재 위치/탑승 입력·선호 수단 변경·지원 밖 접근성이 남았습니다. 장거리 원시 진단은 제품 제공률로 쓰지 않습니다.',
    }
    for row in catalog['features']:
        if row['name'] in current_need:
            row['need'] = current_need[row['name']] + ' 계산~저장 사이 여행 입력 변경과 두 연결의 저장 순서를 검증했습니다. 운영 조건 변경 API·안내 배달 뒤 조건 변경 대응은 별도 남은 범위입니다.'
    counts = Counter(row['status'] for row in catalog['features'])
    assert len(catalog['features']) == 21 and dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    (OUT/'readiness-catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf8')
    cells = [(48,104,'계산 당시 여행 입력','인원·조건으로 안내를 계산함',True),
        (528,104,'계산 입력 사본 보존','중첩 조건도 별도 사본으로 저장',True),
        (48,224,'일정 판·이동 항목만 대조','인원·조건만 바뀌면 판은 유지됨',False),
        (528,224,'같은 여행 행 잠금 아래 대조','현재 입력과 사본이 다르면 보류',False),
        (48,344,'변경 전 안내 저장 가능','인원·조건의 변경 시점을 놓침',False),
        (528,344,'최신 조건의 다음 안내 계산','조건 사본은 안내 내용에 넣지 않음',False)]
    boxes = ''.join(f'<rect x="{x}" y="{y}" width="400" height="72" rx="8" fill="{"#f1f4f8" if focal else "#ffffff"}" stroke="{"#a8720c" if focal else "#6b7488"}"/>'
        f'<text x="{x+200}" y="{y+28}" text-anchor="middle" font-size="20" font-weight="600">{escape(title)}</text>'
        f'<text x="{x+200}" y="{y+56}" text-anchor="middle" font-size="15">{escape(state)}</text>'
        for x,y,title,state,focal in cells)
    arrows = ''.join(f'<path d="M{x} {y} V{y+48}" fill="none" stroke="#6b7488" marker-end="url(#party-arrow)"/>'
        for x in (248,728) for y in (176,296))
    svg = f'''<svg viewBox="0 0 976 520" role="img" aria-labelledby="party-title party-desc">
<title id="party-title">출발 안내 저장 직전에 계산 입력과 현재 입력을 대조</title>
<desc id="party-desc">수정 전은 일정 판만 대조했습니다. 수정 후는 같은 여행 행 잠금 아래 현재 인원과 조건도 대조하고 다르면 저장을 보류합니다.</desc>
<defs><marker id="party-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#6b7488"/></marker></defs>
<rect width="976" height="520" fill="#fbfcfd"/><g font-family="Geist, Noto Sans KR, Malgun Gothic, sans-serif" fill="#161c28">
<text x="248" y="56" font-size="24" text-anchor="middle">수정 전</text><text x="728" y="56" font-size="24" text-anchor="middle">수정 후</text>
{arrows}{boxes}<line x1="48" y1="456" x2="928" y2="456" stroke="#dbe0ea"/>
<text x="48" y="488" font-size="16">저장 순간의 입력 일치를 검증합니다. 배달 뒤 조건 변경·실제 위치·탑승 검증은 아닙니다.</text></g></svg>'''
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[k]))}</td>' for k in
        ('name','status','scope','metric','reason','need'))+'</tr>' for row in catalog['features'])
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>서울 이동 검증 v20</title><style>
body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}
main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}
section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:976px}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}th{{background:#f1f4f8}}a{{color:#2f5bd8}}
@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head><body><main>
<h1>출발 안내를 계산하는 사이 조건이 바뀌면 이전 안내를 저장하지 않습니다</h1>
<p>생성 시각 {escape(proof['created_at'])}. 확대 {proof['regression']['passed']}/{proof['regression']['total']} · 포함 관련 {proof['related_passed']}/{proof['related_total']} · 신규 로컬 개발 DB 8/8.</p>
<section><h2>계산 입력을 보존하고 저장 직전에 다시 검사합니다</h2>
<p>운영 안내는 읽은 인원·전체 조건의 사본을 보존합니다. 안내 저장은 같은 여행 행 잠금 아래 현재 입력을 다시 읽고 사본과 다르면 낡은 안내로 보류합니다. 다른 종류 안내는 기존 계약을 유지합니다.</p>
{svg}<p>DB8/8은 계산 뒤 인원/조건 변경2조건, 사본 분리·JSON 키 순서2조건, 실제 두 연결 잠금 대기2조건, 다른 안내 호환1조건, 논리값/숫자 구분1조건입니다. 설정 API·실운행 정확도 시험이 아닙니다. 예산 같은 무관한 조건 변경도 한 번 저장을 보류할 수 있습니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·근거·백업</a> · <a href="../2026-10-09_mobility_readiness_v19/mobility-readiness.html">이전 v19</a></p></section>
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
