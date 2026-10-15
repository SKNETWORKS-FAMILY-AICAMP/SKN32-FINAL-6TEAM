import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("adapter", Path(__file__).with_name("ollama_adapter.py"))
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class AdapterContract(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"CHAT_MODEL": "resident"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def payload(self, **kwargs):
        return {"model": "resident", "messages": [{"role": "user", "content": "서울 일정"}], **kwargs}

    def test_json_schema_is_enforced_upstream(self):
        schema = {"type": "object", "required": ["index"], "properties": {"index": {"type": "integer"}}}
        result = adapter.chat_payload(self.payload(format=schema))
        self.assertEqual(result["response_format"]["json_schema"]["schema"], schema)

    def test_json_mode(self):
        self.assertEqual(adapter.chat_payload(self.payload(format="json"))["response_format"], {"type": "json_object"})

    def test_thinking_choice_preserved_in_both_directions(self):
        for value in (False, True):
            with self.subTest(think=value):
                result = adapter.chat_payload(self.payload(think=value))
                self.assertIs(result["chat_template_kwargs"]["enable_thinking"], value)

    def test_omitted_thinking_leaves_model_default(self):
        self.assertNotIn("chat_template_kwargs", adapter.chat_payload(self.payload()))

    def test_string_false_not_silently_enabled(self):
        with self.assertRaises(ValueError):
            adapter.chat_payload(self.payload(think="false"))

    def test_limits_and_seed_preserved(self):
        result = adapter.chat_payload(self.payload(options={"num_predict": 1, "seed": 17, "temperature": 0.2}))
        self.assertEqual((result["max_tokens"], result["seed"], result["temperature"]), (1, 17, 0.2))

    def test_unknown_model_refused(self):
        with self.assertRaises(ValueError):
            adapter.chat_payload({**self.payload(), "model": "wrong"})

    def test_images_refused_without_silent_loss(self):
        with self.assertRaises(ValueError):
            adapter.chat_payload(self.payload(messages=[{"role": "user", "content": "사진", "images": ["bytes"]}]))

    def test_stream_refused_without_silent_change(self):
        with self.assertRaises(ValueError):
            adapter.chat_payload(self.payload(stream=True))

    def test_actual_model_identity_matches(self):
        with patch.object(adapter, "upstream", return_value={"data": [{"id": "expected"}]}):
            adapter.check_model("http://127.0.0.1", "expected")

    def test_benchmark_model_switch_cannot_change_app_silently(self):
        with patch.object(adapter, "upstream", return_value={"data": [{"id": "different"}]}):
            with self.assertRaises(RuntimeError):
                adapter.check_model("http://127.0.0.1", "expected")


if __name__ == "__main__":
    unittest.main()
