# Armazenamento imutável das evidências da governança (ADR-GOV-005).
#
# - Bucket S3 com Object Lock em modo COMPLIANCE: nem a conta root apaga ou altera uma
#   evidência antes do fim da retenção.
# - Criptografia com chave KMS gerenciada pelo cliente (CMK), só TLS, sem acesso público.
# - Papel que SÓ o workflow central assume (OIDC do GitHub) e que só pode gravar.
#
# Pré-requisito: o provedor OIDC do GitHub na conta e a customização do claim `sub` para
# incluir `job_workflow_ref` nos repositórios-alvo (ou na organização):
#   gh api -X PUT repos/<owner>/<repo>/actions/oidc/customization/sub \
#     -F use_default=false -f 'include_claim_keys[]=repo' -f 'include_claim_keys[]=context' \
#     -f 'include_claim_keys[]=job_workflow_ref'
# Sem isso o `sub` não diz qual workflow pediu o token e qualquer job do repositório-alvo
# poderia gravar evidência em nome da governança.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "region" {
  description = "Região aprovada para a evidência (ADR-DATA-002)"
  type        = string
  default     = "sa-east-1"
}

variable "bucket_name" {
  type = string
}

variable "retention_years" {
  description = "Retenção definida por compliance/jurídico"
  type        = number
  default     = 5
}

variable "github_owner" {
  description = "Dono (usuário ou organização) dos repositórios-alvo"
  type        = string
}

variable "governance_repository" {
  description = "owner/repo do repositório central de governança"
  type        = string
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_kms_key" "evidence" {
  description         = "Evidências da governança de PR"
  enable_key_rotation = true
}

resource "aws_s3_bucket" "evidence" {
  bucket              = var.bucket_name
  object_lock_enabled = true
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    default_retention {
      mode  = "COMPLIANCE"
      years = var.retention_years
    }
  }
  depends_on = [aws_s3_bucket_versioning.evidence]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.evidence.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket                  = aws_s3_bucket.evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "tls_only" {
  statement {
    sid       = "SomenteTLS"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.evidence.arn, "${aws_s3_bucket.evidence.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  policy = data.aws_iam_policy_document.tls_only.json
}

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Qualquer repositório do dono, mas só pelo workflow central, numa tag de release.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_owner}/*:*:job_workflow_ref:${var.governance_repository}/.github/workflows/governance-required.yml@refs/tags/*",
      ]
    }
  }
}

resource "aws_iam_role" "writer" {
  name                 = "governance-evidence-writer"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "write_only" {
  statement {
    sid       = "GravarEvidencia"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.evidence.arn}/*"]
  }
  statement {
    sid       = "CriptografarComACMK"
    actions   = ["kms:GenerateDataKey", "kms:Encrypt"]
    resources = [aws_kms_key.evidence.arn]
  }
}

resource "aws_iam_role_policy" "writer" {
  name   = "gravar-evidencia"
  role   = aws_iam_role.writer.id
  policy = data.aws_iam_policy_document.write_only.json
}

output "evidence_bucket" {
  description = "Valor de EVIDENCE_BUCKET no governance-required.yml"
  value       = aws_s3_bucket.evidence.id
}

output "evidence_role_arn" {
  description = "Valor de EVIDENCE_ROLE_ARN no governance-required.yml"
  value       = aws_iam_role.writer.arn
}
