import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from governance.policy import load_policies  # noqa: E402
from governance.review import ADRS_DIR, POLICIES_DIR, load_bundle  # noqa: E402


@pytest.fixture(scope="session")
def policies():
    return load_policies(POLICIES_DIR, ADRS_DIR)


@pytest.fixture(scope="session")
def bundle():
    return load_bundle()


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                          text=True).stdout


@pytest.fixture
def repo(tmp_path):
    """Repositório git com branch main e um commit inicial."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "dev@example.com")
    git(tmp_path, "config", "user.name", "dev")
    git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_text("projeto\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "init")
    git(tmp_path, "checkout", "-q", "-b", "feature")
    return tmp_path


def commit_files(repo, files, message="change"):
    for path, content in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
