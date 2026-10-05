# 5차 그림 — GPU 없는 CPU 4코어 배포: 월비용·지연·하루 처리량. 폭 1080px.
#  CPU 측정값은 scripts/plan_qa_bench/results/cpu_eval_summary.txt (cpu_eval_summary.py 가 만든다)에서 읽는다. 파일이 없으면 「중간값」으로 표시한다.
#  가격: AWS 서울 온디맨드(공식 가격 계산기 파일 2026-09-25 판 — 같은 파일을 §76 에서 읽음), 1달러=1,400원, 730시간/월, EBS gp3 30GB $0.0912/GB·월.
#  오라클: 공식 문서(docs.oracle.com Always Free) 현재 2 OCPU·12GB, 종량 단가는 검색 요약값이라 [미확인].
import os
import re
import textwrap
from make_figures import canvas, box, t, head, PAL, INK, SUB, LINE, OUT
from make_figures4 import reading_box, lines_height

HERE = os.path.dirname(os.path.abspath(__file__))
SUM = os.path.join(HERE, '..', '..', 'scripts', 'plan_qa_bench', 'results', 'cpu_eval_summary.txt')
final = os.path.exists(SUM)
warm, cold, acc_non, n_non, acc_all, n_all, n_warm = 4.6, 65.0, None, None, None, None, None
if final:
    s = open(SUM, encoding='utf-8').read()
    m = re.search(r'다음 질문\(같은 일정, 캐시 맞음\) 평균 ([\d.]+)초', s)
    c = re.search(r'첫 질문\(일정 전체를 읽음\) 평균 ([\d.]+)초', s)
    a = re.search(r'합계: 요청 둘 제외 (\d+)/(\d+) = ([\d.]+)% · 전체\(A 채점\) (\d+)/(\d+)', s)
    warm, cold = float(m.group(1)), float(c.group(1))
    acc_non, n_non, acc_all, n_all = int(a.group(1)), int(a.group(2)), int(a.group(4)), int(a.group(5))


def per_day(f):
    avg = (1 - f) * warm + f * cold
    return 86400 / avg, avg


def fmt(n):
    return f'{n:,.0f}'


def fig27():
    tag = '실측' if final else '중간값(측정 진행 중)'
    w0, a0 = per_day(0.0)
    w2, a2 = per_day(0.2)
    w1, a1 = per_day(1.0)
    acc_txt = (f'정확도 {acc_non}/{n_non} = {100 * acc_non / n_non:.1f}% (요청 둘 제외 · HF 4비트 학습 평가 97.5% 와 비교)' if final else '정확도는 835문제 측정 후 채운다 (스모크 6/6 · mix10 앞 120문제 118 맞음)')
    rows = [  # (선택지, 월 비용(앱 포함), 질문당 시간, 하루 처리(한 대), 종류)
        ('① 오라클 무료 ARM (지금 문서: 2 OCPU·12GB)', '0원', f'다음 질문 약 {2 * warm:.0f}초 · 첫 질문 약 {2 * cold:.0f}초 [예상: 코어 반이라 2배]', f'약 {fmt(per_day(0.0)[0] / 2)}건(첫 질문 없을 때)', 'warn'),
        ('② 오라클 종량 4 OCPU·24GB (무료분 차감)', '약 3.9~4.1만원 [미확인 단가]', f'x86 값 {warm:.1f}초 / {cold:.0f}초 · ARM 은 [미측정]', f'약 {fmt(w0)}건(첫 질문 없을 때)', 'plain'),
        ('③ AWS 서울 m6g.xlarge (4 vCPU · 16GiB)', '약 19.6만원', '같은 급 [미측정 — ARM]', '같음', 'plain'),
        ('④ AWS 서울 r6g.xlarge (4 vCPU · 32GiB)', '약 25.3만원', '같은 급 [미측정 — ARM]', '같음', 'plain'),
        ('⑤ RunPod A4000 GPU 포드 (앱 포함)', '약 25.6만원', '0.8~2.1초 (실측: 올라마 E4B QAT)', '약 4.2만~10.4만건', 'gpu'),
        ('⑥ x600 (자체 GPU 4070S)', '0원 + 트래픽', 'GPU 속도 [이 구성은 미측정]', '—', 'done'),
        ('⑦ Luna API', '하루 1천 건 0.7만 · 5천 건 3.7만 · 10만 건 73.9만원 (+앱)', '호출당 지연 [미측정]', '제한 없음(요금만)', 'done'),
    ]
    reading = [
        f'CPU 4코어에서 가르친 E4B(GGUF Q8, 7.5GB)는 같은 일정의 다음 질문을 약 {warm:.1f}초에 풀지만, 일정 전체를 처음 읽는 질문은 약 {cold:.0f}초 걸린다. 한 여행에서 질문이 여러 번 오면 느린 건 첫 질문뿐이다.',
        f'하루 처리량(한 대·24시간 100% 가동 가정): 첫 질문이 없으면 약 {fmt(w0)}건 · 새 여행이 20% 면 약 {fmt(w2)}건(평균 {a2:.1f}초) · 매번 새 여행이면 약 {fmt(w1)}건({cold:.0f}초). 하루 1천 건은 어느 경우든 되고, 5천 건은 캐시가 대부분 맞아야 하고, 10만 건은 한 대로 안 된다.',
        '★무료 ARM 이 줄었다: 오라클 공식 문서의 Always Free 는 지금 2 OCPU · 12GB (이전 4 OCPU · 24GB, 2026-06 보도). 12GB 에는 모델 7.5GB + 앱·DB 가 겨우 들어간다. 유료 CPU(③④) 월 19.6만~25.3만원은 GPU 포드(⑤) 25.6만원의 약 4분의 3~같은 수준이라 값 이점이 작다.',
        '지연 비교: GPU 포드는 0.8~2.1초로 CPU 보다 2~5배 빠르고 첫 질문 65초가 없다. CPU 는 「월 0원 · 느림」, GPU 는 「월 25만원 · 빠름」의 선택이다.',
    ]
    H = 190 + 150 + len(rows) * 106 + lines_height(reading) + 330
    fig, ax = canvas(H)
    head(ax, 'GPU 없는 CPU 4코어 배포 — 월비용과 지연', f'가르친 E4B GGUF Q8 · AMD EPYC 7702 코어 4개(다른 작업과 같은 기계) · {tag}')
    box(ax, 30, 160, 1020, 128, 'now', 16, 2)
    t(ax, 56, 190, '우리가 잰 값 (서버 B, CPU 4코어·GPU 끔, 질문 835개 중 mix8~12)', 15.5, PAL['now'][2], True)
    t(ax, 56, 224, f'첫 질문(일정 전체 약 1,800토큰 읽기) {cold:.0f}초 · 같은 일정 다음 질문 {warm:.1f}초 (새로 읽는 토큰 약 90 · 캐시 약 1,700)', 14, PAL['now'][2])
    t(ax, 56, 254, acc_txt, 13.4, PAL['now'][2])
    y = 306
    t(ax, 40, y, '선택지', 13, SUB, True)
    t(ax, 480, y, '월 비용(앱 포함)', 13, SUB, True)
    t(ax, 700, y, '질문당 시간', 13, SUB, True)
    y += 16
    for nm, cost, lat, cap, kind in rows:
        box(ax, 30, y, 1020, 96, kind, 12, 1.6)
        col = PAL[kind][2]
        t(ax, 46, y + 26, nm, 13, col, True)
        t(ax, 46, y + 62, f'하루 처리: {cap}', 11.6, SUB)
        for i, s in enumerate(textwrap.wrap(cost, 17)[:3]):
            t(ax, 480, y + 24 + i * 22, s, 12.4, col, i == 0)
        for i, s in enumerate(textwrap.wrap(lat, 22)[:3]):
            t(ax, 700, y + 24 + i * 22, s, 12, col)
        y += 106
    y += 6
    y = reading_box(ax, y, '읽는 법', reading, 'gpu')
    reading_box(ax, y, '출처와 한계', ['오라클: docs.oracle.com Always Free(현재 2 OCPU·12GB) · linuxiac.com 2026-06-14 보도(4→2 OCPU, 24→12GB). 종량 단가는 검색 요약값이라 [미확인].',
                                      'AWS: 서울 온디맨드(r6g.xlarge \$0.244 · m6g.xlarge \$0.188 /시간, 가격 계산기 2026-09-25 판) × 730시간 × 1,400원 + EBS 30GB.',
                                      '측정 기계는 x86 이고 ARM(오라클·AWS 그래비톤)은 더 느릴 수 있다 — 상한(낙관)으로 읽는다. 한 번의 측정이다.'], 'warn', 76, 11.6, 26)
    fig.savefig(os.path.join(OUT, 'fig27_CPU_전용_배포_월비용과_지연.png'))


if __name__ == '__main__':
    fig27()
    print('ok', '실측' if final else '중간값')
