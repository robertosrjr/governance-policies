import pytest
from conftest import commit_files, git

from governance.contracts import ContractError, breaking_changes
from governance.deterministic import run_deterministic
from governance.diff import as_new_files, collect_changes
from governance.evaluation import load_cases


def _policy(policies, pid):
    return next(p for p in policies if p.id == pid)


def _case_findings(policies, case_id, pid):
    case = next(c for c in load_cases() if c.id == case_id)
    return run_deterministic([_policy(policies, pid)], as_new_files(case.files, case.base_files))


def test_collect_changes_reports_status_and_base_content(repo):
    commit_files(repo, {"db/migration/V1__a.sql": "CREATE TABLE a (id INT);\n",
                        "db/migration/V2__b.sql": "CREATE TABLE b (id INT);\n",
                        "old.txt": "x\n"})
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "feature")
    git(repo, "checkout", "-q", "-b", "pr")
    commit_files(repo, {"db/migration/V1__a.sql": "CREATE TABLE a (id BIGINT);\n",
                        "db/migration/V3__c.sql": "CREATE TABLE c (id INT);\n"})
    git(repo, "mv", "old.txt", "new.txt")
    git(repo, "rm", "-q", "db/migration/V2__b.sql")
    git(repo, "commit", "-q", "-m", "pr")
    files = {f.path: f for f in collect_changes(repo, "main")}
    assert files["db/migration/V1__a.sql"].status == "modified"
    assert files["db/migration/V1__a.sql"].base_content == "CREATE TABLE a (id INT);\n"
    assert files["db/migration/V3__c.sql"].status == "added"
    assert files["db/migration/V3__c.sql"].base_content is None
    assert files["db/migration/V2__b.sql"].status == "deleted"
    assert files["new.txt"].status == "renamed"
    assert files["new.txt"].base_content == "x\n"


def test_edited_migration_fires_but_new_migration_does_not(policies, repo):
    policy = _policy(policies, "DATA-MIG-001")
    commit_files(repo, {"app/src/main/resources/db/migration/V1__a.sql": "CREATE TABLE a (id INT);\n"})
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "feature")
    git(repo, "checkout", "-q", "-b", "nova")
    commit_files(repo, {"app/src/main/resources/db/migration/V2__b.sql": "CREATE TABLE b (id INT);\n"})
    assert run_deterministic([policy], collect_changes(repo, "main")) == []
    commit_files(repo, {"app/src/main/resources/db/migration/V1__a.sql": "CREATE TABLE a (x INT);\n"})
    findings = run_deterministic([policy], collect_changes(repo, "main"))
    assert [f.file for f in findings] == ["app/src/main/resources/db/migration/V1__a.sql"]


def test_openapi_breaking_changes_are_itemized(policies):
    messages = {f.message.split(": ", 1)[1]
                for f in _case_findings(policies, "api-contract-001-remove-campo", "API-CONTRACT-001")}
    assert messages == {"GET /contas/{id}: parâmetro obrigatório novo 'agencia' (query)",
                        "GET /contas/{id}: propriedade removida da resposta 200 'saldo'"}


def test_avro_breaking_changes_are_itemized(policies):
    messages = {f.message.split(": ", 1)[1]
                for f in _case_findings(policies, "evt-schema-001-quebra", "EVT-SCHEMA-001")}
    assert messages == {"PagamentoRealizado.canal: campo novo sem default",
                        "PagamentoRealizado.valorCentavos: campo removido sem default",
                        "PagamentoRealizado.status: símbolo removido do enum 'ESTORNADO'"}


def test_removed_contract_is_breaking(policies):
    files = as_new_files({"api/openapi.yaml": None}, {"api/openapi.yaml": "openapi: 3.0.3\n"})
    findings = run_deterministic([_policy(policies, "API-CONTRACT-001")], files)
    assert findings and "contrato removido" in findings[0].message


def test_unreadable_contract_in_pr_is_a_finding_not_a_crash():
    with pytest.raises(ContractError):
        breaking_changes("avro", '{"type": "record", "name": "A", "fields": []}', "{quebrado")


def test_openapi_type_change_in_response_is_breaking():
    old = ("paths:\n  /a:\n    get:\n      responses:\n        '200':\n          content:\n"
           "            application/json:\n              schema:\n                properties:\n"
           "                  valor: {type: number}\n")
    assert breaking_changes("openapi", old, old.replace("number", "string")) == [
        "GET /a: tipo de 'valor' na resposta 200 mudou de number para string"]


def test_new_dependency_only_counts_when_absent_from_base(policies):
    assert _case_findings(policies, "gov-adr-001-troca-de-versao", "GOV-ADR-001") == []
    findings = _case_findings(policies, "gov-adr-001-dependencia-nova-sem-adr", "GOV-ADR-001")
    assert [f.message for f in findings] == ["Dependência nova sem ADR no PR."]
    assert findings[0].line is not None


@pytest.mark.parametrize("case_id,policy_id", [
    ("sup-img-001-tag-root-curl", "SUP-IMG-001"),
    ("ai-gw-001-sdk-direto", "AI-GW-001"),
])
def test_every_rule_of_the_policy_fires_on_its_positive_case(policies, case_id, policy_id):
    fired = {f.message for f in _case_findings(policies, case_id, policy_id)}
    assert fired == {r["message"] for r in _policy(policies, policy_id).deterministic}
