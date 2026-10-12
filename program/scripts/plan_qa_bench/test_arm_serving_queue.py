"""mock 서버로 HTTP 오류·해석 실패를 정확도 분모에 유지하는지 확인한다."""
import importlib.util
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

spec = importlib.util.spec_from_file_location('arm_queue', Path(__file__).parent/'server/arm_serving_queue.py')
queue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(queue)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        text = body['messages'][0]['content']
        if text == 'http_error':
            self.send_error(503)
            return
        value = {'choices': [{'message': {'content': text}}], 'timings': {'cache_n': 4}}
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def ask(self, prompt, gold):
        return queue.ask(dict(i=1, set='travel', type='unit', prompt=prompt, gold=gold),
                         dict(seed=7, cache_prompt=True, request_timeout_s=3), self.server.server_port)

    def test_normal_selection(self):
        self.assertTrue(self.ask('{"item": 3}', 3)['correct'])

    def test_null_selection(self):
        self.assertTrue(self.ask('{"item": null}', None)['correct'])

    def test_unparsed_is_failure(self):
        self.assertFalse(self.ask('not json', None)['correct'])

    def test_http_error_is_failure(self):
        self.assertIn('error', self.ask('http_error', None))

    def test_failure_denominator_and_false_positive(self):
        rows = [self.ask('{"item": 3}', 3), self.ask('{"item": 3}', None),
                self.ask('not json', None), self.ask('http_error', None)]
        summary = queue.summarize(rows, 4)
        self.assertEqual((summary['expected'], summary['saved'], summary['correct']), (4, 4, 1))
        self.assertEqual((summary['normal_total'], summary['null_total'], summary['false_positive'], summary['errors_or_unparsed']), (1, 3, 1, 2))


if __name__ == '__main__':
    unittest.main()
