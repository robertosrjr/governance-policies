"""Provedor OpenRouter: contrato da API sem rede (urlopen falso)."""

import io
import json
import urllib.error
import urllib.request
from dataclasses import replace

import pytest

from governance import llm
from governance.diff import as_new_files
from governance.llm import (REQUEST_TIMEOUT_MS, LlmConfig, OpenRouterProvider, ProviderError,
                            build_provider, response_schema, to_json_schema)
from governance.review import evaluate

USECASE = "app/src/main/java/com/x/application/usecase/CriarCliente.java"
TOSTRING_LOG = ('package com.x.application.usecase;\nclass CriarCliente {\n'
                '  void run(Cliente c) {\n    logger.info("criado {}", c);\n  }\n}\n')
CONFIG = LlmConfig(provider="openrouter", model="google/gemini-flash", max_attempts=3)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def completion(content, **extra):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}], **extra}


@pytest.fixture
def api(monkeypatch):
    """Registra as requisições e devolve, em ordem, as respostas (dict) ou erros HTTP (int)."""
    state = {"requests": [], "responses": []}

    def urlopen(request, timeout):
        state["requests"].append((request, timeout))
        answer = state["responses"].pop(0)
        if isinstance(answer, int):
            body = json.dumps({"error": {"code": answer, "message": f"erro {answer}"}}).encode()
            raise urllib.error.HTTPError(request.full_url, answer, "erro", {}, io.BytesIO(body))
        return FakeResponse(json.dumps(answer).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)
    return state


def test_build_provider_selects_openrouter():
    assert isinstance(build_provider(CONFIG, "chave"), OpenRouterProvider)


def test_schema_is_converted_to_strict_json_schema():
    schema = to_json_schema(response_schema({"LGPD-LOG-001"}))
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    item = schema["properties"]["findings"]["items"]
    assert item["type"] == "object" and item["additionalProperties"] is False
    assert item["properties"]["line"]["type"] == "integer"
    assert item["properties"]["policy_id"]["enum"] == ["LGPD-LOG-001"]
    assert set(item["required"]) == set(item["properties"])


def test_request_follows_the_api_contract(api):
    api["responses"] = [completion('{"summary": "ok", "findings": []}')]
    result = OpenRouterProvider(CONFIG, "sk-or-x").review("sistema", "conteúdo",
                                                          response_schema({"X"}))
    assert result == {"summary": "ok", "findings": []}
    [(request, timeout)] = api["requests"]
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request.get_header("Authorization") == "Bearer sk-or-x"
    assert timeout == REQUEST_TIMEOUT_MS / 1000
    body = json.loads(request.data)
    assert body["model"] == "google/gemini-flash" and body["temperature"] == 0
    assert body["max_tokens"] == CONFIG.max_output_tokens
    assert body["messages"] == [{"role": "system", "content": "sistema"},
                                {"role": "user", "content": "conteúdo"}]
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["provider"] == {"require_parameters": True, "data_collection": "deny"}


def test_transient_error_is_retried(api):
    api["responses"] = [503, completion('{"summary": "ok", "findings": []}')]
    assert OpenRouterProvider(CONFIG, "k").review("s", "u", {})["summary"] == "ok"
    assert len(api["requests"]) == 2


def test_rejected_key_is_not_retried(api):
    api["responses"] = [401]
    with pytest.raises(ProviderError) as exc:
        OpenRouterProvider(CONFIG, "k").review("s", "u", {})
    assert exc.value.code == 401 and "erro 401" in str(exc.value)
    assert len(api["requests"]) == 1


@pytest.mark.parametrize("answer, expected", [
    ({"error": {"code": 502, "message": "upstream"}}, ProviderError),
    ({"choices": [{"finish_reason": "error", "message": {"content": ""}}]}, ProviderError),
    ({"choices": [{"finish_reason": "length", "message": {"content": '{"summary": "'}}]},
     ValueError),
    (completion(None), ValueError),
    (completion("não é json"), ValueError),
])
def test_error_inside_http_200_is_not_a_result(api, answer, expected):
    api["responses"] = [answer] * CONFIG.max_attempts
    with pytest.raises(expected):
        OpenRouterProvider(CONFIG, "k").review("s", "u", {})


class Failing:
    def __init__(self, error):
        self.error = error

    def review(self, *_args):
        raise self.error


def run(policies, bundle, provider):
    bundle = replace(bundle, llm=replace(bundle.llm, provider="openrouter"))
    return evaluate(
        as_new_files({USECASE: TOSTRING_LOG}), policies=policies, waivers=[], provider=provider,
        bundle=bundle, subject={"repository": "org/app", "commit": "abc1234", "base": "main",
                                "pull_request": 1},
        governance_ref="v1.0.0", policies_digest="0" * 64, llm_required=True)


def test_messages_name_the_openrouter_secret(policies, bundle):
    missing = run(policies, bundle, provider=None)
    assert "OPENROUTER_API_KEY" in missing["errors"][0]["action"]
    rejected = run(policies, bundle, Failing(ProviderError(401, "No auth credentials found")))
    assert rejected["status"] == "BLOCKED"
    assert "OPENROUTER_API_KEY" in rejected["errors"][0]["action"]


def test_no_credits_blocks_as_unavailable(policies, bundle):
    result = run(policies, bundle, Failing(ProviderError(402, "Insufficient credits")))
    assert result["status"] == "BLOCKED"
    error = result["errors"][0]
    assert error["kind"] == "llm_unavailable" and "HTTP 402" in error["message"]
