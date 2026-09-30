"""Coleta do painel de conformidade no GitHub (ADR-GOV-006).

- Artefatos `governance-<sha>` dos repositórios-alvo na janela: o `result.json` de cada
  avaliação (o artefato expira em 90 dias; para janelas maiores, use o bucket de
  evidências e o modo --from-dir).
- Alertas do Code Scanning da ferramenta `enterprise-governance` em cada PR avaliado:
  os dispensados com motivo "false positive" alimentam a taxa de falso positivo.

Só leitura. O token precisa de leitura de Actions e de Code Scanning nos repositórios.
"""

import io
import json
import logging
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone

from .model import GovernanceError

API = "https://api.github.com"
TOOL = "enterprise-governance"
MAX_PAGES = 20

logger = logging.getLogger("governance.dashboard")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class GitHubClient:
    def __init__(self, token):
        self._headers = {"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json",
                         "X-GitHub-Api-Version": "2022-11-28",
                         "User-Agent": "governance-dashboard"}

    def get_json(self, path):
        request = urllib.request.Request(f"{API}{path}", headers=self._headers)
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - API fixa
            return json.loads(response.read() or "null")

    def get_bytes(self, path):
        """Downloads redirecionam para o storage: o token não pode ir junto."""
        opener = urllib.request.build_opener(_NoRedirect)
        request = urllib.request.Request(f"{API}{path}", headers=self._headers)
        try:
            with opener.open(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                with urllib.request.urlopen(exc.headers["Location"], timeout=120) as response:  # noqa: S310
                    return response.read()
            raise


def _pages(client, path, key=None):
    sep = "&" if "?" in path else "?"
    for page in range(1, MAX_PAGES + 1):
        data = client.get_json(f"{path}{sep}per_page=100&page={page}")
        items = data.get(key, []) if key else data
        yield from items
        if len(items) < 100:
            return


def _result_from_zip(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        name = next((n for n in archive.namelist() if n.endswith("result.json")), None)
        return json.loads(archive.read(name)) if name else None


def collect(client, repositories, window_days, now=None):
    """Retorna (results, false_positives, avisos)."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=window_days)).isoformat()
    results, false_positives, warnings = [], [], []
    for repo in repositories:
        try:
            artifacts = [a for a in _pages(client, f"/repos/{repo}/actions/artifacts", "artifacts")
                         if a["name"].startswith("governance-") and not a["expired"]
                         and a["created_at"] >= since]
        except urllib.error.HTTPError as exc:
            raise GovernanceError(f"{repo}: sem acesso aos artefatos (HTTP {exc.code}). "
                                  "O token precisa de leitura de Actions.") from exc
        prs = set()
        for artifact in artifacts:
            result = _result_from_zip(client.get_bytes(
                f"/repos/{repo}/actions/artifacts/{artifact['id']}/zip"))
            if not result:
                warnings.append(f"{repo}: artefato {artifact['name']} sem result.json")
                continue
            results.append({"result": result, "created_at": artifact["created_at"]})
            if (result.get("subject") or {}).get("pull_request"):
                prs.add(result["subject"]["pull_request"])
        for pr in sorted(prs):
            try:
                alerts = list(_pages(client, f"/repos/{repo}/code-scanning/alerts"
                                             f"?tool_name={TOOL}&ref=refs/pull/{pr}/merge"))
            except urllib.error.HTTPError as exc:
                warnings.append(f"{repo}#{pr}: alertas indisponíveis (HTTP {exc.code}); "
                                "falso positivo não medido")
                continue
            false_positives += [{"repository": repo, "pull_request": pr,
                                 "policy_id": a["rule"]["id"], "dismissed_by":
                                 (a.get("dismissed_by") or {}).get("login"),
                                 "comment": a.get("dismissed_comment")}
                                for a in alerts if a.get("dismissed_reason") == "false positive"]
        logger.info("%s: %d avaliação(ões), %d PR(s)", repo, len(artifacts), len(prs))
    return results, false_positives, warnings


def load_from_dir(directory):
    """Modo offline: result.json exportados (ex.: sincronizados do bucket de evidências)."""
    from pathlib import Path
    results = []
    for path in sorted(Path(directory).rglob("result.json")):
        results.append({"result": json.loads(path.read_text(encoding="utf-8")),
                        "created_at": datetime.fromtimestamp(path.stat().st_mtime,
                                                             timezone.utc).isoformat()})
    return results
