"""보존된 v3 목록을 최신 재검산과 웹 진단 근거로 갱신한 새 산출물."""
from __future__ import annotations
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT/'wiki/records/reports/assets/2026-10-08_mobility_readiness_v3'
OUT = ROOT/'wiki/records/reports/assets/2026-10-09_mobility_readiness_v7'
DEV = ROOT/'wiki/records/reports/assets/2026-10-08_mobility_development_v6/development-summary.json'
WEB = ROOT.parent/'datasets/mobility/raw/kakao_golden/additional_web_2026-10-08_v1'

def load(p):
    return json.loads(p.read_text(encoding='utf8'))

def main():
    d = load(DEV)
    rows = load(OLD/'readiness-catalog.json')['features']
    bus, rail = d['bus_after'], d['rail_after']
    same = d['rail_change']['same_route']
    time = bus['time_without_wait']['absolute']
    rows[6].update(metric=f"버스만인 후보 {d['bus_before']['comparable']}/100 → {bus['comparable']}/100. 대기 제외 ±5분 {time['within']}/{time['n']}; 평균 절대 차이 {time['mae']:.2f}분.",
                   reason='노선 후보 개수 제한·운행 방향·요일·시간대를 수정했다. 각 환승 승차 시각에 운행 여부를 확인한다.',
                   need='2회 이상 환승·첫차와 막차·다른 날짜의 독립 표본 및 실제 탑승 검증.')
    rows[7].update(metric=f"같은 {same['n']}경로 요금 {same['before_present']} → {same['after_present']}. 현재 {rail['fare_present']}/{rail['comparable']} 안내, 그중 상단 {rail['fare_upper']}건. 웹 금액 범위 일치 {rail['fare_in_web_range']}/{rail['fare_present']}.",
                   reason='공식 역간 거리와 신분당선 구간별 별도 운임을 확보했다. OSM 거리·공표 거리의 방향 대응 추정·확정 거리를 구분한다.',
                   need='거리 경계의 정확 요금·자료 충돌 두 구간 및 별도 노선 요금의 추가 검증. 상단은 정확 요금으로 세지 않기.')
    rows[8].update(metric=f"요금 안내 {bus['fare_present']}/{bus['comparable']}; 할인 전 상한 {bus['fare_upper']}건. 웹 범위 일치 {bus['fare_in_web_range']}/{bus['fare_present']}; 상한이 웹 최대 이상 {bus['fare_upper_covers_web_max']}/{bus['fare_upper']}.",
                   reason='단일 탑승 요금 합의 상한이다. 통합거리 환승 할인을 계산하는 제품 경로는 추가 구현이 필요하다.')
    rows[10].update(metric='기존 30쌍은 직선 1,617~3,897m로 제품 1,200m 상한 밖: 공개 제공 0/30, 정책 제외 30/30. 제품 ETA 오차 분모 0. 원시 진단 ±5분 15/30→15/30; MAE 7.038→6.782분.',
                    reason='계단 시간이 일정과 기록 경로 재사용에 전달되도록 수정했다. 관련 회귀 55/55 통과. 원시 MAE 차이의 쌍별 bootstrap95% 구간 −0.727~+0.086분으로 정확도 개선은 확정할 수 없다.',
                    need='허용 거리 안의 실제 공개 도보 옵션과 웹 출입구·경로를 맞춘 표본 확대. 고도 입력의 보행면·방향·횡단 대기 검증. 장거리 원시 진단을 제품 제공률로 쓰지 않기.')
    rows[15].update(metric='서울 버스 API 이용 승인을 완료했고 실제 응답 104정류장을 확인했다. 지하철 실제 응답도 확보했다. 실제 차량 도착 대비 시간 오차는 아직 측정하지 않았다.',
                    reason='공급자 시각·방향·정류장 순서를 보존하고, 출발 대기 등 상태를 0초로 바꾸지 않는다. 자료 조회 성공과 고객 알림 연결 성공은 별도다.',
                    need='새 API 응답의 숫자 ETA/상태 검증, 출발 알림 연결, 제공자 시각이 오래되거나 미래일 때 대체 조회·실제 도착 대조.')
    counts = dict(Counter(r['status'] for r in rows))
    snapshots = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in WEB.glob('*.json')}
    catalog = dict(created_at=datetime.now().astimezone().isoformat(),scope='이동 21개 기능의 현재 근거·남은 작업; 기능 수는 제품 준비율 아님',counts=counts,features=rows,development_source_sha256=hashlib.sha256(DEV.read_bytes()).hexdigest(),web_source_sha256=snapshots)
    OUT.mkdir(parents=True,exist_ok=True)
    for name, obj in [('readiness-catalog.json',catalog),('development-summary.json',d)]:
        with (OUT/name).open('x',encoding='utf8') as out: json.dump(obj,out,ensure_ascii=False,indent=2)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':12,'svg.fonttype':'none'})
    fig, axes = plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    for ax,title,before,after,total in [(axes[0],'버스만으로 경로 산출',d['bus_before']['comparable'],bus['comparable'],100),
                                      (axes[1],'같은 지하철 경로의 요금 안내',same['before_present'],same['after_present'],same['n'])]:
        ax.barh(['이전','현재'],[before,after],color=['#93A5B5','#126B67'],height=.55)
        ax.set_xlim(0,total*1.2);ax.invert_yaxis();ax.set_title(title,loc='left',pad=18)
        for i,v in enumerate([before,after]):ax.text(v+1,i,f'{v}/{total} = {v/total:.1%}',va='center',fontsize=13)
        for edge in ax.spines.values():edge.set_visible(False)
        ax.set_xticks([])
    fig.suptitle('산출과 요금 안내가 늘었습니다. 시간·정확 요금 검증은 별도입니다.',fontsize=14)
    fig.savefig(OUT/'mobility-development.png',dpi=170);fig.savefig(OUT/'mobility-development.svg');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4.5),layout='constrained')
    labels=['다음 큰길 3.8km','네이버 큰길 4.1km','네이버 계단회피 4.7km']
    for y,(label,up,down) in enumerate(zip(labels,[82,82,92],[71,76,78],strict=True)):
        ax.plot([down,up],[y,y],color='#BAC8D2',lw=5,zorder=1)
        ax.scatter([down,up],[y,y],c=['#126B67','#A05A00'],s=90,zorder=2)
        ax.text(down-1,y,f'내려감 {down}분',ha='right',va='center')
        ax.text(up+1,y,f'올라감 {up}분',va='center')
    ax.set_yticks(range(3),labels);ax.set_xlim(52,110);ax.invert_yaxis();ax.set_xlabel('웹 화면의 예상 도보 시간(분)')
    ax.set_title('같은 표시 거리에도 방향별 시간이 다릅니다',loc='left',pad=20)
    for edge in ['top','right','left']:ax.spines[edge].set_visible(False)
    fig.savefig(OUT/'walk-direction-web.png',dpi=170);fig.savefig(OUT/'walk-direction-web.svg');plt.close(fig)
    old_html=(OLD/'mobility-readiness.html').read_text(encoding='utf8')
    css=re.search(r'<style>(.*?)</style>',old_html,re.S).group(1)
    table=''.join(f'<tr data-status="{html.escape(r["status"])}"><th scope="row">{html.escape(r["name"])}<br><span>{html.escape(r["status"])}</span></th><td>{html.escape(r["scope"])}<p>{html.escape(r["metric"])}</p></td><td>{html.escape(r["reason"])}<details><summary>더 필요한 것</summary><p>{html.escape(r["need"])}</p></details></td></tr>' for r in rows)
    nav_url=load(WEB/'naver-W01-walk.json')['url']
    kakao_url=load(WEB/'kakao-W01-share.json')['share_url']
    goog_url=load(WEB/'google-W01-walk.json')['url']
    doc=f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>guguroute 이동 기능 검증 v6</title><style>{css}</style><main>
<header><p class="sub">guguroute / 서울 / 2026-10-08 / 근거 갱신 v6</p><h1>이동 기능, 어디까지 쓸 수 있나</h1><p class="lead">경로와 공식 운임 자료를 보강했습니다.<br>전체 자동 적용 완료를 판정하려면 남은 검증이 필요합니다.</p><p>기존 100쌍을 보고 고친 개발 결과입니다. 실제 운행·결제 정확도와 수정 후 독립 검증을 대신하지 않습니다.</p></header>
<section><h2>경로·요금 안내 개선</h2><img class="chart" src="mobility-development.png" alt="버스 산출과 동일 지하철 경로 요금 안내의 전후 비교"><p>버스 시간은 대기 제외 ±5분 {time['within']}/{time['n']} = {time['within']/time['n']:.1%}. 지하철 시간은 대기 제외 ±5분 {rail['time_without_wait']['absolute']['within']}/{rail['comparable']} = {rail['time_without_wait']['absolute']['within']/rail['comparable']:.1%}. 요금 안내 수와 시간 정확도를 따로 셉니다.</p><p>공식 신분당선 운임은 구간 조합에 따라 계산합니다. 웹의 출발·도착별 정답을 제품에 넣는 보정표는 추가하지 않았습니다. 할인 전 상한과 단일 예상액을 구분합니다.</p></section>
<section><h2>추가 웹 검색으로 찾은 도보 문제</h2><img class="chart" src="walk-direction-web.png" alt="남산 양방향의 표시 거리와 도보 시간 비교"><p>광화문 기념물↔N서울타워를 다음·네이버에서 양방향으로 조회했습니다. 구글은 도보 범위 밖이라고 표시했고, 대중교통 경로는 확보했습니다. 한 구간의 진단이며 기존 N063의 다른 출발 좌표와 섞어 정확도를 계산하지 않았습니다.</p><p>계단 수·지하도·상세 구간과 조회 시각을 원문으로 보관했습니다. 양방향 경로 형상이 완전히 같다는 검증은 아직 없으며, 이 차이를 경사 하나의 효과로 단정하지 않습니다.</p><p><a href="{html.escape(kakao_url)}">다음 지도 경로</a> · <a href="{html.escape(nav_url)}">네이버 도보 경로</a> · <a href="{html.escape(goog_url)}">구글 제공 범위 확인</a></p></section>
<section><h2>서울역→남대문시장 추가 웹 비교</h2><p>조회 원문과 조회 시각을 따로 보존했습니다. 장소 이름과 주소는 확인했지만 공급자별 출입구 좌표·경로 형상이 같다는 검증은 남아 있습니다. 아래 값은 공급자가 표시한 예상값이며, 서로 다른 출발 시각의 대중교통 값을 정확도 평균에 섞지 않습니다.</p><table><thead><tr><th>수단</th><th>네이버 표시</th><th>다음 표시</th><th>확인할 차이</th></tr></thead><tbody><tr><th>도보</th><td>738m · 13분 · 계단 2 · 지하도 1</td><td>972m · 19분</td><td>출입구·지하 연결 경로</td></tr><tr><th>차량·택시</th><td>2.1km · 11분 · 5,200원</td><td>3.4km · 14분 · 약 7,800원</td><td>차량 출입구·회전·우회 경로</td></tr><tr><th>자전거</th><td>944m · 4분</td><td>2.0km · 10분 · 고도 25~43m</td><td>진입점·통행 가능한 길</td></tr><tr><th>대중교통</th><td>최적 9분 · 지하철 1,550원<br>선택 출발 17:32</td><td>첫 버스 후보 12분 · 1,500~2,500원</td><td>운행 노선·탑승 대기·조회 시각</td></tr></tbody></table><p>구글은 한강대로 405의 서울역 주소를 명시한 뒤 버스 8분·도보 합계 6분을 표시했습니다. 처음 자동 선택한 다른 주소의 5분 결과는 비교에서 제외하고 원문만 남겼습니다. 이번 구글 화면에서는 자동차·도보·자전거 선택이 비활성화됐습니다.</p><p>차량 화면의 연료비와 택시비는 서로 다른 항목으로 보존했습니다. 두 지도 값의 차이를 요금 상수 하나로 보정하지 않고 실제 차량 경로와 출입구부터 비교합니다.</p></section><section><h2>고도와 실시간 자료 확보</h2><p>서울 범위의 공개 고도 원자료 2개를 실제 내려받아 각 3,601×3,601 격자와 결측 0을 확인했습니다. 고도 자료를 확보했다는 사실과 제품에 경사 시간을 반영했다는 사실은 별개입니다. 건물·교량·지하통로·계단의 실제 높이 및 원자료 측량 시각은 추가 확인이 필요합니다.</p><p>실제 버스 응답은 정류장 104개, 차량 도착 칸 208개 중 숫자 시간 175개·상태 33개입니다. 출발 대기·곧 도착·회차 대기를 0초로 바꾸지 않습니다. 두 데이터 소스가 실제 DB를 공유하는 시험에서 외부 호출 1회와 동일 공급 시각 재사용을 확인했습니다.</p></section><section><h2>실제 제품 경로로 재검증한 도보</h2><p>기존 30쌍을 쌍마다 공개 구간 계산기로 두 번 호출했습니다. 60회 모두 결과가 같았고, 30쌍 모두 제품의 직선 도보 상한 1,200m를 넘었습니다. 공개 도보 옵션을 제공한 표본은 0/30이므로 제품 시간 오차는 계산하지 않습니다. 계산식 진단의 15/30을 제품 정확도나 제공률로 읽으면 안 됩니다.</p><p>거리 원시 진단은 ±10% 17/30→17/30입니다. MAE가 줄어든 평균 0.255분의 쌍별 bootstrap95% 구간은 −0.727~+0.086분으로, 개선과 악화가 모두 가능한 범위입니다. 계단 소요 전달 결함 수정과 실제 지도 시간 정확도 향상은 따로 검증합니다.</p></section><section><h2>출발 안내와 차량 제약</h2><p>이미 발행한 안내는 경로 조회 전에 같은 테넌트·여행·안내 키의 바깥함 행을 확인합니다. 실제 로컬 DB 시험 16/16에서 안내를 10번 반복해도 발행 1회·경로 조회 1회를 확인했습니다. 동시에 실행되는 회차는 최종 UNIQUE로 중복 발행을 막으며, 조회 호출까지 정확히 한 번으로 잠근 것은 아닙니다. 실제 버스 도착정보를 안내에 연결하는 작업은 남아 있습니다.</p><p>실제 OSM 파일에서 현재 도로그래프 관련 회전 제약 6,258개를 확보했습니다. 회전 제약 자료 확인기 27/27 통과와 차량 탐색 적용은 별개입니다. 현재 자료는 적용 후보이며, 같은 도로의 U턴·경유 도로·차종 예외·조건부 제한을 구분하고 들어온 방향을 보존하는 탐색이 필요합니다.</p></section><section><h2>짧은 도보의 실제 제품 결과</h2><p>서울역↔남대문시장 공개 장소 중심을 사용한 하나의 독립 구간, 두 방향입니다. 우리 값은 양방향 1,179m·20분, 네이버는 738m·13/12분, 다음은 972m·19/18분입니다. 출입구와 경로가 같다는 확인은 남아 있습니다. 이 값들을 제품 정확도 관문에 합산하지 않습니다.</p><p>우리 내부 거리 1,179.3768m는 직선 842.4120m×기존 우회계수 1.4와 같습니다. 품질 표시 optimistic=true·길 밖 접근 최대87.9m여서 기존 거리 하한이 결과를 지배합니다. 이번에 장소별 계수를 맞춰 넣은 것이 아닙니다.</p><figure><img src="../2026-10-09_walk_product_verification_v2/product-scope-and-raw-diagnostic.png" alt="기존 도보30쌍은 제품 정책 밖이며 원시 오차 변화의 신뢰구간은0을 포함함"><figcaption>기존30쌍의 제품 평가 분모와 원시 계산 진단을 구분한 추가 검증입니다.</figcaption></figure></section><section><h2>실시간 안내 연결의 선행 결함 수정</h2><p>버스의 노선ID·승하차 순번·정류소ID를 내부 후보부터 판정·환승·막차 역산까지 유지했습니다. 동명 정류장을 이름만으로 다시 고르던 결함입니다. 요금 유형·구간 시간 범위·대안도 선택한 행을 사용합니다.</p><p>실시간 차량 선택과 도착정보 회귀31/31을 통과했습니다. 접근6분이면3분 뒤 차량은 제외하고7분 뒤 차량의 접근 후 대기1분을 계산합니다. 만차·숫자 ETA 없음·확인시각이 미래/만료된 경우를 별도 상태로 반환합니다. 소비 함수의 시험이며 고객 안내 연결 완료나 실제 운행 정확도가 아닙니다.</p><p>공개 경로 저장에 구간별 관측 문맥을 연결하고 후속 환승을 재계산하는 작업, 차량 회전 제한 적용, 신규 구간 검증은 진행 중입니다. 전체 이동 기능 완료는 선언하지 않습니다.</p></section><section><h2>21개 기능의 근거와 남은 일</h2><p>{' · '.join(f'{k} {v}/21' for k,v in counts.items())}. 목록 분류이며 제품 준비율이 아닙니다. 조건부 사용은 범위가 확인된 시연·참고 안내입니다.</p><div class="filters" role="group" aria-label="기능 판정 필터"><button data-filter="전체" aria-pressed="true">전체 보기</button><button data-filter="조건부 사용" aria-pressed="false">조건부 사용 보기</button><button data-filter="개선 필요" aria-pressed="false">개선 필요 보기</button><button data-filter="추가 검증" aria-pressed="false">추가 검증 보기</button></div><p id="visible-count" aria-live="polite"></p><table><thead><tr><th>기능·판정</th><th>사용 범위·실측</th><th>근거·남은 일</th></tr></thead><tbody>{table}</tbody></table></section>
<section><h2>실제 조회와 시험의 범위</h2><p>무료 공공 버스 도착 API는 승인 후 실제 응답을 확인했습니다. 지도 경로 개발자 API는 이번 추가 수집에서 직접 호출하지 않았습니다. 웹의 예상값을 실제 승차 시간이나 결제액으로 부르지 않습니다.</p><p>로컬 계산기와 데이터 소스의 검증입니다. 배포된 cs 프로젝트 서버의 고객 일정 변경·출발 알림 연결 검증은 이 자료에서 완료로 표시하지 않습니다. 시간 처리 속도는 동시 시험 조건이 달라 전후 성능 우열을 판정하지 않습니다.</p><p>대기 전후는 분리하며, 경로별 비율 차이는 (우리 값/웹 값−1)×100을 계산한 뒤 중앙값을 냅니다. 주요 중앙값의 bootstrap 95% 구간은 집계 JSON에 있습니다.</p></section>
<footer><p><a href="../2026-10-09_mobility_research_v2/research-register.json">2026-10-09까지 확인한 논문·공식자료와 적용 전제</a> · <a href="readiness-catalog.json">기능 근거 데이터</a> · <a href="development-summary.json">재검산 수치·입력 해시</a> · <a href="../2026-10-08_mobility_readiness_v3/mobility-readiness.html">보존된 이전 판</a></p></footer></main><script>const rows=[...document.querySelectorAll('tbody tr[data-status]')],buttons=[...document.querySelectorAll('[data-filter]')];function applyFilter(f){{rows.forEach(r=>r.hidden=f!=='전체'&&r.dataset.status!==f);document.querySelector('#visible-count').textContent=`${{rows.filter(r=>!r.hidden).length}}/${{rows.length}}개 기능 표시`;buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===f)));}}buttons.forEach(b=>b.addEventListener('click',()=>applyFilter(b.dataset.filter)));applyFilter('전체');</script></html>'''
    with (OUT/'mobility-readiness.html').open('x',encoding='utf8') as out:out.write(doc)
    print(json.dumps(dict(features=len(rows),counts=counts,output=str(OUT)),ensure_ascii=False))

if __name__=='__main__':main()
