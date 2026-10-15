"""일정 항목 짚기 시험 · 학습 세트의 자리를 한 곳에서 정한다 (2026-10-16).

세트 파일은 저장소 루트 datasets/core/pointing/ 아래에 있다(git 밖 — 공개 말뭉치 원문이 든 세트가 있어서).
  testset/   시험에만 쓴다      trainset/  학습에만 쓴다
폴더 이름은 그 세트가 무엇인지, 끝의 _v1 · _v2 는 판이다. 점수를 낸 판은 고치지 않고 새 판을 만든다.
옛 이름(769 · D · D2 · D3 · E · H)과의 대응은 같은 폴더의 TESTSETS.md 에 있다.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
POINTING = ROOT / 'datasets' / 'core' / 'pointing'
TEST = POINTING / 'testset'
TRAIN = POINTING / 'trainset'

ITINERARY_QUESTIONS = TEST / 'itinerary_questions_v1'                    # 옛 769(mix8~12) · A~C 채점 정답 gold_sets
QUESTIONS_PLUS_CHITCHAT = TEST / 'questions_plus_chitchat_v1'            # 옛 D
CHITCHAT_ONLY_HOLDOUT = TEST / 'chitchat_only_holdout_v1'                # 옛 D2
SYNTHETIC_CHITCHAT = TEST / 'synthetic_chitchat_plus_questions_v1'       # 옛 D3
REQUESTS_INSIDE_CHITCHAT = TEST / 'requests_inside_chitchat_pairs_v1'    # 옛 E(MX)
TRAP_SENTENCES = TEST / 'confusing_trap_sentences_v1'                    # 옛 H 시험용
TRAP_SENTENCES_TRAIN = TRAIN / 'confusing_trap_sentences_v1'             # 옛 H 학습용

_BY_NAME = {
    **{f'mix{n}.json': ITINERARY_QUESTIONS for n in range(8, 13)},
    'gold_sets.json': ITINERARY_QUESTIONS,
    'all_prompts.json': QUESTIONS_PLUS_CHITCHAT,
    'all_prompts_d2.json': CHITCHAT_ONLY_HOLDOUT,
    'all_prompts_d3.json': SYNTHETIC_CHITCHAT,
}


def fixture(name):
    """세트 파일 이름 → 경로(str). 옮긴 세트가 아니면 예전처럼 이 폴더의 fixtures/ 를 가리킨다."""
    return str(_BY_NAME.get(name, HERE / 'fixtures') / name)
