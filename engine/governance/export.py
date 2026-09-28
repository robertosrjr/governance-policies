"""Artefatos derivados das políticas. Nunca edite os arquivos gerados à mão.

- exports/aws-security-agent/governance-pack.json: Custom Security Requirements Pack.
- .claude/rules/governance-policies.md: regras para o Claude Code (shift-left local).
"""

import json
from pathlib import Path

GENERATED_NOTICE = "GERADO por `python -m governance export`. Edite policies/*.yaml."


def aws_security_agent_pack(policies, bundle_version):
    selected = [p for p in policies if "aws-security-agent" in p.targets]
    return {
        "packName": "Enterprise-Governance-Pack",
        "version": bundle_version,
        "description": f"Requisitos organizacionais derivados de policies/. {GENERATED_NOTICE}",
        "securityRequirements": [{
            "name": p.id.lower(),
            "description": f"{p.title}. {p.description}",
            "applicability": p.raw["compliance"].get("applicability",
                                                     "Arquivos: " + ", ".join(p.include)),
            "complianceCriteria": (f"COMPLIANT if {p.raw['compliance']['compliant']} "
                                   f"NON_COMPLIANT if {p.raw['compliance']['non_compliant']}"),
            "remediationGuidance": p.remediation,
        } for p in selected],
    }


def _enforcement_line(policy):
    parts = []
    for rule in policy.deterministic:
        if rule["type"] == "external":
            parts.append(f"{rule['tool']} (`{rule['reference']}`)")
        else:
            parts.append(f"motor ({rule['type']})")
    if policy.llm:
        parts.append("LLM " + ("bloqueante" if policy.llm_blocking else "consultivo"))
    return ", ".join(parts) or "revisão humana / AWS Security Agent"


def claude_rules_markdown(policies):
    selected = [p for p in policies if "claude-code" in p.targets]
    lines = [
        "# Políticas de governança (Claude Code)",
        "",
        f"<!-- {GENERATED_NOTICE} -->",
        "",
        "Ao gerar ou editar código, respeite as políticas abaixo. As `enforce` + `CRITICAL`",
        "bloqueiam o merge no pipeline central; as `warn` aparecem como alerta.",
        "",
    ]
    for p in selected:
        lines += [
            f"## {p.id} — {p.title}",
            f"- Severidade: `{p.severity}` · modo: `{p.mode}` · ADR: `{p.adr}`",
            f"- Escopo: {', '.join(f'`{g}`' for g in p.include)}",
            f"- Verificação: {_enforcement_line(p)}",
            "",
            p.description,
            "",
            f"**Correção:** {p.remediation}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def render_exports(policies, bundle_version, root):
    root = Path(root)
    return {
        root / "exports" / "aws-security-agent" / "governance-pack.json":
            json.dumps(aws_security_agent_pack(policies, bundle_version),
                       ensure_ascii=False, indent=2) + "\n",
        root / ".claude" / "rules" / "governance-policies.md": claude_rules_markdown(policies),
    }


def write_exports(policies, bundle_version, root, check=False):
    """Grava os artefatos. Com check=True, retorna os que estão desatualizados sem gravar."""
    stale = []
    for path, content in render_exports(policies, bundle_version, root).items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    return stale
