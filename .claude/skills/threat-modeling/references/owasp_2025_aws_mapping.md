# OWASP Top 10:2025 - Mapeamento com AWS Security Agent & AWS Native Services

| Categoria OWASP Top 10:2025 | Mapeamento CWE | Fase de Detecção no AWS Security Agent | Serviço de Mitigação Nativo AWS |
| :--- | :--- | :--- | :--- |
| **A01:2025 - Broken Access Control** | CWE-284, CWE-639 (IDOR), CWE-918 (SSRF) | Design Review, Code Review (PR), Pentest | Amazon Verified Permissions, AWS WAF, IAM |
| **A02:2025 - Security Misconfiguration** | CWE-16, CWE-489, CWE-611 | Code Review (PR), Differential Scan | AWS Config, AWS Security Hub, S3 Block Public Access |
| **A03:2025 - Software Supply Chain Failures** | CWE-1104, CWE-1329, CWE-1395 | Code Review (PR / SBOM) | Amazon Inspector, Amazon CodeArtifact |
| **A04:2025 - Cryptographic Failures** | CWE-319, CWE-321, CWE-327 | Design Review, Code Review | AWS KMS (Customer Managed Keys), AWS Secrets Manager |
| **A05:2025 - Injection** | CWE-78, CWE-79 (XSS), CWE-89 (SQLi) | Pentest (Swarm Workers), Code Review | AWS WAF, Amazon GuardDuty |
| **A06:2025 - Insecure Design** | CWE-269, CWE-501, CWE-657 | Design Review (Scope Docs), Threat Modeling | AWS Security Reference Architecture (AWS SRA) |
| **A07:2025 - Authentication Failures** | CWE-287, CWE-307 | Pentest (Auth Component), Design Review | Amazon Cognito, AWS IAM Identity Center |
| **A08:2025 - Software & Data Integrity Failures**| CWE-345, CWE-502 | Code Review, Pentest | AWS Signer, AWS CodePipeline |
| **A09:2025 - Security Logging Failures** | CWE-778, CWE-117 | Design Review, Code Review | AWS CloudTrail, Amazon CloudWatch Logs |
| **A10:2025 - Mishandling of Exceptional Conditions**| CWE-550, CWE-636, CWE-703 | Pentest, Code Review | AWS Lambda Exception Handlers, CloudWatch Alarms |
