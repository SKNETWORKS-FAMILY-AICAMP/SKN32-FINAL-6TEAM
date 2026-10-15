# 알림 번역 보호 장치의 「금액 단위」 점검 — 고친 뒤 실제 모델로 다시 잰다 (2026-10-15, 6주차 발표 점검 후속).
#  앞판(translate_guard_live.py, 2026-10-06)은 실제 모델 120호출에서 일본어 「35,000원」→「35,000円」 1건이 숫자 대조를 통과한 것을 찾았고,
#  이후 translate.currency_problem 을 넣었다(e3dca265). 그 뒤 실제 모델 재측정이 없었다. 이 판이 그것을 한다.
#  앞판과 다른 점
#   - 모델 = 운영 설정의 모델 그대로(ACOP_OLLAMA_MODEL, 지금 x600 서버 = tripilot-pointer:e4b-ft). 앞판은 gemma4:12b 였다.
#   - 부르는 방법 = 제품 코드 그대로(OllamaChat · make_translator · SYSTEM). 운영과 같은 문맥 길이(ollama_num_ctx)와 keep_alive.
#   - 금액이 든 알림을 늘렸다(앞판 9종 → 이 판 아래 AMOUNT_EXTRA 포함) — 단위 변조는 금액이 있어야만 일어난다.
#   - 언어 = 영어 · 일본어 · 중국어(간체) · 중국어(번체). 번체는 앞판에 없었다.
#   - 독립 검사에 「금액 단위」를 더했다. 제품의 currency_problem 과 다른 눈(숫자 옆이 아니라 번역 전체에서 다른 통화 표기를 찾는다).
#   - 같은 모델 출력을 세 눈으로 센다: ①숫자 대조만(앞판 이전의 보호) ②숫자 + 금액 단위(지금 제품) ③독립 검사(사람이 읽는 눈에 가깝게).
#  제품 코드·DB 는 건드리지 않는다. 모델은 GPU 서버의 Ollama(SSH 포트포워딩) — x600 서버에는 시험 부하를 걸지 않는다.
#  재료는 제품 알림 문체를 따라 내가 쓴 합성 한국어 알림이다(실제 고객 알림 아님). 온도 0 이라 같은 입력은 같은 출력 — 반복 편차는 재지 않는다.
# 사용: OLLAMA_URL=http://127.0.0.1:21435 OLLAMA_MODEL=tripilot-pointer:e4b-ft python translate_guard_live_v2.py
import collections
import concurrent.futures as cf
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'final_project_cs'))
sys.stdout.reconfigure(encoding='utf-8')
from app.infrastructure.notify import translate as T  # noqa: E402
from app.infrastructure.ollama_chat import OllamaChat  # noqa: E402

BASE = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:21435')
MODEL = os.environ.get('OLLAMA_MODEL', 'tripilot-pointer:e4b-ft')
NUM_CTX = int(os.environ.get('OLLAMA_NUM_CTX', '8192'))
LANGS = ['en', 'ja', 'zh-CN', 'zh-TW']
OUT = os.environ.get('OUT', os.path.join(HERE, 'results', 'translate_guard_live_20261015.json'))

# 앞판의 알림 40개를 그대로 쓴다(같은 재료로 견주기 위해). 앞판을 import 하면 모델 호출 코드까지 끌려오므로 파일에서 알림 목록만 읽는다.
_src = open(os.path.join(HERE, 'translate_guard_live.py'), encoding='utf-8').read()
_m = re.search(r'NOTICES = \[(.*?)\n\]\nassert', _src, re.S)
NOTICES_V1 = eval('[' + _m.group(1) + ']')  # noqa: S307 — 우리 저장소의 문자열 목록
assert len(NOTICES_V1) == 40, len(NOTICES_V1)

#: 금액이 든 알림을 더한다(단위 변조가 일어날 수 있는 재료). 문구는 제품 알림 문체를 따라 쓴 합성이다.
AMOUNT_EXTRA = [
    '[변경] 경복궁 야간 개장 입장료는 3,000원이에요. 19:00 입장이 가장 좋아요. 일정 버전 2.',
    '[변경] 점심을 12:30 한식당으로 옮겼어요. 1인 평균 12,000원이에요.',
    '[알림] 택시로 가면 약 18,500원이에요. 지하철은 1,550원이고 12분 더 걸려요.',
    '[변경] 한복 대여 25,000원 예약이 17:00으로 확정됐어요. 일정 버전 8.',
    '[재생] 오늘 예산은 80,000원이에요. 지금까지 31,200원을 썼고 남은 일정은 세 곳이에요.',
    '[알림] 남산케이블카 왕복 14,000원이에요. 마지막 운행은 22:30이에요.',
    '[변경] 숙소를 바꾸면 1박 95,000원이에요. 체크인은 15:00부터예요.',
    '[알림] 공항철도 직통 11,000원, 일반열차 4,750원이에요. 22:10 열차가 막차예요.',
    '[변경] 교통카드 충전 20,000원이 필요해요. 편의점에서 09:30 전에 충전하세요.',
    '[변경] 한강 공원 자전거 대여는 시간당 3,000원이에요. 2시간 이용하면 6,000원이에요.',
    '[알림] 시장 먹거리 4곳을 돌면 약 28,000원이에요. 대기는 15분이에요.',
    '[지연] 택시 기본요금이 4,800원으로 올라 도착이 12:55로 늦어져요.',
    '[변경] 롯데월드 어드벤처 입장권은 성인 62,000원, 어린이 47,000원이에요. 일정 버전 5.',
    '[재생] 쇼핑 일정이에요. 11:30 명동 도착, 예산 150,000원 중 먼저 50,000원을 써요.',
    '[알림] 미술관 특별전은 1인 18,000원이에요. 16:00 이후 입장은 15,000원이에요.',
    '[변경] 야경 크루즈를 취소하면 수수료 10,000원이 있어요. 20:00 이전에 알려 주세요.',
    '[알림] 환승 할인으로 600원 아낄 수 있어요. 10:20 버스로 갈아타세요.',
    '[변경] 호텔 조식은 1인 22,000원이에요. 07:00부터 10:00까지예요.',
    '[알림] 박물관 오디오 가이드는 5,000원이에요. 입구에서 14:00까지 빌릴 수 있어요.',
    '[변경] 저녁 코스 요리 1인 48,000원으로 18:40에 예약했어요. 예약번호 CD4821.',
]
NOTICES = NOTICES_V1 + AMOUNT_EXTRA

TIME = re.compile(r'\d{1,2}:\d{2}')
MONEY = re.compile(r'\d{1,3}(?:,\d{3})+')
TAG = re.compile(r'\[[^\]\s]{1,8}\]')
AMOUNT_SRC = re.compile(r'\d[\d,.]*\s*원')
# 독립 검사용 — 제품 currency_problem 과 정규식·방식을 따로 쓴다(숫자 옆이 아니라 번역 전체에서 찾는다)
WON_ANY = re.compile(r'원|\bwon\b|\bKRW\b|₩|ウォン|韩元|韓元|韩币|韓幣|圆\(韩|韓圓|韩圆', re.I)
FOREIGN_ANY = re.compile(r'円|엔|\byen\b|\bJPY\b|¥|人民币|人民幣|\bRMB\b|\bCNY\b|\bTWD\b|NT\$|新台幣|新台币|\$|\bUSD\b|\bdollars?\b|€|\bEUR\b|\beuros?\b|块|塊|(?<![韩韓])元|圆|圓', re.I)


def unit_problem(src, out):
    """독립 검사 — 원문에 「숫자+원」이 있는데 번역이 ①원 표기를 잃었거나 ②원문에 없던 다른 통화 표기를 쓰면 문제."""
    if not AMOUNT_SRC.search(src):
        return None
    if not WON_ANY.search(out):
        return 'won_mark_lost'
    foreign = set(m.group(0) for m in FOREIGN_ANY.finditer(out)) - set(m.group(0) for m in FOREIGN_ANY.finditer(src))
    # 중국어에서 「元」은 「韩元」의 일부일 수 있다 — 韩元 앞의 元은 위 정규식이 뺐다. 「块」「圆」은 중국어 구어 통화어라 센다.
    if foreign:
        return 'foreign_currency:' + ','.join(sorted(foreign)[:3])
    return None


def digit_guard_only(src, out):
    """숫자 대조만(단위 대조 이전의 제품 보호) — 통과하면 True."""
    o, g = collections.Counter(T._DIGITS.findall(src)), collections.Counter(T._DIGITS.findall(out))
    return not (list((o - g).elements()) or set(g) - set(o))


def one(job):
    i, text, lang = job
    chat = OllamaChat(base_url=BASE, model=MODEL, timeout=180.0, keep_alive='30m', num_ctx=NUM_CTX)
    rec = {'i': i, 'lang': lang, 'src': text, 'raw': '', 'status': '', 'ms': 0.0, 'has_amount': bool(AMOUNT_SRC.search(text))}
    t0 = time.perf_counter()
    try:
        rec['raw'] = chat.text(T.SYSTEM, f'Target language: {lang}\n\n{text}')
    except Exception as e:  # noqa: BLE001
        rec['status'] = 'error'
        rec['why'] = repr(e)[:160]
    rec['ms'] = (time.perf_counter() - t0) * 1000
    if rec['raw']:
        out = rec['raw']
        rec['digit_ok'] = digit_guard_only(text, out)
        rec['product_problem'] = T.currency_problem(text, out) if rec['digit_ok'] else None
        rec['product_pass'] = rec['digit_ok'] and rec['product_problem'] is None
        rec['unit'] = unit_problem(text, out)
        indep = []
        for name, rx in (('time', TIME), ('money', MONEY)):
            if collections.Counter(rx.findall(text)) != collections.Counter(rx.findall(out)):
                indep.append(name)
        for tag in TAG.findall(text):
            if tag not in out:
                indep.append('tag')
                break
        if rec['unit']:
            indep.append('unit')
        rec['indep'] = indep
        rec['status'] = 'passed' if rec['product_pass'] else 'guard_rejected'
    return rec


def main():
    jobs = [(i, t, lang) for i, t in enumerate(NOTICES) for lang in LANGS]
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=1) as ex:        # 한 번에 하나 — GPU 를 나눠 쓰지 않는다
        rows = list(ex.map(one, jobs))
    ok = [r for r in rows if r['status'] != 'error']
    amt = [r for r in ok if r['has_amount']]

    def count(rs, pred):
        return sum(1 for r in rs if pred(r))
    meta = {
        '날짜': time.strftime('%Y-%m-%d %H:%M'), '모델': MODEL, '문맥 길이': NUM_CTX, '호출 수': len(rows), '알림 수': len(NOTICES), '언어': LANGS, '반복': 1,
        '오류 호출': len(rows) - len(ok), '걸린 시간(초)': round(time.time() - t0),
        '금액이 든 호출(분모)': len(amt),
        '금액 호출 중 번역이 숫자 대조만으로는 통과': count(amt, lambda r: r['digit_ok']),
        '금액 호출 중 단위가 어긋난 번역(독립 검사)': count(amt, lambda r: r['unit']),
        '그중 숫자 대조만으로는 통과(=옛 보호가 놓침)': count(amt, lambda r: r['unit'] and r['digit_ok']),
        '그중 지금 제품 보호가 거름': count(amt, lambda r: r['unit'] and r['digit_ok'] and not r['product_pass']),
        '그중 지금 제품 보호도 통과(=새어 나감)': count(amt, lambda r: r['unit'] and r['product_pass']),
        '제품 보호가 거른 것 중 독립 검사로는 멀쩡(오탐 후보)': count(ok, lambda r: r['digit_ok'] and not r['product_pass'] and not r['unit']),
        '전체 호출 중 제품 보호 통과': count(ok, lambda r: r['product_pass']),
        '통과했는데 시각·쉼표 금액·태그가 어긋남(새어 나감)': count(ok, lambda r: r['product_pass'] and any(x in ('time', 'money', 'tag') for x in r['indep'])),
        '언어별 단위 어긋남/금액 호출': {lang: f"{count([r for r in amt if r['lang'] == lang], lambda r: r['unit'])}/{len([r for r in amt if r['lang'] == lang])}" for lang in LANGS},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'meta': meta, 'rows': rows}, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    for r in rows:
        if r.get('unit'):
            print('단위 어긋남 ·', r['lang'], r['unit'], '| 제품통과', r['product_pass'], '|', r['src'][:50], '→', r['raw'][:100].replace('\n', ' '))


if __name__ == '__main__':
    main()
