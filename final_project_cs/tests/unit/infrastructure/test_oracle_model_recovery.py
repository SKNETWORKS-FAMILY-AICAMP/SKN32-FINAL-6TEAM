"""오라클의 SSH → API → 내부 복구와 기존 배포의 순서를 분리 검증한다."""
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.infrastructure import llm_failover as lf, ollama_chat as oc


def settings(**overrides):
    values = dict(ollama_base_url="http://internal.test", ollama_ssh_base_url="http://gpu.test",
                  ollama_model="resident", ollama_ssh_model="trained", ollama_timeout_seconds=600,
                  ollama_keep_alive="-1", ollama_num_ctx=8192, model_route_chat="ssh",
                  llm_failover_enabled=True, llm_failover_local_last=True, openai_api_key_server="sk-test",
                  llm_model="api-test", llm_failover_model="api-test", llm_failover_primary_timeout_seconds=9,
                  llm_failover_api_timeout_seconds=8, llm_failover_total_seconds=15,
                  llm_failover_failures=3, llm_failover_open_seconds=60, llm_failover_vision=False,
                  ollama_fallback_base_urls="")
    return SimpleNamespace(**(values | overrides))


@pytest.fixture(autouse=True)
def isolate():
    lf.reset_state()
    oc.register_route_provider(None)
    lf.register_budget_provider(None)
    yield
    lf.reset_state()
    oc.register_route_provider(None)
    lf.register_budget_provider(None)


@pytest.mark.parametrize("last,expected", [(True, ["ollama", "openai", "local"]),
                                          (False, ["ollama", "ollama2", "openai"])])
def test_explicit_local_last_does_not_change_other_deployments(last, expected):
    target = oc.from_settings(settings(llm_failover_local_last=last))
    assert [b.name for b in target._backends] == expected
    assert target._backends[0].chat.model == "trained"
    assert target._backends[0].timeout == 9
    if last:
        assert target._backends[-1].chat.model == "resident"
        assert target._backends[-1].timeout == 600
        assert target._backends[-1].chat.num_ctx == 8192


@pytest.mark.parametrize("failure", ["none", "gpu", "both", "budget", "key"])
def test_request_reaches_only_the_first_usable_backend(failure):
    seen = []

    def transport(name, broken):
        def post(url, payload):
            seen.append(name)
            if broken:
                raise httpx.ConnectError("unavailable")
            return httpx.Response(200, json={"message": {"content": '{"ok":true}'}},
                                  request=httpx.Request("POST", url))
        return post

    def api_call(**kwargs):
        seen.append("api")
        if failure == "both":
            raise openai.AuthenticationError("invalid", response=httpx.Response(401,
                                             request=httpx.Request("POST", "https://api.test")), body=None)
        assert "person@example.test" not in str(kwargs["messages"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'))])

    primary = oc.OllamaChat(base_url="http://gpu.test", model="trained", timeout=600,
                            transport=transport("gpu", failure != "none"))
    local = oc.OllamaChat(base_url="http://internal.test", model="resident", timeout=600,
                          transport=transport("local", False))
    api = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=api_call)))
    target = lf.wrap_from_settings(primary, settings(openai_api_key_server="" if failure == "key" else "sk-test"),
                                   local_fallback=local, api_client=api, budget=lambda: failure != "budget")
    assert target.json("Return JSON", "서울 일정 person@example.test") == {"ok": True}
    expected = {"none": ["gpu"], "gpu": ["gpu", "api"], "both": ["gpu", "api", "local"],
                "budget": ["gpu", "local"], "key": ["gpu", "local"]}
    assert seen == expected[failure]
    assert lf.current_path()["backend"] == seen[-1].replace("api", "openai").replace("gpu", "ollama")


def test_internal_model_recovery_failure_is_visible():
    def broken(url, payload):
        raise httpx.ConnectError("unavailable")

    primary = oc.OllamaChat(base_url="http://gpu.test", model="trained", transport=broken)
    local = oc.OllamaChat(base_url="http://internal.test", model="resident", transport=broken)
    target = lf.wrap_from_settings(primary, settings(openai_api_key_server=""), local_fallback=local)
    with pytest.raises(oc.OllamaError, match="ollama=connect, local=connect"):
        target.text("서울 일정", "확인")


def test_missing_key_preserves_internal_recovery_without_a_personal_key():
    target = oc.from_settings(settings(openai_api_key_server="", openai_api_key="personal-unused"))
    assert [b.name for b in target._backends] == ["ollama", "local"]
