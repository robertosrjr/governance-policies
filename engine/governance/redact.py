"""Remoção de segredos e dados pessoais antes de qualquer envio a um provedor de LLM.

O achado de segredo já é feito pela camada determinística (SEC-SECRET-001); aqui o
objetivo é não vazar a credencial para um terceiro durante a revisão semântica. CPF,
CNPJ, cartão e e-mail literais também saem: enviar dado de titular a um processador
externo seria um tratamento sem base legal (ADR-GOV-003). O marcador diz o tipo do dado,
para o revisor semântico ainda entender que ali havia um dado pessoal.
"""

import re

from .validators import is_cnpj, is_cpf, is_pan

SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)((?:api[_-]?key|secret|passw(?:or)?d|senha|token|client[_-]?secret)\w*"
               r"\s*[:=]\s*[\"'])([^\"'\s$]{8,})([\"'])"),
)

REDACTED = "[REDACTED]"

PERSONAL_DATA = (
    (re.compile(r"(?<![\w.\-/])\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?![\w\-/]|\.\d)"),
     is_cnpj, "[CNPJ REMOVIDO]"),
    (re.compile(r"(?<![\w.\-/])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\w\-/]|\.\d)"),
     is_cpf, "[CPF REMOVIDO]"),
    (re.compile(r"(?<![\w\-])[3-6](?:[ \-]?\d){12,18}(?![\w\-])"), is_pan, "[CARTÃO REMOVIDO]"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), None, "[EMAIL REMOVIDO]"),
)


def _replace_valid(pattern, validator, marker, text):
    return pattern.sub(lambda m: marker if validator is None or validator(m.group(0))
                       else m.group(0), text)


def redact(text):
    for pattern in SECRET_PATTERNS:
        if pattern.groups == 3:
            text = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}{m.group(3)}", text)
        else:
            text = pattern.sub(REDACTED, text)
    for pattern, validator, marker in PERSONAL_DATA:
        text = _replace_valid(pattern, validator, marker, text)
    return text
