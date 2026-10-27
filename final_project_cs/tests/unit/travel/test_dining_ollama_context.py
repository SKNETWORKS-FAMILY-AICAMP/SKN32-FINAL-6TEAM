from types import SimpleNamespace

import httpx

from app.infrastructure.llm.tool_chat import OllamaToolChat


def test_ollama_tool_chat_context_and_keep_alive_payload():
    payloads = []

    def post(url, payload):
        payloads.append(payload)
        return httpx.Response(
            200, json={"message": {"role": "assistant", "content": "ok"}},
            request=httpx.Request("POST", url),
        )

    chat = OllamaToolChat(base_url="http://ollama.test", model="shared",
                          num_ctx=12288, keep_alive="", post=post)
    chat.step([{"role": "user", "content": "hello"}], [])
    assert payloads[-1]["options"]["num_ctx"] == 12288
    assert "keep_alive" not in payloads[-1]

    chat = OllamaToolChat(base_url="http://ollama.test", model="other", post=post)
    chat.step([{"role": "user", "content": "hello"}], [])
    assert "num_ctx" not in payloads[-1]["options"]
    assert payloads[-1]["keep_alive"] == "30m"


def test_dining_judge_shares_ollama_settings_only_for_same_model(monkeypatch):
    import app.core.settings as settings_module
    from app import composition

    settings = SimpleNamespace(
        llm_provider="ollama", openai_api_key="", ollama_base_url="http://ollama.test",
        ollama_model="shared", ollama_num_ctx=12288, ollama_keep_alive="45m",
    )
    monkeypatch.setattr(settings_module, "get_settings", lambda: settings)
    monkeypatch.setattr(composition, "build_kakao_local", lambda: None)
    monkeypatch.setattr(composition, "build_google_places", lambda: None)
    for model, num_ctx, keep_alive in [("shared", 12288, "45m"), ("other", 0, "30m"), ("", 12288, "45m")]:
        monkeypatch.setattr(settings_module, "dining_agent_judge",
                            lambda: {"model": f"ollama:{model}", "deadline_s": 30.0})
        chat = composition._dining_agent_judge().keywords["chat"]
        assert (chat.model, chat.num_ctx, chat.keep_alive) == (model or "shared", num_ctx, keep_alive)
