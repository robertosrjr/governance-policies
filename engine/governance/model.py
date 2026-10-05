"""Tipos compartilhados entre as camadas do motor."""

from dataclasses import dataclass, field

SEVERITIES = ("CRITICAL", "MAJOR", "MINOR")
MODES = ("enforce", "warn", "audit")


@dataclass(frozen=True)
class ChangedFile:
    """Arquivo alterado no PR: conteúdo final e linhas adicionadas (nº da linha -> texto).

    `status`: added | modified | deleted | renamed | context. `context` é um arquivo que o
    PR NÃO alterou, lido só para as regras estruturais enxergarem o módulo inteiro (ex.:
    o `default_tags` do provider, no mesmo diretório): não seleciona política nem é achado.
    `base_content`: conteúdo na base do PR (arquivos modificados ou renomeados), usado por
    regras que comparam versões.
    """

    path: str
    content: str
    added_lines: dict = field(default_factory=dict)
    deleted: bool = False
    status: str = "modified"
    base_content: str | None = None


@dataclass(frozen=True)
class Policy:
    id: str
    title: str
    version: str
    owner: str
    adr: str
    severity: str
    mode: str
    include: tuple
    exclude: tuple
    description: str
    remediation: str
    deterministic: tuple
    llm: dict | None
    targets: tuple
    raw: dict

    @property
    def llm_blocking(self):
        return bool(self.llm and self.llm.get("blocking"))

    @property
    def llm_engine(self):
        """None (sem LLM), "generative" (revisor que aponta achados) ou "jev" (ADR-GOV-002)."""
        return self.llm.get("engine", "generative") if self.llm else None


@dataclass
class Finding:
    policy_id: str
    severity: str
    file: str
    line: int | None
    message: str
    source: str  # "deterministic" | "llm"
    blocking: bool = False
    waiver_id: str | None = None

    def as_dict(self):
        return {
            "policy_id": self.policy_id,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "source": self.source,
            "blocking": self.blocking,
            "waiver_id": self.waiver_id,
        }


@dataclass(frozen=True)
class RunError:
    """Erro de execução: sempre bloqueia (fail-closed), mas não é defeito no código revisado.

    `kind` diz ao relatório o que explicar; `action` diz a quem abriu o PR o que fazer.
    """

    kind: str  # "llm_unavailable" | "llm_not_configured" | "llm_failure" | "input_too_large" | "secret_scan"
    message: str
    action: str

    def __str__(self):
        return self.message

    def as_dict(self):
        return {"kind": self.kind, "message": self.message, "action": self.action}


class GovernanceError(Exception):
    """Falha que torna o veredito inválido. O pipeline trata como bloqueio (fail-closed)."""
