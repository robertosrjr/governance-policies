import json

import pytest

from governance.cli import main
from governance.evidence import check_result
from governance.model import GovernanceError

REPO, COMMIT = "org/conta", "a" * 40


def approved(**changes):
    result = {
        "schema_version": "1.2",
        "status": "APPROVED",
        "summary": "Aprovado: nenhuma violação nas políticas avaliadas.",
        "subject": {"repository": REPO, "commit": COMMIT, "pull_request": 7},
        "bundle": {"engine_version": "1.6.0", "bundle_version": "1.4.0",
                   "governance_ref": "v1.6.0"},
        "violations": [],
        "errors": [],
    }
    result.update(changes)
    return result


def test_approved_evidence_for_the_same_repo_and_commit_passes():
    assert check_result(approved(), repository="ORG/Conta", commit=COMMIT) == []


@pytest.mark.parametrize("changes,reason", [
    ({"status": "BLOCKED"}, "veredito BLOCKED"),
    ({"subject": {"repository": "org/outro", "commit": COMMIT}}, "outro repositório"),
    ({"subject": {"repository": REPO, "commit": "b" * 40}}, "outro commit"),
    ({"errors": [{"kind": "llm_unavailable"}]}, "erro(s) de execução"),
    ({"violations": [{"blocking": True}]}, "violação bloqueante"),
    ({"bundle": {}}, "governance_ref"),
    ({"schema_version": "9.9"}, "formato desconhecida"),
])
def test_any_doubt_blocks_the_deploy(changes, reason):
    problems = check_result(approved(**changes), repository=REPO, commit=COMMIT)
    assert any(reason in p for p in problems)


def test_non_object_evidence_is_a_configuration_error():
    with pytest.raises(GovernanceError):
        check_result([], repository=REPO, commit=COMMIT)


def test_cli_exit_codes(tmp_path):
    ok, bad = tmp_path / "ok.json", tmp_path / "bad.json"
    ok.write_text(json.dumps(approved()), encoding="utf-8")
    bad.write_text(json.dumps(approved(status="BLOCKED")), encoding="utf-8")
    args = ["verify-evidence", "--repository", REPO, "--commit", COMMIT, "--result"]
    assert main([*args, str(ok)]) == 0
    assert main([*args, str(bad)]) == 1
    assert main([*args, str(tmp_path / "ausente.json")]) == 2
