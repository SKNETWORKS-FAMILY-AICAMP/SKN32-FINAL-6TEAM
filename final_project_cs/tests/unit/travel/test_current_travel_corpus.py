"""현재 운영 안내의 출처·고객 문장과 거래 승인 경계를 확인한다."""
from pathlib import Path
from knowledge.ingest import load_corpus
from app.domains.travel_ops.instances._shared import itinerary_team


def test_current_corpus_has_customer_answers_for_six_travel_scopes():
    docs=load_corpus(Path(__file__).resolve().parents[3]/'knowledge/current-travel/manifest.json')
    assert len(docs)==6 and len({d.frontmatter['scope'] for d in docs})==6
    for doc in docs:
        assert doc.frontmatter['pii_class']=='none'
        assert len(doc.sections)==1
        assert 200<=len(''.join(doc.sections[0].content.split()))<=600
        assert doc.frontmatter['customer_answers'][doc.sections[0].title]


def test_current_cancellation_answer_does_not_invent_deadlines():
    itinerary_team._LINES=None
    answer,sources=itinerary_team.question_answer(None,[{'source_id':'t_current_cancellation_01#c1','score':.9}],None)
    assert sources==['t_current_cancellation_01#c1']
    assert '자동으로 취소되지는 않아요' in answer
    assert '72시간' not in answer and '24시간' not in answer
