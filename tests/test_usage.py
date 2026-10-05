"""Custo da própria esteira (ADR-FINOPS-002): consumo de IA registrado sem rede."""

import io
import json
import urllib.request
from datetime import date

import pytest
from jsonschema import Draft202012Validator
from test_dashboard import REPO, finding, result
from test_evaluation_layers import RESULT_SCHEMA, FakeJev, FakeProvider

from governance import llm
from governance.dashboard import build_metrics, render_html, render_markdown
from governance.diff import as_new_files
from governance.evaluation import format_report
from governance.jev import JevProvider
from governance.llm import LlmConfig, OpenRouterProvider
from governance.review import evaluate
from governance.usage import UsageLog, summarize

OPENROUTER = LlmConfig(provider="openrouter", model="google/gemini-3.5-flash-lite",
                       max_attempts=3)
TYPESAFE = LlmConfig(provider="typesafe", model="jev-1.13.0", max_attempts=2)

# Formato real devolvido pelas duas APIs (sondado em 2026-10-05).
OPENROUTER_USAGE = {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5,
                    "cost": 3.7e-06, "is_byok": False, "cost_details": {"upstream": 3.7e-06}}
JEV_USAGE = {"input_tokens": 284, "output_tokens": 20}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def api(monkeypatch):
    state = {"responses": []}

    def urlopen(request, timeout):
        return FakeResponse(json.dumps(state["responses"].pop(0)).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm.time, "sleep", lambda _s: None)
    return state


def completion(content, finish="stop", usage=OPENROUTER_USAGE):
    return {"choices": [{"finish_reason": finish, "message": {"content": content}}],
            "usage": usage}


def test_openrouter_records_tokens_and_the_cost_the_provider_reports(api):
    api["responses"] = [completion('{"summary": "ok", "findings": []}')]
    provider = OpenRouterProvider(OPENROUTER, "k")
    provider.review("s", "u", {})
    assert provider.usage.rows() == [{
        "provider": "openrouter", "model": "google/gemini-3.5-flash-lite", "calls": 1,
        "input_tokens": 4, "output_tokens": 1, "cost_usd": 3.7e-06}]


def test_every_billed_attempt_counts_even_when_the_answer_is_unusable(api):
    api["responses"] = [completion('{"summary": "', finish="length")] * OPENROUTER.max_attempts
    provider = OpenRouterProvider(OPENROUTER, "k")
    with pytest.raises(ValueError):
        provider.review("s", "u", {})
    [row] = provider.usage.rows()
    assert row["calls"] == 3 and row["input_tokens"] == 12
    assert row["cost_usd"] == pytest.approx(1.11e-05)


def test_jev_records_tokens_without_a_price(api):
    api["responses"] = [{"model": "jev-1.13.0", "usage": JEV_USAGE,
                         "answers": {"l4": {"type": "noul", "noul": 0.9}}}]
    provider = JevProvider(TYPESAFE, "k")
    provider.nouls({"codigo": "x"}, {"l4": "q"})
    assert provider.usage.rows() == [{
        "provider": "typesafe", "model": "jev-1.13.0", "calls": 1, "input_tokens": 284,
        "output_tokens": 20, "cost_usd": None}]


def test_missing_or_malformed_usage_is_recorded_as_a_call_without_numbers(api):
    api["responses"] = [{"choices": [{"finish_reason": "stop",
                                      "message": {"content": '{"findings": []}'}}],
                         "usage": {"prompt_tokens": "muitos", "cost": "caro"}}]
    provider = OpenRouterProvider(OPENROUTER, "k")
    provider.review("s", "u", {})
    [row] = provider.usage.rows()
    assert (row["calls"], row["input_tokens"], row["output_tokens"], row["cost_usd"]) == (
        1, 0, 0, None)


def test_summarize_adds_providers_and_never_invents_a_price():
    openrouter, jev = UsageLog(), UsageLog()
    openrouter.record("openrouter", "m1", input_tokens=100, output_tokens=10, cost_usd=0.001)
    openrouter.record("openrouter", "m1", input_tokens=50, output_tokens=5, cost_usd=0.0005)
    jev.record("typesafe", "jev", input_tokens=300, output_tokens=30)

    class Holder:
        def __init__(self, usage):
            self.usage = usage

    total = summarize(Holder(openrouter), Holder(jev), FakeProvider(), None)
    assert (total["calls"], total["input_tokens"], total["output_tokens"]) == (3, 450, 45)
    assert total["cost_usd"] == pytest.approx(0.0015)
    assert [r["provider"] for r in total["providers"]] == ["openrouter", "typesafe"]
    assert summarize(Holder(jev))["cost_usd"] is None
    assert summarize(None, FakeProvider()) == {
        "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": None, "providers": []}


def test_result_carries_ai_usage_and_stays_valid(policies, bundle, api):
    api["responses"] = [completion('{"summary": "ok", "findings": []}')]
    provider = OpenRouterProvider(OPENROUTER, "k")
    provider.review("s", "u", {})
    usecase = {"app/src/main/java/com/x/application/usecase/CriarCliente.java":
               'class CriarCliente { void run(Cliente c) { logger.info("{}", c); } }\n'}
    outcome = evaluate(
        as_new_files(usecase), policies=policies, waivers=[], provider=provider,
        jev_provider=FakeJev(), bundle=bundle,
        subject={"repository": "org/app", "commit": "abc", "base": "main", "pull_request": 1},
        governance_ref="v1.10.0", policies_digest="0" * 64, llm_required=True)
    Draft202012Validator(RESULT_SCHEMA).validate(outcome)
    usage = outcome["stats"]["ai_usage"]
    assert usage["calls"] >= 1 and usage["cost_usd"] is not None
    assert usage["providers"][0]["provider"] == "openrouter"
    assert outcome["schema_version"] == "1.3"


def test_eval_report_prints_the_consumption_of_the_run():
    report = {"mode": "llm", "cases": 2, "repeat": 1, "metrics": {}, "stability": {},
              "ai_usage": {"calls": 4, "input_tokens": 900, "output_tokens": 40,
                           "cost_usd": 0.0021, "providers": []}}
    assert "Consumo de IA: 4 chamadas, 900 tokens de entrada, 40 de saída, US$ 0.0021" \
        in format_report(report)


def with_usage(pr, rows):
    base = result(pr, violations=[finding("FIN-MONEY-001")])
    base["stats"] = {"ai_usage": {"providers": rows}}
    return {"result": base, "created_at": f"2026-10-{pr:02d}"}


def test_dashboard_sums_ai_cost_and_averages_over_priced_prs(policies):
    openrouter = {"provider": "openrouter", "model": "m1", "calls": 2, "input_tokens": 100,
                  "output_tokens": 10, "cost_usd": 0.002}
    jev = {"provider": "typesafe", "model": "jev", "calls": 3, "input_tokens": 300,
           "output_tokens": 30, "cost_usd": None}
    results = [with_usage(1, [openrouter, jev]), with_usage(2, [openrouter]),
               with_usage(3, [jev]), {"result": result(4), "created_at": "2026-10-04"}]
    metrics = build_metrics(policies, results, [], [], today=date(2026, 10, 30),
                            window_days=90, repositories=[REPO], cases=[])
    ai = metrics["overview"]["ai_cost"]
    assert ai["evaluations_with_ai"] == 3 and ai["calls"] == 10
    assert ai["cost_usd"] == pytest.approx(0.004)
    assert ai["cost_per_pr_usd"] == pytest.approx(0.002)  # 2 PRs com preço, não 3
    assert [m["model"] for m in ai["by_model"]] == ["m1", "jev"]
    assert "US$ 0.0040 em 3 PR(s)" in render_markdown(metrics)
    assert "Custo de IA por modelo" in render_html(metrics)


def test_dashboard_without_ai_usage_says_so(policies):
    metrics = build_metrics(policies, [{"result": result(1), "created_at": "a"}], [], [],
                            today=date(2026, 10, 30), window_days=90, repositories=[REPO],
                            cases=[])
    assert metrics["overview"]["ai_cost"]["cost_usd"] is None
    assert "nenhuma avaliação com IA na janela" in render_markdown(metrics)
