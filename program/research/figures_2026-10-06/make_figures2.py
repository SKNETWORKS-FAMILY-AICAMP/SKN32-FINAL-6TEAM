# 2차 그림 묶음 — 비용 v3(만원 단위·앱 서버 포함) · 캐시 공정 비교 · 모델 성능표 · 결론/조합/장단점 · 진행/앞으로 · 검토한 방법과 결과. 폭 1080px.
#  수치 출처는 연구 문서(여행일정_질문인식_모델비교_2026-09-29.md)의 46·60~76절과 results/export, AWS 공식 가격 파일(2026-09-25 판).
import os
from make_figures import canvas, box, t, head, PAL, INK, SUB, LINE, OUT
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def cell(ax, x, y, w, h, val, small, tone):
    box(ax, x, y, w, h, tone, 10, 2)
    t(ax, x + w / 2, y + h * 0.38, val + '만원', 17, PAL[tone][2], True, 'center')
    t(ax, x + w / 2, y + h * 0.76, small, 11.5, PAL[tone][2], False, 'center')


# ───────────────── 13. 비용 v3 ─────────────────
def fig13():
    H = 1830
    fig, ax = canvas(H)
    head(ax, '월 총비용 비교 v3 — 앱 서버 포함 · 단위 만원', '한 달 30일 · 1달러 = 1,400원 · 캐시 없음 기준(다음 그림에서 설명) · 칸의 숫자는 모두 「만원/월」')
    box(ax, 30, 160, 1020, 330, 'now', 16, 2.2)
    t(ax, 56, 196, '① 앱 서버 (두 방식 모두에 필요) — AWS 서울, 최소 사양', 18, PAL['now'][2], True)
    lines = ['· 1 vCPU · 2GiB 램: t2.small  시간당 \$0.0288 → 한 달 \$21.02 = 2.9만원',
             '· 디스크 8GB (gp3)  \$0.0912/GB·월 → 한 달 \$0.73 = 0.1만원',
             '· 합계 약 3.0만원/월  (더 싼 선택: ARM t4g.small 2.2만원 · t3.small 2.8만원)',
             '· 무료 구간: 새 계정 「무료 플랜」은 크레딧 최대 \$200, 6개월 → 첫 6개월은 0원 가능',
             '   (6개월 뒤 유료 전환 · 허용되는 인스턴스 종류는 공식 문서에서 확인 못 함)']
    for i, s in enumerate(lines):
        t(ax, 56, 238 + i * 36, s, 14, PAL['now'][2])
    t(ax, 56, 440, '출처: AWS 가격 목록(2026-09-25 판) calculator.aws · pricing.us-east-1.amazonaws.com · aws.amazon.com/free/free-tier-faqs', 11.5, PAL['now'][2])
    t(ax, 56, 468, '공개 IPv4 주소 요금은 별도(제 기억 기준 월 약 \$3.7 — 이번에 확인 못 함)', 11.5, PAL['now'][2])
    t(ax, 40, 530, '② 월 총비용 = 앱 서버 + 분류 처리', 20, INK, True)
    for nm, x in (('하루 1천 건\n(월 3만)', 520), ('하루 5천 건\n(월 15만)', 740), ('하루 10만 건\n(월 300만)', 960)):
        t(ax, x, 596, nm, 14, SUB, True, 'center')
    t(ax, 40, 596, '선택지', 14, SUB, True)
    t(ax, 300, 596, '성능', 14, SUB, True, 'center')
    ax.plot([40, 1040], [634, 634], color=LINE, lw=2)
    rows = [
        ('자체 GPU + 앱 AWS', '앱 AWS 3.0 + RunPod GPU', '97.5%', [('27.6', '앱 3.0 + GPU 24.5', 'now'), ('27.6', '앱 3.0 + GPU 24.5', 'now'), ('52.1~76.6', '앱 3.0 + GPU 2~3대', 'bad')]),
        ('자체 GPU 한 곳에', '앱까지 포드 한 대 위에', '97.5%', [('24.5', '앱 포함 · 단일 장애점', 'now'), ('24.5', '앱 포함 · 단일 장애점', 'now'), ('49.1~73.6', 'GPU 2~3대 · 앱 포함', 'bad')]),
        ('Luna API + 앱 AWS', 'API 건당 0.25원', '96.4%', [('3.8', '앱 3.0 + API 0.7', 'now'), ('6.7', '앱 3.0 + API 3.7', 'now'), ('77.0', '앱 3.0 + API 73.9', 'warn')]),
        ('Sol API + 앱 AWS', 'API 건당 4.9원', '98.8%', [('17.8', '앱 3.0 + API 14.8', 'warn'), ('77.0', '앱 3.0 + API 73.9', 'warn'), ('1,481', '앱 3.0 + API 1,478', 'bad')]),
        ('Astra API + 앱 AWS', 'API 건당 24.6원', '99.6%', [('77.0', '앱 3.0 + API 73.9', 'warn'), ('372.6', '앱 3.0 + API 369.6', 'bad'), ('7,395', '앱 3.0 + API 7,392', 'bad')]),
    ]
    y = 650
    for nm, sub, acc, cells in rows:
        box(ax, 30, y, 1020, 124, 'plain', 14, 1.6)
        t(ax, 46, y + 38, nm, 16, INK, True)
        t(ax, 46, y + 78, sub, 12, SUB)
        t(ax, 385, y + 62, acc, 20, INK, True, 'center')
        for (val, small, tone), x in zip(cells, (555, 755, 955)):
            cell(ax, x - 90, y + 14, 180, 96, val, small, tone)
        y += 136
    t(ax, 40, y + 20, '초록 = 싼 쪽 · 노랑 = 비슷하거나 비쌈 · 빨강 = 매우 비쌈. 성능 = 요청 둘 제외 769문제(mix8~12) 정답률', 12.5, SUB)
    y += 56
    box(ax, 30, y, 1020, 360, 'warn', 16, 2.2)
    t(ax, 56, y + 36, '읽는 법과 주의', 18, PAL['warn'][2], True)
    notes = ['· 두 방식 모두 앱 서버가 필요하므로 같이 더했다. 차이(분류 비용)는 앱 서버를 빼도 같다.',
             '· RunPod 요금은 GPU·CPU·램을 묶어 팔아 CPU·램 몫만 따로 뺄 수 없다. 포드 안의 CPU는',
             '   호스트 값(64코어·251GB)만 보이고 우리 몫이 얼마인지 알 수 없다.',
             '· 그래서 「앱을 포드에 같이 올리면 앱 서버 비용 0」 대신 단일 장애점 위험이 생긴다.',
             '· 가르친 E4B(97.5%)와 Luna(96.4%)는 구분 안 됨 → 싼 Luna가 하루 5천 건까지 이긴다. Sol·Astra는 더 정확하지만(Astra는 유의하게 위) 비쌈.',
             '· API 금액은 생각(추론) 토큰이 빠진 값 — 실제는 최대 약 2배 가능(미측정).',
             '· API 점수는 Codex CLI로 잰 것(공정 비교 아님), 실제 고객 질문 분포는 못 잼.']
    for i, s in enumerate(notes):
        t(ax, 56, y + 80 + i * 44, s, 13.5, PAL['warn'][2])
    fig.savefig(os.path.join(OUT, 'fig13_월_총비용_v3.png'))
    plt.close(fig)


# ───────────────── 14. 캐시 공정 비교 ─────────────────
def fig14():
    H = 1550
    fig, ax = canvas(H)
    head(ax, '캐시를 켜면 공정한 비교인가?', '결론: 한쪽만 캐시를 적용한 비교는 불공정 — 같은 조건끼리 비교해야 한다')
    box(ax, 30, 160, 1020, 190, 'plain', 16, 2)
    t(ax, 56, 196, '캐시가 뭔가', 18, INK, True)
    for i, s in enumerate(['고객 질문 한 번은 「일정 목록(같은 앞부분 약 1,500토큰) + 새 질문(짧음)」으로 이루어진다.',
                           '캐시 = 앞부분을 다시 읽지 않고 이전 계산을 재사용하는 것. 같은 일정이 연달아 올 때만 맞는다.',
                           'API는 이 경우 앞부분 요금이 1/10로 줄고, 자체 GPU는 그 계산을 건너뛰어 더 빨라진다.']):
        t(ax, 56, 238 + i * 34, s, 13.5, SUB)
    t(ax, 40, 400, '트래픽 모양별로 양쪽을 나란히', 20, INK, True)
    for x, nm in ((300, '외부 API (Luna)'), (770, '자체 GPU (가르친 E4B)')):
        t(ax, x, 456, nm, 16, INK, True, 'center')
    box(ax, 30, 480, 1020, 330, 'now', 16, 2.2)
    t(ax, 56, 514, '① 같은 팀이 몇 분 안에 연달아 질문 (캐시가 맞음)', 16, PAL['now'][2], True)
    box(ax, 56, 540, 450, 240, 'plain', 12, 1.6)
    t(ax, 281, 572, '요금이 내려감', 16, INK, True, 'center')
    for i, s in enumerate(['Luna 건당 0.25원 → 0.06원', '하루 10만 건: 73.9만 → 17.2만원', '(단가 출처: 2차 자료)']):
        t(ax, 281, 612 + i * 38, s, 13.5, SUB, False, 'center')
    box(ax, 530, 540, 490, 240, 'plain', 12, 1.6)
    t(ax, 775, 572, '요금은 그대로, 처리량이 늘어남', 16, INK, True, 'center')
    for i, s in enumerate(['월 24.5만원 고정', '한 대 한계 하루 6.75만 건 → 더 늘 수 있음', '얼마나 늘지는 측정 예정(GPU 서버 A)']):
        t(ax, 775, 612 + i * 38, s, 13.5, SUB, False, 'center')
    box(ax, 30, 830, 1020, 330, 'warn', 16, 2.2)
    t(ax, 56, 864, '② 팀이 계속 바뀌거나 질문이 드묾 (캐시가 안 맞음 — 현실에 가까움)', 16, PAL['warn'][2], True)
    box(ax, 56, 890, 450, 240, 'plain', 12, 1.6)
    t(ax, 281, 922, '요금 그대로', 16, INK, True, 'center')
    for i, s in enumerate(['Luna 건당 0.25원', '하루 10만 건: 73.9만원', '캐시 보관 시간은 몇 분 수준(미확인)']):
        t(ax, 281, 962 + i * 38, s, 13.5, SUB, False, 'center')
    box(ax, 530, 890, 490, 240, 'plain', 12, 1.6)
    t(ax, 775, 922, '속도 그대로', 16, INK, True, 'center')
    for i, s in enumerate(['월 24.5만원 고정', '캐시 없이 문제당 1.15~1.25초(실측)', '한 대 하루 약 6.75만 건']):
        t(ax, 775, 962 + i * 38, s, 13.5, SUB, False, 'center')
    box(ax, 30, 1190, 1020, 340, 'gpu', 16, 2.2)
    t(ax, 56, 1226, '그래서 어떻게 비교해야 하나', 18, PAL['gpu'][2], True)
    for i, s in enumerate(['· 앞 그림(v2)의 「캐시 있음」 숫자는 API에만 할인을 준 것 → 불공정이다.', '· 옳은 짝: ①이면 양쪽 다 캐시, ②이면 양쪽 다 캐시 없음.',
                           '· GPU는 캐시가 「요금」이 아니라 「한 대가 감당하는 양」을 바꾼다. 월 요금은 같다.', '· 우리 트래픽은 팀마다 일정이 달라 ②가 기본 → 그림 v3는 캐시 없음으로 통일.',
                           '· 측정 예정: 올라마 E4B의 캐시 유무·동시 요청별 속도(GPU 서버 A 대기열에 올려 둠).']):
        t(ax, 56, 1270 + i * 44, s, 13.5, PAL['gpu'][2])
    fig.savefig(os.path.join(OUT, 'fig14_캐시_공정_비교.png'))
    plt.close(fig)


# ───────────────── 15. 모델 성능표 ─────────────────
def fig15():
    H = 1790
    fig, ax = canvas(H)
    head(ax, '모델 성능 한눈에 (정답률)', '시험지 5세트 769문제(요청 둘 유형 제외) · 모두 같은 문제로 채점')
    rows = [
        ('Astra (Codex CLI)', 99.61, 'gpu', '상용*'), ('Claude Fable·Opus (문제별)', 99.35, 'gpu', '상용*'), ('Sol (Codex CLI)', 98.83, 'gpu', '상용*'),
        ('가르친 E4B (4B 활성)', 97.53, 'now', '가르침'), ('Qwen3.8 27B', 97.41, 'done', '로컬'),
        ('Decider 31B', 97.27, 'done', '결정'), ('규칙→OpenJev 26B', 96.75, 'bar', '조합'), ('OpenJev 26B', 96.62, 'done', '결정'),
        ('Luna (Codex CLI)', 96.36, 'gpu', '상용*'), ('Ens3 다수결', 95.77, 'bar', '조합'), ('Gemma 26B-A4B (18GB)', 95.19, 'done', '로컬'), ('Decider-12B 8비트', 94.80, 'done', '결정'),
        ('Winnow-12B', 94.0, 'done', '결정'), ('규칙→E4B (L1)', 93.5, 'bar', '조합'), ('Gemma 12B', 91.42, 'done', '로컬'),
        ('Gemma E4B QAT', 91.16, 'done', '로컬'), ('E4B 기준선(HF 4비트)', 89.47, 'done', '전'),
    ]
    y = 170
    sc = 36
    for nm, v, k, tag in rows:
        kk = 'now' if k == 'now' else ('gpu' if k == 'gpu' else ('warn' if k == 'bar' else 'done'))
        t(ax, 40, y + 18, nm, 14.5, INK, k == 'now')
        box(ax, 340, y, (v - 85) * sc, 36, kk, 6, 1.8)
        t(ax, 340 + (v - 85) * sc + 10, y + 18, f'{v:.1f}%', 15, INK, True)
        t(ax, 1040, y + 18, tag, 12, SUB, False, 'right')
        y += 48
    t(ax, 40, y + 18, '막대 시작 = 85%. 보라(*) = 상용(공정 비교 아님: Codex CLI·Claude 문제별), 초록 = 가르친 모델, 노랑 = 조합, 회색 = 단일 모델', 12, SUB)
    y += 60
    t(ax, 40, y + 20, '이 표에 못 넣은 것 (다른 문제 수)', 18, INK, True)
    y += 54
    box(ax, 30, y, 1020, 190, 'plain', 14, 1.8)
    for i, s in enumerate(['· 가르친 E4B와 짝비교: Astra·Claude는 유의하게 위(p=0.0004·0.003), Sol은 경계(p=0.076), Luna는 구분 안 됨(p=0.22)',
                           '· Clef Flash 9B 71.0% (769) · Clef 27B(층 40개만 GPU) mix11 91.3% — 이 과제에는 맞지 않음',
                           '· Granite 4.2 30B 80% · 8B 55% · 3B 32% (mix8~11) — 맞지 않음', '· Spark 1.3(OpenCode 무료): mix10 요청 둘 제외 151/151 — 점수는 참고만(에이전트 지시문 포함)']):
        t(ax, 50, y + 36 + i * 38, s, 12.5, SUB)
    y += 220
    box(ax, 30, y, 1020, 330, 'warn', 16, 2.2)
    t(ax, 56, y + 34, '읽을 때 주의', 18, PAL['warn'][2], True)
    for i, s in enumerate(['· 1~2문제 차이는 구분되지 않는다(짝비교 검정). 가르친 E4B는 26B보다 위(p=0.01), Claude보다 아래(p=0.003).',
                           '· 가르친 E4B는 학습 1회·평가 1회, 학습 자료와 mix12의 저자가 같아(Claude) mix12에서 이득이 큼.',
                           '· 결정 모델(31B·OpenJev·Decider)의 우위는 Codex가 쓴 세트에서 더 컸다. Qwen3.8 우위는 작성자가 바뀌어도 유지.', '· Claude 문제별 점수는 생각을 끈 값. 묶음 풀이 점수(99.9%)는 공정 비교가 아니어서 뺐다.',
                           '· 실제 고객 질문은 아직 못 잼 — 합성·작성자별 질문으로만 쟀다.']):
        t(ax, 56, y + 76 + i * 46, s, 12.8, PAL['warn'][2])
    fig.savefig(os.path.join(OUT, 'fig15_모델_성능표.png'))
    plt.close(fig)


# ───────────────── 16a. 결론·추천 조합 ─────────────────
def fig16a():
    H = 1490
    fig, ax = canvas(H)
    head(ax, '지금까지의 결론과 추천 조합', '9월 29일~10월 6일, 모델 73종·조합·가르치기·API까지 시험한 결과')
    t(ax, 40, 190, '핵심 결론 6가지', 20, INK, True)
    items = [('가르치기 하나만 26B를 넘겼다', '활성 4B E4B + LoRA 97.5% vs 26B-A4B 95.2% (p=0.01) — 용량은 1/3'),
             ('나머지 요령은 26B와 구분 안 됨', '규칙·임베딩 앞단·앙상블·conformal·생각 켜기·프롬프트 최적화 → 이득 없거나 작음'),
             ('상용 모델이 더 높다 — 단 Luna는 비슷', 'Astra 99.6%·Claude 99.35%(유의하게 위) · Sol 98.8%(경계) ↔ 가르친 E4B 97.5% · Luna 96.4%(서로 구분 안 됨)'),
             ('결정 모델(Jev류)은 확률을 준다', '96.6~97.3%, 위임·앙상블 재료. 단 선택지 상한(16~26)·작성자 편향·한국어 미확인'),
             ('비용은 규모가 가른다', '하루 5천 건까지 Luna API가 가장 쌈(앱 서버 포함 월 7만원 안팎), 하루 약 3만 건부터 자체 GPU 의미'),
             ('아직 모르는 것', '실제 고객 질문 분포 · API 한도·응답 시간·약관 · 가르친 모델 반복 편차')]
    y = 226
    for i, (a, b) in enumerate(items):
        box(ax, 30, y, 1020, 96, 'plain', 12, 1.6)
        t(ax, 50, y + 30, f'{i + 1}. {a}', 16.5, INK, True)
        t(ax, 50, y + 68, b, 12.8, SUB)
        y += 108
    t(ax, 40, y + 28, '추천 조합 (우선순위)', 20, INK, True)
    y += 66
    recs = [('now', '① 출시 초기: Luna API + 규칙 되확인 (정확도가 더 필요하면 Sol·Astra)', '모델은 「몇 번 항목」만 고르고 문장은 DB 값 틀로만 만든다. 앱 서버 AWS 3만원 + Luna API. 99%가 필요하면 Sol·Astra.'),
            ('gpu', '② 규모↑ · 일정이 밖으로 나가는 부담↓: 가르친 E4B', 'RunPod GPU 한 대(24.5만원): 문제당 약 1.3~1.7초, 하루 최대 6.75만 건(이론). 학습 자료는 Claude가 만들고 독립 검증.'),
            ('warn', '③ 표본 검수: Claude·Astra로 일부만 재확인', '틀린 답이 나온 것만 모아 학습 자료에 되먹임(데이터 늘리기).'),
            ('bad', '④ 버리는 것: 앙상블·conformal·생각 켜기·Clef·Granite', '복잡도만 늘고 이득이 없거나 맞지 않았다.')]
    for tone, a, b in recs:
        box(ax, 30, y, 1020, 118, tone, 14, 2)
        t(ax, 50, y + 34, a, 16.5, PAL[tone][2], True)
        t(ax, 50, y + 78, b, 12.5, PAL[tone][2])
        y += 130
    fig.savefig(os.path.join(OUT, 'fig16a_결론_추천조합.png'))
    plt.close(fig)


# ───────────────── 16b. 장단점 ─────────────────
def fig16b():
    H = 1360
    fig, ax = canvas(H)
    head(ax, '방식별 장단점', '정답률은 769문제(요청 둘 제외) 기준 · 비용은 앱 서버 제외 분류 처리만')
    rows = [('외부 API\n(Luna·Sol·Astra)', '96.4~99.6%*', ['구축 0, 가장 높은 정확도', 'Luna 건당 0.25원, 0건이면 0원', '규모 커져도 대수 걱정 없음'], ['일정·이름이 외부 사업자로 나감(약관 고지)', '한도·응답 시간·가격 변동 미확인', '생각 토큰 요금 미반영(최대 2배)'], 'now'),
            ('가르친 E4B\n+ RunPod GPU', '97.5%', ['26B 이상 성능, 용량 1/3', '데이터가 안 나감, 문제당 약 1.3~1.7초', '규모 커지면 건당 단가가 내려감'], ['월 24.5만원 고정(0건이어도)', '학습 자료 제작·검증·재학습 필요', 'GPU 한 대면 단일 장애점'], 'gpu'),
            ('Gemma 26B-A4B\n직접', '95.2%', ['가르치지 않고 바로 씀', '용량 18GB(활성 3.8B)'], ['가르친 E4B보다 낮고 무거움', 'GPU 24GB급 권장'], 'done'),
            ('결정 모델\n(OpenJev·Decider)', '96.6~97.3%', ['한 번 계산에 확률 → 위임·앙상블 재료', '「해당 없음」 확률 제공'], ['선택지 상한 16~26 → 묶음 대회 필요', 'Codex 세트에서 우위 큼(편향)', '유료 호출·한국어 미확인'], 'done'),
            ('소형 조합\n(규칙+임베딩+E4B)', '약 93~95%', ['용량 약 7GB, LLM 호출 44%만', '엉뚱한 답이 적음'], ['설계 복잡(문턱·앞단 학습)', '26B 이상은 못 넘음'], 'warn'),
            ('앙상블·conformal\n·생각 켜기', '26B와 구분 안 됨', ['이론적 보장(conformal)', '일부 세트에서 일시 우위'], ['재현 안 됨, 비용·지연만 증가', '생각 켜기: 9~22배 느림, 이득 -4~+5'], 'bad')]
    y = 170
    for nm, acc, pro, con, tone in rows:
        h = 60 + max(len(pro), len(con)) * 34 + 28
        box(ax, 30, y, 1020, h, 'plain', 14, 1.8)
        box(ax, 46, y + 14, 230, h - 28, tone, 10, 2)
        t(ax, 161, y + h * 0.40, nm, 15.5, PAL[tone][2], True, 'center')
        t(ax, 161, y + h * 0.75, acc, 13.5, PAL[tone][2], True, 'center')
        t(ax, 296, y + 32, '장점', 13.5, PAL['now'][2], True)
        for i, s in enumerate(pro):
            t(ax, 296, y + 66 + i * 34, '· ' + s, 12.6, INK)
        t(ax, 690, y + 32, '단점', 13.5, PAL['bad'][2], True)
        for i, s in enumerate(con):
            t(ax, 690, y + 66 + i * 34, '· ' + s, 12.2, INK)
        y += h + 14
    t(ax, 40, y + 14, '* API 정확도는 769문제 전체, Codex CLI로 잼 — 공정 비교 아님', 12, SUB)
    fig.savefig(os.path.join(OUT, 'fig16b_방식별_장단점.png'))
    plt.close(fig)


# ───────────────── 17a. 진행 중·앞으로 ─────────────────
def fig17a():
    H = 1660
    fig, ax = canvas(H)
    head(ax, '지금 진행 중인 일과 앞으로 할 일', '10월 6일 오전 기준 · 두 GPU 서버가 비지 않도록 다음 일감을 미리 걸어 둠')
    t(ax, 40, 190, '지금 돌아가는 것', 20, INK, True)
    now = [('GPU 서버 A (RTX 2000 Ada)', 'gpu', ['「둘 다 찾기」 Gemma 12B 5세트 끝 → 26B 진행', '다음: OpenJev 회전 9회 → 캐시·동시 요청 측정']),
           ('GPU 서버 B (RTX A4000)', 'gpu', ['Clef 27B 5세트: mix11 끝(91.3%), mix10 진행', '다음: 가르친 E2B(더 작은 학생) → E4B 시드 반복']),
           ('이 PC', 'now', ['Spark 1.3(OpenCode 무료) 나머지 세트 진행', '(Luna·Sol·Astra 시험은 5세트 모두 끝)'])]
    y = 226
    for nm, tone, ls in now:
        box(ax, 30, y, 1020, 150, tone, 14, 2)
        t(ax, 50, y + 34, nm, 17, PAL[tone][2], True)
        for i, s in enumerate(ls):
            t(ax, 50, y + 76 + i * 34, s, 13.5, PAL[tone][2])
        y += 162
    t(ax, 40, y + 24, '끝난 큰 일', 20, INK, True)
    y += 60
    done = ['시험지 835문제(작성자 Codex·Claude) · 모델 73종 비교 · 공정성 표시와 CSV·엑셀', '가르치기 파일럿: 연습문제 1,760개 → 독립 검증 100% → 학습·평가, 기준 통과(+8.1%p)', 'Luna·Sol·Astra 문제별 시험(769문제 전체) · CPU 속도 실측(4B·12B·MoE) · Clef 결과',
            '비용 조사: RunPod·AWS 공식 가격·Colab 약관 · 비용 v3(앱 서버 포함)']
    box(ax, 30, y, 1020, 190, 'done', 14, 1.8)
    for i, s in enumerate(done):
        t(ax, 50, y + 34 + i * 40, '· ' + s, 13, INK)
    y += 218
    t(ax, 40, y + 14, '앞으로 할 일', 20, INK, True)
    y += 50
    todo = [('1', '가르친 모델 반복 편차·더 작은 학생', 'E4B 시드 반복, E2B 학습·평가 → CPU 배포(오라클 ARM·AWS Graviton) 후보 확인'), ('2', '처리량·캐시 측정', '캐시 유무·동시 요청별 속도 → 한 대 한계와 비용 비교 보정'),
            ('3', 'API 비교 마무리', '원시 API 호출로 재확인 · 한도·응답 시간·생각 토큰 비용 확인'), ('4', '실제 고객 질문 재평가', '로그가 쌓이면 합성 질문과의 차이 측정, 틀린 것을 학습 자료에 되먹임'),
            ('5', '배포 결정 자료 확정', '앱 서버 + 분류 처리(API 또는 GPU) 구성과 월 예산, 약관 고지 문구')]
    for n, a, b in todo:
        box(ax, 30, y, 1020, 104, 'plain', 12, 1.6)
        t(ax, 56, y + 52, n, 24, SUB, True, 'center')
        t(ax, 100, y + 32, a, 15.5, INK, True)
        t(ax, 100, y + 72, b, 12.3, SUB)
        y += 114
    fig.savefig(os.path.join(OUT, 'fig17a_진행_앞으로.png'))
    plt.close(fig)


# ───────────────── 17b. 검토한 방법과 결과 ─────────────────
def fig17b():
    H = 2160
    fig, ax = canvas(H)
    head(ax, '검토한 소규모 모델 최적화 방법과 결과', '「26B 이상 성능을 더 작은 모델로」가 목표 — 이득이 있었는지 방법별로')
    rows = [
        ('가르치기(QLoRA 증류)', '★ 이득', 'now', 'E4B 89.5→97.5% (+8.1%p, p=6e-14), 26B(95.2%)보다 위. 자료는 Claude가 만들고 독립 검증'),
        ('규칙 → LLM 앞단', '이득 작음', 'warn', '규칙→E4B 93.5% (직접 91.2%+2.3%p), 규칙→26B는 26B와 같음'),
        ('임베딩 앞단 + E4B (소형 조합, 7GB)', '26B와 동급', 'warn', '독립 303문제 95.7% vs 26B 94.7%(구분 안 됨), 호출 LLM 44%만'),
        ('재평가기·짚기 LoRA', '약한 기반만', 'warn', 'Reranker 0.6B: 12B 호출 45→14%. Qwen3.5-2B 직접 +13~24문제지만 E4B 미만. Gemma E2B(HF) -16'),
        ('프롬프트 바꾸기', '모델마다 다름', 'warn', '형식 지시: 가장 작은 모델만 +13. 정의 한 줄: 모델·유형마다 다름(Luna +18). GEPA 최적화는 효과 없음'),
        ('후보 힌트 5개 실기', '작은 이득', 'warn', '힌트 +6(E4B) · 5개만 싣기는 -22로 해로움'),
        ('앙상블 E1·D1·Ens3', '재현 안 됨', 'bad', 'mix11 우위가 mix12에서 사라짐. 26B·Qwen3.8과 구분 안 됨(p>0.2)'),
        ('conformal 위임', '구분 안 됨', 'bad', '같은 넘김 비율의 확신 문턱과 동일(+0~1, p=1). 커버리지 보장도 목표 미달'),
        ('순환 회전 평균(R4)', '근접', 'warn', 'Decider-12B +10/659, p=0.064(기준 p<0.05 미달, 사후 변형은 p=0.031)'),
        ('비평·승격(V4·V12·L4)', '엉뚱한 답↓', 'warn', '엉뚱한 답 22→16~18, 정답은 -3~+4. 문턱이 불안정'),
        ('생각 켜기', '해롭거나 느림', 'bad', 'Qwen3.8 +5/323(9배 느림), E4B -4(22배 느림)'),
        ('결정 모델(Jev류)', '높지만 한계', 'warn', 'OpenJev 96.6 · Decider31B 97.3%. 선택지 상한·작성자 편향·유료'),
        ('CPU 배포(GPU 없이)', '지금은 불가', 'bad', '4코어: 4B 첫 질문 154초 · 12B 435초 · 26B MoE 456초 → 더 작은 학생(E2B) 시험 대기'),
        ('Clef·Granite·Spark', '맞지 않음/참고', 'bad', 'Clef Flash 71% · Clef 27B(mix11) 91.3% · Granite 30B 80% · Spark 1.3은 에이전트 지시문 포함이라 참고만'),
    ]
    y = 170
    for nm, verdict, tone, detail in rows:
        box(ax, 30, y, 1020, 128, 'plain', 12, 1.6)
        t(ax, 46, y + 32, nm, 15.5, INK, True)
        box(ax, 800, y + 14, 230, 38, tone, 8, 2)
        t(ax, 915, y + 33, verdict, 14, PAL[tone][2], True, 'center')
        # 상세 문장을 두 줄로 나눠 쓴다
        words = detail.split(' ')
        lines, cur = [], ''
        for w in words:
            if len(cur) + len(w) > 60:
                lines.append(cur); cur = w
            else:
                cur = (cur + ' ' + w).strip()
        lines.append(cur)
        for i, s in enumerate(lines[:3]):
            t(ax, 46, y + 70 + i * 26, s, 12.6, SUB)
        y += 140
    fig.savefig(os.path.join(OUT, 'fig17b_방법과_결과.png'))
    plt.close(fig)


if __name__ == '__main__':
    fig13(); fig14(); fig15(); fig16a(); fig16b(); fig17a(); fig17b()
    print('done2')
