import pytest
import yaml
from conftest import commit_files, git
from jsonschema import Draft202012Validator
from test_evaluation_layers import RESULT_SCHEMA

from governance.deterministic import run_deterministic
from governance.diff import as_new_files, collect_changes
from governance.hcl import parse, tokenize
from governance.model import ChangedFile, GovernanceError
from governance.policy import load_policies, select_policies
from governance.review import evaluate

TAG = "FINOPS-TAG-001"
K8S = "FINOPS-K8S-001"


def policy_of(policies, pid):
    return next(p for p in policies if p.id == pid)


def run(policies, pid, files, context=None):
    return run_deterministic([policy_of(policies, pid)], as_new_files(files, None, context))


PROVIDER_PLAIN = 'provider "aws" {\n  region = "sa-east-1"\n}\n'
PROVIDER_DEFAULT = ('provider "aws" {\n  region = "sa-east-1"\n  default_tags {\n    tags = {\n'
                    '      CostCenter = "1234"\n      Owner      = "pagamentos"\n    }\n  }\n}\n')
INSTANCE = 'resource "aws_instance" "web" {\n  ami = "ami-123"\n}\n'


def messages(findings):
    return [f.message for f in findings]


# ---------------------------------------------------------------- leitor de HCL


def test_hcl_reader_ignores_comments_and_braces_inside_strings_and_heredocs():
    text = (
        '# resource "aws_instance" "falso" {\n'
        '/* resource "aws_instance" "outro" { */\n'
        'resource "aws_instance" "real" {\n'
        '  user_data = <<-EOT\n    echo "}" # {\n  EOT\n'
        '  name      = "a}{b ${upper("}")}"\n'
        '  tags = {\n    CostCenter = "1"\n  }\n'
        '}\n')
    blocks = parse(text)
    assert [(b.type, b.labels, b.start, b.end) for b in blocks] == [
        ("resource", ("aws_instance", "real"), 3, 11)]
    assert set(blocks[0].attrs) == {"user_data", "name", "tags"}
    assert tokenize('x = "${a}$${b}"')[2].value == "${a}$${b}"


# ---------------------------------------------------------------- tags (Terraform)


def test_resource_without_tags_is_flagged_when_the_provider_has_no_default_tags(policies):
    findings = run(policies, TAG, {"infra/main.tf": PROVIDER_PLAIN + "\n" + INSTANCE})
    assert len(findings) == 1
    assert "aws_instance.web sem CostCenter, Owner" in findings[0].message
    assert findings[0].line == 5


@pytest.mark.parametrize("files,context", [
    ({"infra/main.tf": PROVIDER_DEFAULT + "\n" + INSTANCE}, None),
    ({"infra/main.tf": INSTANCE}, {"infra/providers.tf": PROVIDER_DEFAULT}),
])
def test_default_tags_of_the_provider_count_even_from_an_unchanged_file(policies, files, context):
    assert run(policies, TAG, files, context) == []


def test_unchanged_provider_without_default_tags_still_leaves_the_resource_flagged(policies):
    findings = run(policies, TAG, {"infra/main.tf": INSTANCE},
                   {"infra/providers.tf": PROVIDER_PLAIN})
    assert len(findings) == 1


def test_child_module_without_a_provider_is_not_flagged(policies):
    """Sem provider no diretório, as tags vêm do módulo raiz: o motor não afirma."""
    assert run(policies, TAG, {"modules/vm/main.tf": INSTANCE}) == []


def test_only_the_missing_tags_are_listed(policies):
    resource = ('resource "aws_s3_bucket" "dados" {\n  bucket = "x"\n'
                '  tags = {\n    "CostCenter" = "1"\n    Name = "dados"\n  }\n}\n')
    findings = run(policies, TAG, {"infra/main.tf": PROVIDER_PLAIN + resource})
    assert len(findings) == 1 and findings[0].message.endswith("aws_s3_bucket.dados sem Owner")


def test_locals_and_merge_are_resolved(policies):
    text = (PROVIDER_PLAIN
            + 'locals {\n  common_tags = {\n    CostCenter = "1"\n    Owner = "time"\n  }\n}\n'
            + 'resource "aws_instance" "web" {\n  ami = "x"\n'
              '  tags = merge(local.common_tags, { Name = "web" })\n}\n')
    assert run(policies, TAG, {"infra/main.tf": text}) == []
    incomplete = text.replace('Owner = "time"', 'Team = "time"')
    assert len(run(policies, TAG, {"infra/main.tf": incomplete})) == 1


@pytest.mark.parametrize("expression", [
    "var.tags", "module.base.tags", 'merge(var.tags, { Name = "x" })',
    'zipmap(["a"], ["b"])', "{ for k, v in var.map : k => v }"])
def test_tags_that_come_from_outside_are_not_asserted(policies, expression):
    resource = f'resource "aws_instance" "web" {{\n  ami = "x"\n  tags = {expression}\n}}\n'
    assert run(policies, TAG, {"infra/main.tf": PROVIDER_PLAIN + resource}) == []


def test_resource_types_outside_the_list_and_untouched_resources_are_ignored(policies):
    other = 'resource "aws_security_group" "sg" {\n  name = "x"\n}\n'
    assert run(policies, TAG, {"infra/main.tf": PROVIDER_PLAIN + other}) == []
    content = PROVIDER_PLAIN + "\n" + INSTANCE
    untouched = ChangedFile(path="infra/main.tf", content=content, added_lines={99: "x"})
    assert run_deterministic([policy_of(policies, TAG)], [untouched]) == []
    touched = ChangedFile(path="infra/main.tf", content=content, added_lines={6: "  ami"})
    assert len(run_deterministic([policy_of(policies, TAG)], [touched])) == 1


def test_provider_alias_decides_which_default_tags_apply(policies):
    text = (PROVIDER_PLAIN
            + 'provider "aws" {\n  alias  = "west"\n  region = "us-west-2"\n  default_tags {\n'
              '    tags = { CostCenter = "1", Owner = "x" }\n  }\n}\n'
            + 'resource "aws_instance" "a" {\n  provider = aws.west\n  ami = "x"\n}\n'
            + 'resource "aws_instance" "b" {\n  ami = "x"\n}\n')
    findings = run(policies, TAG, {"infra/main.tf": text})
    assert [f.message.split(": ")[1].split(" sem")[0] for f in findings] == ["aws_instance.b"]


# ---------------------------------------------------------------- requests e limits (Kubernetes)

COMPLETE = ("          resources:\n            requests: {cpu: 250m, memory: 256Mi}\n"
            "            limits: {memory: 512Mi}\n")


def deployment(containers, kind="Deployment", head=""):
    return (f"{head}apiVersion: apps/v1\nkind: {kind}\nmetadata:\n  name: pedidos\nspec:\n"
            "  template:\n    spec:\n      containers:\n" + containers)


def test_container_without_resources_is_flagged_with_workload_and_name(policies):
    manifest = deployment("        - name: api\n          image: pedidos:1\n")
    findings = run(policies, K8S, {"k8s/deploy.yaml": manifest})
    assert len(findings) == 1 and findings[0].line == 9
    assert ("Deployment 'pedidos', container 'api' sem resources.requests.cpu, "
            "resources.requests.memory, resources.limits.memory") in findings[0].message


def test_complete_containers_and_other_kinds_are_not_flagged(policies):
    manifest = (deployment("        - name: api\n          image: pedidos:1\n" + COMPLETE)
                + "---\napiVersion: v1\nkind: Service\nmetadata:\n  name: s\nspec:\n  ports: []\n"
                + "---\nkey: not-a-manifest\n")
    assert run(policies, K8S, {"k8s/deploy.yaml": manifest}) == []


def test_missing_single_quantity_is_named(policies):
    manifest = deployment("        - name: api\n          image: x\n"
                          "          resources:\n            requests: {memory: 256Mi}\n"
                          "            limits: {memory: 512Mi}\n")
    findings = run(policies, K8S, {"k8s/deploy.yaml": manifest})
    assert messages(findings)[0].endswith("sem resources.requests.cpu")


def test_cronjob_pod_and_statefulset_paths(policies):
    cron = ("apiVersion: batch/v1\nkind: CronJob\nmetadata:\n  name: nightly\nspec:\n"
            "  jobTemplate:\n    spec:\n      template:\n        spec:\n          containers:\n"
            "            - name: job\n              image: x\n")
    pod = ("apiVersion: v1\nkind: Pod\nmetadata:\n  name: p\nspec:\n  containers:\n"
           "    - name: c\n      image: x\n")
    findings = run(policies, K8S, {"k8s/cron.yaml": cron, "k8s/pod.yaml": pod,
                                   "k8s/sts.yaml": deployment("        - {name: d, image: x}\n",
                                                              kind="StatefulSet")})
    assert len(findings) == 3


def test_only_the_touched_container_is_flagged(policies):
    manifest = deployment("        - name: sidecar\n          image: a\n"
                          "        - name: api\n          image: b\n")
    only_second = ChangedFile(path="k8s/d.yaml", content=manifest, added_lines={12: "image: b"})
    findings = run_deterministic([policy_of(policies, K8S)], [only_second])
    assert len(findings) == 1 and "container 'api'" in findings[0].message


def test_helm_templates_are_skipped_and_broken_manifests_are_flagged(policies):
    templated = ("apiVersion: apps/v1\nkind: Deployment\nspec:\n  replicas: {{ .Values.n }}\n")
    broken = "apiVersion: apps/v1\nkind: Deployment\nspec: [unclosed\n"
    unrelated = "name: x\nitems: [unclosed\n"
    assert run(policies, K8S, {"chart/templates/d.yaml": templated}) == []
    assert run(policies, K8S, {"other/config.yaml": unrelated}) == []
    findings = run(policies, K8S, {"k8s/broken.yaml": broken})
    assert len(findings) == 1 and "manifesto ilegível" in findings[0].message


# ---------------------------------------------------------------- Spring (regex)


@pytest.mark.parametrize("text,fires", [
    ("server:\n  shutdown: immediate\n", True),
    ("server.shutdown=immediate\n", True),
    ("server:\n  shutdown: graceful\n", False),
    ("# server.shutdown=immediate\n", False),
    ("server:\n  port: 8080\n", False),
])
def test_explicit_immediate_shutdown(policies, text, fires):
    path = "app/src/main/resources/application.yml"
    assert bool(run(policies, "FINOPS-SHUTDOWN-001", {path: text})) is fires


# ---------------------------------------------------------------- motor: contexto e validação


def test_context_files_do_not_select_policies_nor_count_as_changed(policies):
    context_only = [ChangedFile(path="infra/providers.tf", content=PROVIDER_DEFAULT,
                                status="context")]
    assert select_policies(policies, context_only, "pr-review") == []
    changed = as_new_files({"infra/main.tf": INSTANCE}, None,
                           {"infra/providers.tf": PROVIDER_DEFAULT})
    assert [select_policies(policies, changed, "pr-review") and f.path for f in changed] == [
        "infra/providers.tf", "infra/main.tf"]


def test_stats_count_only_changed_files(policies, bundle):
    files = as_new_files({"infra/main.tf": INSTANCE}, None,
                         {"infra/providers.tf": PROVIDER_PLAIN})
    result = evaluate(
        files, policies=policies, waivers=[], provider=None, bundle=bundle,
        subject={"repository": "org/app", "commit": "abc", "base": "main", "pull_request": 1},
        governance_ref="v1.10.0", policies_digest="0" * 64, llm_required=False)
    Draft202012Validator(RESULT_SCHEMA).validate(result)
    assert result["stats"]["files_changed"] == 1
    assert [v["policy_id"] for v in result["violations"]] == [TAG]


def test_collect_changes_reads_the_terraform_siblings_as_context(repo):
    commit_files(repo, {"infra/main.tf": INSTANCE, "infra/providers.tf": PROVIDER_DEFAULT,
                        "infra/outputs.tf": 'output "x" {\n  value = 1\n}\n'})
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "feature")
    git(repo, "checkout", "-q", "-b", "pr")
    commit_files(repo, {"infra/main.tf": INSTANCE + '\nresource "aws_sqs_queue" "q" {\n}\n'})
    files = {f.path: f for f in collect_changes(repo, "main")}
    assert files["infra/main.tf"].status == "modified"
    assert files["infra/providers.tf"].status == "context"
    assert files["infra/outputs.tf"].status == "context"
    assert files["infra/providers.tf"].added_lines == {}


@pytest.mark.parametrize("rule,message", [
    ({"type": "structured", "check": "terraform_tags", "params": {"required_tags": []},
      "message": "m"}, "required_tags"),
    ({"type": "structured", "check": "kubernetes_resources", "params": {}, "message": "m"},
     "informe params.requests"),
    ({"type": "structured", "check": "kubernetes_resources",
      "params": {"requests": ["gpu"]}, "message": "m"}, "aceita só"),
])
def test_invalid_structured_parameters_invalidate_the_bundle(policies, tmp_path, rule, message):
    source = policy_of(policies, K8S)
    data = {**source.raw, "enforcement": {"deterministic": [rule]}}
    (tmp_path / "FINOPS-K8S-001.yaml").write_text(yaml.safe_dump(data, allow_unicode=True),
                                                  encoding="utf-8")
    with pytest.raises(GovernanceError, match=message):
        load_policies(tmp_path)
