"""Regras estruturais (`type: structured`): leem a estrutura do arquivo, não a linha.

Uma regex enxerga uma linha; "este recurso tem as tags de custo?" e "este contêiner tem
`requests`?" dependem do bloco inteiro. Cada verificação (`check`) é nomeada e recebe os
parâmetros da própria política (`params`), então quem responde pela regra (FinOps, por
exemplo) muda o que é exigido sem tocar no motor (ADR-FINOPS-001).

Princípio comum: só se aponta o que dá para afirmar olhando os arquivos do PR. Onde o
valor vem de fora (variável, módulo, `for_each`), o motor não afirma nada: um falso
positivo ensina o time a ignorar a regra. O que o PR não alterou também não é apontado:
um bloco só entra se alguma linha dele foi adicionada.

- terraform_tags: recurso de um dos `resource_types` sem as `required_tags`, somando as
  tags do recurso e as `default_tags` do provider do mesmo diretório (o módulo).
- kubernetes_resources: contêiner de workload sem `resources.requests`/`limits`.
"""

import posixpath
import re

import yaml

from .hcl import expression, parse
from .model import Finding

CHECKS = ("terraform_tags", "kubernetes_resources")
K8S_QUANTITIES = ("cpu", "memory", "ephemeral-storage")


def param_problems(rule):
    """Erros de configuração dos parâmetros de uma regra estrutural (usado pelo validate)."""
    check, params, problems = rule.get("check"), rule.get("params") or {}, []

    def string_list(name, allowed=None, required=False):
        values = params.get(name)
        if values is None:
            if required:
                problems.append(f"{check}: params.{name} é obrigatório")
        elif (not isinstance(values, list) or not all(isinstance(v, str) and v for v in values)
              or (required and not values)):
            problems.append(f"{check}: params.{name} deve ser uma lista de textos")
        elif allowed and not set(values) <= set(allowed):
            problems.append(f"{check}: params.{name} aceita só {', '.join(allowed)}")

    if check == "terraform_tags":
        string_list("required_tags", required=True)
        string_list("resource_types", required=True)
        if not isinstance(params.get("attribute", "tags"), str):
            problems.append(f"{check}: params.attribute deve ser texto")
    elif check == "kubernetes_resources":
        string_list("requests", K8S_QUANTITIES)
        string_list("limits", K8S_QUANTITIES)
        if not params.get("requests") and not params.get("limits"):
            problems.append(f"{check}: informe params.requests e/ou params.limits")
    else:
        problems.append(f"check desconhecido: {check}")
    return problems


def run_structured(policy, rule, scoped, everything):
    """`scoped`: arquivos do PR no escopo. `everything`: também os vizinhos de contexto."""
    if rule["check"] == "terraform_tags":
        return _terraform_tags(policy, rule, scoped, everything)
    if rule["check"] == "kubernetes_resources":
        return _kubernetes_resources(policy, rule, scoped)
    return []


def _touched(first, last, changed_file):
    return any(first <= line <= last for line in changed_file.added_lines)


# ---------------------------------------------------------------- Terraform


def _split_arguments(tokens):
    arguments, current, depth = [], [], 0
    for token in tokens:
        if token.kind == "p":
            if token.value in "([{":
                depth += 1
            elif token.value in ")]}":
                depth -= 1
            elif token.value == "," and depth == 0:
                arguments.append(current)
                current = []
                continue
        current.append(token)
    if current:
        arguments.append(current)
    return arguments


def _map_keys(tokens):
    """Chaves de um mapa literal `{ ... }` e se a lista é completa."""
    inner = tokens[1:-1]
    if inner and inner[0].kind == "id" and inner[0].value == "for":
        return set(), False
    keys, complete, i = set(), True, 0
    while i < len(inner):
        key = inner[i]
        following = inner[i + 1] if i + 1 < len(inner) else None
        if (key.kind in ("id", "str") and following is not None and following.kind == "p"
                and following.value in "=:"):
            if key.kind == "str" and ("${" in key.value or "%{" in key.value):
                complete = False
            else:
                keys.add(key.value)
            _, i = expression(inner, i + 2, stop_at_comma=True)
        else:
            if key.kind == "p" and key.value == "(":
                complete = False
            i += 1
    return keys, complete


class _Module:
    """Os blocos dos arquivos .tf de um diretório: o que o Terraform trata como um módulo."""

    def __init__(self, blocks):
        self.providers = [b for b in blocks if b.type == "provider"]
        self.locals = {name: tokens for b in blocks if b.type == "locals"
                       for name, tokens in b.attrs.items()}


def _resolve(tokens, module, depth=0):
    """(chaves, completo) de uma expressão de mapa. Completo=False: há algo que não se sabe."""
    if not tokens or depth > 5:
        return set(), False
    first = tokens[0]
    if first.kind == "p" and first.value == "{" and tokens[-1].kind == "p" \
            and tokens[-1].value == "}":
        return _map_keys(tokens)
    if first.kind == "id":
        wraps = len(tokens) >= 3 and tokens[1].value == "(" and tokens[-1].value == ")"
        if first.value == "merge" and wraps:
            keys, complete = set(), True
            for argument in _split_arguments(tokens[2:-1]):
                found, known = _resolve(argument, module, depth + 1)
                keys |= found
                complete &= known
            return keys, complete
        if first.value == "tomap" and wraps:
            return _resolve(tokens[2:-1], module, depth + 1)
        if first.value.startswith("local.") and len(tokens) == 1:
            return _resolve(module.locals.get(first.value[len("local."):], []), module,
                            depth + 1)
    return set(), False


def _provider_alias(block):
    expr = block.attrs.get("alias")
    return expr[0].value if expr and expr[0].kind == "str" else None


def _resource_alias(block):
    """(alias, conhecido): `provider = aws.west` -> ("west", True)."""
    expr = block.attrs.get("provider")
    if not expr:
        return None, True
    if len(expr) == 1 and expr[0].kind == "id" and "." in expr[0].value:
        return expr[0].value.split(".", 1)[1], True
    return None, False


def _default_tags(module, prefix, alias):
    """(chaves, completo, provider visível) das default_tags do provider do recurso."""
    matches = [p for p in module.providers
               if p.labels and p.labels[0] == prefix and _provider_alias(p) == alias]
    if not matches:
        return set(), True, False
    keys, complete = set(), True
    for provider in matches:
        for inner in provider.blocks:
            if inner.type == "default_tags" and "tags" in inner.attrs:
                found, known = _resolve(inner.attrs["tags"], module)
                keys |= found
                complete &= known
    return keys, complete, True


def _terraform_tags(policy, rule, scoped, everything):
    params = rule["params"]
    required = list(params["required_tags"])
    types = set(params["resource_types"])
    attribute = params.get("attribute", "tags")
    parsed, modules, findings = {}, {}, []

    def blocks_of(changed_file):
        if changed_file.path not in parsed:
            parsed[changed_file.path] = parse(changed_file.content)
        return parsed[changed_file.path]

    def module_of(directory):
        if directory not in modules:
            files = [f for f in everything if f.path.endswith(".tf") and not f.deleted
                     and posixpath.dirname(f.path) == directory]
            modules[directory] = _Module([b for f in files for b in blocks_of(f)])
        return modules[directory]

    for changed in scoped:
        if changed.deleted or not changed.path.endswith(".tf"):
            continue
        module = module_of(posixpath.dirname(changed.path))
        for block in blocks_of(changed):
            if (block.type != "resource" or len(block.labels) != 2
                    or block.labels[0] not in types
                    or not _touched(block.start, block.end, changed)):
                continue
            resource_type, name = block.labels
            if attribute in block.attrs:
                own, own_complete = _resolve(block.attrs[attribute], module)
            else:
                own, own_complete = set(), True
            inherited, inherited_complete, visible = set(), True, True
            if resource_type.startswith("aws_") and attribute == "tags":
                alias, alias_known = _resource_alias(block)
                if alias_known:
                    inherited, inherited_complete, visible = _default_tags(
                        module, "aws", alias)
                else:
                    visible = False
            missing = [tag for tag in required if tag not in own | inherited]
            # Sem o provider no diretório (módulo filho), com variável ou com módulo no
            # meio, o valor final vem de fora: não dá para afirmar que falta.
            if missing and own_complete and inherited_complete and visible:
                findings.append(Finding(
                    policy.id, policy.severity, changed.path, block.start,
                    f"{rule['message']}: {resource_type}.{name} sem {', '.join(missing)}",
                    "deterministic"))
    return findings


# ---------------------------------------------------------------- Kubernetes


class _Mapping(dict):
    start = 0
    end = 0


class _LineLoader(yaml.SafeLoader):
    """SafeLoader que guarda a linha inicial e a final de cada mapeamento."""


def _construct_mapping(loader, node):
    mapping = _Mapping(loader.construct_mapping(node, deep=True))
    mapping.start = node.start_mark.line + 1
    mapping.end = max(mapping.start, node.end_mark.line)
    return mapping


_LineLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)

_POD_TEMPLATE = ("spec", "template", "spec")
WORKLOADS = {
    "Deployment": _POD_TEMPLATE, "StatefulSet": _POD_TEMPLATE, "DaemonSet": _POD_TEMPLATE,
    "ReplicaSet": _POD_TEMPLATE, "Job": _POD_TEMPLATE,
    "CronJob": ("spec", "jobTemplate", "spec", "template", "spec"),
    "Pod": ("spec",),
}
_KIND_LINE = re.compile(r"^\s*kind\s*:", re.M)


def _walk(node, path):
    for key in path:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else None


def _quantities(container, group):
    resources = container.get("resources")
    values = resources.get(group) if isinstance(resources, dict) else None
    return values if isinstance(values, dict) else {}


def _kubernetes_resources(policy, rule, scoped):
    params = rule["params"]
    requests, limits = params.get("requests") or [], params.get("limits") or []
    findings = []
    for changed in scoped:
        if changed.deleted or not changed.path.endswith((".yaml", ".yml")):
            continue
        try:
            documents = list(yaml.load_all(changed.content, Loader=_LineLoader))
        except yaml.YAMLError as exc:
            # Template Helm ou Jinja só vira YAML depois de renderizado: não é o que vai
            # para o cluster. YAML inválido que parece manifesto, esse sim é apontado.
            if "{{" not in changed.content and _KIND_LINE.search(changed.content):
                mark = getattr(exc, "problem_mark", None)
                findings.append(Finding(
                    policy.id, policy.severity, changed.path,
                    mark.line + 1 if mark else None,
                    f"{rule['message']}: manifesto ilegível (YAML inválido)", "deterministic"))
            continue
        for document in documents:
            path = WORKLOADS.get(document.get("kind")) if isinstance(document, dict) else None
            pod = _walk(document, path) if path else None
            containers = pod.get("containers") if pod else None
            if not isinstance(containers, list):
                continue
            workload = f"{document['kind']} '{(document.get('metadata') or {}).get('name', '?')}'"
            for container in containers:
                if not isinstance(container, _Mapping) \
                        or not _touched(container.start, container.end, changed):
                    continue
                missing = (
                    [f"resources.requests.{q}" for q in requests
                     if _quantities(container, "requests").get(q) in (None, "")]
                    + [f"resources.limits.{q}" for q in limits
                       if _quantities(container, "limits").get(q) in (None, "")])
                if missing:
                    findings.append(Finding(
                        policy.id, policy.severity, changed.path, container.start,
                        f"{rule['message']}: {workload}, container "
                        f"'{container.get('name', '?')}' sem {', '.join(missing)}",
                        "deterministic"))
    return findings
