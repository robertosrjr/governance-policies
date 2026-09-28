"""CLI: python -m governance {validate,review,export,eval}.

Códigos de saída: 0 aprovado/ok · 1 bloqueado/reprovado · 2 configuração inválida.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from .diff import collect_changes
from .evaluation import coverage_problems, format_report, gate, load_cases, run_eval
from .export import write_exports
from .github import publish_comment
from .llm import PROMPTS_DIR, build_provider
from .model import GovernanceError
from .policy import load_policies, policies_digest
from .report import build_markdown, build_sarif
from .review import ADRS_DIR, POLICIES_DIR, ROOT, WAIVERS_DIR, evaluate, load_bundle
from .waivers import load_waivers

logger = logging.getLogger("governance")


def _load_all(strict_waivers=False):
    policies = load_policies(POLICIES_DIR, ADRS_DIR)
    waivers, warnings = load_waivers(WAIVERS_DIR, {p.id for p in policies},
                                     strict=strict_waivers)
    return policies, waivers, warnings


def cmd_validate(_args):
    policies, _, _ = _load_all(strict_waivers=True)
    bundle = load_bundle()
    reviewers = {p.llm["reviewer"] for p in policies if p.llm}
    problems = [f"prompt ausente para o revisor '{r}'"
                for r in reviewers if not (PROMPTS_DIR / f"{r}.md").is_file()]
    problems += coverage_problems(policies, load_cases())
    if problems:
        raise GovernanceError("Bundle inválido:\n  " + "\n  ".join(sorted(set(problems))))
    logger.info("Bundle %s válido: %d políticas", bundle.version, len(policies))
    return 0


def _head_commit(repo):
    explicit = os.environ.get("HEAD_SHA", "").strip()
    if explicit:
        return explicit
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _provider(args, bundle):
    if args.no_llm:
        return None
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY ausente: camada LLM indisponível")
        return None
    return build_provider(bundle.llm, api_key)


def cmd_review(args):
    policies, waivers, waiver_warnings = _load_all()
    bundle = load_bundle()
    repo = Path(args.repo).resolve()
    files = collect_changes(repo, args.base)
    logger.info("Arquivos alterados: %d", len(files))
    pr = os.environ.get("PR_NUMBER", "").strip()
    subject = {
        "repository": os.environ.get("GITHUB_REPOSITORY", repo.name),
        "commit": _head_commit(repo),
        "base": args.base,
        "pull_request": int(pr) if pr.isdigit() else None,
    }
    result = evaluate(
        files, policies=policies, waivers=waivers, provider=_provider(args, bundle),
        bundle=bundle, subject=subject,
        governance_ref=os.environ.get("GOVERNANCE_REF") or None,
        policies_digest=policies_digest(POLICIES_DIR),
        llm_required=not args.no_llm, extra_warnings=waiver_warnings,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    markdown = build_markdown(result)
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    (out / "results.sarif").write_text(json.dumps(build_sarif(result, policies), indent=2),
                                       encoding="utf-8")
    (out / "report.md").write_text(markdown, encoding="utf-8")
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(markdown + "\n")
    if args.publish_comment:
        publish_comment(subject["repository"], pr, os.environ["GITHUB_TOKEN"], markdown)
    for violation in result["violations"]:
        logger.info("  %-8s %-16s %s:%s (%s%s)", violation["severity"], violation["policy_id"],
                    violation["file"], violation["line"], violation["source"],
                    ", bloqueia" if violation["blocking"] else "")
    for error in result["errors"]:
        logger.error("  %s", error)
    logger.info("Veredito: %s. %s", result["status"], result["summary"])
    return 0 if result["status"] == "APPROVED" else 1


def cmd_export(args):
    policies = load_policies(POLICIES_DIR, ADRS_DIR)
    stale = write_exports(policies, load_bundle().version, ROOT, check=args.check)
    for path in stale:
        logger.info("%s %s", "desatualizado:" if args.check else "gerado:", path.relative_to(ROOT))
    if args.check and stale:
        logger.error("Rode `python -m governance export` e faça commit dos arquivos gerados")
        return 1
    return 0


def cmd_eval(args):
    policies = load_policies(POLICIES_DIR, ADRS_DIR)
    bundle = load_bundle()
    if args.model:
        bundle = replace(bundle, llm=replace(bundle.llm, model=args.model))
    provider = None
    if args.llm:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise GovernanceError("--llm exige GEMINI_API_KEY")
        provider = build_provider(bundle.llm, api_key)
    report = run_eval(policies, load_cases(), provider, bundle.llm, repeat=args.repeat)
    report["model"] = bundle.llm.model if args.llm else None
    print(format_report(report))
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    reasons = gate(report, policies, args.min_recall, args.min_precision)
    for reason in reasons:
        logger.error("  %s", reason)
    logger.info("Eval: %s", "REPROVADO" if reasons else "APROVADO")
    return 1 if reasons else 0


def build_parser():
    parser = argparse.ArgumentParser(prog="governance", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="valida políticas, waivers, prompts e cobertura do eval") \
        .set_defaults(func=cmd_validate)

    review = sub.add_parser("review", help="avalia as mudanças de um repositório git")
    review.add_argument("--repo", default=".", help="checkout do repositório-alvo")
    review.add_argument("--base", required=True, help="ref base, ex.: origin/main")
    review.add_argument("--out", default="governance-out")
    review.add_argument("--no-llm", action="store_true",
                        help="só a camada determinística (uso local; o CI nunca usa)")
    review.add_argument("--publish-comment", action="store_true")
    review.set_defaults(func=cmd_review)

    export = sub.add_parser("export", help="gera artefatos derivados das políticas")
    export.add_argument("--check", action="store_true", help="falha se estiverem desatualizados")
    export.set_defaults(func=cmd_export)

    ev = sub.add_parser("eval", help="avalia o revisor contra eval/cases")
    ev.add_argument("--llm", action="store_true")
    ev.add_argument("--repeat", type=int, default=3)
    ev.add_argument("--model", help="avaliar um modelo candidato sem alterar o bundle")
    ev.add_argument("--min-recall", type=float)
    ev.add_argument("--min-precision", type=float)
    ev.add_argument("--out")
    ev.set_defaults(func=cmd_eval)
    return parser


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console do Windows
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)-7s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except GovernanceError as exc:
        logger.error("%s", exc)
        return 2
