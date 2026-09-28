import pytest
import yaml
from conftest import commit_files, git

from governance.diff import collect_changes, parse_unified_diff
from governance.model import GovernanceError
from governance.policy import glob_match, load_policies


@pytest.mark.parametrize("path,pattern,expected", [
    ("app/src/main/java/x/domain/A.java", "**/domain/**/*.java", True),
    ("domain/A.java", "**/domain/**/*.java", True),
    ("app/domainx/A.java", "**/domain/**/*.java", False),
    (".github/workflows/ci.yml", ".github/**", True),
    ("CODEOWNERS", "**/CODEOWNERS", True),
    ("docs/CODEOWNERS", "**/CODEOWNERS", True),
    ("a/b.java", "*.java", False),
    ("b.java", "*.java", True),
    ("a\\b\\domain\\C.java", "**/domain/*.java", True),
])
def test_glob_match(path, pattern, expected):
    assert glob_match(path, pattern) is expected


def test_invalid_policy_is_rejected(tmp_path):
    (tmp_path / "X-BAD-001.yaml").write_text("id: X-BAD-001\ntitle: incompleta\n",
                                             encoding="utf-8")
    with pytest.raises(GovernanceError, match="Políticas inválidas"):
        load_policies(tmp_path)


def test_llm_blocking_requires_eval_evidence(tmp_path, policies):
    source = next(p for p in policies if p.id == "QUAL-CODE-001")
    data = {**source.raw, "enforcement": {"llm": {**source.llm, "blocking": True}}}
    (tmp_path / "QUAL-CODE-001.yaml").write_text(yaml.safe_dump(data, allow_unicode=True),
                                                 encoding="utf-8")
    with pytest.raises(GovernanceError, match="eval_evidence"):
        load_policies(tmp_path)


def test_parse_unified_diff_tracks_added_line_numbers():
    diff = (
        "diff --git a/A.java b/A.java\n"
        "--- a/A.java\n"
        "+++ b/A.java\n"
        "@@ -1,0 +2,2 @@\n"
        "+linha2\n"
        "+linha3\n"
        "@@ -10 +12 @@\n"
        "-velha\n"
        "+nova12\n"
        "diff --git a/B.java b/B.java\n"
        "--- a/B.java\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-removida\n"
    )
    assert parse_unified_diff(diff) == {"A.java": {2: "linha2", 3: "linha3", 12: "nova12"}}


def test_collect_changes_includes_renames_binaries_and_deletions(repo):
    commit_files(repo, {"keep.txt": "a\n", "gone.txt": "x\n", "old.txt": "mesmo\n"}, "base")
    git(repo, "branch", "-f", "main")
    git(repo, "rm", "-q", "gone.txt")
    git(repo, "mv", "old.txt", "new.txt")
    commit_files(repo, {"keep.txt": "a\nb\n", "img.bin": b"\x00\xff\x00binario"}, "pr")

    changes = {c.path: c for c in collect_changes(repo, "main")}

    assert changes["keep.txt"].added_lines == {2: "b"}
    assert changes["gone.txt"].deleted
    assert "new.txt" in changes and changes["new.txt"].added_lines == {}
    assert changes["img.bin"].content == ""


def test_collect_changes_fails_closed_on_unknown_base(repo):
    with pytest.raises(GovernanceError):
        collect_changes(repo, "origin/nao-existe")
