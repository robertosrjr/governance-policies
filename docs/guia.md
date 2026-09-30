# Guia da plataforma de governança

Este guia explica o que o repositório `governance-policies` faz, quais regras ele aplica,
como usar no dia a dia, como ligar em um repositório novo e as boas práticas para quem
escreve código e para quem mantém as regras. Versão descrita: **v1.9.0** (motor 1.9.0,
bundle 1.5.0, `result.json` 1.3).

Documentos relacionados:

| Documento | Para quê |
|---|---|
| [README](../README.md) | Porta de entrada e índice de todas as decisões (ADRs) |
| [Manual de configuração](manual-configuracao.md) | Ligar a governança num repositório, do zero ao primeiro PR bloqueado e ao primeiro deploy |
| [Manual do ciclo de vida de uma regra](manual-ciclo-de-vida-de-uma-regra.md) | Criar ou mudar uma regra, do ADR ao eval e à release |
| [Fluxo da esteira](fluxo-da-esteira.md) | Diagramas de sequência das cinco jornadas |
| [ADR-GOV-000](../adrs/ADR-GOV-000-modelo-de-governanca.md) | A decisão de arquitetura por trás de tudo |

- [1. Visão geral](#1-visão-geral)
- [2. Como o repositório funciona](#2-como-o-repositório-funciona)
- [3. As regras](#3-as-regras)
- [4. Como usar (quem abre PR)](#4-como-usar-quem-abre-pr)
- [5. Como aplicar em um repositório novo](#5-como-aplicar-em-um-repositório-novo)
- [6. Como mudar as regras (quem mantém)](#6-como-mudar-as-regras-quem-mantém)
- [7. Boas práticas](#7-boas-práticas)
- [8. Problemas comuns](#8-problemas-comuns)

---

## 1. Visão geral

Todo Pull Request de um repositório-alvo (hoje, a PoC `robertosrjr/virtualthreads`) passa
por um check chamado `governance / governance`. Esse check roda o motor **deste**
repositório sobre o diff do PR e dá um veredito: `APPROVED` ou `BLOCKED`. O ruleset do
repositório-alvo só libera o merge com o check verde. No deploy, um **gate de deploy**
confere que o commit veio de um PR aprovado, com a evidência assinada. Toda segunda-feira,
um **painel de conformidade** mostra como as regras estão se comportando.

Os princípios que definem o comportamento:

| Princípio | O que significa na prática |
|---|---|
| **Fonte única** | As regras moram só em `policies/*.yaml`. O comentário no PR, o SARIF, as instruções do Claude Code e o pack do AWS Security Agent são gerados a partir delas. |
| **Determinístico primeiro** | O que dá para verificar com regex, caminho, comparação de contrato ou ArchUnit é verificado assim. A IA só **acrescenta** achados, não aprova nada e não remove achados da camada determinística. |
| **Fail-closed** | Qualquer erro (motor quebrou, provedor de IA fora do ar, chave ausente, tag inexistente) resulta em `BLOCKED`. Nenhum erro vira aprovação. |
| **Conteúdo do PR é dado, nunca instrução** | O motor, as políticas, os prompts, o modelo e a classificação vêm deste repositório. Nada do repositório revisado muda como ele é revisado. |
| **Decisão é evidência** | O `result.json` de cada PR é assinado (Sigstore) e é ele, não o comentário, que o gate de deploy e a auditoria verificam. |

---

## 2. Como o repositório funciona

### 2.1 Estrutura: o que tem em cada pasta

```
governance-policies/
├── policies/        AS REGRAS (fonte única)
├── adrs/            O PORQUÊ de cada regra e de cada decisão da plataforma
├── eval/cases/      EXEMPLOS que provam que cada regra funciona
├── classification/  A CLASSE de cada repositório-alvo (IA permitida, regras endurecidas)
├── waivers/         EXCEÇÕES aprovadas, com validade
├── dashboard/       Repositórios medidos pelo painel de conformidade
├── engine/          O MOTOR que avalia os PRs
├── .github/         Os WORKFLOWS (o que roda no GitHub)
├── templates/       MODELOS para copiar
├── exports/         GERADO: pacote para o AWS Security Agent
├── .claude/         Regras geradas para o Claude Code + skills e agente
├── tests/           Testes do motor
└── docs/            Documentação
```

Quem edita o quê, no dia a dia:

| Quero… | Mexo em |
|---|---|
| Criar ou mudar uma regra | `policies/`, `adrs/` e `eval/cases/` ([manual](manual-ciclo-de-vida-de-uma-regra.md)) |
| Classificar um repositório ou endurecer regras por classe | `classification/repositories.yaml` |
| Liberar uma exceção | `waivers/` |
| Incluir um repositório no painel | `dashboard/repos.txt` |
| Mudar o modelo de IA ou os prompts | `engine/bundle.yaml` e `engine/governance/prompts/` |
| Mudar o comportamento do motor | `engine/governance/*.py` e `tests/` |
| Mudar o que roda no PR, no deploy ou no painel | `.github/workflows/` |
| Nunca editar à mão | `exports/`, `.claude/rules/governance-policies.md` e `engine/*.lock` (são gerados) |

#### `policies/`: as regras

Um arquivo YAML por regra (`ARCH-HEX-001.yaml`, `FIN-MONEY-001.yaml`…). É a **fonte
única**. Cada arquivo diz o que a regra proíbe, onde vale (`scope`), a severidade, o modo
(`enforce`, `warn` ou `audit`), como verificar, como corrigir e qual ADR a justifica
(`adr:`). O formato obrigatório está em `policies/schema/policy.schema.json`, e o
`validate` recusa arquivo fora dele. Cada campo está explicado no
[manual do ciclo de vida](manual-ciclo-de-vida-de-uma-regra.md#etapa-2-a-política-o-quê).

#### `adrs/`: o porquê

Um Markdown por decisão (`ADR-<ÁREA>-<NNN>-tema.md`): contexto, decisão, como é verificada,
alternativas descartadas e consequências. Toda política aponta para um ADR, e o `validate`
falha se ele não existir. São 27 ADRs em dois grupos: os da **plataforma** (`ADR-GOV-*`:
modelo, provedor de IA, Jev, operação em instituição financeira, release, painel,
classificação...) e os das **regras para o código** (arquitetura, dinheiro, LGPD,
segurança, dados, contratos, cadeia de suprimentos, IA, qualidade). O índice, com uma
linha por ADR, está no [README](../README.md#decisões-de-arquitetura-adrs).

#### `eval/cases/`: os exemplos que provam as regras

Um YAML por caso: arquivos de código e o resultado esperado para cada política (`true` =
deve disparar; `false` = não pode disparar). `base_files` descreve a versão anterior,
para as regras que comparam versões. Casos com `requires_llm: true` só rodam no eval com
IA. Política em `enforce` precisa de pelo menos um caso positivo e um negativo.

#### `classification/`: a classe de cada repositório

`repositories.yaml` define as classes (`interno`, `confidencial`, `restrito`,
`nao-classificado`) e a classe de cada repositório-alvo. A classe decide se o código pode
ir para um provedor de IA e quais regras ficam mais rígidas
([ADR-GOV-009](../adrs/ADR-GOV-009-classificacao-de-repositorios.md)). Detalhes em
[2.4](#24-a-classe-do-repositório).

#### `waivers/`: as exceções

Um YAML por exceção aprovada (`WVR-AAAA-NNN.yaml`): qual política, qual repositório,
quais caminhos, por quê, quem pediu, quem aprovou e até quando vale (máximo de 90 dias).
Hoje está vazia, só com `README.md` (as regras de uma exceção) e
`schema/waiver.schema.json` (o formato obrigatório).

#### `dashboard/`: o painel de conformidade

`repos.txt` lista os repositórios que o painel semanal mede
([ADR-GOV-006](../adrs/ADR-GOV-006-painel-de-conformidade.md)).

#### `engine/`: o motor

| Arquivo ou pasta | Para que serve |
|---|---|
| `bundle.yaml` | Provedor, modelo, temperatura, limites e tentativas do revisor generativo e do Jev. Mudar aqui é nova versão do revisor e exige eval com IA. |
| `requirements.in` / `requirements-dev.in` | Dependências diretas (o que editar). |
| `requirements.lock` / `requirements-dev.lock` | GERADOS: versões exatas com hash. O CI só instala o que bate com o hash. |
| `governance/prompts/` | Instruções do revisor generativo: `base.md` (regras comuns e proteção contra texto malicioso no código), `lgpd.md`, `quality.md`, `security.md`. |
| `governance/result.schema.json` | O formato do `result.json` (a evidência). Mudou o formato, sobe o `schema_version` e o gate de deploy. |

Os módulos Python em `engine/governance/`, na ordem em que um PR passa por eles:

| Módulo | O que faz |
|---|---|
| `cli.py`, `__main__.py` | Os comandos `review`, `validate`, `export`, `eval`, `verify-evidence` e `dashboard`. |
| `diff.py` | Descobre os arquivos alterados, o tipo de mudança (adicionado, modificado, renomeado, removido), as linhas adicionadas e o conteúdo na base. |
| `policy.py` | Carrega e valida as políticas; escolhe as que valem para os arquivos alterados. |
| `classification.py` | Lê a classe do repositório e endurece as políticas que a classe manda. |
| `deterministic.py` | Camada T0: regex, caminho, arquivo acompanhante e contrato. É a que bloqueia. |
| `validators.py` | Dígito verificador de CPF e CNPJ e Luhn de cartão, para as regras com `validator`. |
| `contracts.py` | Quebras de compatibilidade entre a base e o PR em contratos OpenAPI e Avro. |
| `redact.py` | Tira segredos, CPF, CNPJ, cartão e e-mail do código antes de enviá-lo à IA. |
| `llm.py` | Camada T1 generativa: chama o revisor, filtra a resposta e traduz falhas do provedor em mensagens claras. |
| `jev.py` | Camada T1 por julgamento tipado: o Jev responde a probabilidade de "sim" para cada linha marcada. |
| `waivers.py` | Carrega as exceções e marca os achados que elas cobrem. |
| `verdict.py` | Decide `APPROVED` ou `BLOCKED` e monta o `result.json`. |
| `report.py` | Escreve o comentário do PR e o SARIF. |
| `github.py` | Publica (ou atualiza) o comentário no PR. |
| `review.py` | Junta as camadas: é o núcleo usado pelo `review`, pelo `eval` e pelos testes. |
| `evaluation.py` | O comando `eval`: roda os casos e calcula acerto por política. |
| `export.py` | Gera `exports/` e `.claude/rules/governance-policies.md` a partir das políticas. |
| `evidence.py` | O comando `verify-evidence`, usado pelo gate de deploy. |
| `dashboard.py`, `dashboard_github.py` | O comando `dashboard`: métricas e coleta no GitHub. |
| `model.py` | Os tipos compartilhados (política, arquivo alterado, achado, erro). |

#### `.github/`: o que roda no GitHub

| Arquivo | Para que serve |
|---|---|
| `workflows/governance-required.yml` | Avalia os PRs **dos outros repositórios** (chamado por eles). |
| `workflows/governance-deploy-gate.yml` | Gate de deploy: chamado pelo pipeline de deploy dos outros repositórios. |
| `workflows/compliance-dashboard.yml` | Painel de conformidade, toda segunda-feira. |
| `workflows/ci.yml` | O CI **deste** repositório: testes, validação, exports e eval a cada PR daqui. |
| `CODEOWNERS` | Quem precisa aprovar mudanças em regras, classificação, motor, prompts e exceções. |

#### `templates/`: modelos para copiar

| Arquivo | Para quê |
|---|---|
| `policy-template.yaml` | Ponto de partida de uma regra nova. |
| `adr-template.md` | Ponto de partida de um ADR. |
| `waiver-example.yaml` | Exemplo comentado de exceção. |
| `target-repo/governance.yml` | Vai para `.github/workflows/` do repositório-alvo (modo conta pessoal). |
| `target-repo/deploy.yml` | Exemplo de pipeline de deploy com o gate de deploy. |
| `target-repo/CODEOWNERS` | Vai para `.github/` do repositório-alvo. |
| `org-ruleset.json` | Ruleset da organização que obriga todos os repositórios a rodar a governança. |
| `evidence-store/main.tf` | Terraform do bucket de evidências (S3 com Object Lock, KMS, sa-east-1). |

#### `exports/`: gerado para o AWS Security Agent

`aws-security-agent/governance-pack.json`: as políticas no formato que o AWS Security
Agent lê, incluindo as de auditoria (OWASP), que não rodam no PR. **Gerado** por
`python -m governance export`; não edite.

#### `.claude/`: Claude Code e AWS Security Agent

| Arquivo ou pasta | Para que serve |
|---|---|
| `rules/governance-policies.md` | **Gerado** a partir de `policies/`. O Claude Code lê este arquivo e segue as regras ao escrever código. É também a lista completa e sempre atualizada das regras. |
| `rules/filtering.md` | Pastas que o AWS Security Agent deve ignorar. O motor não usa. |
| `agents/security_coordinator_agent.json` | Agente coordenador do AWS Security Agent. |
| `skills/threat-modeling/`, `skills/pentest-validator/` | Modelagem de ameaças (STRIDE + OWASP Top 10:2025) e validação de vulnerabilidades em pentest. |
| `skills/global-ai-principles/` | Consultora de princípios éticos de IA; a parte verificável virou as políticas AI-HUMAN, AI-FAIR e AI-INV ([ADR-AI-002](../adrs/ADR-AI-002-principios-eticos-como-guardrails.md)). |
| `skills/typesafe-ai/` | Orientação para usar o Jev e os primitivos da TypeSafe. |

O motor que avalia os PRs **não lê** nada de `.claude/` (nem daqui, nem do repositório
avaliado). Skills orientam; só `policies/` decide
([ADR-GOV-008](../adrs/ADR-GOV-008-skills-como-orientacao.md)).

#### `tests/`: testes do motor

| Arquivo | O que testa |
|---|---|
| `conftest.py` | Preparação comum: carrega políticas e cria repositórios git descartáveis. |
| `test_policy_and_diff.py` | Leitura de políticas, escopo por caminho e leitura do diff. |
| `test_evaluation_layers.py` | As garantias do modelo: T0 bloqueia, IA só acrescenta, falhas bloqueiam com a mensagem certa, conteúdo isolado e sem segredos, waivers. |
| `test_jev.py`, `test_openrouter.py` | O Jev e o provedor OpenRouter, com provedores falsos. |
| `test_financial_rules.py` | Validadores, remoção de dado pessoal e cada regra das políticas financeiras. |
| `test_architecture_rules.py` | Tipo de mudança no diff, comparação de contratos, arquivo acompanhante. |
| `test_classification.py` | Classes, endurecimento, IA desligada por classe. |
| `test_evidence.py`, `test_dashboard.py` | Gate de deploy e painel de conformidade. |
| `test_waivers_cli_and_bundle.py` | Exceções, comandos de ponta a ponta, eval, exports, gitleaks e submódulos. |

#### `docs/`: documentação

| Arquivo | Para quem |
|---|---|
| `guia.md` | Este guia: como tudo funciona. |
| `manual-configuracao.md` | Passo a passo para ligar a governança num repositório e testar. |
| `manual-ciclo-de-vida-de-uma-regra.md` | Passo a passo para criar ou mudar uma regra. |
| `fluxo-da-esteira.md` | Diagramas de sequência das jornadas. |
| `artigo-*.md` | Artigos sobre a experiência (versões para público geral e para arquitetos). |
| `Governança SecLLMOps Enterprise.docx` | O roteiro original que deu origem ao projeto (histórico). |

#### Arquivos na raiz

| Arquivo | Para que serve |
|---|---|
| `README.md` | Porta de entrada: resumo, índice de ADRs, configuração. |
| `CLAUDE.md` | Regras para quem edita este repositório, inclusive assistentes de IA. |
| `pyproject.toml` | Nome e versão do motor; configuração do pytest. |
| `.gitattributes` | Força fim de linha LF (evita que o Windows quebre o `export --check`). |
| `.gitignore` | O que o git ignora (caches, saídas locais, resultados de eval, worktrees de agentes). |

### 2.2 O caminho de um PR

1. O PR é aberto no repositório-alvo, recebe um push ou é reaberto.
2. O `.github/workflows/governance.yml` do repositório-alvo chama o workflow central
   [governance-required.yml](../.github/workflows/governance-required.yml) numa **tag**
   deste repositório (ex.: `v1.9.0`) e repassa só as chaves do projeto, OpenRouter e
   TypeSafe (nunca `secrets: inherit`, que entrega todos os segredos).
3. O workflow central:
   1. baixa o código do PR em `target/`, como dado;
   2. baixa este repositório na tag em `governance/`: motor, políticas, classificação,
      prompts e modelo;
   3. instala as dependências com hash conferido;
   4. roda o **gitleaks** em cada commit do PR;
   5. roda o **motor** (`python -m governance review`) no diff;
   6. publica o SARIF no Code Scanning (checks `enterprise-governance` e `gitleaks`);
   7. assina o `result.json` (Sigstore);
   8. grava a evidência no bucket imutável, se estiver configurado;
   9. guarda `out/` como artefato `governance-<sha>` por 90 dias;
   10. dá o veredito: só passa se o motor **e** o gitleaks terminarem com 0.
4. No merge, o pipeline de deploy chama o
   [gate de deploy](../.github/workflows/governance-deploy-gate.yml) (seção
   [5.3](#53-gate-de-deploy)).

Os diagramas de sequência desse caminho estão no [fluxo da esteira](fluxo-da-esteira.md).

### 2.3 O que o motor faz com o diff

```
arquivos alterados (+ tipo de mudança e conteúdo na base)
   │
   ├─ 1. Classe do repositório: IA permitida? quais políticas endurecem?
   ├─ 2. Seleção: só entram as políticas cujo `scope` casa com algum arquivo alterado
   ├─ 3. T0 determinístico: regex nas linhas ADICIONADAS (com validador de CPF/CNPJ/cartão),
   │            caminho alterado, arquivo acompanhante exigido, quebra de contrato
   ├─ 4. T1 IA (se a classe permitir): conteúdo sem segredos nem dado pessoal;
   │            revisor generativo aponta achados; Jev julga as linhas marcadas;
   │            achados repetidos de T0 são descartados, nada de T0 é removido
   ├─ 5. Waivers válidos marcam os achados que cobrem
   └─ 6. Veredito + result.json + SARIF + comentário no PR
```

O motor olha só as **linhas adicionadas** no PR. Código antigo que já viola uma regra
não bloqueia o PR de quem não mexeu nele. As exceções são as regras que olham o arquivo
como um todo: migração editada, contrato comparado com a base, arquivo acompanhante.

### 2.4 A classe do repositório

| Classe | IA | Endurece | Para |
|---|---|---|---|
| `interno` | Sim | — | Sem dado pessoal nem de cartão |
| `confidencial` | Não, até o contrato do provedor | — | Trata dado pessoal (LGPD) |
| `restrito` | Não | SEC-PAN-001, LGPD-DATA-001, SEC-CRYPTO-001 → `enforce` | Ambiente de cartão (PCI) ou dado sensível |
| `nao-classificado` | Não | — | Padrão para repositório fora da lista |

- **IA desligada pela classe não é erro:** as políticas semânticas não rodam, o PR não é
  bloqueado por isso, e o comentário e a evidência registram a classe.
- **A classe só endurece** uma política, nunca afrouxa.
- A classe aparece no rodapé do comentário do PR (`· classe interno`).

### 2.5 Quando um achado bloqueia

Um achado bloqueia o merge quando **tudo** isto é verdade:

- a política está em modo `enforce` (pelo próprio arquivo ou pela classe do repositório);
- a severidade é `CRITICAL`;
- o achado veio da camada determinística, **ou** a política tem `llm.blocking: true`;
- não existe waiver válido para ele.

| Modo | Efeito |
|---|---|
| `enforce` | Pode bloquear (se também for CRITICAL). |
| `warn` | Aparece no comentário e no SARIF como alerta. Nunca bloqueia. |
| `audit` | Não roda no PR. É exportada para revisão humana e para o AWS Security Agent. |

### 2.6 Versões

- O repositório-alvo usa uma **tag** deste repositório. Mudar a `main` daqui não afeta
  ninguém até existir uma tag nova e o repositório-alvo apontar para ela.
- A versão do motor acompanha a tag; o `bundle_version` sobe quando muda modelo, prompt,
  orçamento ou políticas; cada política tem `version` própria.
- O `result.json` registra tudo isso, a classe do repositório e o digest das políticas:
  dá para saber exatamente com quais regras um commit foi aprovado.
- **Tag publicada nunca se move.** As tags v1.4.0 a v1.7.0 estão defeituosas (use a
  v1.7.1 ou posterior). O processo completo está no
  [ADR-GOV-007](../adrs/ADR-GOV-007-release-e-versionamento.md).

---

## 3. As regras

São 34 políticas. A lista completa e sempre atualizada, com escopo, verificação e
correção de cada uma, é gerada em
[.claude/rules/governance-policies.md](../.claude/rules/governance-policies.md). O resumo:

### 3.1 As que bloqueiam (`enforce`, CRITICAL)

| Id | O que proíbe | Como verifica |
|---|---|---|
| ARCH-HEX-001 | Domínio dependendo de Spring ou JPA | regex + ArchUnit no build |
| ARCH-HEX-002 | `domain` ou `application` referenciando `infrastructure` | regex + ArchUnit no build |
| LGPD-LOG-001 | Dado pessoal em log, trace, métrica ou exceção sem mascaramento | regex (bloqueia) + Jev (alerta) |
| SEC-SECRET-001 | Chave, token, senha ou chave privada no código ou em configuração | regex + gitleaks |
| SEC-UNICODE-001 | Caracteres invisíveis ou bidirecionais (Trojan Source) | regex |
| SEC-OBFUSC-001 | Escape `\uXXXX` fora de literal em Java | regex |

Na classe `restrito`, também bloqueiam SEC-PAN-001, LGPD-DATA-001 e SEC-CRYPTO-001.

### 3.2 As que alertam (`warn`)

| Tema | Políticas |
|---|---|
| Dinheiro e resiliência | FIN-MONEY-001 (`double` para dinheiro, `divide` sem `RoundingMode`), RES-IDEMP-001 (retry em escrita financeira sem idempotência, Jev) |
| Segurança e dados | SEC-CRYPTO-001 (criptografia fraca, TLS antigo), SEC-PAN-001 (número de cartão), LGPD-DATA-001 (CPF real), SEC-CONFIG-001 (configuração Spring insegura) |
| Banco de dados e nuvem | DATA-MIG-001 (migração editada), DATA-MIG-002 (DDL destrutivo), DATA-RES-001 (região fora do Brasil) |
| Arquitetura e contratos | ARCH-TIME-001 (relógio da máquina no domínio), API-CONTRACT-001 (quebra de OpenAPI), EVT-SCHEMA-001 (quebra de Avro), GOV-ADR-001 (decisão estrutural sem ADR) |
| Cadeia de suprimentos | SUP-DEP-001 (SNAPSHOT, versão flutuante), SUP-IMG-001 (imagem sem digest, root, `curl \| sh`) |
| IA nas aplicações | AI-GW-001 (LLM fora do gateway), AI-MODEL-001 (modelo não fixado), AI-HUMAN-001 (IA decide sozinha sobre cliente, Jev), AI-FAIR-001 (dado sensível em modelo, Jev), AI-INV-001 (uso de IA sem inventário) |
| Revisão e qualidade | LLM-INJ-001 (texto dirigido a IA), GOV-SELF-001 (mudança em CI ou em configuração de agentes), QUAL-CODE-001 (qualidade, revisor generativo) |

Toda política nova entra em `warn` e só sobe para `enforce` com números: casos no eval,
14 dias em `warn`, ao menos 10 achados e falso positivo abaixo de 5%
([ADR-GOV-003](../adrs/ADR-GOV-003-operacao-em-instituicao-financeira.md)). O painel de
conformidade mostra quando cada uma está pronta.

### 3.3 Só de auditoria (não rodam no PR)

OWASP-A01 (controle de acesso), A02 (configuração segura), A03 (cadeia de suprimentos), A04
(criptografia) e A10 (tratamento de exceções). Tratam de desenho e de execução, não do
diff: ficam para revisão humana e para o AWS Security Agent. A parte verificável no
código já virou política própria (SEC-CONFIG-001, SEC-CRYPTO-001, SUP-DEP-001).

### 3.4 Como corrigir

Cada achado no comentário do PR traz a correção. As mais comuns:

| Id | Correção |
|---|---|
| ARCH-HEX-001 | Tire anotações Spring/JPA do domínio. Mapeamento ORM vai para `infrastructure/persistence` com mapper. |
| ARCH-HEX-002 | Crie uma porta em `application/port/out` e implemente o adaptador em `infrastructure`. |
| LGPD-LOG-001 | `PIISanitizer.mask(valor)` antes de logar, ou logue só um id técnico. |
| SEC-SECRET-001 | Remova o valor, **revogue a credencial** (ela já está no histórico) e leia de um cofre. |
| FIN-MONEY-001 | `BigDecimal` a partir de `String` ou `valueOf`, e `RoundingMode` explícito. |
| ARCH-TIME-001 | Injete um `Clock` e use fuso explícito. |
| GOV-SELF-001 | Nada a corrigir: é um aviso para o revisor humano olhar a mudança. |

As demais estão no arquivo gerado e no ADR de cada política.

---

## 4. Como usar (quem abre PR)

### 4.1 No dia a dia

1. Abra o PR normalmente.
2. Espere o check `governance / governance` (alguns minutos).
3. Leia o **comentário do motor** no PR. Ele lista cada achado com política, severidade,
   arquivo, linha e se bloqueia. O rodapé mostra a versão do motor, os modelos de IA e a
   classe do repositório.
4. Se bloqueou, corrija e faça push. O check roda de novo sozinho.
5. Alertas (`warn`) não impedem o merge, mas leia: costumam apontar problemas reais.

Os achados também aparecem em **Security → Code scanning** e em **Files changed**, na
linha do problema.

### 4.2 Testar antes do push

Com os dois repositórios lado a lado no disco, a partir deste repositório:

```bash
PYTHONPATH=engine python -m governance review --repo ../../java/virtualthreads --base origin/main --no-llm
```

- `--no-llm` roda só a camada determinística, que é a que bloqueia. Não precisa de chave.
- Sem `--no-llm`, é preciso `OPENROUTER_API_KEY` e `TYPESAFE_API_KEY` no ambiente (se a
  classe do repositório permitir IA).
- A saída termina em `Veredito: APPROVED` ou `Veredito: BLOCKED`. Os arquivos ficam em
  `governance-out/`.

### 4.3 Quando a regra está errada para o seu caso

Não contorne a regra (renomear pacote, quebrar a linha para a regex não pegar). Os
caminhos legítimos:

- **Falso positivo:** em **Security → Code scanning**, dispense o alerta com o motivo
  **"False positive"**. Isso não desbloqueia o PR, mas entra na medição da regra no
  painel. Se a regra bloqueou, abra também uma issue ou PR neste repositório com o
  trecho: ele vira caso de eval e a regra é corrigida.
- **Exceção justificada:** peça um waiver (seção [6.3](#63-pedir-uma-exceção-waiver)).

Não existe bypass por comentário no PR.

---

## 5. Como aplicar em um repositório novo

O passo a passo completo, com comandos, configuração do ruleset e os erros que
encontramos, está no [manual de configuração](manual-configuracao.md). O resumo:

### 5.1 Em qualquer modo

1. **Classifique o repositório** em `classification/repositories.yaml` (por PR neste
   repositório). Fora da lista, ele roda sem IA como `nao-classificado`.
2. **Inclua-o no painel** em `dashboard/repos.txt`.
3. **CODEOWNERS:** copie [templates/target-repo/CODEOWNERS](../templates/target-repo/CODEOWNERS)
   para `.github/CODEOWNERS`.
4. **Remova** qualquer workflow de IA que leia prompts ou scripts do próprio repositório.
5. **ArchUnit:** mantenha os testes `ArchitectureTest#domain_should_not_depend_on_frameworks`
   e `#application_should_not_depend_on_infrastructure` no build.
6. **Deploy:** faça o deploy depender do gate de deploy
   ([templates/target-repo/deploy.yml](../templates/target-repo/deploy.yml)).

### 5.2 Modo conta pessoal (atual, provisório)

1. **Workflow:** copie [templates/target-repo/governance.yml](../templates/target-repo/governance.yml)
   para `.github/workflows/governance.yml`. A tag do `uses:` e o `governance_ref` têm
   que ser iguais, e iguais às do `deploy.yml`.
2. **Segredos do projeto** (*Settings → Secrets and variables → Actions*), repassados no
   `secrets:` do `governance.yml`: uma chave da OpenRouter como `OPENROUTER_API_KEY` e
   uma da TypeSafe como `TYPESAFE_API_KEY` (na PoC: `VIRTUALTHREADS_OR_API_KEY` e
   `VIRTUALTHREADS_JEV_API_KEY`). Sem a da TypeSafe, todo PR com Java é bloqueado por
   "revisor de IA não configurado" numa classe com IA.
3. **Ruleset** do branch principal (*Settings → Rules → Rulesets*):
   - Bypass list vazia;
   - Restrict deletions e Block force pushes;
   - Require a pull request before merging, com 0 aprovações (com um único dono, você não
     conseguiria aprovar os próprios PRs);
   - Require status checks: `governance / governance`, com **"Require branches to be up
     to date"** marcado (sem isso, o commit de merge pode trazer código que o gate não
     avaliou).
4. **Teste o bloqueio:** um PR com `import org.springframework.stereotype.Component;` em
   uma classe de `domain/` deve ficar vermelho com ARCH-HEX-001 e ter o merge recusado.

**Limite deste modo:** quem abre o PR pode editar ou apagar o `governance.yml`. O check
obrigatório e o CODEOWNERS só reduzem esse risco. Não trate o resultado como controle
formal até migrar para a organização.

### 5.3 Gate de deploy

O check protege o merge. O gate de deploy garante que só código aprovado vai para
produção: o `deploy.yml` do repositório-alvo chama o
[governance-deploy-gate.yml](../.github/workflows/governance-deploy-gate.yml), que:

1. acha o PR que gerou o commit implantado e bloqueia commit sem PR (push direto);
2. baixa o `result.json` da avaliação do PR;
3. verifica a assinatura, exigindo que quem assinou seja o workflow central;
4. confere o conteúdo: aprovado, mesmo repositório, mesmo commit.

Sem evidência válida, o job de deploy nem roda
([ADR-GOV-005](../adrs/ADR-GOV-005-gate-de-deploy-e-retencao-de-evidencia.md)).

### 5.4 Modo organização (o destino)

1. Crie a organização no GitHub e transfira os repositórios.
2. Aplique [templates/org-ruleset.json](../templates/org-ruleset.json) com o
   `repository_id` deste repositório e a tag atual: required workflow para **todos** os
   repositórios, 1 aprovação de CODEOWNER, check com branch atualizado, sem bypass.
3. Segredos da organização: `OPENROUTER_API_KEY` e `TYPESAFE_API_KEY` (restritos aos
   repositórios selecionados) e, se este repositório for privado, `GOVERNANCE_READ_TOKEN`.
4. Apague o `governance.yml` dos repositórios-alvo (o ruleset substitui).
5. Troque os usuários do CODEOWNERS por times.

---

## 6. Como mudar as regras (quem mantém)

Toda mudança neste repositório entra por PR. O [ci.yml](../.github/workflows/ci.yml) roda
testes, `validate`, `export --check` e `eval`, e bloqueia se algo regredir.

### 6.1 Criar ou alterar uma regra

O passo a passo completo, campo a campo e até o eval, está no
[manual do ciclo de vida de uma regra](manual-ciclo-de-vida-de-uma-regra.md). Em uma
frase: ADR em `adrs/`, política em `policies/` (a partir dos templates), casos positivo e
negativo em `eval/cases/`, `export`, e os comandos:

```bash
python -m pytest
PYTHONPATH=engine python -m governance validate
PYTHONPATH=engine python -m governance export
PYTHONPATH=engine python -m governance eval
```

Ao alterar uma regra existente: suba o `version` da política, e todo falso positivo ou
falso negativo encontrado vira caso de eval **antes** da correção.

### 6.2 Classificar um repositório ou endurecer regras

Edite `classification/repositories.yaml`: `repositories` define a classe de cada
repositório; `raise_mode` numa classe sobe o modo de uma política só naquela classe. O
`validate` recusa classe que afrouxa regra e `enforce` sem casos de eval. Quando o
contrato do provedor de IA sair, é aqui que se liga a IA para `confidencial`.

### 6.3 Pedir uma exceção (waiver)

1. Copie [templates/waiver-example.yaml](../templates/waiver-example.yaml) para
   `waivers/WVR-AAAA-NNN.yaml`.
2. Preencha: política, repositório, `paths` o mais estreitos possível, justificativa,
   quem pediu, quem aprovou e a validade.
3. Abra um PR neste repositório. Regras que o motor confere:
   - `approved_by` diferente de `requested_by`;
   - validade de no máximo **90 dias**;
   - `commit` (opcional) restringe a exceção a um commit.
4. Depois do merge, publique uma tag nova e atualize o repositório-alvo.

Waiver vencido é ignorado e o achado volta a bloquear. O CI deste repositório falha
enquanto houver waiver inválido, para forçar a limpeza. O painel mostra os que vencem em
até 30 dias.

### 6.4 Mudar o modelo, os prompts ou o `bundle.yaml`

É uma nova versão do revisor:

1. Suba `bundle_version` em [engine/bundle.yaml](../engine/bundle.yaml).
2. Rode o eval com IA (localmente com `OPENROUTER_API_KEY` e `TYPESAFE_API_KEY`, ou pelo
   `ci.yml` em *Actions → ci → Run workflow* com `llm_repeat` > 0):
   ```bash
   PYTHONPATH=engine python -m governance eval --llm --repeat 5
   ```
3. Só faça merge sem regressão de precisão e recall, com os números na mensagem do commit.

Para testar um modelo candidato sem alterar o bundle: `eval --llm --model <modelo>`.

### 6.5 Deixar a IA bloquear

Uma política só pode ter `llm.blocking: true` com `llm.eval_evidence` apontando para um
resultado de eval que justifique isso. O `validate` recusa sem a evidência. Hoje nenhuma
política usa a IA para bloquear.

### 6.6 Publicar uma nova versão

Processo do [ADR-GOV-007](../adrs/ADR-GOV-007-release-e-versionamento.md):

1. Suba a versão do motor (`engine/governance/__init__.py` e `pyproject.toml`) igual à
   tag nova.
2. Merge na `main` com o CI verde.
3. Tag nova, sem mover as antigas:
   ```bash
   git tag v1.10.0
   git push origin v1.10.0
   ```
4. **Smoke test:** no repositório piloto, um PR trocando a tag no `governance.yml` e no
   `deploy.yml` (nos dois lugares de cada um). O próprio PR roda na versão nova; depois
   do merge, o gate de deploy tem de liberar.

Versionamento: **patch** para correção, **minor** para regra nova em `warn`, classe ou
funcionalidade da plataforma, **major** para mudança que quebra quem usa (formato do
`result.json` sem compatibilidade, entrada obrigatória nova nos workflows).

---

## 7. Boas práticas

### 7.1 Para quem escreve código

- **Rode o review local com `--no-llm` antes do push.** É rápido e mostra o mesmo bloqueio
  que o CI.
- **Mantenha o domínio puro.** Spring, JPA e `infrastructure` ficam fora de `domain/` e
  `application/`; relógio entra como `Clock`.
- **Dinheiro é `BigDecimal`**, com `RoundingMode` explícito.
- **Nunca logue objeto inteiro, request ou response.** Logue ids técnicos, ou passe o
  valor por `PIISanitizer.mask`.
- **Massa de teste sem dado real:** CPF com dígito inválido, cartões de teste das
  bandeiras.
- **Segredo commitado é segredo vazado**, mesmo que você apague no commit seguinte.
  Revogue a credencial.
- **Não tente enganar a regex** (quebrar linha, escapes Unicode, concatenação). Há regras
  para ofuscação, e o ArchUnit olha o bytecode.
- **Marque falso positivo no Code Scanning.** É o que faz a regra melhorar.
- **PRs pequenos.** O revisor de IA tem orçamento de contexto; diffs menores dão revisões
  melhores.

### 7.2 Para quem mantém as regras

- **Determinístico primeiro.** Se dá para ser regex, caminho, contrato ou ArchUnit, não
  use IA.
- **Toda regra tem motivo e exemplo.** Sem ADR e sem casos de eval, a regra não entra.
- **Comece em `warn`, promova com números.** Uma regra que bloqueia errado ensina o time
  a contorná-la.
- **Falso positivo vira caso de eval** antes da correção.
- **Waiver estreito e curto.**
- **Tag imutável** e smoke test antes de anunciar.
- **Não edite arquivos gerados.** Edite a fonte e rode `export`.
- **Mudança de modelo ou prompt é release**, com eval antes.

### 7.3 Para quem opera

- **Classifique antes de ligar.** Repositório sem classe roda sem IA.
- **Um repositório-alvo por vez.** Ligue em um, observe alguns PRs e só então expanda.
- **Olhe o painel toda semana:** bloqueios por erro da esteira (provedor fora do ar),
  falso positivo por regra, waivers vencendo e regras prontas para `enforce`.
- **Acompanhe `GOV-SELF-001`.** Mudanças em `.github/` do repositório-alvo podem desligar
  a governança no modo conta pessoal.
- **Tokens vencem.** O `DASHBOARD_TOKEN` e as chaves de IA têm validade; quando vencem,
  o painel falha ou os PRs bloqueiam com a causa explicada.
- **Migre para a organização** antes de usar o resultado como controle formal.
- **LGPD Art. 33 e CMN 4.893:** o código sai para o provedor de IA. Até o contrato, use a
  classificação para manter repositórios com dado real sem IA.

---

## 8. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| A execução aparece com o nome do arquivo (`.github/workflows/governance.yml`) e falha na hora | A tag do `uses:` não existe neste repositório, ou o repositório é privado sem acesso liberado | `git ls-remote --tags origin` aqui; publique a tag. Se for privado, *Settings → Actions → General → Access*. |
| Falha no passo "Checkout do motor" com `No url found for submodule path '.claude/worktrees/...'` | Tag defeituosa (v1.4.0 a v1.7.0) | Use a v1.7.1 ou posterior. O `validate` agora impede que isso volte. |
| Comentário "⚠️ Revisor de IA indisponível" | O provedor respondeu 503, 429 ou não respondeu. O PR fica bloqueado (fail-closed), mas não é problema no código | Espere alguns minutos e *Re-run all jobs*. |
| "Revisor de IA não configurado (sem TYPESAFE_API_KEY)" | O segredo da TypeSafe não existe ou não é repassado no `governance.yml` | Crie o segredo e confira a linha `TYPESAFE_API_KEY:` no `secrets:`. |
| Aviso "Classe nao-classificado: revisão por IA desligada" | O repositório não está em `classification/repositories.yaml` | Classifique-o por PR neste repositório. Enquanto isso, só as regras determinísticas rodam. |
| Comentário "❗ Erros de execução" | Chave recusada, arquivo grande demais para o revisor ou gitleaks com segredo | Cada erro vem com **O que fazer**. |
| Comentário "❗ Erro de configuração" | O motor nem conseguiu avaliar (ex.: base do diff inexistente) | Rode de novo. Se repetir, avise o time de plataforma com o link da execução. |
| Gate de deploy: "O commit ... não veio de um PR" | Push direto ou deploy de branch sem PR | Todo código, inclusive hotfix, vai por PR. |
| Gate de deploy: "Evidência ... indisponível" | O artefato do PR expirou (90 dias) | Reavalie o PR, ou recupere a evidência do bucket quando a retenção estiver ligada. |
| Gate de deploy falha no `gh attestation verify` | O `result.json` não foi assinado pelo workflow central (PR de fork, ou workflow diferente) | Faça o PR a partir de um branch do próprio repositório. |
| Painel de conformidade falha com HTTP 401 ou 403 | `DASHBOARD_TOKEN` vencido ou sem permissão | Gere outro token com leitura de Actions e Code scanning alerts e atualize o segredo. |
| O check exigido não aparece para escolher no ruleset | O GitHub só lista checks que já rodaram uma vez | Abra um PR primeiro, ou crie o ruleset pela API com o nome `governance / governance`. |
| O PR não roda de novo depois de uma correção fora do PR (ex.: nova tag) | O workflow só dispara em abrir, push ou reabrir | Feche e reabra o PR, ou *Re-run all jobs*. |
| `GOV-SELF-001` em todo PR que mexe em `.github/` | Comportamento esperado | É um aviso para revisão humana. Não bloqueia. |
| Mudou a `main` daqui e nada mudou nos PRs | O repositório-alvo usa uma tag fixa | Publique uma tag nova e atualize o repositório-alvo ([6.6](#66-publicar-uma-nova-versão)). |
| `export --check` falha no CI | Alguém editou uma política sem regenerar os exports | `python -m governance export` e commit dos arquivos gerados. |
| Quebra de fim de linha (CRLF) em arquivos gerados | `core.autocrlf` do Windows | O `.gitattributes` fixa LF; não o remova. |
