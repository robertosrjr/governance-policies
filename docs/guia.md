# Guia da plataforma de governança

Este guia explica o que o repositório `governance-policies` faz, quais regras ele aplica,
como usar no dia a dia, como ligar em um repositório novo e as boas práticas para quem
escreve código e para quem mantém as regras.

Para a decisão de arquitetura por trás de tudo, leia o
[ADR-GOV-000](../adrs/ADR-GOV-000-modelo-de-governanca.md).

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
repositório-alvo só libera o merge com o check verde.

Três princípios definem o comportamento:

| Princípio | O que significa na prática |
|---|---|
| **Fonte única** | As regras moram só em `policies/*.yaml`. O comentário no PR, o SARIF, as instruções do Claude Code e o pack do AWS Security Agent são gerados a partir delas. |
| **Determinístico primeiro** | O que dá para verificar com regex, path ou ArchUnit é verificado assim. O LLM só **acrescenta** achados, não aprova nada e não remove achados da camada determinística. |
| **Fail-closed** | Qualquer erro (motor quebrou, LLM obrigatório sem chave, tag inexistente) resulta em `BLOCKED`. Nenhum erro vira aprovação. |

Um quarto ponto, de segurança: **o conteúdo do PR é dado, nunca instrução**. O motor,
as políticas, os prompts e o modelo vêm deste repositório. Nada do repositório revisado
muda como ele é revisado.

---

## 2. Como o repositório funciona

### 2.1 Estrutura

```
policies/*.yaml            As regras. 1 arquivo = 1 regra. Schema em policies/schema/
adrs/                      O porquê de cada regra (ADR-<ÁREA>-<NNN>)
waivers/                   Exceções aprovadas, com validade
eval/cases/                Exemplos executáveis: código que deve e que não deve violar cada regra
engine/governance/         O motor (Python)
engine/governance/prompts/ Prompts dos revisores LLM
engine/bundle.yaml         Provedor, modelo, temperatura e orçamento do LLM
exports/                   GERADO: pack do AWS Security Agent
.claude/rules/             GERADO: as regras em formato de instrução para o Claude Code
.github/workflows/         governance-required.yml (roda nos repos-alvo) e ci.yml (roda aqui)
templates/                 Modelos de política, ADR, waiver, CODEOWNERS e workflow do repo-alvo
```

### 2.2 O caminho de um PR

1. O PR é aberto no repositório-alvo, ou recebe um push, ou é reaberto.
2. O `.github/workflows/governance.yml` do repositório-alvo chama o workflow central
   [governance-required.yml](../.github/workflows/governance-required.yml) numa **tag**
   deste repositório (ex.: `v1.0.0`) e repassa os segredos (`secrets: inherit`).
3. O workflow central:
   1. baixa o código do PR em `target/`, como dado;
   2. baixa este repositório na tag em `governance/`: motor, políticas, prompts e modelo;
   3. instala as dependências com hash conferido;
   4. roda o **gitleaks** em cada commit do PR;
   5. roda o **motor** (`python -m governance review`) no diff;
   6. publica o SARIF no Code Scanning (checks `enterprise-governance` e `gitleaks`);
   7. assina o `result.json` (Sigstore) e guarda `out/` como artefato por 90 dias;
   8. dá o veredito: só passa se o motor **e** o gitleaks terminarem com 0.

### 2.3 O que o motor faz com o diff

```
arquivos alterados
   │
   ├─ 1. Seleção: só entram as políticas cujo `scope` casa com algum arquivo alterado
   ├─ 2. T0 determinístico: regex nas linhas ADICIONADAS, ou "path alterado"
   ├─ 3. T1 LLM: só políticas com `enforcement.llm`; conteúdo sem segredos, delimitado;
   │            achados repetidos de T0 são descartados, nada de T0 é removido
   ├─ 4. Waivers válidos marcam os achados que cobrem
   └─ 5. Veredito + result.json + SARIF + comentário no PR
```

O motor olha só as **linhas adicionadas** no PR. Código antigo que já viola uma regra não
bloqueia o PR de quem não mexeu nele.

### 2.4 Quando um achado bloqueia

Um achado bloqueia o merge quando **tudo** isto é verdade:

- a política está em modo `enforce`;
- a severidade é `CRITICAL`;
- o achado veio da camada determinística, **ou** a política tem `llm.blocking: true`;
- não existe waiver válido para ele.

Os modos:

| Modo | Efeito |
|---|---|
| `enforce` | Pode bloquear (se também for CRITICAL). |
| `warn` | Aparece no comentário e no SARIF como alerta. Nunca bloqueia. |
| `audit` | Não roda no PR. É exportada para revisão humana e para o AWS Security Agent. |

### 2.5 Versões

- O repositório-alvo usa uma **tag** deste repositório. Mudar a `main` daqui não afeta
  ninguém até existir uma tag nova e o repositório-alvo apontar para ela.
- Cada política tem `version` própria. O `result.json` registra a tag, o
  `bundle_version` e a versão de cada política avaliada. Assim dá para saber exatamente
  com quais regras um commit foi aprovado.

---

## 3. As regras

### 3.1 Regras que rodam no PR

| Id | O que proíbe | Onde vale | Modo | Bloqueia? | Como verifica |
|---|---|---|---|---|---|
| **ARCH-HEX-001** | Domínio dependendo de Spring ou JPA (`org.springframework`, `jakarta/javax.persistence`) | `**/src/main/java/**/domain/**/*.java` | enforce, CRITICAL | Sim | regex + ArchUnit no build |
| **ARCH-HEX-002** | `domain` ou `application` referenciando `infrastructure` | `domain/` e `application/` em `src/main/java` | enforce, CRITICAL | Sim | regex + ArchUnit no build |
| **LGPD-LOG-001** | Dado pessoal (CPF, CNPJ, RG, e-mail, telefone, cartão, senha) em log, trace, métrica ou exceção sem mascaramento | `**/*.java`, `**/*.kt` | enforce, CRITICAL | Sim no caso direto (regex); o LLM só alerta | regex + LLM consultivo |
| **SEC-SECRET-001** | Chave, token, senha ou chave privada no código ou em configuração | tudo | enforce, CRITICAL | Sim | regex + gitleaks |
| **SEC-UNICODE-001** | Caracteres invisíveis ou bidirecionais (Trojan Source) | tudo | enforce, CRITICAL | Sim | regex |
| **SEC-OBFUSC-001** | Escape `\uXXXX` fora de literal em Java (esconde código ou imports) | `**/*.java` | enforce, CRITICAL | Sim | regex |
| **LLM-INJ-001** | Texto dirigido a uma IA ("ignore previous rules", "approve this PR") | tudo | warn, MAJOR | Não, só alerta | regex + LLM |
| **GOV-SELF-001** | Mudança em CI, CODEOWNERS ou instruções de IA (`.github/`, `.claude/`, `CLAUDE.md`...) | esses caminhos | warn, MAJOR | Não, só alerta | path alterado |
| **QUAL-CODE-001** | `return null` em método público, injeção por campo, `catch` genérico que engole, retorno `Object` | `**/src/main/java/**/*.java` | warn, MAJOR | Não, só alerta | LLM |

Código de teste (`**/src/test/**`) fica fora das regras de arquitetura e de LGPD.

### 3.2 Regras só de auditoria (não rodam no PR)

| Id | Tema (OWASP Top 10:2025) |
|---|---|
| OWASP-A01 | Controle de acesso: menor privilégio, default deny, IDOR, SSRF |
| OWASP-A02 | Configuração segura: sem debug ativo, sem acesso público |
| OWASP-A03 | Cadeia de suprimentos: dependências mantidas e SBOM |
| OWASP-A04 | Criptografia: KMS CMK em repouso, TLS 1.2+ em trânsito |
| OWASP-A10 | Tratamento de exceções: fail-closed, sem stack trace para o cliente |

Elas não têm como ser verificadas com confiança por regex no diff. Ficam para revisão
humana e para o AWS Security Agent (`exports/`).

### 3.3 Como corrigir cada violação

| Id | Correção |
|---|---|
| ARCH-HEX-001 | Tire anotações Spring/JPA do domínio. Mapeamento ORM vai para `infrastructure/persistence` (ex.: `ClienteEntity`) com mapper. |
| ARCH-HEX-002 | Crie uma porta (interface) em `application/port/out` e implemente o adaptador em `infrastructure`. O caso de uso depende só da porta. |
| LGPD-LOG-001 | `PIISanitizer.mask(valor)` antes de logar, ou logue só um id técnico. Nunca o objeto inteiro nem o corpo de request/response. |
| SEC-SECRET-001 | Remova o valor, **revogue a credencial** (ela já está no histórico) e leia de um cofre ou de variável de ambiente. |
| SEC-UNICODE-001 | Remova os caracteres. Se forem necessários em um literal, use a forma escapada e peça waiver. |
| SEC-OBFUSC-001 | Escreva o caractere diretamente. Escape só dentro de literal de string ou char. |
| LLM-INJ-001 | Remova o texto. Se for teste de guardrail, deixe em diretório de teste. |
| GOV-SELF-001 | Nada a corrigir: é um aviso para o revisor humano olhar a mudança com atenção. |
| QUAL-CODE-001 | `Optional` ou exceção de domínio em vez de `null`; injeção por construtor; trate exceções específicas; tipe o retorno. |

O texto completo de cada regra, com o motivo, está no ADR indicado no arquivo da
política em `policies/`.

---

## 4. Como usar (quem abre PR)

### 4.1 No dia a dia

1. Abra o PR normalmente.
2. Espere o check `governance / governance`. Leva alguns minutos.
3. Leia o **comentário do motor** no PR. Ele lista cada achado com política, severidade,
   arquivo, linha e se bloqueia.
4. Se bloqueou, corrija conforme a [tabela 3.3](#33-como-corrigir-cada-violação) e faça push.
   O check roda de novo sozinho.
5. Alertas (`warn`) não impedem o merge, mas o revisor humano deve olhar.

Os achados também aparecem na aba **Security → Code scanning** do repositório e em
**Files changed**, na linha do problema.

### 4.2 Testar antes do push

Com os dois repositórios lado a lado no disco, a partir deste repositório:

```bash
PYTHONPATH=engine python -m governance review --repo ../../java/virtualthreads --base origin/main --no-llm
```

- `--no-llm` roda só a camada determinística, que é a que bloqueia. Não precisa de chave.
- Sem `--no-llm`, é preciso `GEMINI_API_KEY` no ambiente.
- A saída termina em `Veredito: APPROVED` ou `Veredito: BLOCKED`. Os arquivos ficam em
  `governance-out/`.

### 4.3 Quando a regra está errada para o seu caso

Não contorne a regra (renomear pacote, quebrar a linha para a regex não pegar). Os dois
caminhos legítimos são:

- **Falso positivo**: abra uma issue ou PR neste repositório com o trecho de código. Ele
  vira um caso de eval e a regra é corrigida.
- **Exceção justificada**: peça um waiver (seção [6.3](#63-pedir-uma-exceção-waiver)).

Não existe bypass por comentário no PR.

---

## 5. Como aplicar em um repositório novo

### 5.1 Modo conta pessoal (atual, provisório)

1. **CODEOWNERS**: copie [templates/target-repo/CODEOWNERS](../templates/target-repo/CODEOWNERS)
   para `.github/CODEOWNERS` e troque `@org/plataforma` pelo seu usuário.
2. **Workflow**: copie [templates/target-repo/governance.yml](../templates/target-repo/governance.yml)
   para `.github/workflows/governance.yml`. A tag do `uses:` e o `governance_ref` têm que
   ser iguais.
3. **Remova** qualquer workflow de IA que leia prompts ou scripts do próprio repositório
   (na PoC eram `ai-governance.yml` e `.github/scripts/`).
4. **Segredo**: `GEMINI_API_KEY` em *Settings → Secrets and variables → Actions*.
5. **Ruleset** do branch principal (*Settings → Rules → Rulesets*):
   - Bypass list vazia;
   - Restrict deletions e Block force pushes;
   - Require a pull request before merging, com 0 aprovações e sem code owner review
     (com um único dono, você não conseguiria aprovar os próprios PRs);
   - Require status checks: `governance / governance`, com "up to date" marcado.
6. **ArchUnit**: mantenha os testes `ArchitectureTest#domain_should_not_depend_on_frameworks`
   e `#application_should_not_depend_on_infrastructure` no build.
7. **Teste o bloqueio**: um PR com `import org.springframework.stereotype.Component;` em
   uma classe de `domain/` deve ficar vermelho com ARCH-HEX-001. Feche sem merge.

Faça os passos 1 a 3 em um PR: esse PR já roda a governança nova.

**Limite deste modo**: quem abre o PR pode editar ou apagar o `governance.yml`. O check
obrigatório e o CODEOWNERS só reduzem esse risco. Não trate o resultado como controle
formal até migrar para a organização.

### 5.2 Modo organização (o destino)

1. Crie a organização no GitHub (plano Team ou Enterprise) e transfira os repositórios.
2. Aplique [templates/org-ruleset.json](../templates/org-ruleset.json) com o
   `repository_id` deste repositório e a tag: ele obriga **todos** os repositórios a
   rodar o workflow central, sem que eles possam removê-lo.
3. Segredos da organização: `GEMINI_API_KEY` e, se este repositório for privado,
   `GOVERNANCE_READ_TOKEN`.
4. Apague o `governance.yml` dos repositórios-alvo (o ruleset substitui).
5. Troque os usuários do CODEOWNERS por times e ligue "Require review from Code Owners".

### 5.3 Gate de deploy

O check protege o merge. Para garantir que só código aprovado vai para produção, o
pipeline de deploy deve verificar o `result.json` atestado do commit (comandos no
[README](../README.md#gate-de-deploy)). Sem evidência aprovada, sem deploy.

---

## 6. Como mudar as regras (quem mantém)

Toda mudança neste repositório entra por PR. O [ci.yml](../.github/workflows/ci.yml) roda
testes, `validate`, `export --check` e `eval`, e bloqueia se algo regredir.

### 6.1 Criar uma regra nova

1. Copie [templates/policy-template.yaml](../templates/policy-template.yaml) para
   `policies/<ID>.yaml`.
2. Escreva o ADR em `adrs/` a partir de [templates/adr-template.md](../templates/adr-template.md).
3. Crie casos em `eval/cases/`: pelo menos **um positivo** (deve violar) e **um negativo**
   (parecido, mas correto). Política `enforce` sem os dois não passa no `validate`.
4. Comece em `warn`. Suba para `enforce` depois de ver a regra rodando em PRs reais sem
   falso positivo.
5. Rode tudo e regenere os arquivos gerados:
   ```bash
   python -m pytest
   PYTHONPATH=engine python -m governance validate
   PYTHONPATH=engine python -m governance export
   PYTHONPATH=engine python -m governance eval
   ```

Um caso de eval é só o código e a expectativa:

```yaml
id: arch-hex-001-import-spring
description: Domínio importando Spring e JPA (caso clássico).
files:
  app/src/main/java/com/empresa/pedidos/domain/model/Cliente.java: |
    package com.empresa.pedidos.domain.model;
    import org.springframework.stereotype.Component;
    @Component
    public class Cliente {}
expect:
  ARCH-HEX-001: true
  ARCH-HEX-002: false
```

### 6.2 Alterar uma regra existente

- Suba o `version` da política.
- Todo falso positivo ou falso negativo encontrado vira um caso de eval **antes** da
  correção. Assim ele não volta.
- Não edite `exports/`, `.claude/rules/governance-policies.md` nem os `.lock`: edite a
  fonte e rode `export` ou regenere o lock.

### 6.3 Pedir uma exceção (waiver)

1. Copie [templates/waiver-example.yaml](../templates/waiver-example.yaml) para
   `waivers/WVR-AAAA-NNN.yaml`.
2. Preencha: política, repositório, `paths` o mais estreitos possível, justificativa,
   quem pediu, quem aprovou e a validade.
3. Abra um PR neste repositório. Regras que o motor confere:
   - `approved_by` diferente de `requested_by`;
   - validade de no máximo **90 dias**;
   - `paths: ["**"]` sozinho é rejeitado;
   - `commit` (opcional) restringe a exceção a um commit.
4. Depois do merge, publique uma tag nova e atualize o repositório-alvo.

Waiver vencido é ignorado e o achado volta a bloquear. O CI deste repositório falha
enquanto houver waiver vencido, para forçar a limpeza.

### 6.4 Mudar o modelo, os prompts ou o `bundle.yaml`

Isso é uma nova versão do revisor LLM:

1. Suba `bundle_version` em [engine/bundle.yaml](../engine/bundle.yaml).
2. Rode o eval com LLM (localmente com `GEMINI_API_KEY`, ou pelo `ci.yml` em
   *Actions → ci → Run workflow* com `llm_repeat` > 0):
   ```bash
   PYTHONPATH=engine python -m governance eval --llm --repeat 5
   ```
3. Só faça merge sem regressão de precisão e recall.

Para testar um modelo candidato sem alterar o bundle: `eval --llm --model <modelo>`.

### 6.5 Deixar o LLM bloquear

Uma política só pode ter `llm.blocking: true` com `llm.eval_evidence` apontando para um
resultado de eval que justifique isso. O `validate` recusa sem a evidência. Hoje nenhuma
política usa o LLM para bloquear.

### 6.6 Publicar uma nova versão

1. Merge na `main` deste repositório.
2. Tag nova, sem mover as antigas:
   ```bash
   git tag -a v1.1.0 -m "Descrição da mudança"
   git push origin v1.1.0
   ```
3. No repositório-alvo, abra um PR trocando a tag nos **dois** lugares do
   `governance.yml` (`@v1.1.0` e `governance_ref: v1.1.0`). O próprio PR já roda com a
   versão nova.

Versionamento sugerido: **patch** (`v1.0.1`) para correção de falso positivo, **minor**
(`v1.1.0`) para regra nova em `warn` ou waiver, **major** (`v2.0.0`) para regra que passa
a bloquear ou mudança no formato do `result.json`.

---

## 7. Boas práticas

### 7.1 Para quem escreve código

- **Rode o review local com `--no-llm` antes do push.** É rápido e mostra o mesmo bloqueio
  que o CI.
- **Mantenha o domínio puro.** Spring, JPA e `infrastructure` ficam fora de `domain/` e
  `application/`. O domínio depende só de Java e de tipos do domínio.
- **Nunca logue objeto inteiro, request ou response.** Logue ids técnicos, ou passe o valor
  por `PIISanitizer.mask`.
- **Segredo commitado é segredo vazado**, mesmo que você apague no commit seguinte: o
  gitleaks olha cada commit do PR e o histórico continua existindo. Revogue a credencial.
- **Não tente enganar a regex** (quebrar linha, escapes Unicode, montar o nome do pacote
  por concatenação). Há regras específicas para ofuscação, e o ArchUnit olha o bytecode.
- **Leia os alertas `warn`.** Eles não bloqueiam, mas costumam apontar problemas reais de
  qualidade e LGPD que a regex não pega.
- **PRs pequenos.** O revisor LLM tem orçamento de contexto; diffs menores dão revisões
  melhores.

### 7.2 Para quem mantém as regras

- **Determinístico primeiro.** Se dá para ser regex, path ou ArchUnit, não use LLM.
- **Toda regra tem motivo e exemplo.** Sem ADR e sem casos de eval, a regra não entra.
- **Comece em `warn`, promova para `enforce`.** Uma regra que bloqueia errado ensina o time
  a contorná-la.
- **Falso positivo vira caso de eval** antes da correção.
- **Waiver estreito e curto.** Um caminho específico, poucos dias, com justificativa que
  diga quando a exceção deixa de ser necessária.
- **Tag imutável.** Nunca mova nem apague uma tag publicada: o `result.json` atestado
  referencia a tag.
- **Não edite arquivos gerados.** Edite a fonte e rode `export`.
- **Mudança de modelo ou prompt é release**, com eval antes.

### 7.3 Para quem opera

- **Um repositório-alvo por vez.** Ligue em um repositório, observe alguns PRs e só então
  expanda.
- **Acompanhe `GOV-SELF-001`.** Mudanças em `.github/` do repositório-alvo podem desligar a
  governança no modo conta pessoal. Revise essas com atenção.
- **Migre para a organização** antes de usar o resultado como controle formal (auditoria,
  compliance).
- **LGPD Art. 33**: o diff sai do país para o provedor de LLM. Formalize a base legal ou o
  contrato antes de rodar em repositórios com dado real.

---

## 8. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| A execução aparece com o nome do arquivo (`.github/workflows/governance.yml`) e falha na hora | A tag do `uses:` não existe neste repositório, ou o repositório é privado sem acesso liberado | `git ls-remote --tags origin` aqui; publique a tag. Se for privado, *Settings → Actions → General → Access*. |
| Comentário "⚠️ Revisor de IA indisponível" | O provedor de LLM respondeu 503 (sobrecarga), 429 (cota esgotada) ou não respondeu. O PR fica bloqueado (fail-closed), mas não é problema no código | Espere alguns minutos e clique em *Re-run all jobs*. O comentário diz se as regras que rodaram acharam alguma violação. |
| Comentário "❗ Erros de execução" | Chave recusada, segredo ausente, arquivo grande demais para o revisor ou gitleaks com segredo | Cada erro vem com **O que fazer**. Os mesmos textos aparecem como anotações na página da execução. |
| Comentário "❗ Erro de configuração" | O motor nem conseguiu avaliar (ex.: base do diff inexistente) | Rode de novo. Se repetir, avise o time de plataforma com o link da execução. |
| O check exigido não aparece para escolher no ruleset | O GitHub só lista checks que já rodaram uma vez | Abra um PR primeiro, ou crie o ruleset pela API com o nome `governance / governance`. |
| O PR não roda de novo depois de uma correção fora do PR (ex.: nova tag) | O workflow só dispara em abrir, push ou reabrir | Feche e reabra o PR, ou use *Re-run all jobs*. |
| `GOV-SELF-001` em todo PR que mexe em `.github/` | Comportamento esperado | É um aviso para revisão humana. Não bloqueia. |
| Mudou a `main` daqui e nada mudou nos PRs | O repositório-alvo usa uma tag fixa | Publique uma tag nova e atualize o `governance.yml` do alvo (seção [6.6](#66-publicar-uma-nova-versão)). |
| `export --check` falha no CI | Alguém editou uma política sem regenerar os exports | Rode `python -m governance export` e commite os arquivos gerados. |
| Quebra de fim de linha (CRLF) em arquivos gerados | `core.autocrlf` do Windows | O `.gitattributes` fixa LF; não o remova. |
