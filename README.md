# Plataforma de Governança e SecLLMOps

Políticas-como-código avaliadas em todo Pull Request da organização, com regras
determinísticas como base, revisão semântica por LLM apenas como camada aditiva, e
evidência atestada por commit.

**Versão atual: v1.10.0** (motor 1.10.0, bundle 1.6.0, `result.json` 1.3). A v1.9.0 foi
validada de ponta a ponta na PoC `virtualthreads` (PR aprovado, aprovado com alertas e
bloqueado; merge recusado com check vermelho; push direto recusado; deploy liberado só
com evidência assinada); a v1.10.0 aguarda o smoke test do
[ADR-GOV-007](adrs/ADR-GOV-007-release-e-versionamento.md).

**Guia completo** (regras, funcionamento, como usar, como aplicar, boas práticas e
problemas comuns): [docs/guia.md](docs/guia.md).

**Manual de configuração** (passo a passo para ligar a governança em um repositório, do
zero ao primeiro PR bloqueado): [docs/manual-configuracao.md](docs/manual-configuracao.md).

**Manual do ciclo de vida de uma regra** (cada etapa e cada arquivo, do ADR à política,
aos casos de eval, ao eval com e sem LLM, à release e à promoção para `enforce`):
[docs/manual-ciclo-de-vida-de-uma-regra.md](docs/manual-ciclo-de-vida-de-uma-regra.md).

**Fluxo da esteira** (diagramas de sequência Mermaid das cinco jornadas: ciclo de vida de
uma regra, dos templates e ADRs à release; adoção de um repositório-alvo; avaliação do
PR; deploy e auditoria; painel de conformidade; e cada arquivo lido ou gerado):
[docs/fluxo-da-esteira.md](docs/fluxo-da-esteira.md).

Decisão de arquitetura: [ADR-GOV-000](adrs/ADR-GOV-000-modelo-de-governanca.md). Todas as
decisões estão em [Decisões de arquitetura (ADRs)](#decisões-de-arquitetura-adrs).
Origem: a PoC `virtualthreads` (pipeline Gemini no PR) e o roteiro em
`docs/Governança SecLLMOps Enterprise.docx`.

## Decisões de arquitetura (ADRs)

O ADR explica o porquê; a regra verificável fica em `policies/*.yaml`, que aponta o seu
ADR. *Proposto* = depende de decisão fora do time de plataforma (jurídico, segurança da
informação, plataforma corporativa).

**A plataforma**

| ADR | Decisão | Status |
|---|---|---|
| [ADR-GOV-000](adrs/ADR-GOV-000-modelo-de-governanca.md) | Modelo: quem governa fica separado de quem é governado; determinístico primeiro, LLM só aditivo; uma regra, uma fonte; fail-closed | Aceito |
| [ADR-GOV-001](adrs/ADR-GOV-001-provedor-llm-openrouter.md) | Provedor de LLM via OpenRouter, com modelo fixo e chave por projeto | Aceito |
| [ADR-GOV-002](adrs/ADR-GOV-002-julgamento-tipado-jev.md) | Julgamento tipado (Jev): a regex localiza, o modelo só devolve probabilidade | Aceito |
| [ADR-GOV-003](adrs/ADR-GOV-003-operacao-em-instituicao-financeira.md) | Operação em instituição financeira: dado pessoal fora do LLM, provedor de IA (CMN 4.893, LGPD Art. 33), rollout `warn` → `enforce`, segregação de funções | Proposto |
| [ADR-GOV-004](adrs/ADR-GOV-004-decisao-estrutural-exige-adr.md) | Decisão estrutural (dependência, módulo, datastore novo) chega com o seu ADR | Aceito |
| [ADR-GOV-005](adrs/ADR-GOV-005-gate-de-deploy-e-retencao-de-evidencia.md) | Gate de deploy verifica a atestação; evidência em armazenamento imutável | Aceito |
| [ADR-GOV-006](adrs/ADR-GOV-006-painel-de-conformidade.md) | Painel de conformidade; falso positivo medido pelo Code Scanning | Aceito |
| [ADR-GOV-007](adrs/ADR-GOV-007-release-e-versionamento.md) | Release e versionamento: tag não se move, smoke test no destino, sem submódulo | Aceito |
| [ADR-GOV-008](adrs/ADR-GOV-008-skills-como-orientacao.md) | Skills orientam, políticas decidem; triagem das skills; políticas como fitness functions | Aceito |
| [ADR-GOV-009](adrs/ADR-GOV-009-classificacao-de-repositorios.md) | Classificação de repositórios: a classe decide se o código vai para a IA e quais regras endurecem | Aceito |
| [ADR-FINOPS-002](adrs/ADR-FINOPS-002-custo-da-esteira.md) | O custo da própria esteira é medido: consumo de IA por PR na evidência e no painel | Aceito |

**Regras para o código dos repositórios-alvo**

| ADR | Decisão | Políticas | Status |
|---|---|---|---|
| [ADR-ARCH-001](adrs/ADR-ARCH-001-arquitetura-hexagonal.md) | Domínio isolado na arquitetura hexagonal | ARCH-HEX-001/002 | Aceito |
| [ADR-ARCH-002](adrs/ADR-ARCH-002-relogio-e-fuso-explicitos.md) | Relógio injetável e fuso explícito na regra de negócio | ARCH-TIME-001 | Aceito |
| [ADR-FIN-001](adrs/ADR-FIN-001-aritmetica-monetaria.md) | Aritmética monetária exata e arredondamento explícito | FIN-MONEY-001 | Aceito |
| [ADR-FIN-002](adrs/ADR-FIN-002-idempotencia-em-escrita-financeira.md) | Escrita financeira idempotente; nada de retry cego | RES-IDEMP-001 | Aceito |
| [ADR-LGPD-001](adrs/ADR-LGPD-001-dado-pessoal-em-observabilidade.md) | Dado pessoal fora de logs, traces, métricas e exceções | LGPD-LOG-001 | Aceito |
| [ADR-LGPD-002](adrs/ADR-LGPD-002-dado-pessoal-real-no-repositorio.md) | Repositório não é ambiente para dado pessoal real | LGPD-DATA-001 | Aceito |
| [ADR-SEC-001](adrs/ADR-SEC-001-segredos-e-manipulacao-de-revisores.md) | Segredos, ofuscação e manipulação de revisores | SEC-SECRET/UNICODE/OBFUSC-001, LLM-INJ-001 | Aceito |
| [ADR-SEC-002](adrs/ADR-SEC-002-requisitos-owasp-2025.md) | Requisitos OWASP Top 10:2025; configuração Spring segura | OWASP-A01..A10, SEC-CONFIG-001 | Aceito |
| [ADR-SEC-003](adrs/ADR-SEC-003-criptografia-e-dados-de-cartao.md) | Criptografia verificável e nenhum dado de cartão no repositório | SEC-CRYPTO-001, SEC-PAN-001 | Aceito |
| [ADR-DATA-001](adrs/ADR-DATA-001-evolucao-de-schema.md) | Migrações imutáveis e expand/contract | DATA-MIG-001/002 | Aceito |
| [ADR-DATA-002](adrs/ADR-DATA-002-residencia-de-dados.md) | Residência de dados em região aprovada | DATA-RES-001 | Proposto |
| [ADR-API-001](adrs/ADR-API-001-contratos-compativeis.md) | Contratos de API e de eventos evoluem sem quebrar consumidores | API-CONTRACT-001, EVT-SCHEMA-001 | Aceito |
| [ADR-SUP-001](adrs/ADR-SUP-001-cadeia-de-suprimentos-reproduzivel.md) | Build e imagem reproduzíveis | SUP-DEP-001, SUP-IMG-001 | Aceito |
| [ADR-AI-001](adrs/ADR-AI-001-ia-nas-aplicacoes.md) | IA pelo gateway corporativo e com modelo fixado | AI-GW-001, AI-MODEL-001, GOV-SELF-001 | Proposto |
| [ADR-AI-002](adrs/ADR-AI-002-principios-eticos-como-guardrails.md) | Princípios éticos de IA como guardrails | AI-HUMAN-001, AI-FAIR-001, AI-INV-001 | Aceito |
| [ADR-QUAL-001](adrs/ADR-QUAL-001-regras-de-qualidade.md) | Regras objetivas de qualidade de código | QUAL-CODE-001 | Aceito |
| [ADR-FINOPS-001](adrs/ADR-FINOPS-001-finops-no-pull-request.md) | FinOps no PR: o que o gate verifica (tags de custo, requests/limits, desligamento gracioso) e o que fica de fora | FINOPS-TAG-001, FINOPS-K8S-001, FINOPS-SHUTDOWN-001 | Aceito |

Novo ADR: [templates/adr-template.md](templates/adr-template.md).

## Como funciona

1. O ruleset da organização exige o workflow
   [governance-required.yml](.github/workflows/governance-required.yml) em todo PR, numa
   ref fixada deste repositório. O repo-alvo não consegue alterá-lo.
2. O workflow faz checkout do PR (como dado) e do motor (desta revisão), roda o gitleaks
   nos commits do PR e o motor sobre o diff.
3. O motor lê a **classe do repositório** em `classification/repositories.yaml`
   ([ADR-GOV-009](adrs/ADR-GOV-009-classificacao-de-repositorios.md)): `interno` usa IA;
   `confidencial`, `restrito` e `nao-classificado` rodam sem IA (registrado, sem
   bloquear por isso); `restrito` sobe SEC-PAN-001, LGPD-DATA-001 e SEC-CRYPTO-001 para
   `enforce`. Depois escolhe as políticas cujo `scope` casa com os arquivos alterados e aplica:
   - **T0 determinístico**: bloqueia em `enforce` + `CRITICAL`. Tipos de regra:
     `regex` nas linhas adicionadas (com `validator` confere dígito verificador de
     CPF/CNPJ e Luhn de cartão); `path_changed` (arquivo adicionado, modificado,
     renomeado ou removido); `requires_companion` (se X muda, Y também precisa mudar, ex.:
     dependência nova exige ADR); `contract` (compara base e PR de um contrato OpenAPI ou
     Avro e aponta cada quebra de compatibilidade); `structured` (lê a estrutura do arquivo:
     as tags de custo de um recurso Terraform, os `requests`/`limits` de um contêiner
     Kubernetes; só afirma o que dá para afirmar e só olha o que o PR alterou);
   - **T1 LLM** (só políticas com `enforcement.llm`): recebe o conteúdo sem segredos e
     sem CPF, CNPJ, cartão e e-mail literais (trocados por um marcador do tipo),
     delimitado por uma tag com nonce; só acrescenta achados; só bloqueia com
     `llm.blocking: true`, que exige evidência de eval.
4. Waivers válidos (aprovador ≠ solicitante, até 90 dias) são descontados.
5. Saídas: comentário no PR, SARIF no Code Scanning, `result.json` atestado (Sigstore),
   guardado como artefato e, com a retenção configurada, gravado num bucket imutável
   (Object Lock). Qualquer erro bloqueia.
6. No deploy, o [gate de deploy](.github/workflows/governance-deploy-gate.yml) acha o PR
   do commit implantado, verifica a atestação (assinada pelo workflow central) e o
   veredito. Sem PR aprovado, não implanta
   ([ADR-GOV-005](adrs/ADR-GOV-005-gate-de-deploy-e-retencao-de-evidencia.md)).
7. Toda segunda-feira, o [painel de conformidade](.github/workflows/compliance-dashboard.yml)
   consolida os vereditos dos repositórios de `dashboard/repos.txt`: achados, bloqueios e
   falso positivo por política (alerta dispensado como "False positive" no Code
   Scanning), prontidão de cada política para `enforce`, bloqueios por erro da esteira e
   waivers vencendo ([ADR-GOV-006](adrs/ADR-GOV-006-painel-de-conformidade.md)).
   O painel também mostra o custo de IA da própria esteira (total, média por PR e por
   modelo; [ADR-FINOPS-002](adrs/ADR-FINOPS-002-custo-da-esteira.md)).
   Localmente: `python -m governance dashboard --repo owner/repo` (com `GITHUB_TOKEN`).

Fluxo completo, arquivos lidos e gerados em cada etapa:
[docs/fluxo-da-esteira.md](docs/fluxo-da-esteira.md).

## Políticas

| Id | Modo | Camadas |
|---|---|---|
| ARCH-HEX-001 domínio sem Spring/JPA | enforce | regex + ArchUnit no build |
| ARCH-HEX-002 camadas internas sem infrastructure | enforce | regex + ArchUnit no build |
| LGPD-LOG-001 dado pessoal em log/trace/métrica | enforce | regex (bloqueia) + LLM (consultivo) |
| SEC-SECRET-001 credencial versionada | enforce | regex + gitleaks |
| SEC-UNICODE-001 caracteres invisíveis/bidi | enforce | regex |
| SEC-OBFUSC-001 escape Unicode fora de literal (Java) | enforce | regex |
| FIN-MONEY-001 dinheiro em double/float, divide/setScale sem RoundingMode | warn | regex |
| SEC-CRYPTO-001 hash/cifra fraca, TLS antigo, verificação desligada, Random em segredo | warn | regex |
| SEC-PAN-001 número de cartão versionado (PCI DSS) | warn | regex + Luhn |
| LGPD-DATA-001 CPF válido versionado (massa de teste, config, docs) | warn | regex + dígito verificador |
| SEC-CONFIG-001 configuração Spring insegura em produção | warn | regex |
| DATA-MIG-001 migração versionada editada, renomeada ou removida | warn | path (só modificado) |
| DATA-MIG-002 DDL/DML destrutivo sem expand/contract | warn | regex |
| DATA-RES-001 região de nuvem fora da lista aprovada (Terraform) | warn | regex |
| ARCH-TIME-001 relógio/fuso da máquina no domínio | warn | regex |
| API-CONTRACT-001 quebra de contrato OpenAPI | warn | contract (base × PR) |
| EVT-SCHEMA-001 quebra de schema Avro | warn | contract (base × PR) |
| RES-IDEMP-001 retry em escrita financeira sem idempotência | warn | regex de candidatos + Jev |
| SUP-DEP-001 dependência SNAPSHOT ou versão flutuante | warn | regex |
| SUP-IMG-001 imagem sem digest, root, curl \| sh | warn | regex |
| AI-GW-001 SDK ou endpoint de LLM fora do gateway corporativo | warn | regex |
| AI-MODEL-001 modelo de IA não fixado (latest/auto/roteador) | warn | regex |
| AI-HUMAN-001 decisão sobre cliente tomada só pela IA (LGPD Art. 20) | warn | regex de candidatos + Jev |
| AI-FAIR-001 dado pessoal sensível em modelo, score ou regra de decisão | warn | regex de candidatos + Jev |
| AI-INV-001 uso novo de IA sem entrada no inventário de IA | warn | requires_companion |
| FINOPS-TAG-001 recurso Terraform sem as tags de custo (CostCenter, Owner), somando `default_tags` | warn | structured |
| FINOPS-K8S-001 contêiner Kubernetes sem requests e limits | warn | structured |
| FINOPS-SHUTDOWN-001 `server.shutdown: immediate` em produção | warn | regex |
| GOV-ADR-001 dependência, módulo ou datastore novo sem ADR no PR | warn | requires_companion |
| LLM-INJ-001 texto dirigido a IA | warn | regex + LLM (sinal) |
| GOV-SELF-001 mudança em CI, instruções de IA ou configuração de agentes (MCP) | warn | path |
| QUAL-CODE-001 regras objetivas de qualidade | warn | LLM |
| OWASP-A01/A02/A03/A04/A10 | audit | só exportadas para o AWS Security Agent |

Toda política nova entra em `warn` e sobe para `enforce` pelos critérios do
ADR-GOV-003: casos no eval, duas semanas em `warn` nos repositórios piloto e falso
positivo abaixo de 5% (números no painel de conformidade). A classe `restrito` já roda
SEC-PAN-001, LGPD-DATA-001 e SEC-CRYPTO-001 em `enforce` (ADR-GOV-009). Cada política
aponta o ADR que explica o porquê (`adrs/`).

### Evolução de FinOps

As regras de FinOps do PR e a fronteira do que o gate verifica estão no
[ADR-FINOPS-001](adrs/ADR-FINOPS-001-finops-no-pull-request.md). Falta a estimativa de custo
da mudança (ferramenta externa, com o limite aplicado pelo motor): o desenho está no ADR e
depende do dono do orçamento e da aprovação do serviço de preços. O teste de encerramento
(SIGTERM) e o canary com rollback por custo são do pipeline de deploy, não do gate.

### Pendências para produção em instituição financeira

- Contratar o provedor de LLM e o Jev como serviço de nuvem avaliado (retenção zero,
  sem treino, região definida, Resolução CMN 4.893 e LGPD Art. 33). Até lá, LLM só em
  repositórios piloto sem dado sensível.
- Classificar cada repositório da organização em `classification/repositories.yaml`
  (fora da lista, o repositório roda sem IA como `nao-classificado`).
- Criar o bucket de evidências ([templates/evidence-store](templates/evidence-store/main.tf))
  com a retenção definida por compliance e preencher `EVIDENCE_BUCKET` e
  `EVIDENCE_ROLE_ARN` no workflow central; ligar o gate de deploy
  ([templates/target-repo/deploy.yml](templates/target-repo/deploy.yml)) nos pipelines.
- Quando houver um time: waiver como processo (solicitação e aprovação de AppSec) e
  integração com a gestão de mudança (ServiceNow/Jira).
- Migrar para organização (required workflow + ruleset com 1 aprovação e CODEOWNERS).
- Gateway corporativo de IA (pré-requisito da AI-GW-001, ADR-AI-001), registry de
  imagens aprovado (ADR-SUP-001) e lista de regiões aprovada (ADR-DATA-002).

## Adoção em um repositório-alvo

1. **Classifique o repositório** em [classification/repositories.yaml](classification/repositories.yaml)
   (`interno`, `confidencial` ou `restrito`), por PR neste repositório. Fora da lista, ele
   roda como `nao-classificado`, sem IA ([ADR-GOV-009](adrs/ADR-GOV-009-classificacao-de-repositorios.md)).
2. Inclua o repositório em [dashboard/repos.txt](dashboard/repos.txt) para entrar no painel.
3. Copie [templates/target-repo/CODEOWNERS](templates/target-repo/CODEOWNERS) para
   `.github/CODEOWNERS` do repo-alvo.
4. Remova qualquer workflow de IA local que leia prompts do próprio repositório (na PoC:
   `.github/workflows/ai-governance.yml` e `.github/scripts/orchestrator.py`).
5. Mantenha o ArchUnit no build: é a verificação de arquitetura sobre o bytecode.
6. No pipeline de deploy, adicione o job do gate de deploy e faça o deploy depender dele
   ([templates/target-repo/deploy.yml](templates/target-repo/deploy.yml)).

## Configuração da organização (uma vez)

1. Aplique [templates/org-ruleset.json](templates/org-ruleset.json) com o `repository_id`
   deste repositório e a tag da versão atual: required workflow, 1 aprovação de
   CODEOWNER, check `governance / governance` com o PR atualizado antes do merge
   (`strict`), sem bypass.
2. Secrets da organização, de preferência restritos aos repositórios selecionados:
   `OPENROUTER_API_KEY` (revisor generativo, [ADR-GOV-001](adrs/ADR-GOV-001-provedor-llm-openrouter.md)),
   `TYPESAFE_API_KEY` (Jev, [ADR-GOV-002](adrs/ADR-GOV-002-julgamento-tipado-jev.md)) e, se
   este repositório for privado, `GOVERNANCE_READ_TOKEN` (só leitura aqui).
3. Neste repositório: o secret `DASHBOARD_TOKEN` (leitura de Actions e de Code scanning
   alerts nos repositórios do painel) e, com o bucket de evidências criado
   ([templates/evidence-store](templates/evidence-store/main.tf)), `EVIDENCE_BUCKET` e
   `EVIDENCE_ROLE_ARN` no [workflow central](.github/workflows/governance-required.yml).
4. Ajuste `GOVERNANCE_REPOSITORY` nos workflows se o nome deste repositório mudar.
5. Confirme no primeiro PR que `github.workflow_sha` aponta para a revisão deste
   repositório: se não apontar, o checkout do motor falha e o PR é bloqueado
   (fail-closed), sem aprovar nada indevidamente.

## Modo conta pessoal (sem organização, provisório)

Sem organização não há required workflow. O repo-alvo chama o workflow central:

1. Copie [templates/target-repo/governance.yml](templates/target-repo/governance.yml) para
   `.github/workflows/governance.yml` e [templates/target-repo/deploy.yml](templates/target-repo/deploy.yml)
   para o pipeline de deploy, com a **mesma tag** no `uses:` e em `governance_ref` dos dois.
2. Crie no repo-alvo os secrets **só deste projeto** e repasse-os no `secrets:` do
   `governance.yml`: uma chave da OpenRouter (https://openrouter.ai/keys, com limite
   mensal) como `OPENROUTER_API_KEY` e uma da TypeSafe como `TYPESAFE_API_KEY`. Na PoC:
   `VIRTUALTHREADS_OR_API_KEY` e `VIRTUALTHREADS_JEV_API_KEY`. Se este repositório for
   privado, libere-o em *Settings → Actions → General → Access*.
3. Ruleset do repo-alvo no branch principal: exigir PR e o status check
   `governance / governance`, com **"Require branches to be up to date"** (sem isso, o
   commit de merge pode trazer código que o gate não avaliou). Rulesets em repositório
   privado exigem plano Pro.

Limite conhecido: o PR pode editar ou remover a chamada (ADR-GOV-000, alternativas
rejeitadas). O CODEOWNERS e o check obrigatório só reduzem esse risco. Migre para o
ruleset da organização antes de tratar o resultado como controle.

### O que acontece em um PR, passo a passo

Exemplo com a PoC `robertosrjr/virtualthreads`, classificada como `interno`, que chama
este repositório na tag `v1.10.0`.

```mermaid
flowchart LR
    A[PR na PoC] --> B[governance.yml<br/>da PoC]
    B -- "uses: ...@v1.10.0<br/>secrets: OPENROUTER_API_KEY, TYPESAFE_API_KEY" --> C[governance-required.yml<br/>deste repositório]
    C --> D[gitleaks + motor]
    D --> E{Veredito}
    E -- APPROVED --> F[check verde:<br/>ruleset libera o merge]
    E -- BLOCKED ou erro --> G[check vermelho:<br/>ruleset bloqueia o merge]
    F --> H[merge no main] --> I[deploy.yml:<br/>gate de deploy]
    I -- evidência válida --> J[deploy]
```

**1. Alguém abre um PR na PoC** (ou faz push no branch dele, ou reabre o PR).

**2. O workflow da PoC dispara.** O `.github/workflows/governance.yml` da PoC diz só
*quando* rodar e *qual versão* usar:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]   # abrir, novo push, reabrir
jobs:
  governance:
    uses: robertosrjr/governance-policies/.github/workflows/governance-required.yml@v1.10.0
    with:
      governance_ref: v1.10.0                  # a mesma tag do 'uses:'
    secrets:                                  # só as chaves do projeto, nunca 'inherit'
      OPENROUTER_API_KEY: ${{ secrets.VIRTUALTHREADS_OR_API_KEY }}
      TYPESAFE_API_KEY: ${{ secrets.VIRTUALTHREADS_JEV_API_KEY }}
```

**3. O workflow central roda** ([governance-required.yml](.github/workflows/governance-required.yml)),
em um runner do GitHub:

| Passo do workflow | O que faz |
|---|---|
| Checkout do repositório-alvo | Baixa o código do PR em `target/`. É tratado como **dado**, nunca como instrução. |
| Checkout do motor | Baixa **este** repositório na tag fixada em `governance/`: motor, políticas, classificação, prompts e modelo. |
| Instalar dependências | `pip install --require-hashes`: só instala pacotes com hash conferido. |
| gitleaks | Procura segredos em **cada commit** do PR, inclusive nos já apagados. |
| Avaliar políticas | `python -m governance review`: aplica a classe do repositório, as regras determinísticas (T0) e a IA (T1, se a classe permitir) e comenta o relatório no PR. |
| Publicar SARIF | Envia os achados para o Code Scanning (checks `enterprise-governance` e `gitleaks`). |
| Atestar o resultado | Assina o `result.json` (Sigstore). É a evidência do gate de deploy. |
| Reter a evidência | Com o bucket configurado, grava a evidência em armazenamento imutável; sem ele, só avisa. |
| Guardar evidência | Salva `out/` como artefato `governance-<sha>` por 90 dias. |
| Veredito | Só passa se o motor **e** o gitleaks terminarem com 0. Qualquer erro reprova (fail-closed). |

**4. O resultado vira o check `governance / governance`** (job da PoC / job central). O
ruleset `protecao-main` da PoC exige esse check, o PR atualizado e um PR para a `main`:

- ✅ verde: o botão de merge é liberado;
- ❌ vermelho: o merge fica bloqueado, e o comentário do motor no PR diz a política, o
  arquivo e a linha.

**5. No merge, o `deploy.yml` da PoC** chama o gate de deploy (próxima seção) e só então
implanta.

Na PoC ficam só os **secrets** `VIRTUALTHREADS_OR_API_KEY` e `VIRTUALTHREADS_JEV_API_KEY`,
o `governance.yml` e o `deploy.yml`. O `GEMINI_API_KEY` e a variável `GEMINI_MODEL`, da
época do pipeline próprio da PoC, podem ser apagados: o modelo fica em
[engine/bundle.yaml](engine/bundle.yaml), para o repositório revisado não poder escolher
um modelo mais fraco.

### Testar o bloqueio

Em um branch novo da PoC, coloque uma dependência de framework no domínio, por exemplo
`import org.springframework.stereotype.Component;` em uma classe de
`application/pedidos/src/main/java/.../domain/`, e abra um PR. O esperado é
`ARCH-HEX-001` (CRITICAL), o check `governance / governance` vermelho e o merge recusado.
Feche o PR sem merge. Para ver o mesmo resultado antes do push:

```bash
PYTHONPATH=engine python -m governance review --repo ../../java/virtualthreads --base origin/main --no-llm
```

## Gate de deploy

O deploy de um commit só prossegue se ele veio de um PR com avaliação aprovada e
assinada pelo workflow central ([ADR-GOV-005](adrs/ADR-GOV-005-gate-de-deploy-e-retencao-de-evidencia.md)).
O repositório-alvo chama o [governance-deploy-gate.yml](.github/workflows/governance-deploy-gate.yml)
antes do deploy ([templates/target-repo/deploy.yml](templates/target-repo/deploy.yml)), que:

1. acha o PR do commit implantado (o commit de merge não é o commit avaliado) e bloqueia
   commit sem PR;
2. baixa o `result.json` da avaliação do PR;
3. verifica a assinatura com `gh attestation verify --signer-workflow` (sem isso, um job
   qualquer do repo-alvo poderia atestar um resultado forjado);
4. confere o conteúdo com `python -m governance verify-evidence`: veredito aprovado, mesmo
   repositório, mesmo commit.

Para uma auditoria, a mesma verificação à mão, com o SHA do último commit do PR:

```bash
gh run download <run-id> -R org/app -n "governance-${SHA}" -D evidence
gh attestation verify evidence/result.json -R org/app \
  --predicate-type https://github.com/robertosrjr/governance-policies/governance-result/v1 \
  --signer-workflow robertosrjr/governance-policies/.github/workflows/governance-required.yml
PYTHONPATH=engine python -m governance verify-evidence --result evidence/result.json \
  --repository org/app --commit "$SHA"
```

## Onde ficam as evidências e o painel

| O quê | Onde | Retenção |
|---|---|---|
| Veredito de cada PR (`result.json`, `report.md`, SARIF) | Repo-alvo → Actions → execução `governance` do PR → Artifacts → `governance-<sha>` | 90 dias |
| Assinatura do veredito | Repo-alvo → Actions → Attestations | Enquanto o repositório existir |
| Achados na linha do código e falso positivo | Repo-alvo → Security → Code scanning | Enquanto o repositório existir |
| Comentário do relatório | No próprio PR | Enquanto o repositório existir |
| Painel de conformidade (`dashboard.html`, `.json`, `.md`) | Este repositório → Actions → `compliance-dashboard` → Artifacts; o resumo aparece na execução | 90 dias |
| Evidência de longo prazo | Bucket S3 com Object Lock (quando configurado) | Definida por compliance |

## Publicar uma nova versão

Processo do [ADR-GOV-007](adrs/ADR-GOV-007-release-e-versionamento.md):

1. Suba a versão do motor (`engine/governance/__init__.py` e `pyproject.toml`) igual à
   tag; suba `bundle_version` só se mudou modelo, prompt, orçamento ou políticas.
2. `pytest`, `validate`, `export --check` e `eval` verdes (o CI roda). Mudou o bundle:
   `eval --llm --repeat 5` aprovado, com os números na mensagem do commit.
3. Commit e push na `main`, e uma tag **nova**: `git tag v1.10.0 && git push origin v1.10.0`.
   Tag publicada não se move: defeito se corrige com uma versão nova.
4. **Smoke test:** na PoC, troque a tag no `governance.yml` e no `deploy.yml` (no `uses:` e
   em `governance_ref`) por PR. O próprio PR roda na versão nova; depois do merge, o gate
   de deploy tem de liberar.

> As tags **v1.4.0 a v1.7.0** estão defeituosas (worktrees de agentes versionadas como
> submódulo quebram o checkout do motor). Use a v1.7.1 ou posterior.

## Desenvolvimento

```bash
pip install --no-deps --require-hashes -r engine/requirements-dev.lock
python -m pytest
PYTHONPATH=engine python -m governance validate
PYTHONPATH=engine python -m governance export --check
PYTHONPATH=engine python -m governance eval
PYTHONPATH=engine python -m governance dashboard --repo robertosrjr/virtualthreads   # com GITHUB_TOKEN
```

Regras para editar este repositório: [CLAUDE.md](CLAUDE.md).
