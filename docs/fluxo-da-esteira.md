# Fluxo da esteira de governança

Como uma decisão de arquitetura vira regra, como essa regra avalia um Pull Request e
como a evidência chega ao deploy, à auditoria e ao painel de conformidade. São cinco
jornadas, cada uma com os arquivos que lê e os que gera.

- [1. Ciclo de vida de uma regra](#1-ciclo-de-vida-de-uma-regra) (time de plataforma, repositório central)
- [2. Adoção de um repositório-alvo](#2-adoção-de-um-repositório-alvo) (plataforma e time do produto, uma vez)
- [3. Avaliação de um Pull Request](#3-avaliação-de-um-pull-request) (a cada PR)
- [4. Deploy e auditoria](#4-deploy-e-auditoria)
- [5. Painel de conformidade e promoção de regras](#5-painel-de-conformidade-e-promoção-de-regras)
- [Arquivos: quem cria, quando é usado](#arquivos-quem-cria-quando-é-usado)

## 1. Ciclo de vida de uma regra

Passo a passo escrito, com cada campo e cada verificação explicados:
[manual-ciclo-de-vida-de-uma-regra.md](manual-ciclo-de-vida-de-uma-regra.md).

Uma decisão nasce como ADR e vira política, a partir dos templates. Nada chega aos
repositórios-alvo sem testes, validação, exports atualizados, eval sem regressão, tag
de release e smoke test (ADR-GOV-007).

```mermaid
sequenceDiagram
    autonumber
    actor Arq as Arquiteto / time de plataforma
    participant Tpl as templates/
    participant Central as Repositório central<br/>(governance-policies)
    participant CI as ci.yml
    participant LLM as OpenRouter / TypeSafe
    participant PoC as Repositório piloto (PoC)
    participant Dev as Claude Code do desenvolvedor

    Arq->>Tpl: copia adr-template.md
    Arq->>Central: adrs/ADR-AREA-NNN.md (contexto, decisão, alternativas, consequências)
    Arq->>Tpl: copia policy-template.yaml
    Arq->>Central: policies/ID.yaml (escopo, regra, severidade, modo warn,<br/>adr: ADR-AREA-NNN), no formato de policies/schema/policy.schema.json
    Arq->>Central: eval/cases/id-*.yaml (casos positivo e negativo;<br/>base_files quando a regra compara versões)
    opt Regra que depende da classe do repositório
        Arq->>Central: classification/repositories.yaml (raise_mode: a classe só endurece)
    end
    Arq->>Central: python -m governance export
    Central-->>Central: gera exports/aws-security-agent/governance-pack.json<br/>e .claude/rules/governance-policies.md (nunca editados à mão)
    Arq->>Central: sobe a versão do motor (e bundle_version, se mudou o bundle)
    Arq->>Central: abre PR (.github/CODEOWNERS exige o dono da área)
    Central->>CI: PR dispara o ci.yml
    CI->>CI: pytest + validate (schema, ADR citado existe, waivers,<br/>prompts, classificação, cobertura do eval, nenhum submódulo)
    CI->>CI: export --check (gerados em dia) + eval determinístico
    opt Mudança de modelo, prompt, bundle.yaml ou política com LLM
        Arq->>CI: eval --llm --repeat 5
        CI->>LLM: casos com requires_llm (conteúdo sem segredo nem dado pessoal)
        LLM-->>CI: achados / probabilidades
        CI-->>Arq: eval-llm-X.json (números vão na mensagem do commit)
    end
    Arq->>Central: merge + tag vX.Y.Z nova (tag publicada nunca se move)
    Arq->>PoC: smoke test: PR trocando a tag no governance.yml e no deploy.yml
    PoC-->>Arq: PR avaliado na versão nova; merge liberado pelo gate de deploy
    Central-->>Dev: .claude/rules/governance-policies.md orienta o assistente<br/>antes do PR (shift-left)
    Note over Arq,Central: Promoção warn → enforce: novo PR na política,<br/>com os números do painel (jornada 5)
```

## 2. Adoção de um repositório-alvo

O que o time de plataforma e o time do produto fazem, uma vez, para um repositório passar
a ser governado. Os arquivos saem de `templates/`; a classe e o painel ficam no
repositório central, para o repositório-alvo não poder mudá-los.

```mermaid
sequenceDiagram
    autonumber
    actor Plat as Time de plataforma
    participant Central as Repositório central
    participant Tpl as templates/
    actor Time as Time do produto
    participant Alvo as Repositório-alvo
    participant Org as Organização GitHub / AWS

    Plat->>Central: classification/repositories.yaml: classe do repositório<br/>(interno, confidencial, restrito)
    Plat->>Central: dashboard/repos.txt: entra no painel
    Note over Plat,Central: por PR, aprovado pelos CODEOWNERS
    alt Com organização
        Plat->>Tpl: org-ruleset.json
        Plat->>Org: ruleset: required workflow na tag, 1 aprovação de CODEOWNER,<br/>check governance / governance com PR atualizado, sem bypass
        Plat->>Org: secrets da org: OPENROUTER_API_KEY, TYPESAFE_API_KEY
    else Conta pessoal (provisório)
        Time->>Tpl: target-repo/governance.yml
        Time->>Alvo: .github/workflows/governance.yml (uses: ...@vX.Y.Z)
        Time->>Alvo: secrets do projeto (OpenRouter e TypeSafe)<br/>e ruleset: PR + check obrigatório + branch atualizado
    end
    Time->>Tpl: target-repo/CODEOWNERS e target-repo/deploy.yml
    Time->>Alvo: .github/CODEOWNERS (CI e instruções de IA com a plataforma)
    Time->>Alvo: deploy.yml: o deploy depende do gate de deploy
    opt Retenção de longo prazo
        Plat->>Tpl: evidence-store/main.tf
        Plat->>Org: bucket S3 com Object Lock (sa-east-1) e papel OIDC só de escrita
        Plat->>Central: EVIDENCE_BUCKET e EVIDENCE_ROLE_ARN no workflow central
    end
    Time->>Alvo: primeiro PR: avaliado pela classe definida no central (jornada 3)
```

## 3. Avaliação de um Pull Request

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
    Motor->>Motor: classe do repositório (classification/repositories.yaml):<br/>IA permitida? quais políticas endurecem?
    Motor->>Motor: git diff base...HEAD: arquivos, status,<br/>linhas adicionadas, conteúdo da base
    Motor->>Motor: seleciona políticas pelo scope
    Motor->>Motor: T0 determinístico: regex (+ CPF/CNPJ/Luhn),<br/>path_changed, requires_companion, contract
    opt Há política semântica no escopo e a classe permite IA
        Motor->>Motor: redact: remove segredos, CPF, CNPJ, cartão, e-mail
        Motor->>IA: arquivos do escopo (revisor) ou linhas candidatas (Jev)
        IA-->>Motor: achados ou probabilidades (só acrescentam)
    end
    Motor->>Motor: veredito = T0 ∪ T1 − waivers válidos<br/>erro, timeout ou entrada grande demais ⇒ BLOCKED
    Note over Motor: classe sem IA: a parte semântica não roda,<br/>fica registrada e não bloqueia
    Motor-->>WF: out/result.json (com a classe), out/results.sarif, out/report.md
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

## 4. Deploy e auditoria

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

## 5. Painel de conformidade e promoção de regras

Toda segunda-feira o painel transforma os vereditos em números. É deles que sai a
promoção de uma política de `warn` para `enforce` (ADR-GOV-003 e ADR-GOV-006).

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Desenvolvedor
    participant CS as Code Scanning<br/>(repositório-alvo)
    participant Dash as compliance-dashboard.yml<br/>(repositório central)
    participant GH as GitHub API<br/>(Artifacts, Code Scanning)
    actor Arq as Arquiteto / time de plataforma
    participant Central as Repositório central

    opt Achado errado num PR
        Dev->>CS: dispensa o alerta com o motivo "False positive"<br/>(não desbloqueia; entra na medição)
    end
    Dash->>Dash: segunda-feira 8h (ou Run workflow)<br/>lê dashboard/repos.txt, DASHBOARD_TOKEN
    Dash->>GH: artefatos governance-SHA dos últimos 90 dias
    GH-->>Dash: result.json da última avaliação de cada PR
    Dash->>GH: alertas da ferramenta enterprise-governance em cada PR
    GH-->>Dash: dispensados como "false positive"
    Dash->>Dash: por política: achados, PRs, bloqueios, falso positivo,<br/>dias no modo atual, prontidão para enforce
    Dash->>Dash: geral: aprovados, bloqueados, bloqueados só por erro,<br/>avaliações por classe, waivers vencendo
    Dash-->>Arq: artefato compliance-dashboard<br/>(dashboard.html, .json, .md) + resumo na execução
    alt Política pronta para enforce
        Arq->>Central: PR mudando mode: warn → enforce,<br/>citando os números do painel
    else Falso positivo alto
        Arq->>Central: PR corrigindo a regra (e novos casos de eval)
    end
```

## Arquivos: quem cria, quando é usado

| Arquivo | Quem cria | Quando é usado |
|---|---|---|
| `templates/adr-template.md`, `templates/policy-template.yaml` | Plataforma | Ponto de partida de um ADR e de uma política (jornada 1) |
| `adrs/ADR-*.md` | Arquiteto | Revisão humana; cada política aponta o seu ADR |
| `policies/*.yaml` | Arquiteto (PR com CODEOWNER) | Todo PR avaliado: escopo, regras, severidade, modo |
| `policies/schema/policy.schema.json` | Plataforma | `validate` no CI e na carga do motor |
| `waivers/*.yaml` | Solicitante + aprovador (AppSec) | Todo PR: exceção por repositório, caminho e prazo |
| `classification/repositories.yaml` | Segurança da informação | Todo PR: classe do repositório (IA permitida, políticas endurecidas) |
| `dashboard/repos.txt` | Plataforma | Painel semanal: repositórios medidos |
| `engine/bundle.yaml` | Plataforma (release do bundle) | Todo PR com política semântica: provedor, modelo, orçamento |
| `engine/governance/prompts/*.md` | Plataforma (release do bundle) | Revisor LLM generativo |
| `eval/cases/*.yaml` | Arquiteto | CI do central; `eval --llm` antes de release |
| `eval-llm-*.json` | `eval --llm` | Evidência para promover política ou trocar modelo |
| `exports/aws-security-agent/governance-pack.json` | `export` (gerado) | AWS Security Agent |
| `.claude/rules/governance-policies.md` | `export` (gerado) | Claude Code, antes do PR |
| `.github/CODEOWNERS` (central) | Plataforma | Todo PR no central: quem aprova política, classificação, waiver, motor |
| `templates/target-repo/*`, `templates/org-ruleset.json` | Plataforma | Adoção de um repositório (jornada 2) |
| `templates/evidence-store/main.tf` | Plataforma | Cria o bucket de evidências (jornada 2) |
| `governance.yml` (alvo) / ruleset da org | Plataforma | Dispara a avaliação em todo PR |
| `out/result.json` | Motor, a cada PR | Veredito e classe; atestado; lido pelo gate de deploy, pela auditoria e pelo painel |
| `out/results.sarif`, `out/gitleaks.sarif` | Motor, gitleaks | Anotações na linha (Code Scanning) |
| `out/report.md` | Motor | Comentário no PR e resumo da execução |
| Atestação (Sigstore) | `actions/attest` | Gate de deploy e auditoria: prova de origem |
| Artefato `governance-SHA` | Workflow do PR | Gate de deploy (até 90 dias) |
| Prefixo no bucket de evidências | Workflow do PR (OIDC) | Auditoria (retenção definida por compliance) |
| `deploy.yml` (alvo) | Time do produto | Chama o gate antes do deploy |
| Alerta dispensado como "False positive" | Desenvolvedor, no Code Scanning | Painel: taxa de falso positivo por política |
| Artefato `compliance-dashboard` | Painel semanal | Liderança e promoção `warn` → `enforce` (90 dias) |
