"""Remoção de segredos antes de qualquer envio a um provedor de LLM.

O achado de segredo já é feito pela camada determinística (SEC-SECRET-001); aqui o
objetivo é não vazar a credencial para um terceiro durante a revisão semântica.
"""

import re

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


def redact(text):
    for pattern in SECRET_PATTERNS:
        if pattern.groups == 3:
            text = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}{m.group(3)}", text)
        else:
            text = pattern.sub(REDACTED, text)
    return text
