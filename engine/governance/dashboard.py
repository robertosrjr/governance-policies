"""Painel de conformidade (ADR-GOV-006): do veredito de cada PR aos números de gestão.

Entradas: a última avaliação (`result.json`) de cada PR na janela, os alertas do Code
Scanning dispensados como "false positive", os waivers e as políticas. Saída: métricas
por política, prontidão para `enforce` pelos critérios do ADR-GOV-003, saúde da esteira
e waivers vencendo. Este módulo não acessa rede; a coleta está em dashboard_github.py.
"""

import html
import subprocess
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from .evaluation import load_cases

# Critérios do ADR-GOV-003 para warn -> enforce
MIN_DAYS_IN_MODE = 14
MAX_FP_RATE = 0.05
MIN_FINDINGS = 10  # sem amostra mínima, "0% de falso positivo" não quer dizer nada
EXPIRING_DAYS = 30


def latest_per_pr(results):
    """Uma avaliação por (repositório, PR): a mais recente. Sem PR, cada execução conta."""
    latest = {}
    for item in results:
        result, created = item["result"], item.get("created_at", "")
        subject = result.get("subject") or {}
        key = (subject.get("repository", "").lower(),
               subject.get("pull_request") or f"commit:{subject.get('commit')}")
        if key not in latest or created > latest[key]["created_at"]:
            latest[key] = {"result": result, "created_at": created}
    return [v["result"] for v in latest.values()]


def mode_since(policy_path):
    """Data em que a política entrou no modo atual (primeiro commit que introduziu a linha)."""
    try:
        mode_line = next(line for line in Path(policy_path).read_text(encoding="utf-8")
                         .splitlines() if line.startswith("mode:"))
        out = subprocess.run(
            ["git", "log", "--reverse", "--format=%cs", "-S", mode_line, "--", str(policy_path)],
            cwd=Path(policy_path).parent, capture_output=True, text=True, check=True).stdout
        first = out.split()
        return date.fromisoformat(first[0]) if first else None
    except (OSError, StopIteration, subprocess.CalledProcessError, ValueError):
        return None


def _eval_coverage(cases):
    coverage = defaultdict(set)
    for case in cases:
        for pid, expected in case.expect.items():
            coverage[pid].add(bool(expected))
    return coverage


def _readiness(policy, row, since, today, coverage):
    if policy.mode == "enforce":
        return "enforce", []
    if policy.mode == "audit":
        return "audit", ["em audit: sem verificação no PR"]
    missing = []
    if coverage.get(policy.id) != {True, False}:
        missing.append("casos positivo e negativo no eval")
    days = (today - since).days if since else None
    if days is None or days < MIN_DAYS_IN_MODE:
        missing.append(f"{MIN_DAYS_IN_MODE} dias em warn (hoje: {days if days is not None else '?'})")
    if row["findings"] < MIN_FINDINGS:
        missing.append(f"amostra de {MIN_FINDINGS} achados (hoje: {row['findings']})")
    elif row["fp_rate"] is not None and row["fp_rate"] >= MAX_FP_RATE:
        return "falso positivo alto", [f"falso positivo {row['fp_rate']:.0%} (limite "
                                       f"{MAX_FP_RATE:.0%}): revise a regra"]
    return ("pronta para enforce" if not missing else "coletando dados"), missing


def build_metrics(policies, results, false_positives, waivers, *, today, window_days,
                  repositories, policy_since=None, cases=None):
    """`results`: [{"result": result.json, "created_at": iso}]. `false_positives`:
    [{"repository", "policy_id"}] (alertas dispensados como false positive)."""
    evaluations = latest_per_pr(results)
    policy_since = policy_since or {}
    coverage = _eval_coverage(cases if cases is not None else load_cases())
    findings = Counter()
    prs_with = defaultdict(set)
    blocking = Counter()
    for result in evaluations:
        subject = result.get("subject") or {}
        pr_key = (subject.get("repository"), subject.get("pull_request"))
        for violation in result.get("violations") or ():
            findings[violation["policy_id"]] += 1
            prs_with[violation["policy_id"]].add(pr_key)
            blocking[violation["policy_id"]] += bool(violation.get("blocking"))
    fps = Counter(fp["policy_id"] for fp in false_positives)

    rows = []
    for policy in sorted(policies, key=lambda p: p.id):
        row = {"id": policy.id, "title": policy.title, "mode": policy.mode,
               "severity": policy.severity, "adr": policy.adr,
               "findings": findings[policy.id], "prs": len(prs_with[policy.id]),
               "blocking": blocking[policy.id], "false_positives": fps[policy.id]}
        row["fp_rate"] = (row["false_positives"] / row["findings"]) if row["findings"] else None
        since = policy_since.get(policy.id)
        row["mode_since"] = since.isoformat() if since else None
        row["readiness"], row["missing"] = _readiness(policy, row, since, today, coverage)
        rows.append(row)

    statuses = Counter(r.get("status") for r in evaluations)
    by_class = Counter(((r.get("classification") or {}).get("name") or "sem registro")
                       for r in evaluations)
    error_kinds = Counter(e.get("kind", "?") for r in evaluations for e in r.get("errors") or ())
    blocked_by_error_only = sum(
        1 for r in evaluations if r.get("status") == "BLOCKED" and r.get("errors")
        and not any(v.get("blocking") for v in r.get("violations") or ()))
    active_waivers = [{"id": w.id, "policy_id": w.policy_id, "repository": w.repository,
                       "expires": w.expires.isoformat(),
                       "days_left": (w.expires - today).days} for w in waivers]
    return {
        "generated_at": today.isoformat(),
        "window": {"days": window_days,
                   "from": (today - timedelta(days=window_days)).isoformat()},
        "repositories": sorted(repositories),
        "overview": {
            "evaluations": len(evaluations),
            "approved": statuses.get("APPROVED", 0),
            "blocked": statuses.get("BLOCKED", 0),
            "blocked_by_error_only": blocked_by_error_only,
            "errors_by_kind": dict(error_kinds.most_common()),
            "evaluations_by_class": dict(by_class.most_common()),
            "ready_for_enforce": [r["id"] for r in rows if r["readiness"] == "pronta para enforce"],
            "high_false_positive": [r["id"] for r in rows if r["readiness"] == "falso positivo alto"],
        },
        "policies": rows,
        "waivers": {
            "active": sorted(active_waivers, key=lambda w: w["days_left"]),
            "expiring": [w for w in active_waivers if w["days_left"] <= EXPIRING_DAYS],
        },
        "criteria": {"min_days_in_mode": MIN_DAYS_IN_MODE, "max_fp_rate": MAX_FP_RATE,
                     "min_findings": MIN_FINDINGS},
    }


def _pct(value):
    return "—" if value is None else f"{value:.0%}"


def render_markdown(metrics):
    o = metrics["overview"]
    lines = [
        "## Painel de conformidade da governança", "",
        f"Janela: {metrics['window']['days']} dias (desde {metrics['window']['from']}) · "
        f"{len(metrics['repositories'])} repositório(s) · {o['evaluations']} PR(s) avaliados", "",
        f"- Aprovados: **{o['approved']}** · Bloqueados: **{o['blocked']}** "
        f"(só por erro de execução: {o['blocked_by_error_only']})",
        f"- Prontas para enforce: {', '.join(o['ready_for_enforce']) or 'nenhuma'}",
        f"- Falso positivo acima do limite: {', '.join(o['high_false_positive']) or 'nenhuma'}",
        f"- Waivers vencendo em até {EXPIRING_DAYS} dias: {len(metrics['waivers']['expiring'])}",
        "- Avaliações por classe de repositório: " + (", ".join(
            f"{k}: {v}" for k, v in o["evaluations_by_class"].items()) or "nenhuma"),
        "", "| Política | Modo | Achados | PRs | Bloqueios | Falso positivo | Prontidão |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in metrics["policies"]:
        if r["mode"] == "audit":
            continue
        lines.append(f"| {r['id']} | {r['mode']} | {r['findings']} | {r['prs']} | "
                     f"{r['blocking']} | {r['false_positives']} ({_pct(r['fp_rate'])}) | "
                     f"{r['readiness']} |")
    return "\n".join(lines) + "\n"


_CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1f2328;--muted:#656d76;--line:#d0d7de;
--ok:#1a7f37;--warn:#9a6700;--bad:#cf222e;--info:#0969da;--chip:#eaeef2}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0d1117;--card:#161b22;
--fg:#e6edf3;--muted:#8d96a0;--line:#30363d;--ok:#3fb950;--warn:#d29922;--bad:#f85149;
--info:#4493f8;--chip:#21262d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}
.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
gap:12px;margin:16px 0}.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:14px}.num{font-size:26px;font-weight:600}section{margin-top:24px}
.table{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;min-width:760px}th,td{text-align:left;padding:8px 10px;
border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}.chip{display:inline-block;padding:1px 8px;
border-radius:10px;background:var(--chip);font-size:12px}.ok{color:var(--ok)}.warn{color:var(--warn)}
.bad{color:var(--bad)}.info{color:var(--info)}ul{margin:4px 0;padding-left:18px}
"""

_READINESS_CLASS = {"enforce": "info", "pronta para enforce": "ok", "coletando dados": "warn",
                    "falso positivo alto": "bad", "audit": "muted"}


def render_html(metrics):
    e = html.escape
    o = metrics["overview"]
    cards = [("PRs avaliados", o["evaluations"], ""), ("Aprovados", o["approved"], "ok"),
             ("Bloqueados", o["blocked"], "bad"),
             ("Bloqueados só por erro", o["blocked_by_error_only"], "warn"),
             ("Prontas para enforce", len(o["ready_for_enforce"]), "ok"),
             ("Waivers vencendo", len(metrics["waivers"]["expiring"]), "warn")]
    rows = []
    for r in metrics["policies"]:
        missing = "".join(f"<li>{e(m)}</li>" for m in r["missing"])
        rows.append(
            f"<tr><td><b>{e(r['id'])}</b><br><span class='muted'>{e(r['title'])}</span></td>"
            f"<td><span class='chip'>{e(r['mode'])}</span><br><span class='muted'>"
            f"{e(r['mode_since'] or '—')}</span></td><td>{e(r['severity'])}</td>"
            f"<td class='n'>{r['findings']}</td><td class='n'>{r['prs']}</td>"
            f"<td class='n'>{r['blocking']}</td>"
            f"<td class='n'>{r['false_positives']} ({e(_pct(r['fp_rate']))})</td>"
            f"<td><span class='{_READINESS_CLASS.get(r['readiness'], '')}'>{e(r['readiness'])}"
            f"</span>{'<ul>' + missing + '</ul>' if missing else ''}</td></tr>")
    errors = "".join(f"<li>{e(k)}: {v}</li>" for k, v in o["errors_by_kind"].items()) \
        or "<li>nenhum</li>"
    waivers = "".join(
        f"<tr><td>{e(w['id'])}</td><td>{e(w['policy_id'])}</td><td>{e(w['repository'])}</td>"
        f"<td>{e(w['expires'])}</td><td class='n {'warn' if w['days_left'] <= EXPIRING_DAYS else ''}'>"
        f"{w['days_left']}</td></tr>" for w in metrics["waivers"]["active"]) \
        or "<tr><td colspan='5' class='muted'>nenhum waiver ativo</td></tr>"
    by_class = "".join(f"<li>{e(k)}: {v}</li>" for k, v in o["evaluations_by_class"].items())         or "<li>nenhuma</li>"
    c = metrics["criteria"]
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel de conformidade</title><style>{_CSS}</style></head>
<body><main>
<h1>Painel de conformidade da governança</h1>
<div class="muted">Gerado em {e(metrics['generated_at'])} · janela de {metrics['window']['days']} dias
(desde {e(metrics['window']['from'])}) · {e(', '.join(metrics['repositories']))}</div>
<div class="grid">{''.join(f"<div class='card'><div class='muted'>{e(t)}</div><div class='num {cls}'>{v}</div></div>" for t, v, cls in cards)}</div>
<section><h2>Políticas</h2>
<p class="muted">Prontidão pelo ADR-GOV-003: casos positivo e negativo no eval, {c['min_days_in_mode']}
dias no modo warn, ao menos {c['min_findings']} achados e falso positivo abaixo de
{c['max_fp_rate']:.0%}. Falso positivo = alerta dispensado como "false positive" no Code Scanning.</p>
<div class="table"><table><thead><tr><th>Política</th><th>Modo (desde)</th><th>Severidade</th>
<th>Achados</th><th>PRs</th><th>Bloqueios</th><th>Falso positivo</th><th>Prontidão</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></section>
<section><h2>Saúde da esteira</h2><div class="grid">
<div class="card">Erros de execução nas avaliações:<ul>{errors}</ul></div>
<div class="card">Avaliações por classe de repositório (ADR-GOV-009):<ul>{by_class}</ul></div>
</div></section>
<section><h2>Waivers ativos</h2><div class="table"><table><thead><tr><th>Waiver</th>
<th>Política</th><th>Repositório</th><th>Vence em</th><th>Dias</th></tr></thead>
<tbody>{waivers}</tbody></table></div></section>
</main></body></html>
"""
