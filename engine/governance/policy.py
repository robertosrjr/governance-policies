"""Carga, validação e seleção de políticas.

A seleção é determinística: uma política é avaliada quando algum arquivo alterado casa
com `scope.include` e não casa com `scope.exclude`. Não há busca vetorial: o conjunto de
políticas avaliadas em um PR é reproduzível e auditável.
"""

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from .model import GovernanceError, Policy

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "policies" / "schema" / "policy.schema.json"


@lru_cache(maxsize=512)
def _glob_regex(pattern):
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def glob_match(path, pattern):
    """Glob estilo gitignore com suporte a `**` (independe da versão do Python)."""
    return bool(_glob_regex(pattern).match(path.replace("\\", "/")))


def in_scope(policy, path):
    return any(glob_match(path, p) for p in policy.include) and not any(
        glob_match(path, p) for p in policy.exclude
    )


def _schema_validator():
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def _to_policy(data):
    enforcement = data.get("enforcement", {})
    scope = data["scope"]
    return Policy(
        id=data["id"],
        title=data["title"],
        version=data["version"],
        owner=data["owner"],
        adr=data["adr"],
        severity=data["severity"],
        mode=data["mode"],
        include=tuple(scope["include"]),
        exclude=tuple(scope.get("exclude", ())),
        description=data["description"].strip(),
        remediation=data["remediation"].strip(),
        deterministic=tuple(enforcement.get("deterministic", ())),
        llm=enforcement.get("llm"),
        targets=tuple(data["targets"]),
        raw=data,
    )


def _semantic_errors(data, path, adrs_dir):
    errors = []
    if path.stem != data["id"]:
        errors.append(f"{path.name}: nome do arquivo deve ser {data['id']}.yaml")
    if adrs_dir and not list(adrs_dir.glob(f"{data['adr']}-*.md")):
        errors.append(f"{path.name}: ADR {data['adr']} não encontrado em {adrs_dir}")
    for rule in data.get("enforcement", {}).get("deterministic", ()):
        for key in ("pattern", "exclude", "strip", "trigger"):
            if key in rule:
                try:
                    re.compile(rule[key])
                except re.error as exc:
                    errors.append(f"{path.name}: regex inválida em {key}: {exc}")
    llm = data.get("enforcement", {}).get("llm")
    if llm and "candidates" in llm:
        try:
            re.compile(llm["candidates"])
        except re.error as exc:
            errors.append(f"{path.name}: regex inválida em llm.candidates: {exc}")
    if llm and llm.get("blocking") and not llm.get("eval_evidence"):
        errors.append(f"{path.name}: llm.blocking=true exige llm.eval_evidence (resultado de eval)")
    return errors


def load_policies(policies_dir, adrs_dir=None):
    """Carrega e valida todas as políticas. Qualquer erro invalida o bundle inteiro."""
    policies_dir = Path(policies_dir)
    validator = _schema_validator()
    policies, errors = [], []
    for path in sorted(policies_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        schema_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if schema_errors:
            errors += [f"{path.name}: {'/'.join(map(str, e.path)) or '<raiz>'}: {e.message}"
                       for e in schema_errors]
            continue
        errors += _semantic_errors(data, path, Path(adrs_dir) if adrs_dir else None)
        policies.append(_to_policy(data))
    ids = [p.id for p in policies]
    errors += [f"id duplicado: {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    if errors:
        raise GovernanceError("Políticas inválidas:\n  " + "\n  ".join(errors))
    if not policies:
        raise GovernanceError(f"Nenhuma política encontrada em {policies_dir}")
    return policies


def policies_digest(policies_dir):
    """SHA-256 do conjunto de políticas: identifica exatamente o que foi avaliado."""
    digest = hashlib.sha256()
    for path in sorted(Path(policies_dir).glob("*.yaml")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def select_policies(policies, files, target):
    """Políticas do alvo `target` com ao menos um arquivo alterado (ou removido) no escopo."""
    return [p for p in policies
            if target in p.targets and any(in_scope(p, f.path) for f in files)]
