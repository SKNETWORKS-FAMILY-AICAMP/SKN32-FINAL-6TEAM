import importlib.util
import json
import os
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('guard_adapter', Path(__file__).with_name('ollama_adapter.py'))
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def response(content, reason='stop'):
    return {'choices': [{'message': {'content': content}, 'finish_reason': reason}],
            'usage': {'completion_tokens': 4}, 'timings': {'predicted_ms': 3}}


class ResponseGuard(unittest.TestCase):
    def test_valid_text_preserved(self):
        value = adapter.chat_response(response(' 경복궁 일정입니다. '), {})
        self.assertEqual(value['message']['content'], ' 경복궁 일정입니다. ')
        self.assertEqual(value['done_reason'], 'stop')
        self.assertEqual(value['usage']['completion_tokens'], 4)

    def test_json_document_preserved_without_repair(self):
        text = ' {"target_item": "i1", "minutes": 0}\n'
        self.assertEqual(adapter.chat_response(response(text), {'format': {}})['message']['content'], text)

    def test_incomplete_or_empty_is_model_error(self):
        for content, reason in [('', 'length'), ('  ', 'stop'), (None, 'stop'), ('{}', 'length'), ('{}', None), ('{}', 'content_filter')]:
            with self.subTest(content=content, reason=reason), self.assertRaises(adapter.ModelOutputError):
                adapter.chat_response(response(content, reason), {'format': 'json'})

    def test_invalid_json_never_repaired(self):
        for text in ['{"action":', '{} trailing', '```json\n{}\n```', '{"n":NaN}', '{"n":1,"n":2}']:
            with self.subTest(text=text), self.assertRaises(adapter.ModelOutputError):
                adapter.chat_response(response(text), {'format': 'json'})

    def test_malformed_envelope_is_model_error(self):
        for value in [{}, {'choices': []}, {'choices': [None]}, {'choices': [{'message': {}}]}]:
            with self.subTest(value=value), self.assertRaises(adapter.ModelOutputError):
                adapter.chat_response(value, {})

    def test_failure_diagnostics_do_not_contain_content(self):
        secret_text = '{"private-trip":'
        with self.assertRaises(adapter.ModelOutputError) as error:
            adapter.chat_response(response(secret_text), {'format': 'json'})
        self.assertNotIn(secret_text, json.dumps(error.exception.diagnostics))
        self.assertEqual(len(error.exception.diagnostics['content_sha256']), 64)

    def test_http_distinguishes_client_and_model_failures(self):
        environment = {'CHAT_MODEL': 'resident', 'CHAT_ID': 'model', 'CHAT_URL': 'http://127.0.0.1'}
        with patch.dict(os.environ, environment), patch.object(adapter, 'check_model'), patch.object(adapter, 'upstream') as upstream:
            server = adapter.ThreadingHTTPServer(('127.0.0.1', 0), adapter.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for model, raw, expected in [('wrong', response('{}'), 400), ('resident', response('', 'length'), 502), ('resident', response('{"action":'), 502), ('resident', response('{"action":"other"}'), 200)]:
                    upstream.return_value = raw
                    body = json.dumps({'model': model, 'messages': [{'role': 'user', 'content': '서울 일정'}], 'format': 'json'}).encode()
                    request = urllib.request.Request('http://127.0.0.1:%s/api/chat' % server.server_port, body, {'Content-Type': 'application/json'})
                    try:
                        with urllib.request.urlopen(request) as result:
                            status = result.status
                    except urllib.error.HTTPError as error:
                        status = error.code
                        error.close()
                    self.assertEqual(status, expected)
                upstream.side_effect = ValueError('malformed upstream JSON')
                body = json.dumps({'model': 'resident', 'messages': [{'role': 'user', 'content': '서울 일정'}]}).encode()
                request = urllib.request.Request('http://127.0.0.1:%s/api/chat' % server.server_port, body, {'Content-Type': 'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    urllib.request.urlopen(request)
                self.assertEqual(failure.exception.code, 502)
                failure.exception.close()
            finally:
                server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
