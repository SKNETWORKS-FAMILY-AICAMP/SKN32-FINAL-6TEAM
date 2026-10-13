import unittest
from app_schema_diagnostic_20261011 import inspect_response


class ResponseInspection(unittest.TestCase):
    def response(self, content, reason='stop', **fields):
        return {'choices': [{'message': {'content': content, **fields}, 'finish_reason': reason}]}

    def test_correct_and_incorrect_targets(self):
        expected = {'action': 'answer_fact', 'target_item': 'i1', 'fact': 'time'}
        self.assertTrue(inspect_response(self.response('{"action":"answer_fact","target_item":"i1","fact":"time"}'), expected)['correct'])
        self.assertFalse(inspect_response(self.response('{"action":"answer_fact","target_item":"i2","fact":"time"}'), expected)['correct'])

    def test_empty_reasoning_and_budget_are_not_success(self):
        result = inspect_response(self.response('', 'length', reasoning_content='thinking'), {'action': 'other'})
        self.assertFalse(result['parsed'])
        self.assertTrue(result['empty_content'])
        self.assertEqual(result['reasoning_characters'], 8)
        self.assertEqual(result['finish_reason'], 'length')

    def test_malformed_and_non_object_fail(self):
        for content in ['{', '[]', 'null', None, '   ']:
            self.assertFalse(inspect_response(self.response(content), {'action': 'other'})['correct'])


if __name__ == '__main__':
    unittest.main()
