# Fluxo da esteira de governança

Como uma decisão de arquitetura vira regra, como essa regra avalia um Pull Request e
como a evidência chega ao deploy e à auditoria. São três jornadas, cada uma com os
arquivos que lê e os que gera.

- [1. Ciclo de vida de uma regra](#1-ciclo-de-vida-de-uma-regra) (time de plataforma, repositório central)
- [2. Avaliação de um Pull Request](#2-avaliação-de-um-pull-request) (repositório-alvo)
- [3. Deploy e auditoria](#3-deploy-e-auditoria)
- [Arquivos: quem cria, quando é usado](#arquivos-quem-cria-quando-é-usado)

## 1. Ciclo de vida de uma regra

Uma decisão nasce como ADR e vira política. Nada chega aos repositórios-alvo sem
testes, validação, exports atualizados e eval sem regressão; e só depois de uma tag de
release.

```mermaid
sequenceDiagram
    autonumber
    actor Arq as Arquiteto / time de plataforma
    participant Central as Repositório central<br/>(governance-policies)
    participant CI as ci.yml
    participant LLM as OpenRouter / TypeSafe
    participant Dev as Claude Code do desenvolvedor

    Arq->>Central: adrs/ADR-XXX.md (o porquê)
    Arq->>Central: policies/ID.yaml (o quê: escopo, regra, severidade, modo warn)
    Arq->>Central: eval/cases/id-*.yaml (casos positivo e negativo)
    Arq->>Central: python -m governance export
    Central-->>Central: gera exports/aws-security-agent/governance-pack.json<br/>e .claude/rules/governance-policies.md
    Arq->>Central: abre PR (CODEOWNERS exige aprovação do dono)
    Central->>CI: PR dispara o ci.yml
    CI->>CI: pytest (motor) + validate (schema das políticas,<br/>waivers, ADRs, prompts, cobertura do eval)
    CI->>CI: export --check (gerados em dia) + eval determinístico
    opt Mudança de modelo, prompt, bundle.yaml ou política com LLM
        Arq->>CI: workflow_dispatch: eval --llm --repeat 5
        CI->>LLM: casos com requires_llm (conteúdo sem segredo nem dado pessoal)
        LLM-->>CI: achados / probabilidades
        CI-->>Arq: eval-llm-X.json (evidência para promover a regra)
    end
    Arq->>Central: merge + tag vX.Y.Z (release do bundle)
    Central-->>Dev: .claude/rules/governance-policies.md orienta o assistente<br/>antes do PR (shift-left)
    Note over Arq,Central: Promoção warn → enforce: novo PR na política,<br/>com os critérios do ADR-GOV-003
```

## 2. Avaliação de um Pull Request

O repositório-alvo não controla nada da avaliação: o workflow, o motor, as políticas, os
prompts e o modelo vêm do repositório central, numa tag fixada. O código do PR é dado,
nunca instrução.

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Desenvolvedor
    participant Alvo as Repositório-alvo
    participant WF as governance-required.yml<br/>(workflow central)
    participant GL as gitleaks
    participant Motor as Motor (engine/governance)
    participant IA as OpenRouter / Jev
    participant GH as GitHub (PR, Code Scanning,<br/>Attestations, Artifacts)
    participant S3 as Bucket de evidências<br/>(Object Lock)

    Dev->>Alvo: abre ou atualiza o PR
    Alvo->>WF: governance.yml (conta pessoal) ou ruleset da org<br/>chama o workflow na tag fixada
    WF->>WF: checkout do PR em target/ (dado não confiável)
    WF->>WF: checkout do central em governance/ (mesma tag)<br/>pip install --require-hashes requirements.lock
    WF->>GL: varre os commits do PR (binário com SHA-256 conferido)
    GL-->>WF: out/gitleaks.sarif + código de saída
    WF->>Motor: python -m governance review
    Motor->>Motor: lê policies/*.yaml, waivers/*.yaml,<br/>engine/bundle.yaml, prompts/*.md
    Motor->>Motor: git diff base...HEAD: arquivos, status,<br/>linhas adicionadas, conteúdo da base
    Motor->>Motor: seleciona políticas pelo scope
    Motor->>Motor: T0 determinístico: regex (+ CPF/CNPJ/Luhn),<br/>path_changed, requires_companion, contract
    opt Há política semântica no escopo
        Motor->>Motor: redact: remove segredos, CPF, CNPJ, cartão, e-mail
        Motor->>IA: arquivos do escopo (revisor) ou linhas candidatas (Jev)
        IA-->>Motor: achados ou probabilidades (só acrescentam)
    end
    Motor->>Motor: veredito = T0 ∪ T1 − waivers válidos<br/>erro, timeout ou entrada grande demais ⇒ BLOCKED
    Motor-->>WF: out/result.json, out/results.sarif, out/report.md
    WF->>GH: comentário no PR (report.md) + SARIF no Code Scanning
    WF->>GH: atesta out/result.json (Sigstore, predicate governance-result/v1)
    GH-->>WF: bundle da atestação
    opt EVIDENCE_BUCKET configurado
        WF->>S3: OIDC → papel só de escrita<br/>result.json, report.md, SARIF, attestation.jsonl
    end
    WF->>GH: artefato governance-SHA do PR (out/, 90 dias)
    WF-->>Alvo: check governance / governance<br/>verde (APPROVED) ou vermelho (BLOCKED)
    Alvo-->>Dev: merge liberado só com check verde,<br/>aprovação de CODEOWNER e branch atualizado
```

## 3. Deploy e auditoria

O commit que vai para produção é o merge no main, que não é o commit avaliado. O gate de
deploy liga os dois pelo PR e só libera com evidência assinada pelo workflow central.

```mermaid
sequenceDiagram
    autonumber
    participant Pipe as deploy.yml<br/>(repositório-alvo)
    participant Gate as governance-deploy-gate.yml<br/>(workflow central)
    participant GH as GitHub (API, Artifacts,<br/>Attestations)
    participant Motor as Motor (verify-evidence)
    participant Prod as Produção
    actor Aud as Auditoria / compliance
    participant S3 as Bucket de evidências

    Pipe->>Gate: push no main chama o gate (tag fixada)
    Gate->>GH: commits/SHA/pulls: qual PR gerou o commit?
    GH-->>Gate: PR mergeado → último commit avaliado (head)
    alt Commit sem PR (push direto)
        Gate-->>Pipe: bloqueia: sem avaliação da governança
    end
    Gate->>GH: baixa o artefato governance-head
    GH-->>Gate: evidence/result.json
    Gate->>GH: gh attestation verify --signer-workflow<br/>(assinado pelo workflow central?)
    GH-->>Gate: assinatura válida ou inválida
    Gate->>Motor: verify-evidence: APPROVED, mesmo repositório,<br/>mesmo commit, sem erro, governance_ref presente
    alt Evidência válida
        Motor-->>Gate: liberado
        Gate-->>Pipe: ok
        Pipe->>Prod: deploy (environment production)
    else Qualquer dúvida
        Motor-->>Gate: motivos
        Gate-->>Pipe: bloqueado (resumo da execução explica)
    end
    Note over Aud,S3: Anos depois
    Aud->>S3: evidência do PR do commit em produção
    S3-->>Aud: result.json + attestation.jsonl (imutáveis até o fim da retenção)
    Aud->>Aud: gh attestation verify: prova que o workflow central,<br/>naquela versão de políticas, aprovou aquele commit
```

## Arquivos: quem cria, quando é usado

| Arquivo | Quem cria | Quando é usado |
|---|---|---|
| `adrs/ADR-*.md` | Arquiteto | Revisão humana; cada política aponta o seu ADR |
| `policies/*.yaml` | Arquiteto (PR com CODEOWNER) | Todo PR avaliado: escopo, regras, severidade, modo |
| `policies/schema/policy.schema.json` | Plataforma | `validate` no CI e na carga do motor |
| `waivers/*.yaml` | Solicitante + aprovador (AppSec) | Todo PR: exceção por repositório, caminho e prazo |
| `engine/bundle.yaml` | Plataforma (release do bundle) | Todo PR com política semântica: provedor, modelo, orçamento |
| `engine/governance/prompts/*.md` | Plataforma (release do bundle) | Revisor LLM generativo |
| `eval/cases/*.yaml` | Arquiteto | CI do central; `eval --llm` antes de release |
| `eval-llm-*.json` | `eval --llm` | Evidência para promover política ou trocar modelo |
| `exports/aws-security-agent/governance-pack.json` | `export` (gerado) | AWS Security Agent |
| `.claude/rules/governance-policies.md` | `export` (gerado) | Claude Code, antes do PR |
| `governance.yml` (alvo) / ruleset da org | Plataforma | Dispara a avaliação em todo PR |
| `out/result.json` | Motor, a cada PR | Veredito; atestado; lido pelo gate de deploy e pela auditoria |
| `out/results.sarif`, `out/gitleaks.sarif` | Motor, gitleaks | Anotações na linha (Code Scanning) |
| `out/report.md` | Motor | Comentário no PR e resumo da execução |
| Atestação (Sigstore) | `actions/attest` | Gate de deploy e auditoria: prova de origem |
| Artefato `governance-SHA` | Workflow do PR | Gate de deploy (até 90 dias) |
| Prefixo no bucket de evidências | Workflow do PR (OIDC) | Auditoria (retenção definida por compliance) |
| `deploy.yml` (alvo) | Time do produto | Chama o gate antes do deploy |
