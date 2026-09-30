"""Camada T0: regras determinísticas declaradas nas políticas.

Tipos de regra (`enforcement.deterministic[].type`):
- regex: aplicada a cada linha ADICIONADA. `strip` remove trechos antes do teste
  (ex.: literais de string, chamadas a mask()); `exclude` descarta a linha;
  `validator` (cpf, cnpj, pan) exige que algum trecho casado passe na validação.
- path_changed: um único achado por política, listando os arquivos do escopo alterados,
  removidos ou renomeados.
- external: aplicada fora do motor (ex.: ArchUnit no build do repo-alvo). Só documenta.
"""

import re

from .model import Finding
from .policy import in_scope
from .validators import VALIDATORS

MAX_LISTED_PATHS = 5


def _regex_findings(policy, rule, changed_file):
    pattern = re.compile(rule["pattern"])
    exclude = re.compile(rule["exclude"]) if rule.get("exclude") else None
    strip = re.compile(rule["strip"]) if rule.get("strip") else None
    validator = VALIDATORS[rule["validator"]] if rule.get("validator") else None
    for line_no, text in sorted(changed_file.added_lines.items()):
        if exclude and exclude.search(text):
            continue
        candidate = strip.sub(" ", text) if strip else text
        if validator:
            hit = any(validator(m.group(0)) for m in pattern.finditer(candidate))
        else:
            hit = pattern.search(candidate)
        if hit:
            yield Finding(policy.id, policy.severity, changed_file.path, line_no,
                          rule["message"], "deterministic")


def _path_finding(policy, rule, paths):
    listed = ", ".join(paths[:MAX_LISTED_PATHS])
    more = f" e mais {len(paths) - MAX_LISTED_PATHS}" if len(paths) > MAX_LISTED_PATHS else ""
    return Finding(policy.id, policy.severity, paths[0], None,
                   f"{rule['message']} ({len(paths)} arquivo(s): {listed}{more})",
                   "deterministic")


def run_deterministic(policies, files):
    findings, seen = [], set()
    for policy in policies:
        scoped = [f for f in files if in_scope(policy, f.path)]
        for rule in policy.deterministic:
            if rule["type"] == "regex":
                produced = [x for f in scoped for x in _regex_findings(policy, rule, f)]
            elif rule["type"] == "path_changed" and scoped:
                produced = [_path_finding(policy, rule, [f.path for f in scoped])]
            else:
                continue
            for finding in produced:
                key = (finding.policy_id, finding.file, finding.line)
                if key not in seen:
                    seen.add(key)
                    findings.append(finding)
    return findings
