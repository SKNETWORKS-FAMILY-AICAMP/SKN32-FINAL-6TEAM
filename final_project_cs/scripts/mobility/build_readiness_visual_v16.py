"""출발 재검증의 사건 조회 우회 수정과 기존 21개 판단을 새 판으로 보존한다."""
from collections import Counter
from copy import deepcopy
from datetime import datetime
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v15'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v16'


def main(proof_path):
    proof = json.loads(Path(proof_path).read_text(encoding='utf8'))
    catalog = deepcopy(json.loads((OLD/'readiness-catalog.json').read_text(encoding='utf8')))
    catalog['created_at'] = datetime.now().astimezone().isoformat()
    catalog['departure_source_gate'] = proof
    for row in catalog['features']:
        if row['name'] in ('실시간 지하철·버스 도착', '도보 소요·역 접근 시간'):
            row['need'] += ' 사건 대상 없는 이동은 사건 조회와 분리해 현재 모델을 재검증한다. DB 도보 2조건 확인; 지각 Case 전달과 실제 보행 오차는 남음.'
    counts = Counter(row['status'] for row in catalog['features'])
    assert len(catalog['features']) == 21 and dict(counts) == catalog['counts']
    OUT.mkdir(exist_ok=False)
    with (OUT/'readiness-catalog.json').open('x', encoding='utf8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    # 워크스페이스 .diagram-design의 acop 프로필: 외부 글꼴이 안 되면 로컬 한글 글꼴 사용.
    cells = [
        (48, 112, '사건 소스 없음', '조기 반환', True),
        (528, 112, '선택 경로의 사건 대상 없음', '불필요한 조회 생략', True),
        (48, 232, '현재 이동 모델', '실행되지 않음', False),
        (528, 232, '현재 이동 모델', '현재 장소·시각으로 재검증', False),
        (48, 352, '출발 안내', '저장된 출발·도착 시각', False),
        (528, 352, '출발 안내', '새 시간 안내 / 단절이면 보류', False),
    ]
    boxes = ''.join(f'<rect x="{x}" y="{y}" width="400" height="72" rx="8" '
        f'fill="{"#f1f4f8" if focal else "#ffffff"}" stroke="{"#a8720c" if focal else "#6b7488"}"/>'
        f'<text x="{x+200}" y="{y+28}" text-anchor="middle" font-size="20" font-weight="600">{escape(title)}</text>'
        f'<text x="{x+200}" y="{y+56}" text-anchor="middle" font-size="16">{escape(state)}</text>'
        for x, y, title, state, focal in cells)
    arrows = ''.join(f'<path d="M{x} {y} V{y+48}" fill="none" stroke="#6b7488" marker-end="url(#gate-arrow)"/>'
        for x in (248, 728) for y in (184, 304))
    svg = f'''<svg viewBox="0 0 976 536" role="img" aria-labelledby="gate-title gate-desc">
<title id="gate-title">사건 소스 누락이 도보 재검증을 막던 우회 수정</title>
<desc id="gate-desc">사건 소스가 없던 도보의 수정 전 저장 시각 안내와 수정 후 현재 모델 재검증 및 단절 보류를 비교합니다.</desc>
<defs><marker id="gate-arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#6b7488"/></marker>
<marker id="gate-arrow-accent" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#a8720c"/></marker>
<marker id="gate-arrow-link" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#2f5bd8"/></marker></defs>
<rect width="976" height="536" fill="#fbfcfd"/>
<g font-family="Geist, Noto Sans KR, Malgun Gothic, sans-serif" fill="#161c28">
<text x="248" y="64" font-size="24" text-anchor="middle">수정 전</text>
<text x="728" y="64" font-size="24" text-anchor="middle">수정 후</text>
{arrows}{boxes}
<line x1="48" y1="464" x2="928" y2="464" stroke="#dbe0ea"/>
<text x="48" y="492" font-size="16">첫 차이: 사건 소스 유무가 현재 이동 모델 실행을 막는가</text>
<text x="48" y="520" font-size="16">모델 재검증은 실제 보행·탑승 관측이 아닙니다.</text></g></svg>'''
    rows = ''.join('<tr>'+''.join(f'<td>{escape(str(row[key]))}</td>' for key in
        ('name', 'status', 'scope', 'metric', 'reason', 'need'))+'</tr>' for row in catalog['features'])
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>서울 이동 검증 v16</title>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&amp;family=Geist:wght@400;600&amp;family=Noto+Sans+KR:wght@400;600&amp;family=Noto+Serif+KR:wght@400&amp;display=swap" rel="stylesheet">
<style>body{{margin:0;background:#fbfcfd;color:#161c28;font:16px/1.65 Geist,'Noto Sans KR','Malgun Gothic',sans-serif}}
main{{max-width:1320px;margin:auto;padding:32px}}h1{{font:32px/1.3 'Instrument Serif','Noto Serif KR',serif}}h2{{font-size:24px}}
section{{margin:24px 0;padding:24px;border:1px solid #dbe0ea}}svg{{width:100%;height:auto;max-width:976px}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:940px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid #dbe0ea;vertical-align:top}}
th{{background:#f1f4f8}}a{{color:#2f5bd8}}@media(max-width:600px){{main{{padding:12px}}section{{padding:16px}}}}</style></head>
<body><main><h1>도보 재계산을 사건 소스와 분리하고, 예전 안내로 우회하던 경로를 막았습니다</h1>
<p>확대 시험 {proof['regression']['passed']}/{proof['regression']['total']} · 포함 관련 시험 {proof['related_passed']}/{proof['related_total']} · 로컬 개발 DB 도보 2/2.</p>
<section><h2>무엇이 달라졌나</h2><p>현재 관측 기능이 켜져 있고 확인할 사건 대상이 없는 이동은 불필요한 사건 조회 없이 현재 장소·시간으로 다시 계산합니다.
도보 단절은 보류하며, 노선 확인이 필요한 이동의 사건 소스가 빠지면 예전 문구를 발행하지 않습니다. 경로 정의가 빠진 이동도 보류합니다.</p>
{svg}<p>그림: 비교 추적 흐름도, 문서 폭 976×536, acop 프로필. 현재 관측 기능이 등록된 경로만 비교했습니다. 노선 소스 실패와 경로 정의 누락의 상세 조건은 보고서에 있습니다.
외부 글꼴이 로드되지 않으면 로컬 한글 글꼴을 사용합니다.</p>
<p><a href="../../{escape(proof['report'])}">보고서·실행 로그·백업</a> · <a href="../2026-10-09_mobility_readiness_v15/mobility-readiness.html">이전 v15</a></p></section>
<section><h2>21개 기능의 판단과 남은 검증</h2><p>조건부 사용 4/21 · 개선 필요 9/21 · 추가 검증 8/21. 기능 수는 제품 준비율이 아닙니다.</p>
<div class="table"><table><thead><tr><th>기능</th><th>판단</th><th>확인 범위</th><th>비교 수치</th><th>근거</th><th>남은 일</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<p>모델 재검증과 실제 이동시간 정확도는 별개입니다. 이번 새 지도 웹 경로 관측·실제 보행/탑승/결제 측정은 없습니다.
지각 Case 전달·옛 문맥 재경로·탑승 중 갱신·합법 차량 진입·복잡한 회전·혼합 운임은 남았습니다. 전체 21개 기능 완료는 아닙니다.</p>
<p>mock 서버 시험(화면 반응): 안 했음. 실서버 확인(로컬 개발 DB 연동): 했음. 배포된 cs 프로젝트 서버 응답: 안 했음.</p></main></body></html>'''
    with (OUT/'mobility-readiness.html').open('x', encoding='utf8') as f:
        f.write(html)
    print(json.dumps(dict(features=len(catalog['features']), counts=dict(counts)), ensure_ascii=True))


if __name__ == '__main__':
    import sys
    main(sys.argv[1])
