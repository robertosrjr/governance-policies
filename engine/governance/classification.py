"""Classificação dos repositórios-alvo (ADR-GOV-009).

A classe de um repositório decide duas coisas: se o código pode ir para um provedor de
IA e quais políticas endurecem. A classificação vive no repositório central; o
repositório-alvo não consegue se declarar numa classe mais branda. Repositório fora da
lista recebe a classe `default`.
"""

from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from .model import GovernanceError

CLASSIFICATION_FILE = Path(__file__).resolve().parents[2] / "classification" / "repositories.yaml"
MODE_RANK = {"audit": 0, "warn": 1, "enforce": 2}


@dataclass(frozen=True)
class Classification:
    name: str
    description: str
    llm: bool
    raise_mode: dict = field(default_factory=dict)
    source: str = "listed"  # "listed" (no arquivo) | "default" (repositório fora da lista)

    def as_dict(self, raised=()):
        return {"name": self.name, "source": self.source, "llm": self.llm,
                "raised": {pid: self.raise_mode[pid] for pid in sorted(raised)}}


@dataclass(frozen=True)
class Catalog:
    default: str
    classes: dict
    repositories: dict

    def for_repository(self, repository):
        name = self.repositories.get((repository or "").lower())
        source = "listed" if name else "default"
        return replace(self.classes[name or self.default], source=source)


def load_catalog(policies, path=CLASSIFICATION_FILE):
    """Carrega e valida. Qualquer inconsistência invalida o bundle (fail-closed)."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise GovernanceError(f"Classificação ilegível ({path}): {exc}") from exc
    by_id = {p.id: p for p in policies}
    problems, classes = [], {}
    for name, spec in (data.get("classes") or {}).items():
        if not isinstance(spec, dict) or not isinstance(spec.get("llm"), bool):
            problems.append(f"classe {name}: `llm` (true/false) é obrigatório")
            continue
        raise_mode = spec.get("raise_mode") or {}
        for pid, mode in raise_mode.items():
            policy = by_id.get(pid)
            if policy is None:
                problems.append(f"classe {name}: política desconhecida {pid}")
            elif mode not in MODE_RANK:
                problems.append(f"classe {name}: modo inválido {mode} para {pid}")
            elif MODE_RANK[mode] <= MODE_RANK[policy.mode]:
                problems.append(f"classe {name}: {pid} já está em {policy.mode}; a classe só "
                                "pode endurecer uma política")
        classes[name] = Classification(name=name, description=str(spec.get("description", "")),
                                       llm=spec["llm"], raise_mode=dict(raise_mode))
    default = data.get("default")
    if default not in classes:
        problems.append(f"classe padrão `{default}` não existe")
    repositories = {}
    for repo, name in (data.get("repositories") or {}).items():
        if name not in classes:
            problems.append(f"{repo}: classe desconhecida {name}")
        repositories[str(repo).lower()] = name
    if problems:
        raise GovernanceError("Classificação inválida:\n  " + "\n  ".join(problems))
    return Catalog(default=default, classes=classes, repositories=repositories)


def apply_classification(policies, classification):
    """Políticas com o modo endurecido pela classe e os ids que mudaram."""
    effective, raised = [], []
    for policy in policies:
        mode = classification.raise_mode.get(policy.id)
        if mode and MODE_RANK[mode] > MODE_RANK[policy.mode]:
            effective.append(replace(policy, mode=mode))
            raised.append(policy.id)
        else:
            effective.append(policy)
    return effective, raised
