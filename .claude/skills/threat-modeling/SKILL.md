---
name: threat-modeling
description: Automates STRIDE-based threat modeling and OWASP Top 10:2025 risk identification by synthesizing scope docs and source code.
---

# Threat Modeling Skill (STRIDE + OWASP Top 10:2025)

## Overview
This skill provides structured reasoning procedures for the AWS Security Agent to perform threat modeling on application architecture documents (`scope docs`) and repository source code.

## Workflow

### 1. Ingestion & Boundary Mapping
- Analyze `scope docs` (architecture diagrams, API specs) to identify:
  - System components (services, databases, Lambda functions)
  - Data flows and protocols
  - Trust boundaries (e.g., public internet to VPC, IAM role transitions)

### 2. STRIDE Categorization
Evaluate each trust boundary crossing against the 6 STRIDE threats:
- **Spoofing**: Unauthenticated callers or weak JWT verification (OWASP A07:2025).
- **Tampering**: Missing payload signatures or unencrypted transit (OWASP A08:2025).
- **Repudiation**: Missing audit logging in CloudTrail/CloudWatch (OWASP A09:2025).
- **Information Disclosure**: Cleartext data or stack trace exposure (OWASP A04/A10:2025).
- **Denial of Service**: Unthrottled API Gateway endpoints or resource exhaustion.
- **Elevation of Privilege**: Over-privileged IAM roles, IDOR, or Broken Access Control (OWASP A01:2025).

### 3. Report Generation
Output a structured system overview and threat matrix including:
- Threat Statement
- STRIDE Category & OWASP Top 10 Mapping
- Impact Rating & CVSS v3.1 Estimate
- Actionable Remediation Steps
