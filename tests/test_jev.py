"""Julgamento tipado pelo Jev (ADR-GOV-002): contrato da API e garantias, sem rede."""

import io
import json
import urllib.error
import urllib.request
from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator

from governance import llm
from governance.diff import as_new_files
from governance.jev import JevProvider, build_state, candidates
from governance.llm import REQUEST_TIMEOUT_MS, LlmConfig, ProviderError
from governance.report import build_markdown
from governance.review import evaluate

from test_evaluation_layers import RESULT_SCHEMA

CONFIG = LlmConfig(provider="typesafe", model="jev-1.13.0", max_attempts=2)
CLIENTE = "app/src/main/java/com/x/domain/model/Cliente.java"
USECASE = "app/src/main/java/com/x/application/usecase/CriarCliente.java"
CLIENTE_SRC = "package com.x.domain.model;\npublic record Cliente(String id, String cpf) {}\n"
USECASE_SRC = (
    "package com.x.application.usecase;\n"
    "class CriarCliente {\n"
    "  void run(Cliente c) {\n"
    '    logger.info("criado {}", c);\n'
    '    String apiKey = "abcdefgh12345678";\n'
    "  }\n"
    "}\n"
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def api(monkeypatch):
    state = {"requests": [], "responses": []}

    def urlopen(request, timeout):
        state["requests"].append((request, timeout))
        answer = state["responses"].pop(0)
        if isinstance(answer, int):
            body = json.dumps({"detail": {"message": f"erro {answer}"}}).encode()
            raise urllib.error.HTTPError(request.full_url, answer, "erro", {}, io.BytesIO(body))
        return FakeResponse(json.dumps(answer).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)
    return state


def test_request_follows_the_api_contract(api):
    api["responses"] = [{"model": "jev-1.13.0",
                         "answers": {"l4": {"type": "noul", "noul": 0.91}}}]
    assert JevProvider(CONFIG, "ts-x").nouls({"codigo": "x"}, {"l4": "Loga CPF?"}) == \
        {"l4": 0.91}
    [(request, timeout)] = api["requests"]
    assert request.full_url == "https://api.typesafe.ai/v1/systemone"
    assert request.get_header("Authorization") == "Bearer ts-x"
    assert timeout == REQUEST_TIMEOUT_MS / 1000
    assert json.loads(request.data) == {
        "model": "jev-1.13.0", "state": {"codigo": "x"},
        "questions": {"l4": {"type": "noul", "instructions": "Loga CPF?"}}}


@pytest.mark.parametrize("answers", [{}, {"l4": {"type": "noul"}},
                                     {"l4": {"type": "noul", "noul": 1.7}}])
def test_incomplete_answer_is_an_error_not_a_no(api, answers):
    api["responses"] = [{"answers": answers}] * CONFIG.max_attempts
    with pytest.raises(ValueError):
        JevProvider(CONFIG, "k").nouls("s", {"l4": "q"})


def test_rejected_key_is_not_retried_and_keeps_the_message(api):
    api["responses"] = [401]
    with pytest.raises(ProviderError) as exc:
        JevProvider(CONFIG, "k").nouls("s", {"q": "q"})
    assert exc.value.code == 401 and "erro 401" in str(exc.value)
    assert len(api["requests"]) == 1


def lgpd(policies):
    return next(p for p in policies if p.id == "LGPD-LOG-001")


def test_candidates_are_only_added_lines_matching_the_policy(policies):
    [changed] = as_new_files({USECASE: USECASE_SRC})
    changed.added_lines.pop(4)
    assert candidates(lgpd(policies), changed) == {}
    [changed] = as_new_files({USECASE: USECASE_SRC})
    assert list(candidates(lgpd(policies), changed)) == [4]


def test_state_has_cited_files_and_no_secrets():
    cliente, usecase = as_new_files({CLIENTE: CLIENTE_SRC, USECASE: USECASE_SRC})
    state = build_state(usecase, [cliente, usecase])
    assert list(state["outros_arquivos"]) == [CLIENTE]  # `Cliente` é citado
    assert "abcdefgh12345678" not in json.dumps(state) and "[REDACTED]" in state["codigo"]
    assert "4| " in state["codigo"]  # linhas numeradas, como na pergunta


class Jev:
    def __init__(self, probability=0.0, error=None):
        self.probability, self.error, self.calls = probability, error, []

    def nouls(self, state, questions):
        self.calls.append((state, questions))
        if self.error:
            raise self.error
        return {qid: self.probability for qid in questions}


def run(policies, bundle, jev, files=None, llm_required=True):
    result = evaluate(
        as_new_files(files or {CLIENTE: CLIENTE_SRC, USECASE: USECASE_SRC}),
        policies=[p for p in policies if p.llm_engine != "generative"], waivers=[],
        provider=None, jev_provider=jev, bundle=bundle,
        subject={"repository": "org/app", "commit": "abc1234", "base": "main",
                 "pull_request": 1},
        governance_ref="v1", policies_digest="0" * 64, llm_required=llm_required)
    Draft202012Validator(RESULT_SCHEMA).validate(result)
    return result


def test_probability_above_threshold_is_an_advisory_finding(policies, bundle):
    jev = Jev(probability=0.9)
    result = run(policies, bundle, jev)
    [finding] = [v for v in result["violations"] if v["policy_id"] == "LGPD-LOG-001"]
    assert finding["line"] == 4 and finding["source"] == "llm"
    assert finding["blocking"] is False and "p=0.90" in finding["message"]
    # o único bloqueio é o segredo de mentira do arquivo (SEC-SECRET-001, determinístico)
    assert {v["policy_id"] for v in result["violations"] if v["blocking"]} == {"SEC-SECRET-001"}
    state, questions = jev.calls[0]
    assert list(questions) == ["linha_4"]
    assert 'logger.info("criado {}", c);' in questions["linha_4"]  # {text}, chaves intactas
    assert result["bundle"]["jev"] == {"provider": "typesafe", "model": bundle.jev.model}
    assert f"Jev {bundle.jev.model}" in build_markdown(result)


def test_probability_below_threshold_is_not_a_finding(policies, bundle):
    result = run(policies, bundle, Jev(probability=0.2))
    assert not [v for v in result["violations"] if v["policy_id"] == "LGPD-LOG-001"]


def test_file_without_candidates_is_not_sent(policies, bundle):
    jev = Jev(probability=0.9)
    run(policies, bundle, jev, files={CLIENTE: CLIENTE_SRC})
    assert jev.calls == []


def test_jev_failure_is_fail_closed_and_names_the_secret(policies, bundle):
    result = run(policies, bundle, Jev(error=ProviderError(401, "Cannot authenticate")))
    assert result["status"] == "BLOCKED"
    assert "TYPESAFE_API_KEY" in result["errors"][0]["action"]


def test_missing_jev_in_ci_is_fail_closed(policies, bundle):
    result = run(policies, bundle, None)
    assert result["status"] == "BLOCKED"
    error = result["errors"][0]
    assert error["kind"] == "llm_not_configured" and "TYPESAFE_API_KEY" in error["action"]
    assert result["bundle"]["jev"] is None


def test_state_over_budget_blocks_instead_of_truncating(policies, bundle):
    small = replace(bundle, jev=replace(bundle.jev, max_input_chars=50))
    jev = Jev(probability=0.9)
    result = run(policies, small, jev)
    assert result["status"] == "BLOCKED"
    assert result["errors"][0]["kind"] == "input_too_large"
    assert jev.calls == []


def test_deterministic_finding_is_not_duplicated_by_jev(policies, bundle):
    src = USECASE_SRC.replace('logger.info("criado {}", c);', 'logger.info("cpf " + cpf);')
    result = run(policies, bundle, Jev(probability=0.9), files={USECASE: src})
    found = [v for v in result["violations"] if v["policy_id"] == "LGPD-LOG-001"]
    assert [(v["line"], v["source"]) for v in found] == [(4, "deterministic")]
