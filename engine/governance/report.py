"""Saídas para humanos (comentário no PR) e ferramentas (SARIF para o Code Scanning)."""

import html
import re

COMMENT_MARKER = "<!-- governance-review -->"
MAX_COMMENT_CHARS = 60_000
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


def sanitize(text):
    """Remove imagens e links (vetor de exfiltração) e escapa HTML e pipes de tabela."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "[imagem removida]", str(text))
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "[url removida]", text)
    return html.escape(text).replace("|", "\\|").replace("\n", " ")


def _row(finding):
    location = f"{finding['file']}:{finding['line'] if finding['line'] is not None else '-'}"
    flag = "⛔" if finding["blocking"] else ("🔎" if finding["source"] == "llm" else "⚠️")
    cells = [f"{flag} {finding['severity']}", finding["policy_id"], location,
             finding["source"], finding["message"]]
    return "| " + " | ".join(sanitize(c) for c in cells) + " |"


def _table(findings):
    header = ["| Severidade | Política | Local | Origem | Descrição |", "|---|---|---|---|---|"]
    return "\n".join(header + [_row(f) for f in findings])


def _errors_section(result):
    errors = result["errors"]
    only_llm_down = all(e["kind"] == "llm_unavailable" for e in errors)
    if only_llm_down:
        lines = ["### ⚠️ Revisor de IA indisponível",
                 "O PR fica bloqueado porque a revisão não pôde ser concluída (fail-closed)."]
    else:
        lines = ["### ❗ Erros de execução (fail-closed)",
                 "A revisão não pôde ser concluída. O PR fica bloqueado até o erro ser resolvido."]
    if any(v["blocking"] for v in result["violations"]):
        lines.append("Além do erro, as regras que rodaram encontraram violação bloqueante "
                     "(veja **Achados**).")
    else:
        lines.append("As regras que rodaram não encontraram violação bloqueante.")
    actions = {e["action"] for e in errors}
    if len(actions) == 1:  # ex.: os três revisores fora do ar pelo mesmo motivo
        bullets = "\n".join(f"- {sanitize(e['message'])}" for e in errors)
        return "\n\n".join([*lines, bullets, f"**O que fazer:** {sanitize(actions.pop())}"])
    bullets = "\n".join(f"- **{sanitize(e['message'])}** {sanitize(e['action'])}"
                        for e in errors)
    return "\n\n".join([*lines, bullets])


def build_config_error_markdown(message):
    """Comentário quando o motor nem chega a avaliar (ex.: base do diff inexistente)."""
    return "\n\n".join([
        COMMENT_MARKER,
        "## 🛡️ Governança — ❌ Bloqueado",
        "### ❗ Erro de configuração",
        "O motor não conseguiu avaliar o PR, então nenhuma regra rodou. O PR fica bloqueado "
        "(fail-closed).",
        f"```\n{sanitize_block(message)}\n```",
        "Isso costuma ser configuração do pipeline, não do seu código. Rode de novo (Re-run "
        "all jobs no check governance). Se repetir, avise o time de plataforma com o link "
        "desta execução.",
    ])


def sanitize_block(text):
    """Texto dentro de bloco de código: sem crases que fechem o bloco, com limite de tamanho."""
    return str(text).replace("`", "'")[:2000]


def _classification_note(classification):
    if not classification:
        return ""
    note = f" · classe {sanitize(classification['name'])}"
    if classification["source"] == "default":
        note += " (repositório não classificado)"
    if classification["raised"]:
        note += " · endurecidas: " + ", ".join(sanitize(p) for p in classification["raised"])
    return note


def build_markdown(result):
    icon = "✅ Aprovado" if result["status"] == "APPROVED" else "❌ Bloqueado"
    bundle = result["bundle"]
    llm = bundle["llm"]
    parts = [
        COMMENT_MARKER,
        f"## 🛡️ Governança — {icon}",
        sanitize(result["summary"]),
        f"<sub>bundle {bundle['bundle_version']} · motor {bundle['engine_version']} · "
        f"políticas `{bundle['policies_digest'][:12]}` · "
        f"LLM {sanitize(llm['model']) if llm else 'desligado'}"
        f"{' · Jev ' + sanitize(bundle['jev']['model']) if bundle.get('jev') else ''}"
        f"{_classification_note(result.get('classification'))}</sub>",
    ]
    if result["errors"]:
        parts.append(_errors_section(result))
    shown = [v for v in result["violations"] if v["mode"] != "audit"]
    if shown:
        parts.append("### Achados\n" + _table(shown))
    if result["waived"]:
        parts.append("<details><summary>Cobertos por waiver</summary>\n\n"
                     + _table(result["waived"]) + "\n</details>")
    if result["warnings"]:
        parts.append("<details><summary>Avisos</summary>\n\n"
                     + "\n".join(f"- {sanitize(w)}" for w in result["warnings"]) + "\n</details>")
    parts.append("_⛔ bloqueia · ⚠️ não bloqueia · 🔎 achado de LLM (consultivo). "
                 "Exceções: waiver no repositório central, nunca por comentário. "
                 "Achado errado? Em Security → Code scanning, dispense o alerta com o motivo "
                 "\"False positive\": entra na medição da regra (não desbloqueia o PR)._")
    report = "\n\n".join(parts)
    if len(report) > MAX_COMMENT_CHARS:
        report = (report[:MAX_COMMENT_CHARS]
                  + "\n\n_Relatório truncado para exibição. O veredito e a lista completa "
                    "estão no SARIF e no artefato result.json._")
    return report


def _level(finding):
    if finding["blocking"]:
        return "error"
    return "note" if finding["severity"] == "MINOR" else "warning"


def _sarif_result(finding, rule_index):
    location = {"physicalLocation": {"artifactLocation": {"uri": finding["file"]}}}
    if finding["line"]:
        location["physicalLocation"]["region"] = {"startLine": finding["line"]}
    result = {
        "ruleId": finding["policy_id"],
        "ruleIndex": rule_index[finding["policy_id"]],
        "level": _level(finding),
        "message": {"text": finding["message"]},
        "locations": [location],
        "properties": {"source": finding["source"], "mode": finding["mode"],
                       "blocking": finding["blocking"]},
    }
    if finding["waiver_id"]:
        result["suppressions"] = [{"kind": "external",
                                   "justification": f"waiver {finding['waiver_id']}"}]
    return result


def build_sarif(result, policies):
    evaluated = {p["id"] for p in result["policies_evaluated"]}
    rules = [p for p in policies if p.id in evaluated]
    rule_index = {p.id: i for i, p in enumerate(rules)}
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "enterprise-governance",
                "version": result["bundle"]["engine_version"],
                "rules": [{
                    "id": p.id,
                    "name": p.id.replace("-", ""),
                    "shortDescription": {"text": p.title},
                    "fullDescription": {"text": p.description},
                    "help": {"text": p.remediation},
                    "properties": {"severity": p.severity, "mode": p.mode, "adr": p.adr,
                                   "tags": ["governance", p.adr]},
                } for p in rules],
            }},
            "results": [_sarif_result(f, rule_index)
                        for f in result["violations"] + result["waived"]],
        }],
    }
