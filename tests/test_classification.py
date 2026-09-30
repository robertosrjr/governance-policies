import json

import pytest
import yaml
from conftest import commit_files
from jsonschema import Draft202012Validator
from test_evaluation_layers import RESULT_SCHEMA, FakeJev, FakeProvider

from governance.classification import CLASSIFICATION_FILE, apply_classification, load_catalog
from governance.cli import main
from governance.diff import as_new_files
from governance.model import GovernanceError
from governance.report import build_markdown
from governance.review import evaluate

PAN_FIXTURE = {"app/src/test/resources/cartoes.json": '{"numero": "4532 3994 9366 5645"}\n'}
TOSTRING_LOG = {
    "app/src/main/java/com/x/application/usecase/CriarCliente.java":
        'class CriarCliente { void run(Cliente c) { logger.info("criado {}", c); } }\n'}


def run(policies, bundle, files, classification, provider=None, jev=None):
    effective, raised = apply_classification(policies, classification)
    result = evaluate(
        as_new_files(files), policies=effective, waivers=[], provider=provider,
        jev_provider=jev, bundle=bundle,
        subject={"repository": "org/app", "commit": "abc", "base": "main", "pull_request": 1},
        governance_ref="v1.9.0", policies_digest="0" * 64, llm_required=True,
        classification=classification, raised=raised)
    Draft202012Validator(RESULT_SCHEMA).validate(result)
    return result


@pytest.fixture(scope="module")
def catalog(policies):
    return load_catalog(policies)


def test_listed_repository_gets_its_class_and_unknown_gets_the_cautious_default(catalog):
    listed = catalog.for_repository("RobertoSRJr/VirtualThreads")
    assert (listed.name, listed.source, listed.llm) == ("interno", "listed", True)
    unknown = catalog.for_repository("org/desconhecido")
    assert (unknown.name, unknown.source, unknown.llm) == ("nao-classificado", "default", False)


def test_restricted_class_makes_card_numbers_block(policies, bundle, catalog):
    interno = run(policies, bundle, PAN_FIXTURE, catalog.classes["interno"], FakeProvider(), FakeJev())
    assert interno["status"] == "APPROVED"
    restrito = run(policies, bundle, PAN_FIXTURE, catalog.classes["restrito"])
    assert restrito["status"] == "BLOCKED"
    assert restrito["classification"]["raised"]["SEC-PAN-001"] == "enforce"
    assert [v["mode"] for v in restrito["violations"] if v["policy_id"] == "SEC-PAN-001"] == ["enforce"]


def test_class_without_llm_skips_semantic_review_without_blocking(policies, bundle, catalog):
    provider, jev = FakeProvider(), FakeJev(probability=0.99)
    result = run(policies, bundle, TOSTRING_LOG, catalog.classes["confidencial"], provider, jev)
    assert result["status"] == "APPROVED" and result["errors"] == []
    assert provider.calls == []
    assert any("revisão por IA desligada" in w for w in result["warnings"])
    assert result["classification"] == {"name": "confidencial", "source": "listed",
                                        "llm": False, "raised": {}}
    assert "classe confidencial" in build_markdown(result)


@pytest.mark.parametrize("change,message", [
    ({"classes": {"restrito": {"llm": False, "raise_mode": {"ARCH-HEX-001": "warn"}}}},
     "só pode endurecer"),
    ({"classes": {"restrito": {"llm": False, "raise_mode": {"NAO-EXISTE-001": "enforce"}}}},
     "política desconhecida"),
    ({"repositories": {"org/app": "ultra-secreto"}}, "classe desconhecida"),
    ({"default": "sem-classe"}, "classe padrão"),
])
def test_inconsistent_classification_invalidates_the_bundle(policies, tmp_path, change, message):
    data = yaml.safe_load(CLASSIFICATION_FILE.read_text(encoding="utf-8"))
    for key, value in change.items():
        data[key] = {**data[key], **value} if isinstance(value, dict) else value
    path = tmp_path / "repositories.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(GovernanceError, match=message):
        load_catalog(policies, path)


def test_review_records_the_class_and_needs_no_ai_key_when_ai_is_off(repo, tmp_path, monkeypatch):
    for var in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/nao-classificado")
    commit_files(repo, TOSTRING_LOG)
    out = tmp_path / "out"
    assert main(["review", "--repo", str(repo), "--base", "main", "--out", str(out)]) == 0
    result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    assert result["schema_version"] == "1.3"
    assert result["classification"]["name"] == "nao-classificado"
    assert result["classification"]["source"] == "default"
