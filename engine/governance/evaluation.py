"""Avaliação do próprio revisor (LLMOps): o bundle só é promovido se não regredir.

Cada caso em eval/cases/*.yaml traz arquivos e a expectativa por política
(`true` = deve disparar, `false` = não pode disparar). Casos com `requires_llm: true`
só rodam com `--llm`.

- Modo offline (CI de todo PR neste repo): casos determinísticos devem bater 100%.
- Modo LLM: roda N vezes (não determinismo), mede recall/precisão por política e a
  estabilidade de cada caso. `--min-recall/--min-precision` viram gate de release.
"""

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml

from .diff import as_new_files
from .review import run_layers

CASES_DIR = Path(__file__).resolve().parents[2] / "eval" / "cases"


@dataclass(frozen=True)
class Case:
    id: str
    description: str
    requires_llm: bool
    tags: tuple
    files: dict
    expect: dict


def load_cases(cases_dir=CASES_DIR):
    cases = []
    for path in sorted(Path(cases_dir).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases.append(Case(id=data["id"], description=data["description"],
                          requires_llm=bool(data.get("requires_llm")),
                          tags=tuple(data.get("tags", ())),
                          files=data["files"], expect=data["expect"]))
    return cases


def coverage_problems(policies, cases):
    """Política em enforce precisa de ao menos um caso positivo e um negativo."""
    problems = []
    known = {p.id for p in policies}
    for case in cases:
        problems += [f"{case.id}: política desconhecida {pid}"
                     for pid in case.expect if pid not in known]
    for policy in policies:
        if policy.mode != "enforce" or "pr-review" not in policy.targets:
            continue
        values = [c.expect[policy.id] for c in cases if policy.id in c.expect]
        if True not in values or False not in values:
            problems.append(f"{policy.id}: enforce exige casos positivo e negativo em eval/cases")
    return problems


def _score(counts):
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    recall = tp / (tp + fn) if tp + fn else None
    precision = tp / (tp + fp) if tp + fp else None
    return recall, precision


def run_eval(policies, cases, provider=None, llm_config=None, repeat=1, jev_provider=None,
             jev_config=None):
    use_llm = provider is not None or jev_provider is not None
    selected = [c for c in cases if use_llm or not c.requires_llm]
    counts = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    deterministic_failures, errors = [], []
    stability = {}
    for case in selected:
        files = as_new_files(case.files)
        matches = 0
        for _ in range(repeat if use_llm else 1):
            _, findings, run_errors, _, _ = run_layers(files, policies, provider, llm_config,
                                                       use_llm, jev_provider, jev_config)
            errors += [f"{case.id}: {e}" for e in run_errors]
            fired = {f.policy_id for f in findings}
            fired_det = {f.policy_id for f in findings if f.source == "deterministic"}
            case_ok = True
            for policy_id, expected in case.expect.items():
                got = policy_id in fired
                key = ("tp" if got else "fn") if expected else ("fp" if got else "tn")
                counts[policy_id][key] += 1
                case_ok &= got == expected
                if not case.requires_llm and (policy_id in fired_det) != expected:
                    deterministic_failures.append(
                        f"{case.id}: {policy_id} esperado={expected} obtido={not expected}")
            matches += case_ok
        stability[case.id] = matches / (repeat if use_llm else 1)
    metrics = {pid: {**c, "recall": _score(c)[0], "precision": _score(c)[1]}
               for pid, c in sorted(counts.items())}
    return {
        "mode": "llm" if use_llm else "offline",
        "repeat": repeat if use_llm else 1,
        "cases": len(selected),
        "metrics": metrics,
        "stability": stability,
        "deterministic_failures": sorted(set(deterministic_failures)),
        "errors": errors,
    }


def gate(report, policies, min_recall=None, min_precision=None):
    """Retorna a lista de motivos de reprovação do bundle."""
    reasons = list(report["deterministic_failures"]) + list(report["errors"])
    llm_policies = {p.id for p in policies if p.llm}
    if report["mode"] == "llm":
        for pid, m in report["metrics"].items():
            if pid not in llm_policies:
                continue
            if min_recall is not None and m["recall"] is not None and m["recall"] < min_recall:
                reasons.append(f"{pid}: recall {m['recall']:.2f} < {min_recall}")
            if (min_precision is not None and m["precision"] is not None
                    and m["precision"] < min_precision):
                reasons.append(f"{pid}: precisão {m['precision']:.2f} < {min_precision}")
    return reasons


def format_report(report):
    lines = [f"Eval ({report['mode']}, {report['cases']} casos, repetições={report['repeat']})",
             f"{'política':<18} {'TP':>3} {'FP':>3} {'FN':>3} {'TN':>3} {'recall':>7} {'prec.':>7}"]
    for pid, m in report["metrics"].items():
        fmt = lambda v: "   -  " if v is None else f"{v:6.2f}"  # noqa: E731
        lines.append(f"{pid:<18} {m['tp']:>3} {m['fp']:>3} {m['fn']:>3} {m['tn']:>3} "
                     f"{fmt(m['recall']):>7} {fmt(m['precision']):>7}")
    unstable = {k: v for k, v in report["stability"].items() if v < 1}
    if unstable:
        lines.append("Casos instáveis (fração de execuções corretas):")
        lines += [f"  {k}: {v:.2f}" for k, v in sorted(unstable.items())]
    return "\n".join(lines)
