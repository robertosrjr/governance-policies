"""Mudanças incompatíveis entre a versão da base e a do PR de um contrato (ADR-API-001).

Cobre as quebras mais comuns, sem ferramenta externa, para que o resultado seja
reproduzível e testável no eval:
- OpenAPI 3: caminho ou operação removidos, parâmetro obrigatório novo, corpo de request
  que passa a ser obrigatório ou ganha propriedade obrigatória, resposta 2xx removida,
  propriedade removida ou com tipo alterado na resposta 2xx (JSON, com $ref local).
- Avro: campo novo sem default, campo removido sem default, tipo alterado sem promoção
  válida, símbolo de enum removido (compatibilidade FULL entre as duas versões).
O que não está na lista (oneOf, allOf, callbacks, headers de resposta) não é comparado.
"""

import json

import yaml

HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
AVRO_PROMOTIONS = {("int", "long"), ("int", "float"), ("int", "double"), ("long", "float"),
                   ("long", "double"), ("float", "double"), ("string", "bytes"),
                   ("bytes", "string")}


class ContractError(ValueError):
    """O contrato do PR não pôde ser lido."""


def _load(text, fmt):
    try:
        data = json.loads(text) if fmt == "avro" else yaml.safe_load(text)
    except (ValueError, yaml.YAMLError) as exc:
        raise ContractError(str(exc).splitlines()[0]) from None
    if not isinstance(data, (dict, list)):
        raise ContractError("conteúdo não é um objeto")
    return data


# ---------------------------------------------------------------- OpenAPI

def _resolve(spec, node, depth=0):
    while isinstance(node, dict) and "$ref" in node and depth < 20:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            return {}
        node = spec
        for part in ref[2:].split("/"):
            node = node.get(part, {}) if isinstance(node, dict) else {}
        depth += 1
    return node if isinstance(node, dict) else {}


def _json_schema(spec, holder):
    content = _resolve(spec, holder).get("content") or {}
    media = next((v for k, v in content.items() if "json" in k), None)
    return _resolve(spec, (media or {}).get("schema") or {})


def _params(spec, path_item, operation):
    params = {}
    for raw in [*(path_item.get("parameters") or []), *(operation.get("parameters") or [])]:
        p = _resolve(spec, raw)
        if "name" in p:
            params[(p.get("in"), p["name"])] = bool(p.get("required"))
    return params


def _openapi_breaks(old, new):
    breaks = []
    old_paths, new_paths = old.get("paths") or {}, new.get("paths") or {}
    for path, old_item in old_paths.items():
        if path not in new_paths:
            breaks.append(f"caminho removido: {path}")
            continue
        old_item, new_item = _resolve(old, old_item), _resolve(new, new_paths[path])
        for method in HTTP_METHODS:
            if method not in old_item:
                continue
            op = f"{method.upper()} {path}"
            if method not in new_item:
                breaks.append(f"operação removida: {op}")
                continue
            old_op, new_op = old_item[method] or {}, new_item[method] or {}
            old_params = _params(old, old_item, old_op)
            for key, required in _params(new, new_item, new_op).items():
                if required and not old_params.get(key):
                    breaks.append(f"{op}: parâmetro obrigatório novo '{key[1]}' ({key[0]})")
            old_body, new_body = (_resolve(old, old_op.get("requestBody") or {}),
                                  _resolve(new, new_op.get("requestBody") or {}))
            if new_body.get("required") and old_body and not old_body.get("required"):
                breaks.append(f"{op}: corpo da requisição passou a ser obrigatório")
            old_req = set(_json_schema(old, old_body).get("required") or [])
            for name in sorted(set(_json_schema(new, new_body).get("required") or []) - old_req):
                breaks.append(f"{op}: propriedade obrigatória nova no corpo '{name}'")
            new_responses = new_op.get("responses") or {}
            for status, old_resp in (old_op.get("responses") or {}).items():
                if not str(status).startswith("2"):
                    continue
                if status not in new_responses:
                    breaks.append(f"{op}: resposta {status} removida")
                    continue
                old_props = _json_schema(old, old_resp).get("properties") or {}
                new_props = _json_schema(new, new_responses[status]).get("properties") or {}
                for name, old_prop in old_props.items():
                    if name not in new_props:
                        breaks.append(f"{op}: propriedade removida da resposta {status} '{name}'")
                        continue
                    old_type = _resolve(old, old_prop).get("type")
                    new_type = _resolve(new, new_props[name]).get("type")
                    if old_type and new_type and old_type != new_type:
                        breaks.append(f"{op}: tipo de '{name}' na resposta {status} mudou de "
                                      f"{old_type} para {new_type}")
    return breaks


# ---------------------------------------------------------------- Avro

def _avro_kind(schema):
    if isinstance(schema, str):
        return schema
    if isinstance(schema, list):
        return "union"
    if isinstance(schema, dict):
        return schema.get("type") if schema.get("type") not in ("record", "enum", "fixed") \
            else f"{schema['type']}:{schema.get('name')}"
    return None


def _avro_breaks(old, new, where, named_old, named_new):
    for schema, named in ((old, named_old), (new, named_new)):
        if isinstance(schema, dict) and schema.get("name"):
            named.setdefault(schema["name"], schema)
    old = named_old.get(old, old) if isinstance(old, str) else old
    new = named_new.get(new, new) if isinstance(new, str) else new
    old_kind, new_kind = _avro_kind(old), _avro_kind(new)
    if old_kind != new_kind:
        if (old_kind, new_kind) in AVRO_PROMOTIONS:
            return []
        return [f"{where}: tipo mudou de {old_kind} para {new_kind}"]
    breaks = []
    if old_kind == "union":
        old_branches = {_avro_kind(b) for b in old}
        new_branches = {_avro_kind(b) for b in new}
        breaks += [f"{where}: tipo {b} removido da união"
                   for b in sorted(map(str, old_branches - new_branches))]
    elif old_kind.startswith("enum:"):
        breaks += [f"{where}: símbolo removido do enum '{s}'"
                   for s in old.get("symbols", []) if s not in new.get("symbols", [])]
    elif old_kind.startswith("record:"):
        old_fields = {f["name"]: f for f in old.get("fields", [])}
        new_fields = {f["name"]: f for f in new.get("fields", [])}
        for name, field in new_fields.items():
            if name not in old_fields and "default" not in field:
                breaks.append(f"{where}.{name}: campo novo sem default")
        for name, field in old_fields.items():
            if name not in new_fields:
                if "default" not in field:
                    breaks.append(f"{where}.{name}: campo removido sem default")
                continue
            breaks += _avro_breaks(field["type"], new_fields[name]["type"], f"{where}.{name}",
                                   named_old, named_new)
    elif old_kind in ("array", "map"):
        key = "items" if old_kind == "array" else "values"
        breaks += _avro_breaks(old.get(key), new.get(key), f"{where}[]", named_old, named_new)
    return breaks


def breaking_changes(fmt, old_text, new_text):
    """Lista de quebras de `old_text` para `new_text`. Base ilegível: nada a comparar."""
    new = _load(new_text, fmt)
    try:
        old = _load(old_text, fmt)
    except ContractError:
        return []
    if fmt == "openapi":
        if not isinstance(old, dict) or not isinstance(new, dict):
            return []
        return _openapi_breaks(old, new)
    name = old.get("name", "registro") if isinstance(old, dict) else "registro"
    return _avro_breaks(old, new, name, {}, {})
