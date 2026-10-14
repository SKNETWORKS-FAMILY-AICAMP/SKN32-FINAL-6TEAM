"""일정 짚기 모델이 요청 해석과 **같은 모델**이면 같은 문맥 길이를 보낸다 — 다르면 Ollama 가 부를 때마다 모델을 다시 올린다."""
from types import SimpleNamespace

from app.domains.travel_ops.components.conversation import item_pointer
from app.domains.travel_ops.instances._shared import itinerary_team


def _settings(**over):
    base = dict(ollama_pointer_model="tripilot-pointer:e4b-ft", ollama_base_url="http://ollama.test:11434",
                ollama_pointer_timeout_seconds=30.0, ollama_pointer_keep_alive="", ollama_pointer_background_warm=False,
                ollama_pointer_warm_timeout_seconds=180.0, ollama_num_ctx=8192, ollama_model="gemma4:12b")
    base.update(over)
    return SimpleNamespace(**base)


def test_a_separate_pointer_model_keeps_its_own_context_length():
    try:
        assert item_pointer.register_from_settings(_settings()).num_ctx == 0
    finally:
        itinerary_team.set_item_pointer(None)


def test_a_pointer_sharing_the_interpreter_model_sends_the_same_context_length():
    try:
        pointer = item_pointer.register_from_settings(_settings(ollama_model="tripilot-pointer:e4b-ft"))
        sent = []

        def post(url, payload, timeout):
            sent.append(payload["options"].get("num_ctx"))
            return SimpleNamespace(status_code=200, json=lambda: {"message": {"content": '{"item": null}'}}, text="")
        pointer._post = post
        pointer._ask("prompt")
        assert pointer.num_ctx == 8192 and sent == [8192]
    finally:
        itinerary_team.set_item_pointer(None)
