"""Agregação dos achados em um veredito e no documento de evidência (result.json).

Regra de bloqueio de um achado:
    política em modo `enforce`
    E severidade CRITICAL
    E (origem determinística OU política com `llm.blocking: true`)
    E sem waiver válido.
Qualquer erro de execução bloqueia (fail-closed).
"""

from . import __version__

# 1.1: `errors` passou de texto para {kind, message, action}.
RESULT_SCHEMA_VERSION = "1.2"


def mark_blocking(findings, policies_by_id):
    for finding in findings:
        policy = policies_by_id[finding.policy_id]
        by_source = finding.source == "deterministic" or policy.llm_blocking
        finding.blocking = (policy.mode == "enforce" and finding.severity == "CRITICAL"
                            and by_source and finding.waiver_id is None)
    return findings


def _adr_compliance(evaluated, active):
    status = {p.adr: "PASS" for p in evaluated}
    for finding, policy in active:
        if policy.mode == "audit":
            continue
        current = status[policy.adr]
        if finding.blocking:
            status[policy.adr] = "FAIL"
        elif current == "PASS":
            status[policy.adr] = "WARN"
    return dict(sorted(status.items()))


def _summary(blocking, active, errors):
    # Violações e erros aparecem juntos: um erro não pode esconder uma violação real.
    reasons = []
    if blocking:
        reasons.append(f"{len(blocking)} violação(ões) bloqueante(s)")
    if errors and all(e.kind == "llm_unavailable" for e in errors):
        reasons.append("revisor de IA indisponível")
    elif errors:
        reasons.append(f"{len(errors)} erro(s) de execução impedem um veredito confiável")
    if reasons:
        return "Bloqueado: " + " e ".join(reasons) + "."
    if active:
        return f"Aprovado com {len(active)} achado(s) não bloqueante(s)."
    return "Aprovado: nenhuma violação nas políticas avaliadas."


def build_result(*, evaluated, findings, errors, warnings, subject, bundle, stats):
    policies_by_id = {p.id: p for p in evaluated}
    mark_blocking(findings, policies_by_id)
    active = [f for f in findings if f.waiver_id is None]
    waived = [f for f in findings if f.waiver_id is not None]
    blocking = [f for f in active if f.blocking]
    status = "BLOCKED" if blocking or errors else "APPROVED"

    def with_mode(finding):
        return {**finding.as_dict(), "mode": policies_by_id[finding.policy_id].mode}

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": status,
        "summary": _summary(blocking, active, errors),
        "subject": subject,
        "bundle": {"engine_version": __version__, **bundle},
        "policies_evaluated": [{"id": p.id, "version": p.version, "mode": p.mode}
                               for p in evaluated],
        "adr_compliance": _adr_compliance(evaluated,
                                          [(f, policies_by_id[f.policy_id]) for f in active]),
        "violations": [with_mode(f) for f in active],
        "waived": [with_mode(f) for f in waived],
        "errors": [e.as_dict() for e in errors],
        "warnings": list(warnings),
        "stats": stats,
    }
