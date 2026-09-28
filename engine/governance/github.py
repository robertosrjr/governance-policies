"""Publicação do relatório como comentário único no PR."""

import json
import logging
import urllib.request

from .report import COMMENT_MARKER

API = "https://api.github.com"
BOT_LOGIN = "github-actions[bot]"
MAX_PAGES = 10

logger = logging.getLogger("governance.github")


def _request(method, path, token, body=None):
    request = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - URL fixa
        return json.loads(response.read() or "null")


def _previous_comment_id(repo, pr_number, token):
    """Só reaproveita comentário do próprio bot: um comentário humano com o marcador é ignorado."""
    for page in range(1, MAX_PAGES + 1):
        comments = _request("GET", f"/repos/{repo}/issues/{pr_number}/comments"
                                   f"?per_page=100&page={page}", token)
        for comment in comments:
            if (comment.get("user", {}).get("login") == BOT_LOGIN
                    and COMMENT_MARKER in comment.get("body", "")):
                return comment["id"]
        if len(comments) < 100:
            return None
    return None


def publish_comment(repo, pr_number, token, body):
    comment_id = _previous_comment_id(repo, pr_number, token)
    if comment_id:
        _request("PATCH", f"/repos/{repo}/issues/comments/{comment_id}", token, {"body": body})
        logger.info("Comentário %s atualizado no PR #%s", comment_id, pr_number)
    else:
        _request("POST", f"/repos/{repo}/issues/{pr_number}/comments", token, {"body": body})
        logger.info("Comentário publicado no PR #%s", pr_number)
