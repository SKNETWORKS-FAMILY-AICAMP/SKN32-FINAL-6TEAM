"""Policy-wrapper reader must never select general structured on omitted stream.

Only in-memory providers/budgets; real pipeline and FailoverChat dispatch.
★role-manager 판: `pipeline.read_source` 는 `reading_stream` 이 없으면 가드레일 `travel.intake_reading` 값을 채운다(`_reading_stream`).
  그래서 정책 생략 반례는 `read_source` 에서 「명시 실패」가 아니라 **reader 전용 입구(`reader_structured_stream` · `reader_json_stream`)로만**
  간다 — 어느 쪽이든 유료 · 일반 예산 · reader 예산 0회가 계약이다. 직접 `agent_read.read(stream=None)` 은 그대로 명시 거부.
"""
from datetime import date

import pytest

from app.domains.travel_ops.components.intake import agent_read, pipeline
from app.infrastructure.llm_failover import CircuitBreaker, FailoverChat, _Backend
from app.infrastructure.ollama_chat import OllamaError


def counterexample_chat():
    events = {'local': [], 'paid': [], 'global_reserve': [], 'strict_reserve': [], 'line': []}

    class Local:
        def structured(self, system, user, schema, **options):
            events['local'].append((system, user))
            raise OllamaError('synthetic local failure')

        structured_stream = structured

        def json(self, *args, **options):
            events['line'].append(args)
            return {'spans': []}

        json_stream = json

    class Paid:
        def structured(self, system, user, schema, **options):
            events['paid'].append((system, user))
            return {'items': []}

        structured_stream = structured

        def json_stream(self, system, user, **options):
            events['paid'].append((system, user))
            return {'spans': []}

    def global_reserve():
        events['global_reserve'].append(True)
        return True

    def strict_reserve():
        events['strict_reserve'].append(True)
        return False

    def backend(name, provider, **options):
        return _Backend(name, provider, CircuitBreaker(name, threshold=1, open_seconds=1), **options)

    chat = FailoverChat([backend('local', Local()), backend('paid', Paid(), is_api=True,
                        budget=global_reserve, reader_budget=strict_reserve)])
    return chat, events


def test_read_source_omitted_stream_cannot_bypass_reader_policy():
    from app.infrastructure import llm_failover
    chat, events = counterexample_chat()
    with pytest.raises(pipeline.IntakeRejected) as caught:
        pipeline.read_source('김여행', agent=chat, agent_mode='on', today=date(2026, 10, 24))
    assert caught.value.code == 'reading_model_failed'
    # RED(옛 판) 은 유료 1 · 일반 예산 1 · reader 예산 0 · 원문 「김여행」 전송이었다
    assert events['paid'] == events['global_reserve'] == events['strict_reserve'] == [], repr(events)
    assert len(events['local']) == 1                              # 가드레일 스트림 정책으로 reader 입구만 탔다
    path = llm_failover.current_path()
    assert path['op'] == 'reader_structured_stream' and ('paid', 'reader_external_disabled') in path['reasons']


@pytest.mark.parametrize('mode', ['on', 'shadow'])
def test_missing_policy_never_reaches_paid_even_with_legacy_reader_available(mode):
    chat, events = counterexample_chat()
    try:
        pipeline.read_source('김여행 알수없는줄', chat=chat, agent=chat, agent_mode=mode,
                             today=date(2026, 10, 24))
    except pipeline.IntakeRejected as exc:
        assert exc.code == 'reading_model_failed'
    assert events['paid'] == events['global_reserve'] == events['strict_reserve'] == [], 'must not reach paid/budget'


def test_direct_agent_reader_requires_wrapper_stream_policy():
    chat, events = counterexample_chat()
    with pytest.raises(RuntimeError, match='reader_stream_required'):
        agent_read.read('김여행', ['김여행'], chat, today=date(2026, 10, 24))
    assert events == {key: [] for key in events}


def test_explicit_agent_off_keeps_safe_legacy_line_reader():
    chat, events = counterexample_chat()
    pipeline.read_source('김여행 알수없는줄', chat=chat, agent=chat, agent_mode='off',
                         today=date(2026, 10, 24))
    assert len(events['line']) == 1                                # 줄 읽기는 `reader_json_stream` 으로 로컬만
    assert events['local'] == events['paid'] == events['global_reserve'] == events['strict_reserve'] == []


def test_nonwrapper_legacy_structured_remains_supported():
    calls = []

    class LegacyLocal:
        def structured(self, system, user, schema, **options):
            calls.append(user)
            return {'items': []}

    agent_read.read('남산', ['남산'], LegacyLocal(), today=date(2026, 10, 24))
    assert calls == ['남산']


def test_general_business_structured_policy_is_unchanged():
    chat, events = counterexample_chat()
    assert chat.structured('travel unit', '김여행', {}) == {'items': []}
    assert len(events['local']) == len(events['paid']) == len(events['global_reserve']) == 1
    assert events['paid'][0][1] == '김여행'
    assert events['strict_reserve'] == events['line'] == []
