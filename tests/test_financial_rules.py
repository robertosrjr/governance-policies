import pytest

from governance.deterministic import run_deterministic
from governance.diff import as_new_files
from governance.evaluation import load_cases
from governance.redact import redact
from governance.validators import is_cnpj, is_cpf, is_pan


@pytest.mark.parametrize("value,expected", [
    ("123.456.789-09", True),
    ("12345678909", True),
    ("123.456.789-00", False),
    ("111.111.111-11", False),
    ("1234567890", False),
])
def test_cpf(value, expected):
    assert is_cpf(value) is expected


def test_cnpj():
    assert is_cnpj("11.222.333/0001-81")
    assert not is_cnpj("11.222.333/0001-80")
    assert not is_cnpj("00000000000000")


@pytest.mark.parametrize("value,expected", [
    ("4532 3994 9366 5645", True),
    ("4532399493665646", False),   # Luhn inválido
    ("4111111111111111", False),   # número de teste da bandeira
    ("1727600000000", False),      # timestamp: prefixo fora das bandeiras
])
def test_pan(value, expected):
    assert is_pan(value) is expected


def test_redact_removes_personal_data_but_keeps_its_kind():
    text = ('log.info("cpf 123.456.789-09 cartao 4532 3994 9366 5645 '
            'cnpj 11.222.333/0001-81 email joao@banco.com.br")')
    out = redact(text)
    for kept in ("[CPF REMOVIDO]", "[CARTÃO REMOVIDO]", "[CNPJ REMOVIDO]", "[EMAIL REMOVIDO]"):
        assert kept in out
    for gone in ("123.456.789-09", "4532 3994", "0001-81", "joao@"):
        assert gone not in out


def test_redact_keeps_numbers_that_are_not_personal_data():
    text = "ts=1727600000000 cpfInvalido=123.456.789-00 versao=3.14 teste=4111111111111111"
    assert redact(text) == text


@pytest.mark.parametrize("case_id,policy_id", [
    ("fin-money-001-double-e-divide", "FIN-MONEY-001"),
    ("sec-crypto-001-apis-inseguras", "SEC-CRYPTO-001"),
    ("sec-config-001-producao-insegura", "SEC-CONFIG-001"),
])
def test_every_rule_of_the_policy_fires_on_its_positive_case(policies, case_id, policy_id):
    """O eval confere a política; aqui cada regra dela precisa ter produzido um achado."""
    case = next(c for c in load_cases() if c.id == case_id)
    policy = next(p for p in policies if p.id == policy_id)
    findings = run_deterministic([policy], as_new_files(case.files))
    fired = {f.message for f in findings}
    expected = {r["message"] for r in policy.deterministic}
    assert fired == expected


def test_validator_suppresses_regex_match_that_fails_validation(policies):
    policy = next(p for p in policies if p.id == "LGPD-DATA-001")
    files = as_new_files({"a.csv": "123.456.789-00\n", "b.csv": "x;123.456.789-09\n"})
    assert [f.file for f in run_deterministic([policy], files)] == ["b.csv"]
