"""Provider-complete semantic failures retain safe identifiers, never input/output."""
import unittest
from unittest.mock import patch
from app.domains.travel_ops.components.conversation import decision_unit as unit
from app.infrastructure.ollama_chat import validate_content


class SemanticReply:
    def __init__(self, raw):
        self.raw = raw
        self.calls = 0

    def structured_validated(self, system, user, schema, *, validator, num_predict):
        self.calls += 1
        return validate_content(self.raw, validator)


class EvidenceFailureCodes(unittest.TestCase):
    def check_failure(self, spec, code):
        chat = SemanticReply({'action': 'change_time', 'time_edit': spec})
        with self.assertRaises(unit.DecisionFailed) as caught:
            unit.decide(chat, stops=[], changes=[], history=[], selected_item_id=None, message='request')
        self.assertIn(f'evidence_validation:{code}', str(caught.exception))
        self.assertEqual(chat.calls, 1)
        self.assertNotIn('not quoted', str(caught.exception))

    def test_inconsistent_scope(self):
        self.check_failure({'boundary': 'end', 'scope': 'following', 'evidence': 'request'}, 'inconsistent_temporal_scope')

    def test_unquoted_edit(self):
        self.check_failure({'boundary': 'end', 'scope': 'item', 'evidence': 'not quoted'}, 'unquoted_time_edit')

    def test_unquoted_clock(self):
        self.check_failure({'boundary': 'end', 'scope': 'item', 'evidence': 'request', 'time': '19:00'}, 'unquoted_temporal_clock')

    def test_successful_read_remains_successful(self):
        chat = SemanticReply({'action': 'other', 'social': 'Hello', 'general_requests': [], 'reads': []})
        decision = unit.decide(chat, stops=[], changes=[], history=[], selected_item_id=None, message='Hello')
        self.assertEqual(decision.action, 'other')
        self.assertEqual(decision.social, 'Hello')
        self.assertEqual(chat.calls, 1)

    def test_nonsemantic_provider_failure_is_not_relabelled(self):
        class Unavailable:
            def structured_validated(self, *args, **kwargs):
                raise RuntimeError('transport_unavailable')
        with self.assertRaises(unit.DecisionFailed) as caught:
            unit.decide(Unavailable(), stops=[], changes=[], history=[], selected_item_id=None, message='request')
        self.assertEqual(str(caught.exception), 'RuntimeError: transport_unavailable')

    def test_unknown_error_never_exposes_private_exception(self):
        with patch('app.domains.travel_ops.components.conversation.edit_intent.validate', side_effect=ValueError('private customer text secret=not-for-report')):
            with self.assertRaises(unit.DecisionFailed) as caught:
                unit.decide(SemanticReply({}), stops=[], changes=[], history=[], selected_item_id=None, message='request')
        self.assertIn('evidence_validation:unspecified', str(caught.exception))
        self.assertNotIn('private customer', str(caught.exception))
        self.assertNotIn('not-for-report', str(caught.exception))
