"""Camada T0: regras determinísticas declaradas nas políticas.

Tipos de regra (`enforcement.deterministic[].type`):
- regex: aplicada a cada linha ADICIONADA. `strip` remove trechos antes do teste
  (ex.: literais de string, chamadas a mask()); `exclude` descarta a linha;
  `validator` (cpf, cnpj, pan) exige que algum trecho casado passe na validação.
- path_changed: um único achado por política, listando os arquivos do escopo alterados,
  removidos ou renomeados (`change_types` restringe: added, modified, deleted, renamed).
- requires_companion: se um arquivo do escopo muda (ou tem linha adicionada que casa com
  `trigger`), o PR precisa alterar também algum arquivo que case com `companion`. Com
  grupos nomeados `key`, `key2`... no trigger, só conta o que não existia na base (ex.:
  dependência nova, e não troca de versão).
- contract: compara a versão da base com a do PR (`format`: openapi ou avro) e aponta
  cada mudança incompatível (contracts.py).
- structured: lê a estrutura do arquivo (blocos do Terraform, contêineres do Kubernetes);
  cada `check` e seus `params` estão em structured.py.
- external: aplicada fora do motor (ex.: ArchUnit no build do repo-alvo). Só documenta.
"""

import re

from .contracts import ContractError, breaking_changes
from .model import Finding
from .policy import glob_match, in_scope
from .structured import run_structured
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


def _companion_finding(policy, rule, scoped, files):
    trigger = re.compile(rule["trigger"]) if rule.get("trigger") else None
    hit = None
    for changed_file in scoped:
        if trigger is None:
            hit = hit or (changed_file.path, None)
            continue
        for line_no, text in sorted(changed_file.added_lines.items()):
            match = trigger.search(text)
            if not match:
                continue
            key = next((v for k, v in match.groupdict().items() if k.startswith("key") and v),
                       None)
            if key and changed_file.base_content and key in changed_file.base_content:
                continue
            hit = (changed_file.path, line_no)
            break
        if hit:
            break
    if hit is None:
        return []
    companions = [f for f in files if not f.deleted
                  and any(glob_match(f.path, g) for g in rule["companion"])]
    if companions:
        return []
    return [Finding(policy.id, policy.severity, hit[0], hit[1], rule["message"],
                    "deterministic")]


def _contract_findings(policy, rule, changed_file):
    if changed_file.deleted:
        return [Finding(policy.id, policy.severity, changed_file.path, None,
                        f"{rule['message']}: contrato removido", "deterministic")]
    if changed_file.base_content is None:
        return []
    try:
        breaks = breaking_changes(rule["format"], changed_file.base_content,
                                  changed_file.content)
    except ContractError as exc:
        breaks = [f"contrato ilegível no PR ({exc})"]
    return [Finding(policy.id, policy.severity, changed_file.path, None,
                    f"{rule['message']}: {detail}", "deterministic") for detail in breaks]


def run_deterministic(policies, files):
    findings, seen = [], set()
    changed = [f for f in files if f.status != "context"]
    for policy in policies:
        scoped = [f for f in changed if in_scope(policy, f.path)]
        for rule in policy.deterministic:
            if rule["type"] == "regex":
                produced = [x for f in scoped for x in _regex_findings(policy, rule, f)]
            elif rule["type"] == "path_changed":
                kinds = rule.get("change_types")
                paths = [f.path for f in scoped if not kinds or f.status in kinds]
                produced = [_path_finding(policy, rule, paths)] if paths else []
            elif rule["type"] == "requires_companion" and scoped:
                produced = _companion_finding(policy, rule, scoped, changed)
            elif rule["type"] == "structured":
                produced = run_structured(policy, rule, scoped, files)
            elif rule["type"] == "contract":
                produced = [x for f in scoped for x in _contract_findings(policy, rule, f)]
            else:
                continue
            for finding in produced:
                # sem linha (contrato, caminho), cada mensagem é um achado distinto
                key = (finding.policy_id, finding.file, finding.line,
                       finding.message if finding.line is None else None)
                if key not in seen:
                    seen.add(key)
                    findings.append(finding)
    return findings
