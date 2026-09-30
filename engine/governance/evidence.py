"""Verificação da evidência antes do deploy (ADR-GOV-005).

A assinatura do `result.json` é verificada pelo `gh attestation verify` no workflow do
gate de deploy, exigindo que quem assinou seja o workflow central. Aqui se verifica o
conteúdo: que a evidência é do repositório e do commit que vão para produção e que o
veredito foi de aprovação. Qualquer dúvida reprova (fail-closed).
"""

from .model import GovernanceError

KNOWN_SCHEMAS = ("1.2", "1.3")


def check_result(result, *, repository, commit):
    """Lista de motivos para NÃO implantar. Vazia = evidência válida."""
    if not isinstance(result, dict):
        raise GovernanceError("result.json não é um objeto")
    problems = []
    schema = result.get("schema_version")
    if schema not in KNOWN_SCHEMAS:
        problems.append(f"versão do formato desconhecida ({schema}); atualize o gate de deploy")
    if result.get("status") != "APPROVED":
        problems.append(f"veredito {result.get('status')}: {result.get('summary', '')}".strip())
    subject = result.get("subject") or {}
    if (subject.get("repository") or "").lower() != repository.lower():
        problems.append(f"evidência de outro repositório ({subject.get('repository')})")
    if subject.get("commit") != commit:
        problems.append(f"evidência de outro commit ({subject.get('commit')}, esperado {commit})")
    if result.get("errors"):
        problems.append(f"{len(result['errors'])} erro(s) de execução registrados")
    if any(v.get("blocking") for v in result.get("violations") or ()):
        problems.append("há violação bloqueante registrada")
    if not (result.get("bundle") or {}).get("governance_ref"):
        problems.append("sem governance_ref: não dá para saber quais políticas avaliaram o PR")
    return problems
