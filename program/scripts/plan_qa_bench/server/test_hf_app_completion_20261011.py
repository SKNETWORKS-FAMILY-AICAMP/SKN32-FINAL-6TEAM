import json
import unittest
from hf_app_completion_20261011 import inspect, gate


class CompletionContract(unittest.TestCase):
    schema = {'type': 'object', 'properties': {'action': {'type': 'string', 'enum': ['other']},
        'minutes': {'type': 'integer'}}, 'required': ['action', 'minutes']}

    def test_complete_schema_and_semantics(self):
        self.assertTrue(inspect('{"action":"other","minutes":0}', 'stop', {'action': 'other'}, self.schema)['correct'])

    def test_failure_is_retained_for_budget_duplicate_invalid_and_missing(self):
        for content, finish in [('{"action":"other","minutes":0}', 'length'),
            ('{"action":"other","action":"other","minutes":0}', 'stop'),
            ('{"action":"other","minutes":true}', 'stop'), ('{"action":"other"}', 'stop'),
            ('{"action":"other","minutes":NaN}', 'stop'), ('', 'stop')]:
            self.assertFalse(inspect(content, finish, {'action': 'other'}, self.schema)['correct'])

    def test_unsupported_schema_never_claims_valid(self):
        schema = dict(self.schema, additionalProperties=False)
        self.assertFalse(inspect('{"action":"other","minutes":0}', 'stop', {'action': 'other'}, schema)['schema_valid'])

    def test_stability_requires_all_unique_conditions_both_repeats(self):
        rows = [dict(case=str(i), history='fixed', repeat=j, budget=800, correct=True) for i in range(12) for j in [1, 2]]
        self.assertTrue(gate(rows))
        self.assertFalse(gate(rows[:-1]))
        rows[-1]['correct'] = False
        self.assertFalse(gate(rows))


if __name__ == '__main__':
    unittest.main()
