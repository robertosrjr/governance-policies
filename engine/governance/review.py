"""Núcleo da avaliação: independe de git e de GitHub (reutilizado pelo eval e pelos testes)."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .deterministic import run_deterministic
from .jev import run_jev
from .llm import LlmConfig, api_key_env, run_llm
from .model import RunError
from .policy import select_policies
from .usage import summarize
from .verdict import build_result
from .waivers import apply_waivers

ROOT = Path(__file__).resolve().parents[2]
POLICIES_DIR = ROOT / "policies"
ADRS_DIR = ROOT / "adrs"
WAIVERS_DIR = ROOT / "waivers"
BUNDLE_FILE = ROOT / "engine" / "bundle.yaml"
TARGET = "pr-review"


@dataclass(frozen=True)
class Bundle:
    version: str
    llm: LlmConfig
    jev: LlmConfig | None = None  # julgamento tipado (ADR-GOV-002)


def load_bundle(path=BUNDLE_FILE):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    jev = LlmConfig(**data["jev"]) if data.get("jev") else None
    return Bundle(version=data["bundle_version"], llm=LlmConfig(**data["llm"]), jev=jev)


def _not_configured(policies, config, llm_required, errors, warnings):
    ids = ", ".join(p.id for p in policies)
    if not llm_required:
        warnings.append(f"LLM desligado (--no-llm): {ids} não foram avaliadas.")
        return
    key_env = api_key_env(config.provider) if config else "a chave do provedor"
    errors.append(RunError(
        "llm_not_configured",
        f"Revisor de IA não configurado (sem {key_env}): {ids} não foram avaliadas.",
        f"Crie o segredo {key_env} em Settings → Secrets and variables → Actions "
        "do repositório e rode de novo."))


def run_layers(files, policies, provider, llm_config, llm_required, jev_provider=None,
               jev_config=None, llm_allowed=True, classification_name=None):
    """Executa T0 e T1. Retorna (políticas avaliadas, achados, erros, avisos, descartados)."""
    evaluated = select_policies(policies, files, TARGET)
    findings = run_deterministic(evaluated, files)
    errors, warnings, discarded, semantic_findings = [], [], 0, []
    generative = [p for p in evaluated if p.llm_engine == "generative"]
    judged = [p for p in evaluated if p.llm_engine == "jev"]
    if not llm_allowed and (generative or judged):
        # Decisão de classificação (ADR-GOV-009), não falha: registra e segue sem IA.
        ids = ", ".join(p.id for p in generative + judged)
        warnings.append(f"Classe {classification_name}: revisão por IA desligada; a parte "
                        f"semântica de {ids} não foi avaliada (só as regras determinísticas).")
        generative, judged = [], []
    if generative and provider is None:
        _not_configured(generative, llm_config, llm_required, errors, warnings)
    elif generative:
        llm_findings, llm_errors, discarded = run_llm(generative, files, provider, llm_config)
        semantic_findings += llm_findings
        errors += llm_errors
    if judged and jev_provider is None:
        _not_configured(judged, jev_config, llm_required, errors, warnings)
    elif judged:
        jev_findings, jev_errors = run_jev(judged, files, jev_provider, jev_config)
        semantic_findings += jev_findings
        errors += jev_errors
    known = {(f.policy_id, f.file, f.line) for f in findings}
    # T1 só acrescenta: duplicatas de T0 são descartadas, nada de T0 é removido
    findings += [f for f in semantic_findings if (f.policy_id, f.file, f.line) not in known]
    return evaluated, findings, errors, warnings, discarded


def evaluate(files, *, policies, waivers, provider, bundle, subject, governance_ref,
             policies_digest, llm_required, extra_warnings=(), extra_errors=(),
             jev_provider=None, classification=None, raised=()):
    llm_allowed = classification.llm if classification else True
    evaluated, findings, errors, warnings, discarded = run_layers(
        files, policies, provider, bundle.llm, llm_required, jev_provider, bundle.jev,
        llm_allowed=llm_allowed,
        classification_name=classification.name if classification else None)
    errors = [*extra_errors, *errors]
    apply_waivers(findings, waivers, subject["repository"], subject["commit"])
    return build_result(
        evaluated=evaluated,
        findings=findings,
        errors=errors,
        warnings=[*extra_warnings, *warnings],
        subject=subject,
        bundle={
            "bundle_version": bundle.version,
            "governance_ref": governance_ref,
            "policies_digest": policies_digest,
            "llm": ({"provider": bundle.llm.provider, "model": bundle.llm.model}
                    if provider is not None else None),
            "jev": ({"provider": bundle.jev.provider, "model": bundle.jev.model}
                    if jev_provider is not None and bundle.jev else None),
        },
        stats={"files_changed": sum(1 for f in files if f.status != "context"),
               "llm_findings_discarded": discarded,
               "ai_usage": summarize(provider, jev_provider)},
        classification=classification.as_dict(raised) if classification else None,
    )
