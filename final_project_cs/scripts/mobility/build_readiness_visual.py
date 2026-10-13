"""이동 기능별 사용 범위·비교 근거를 독립 HTML과 PNG/PDF로 만든다.

설계: 흰색/옅은 청색(#EEF4F8), 남색(#193A56), 청록(#126B67),
황갈색(#A05A00), 회색(#52606C). 맑은 고딕. 경로의 두 끝점처럼
전후를 연결하는 비교 도표를 중심으로, 기능 표와 근거를 왼쪽 정렬한다.
준비율 원형 도표 대신 산출률과 오차를 분리한다. 외부 스크립트·폰트 없음.
"""
from __future__ import annotations
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT/'wiki/records/reports/assets/2026-10-08_mobility_readiness_v3'
DEV = ROOT/'wiki/records/reports/assets/2026-10-08_mobility_development_v3'
REPEAT = ROOT/'wiki/records/reports/assets/2026-10-08_mobility_development_v2'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def feature(name, status, scope, metric, reason, need, source):
    return dict(name=name,status=status,scope=scope,metric=metric,reason=reason,need=need,source=source)


def catalog(d):
    return [
      feature('택시 미터 예상액','조건부 사용','서울 중형·예상액 안내','카카오 ±1,000원 55/100; 중앙 −900원/−7.2%. 네이버 9/12.',
              '공식 거리·저속 시간 요율은 구현됐으나 추천 경로와 저속 구간이 다르다.',
              '같은 경로·출발 시각으로 반복 대조; 실제 미터 영수증. 대형·모범·호출료 범위 분리.','taxi'),
      feature('택시 예산 여유','조건부 사용','예산용 예상액; 결제 상한 약속 제외','카카오 예상액 이상 96/100; 네이버 11/12. 중앙 여유 +27.4%/+36.0%.',
              '37%는 앞 자료에서 고정한 여유. 웹 예상액을 덮는 빈도이며 실제 결제 보장이 아니다.',
              '다른 날·교통 상태의 새 경로 검증; 실제 결제 초과율과 과다 여유를 함께 재기.','taxi'),
      feature('자동차 소요 시간','개선 필요','일정의 참고 시간','카카오 ±5분 88/100; 중앙 −1.70분/−10.4%; 절대오차 평균 2.49분.',
              '도로급 정적 속도로 경로를 고른 뒤 교통 속도로 시간을 재산정한다. 두 기준이 다르다.',
              '교통 상태를 경로 선택 비용에도 반영하는 실험; 출퇴근·한강 횡단 반복 측정.','fresh'),
      feature('자동차 경로 거리','개선 필요','범위가 확인된 경로 참고','카카오 ±10% 53/100; 중앙 −6.8%; 절대오차 평균 1.256km.',
              '택시 부족 4건은 우리 거리가 웹 경로보다 약 35~45% 짧았다. 요율만 바꿔 해결되지 않는다.',
              '회전 제한·도로 연결·경로 형상 대조 및 지도 그래프 갱신.','fresh'),
      feature('대중교통 전체 소요','개선 필요','오차·제외 경로를 확인한 일정 참고','수정 전 카카오 대기 제외 ±5분: 빠른 후보 72/100·추천안 68/100. 추가 네이버 7/8 → 8/8; 절대오차 평균 7.38 → 2.63분.',
              '부분 순환선의 없는 연결을 수정해 연신내→합정이 62→19분(웹 18분)으로 회복됐다. 기존 자료를 보고 수정한 8쌍이라 독립 검증이 필요하다.',
              '같은 출발 시각·입구·목표 경로로 별도 날짜 반복 측정.','multi'),
      feature('지하철 경로 산출','조건부 사용','거리·노선 범위가 확인된 서울 경로',f"수단을 엄격히 나눈 재집계: {d['rail_before']['comparable']}/96 → {d['rail_after']['comparable']}/96.",
              '실제 구간열로 수단을 구분했다. 기존 95/96에는 버스 혼합 후보가 섞여 있었다.',
              '급행·종착·지선·요일·막차 구간의 독립 검증.','development'),
      feature('버스 직행·환승 산출','개선 필요','직행과 1회 환승의 참고안',"52/100 → 95/100. 회복 43건, 기존 52건 유지. 대기 제외 ±5분 53/95.",
              '버스만 고를 때 환승 생성이 차단되던 조건과 가장 이른 도착의 환승 누락을 수정했다.',
              '남은 5건 원인·2회 이상 환승·재탐색 상한·실행 시간. 새 경로 검증.','development'),
      feature('지하철 요금','개선 필요','정확·추정·범위 상단을 표시',f"같은 {d['rail_same_route']['n']}경로: 요금 칸 {d['rail_same_route']['before_present']} → {d['rail_same_route']['after_present']}. 추가 상단 {d['rail_same_route']['new_upper']}건. 추가 웹 8쌍 요금 표시 5/8·동일 금액 3/8.",
              '요금 구간 경계를 넘는 거리 범위는 확정 요금을 낼 수 없다. 자료 없는 노선은 기본요금으로 메우지 않는다.',
              '누락 구간 거리·별도 운임 자료 확보. 상단 안내를 정확도 개선으로 세지 않기.','development'),
      feature('버스·혼합 환승 요금','개선 필요','할인 전 상한 표시','수정 후 버스 요금 칸 94/95; 이 중 50건 할인 전 상한. 웹 범위 일치 35/94.',
              '탈것별 단일 요금 합으로 예산을 안내한다. 통합거리 할인 요금 자체를 계산한 값은 아니다.',
              '실제 운임거리·환승 할인·하차 태그·조조 적용을 계산하고 같은 경로로 검증.','development'),
      feature('장소 사이 도보 거리','추가 검증','1.2km 정책 안의 직접 도보; 출입점 정렬 검증 대기',
              '기존 카카오 30쌍은 제품 상한 밖: 공개 제공 0/30. 원시 진단 ±10% 17/30·중앙 +2.1%는 제품 정확도가 아니다. 기존 네이버 MAE 0.68km/12쌍도 출입점·정책 정렬 미검증.',
              '정책 밖 원시 거리 비교가 조건부 사용 판정에 연결돼 있었다. 정책 안의 정렬된 새 제품 비교를 확보하지 못했다.',
              '같은 출입점 좌표·조회시각·추천 경로를 보존한 정책 안 새 표본과 제품 도보 옵션을 대조하고 실제 보행도 별도로 측정한다. 공원·계단·횡단보도 연결을 검증한다.','fresh'),
      feature('도보 소요·역 접근 시간','개선 필요','보행 속도에 따른 참고값','도보 ±5분: 카카오 15/30, 네이버 4/12. 대중교통 접근 도보 중앙 −26.4%(98쌍).',
              '전체 도보와 역 진입·환승 도보의 오차 양상이 다르다. 속도 상수 하나로 고칠 근거가 없다.',
              '출구·개찰·고도·계단·신호 대기 분리; 실제 보행 반복 측정.','fresh'),
      feature('자전거 경로','개선 필요','도로망상의 참고 경로','카카오 거리 ±10% 16/30; 네이버 거리 중앙 −17.5%(12쌍).',
              '자전거길 선호와 강변·횡단 연결에서 서비스별 경로가 다르다.',
              '허용 도로·강변 진입·교량·경로 형상 확인. 안전 경로 정확도를 별도로 재기.','multi'),
      feature('자전거 소요','개선 필요','운행 시간 참고','카카오 ±5분 23/30; 중앙 −3.2분/−17.9%. 네이버 절대오차 평균 12.73분/12쌍.',
              '현재 시간이 짧게 나오는 경향. 속도를 20km/h로 올리는 계산은 오히려 차이를 키웠다.',
              '경로를 먼저 대조한 뒤 경사·정지·자전거 유형·대여 시간을 분리.','fresh'),
      feature('첫차·막차·출발 역산','추가 검증','시간표를 쓰는 판정 로직','웹 첫차·막차 확인은 한 경로. 전체 노선·요일 통과율 분모 미확보.',
              '코드·단위 시험은 있으나 실제 운행 시간에 대한 대표 검증이 부족하다.',
              '평일·주말·공휴일·자정 넘김·환승 막차와 실제 출발 안내를 묶어 검증.','wiki'),
      feature('환승 횟수·역 출구·승차 칸','추가 검증','원자료가 있는 항목 표시','기존 추천안 환승 횟수 일치 66/100. 출구·승차 칸 정확도 분모 미확보.',
              '추천안이 달라 환승 횟수 차이가 곧 오류는 아니다. 승차 칸은 경로 정확 일치 자료만 표시한다.',
              '같은 경로로 환승·출구·개찰과 안내 칸을 직접 대조.','wiki'),
      feature('실시간 지하철·버스 도착','추가 검증','연결 및 원자료 조회','실제 도착 대비 오차·누락률을 이번 웹 대조로 재지 않았다.',
              '현재 시각의 도착 정보를 미래 일정 시간표와 섞지 않도록 해야 한다.',
              '같은 정류장 반복 관측·실제 도착 기록·오래된 값 및 실패 전환 확인.','wiki'),
      feature('혼잡 안내','추가 검증','근거 자료가 있는 혼잡 경고','실제 혼잡 대비 정확도 분모 미확보.',
              '노선·시간대 통계와 급행/실제 차량 혼잡은 다를 수 있다.',
              '일반·급행 구분 및 경고의 실제 일치율·누락률 측정.','wiki'),
      feature('무정차·도로 사고 감시','추가 검증','연결된 소스의 사건 판정','공지에서 역을 읽는 로직·도로 사건 대체 소스는 구현. 실제 사건 회수율 미측정.',
              '공지 제목만으로 역을 못 읽는 경우가 있다. 사건 없음과 읽기 실패를 구분해야 한다.',
              '실제 공지 재생·동명 역·다역 공지·두 소스 동시 실패·지연 검증.','wiki'),
      feature('따릉이 대여·반납·재고','추가 검증','대여소 및 실시간 재고 조회','지도 자전거 시간 비교는 실제 대여소 재고·반납 성공률 시험이 아니다.',
              '도로 주행 시간 외에 대여소 접근·잠금 해제·반납·재고가 필요하다.',
              '주행 전후 재고 변동·마감·만차·대체 대여소·전체 여정 소요 측정.','wiki'),
      feature('사건 후 일정 조정·자동 적용','추가 검증','계산기와 Team 연결','이번 오프라인 100쌍 대조는 배포된 cs 프로젝트 서버의 일정 변경 검증이 아니다.',
              '후보를 내는 능력과 고객 일정에 안전하게 적용하는 능력은 별도로 검증해야 한다.',
              '여행 전체 재생: 제약·동시 변경·실패 전환·알림·최신 링크 확인.','wiki'),
      feature('지도 경로 표시','추가 검증','화면 개선 검토','네이버와 우리 화면의 사용자 과제 성공률·경로 표시 정확도 비교는 아직 안 했다.',
              '경로선·구간 색·출발/도착·정류장·환승·시간 카드를 연결해야 길을 따라갈 수 있다.',
              '실제 경로 형상을 가진 지도 시안 및 휴대폰 화면·클릭 연동 시험.','wiki'),
    ]


def draw(d, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.backends.backend_pdf import PdfPages
    font=FontProperties(fname='C:/Windows/Fonts/malgun.ttf')
    plt.rcParams.update({'font.family':font.get_name(),'font.size':11,'axes.unicode_minus':False})
    navy,teal,gray='#193A56','#126B67','#52606C'
    fig,axs=plt.subplots(1,2,figsize=(13,5.5),layout='constrained')
    ax=axs[0];labels=['버스 경로 산출\n(전체 100쌍)','지하철 요금 안내\n(같은 경로 93쌍)']
    same=d['rail_same_route']; n=same['n']; bn=same['before_present']; an=same['after_present']
    labels[1]=f'지하철 요금 안내\n(같은 경로 {n}쌍)'
    before=[52,bn/n*100];after=[95,an/n*100]
    for y,(b,a) in enumerate(zip(before,after)):
        ax.plot([b,a],[y,y],color='#9ABAB8',lw=6)
        ax.scatter([b,a],[y,y],c=[gray,teal],s=130,zorder=3)
        ax.text(b,y+.13,['52/100 = 52%',f'{bn}/{n} = {bn/n*100:.1f}%'][y],ha='center',color=gray)
        ax.text(a,y-.2,['95/100 = 95%',f'{an}/{n} = {an/n*100:.1f}%'][y],ha='center',color=teal)
    ax.set(yticks=[0,1],yticklabels=labels,xlim=(40,105),ylim=(-.6,1.6),xlabel='산출·안내 가능 비율 (%)',title='나오지 않던 답을 회복')
    ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
    ax=axs[1];before=28/52*100;after=33/52*100
    ax.barh(['수정 전','수정 후'],[before,after],color=[gray,teal],height=.45)
    for y,t in enumerate(['28/52 = 53.8%','33/52 = 63.5%']):ax.text(2,y,t,color='white',va='center')
    ax.set(xlim=(0,100),xlabel='카카오 버스 소요와 ±5분 이내 (%)',title='기존에 나오던 같은 52쌍의 시간')
    ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
    fig.suptitle('triPilot 이동 기능 개선 · 산출률과 시간 오차를 구분',fontsize=18,color=navy)
    fig.supxlabel('서울 · 기존 100쌍을 개발에 재사용 · 대기 시간 제외 · 추가 지하철 요금 10건은 상단 예상액\n수정 후 버스 전체는 ±5분 53/95 = 55.8%, 절대오차 평균 8.34분. 실제 운행·결제 검증 아님.',fontsize=10)
    for ext in ('png','svg'):fig.savefig(path/f'mobility-development.{ext}',dpi=180)
    with PdfPages(path/'mobility-readiness-charts.pdf') as pdf:
        pdf.savefig(fig)
        plt.close(fig)
        f,ax=plt.subplots(figsize=(13,7),layout='constrained')
        rows=[('택시 예상액 ±1,000원',55,100),('택시 예산 ≥ 카카오 예상액',96,100),('자동차 시간 ±5분',88,100),
              ('대중교통 대기 제외 ±5분',72,100),('버스 대기 제외 ±5분 (수정 후)',53,95),('도보 시간 ±5분',15,30),('자전거 시간 ±5분',23,30)]
        ax.barh([r[0] for r in rows],[r[1]/r[2]*100 for r in rows],color=navy,height=.55)
        for y,(_,n,m) in enumerate(rows):ax.text(2,y,f'{n}/{m} = {n/m*100:.1f}%',color='white',va='center')
        ax.invert_yaxis();ax.set(xlim=(0,100),xlabel='정의한 조건을 만족한 표본 (%)',title='서로 다른 기능은 서로 다른 기준으로 판단')
        f.supxlabel('카카오 웹 예상값 기준. 예산 충족률은 정확도가 아니며, 표본 수와 허용 오차도 서로 다릅니다.\n100쌍: 서울 단회 관측. 도보·자전거: 짧은 경로 30쌍. 웹 조회와 우리 도착 목표는 완전히 같지 않습니다.',fontsize=10)
        pdf.savefig(f);f.savefig(path/'mobility-feature-comparison.png',dpi=180);plt.close(f)
        repeat=read(REPEAT/'naver-repeat-final-summary.json')
        old={r['id']:r for r in read(REPEAT/'naver-repeat-summary.json')['public_rows']}
        rr=sorted(repeat['public_rows'],key=lambda r:r['id'])
        f,ax=plt.subplots(figsize=(13,6),layout='constrained')
        labels=[r['a'].split('역')[0]+' → '+r['b'].split('역')[0] for r in rr]
        for i,r in enumerate(rr):
            ours=r['our_min']-r['our_wait'];web=r['web_min']
            prior=old[r['id']]['our_min']-old[r['id']]['our_wait']
            ax.plot([prior,ours],[i,i],color='#9ABAB8',lw=4)
            ax.scatter([prior],[i],color='#A05A00',s=65,zorder=3)
            ax.scatter([web,ours],[i,i],color=[gray,'#A05A00' if abs(ours-web)>5 else teal],s=65,zorder=3)
            ax.text(max(ours,web,prior)+1,i,f"웹 {web} / 수정 전 {prior} / 후 {ours}분",va='center',fontsize=10)
        ax.set(yticks=range(len(rr)),yticklabels=labels,xlim=(0,100),xlabel='소요 시간 (분)',title='추가 네이버 8쌍: 없는 연결을 고쳐 큰 오차를 줄임')
        ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
        f.supxlabel('우리 대기 제외 ±5분 7/8 → 8/8 · 중앙 +3 → +2.5분, +11.1 → +7.0% · 절대오차 평균 7.38 → 2.63분\n10월 8일 출발 12:15 웹 화면, 우리 계산은 웹 도착 시각 목표. 역 입구·추천 경로는 다를 수 있음. 진단 표본, 독립 검증 아님.',fontsize=10)
        pdf.savefig(f);f.savefig(path/'mobility-new-web-8.png',dpi=180);plt.close(f)


def main():
    d=read(DEV/'development-summary.json');rows=catalog(d)
    ASSETS.mkdir(parents=True,exist_ok=True)
    sources={'fresh':'2026-10-08_0503_이동_새100쌍_카카오웹_성능조사.md',
             'multi':'2026-10-08_0954_이동_네이버_구글_웹_12쌍_대조.md',
             'taxi':'2026-10-08_0924_택시_공식요율과_네이버_구글_대조.md',
             'development':read(DEV/'final-evidence.json')['report_file']}
    table=''
    for r in rows:
        vals={k:html.escape(v) for k,v in r.items()}
        source=('../'*4+'teams/mobility.md') if r['source']=='wiki' else '../../'+sources[r['source']]
        table+=f'<tr data-status="{vals["status"]}"><th scope="row">{vals["name"]}<span class="status">{vals["status"]}</span></th><td>{vals["scope"]}<p class="metric">{vals["metric"]}</p></td><td>{vals["reason"]}<details><summary>더 필요한 검증 보기</summary><p>{vals["need"]}</p><a href="{source}">근거 문서 열기</a></details></td></tr>'
    counts={s:sum(r['status']==s for r in rows) for s in ('조건부 사용','개선 필요','추가 검증')}
    doc='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>triPilot 이동 기능 사용 범위</title><style>
    :root{--ink:#193A56;--teal:#126B67;--line:#CBD8E1;--soft:#EEF4F8;--muted:#52606C;--warn:#A05A00}*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font:16px/1.65 'Malgun Gothic',sans-serif}main{max-width:1160px;margin:auto;padding:40px 28px 80px}header{border-bottom:4px solid var(--ink);padding-bottom:28px}h1{font-size:38px;line-height:1.25;letter-spacing:-1.5px;margin:12px 0}h2{font-size:25px;margin:38px 0 12px}h3{font-size:19px}p{max-width:78ch}a{color:var(--teal);text-underline-offset:3px}.sub{color:var(--muted)}.lead{font-size:20px;max-width:55ch}.callout{background:var(--soft);border-left:5px solid var(--teal);padding:18px 22px;margin:22px 0}.chart{display:block;width:100%;height:auto}.filters{display:flex;gap:10px;flex-wrap:wrap;padding:18px 0}button{font:inherit;border:1px solid var(--line);background:white;color:var(--ink);padding:8px 15px;border-radius:4px;cursor:pointer}button[aria-pressed=true]{color:white;background:var(--ink)}:focus-visible{outline:3px solid var(--warn);outline-offset:3px}table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{border-bottom:1px solid var(--line);padding:18px 14px;text-align:left;vertical-align:top}thead th{background:var(--soft)}thead th:first-child{width:23%}thead th:nth-child(2){width:39%}tbody th{font-size:17px}.status{display:block;color:var(--teal);font-size:13px;margin-top:5px}.metric{font-size:14px;font-weight:bold;margin:10px 0 0}.count{font-size:14px;color:var(--muted)}details{font-size:14px;margin-top:12px}summary{cursor:pointer;color:var(--teal);font-weight:bold}details p{margin:12px 0}.method{display:grid;grid-template-columns:1fr 1fr;gap:22px}.method article{border-top:2px solid var(--line);padding-top:8px}footer{border-top:2px solid var(--ink);margin-top:40px;padding-top:18px;font-size:14px;color:var(--muted)}[hidden]{display:none!important}@media(max-width:700px){main{padding:22px 16px}h1{font-size:29px}.lead{font-size:18px}.method{grid-template-columns:1fr}table,tbody,tr,th,td{display:block;width:100%}thead{display:none}tr{border:1px solid var(--line);margin-bottom:16px}th,td{border:0;padding:12px 16px}tbody th{background:var(--soft)}}@media print{main{max-width:none;padding:0}button,.filters{display:none}details{display:block}tr{break-inside:avoid}h2{break-after:avoid}}
    </style><main><header><p class="sub">triPilot 이동 검증 기록 / 2026년 10월 8일 / 서울</p><h1>이동 기능, 어디까지 쓸 수 있나</h1><p class="lead">버스 경로 누락은 줄였습니다.<br>고객 일정에 자동 적용할 수준의 검증은 남아 있습니다.</p><p>조건부 사용은 <strong>범위가 확인된 시연·참고 안내</strong>를 뜻합니다. 실제 운행이나 결제의 정확도를 보장하는 판정은 아닙니다.</p></header>
    <section><h2>이번에 고친 것과 달라진 수치</h2><img class="chart" src="mobility-development.png" alt="버스 산출률 52퍼센트에서 95퍼센트, 지하철 같은 93경로의 요금 안내 68개에서 78개. 기존 버스 52쌍의 시간 허용 오차 충족은 28개에서 33개로 증가"><div class="callout"><strong>버스 43경로를 회복했습니다.</strong> 버스만 선택해도 버스 환승을 만들고, 가장 이른 도착 탐색에도 넣습니다. 환승을 금지한 동행 조건은 지킵니다.<br><strong>지하철 10경로에 상단 예상액을 추가했습니다.</strong> 확정 요금으로 바꾸지 않았으며, 정확·단일 추정 요금 68건은 그대로입니다.</div><p>택시 요율과 37% 예산 여유는 이번에 바꾸지 않았습니다. 출발·도착별 정답을 넣는 표나 지도 요금을 덮어쓰는 보정도 추가하지 않았습니다. 자료가 없는 노선의 요금을 기본요금으로 채우지 않습니다.</p></section>
    <section><h2>기능별 사용 범위와 남은 일</h2><p class="count">CATALOG_COUNTS. 이는 기능 목록의 분류이며 제품 준비율이 아닙니다.</p><div class="filters" role="group" aria-label="사용 범위별 기능 필터"><button data-filter="전체" aria-pressed="true">전체 보기</button><button data-filter="조건부 사용" aria-pressed="false">조건부 사용 보기</button><button data-filter="개선 필요" aria-pressed="false">개선 필요 보기</button><button data-filter="추가 검증" aria-pressed="false">추가 검증 보기</button></div><p id="visible-count" aria-live="polite"></p><table><thead><tr><th>기능 / 판정</th><th>사용 범위 / 비교 수치</th><th>판정 근거 / 더 필요한 것</th></tr></thead><tbody>FEATURE_TABLE</tbody></table></section>
    <section><h2>비교 수치를 읽는 기준</h2><img class="chart" src="mobility-feature-comparison.png" alt="기능별 서로 다른 허용 오차와 예산 충족 조건을 비교한 도표"><div class="method"><article><h3>자료가 말해 주는 것</h3><p>카카오: 이전 200쌍과 겹치지 않는 100쌍, 짧음 30·중간 40·김 30. 네이버 48건과 구글 좌표 대중교통 12건은 그중 선택한 같은 12쌍입니다. 다음 지도는 카카오 연결을 확인한 것입니다. 티맵 실제 대조 경로는 0건입니다.</p><p>대기 포함 시간과 우리 대기를 뺀 시간을 분리했습니다. 오차 비율은 경로별 (우리 값 ÷ 웹 값 − 1) × 100의 중앙값입니다. 중앙 0%도 모든 경로가 맞는다는 뜻은 아닙니다.</p></article><article><h3>추가로 확인해야 할 것</h3><p>개선에 기존 100쌍을 다시 썼으므로 수정 후 독립 검증이 아닙니다. 지도별 조회 시각·선택 장소·추천 경로·도착 조건이 완전히 같지 않습니다. 반복은 다른 시간대 진단이며 실제 탑승은 하지 않았습니다.</p><p>이번 검증은 로컬 계산기입니다. 배포된 cs 프로젝트 서버의 응답·고객 일정 자동 변경·알림·실제 결제는 확인하지 않았습니다. 동시 실험으로 처리 시간 전후 우열도 판정하지 않습니다.</p></article></div></section><footer><p>자료: 카카오·네이버·구글 지도 웹 화면의 예상값, 서울시 공식 교통 요금, 로컬 계산기 재계산. 외부 지도 개발자 API 호출 없이 브라우저 화면을 읽었습니다. 원문은 git 제외 데이터 폴더에 보존하고 공유 자료에는 집계와 근거만 담았습니다.</p><p><a href="mobility-readiness-charts.pdf">그림 PDF 열기</a>　<a href="readiness-catalog.json">기능 목록 데이터 열기</a>　<a href="https://sftc.seoul.go.kr/seoul/mulga/main/contents.do?menuNo=200021">서울시 공식 지하철 요금 확인</a></p></footer></main><script>const buttons=[...document.querySelectorAll('[data-filter]')],rows=[...document.querySelectorAll('tbody tr')];function applyFilter(filter){rows.forEach(r=>r.hidden=filter!=='전체'&&r.dataset.status!==filter);document.querySelector('#visible-count').textContent=`${rows.filter(r=>!r.hidden).length}/${rows.length}개 기능 표시`;buttons.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===filter)));}buttons.forEach(b=>b.addEventListener('click',()=>applyFilter(b.dataset.filter)));applyFilter('전체');</script></html>'''
    extra='<section><h2>추가 웹 조회에서 고친 큰 오차</h2><img class="chart" src="mobility-new-web-8.png" alt="연신내 합정 웹 18분, 우리 대기 제외 수정 전 57분에서 수정 후 19분. 8쌍 절대오차 평균 7.38분에서 2.63분"><p>부분 순환선은 실제 연결·운행 방향을 따라 계산하게 고쳤습니다. 연신내→합정의 대기 포함 시간이 62→19분(웹 18분)으로 줄었습니다. 다른 경로가 나빠지지 않도록 하차역 뒤 자료 부족과 타는 구간 자료 부족을 구분했습니다.</p><p>같은 8쌍에서 대기 포함 ±5분은 5/8→6/8, 대기 제외는 7/8→8/8입니다. 대기 제외 절대오차 평균은 7.38→2.63분. 요금은 5/8에 표시되며 웹과 같은 금액은 2/8→3/8입니다. 웹은 12:15 출발, 우리 계산은 웹 도착 시각 목표로 조회했습니다. 수정에 사용한 진단 표본이며 독립 검증·실제 승차·결제 측정이 아닙니다.</p></section>'
    doc=doc.replace('<section><h2>기능별 사용 범위와 남은 일</h2>',extra+'<section><h2>기능별 사용 범위와 남은 일</h2>')
    doc=doc.replace('FEATURE_TABLE',table).replace('CATALOG_COUNTS',f"{len(rows)}개 기능: "+', '.join(f'{s} {n}개' for s,n in counts.items()))
    for name,body in [('readiness-catalog.json',json.dumps({'scope':'이동 모듈 기능·고객 안내 범위','counts':counts,'features':rows},ensure_ascii=False,indent=2)),('mobility-readiness.html',doc)]:
        with (ASSETS/name).open('x',encoding='utf-8') as f:f.write(body)
    draw(d,ASSETS)
    print(json.dumps({'folder':str(ASSETS),'features':len(rows),'counts':counts},ensure_ascii=False))


if __name__=='__main__':main()
