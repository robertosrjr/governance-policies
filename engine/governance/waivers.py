"""Waivers: exceções aprovadas, com escopo, aprovador, validade e trilha no git.

Substitui o override por comentário no PR. Um waiver só vale quando:
- está no repositório central (protegido por CODEOWNERS);
- quem aprovou é diferente de quem pediu;
- não expirou e a validade total não passa de MAX_DAYS;
- casa repositório, política e caminho do achado (e o commit, se informado).
"""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from .model import GovernanceError
from .policy import glob_match

MAX_DAYS = 90
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "waivers" / "schema" / "waiver.schema.json"


@dataclass(frozen=True)
class Waiver:
    id: str
    policy_id: str
    repository: str
    paths: tuple
    justification: str
    requested_by: str
    approved_by: str
    created: date
    expires: date
    commit: str | None = None

    def covers(self, finding, repository, commit):
        return (
            finding.policy_id == self.policy_id
            and repository.lower() == self.repository.lower()
            and any(glob_match(finding.file, p) for p in self.paths)
            and (self.commit is None or (commit or "").startswith(self.commit))
        )


def _problems(waiver, today):
    problems = []
    if waiver.approved_by.lower() == waiver.requested_by.lower():
        problems.append("aprovador igual ao solicitante")
    if waiver.expires < waiver.created:
        problems.append("expira antes de ser criado")
    if (waiver.expires - waiver.created).days > MAX_DAYS:
        problems.append(f"validade acima de {MAX_DAYS} dias")
    if waiver.expires < today:
        problems.append(f"expirado em {waiver.expires.isoformat()}")
    return problems


def load_waivers(waivers_dir, policy_ids, today=None, strict=False):
    """Retorna (válidos, avisos). Com strict=True, qualquer problema vira erro (CI do repo central)."""
    today = today or date.today()
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    valid, warnings = [], []
    for path in sorted(Path(waivers_dir).glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data = {k: v.isoformat() if isinstance(v, date) else v for k, v in raw.items()}
        errors = [e.message for e in validator.iter_errors(data)]
        try:
            created, expires = date.fromisoformat(data["created"]), date.fromisoformat(data["expires"])
        except (KeyError, TypeError, ValueError):
            errors.append("created/expires devem ser datas AAAA-MM-DD")
        if errors:
            warnings.append(f"{path.name}: inválido ({'; '.join(errors)})")
            continue
        waiver = Waiver(
            id=data["id"], policy_id=data["policy_id"], repository=data["repository"],
            paths=tuple(data["paths"]), justification=data["justification"],
            requested_by=data["requested_by"], approved_by=data["approved_by"],
            created=created, expires=expires, commit=data.get("commit"),
        )
        problems = _problems(waiver, today)
        if waiver.policy_id not in policy_ids:
            problems.append(f"política desconhecida {waiver.policy_id}")
        if problems:
            warnings.append(f"{waiver.id}: ignorado ({'; '.join(problems)})")
            continue
        valid.append(waiver)
    if strict and warnings:
        raise GovernanceError("Waivers inválidos:\n  " + "\n  ".join(warnings))
    return valid, warnings


def apply_waivers(findings, waivers, repository, commit):
    for finding in findings:
        match = next((w for w in waivers if w.covers(finding, repository, commit)), None)
        if match:
            finding.waiver_id = match.id
    return findings
