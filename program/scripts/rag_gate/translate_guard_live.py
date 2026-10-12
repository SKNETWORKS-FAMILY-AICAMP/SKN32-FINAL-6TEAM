# 알림 번역의 「숫자 보호」를 실제 모델 호출로 잰다 — 제품 코드(`app/infrastructure/notify/translate.py` 의 make_translator · OllamaChat)를 그대로 부르고,
#  모델이 원문의 시각·금액·버전 숫자를 바꾼 번역을 몇 건 냈고(걸러야 할 건수), 보호 장치가 몇 건 걸렀고, 몇 건이 새어 나갔는지(통과했는데 독립 검사로 어긋난 건수) 센다.
#  재료: 제품 알림 문체를 따라 내가 쓴 한국어 알림 40개(시각·금액·버전·대괄호 태그가 들어 있다 — 합성) × 영어·일본어·중국어(간체) = 120건.
#  독립 검사(제품 보호 장치와 다른 눈): ①「HH:MM」 시각 문자열이 횟수까지 그대로 ②쉼표 금액(5,000)이 횟수까지 그대로 ③대괄호 태그([재생] 등)가 그대로 남았는지.
#  제품 코드·DB 는 건드리지 않는다. Ollama 는 x600 서버의 것(SSH 포트포워딩 127.0.0.1:11434) — 임베딩에 쓰던 그 통로다. 모델 = 제품 기본 gemma4:12b.
# 사용: python translate_guard_live.py   → results/translate_guard_live.json
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
from app.infrastructure.notify.translate import TranslationRejected, make_translator  # noqa: E402
from app.infrastructure.ollama_chat import OllamaChat  # noqa: E402

BASE = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
MODEL = os.environ.get('OLLAMA_MODEL', 'gemma4:12b')
LANGS = ['en', 'ja', 'zh-CN']

NOTICES = [
    '[변경] 내일 14:10 경복궁 입장이 비 예보로 어려워 보여요. 15:30 국립중앙박물관(입장료 5,000원)으로 바꿨어요. 일정 버전 4.',
    '[재생] 오늘 09:00에 시작해요. 첫 일정은 09:40 남산서울타워이고, 숙소에서 지하철로 28분 걸려요.',
    '[알림] 18:20 출발 전 확인: 광장시장 마약김밥 줄이 길어 대기 40분이 예상돼요. 19:00 저녁 예약은 그대로예요.',
    '[변경] 3번 일정이 17:30에서 16:45로 당겨졌어요. 이동 시간 35분을 반영했어요. 일정 버전 7.',
    '[지연] 지하철 2호선이 12분 지연되고 있어요. 11:05 도착 예정이 11:17로 늦어져요.',
    '[재생] 2일차가 시작돼요. 08:30 호텔 출발, 10:00 북촌한옥마을 도착, 점심은 12:30 예정이에요.',
    '[변경] 롯데월드 자유이용권 62,000원 예약이 확정됐어요. 입장은 10:00부터 가능해요.',
    '[알림] 21:00에 닫는 가게라 라스트오더는 20:30이에요. 20:00 전에 도착하는 걸 권해요.',
    '[변경] 한강 유람선이 강풍으로 취소돼 19:30 N서울타워 야경으로 바꿨어요. 입장권은 16,000원이에요. 일정 버전 5.',
    '[재생] 3일차 일정이에요. 09:15 DDP 전시, 13:00 이태원 점심, 16:20 한남동 카페 순서예요.',
    '[알림] 비가 14:00부터 17:00까지 올 예정이에요. 실외 일정 2개를 실내로 옮길 수 있어요.',
    '[변경] 택시 요금이 예상보다 높아 지하철로 바꿨어요. 22분 더 걸리지만 2,750원 아낄 수 있어요.',
    '[지연] 버스 402번이 8분 늦게 와요. 12:40 도착 예정이 12:48이 돼요. 다음 일정까지 여유는 15분이에요.',
    '[재생] 오늘은 4명 일정이에요. 10:30 창덕궁 후원 관람(1인 8,000원)이 예약돼 있어요.',
    '[변경] 5일차 11:00 일정이 휴관이라 12:15 서울식물원으로 옮겼어요. 일정 버전 9.',
    '[알림] 공항철도 막차는 23:48이에요. 22:30 전에는 숙소로 출발하는 걸 권해요.',
    '[변경] 점심 12:00 예약이 만석이라 12:45 근처 식당으로 바꿨어요. 대기 없이 앉을 수 있어요.',
    '[재생] 마지막 날이에요. 07:50 체크아웃, 09:20 인천공항 도착을 권해요. 비행기는 11:55 출발이에요.',
    '[알림] 오늘 미세먼지가 나쁨(78)이에요. 야외 2시간 일정은 짧게 줄이는 걸 권해요.',
    '[변경] 4번 일정 이동 시간이 18분에서 31분으로 늘었어요. 도착은 15:12에서 15:25가 돼요. 일정 버전 12.',
    '[재생] 6일차 아침 08:45이에요. 오늘은 3곳을 돌고 18:00에 저녁이 예정돼 있어요.',
    '[변경] 쇼핑 일정이 11:30에서 13:10으로 미뤄졌어요. 명동 매장 영업이 10:30에 시작해요.',
    '[알림] 경복궁 수문장 교대식은 10:00과 14:00에 있어요. 지금 일정은 13:40 도착이라 맞아요.',
    '[지연] 항공편이 25분 늦게 도착해요. 14:05 착륙이 14:30이 돼요. 택시 예약을 15:10으로 옮겼어요.',
    '[변경] 인사동 쌈지길 방문은 30분 줄여 45분으로 했어요. 다음 일정은 14:20 그대로예요.',
    '[재생] 오늘 일정 5개 중 첫 번째는 09:30 서울숲이에요. 날씨는 맑고 최고 24도예요.',
    '[알림] 예약번호 AB7392 의 입장은 15:00까지 가능해요. 현재 이동 시간이 42분이라 14:10 출발이 필요해요.',
    '[변경] 숙소 근처 식당 3곳 중 평점 4.6점 가게로 19:20 저녁을 잡았어요. 1인 평균 14,000원이에요.',
    '[재생] 2일차 마지막 일정은 20:15 홍대 거리 산책이에요. 23:00 전에 숙소로 돌아와요.',
    '[변경] 에버랜드 대신 서울랜드로 바꿨어요. 이동 시간은 1시간 10분, 입장료는 성인 54,000원이에요. 일정 버전 3.',
    '[알림] 지하철 5호선 광화문역 출구 4번이 공사로 막혀요. 도보 6분 더 걸리고 10:48 도착이 10:54가 돼요.',
    '[지연] 택시 호출이 17분 걸려요. 16:10 출발이 16:27이 돼요.',
    '[변경] 3일차 점심이 13:00에서 12:20으로 당겨졌어요. 오후 일정 시작은 14:00 그대로예요.',
    '[재생] 오늘 일정은 6시간이에요. 10:00 시작, 16:00 종료 예정이고 이동은 총 1시간 25분이에요.',
    '[알림] 롯데타워 전망대 야경 시간은 19:10 입장이 가장 좋아요. 현재 예약은 19:30이라 20분 늦어요.',
    '[변경] 우천으로 야외 일정 2개를 취소하고 13:30 코엑스 아쿠아리움(성인 35,000원)으로 바꿨어요. 일정 버전 6.',
    '[재생] 4일차 첫 일정은 09:00 광화문 광장이에요. 이후 11:20 서촌, 13:10 점심이에요.',
    '[알림] 마지막 지하철까지 1시간 5분 남았어요. 지금 22:40에 출발하면 23:15 도착이에요.',
    '[변경] 쇼핑 예산 120,000원 중 이미 78,500원을 썼어요. 남은 일정은 두 곳이에요.',
    '[지연] 공연 입장이 15분 늦어져 19:45 시작이에요. 저녁 식사를 18:15로 앞당겼어요.',
]
assert len(NOTICES) == 40, len(NOTICES)

TIME = re.compile(r'\d{1,2}:\d{2}')
MONEY = re.compile(r'\d{1,3}(?:,\d{3})+')
TAG = re.compile(r'\[[^\]\s]{1,8}\]')


class Spy:
    """Ollama 호출을 감싸 원문 번역(보호 장치 전)을 따로 기록한다."""

    def __init__(self, chat):
        self.chat = chat
        self.last = ''
        self.err = None

    def text(self, system, user):
        out = self.chat.text(system, user)
        self.last = out
        return out


def one(job):
    i, text, lang = job
    chat = Spy(OllamaChat(base_url=BASE, model=MODEL, timeout=180.0, keep_alive='30m'))
    tr = make_translator(chat)
    t0 = time.perf_counter()
    rec = {'i': i, 'lang': lang, 'src': text, 'raw': '', 'status': '', 'ms': 0.0, 'indep': []}
    try:
        out = tr(text, lang)
        rec['status'] = 'passed'
        rec['raw'] = out
    except TranslationRejected as e:
        rec['status'] = 'guard_rejected'
        rec['raw'] = chat.last
        rec['why'] = str(e)
    except Exception as e:  # noqa: BLE001
        rec['status'] = 'error'
        rec['why'] = repr(e)[:160]
    rec['ms'] = (time.perf_counter() - t0) * 1000
    # 독립 검사 — 통과·거절 모두 같은 눈으로 본다(거절된 것 중 실제로 어긋난 것이 몇 건인지도 알기 위해)
    if rec['raw']:
        for name, rx in (('time', TIME), ('money', MONEY)):
            if collections.Counter(rx.findall(text)) != collections.Counter(rx.findall(rec['raw'])):
                rec['indep'].append(name)
        for tag in TAG.findall(text):
            if tag not in rec['raw']:
                rec['indep'].append('tag')
                break
    return rec


def main():
    jobs = [(i, t, lang) for i, t in enumerate(NOTICES) for lang in LANGS]
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        rows = list(ex.map(one, jobs))
    c = collections.Counter(r['status'] for r in rows)
    passed = [r for r in rows if r['status'] == 'passed']
    leaked = [r for r in passed if r['indep']]
    rej = [r for r in rows if r['status'] == 'guard_rejected']
    rej_real = [r for r in rej if r['indep']]
    by_lang = {}
    for lang in LANGS:
        rl = [r for r in rows if r['lang'] == lang]
        by_lang[lang] = {'n': len(rl), 'passed': sum(1 for r in rl if r['status'] == 'passed'), 'rejected': sum(1 for r in rl if r['status'] == 'guard_rejected'),
                         'error': sum(1 for r in rl if r['status'] == 'error'), 'leaked': sum(1 for r in rl if r['status'] == 'passed' and r['indep'])}
    ms = sorted(r['ms'] for r in rows if r['status'] != 'error')
    q = lambda p: ms[min(len(ms) - 1, int(p * len(ms)))] if ms else None  # noqa: E731
    meta = {'날짜': time.strftime('%Y-%m-%d %H:%M'), '모델': MODEL, '호출 수': len(rows), '알림 수': len(NOTICES), '언어': LANGS, '반복': 1, '걸린 시간(초)': round(time.time() - t0),
            '결과': dict(c), '통과했는데 독립 검사로 어긋남(새어 나감)': len(leaked), '보호 장치가 거른 것': len(rej), '거른 것 중 독립 검사로도 어긋남': len(rej_real),
            '번역 지연 ms p50': q(0.5), 'p95': q(0.95), '언어별': by_lang}
    json.dump({'meta': meta, 'rows': rows}, open(os.path.join(HERE, 'results', 'translate_guard_live.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    for r in leaked[:6]:
        print('새어 나감 ·', r['lang'], r['indep'], '|', r['src'][:60], '→', r['raw'][:90])
    for r in rej[:6]:
        print('거름 ·', r['lang'], r.get('why', '')[:70], '|', r['raw'][:80])


if __name__ == '__main__':
    main()
