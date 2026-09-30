import io
import json
import zipfile
from datetime import date, datetime, timezone

from governance.dashboard import build_metrics, latest_per_pr, render_html, render_markdown
from governance.dashboard_github import collect
from governance.evaluation import Case
from governance.waivers import Waiver

TODAY = date(2026, 10, 30)
REPO = "org/conta"


def result(pr, status="APPROVED", violations=(), errors=()):
    return {"status": status, "subject": {"repository": REPO, "pull_request": pr, "commit": "x"},
            "violations": list(violations), "errors": list(errors)}


def finding(pid, blocking=False):
    return {"policy_id": pid, "blocking": blocking, "file": "A.java", "line": 1}


def cases_for(*pids):
    return [Case(id=f"{p}-{e}", description="", requires_llm=False, tags=(), files={},
                 expect={p: e}) for p in pids for e in (True, False)]


def metrics(policies, results, fps=(), waivers=(), since=None, cases=None):
    return build_metrics(policies, results, list(fps), list(waivers), today=TODAY,
                         window_days=90, repositories=[REPO], policy_since=since or {},
                         cases=cases if cases is not None else cases_for("FIN-MONEY-001"))


def row(m, pid):
    return next(r for r in m["policies"] if r["id"] == pid)


def test_only_the_latest_evaluation_of_each_pr_counts():
    old = {"result": result(7, "BLOCKED", [finding("ARCH-HEX-001", True)]),
           "created_at": "2026-10-01T10:00:00Z"}
    new = {"result": result(7), "created_at": "2026-10-02T10:00:00Z"}
    assert latest_per_pr([new, old]) == [new["result"]]


def test_warn_policy_with_enough_data_and_low_false_positive_is_ready(policies):
    results = [{"result": result(n, violations=[finding("FIN-MONEY-001")]),
                "created_at": f"2026-10-{n:02d}"} for n in range(1, 21)]
    m = metrics(policies, results, fps=[{"policy_id": "FIN-MONEY-001"}],
                since={"FIN-MONEY-001": date(2026, 10, 1)})
    fin = row(m, "FIN-MONEY-001")
    assert (fin["findings"], fin["prs"], fin["false_positives"]) == (20, 20, 1)
    assert fin["fp_rate"] == 0.05 and fin["readiness"] == "falso positivo alto"
    m = metrics(policies, results, since={"FIN-MONEY-001": date(2026, 10, 1)})
    assert row(m, "FIN-MONEY-001")["readiness"] == "pronta para enforce"
    assert m["overview"]["ready_for_enforce"] == ["FIN-MONEY-001"]


def test_missing_criteria_are_listed(policies):
    m = metrics(policies, [{"result": result(1, violations=[finding("FIN-MONEY-001")]),
                            "created_at": "2026-10-29"}],
                since={"FIN-MONEY-001": date(2026, 10, 25)}, cases=[])
    fin = row(m, "FIN-MONEY-001")
    assert fin["readiness"] == "coletando dados"
    assert any("eval" in x for x in fin["missing"])
    assert any("14 dias" in x for x in fin["missing"])
    assert any("amostra" in x for x in fin["missing"])
    assert row(m, "ARCH-HEX-001")["readiness"] == "enforce"


def test_overview_separates_blocking_by_rule_from_blocking_by_error(policies):
    results = [
        {"result": result(1, "BLOCKED", [finding("ARCH-HEX-001", True)]), "created_at": "a"},
        {"result": result(2, "BLOCKED", errors=[{"kind": "llm_unavailable"}]), "created_at": "a"},
        {"result": result(3), "created_at": "a"},
    ]
    o = metrics(policies, results)["overview"]
    assert (o["evaluations"], o["approved"], o["blocked"], o["blocked_by_error_only"]) == (3, 1, 2, 1)
    assert o["errors_by_kind"] == {"llm_unavailable": 1}


def test_expiring_waivers(policies):
    waiver = Waiver(id="W-1", policy_id="FIN-MONEY-001", repository=REPO, paths=("**",),
                    justification="x", requested_by="a", approved_by="b",
                    created=date(2026, 10, 1), expires=date(2026, 11, 10))
    m = metrics(policies, [], waivers=[waiver])
    assert m["waivers"]["expiring"][0]["days_left"] == 11


def test_html_escapes_content_and_markdown_skips_audit(policies):
    evil = finding("FIN-MONEY-001")
    m = metrics(policies, [{"result": result(1, violations=[evil]), "created_at": "a"}])
    m["repositories"] = ["<script>alert(1)</script>"]
    page = render_html(m)
    assert "<script>alert(1)" not in page and "&lt;script&gt;" in page
    assert "OWASP-A01" not in render_markdown(m)


class FakeClient:
    def __init__(self, artifacts, alerts):
        self.artifacts, self.alerts = artifacts, alerts

    def get_json(self, path):
        if "/actions/artifacts" in path:
            return {"artifacts": self.artifacts if "page=1" in path else []}
        pr = int(path.split("refs/pull/")[1].split("/")[0])
        return self.alerts.get(pr, []) if "page=1" in path else []

    def get_bytes(self, path):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("result.json", json.dumps(result(12, violations=[finding("FIN-MONEY-001")])))
        return buffer.getvalue()


def test_collect_reads_artifacts_and_false_positive_dismissals():
    artifacts = [
        {"id": 1, "name": "governance-abc", "expired": False, "created_at": "2026-10-20T00:00:00Z"},
        {"id": 2, "name": "governance-old", "expired": False, "created_at": "2026-01-01T00:00:00Z"},
        {"id": 3, "name": "outra-coisa", "expired": False, "created_at": "2026-10-20T00:00:00Z"},
    ]
    alerts = {12: [{"rule": {"id": "FIN-MONEY-001"}, "dismissed_reason": "false positive",
                    "dismissed_by": {"login": "dev"}},
                   {"rule": {"id": "ARCH-TIME-001"}, "dismissed_reason": "won't fix"}]}
    results, fps, warnings = collect(FakeClient(artifacts, alerts), [REPO], 90,
                                     now=datetime(2026, 10, 30, tzinfo=timezone.utc))
    assert len(results) == 1 and warnings == []
    assert fps == [{"repository": REPO, "pull_request": 12, "policy_id": "FIN-MONEY-001",
                    "dismissed_by": "dev", "comment": None}]
