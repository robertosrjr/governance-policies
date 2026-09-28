"""Coleta das mudanças do PR a partir do git.

O motor recebe o conteúdo final de cada arquivo alterado e o conjunto de linhas
adicionadas. Regras determinísticas olham só as linhas adicionadas; o LLM recebe o
arquivo inteiro (contexto) mas só pode apontar linhas adicionadas.
"""

import re
import subprocess
from pathlib import Path

from .model import ChangedFile, GovernanceError

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _unquote(path):
    if len(path) >= 2 and path[0] == path[-1] == '"':
        return path[1:-1].encode("latin-1", "backslashreplace").decode("unicode_escape") \
            .encode("latin-1").decode("utf-8", "replace")
    return path


def parse_unified_diff(diff_text):
    """Retorna {caminho: {linha: texto}} com as linhas adicionadas de um diff unificado.

    Remoções de arquivo (`+++ /dev/null`) não aparecem aqui; `collect_changes` as obtém
    com `--diff-filter=D`.
    """
    files, current, line_no = {}, None, 0
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            current = None
        elif raw.startswith("+++ "):
            target = _unquote(raw[4:].strip())
            current = None if target == "/dev/null" else (
                target[2:] if target.startswith("b/") else target)
            if current:
                files.setdefault(current, {})
        elif current and (match := HUNK_RE.match(raw)):
            line_no = int(match.group(1))
        elif current and raw.startswith("+"):
            files[current][line_no] = raw[1:]
            line_no += 1
        elif current and raw.startswith(" "):
            line_no += 1
    return files


def _git(repo, *args):
    try:
        return subprocess.run(
            ["git", "-c", "core.quotepath=off", *args], cwd=repo,
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise GovernanceError(f"git {' '.join(args)} falhou: {exc.stderr.strip()[:300]}") from exc


def _names(repo, base, diff_filter=None):
    args = ["diff", "--name-only", "-M", f"{base}...HEAD"]
    if diff_filter:
        args.insert(2, f"--diff-filter={diff_filter}")
    return set(_git(repo, *args).splitlines()) - {""}


def collect_changes(repo, base):
    """Arquivos alterados entre `base` e HEAD (three-dot: só o que o PR introduz).

    Renomeações sem mudança de conteúdo, binários e remoções entram na lista (sem linhas
    adicionadas) para que regras de caminho, como GOV-SELF-001, os enxerguem.
    """
    repo = Path(repo)
    added_by_path = parse_unified_diff(
        _git(repo, "diff", "--unified=0", "--no-color", "-M", f"{base}...HEAD"))
    deleted = _names(repo, base, "D")
    changes = []
    for path in sorted(_names(repo, base) | set(added_by_path)):
        if path in deleted:
            changes.append(ChangedFile(path=path, content="", deleted=True))
            continue
        try:
            content = (repo / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = ""  # binário: só regras de caminho se aplicam
        except FileNotFoundError as exc:
            raise GovernanceError(f"Arquivo do diff ausente no checkout: {path}") from exc
        changes.append(ChangedFile(path=path, content=content,
                                   added_lines=added_by_path.get(path, {})))
    return changes


def as_new_files(files):
    """Trata cada arquivo como novo (todas as linhas adicionadas). Usado no eval."""
    return [
        ChangedFile(path=path, content=content,
                    added_lines={i: line for i, line in enumerate(content.splitlines(), 1)})
        for path, content in files.items()
    ]
