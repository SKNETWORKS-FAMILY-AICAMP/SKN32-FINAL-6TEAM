# 6차 그림 — 비용 v6(그림 22 에 CPU 전용·C 채점 추가) · 처리량 v6(그림 23 에 CPU 4코어 측정 추가). 새 판이라 fig22·fig23 원본은 그대로 둔다.
#  사용자 지적(2026-10-06): CPU 전용 배포는 별도 그림이 아니라 「월 총비용」과 「처리량」 그림에 반영해야 한다 → 이 파일이 그 새 판.
#  CPU 측정값은 scripts/plan_qa_bench/results/cpu_eval_summary.txt(cpu_eval_summary.py)에서 읽는다. 없으면 「중간값」으로 표시한다.
import os
import re
import textwrap
from make_figures import canvas, box, t, head, PAL, INK, SUB, LINE, OUT

HERE = os.path.dirname(os.path.abspath(__file__))
SUM = os.path.join(HERE, '..', '..', 'scripts', 'plan_qa_bench', 'results', 'cpu_eval_summary.txt')
final = os.path.exists(SUM)
warm, cold, cpu_acc, cpu_n = 4.6, 65.0, None, None
if final:
    s = open(SUM, encoding='utf-8').read()
    warm = float(re.search(r'다음 질문\(같은 일정, 캐시 맞음\) 평균 ([\d.]+)초', s).group(1))
    cold = float(re.search(r'첫 질문\(일정 전체를 읽음\) 평균 ([\d.]+)초', s).group(1))
    a = re.search(r'합계: 요청 둘 제외 (\d+)/(\d+) = ([\d.]+)%', s)
    cpu_acc, cpu_n = int(a.group(1)), int(a.group(2))
TAG = '실측' if final else '중간값'
F_NEW = 0.2                                            # 새 여행(첫 질문)이 차지하는 비율 가정
AVG4 = (1 - F_NEW) * warm + F_NEW * cold              # 4코어 평균 초/건
AVG2 = 2 * AVG4                                        # 2코어 [예상: 코어 수에 반비례]
DAY4_WARM, DAY4_MIX = 86400 / warm, 86400 / AVG4


def cell(ax, x, y, w, h, val, small, tone, unit='만원'):
    box(ax, x, y, w, h, tone, 10, 2)
    t(ax, x + w / 2, y + h * 0.38, val + unit, 16.5, PAL[tone][2], True, 'center')
    t(ax, x + w / 2, y + h * 0.76, small, 11, PAL[tone][2], False, 'center')


def util(n, avg):
    return 100 * n * avg / 86400


def tone_of(p):
    return 'now' if p < 60 else ('warn' if p < 100 else 'bad')


def box_text(ax, y, title, lines, kind, width=70, size=12.2, lh=30):
    wrapped = [w for s in lines for w in textwrap.wrap(s, width, subsequent_indent='  ')]
    h = 60 + len(wrapped) * lh + 16
    box(ax, 30, y, 1020, h, kind, 16, 2.2)
    t(ax, 56, y + 32, title, 16.5, PAL[kind][2], True)
    for i, s in enumerate(wrapped):
        t(ax, 56, y + 66 + i * lh, s, size, PAL[kind][2])
    return y + h + 18, h


# ───────────────── 22 v6. 월 총비용 — CPU 전용·C 채점 추가 ─────────────────
def fig22_v6():
    gpu_lines = ['· RunPod 공식 페이지를 읽은 값: A4000 시큐어 시간당 0.25달러 · 커뮤니티 0.17달러 (포드 사양은 페이지에 없음 → 콘솔 값)',
                 '· 월(730시간): 시큐어 182.5달러 = 25.6만원 · 커뮤니티 124.1달러 = 17.4만원 · 참고 RTX 2000 Ada 시큐어 0.24달러 = 24.5만원',
                 '· AWS 서울에서 같은 16 vCPU·64GiB: m5a.4xlarge 월 86.7만원(최저). 앱 스택은 평소 1.2GiB·급등 1.8GiB(x600 실측)라 61GB 포드에 같이 올려도 여유']
    cpu_lines = [f'· 가르친 E4B 를 GGUF Q8(7.5GB)로 바꿔 CPU 4코어(GPU 끔)에서 835문제를 풀었다({TAG}): 같은 일정의 다음 질문 {warm:.1f}초 · 일정 전체를 처음 읽는 첫 질문 {cold:.0f}초 · 정답 {cpu_acc if final else "측정 중"}/{cpu_n if final else ""}(빈 응답 12개는 틀린 것으로 셈).',
                 '· 월 값은 서버 가격 + 디스크. AWS 서울 온디맨드 m6g.xlarge(4 vCPU·16GiB) 시간당 \\$0.188 = 19.6만원 · r6g.xlarge(4 vCPU·32GiB) 시간당 \\$0.244 = 25.3만원(EBS 30GB 포함).',
                 '· ★오라클 무료 ARM 은 공식 문서 기준 지금 2 OCPU·12GB (이전 4 OCPU·24GB — 2026-06 보도). 종량 4 OCPU·24GB 는 무료분 차감 약 4만원(단가는 검색 요약값 [미확인]).',
                 f'· 가동률 = 하루 건수 × 평균 초 ÷ 86,400. CPU 평균은 새 여행(첫 질문)이 {int(F_NEW * 100)}% 라는 가정: 4코어 {AVG4:.1f}초/건 · 2코어 {AVG2:.0f}초/건 [예상 — 코어 반이면 2배]. ARM 은 미측정(x86 값은 낙관).']
    acc_cpu = f'{100 * cpu_acc / cpu_n:.1f}%' if final else '측정 중'
    c_cpu = f'C {100 * cpu_acc / 835:.1f}%' if final else 'C 측정 중'
    # (이름, 부가 설명, 지연, 정답률 769, C 835, 칸 3개)
    n1, n2, n3 = 1000, 5000, 100000
    rows = [
        ('A4000 시큐어 · 한 곳', '앱까지 포드 위 · 가르친 E4B', '질문당 1.5~1.7초(실측, 4비트+어댑터)', '97.5%', 'C 89.8%',
         [('25.6', '가동 2%', 'now', '만원'), ('25.6', '가동 9%', 'now', '만원'), ('51.1~76.7', '2~3대 (185%)', 'bad', '만원')]),
        ('A4000 커뮤니티 · 한 곳', '값은 페이지 읽은 값 · 중단 위험', '질문당 1.5~1.7초', '97.5%', 'C 89.8%',
         [('17.4', '가동 2%', 'now', '만원'), ('17.4', '가동 9%', 'now', '만원'), ('34.8~52.2', '2~3대 (185%)', 'warn', '만원')]),
        ('A4000 시큐어 + 앱 AWS', '포드는 GPU만 · 앱은 AWS', '질문당 1.5~1.7초', '97.5%', 'C 89.8%',
         [('31.0', 'GPU 25.6 + 앱 5.4', 'warn', '만원'), ('31.0', 'GPU 25.6 + 앱 5.4', 'warn', '만원'), ('61.8~87.4', 'GPU 2~3대 + 앱 10.7', 'bad', '만원')]),
        ('2000 Ada 시큐어 · 한 곳', '참고(8코어·31GB) · 속도는 무학습 E4B QAT 올라마 값', '질문당 0.8~2.1초(실측, 캐시·동시 설정에 따라)', '97.5%', 'C 89.8%',
         [('24.5', '가동 2%', 'now', '만원'), ('24.5', '가동 12% (최악)', 'now', '만원'), ('49.0', '2대 (동시 4 도 96%)', 'warn', '만원')]),
        ('x600 (보유)', '앱 + 가르친 E4B', '속도 미측정', '97.5%', 'C 89.8%',
         [('0.0', '+ 인터넷 요금', 'now', '만원'), ('0.0', '+ 인터넷 요금', 'now', '만원'), ('불가', '한 대 약 185%', 'bad', '')]),
        ('★오라클 무료 ARM 2코어·12GB', 'CPU 만 · 가르친 E4B Q8 (12GB 에 7.5GB+앱)', f'다음 질문 약 {2 * warm:.0f}초 · 첫 질문 약 {2 * cold:.0f}초 [예상]', acc_cpu, c_cpu,
         [('0.0', f'가동 {util(n1, AVG2):.0f}%', tone_of(util(n1, AVG2)), '만원'), ('불가', f'가동 {util(n2, AVG2):.0f}%', 'bad', ''), ('불가', f'가동 {util(n3, AVG2):,.0f}%', 'bad', '')]),
        ('★오라클 종량 4코어·24GB', '무료분(2/12) 차감 · CPU 만', f'다음 {warm:.1f}초 · 첫 {cold:.0f}초 (x86, ARM 미측정)', acc_cpu, c_cpu,
         [('약 4.0', f'가동 {util(n1, AVG4):.0f}% [단가 미확인]', tone_of(util(n1, AVG4)), '만원'), ('약 4.0', f'가동 {util(n2, AVG4):.0f}% (빠듯)', tone_of(util(n2, AVG4)), '만원'), ('불가', f'가동 {util(n3, AVG4):,.0f}%', 'bad', '')]),
        ('★AWS m6g.xlarge 4코어·16GB', 'CPU 만 · 앱 포함 · 디스크 포함', f'다음 {warm:.1f}초 · 첫 {cold:.0f}초 (그래비톤 미측정)', acc_cpu, c_cpu,
         [('19.6', f'가동 {util(n1, AVG4):.0f}%', tone_of(util(n1, AVG4)), '만원'), ('19.6', f'가동 {util(n2, AVG4):.0f}% (빠듯)', tone_of(util(n2, AVG4)), '만원'), ('불가', f'약 {util(n3, AVG4) / 100:.0f}대 필요', 'bad', '')]),
        ('★AWS r6g.xlarge 4코어·32GB', 'CPU 만 · 앱 포함 · 디스크 포함', f'다음 {warm:.1f}초 · 첫 {cold:.0f}초 (그래비톤 미측정)', acc_cpu, c_cpu,
         [('25.3', f'가동 {util(n1, AVG4):.0f}%', tone_of(util(n1, AVG4)), '만원'), ('25.3', f'가동 {util(n2, AVG4):.0f}% (빠듯)', tone_of(util(n2, AVG4)), '만원'), ('불가', f'약 {util(n3, AVG4) / 100:.0f}대 필요', 'bad', '')]),
        ('Luna API + 앱 AWS', 'API 건당 0.25원 · Codex 호출', '지연 미측정', '96.4%', 'C 88.7%',
         [('6.1', 'API 0.7 + 앱 5.4', 'now', '만원'), ('9.1', 'API 3.7 + 앱 5.4', 'now', '만원'), ('84.6', 'API 73.9 + 앱 10.7', 'warn', '만원')]),
    ]
    reading = ['달라진다: CPU 전용은 하루 1천 건이면 월 0원(무료 ARM, 느림)~19.6만원(AWS)이고, 5천 건부터 가동률이 100% 근처라 안전하지 않다. 10만 건은 CPU 로는 한 대로 안 된다.',
               f'유료 CPU(AWS 19.6만~25.3만원)는 GPU 포드(25.6만원)와 값이 비슷한데 속도는 2~5배 느리고 첫 질문이 {cold:.0f}초다 — 값 이점은 무료 구간(오라클)에서만 생긴다. 그런데 그 무료 구간이 2 OCPU·12GB 로 줄었다.',
               '정답률 칸: 왼쪽은 요청 둘 제외 769문제, 아래 작은 글씨 C 는 요청 둘 66문제를 포함한 835문제 C 채점(한 항목 모델은 요청 둘 C=0 이라 769÷835 가 상한).',
               '위험: 포드 한 대에 앱까지 올리면 단일 장애점, 커뮤니티는 중단·재배정 위험(미확인). CPU 측정은 x86 한 번이다.']
    H = 2600
    fig, ax = canvas(H)
    head(ax, '월 총비용 v6 — CPU 전용 · C 채점 추가 · 단위 만원/월', f'건 = 고객 질문 1개를 일정 항목 번호로 짚는 모델 호출 1번 · 30일 · 1달러=1,400원 · CPU 값 {TAG}')
    y, _ = box_text(ax, 160, '기존: RunPod A4000 포드 기준 (v5)', gpu_lines, 'gpu', 74, 12.2, 28)
    y, _ = box_text(ax, y, '★추가: GPU 없는 CPU 4코어 배포', cpu_lines, 'now', 74, 12.2, 28)
    t(ax, 40, y + 20, '월 총비용 (만원)', 20, INK, True)
    y += 50
    for nm, x in (('하루 1천 건', 560), ('하루 5천 건', 760), ('하루 10만 건', 960)):
        t(ax, x, y + 18, nm, 13.5, SUB, True, 'center')
    t(ax, 40, y + 18, '선택지 · 질문당 시간', 14, SUB, True)
    t(ax, 395, y + 18, '정답률(769)', 13, SUB, True, 'center')
    ax.plot([40, 1040], [y + 40, y + 40], color=LINE, lw=2)
    y += 54
    for nm, sub, lat, acc, c, cells in rows:
        star = nm.startswith('★')
        box(ax, 30, y, 1020, 130, 'plain', 14, 1.6)
        t(ax, 46, y + 28, nm, 14, INK, True)
        for k, line in enumerate(textwrap.wrap(sub + ' · ' + lat, 27)[:4]):
            t(ax, 46, y + 56 + k * 21, line, 10.6, SUB)
        t(ax, 395, y + 52, acc, 19, INK, True, 'center')
        t(ax, 395, y + 90, c, 11.5, SUB, False, 'center')
        for (val, small, tone, unit), x in zip(cells, (560, 760, 960)):
            cell(ax, x - 90, y + 14, 180, 102, val, small, tone, unit)
        y += 140
    for k, line in enumerate(textwrap.wrap('초록 = 60% 미만 · 노랑 = 100% 미만(빠듯) · 빨강 = 한 대로 불가. 가동 = 한 대의 하루 최대 건수 대비. GPU 줄은 하루 5.4만 건(A4000) 기준, CPU 줄은 위 가정.', 96)):
        t(ax, 40, y + 14 + k * 22, line, 11.4, SUB)
    y += 70
    y, _ = box_text(ax, y, '그래서 달라지는 것', reading, 'gpu', 74, 12.2, 29)
    fig.set_size_inches(10.8, (y + 20) / 100)
    ax.set_ylim(y + 20, 0)
    fig.savefig(os.path.join(OUT, 'fig22_월_총비용_v6_CPU포함.png'))


# ───────────────── 23 v6. 처리량 — CPU 4코어 측정 추가 ─────────────────
def fig23_v6():
    data = [('GPU 순차 · 캐시 안 맞음', 2.07, 1737, 'bad'), ('GPU 순차 · 캐시 맞음', 1.23, 2922, 'now'), ('GPU 동시 2 · 캐시 안 맞음', 1.38, 2604, 'warn'), ('GPU 동시 4 · 캐시 안 맞음', 0.83, 4324, 'now'),
            ('GPU 동시 8 · 캐시 안 맞음', 1.07, 3356, 'warn'),
            ('★CPU 4코어 · 다음 질문(캐시 맞음)', warm, 3600 / warm, 'gpu'), ('★CPU 4코어 · 첫 질문(캐시 안 맞음)', cold, 3600 / cold, 'gpu')]
    reading = ['캐시가 맞으면 문제당 1.23초, 안 맞으면 2.07초 → 앞부분 재사용만으로 1.7배 빠르다(GPU). 요청을 4개 동시에 받으면 캐시 없이도 시간당 4,324건(순차의 2.5배), 8개는 오히려 떨어진다.',
               f'★CPU 4코어(GPU 끔, 가르친 E4B GGUF Q8, {TAG}): 같은 일정의 다음 질문 {warm:.1f}초(시간당 {3600 / warm:,.0f}건), 일정 전체를 처음 읽는 첫 질문 {cold:.0f}초(시간당 {3600 / cold:,.0f}건). 캐시 효과가 GPU 의 1.7배가 아니라 약 {cold / warm:.0f}배다.',
               '한계: GPU 는 40문제 1회씩(같은 문제를 되풀이해 동시 측정에 캐시가 일부 섞였을 수 있음). CPU 는 835문제 한 번이며 x86(AMD EPYC 7702 코어 4개)이고 같은 기계에서 다른 작업이 돌았다 — ARM 은 더 느릴 수 있다.']
    cols = [('GPU 순차\n캐시 없음', 41700, 'g'), ('GPU 순차\n캐시 있음', 70100, 'g'), ('GPU 동시 4\n캐시 없음', 103800, 'g'), ('가르친 E4B\nA4000 1.6초', 54000, 'g'),
            (f'★CPU 4코어\n다음 질문만', DAY4_WARM, 'c'), (f'★CPU 4코어\n새 여행 {int(F_NEW * 100)}%', DAY4_MIX, 'c')]
    H = 2300
    fig, ax = canvas(H)
    head(ax, '한 대가 하루 몇 건? v6 — GPU 실측 + ★CPU 4코어 실측', f'GPU 올라마 E4B QAT(2000 Ada) 40문제 · ★CPU 가르친 E4B GGUF Q8 코어 4개 835문제 · {TAG}')
    t(ax, 40, 190, '시간당 처리 건수 (많을수록 좋음)', 19, INK, True)
    y, scale = 226, 440 / 4400
    for nm, sec, qh, tone in data:
        t(ax, 40, y + 28, nm, 14, INK, True)
        w = max(qh * scale, 8)
        box(ax, 370, y, w, 56, tone, 8, 2)
        t(ax, 370 + w + 12, y + 20, f'{qh:,.0f}건/시간', 14.5, INK, True)
        t(ax, 370 + w + 12, y + 44, f'문제당 {sec:.2f}초 · 하루 {qh * 24 / 1000:.1f}천 건', 11.5, SUB)
        y += 74
    y, _ = box_text(ax, y + 10, '읽는 법', reading, 'warn', 72, 12.2, 28)
    t(ax, 40, y + 20, '하루 요청 수별 한 대의 가동률 — 예상', 19, INK, True)
    y += 54
    xs = [290, 405, 520, 635, 760, 905]
    t(ax, 40, y + 14, '하루', 13, SUB, True)
    for (nm, cap, kind), x in zip(cols, xs):
        for k, line in enumerate(nm.split('\n')):
            t(ax, x, y + 12 + k * 18, line, 11, SUB, True, 'center')
        t(ax, x, y + 52, f'{cap / 10000:.1f}만/일' if cap >= 10000 else f'{cap / 1000:.1f}천/일', 10.5, SUB, False, 'center')
    y += 76
    for nm, n in (('1천 건', 1000), ('5천 건', 5000), ('10만 건', 100000)):
        box(ax, 30, y, 1020, 88, 'plain', 10, 1.6)
        t(ax, 46, y + 44, nm, 15, INK, True)
        for (cn, cap, kind), x in zip(cols, xs):
            pct = 100 * n / cap
            tone = tone_of(pct)
            box(ax, x - 52, y + 12, 104, 64, tone, 8, 1.8)
            t(ax, x, y + 44, f'{pct:,.0f}%', 15.5, PAL[tone][2], True, 'center')
        y += 98
    for k, line in enumerate(textwrap.wrap('초록 = 60% 미만 · 노랑 = 100% 미만(빠듯) · 빨강 = 한 대로 불가. GPU 넷째 열 = A4000 어댑터 따로 1.6초. CPU 는 가르친 E4B 를 그대로 CPU 에 올린 값.', 96)):
        t(ax, 40, y + 14 + k * 22, line, 11, SUB)
    y += 70
    cl = [f'하루 1천 건은 CPU 4코어 한 대로도 된다(가동 {util(1000, AVG4):.0f}%). 5천 건은 가동 {util(5000, AVG4):.0f}% 라 새 여행이 20% 만 섞여도 한계 — 같은 여행의 질문이 몰려 와야 한다.',
          f'하루 10만 건은 CPU 로는 약 {util(100000, AVG4) / 100:.0f}대가 필요해 현실적이지 않다. GPU 는 동시 4 로 받으면 한 대로 96%.',
          '일정 앞부분 캐시를 여행마다 오래 들고 있도록 서빙 슬롯을 늘리는 설정이 CPU 에서 가장 큰 지렛대다(미측정). 일정 전체 대신 후보 몇 개만 읽히면 첫 질문 시간도 줄 것으로 예상하나 가르친 모델 재학습이 필요하다.',
          f'질문당 시간 비교: CPU {warm:.1f}초대 · GPU 0.8~2.1초 → CPU 는 2~5배 느리고, 첫 질문은 30~80배 느리다.']
    y, _ = box_text(ax, y, '그래서 달라지는 것', cl, 'now', 72, 12.2, 28)
    fig.set_size_inches(10.8, (y + 20) / 100)
    ax.set_ylim(y + 20, 0)
    fig.savefig(os.path.join(OUT, 'fig23_처리량_v6_CPU포함.png'))


if __name__ == '__main__':
    fig22_v6()
    fig23_v6()
    print('ok', TAG)
