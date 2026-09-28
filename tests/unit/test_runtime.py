"""Transport error handling must never change the target model silently."""
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import NotFoundError

from core.openai_runtime import OpenAIAgent, OpenAIRunner
from core import utils


def not_found():
    response = httpx.Response(404, request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"))
    return NotFoundError("No endpoints", response=response, body={})


def test_blue_only_retries_same_model_free_alias_and_records_it(monkeypatch):
    completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="banking help"))])
    create = Mock(side_effect=[not_found(), completion, completion])
    runner = OpenAIRunner(app_name="blue", model="liquid/lfm-2.5-2.6b", provider="openrouter")
    monkeypatch.setattr(runner, "_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    agent = OpenAIAgent(name="blue", instruction="Banking assistant")
    assert asyncio.run(runner.chat(agent, "account")) == "banking help"
    assert asyncio.run(runner.chat(agent, "loan")) == "banking help"
    assert [call.kwargs["model"] for call in create.call_args_list] == [
        "liquid/lfm-2.5-2.6b", "liquid/lfm-2.5-2.6b:free", "liquid/lfm-2.5-2.6b:free",
    ]
    assert runner.model == "liquid/lfm-2.5-2.6b"
    assert runner.api_model == "liquid/lfm-2.5-2.6b:free"


def test_red_does_not_switch_models_after_404(monkeypatch):
    create = Mock(side_effect=not_found())
    runner = OpenAIRunner(app_name="red", model="gpt-4o-mini")
    monkeypatch.setattr(runner, "_client", lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    with pytest.raises(NotFoundError):
        asyncio.run(runner.chat(OpenAIAgent(name="red", instruction="Lab"), "account"))
    assert create.call_count == 1


@pytest.mark.parametrize("non_retry_code", [401, 429])
def test_transient_retry_has_a_bound_and_auth_errors_are_not_retried(monkeypatch, non_retry_code):
    class ProviderError(Exception):
        def __init__(self, code):
            self.code = code

    attempts = []

    async def fail(*args, **kwargs):
        attempts.append(1)
        raise ProviderError(503)

    async def no_sleep(delay):
        assert delay in {2, 4}

    monkeypatch.setattr(utils, "_chat_once", fail)
    monkeypatch.setattr(utils.asyncio, "sleep", no_sleep)
    with pytest.raises(ProviderError):
        asyncio.run(utils.chat_with_agent(None, None, "account"))
    assert len(attempts) == 3

    async def unauthorized(*args, **kwargs):
        attempts.append(1)
        raise ProviderError(non_retry_code)

    monkeypatch.setattr(utils, "_chat_once", unauthorized)
    with pytest.raises(ProviderError):
        asyncio.run(utils.chat_with_agent(None, None, "account"))
    assert len(attempts) == 4
