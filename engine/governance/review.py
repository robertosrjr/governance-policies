"""Núcleo da avaliação: independe de git e de GitHub (reutilizado pelo eval e pelos testes)."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from .deterministic import run_deterministic
from .llm import LlmConfig, run_llm
from .model import RunError
from .policy import select_policies
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


def load_bundle(path=BUNDLE_FILE):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Bundle(version=data["bundle_version"], llm=LlmConfig(**data["llm"]))


def run_layers(files, policies, provider, llm_config, llm_required):
    """Executa T0 e T1. Retorna (políticas avaliadas, achados, erros, avisos, descartados)."""
    evaluated = select_policies(policies, files, TARGET)
    findings = run_deterministic(evaluated, files)
    errors, warnings, discarded = [], [], 0
    semantic = [p for p in evaluated if p.llm]
    if semantic and provider is None:
        ids = ", ".join(p.id for p in semantic)
        if llm_required:
            errors.append(RunError(
                "llm_not_configured",
                f"Revisor de IA não configurado (sem GEMINI_API_KEY): {ids} não foram avaliadas.",
                "Crie o segredo GEMINI_API_KEY em Settings → Secrets and variables → Actions "
                "do repositório e rode de novo."))
        else:
            warnings.append(f"LLM desligado (--no-llm): {ids} não foram avaliadas.")
    elif semantic:
        llm_findings, llm_errors, discarded = run_llm(semantic, files, provider, llm_config)
        known = {(f.policy_id, f.file, f.line) for f in findings}
        # T1 só acrescenta: duplicatas de T0 são descartadas, nada de T0 é removido
        findings += [f for f in llm_findings if (f.policy_id, f.file, f.line) not in known]
        errors += llm_errors
    return evaluated, findings, errors, warnings, discarded


def evaluate(files, *, policies, waivers, provider, bundle, subject, governance_ref,
             policies_digest, llm_required, extra_warnings=(), extra_errors=()):
    evaluated, findings, errors, warnings, discarded = run_layers(
        files, policies, provider, bundle.llm, llm_required)
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
        },
        stats={"files_changed": len(files), "llm_findings_discarded": discarded},
    )
