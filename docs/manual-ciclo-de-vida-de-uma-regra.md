# Manual: ciclo de vida de uma regra

Este manual acompanha uma regra desde a decisão de arquitetura até ela estar em
produção nos Pull Requests, passando por cada arquivo que ela toca e por cada
verificação que ela precisa passar, inclusive o eval. O exemplo é uma regra real
deste repositório, a **FIN-MONEY-001** ("dinheiro não é `double`"); quando a regra
depende de IA, o exemplo é a **RES-IDEMP-001** ("retry em escrita financeira sem
idempotência").

O diagrama resumido desta jornada está em
[fluxo-da-esteira.md, jornada 1](fluxo-da-esteira.md#1-ciclo-de-vida-de-uma-regra).
As decisões que fundamentam o processo estão no
[ADR-GOV-000](../adrs/ADR-GOV-000-modelo-de-governanca.md) (modelo),
[ADR-GOV-003](../adrs/ADR-GOV-003-operacao-em-instituicao-financeira.md) (rollout) e
[ADR-GOV-007](../adrs/ADR-GOV-007-release-e-versionamento.md) (release).

## Sumário

- [Visão geral: as etapas e os arquivos](#visão-geral-as-etapas-e-os-arquivos)
- [Etapa 0. A decisão: isso deve virar regra?](#etapa-0-a-decisão-isso-deve-virar-regra)
- [Etapa 1. O ADR: o porquê](#etapa-1-o-adr-o-porquê)
- [Etapa 2. A política: o quê](#etapa-2-a-política-o-quê)
- [Etapa 3. Os casos de eval: a prova](#etapa-3-os-casos-de-eval-a-prova)
- [Etapa 4. Testes do motor (quando precisa)](#etapa-4-testes-do-motor-quando-precisa)
- [Etapa 5. Classificação (opcional)](#etapa-5-classificação-opcional)
- [Etapa 6. Export: os arquivos gerados](#etapa-6-export-os-arquivos-gerados)
- [Etapa 7. Validação local](#etapa-7-validação-local)
- [Etapa 8. O eval](#etapa-8-o-eval)
- [Etapa 9. Versões, PR e CI no repositório central](#etapa-9-versões-pr-e-ci-no-repositório-central)
- [Etapa 10. Release e smoke test](#etapa-10-release-e-smoke-test)
- [Etapa 11. A regra em produção: warn, medição e promoção](#etapa-11-a-regra-em-produção-warn-medição-e-promoção)
- [Checklist](#checklist)
- [Problemas comuns](#problemas-comuns)

## Visão geral: as etapas e os arquivos

| Etapa | O que você faz | Arquivos |
|---|---|---|
| 0 | Decide se a decisão de arquitetura vira regra e de que tipo | nenhum |
| 1 | Escreve o porquê | `templates/adr-template.md` → `adrs/ADR-<ÁREA>-<NNN>-<tema>.md` |
| 2 | Escreve a regra verificável | `templates/policy-template.yaml` → `policies/<ID>.yaml`, validado por `policies/schema/policy.schema.json` |
| 3 | Escreve os exemplos que provam a regra | `eval/cases/<id>-*.yaml` |
| 4 | Testa o motor, se a regra usou algo novo | `tests/*.py` |
| 5 | Endurece a regra para uma classe de repositório (opcional) | `classification/repositories.yaml` |
| 6 | Gera os derivados | `exports/aws-security-agent/governance-pack.json`, `.claude/rules/governance-policies.md` |
| 7 | Valida localmente | nenhum (comandos) |
| 8 | Mede a regra no eval | `eval-offline.json`, `eval-llm-<bundle>.json` (não versionados) |
| 9 | Sobe versões e abre o PR | `engine/governance/__init__.py`, `pyproject.toml`, `engine/bundle.yaml`, `.github/CODEOWNERS`, `.github/workflows/ci.yml` |
| 10 | Publica e testa no destino | tag `vX.Y.Z`; `governance.yml` e `deploy.yml` do repositório piloto |
| 11 | Acompanha e promove | painel de conformidade; `mode:` na política |

Uma regra só existe quando as três peças existem juntas: **ADR** (por quê), **política**
(o quê) e **casos de eval** (a prova). O CLAUDE.md deste repositório exige isso, e o
`validate` recusa uma política em `enforce` sem casos positivo e negativo.

---

## Etapa 0. A decisão: isso deve virar regra?

Nem toda boa prática vira regra. Antes de escrever qualquer arquivo, responda:

1. **A decisão é importante?** O descumprimento causa incidente, prejuízo, problema
   regulatório ou dívida difícil de pagar? "Dinheiro em `double`" gera diferença de
   centavos em conciliação, juros e rateio: sim.
2. **Dá para verificar olhando o PR?** A regra precisa ser observável no diff: uma
   linha, um arquivo, a diferença entre duas versões de um contrato. "O sistema deve ser
   rápido" não é observável no PR; é uma fitness function de runtime e fica com a
   observabilidade (ADR-GOV-008).
3. **Qual é o mecanismo mais simples que resolve?** Use sempre o primeiro que servir, na
   ordem abaixo. Esta é a regra "determinístico primeiro" do ADR-GOV-000.

| Mecanismo | Quando usar | Exemplo |
|---|---|---|
| `regex` nas linhas adicionadas | O problema aparece numa linha, com um padrão reconhecível | `double valorTarifa` (FIN-MONEY-001) |
| `regex` + `validator` | A regex acha candidatos, mas só um cálculo confirma | CPF com dígito verificador válido (LGPD-DATA-001), cartão com Luhn (SEC-PAN-001) |
| `path_changed` | O problema é mexer num arquivo | migração versionada editada (DATA-MIG-001) |
| `requires_companion` | Se um arquivo muda, outro precisa mudar junto | dependência nova sem ADR (GOV-ADR-001) |
| `contract` | O problema é a diferença entre a base e o PR | campo removido de um contrato OpenAPI (API-CONTRACT-001) |
| `external` | Outra ferramenta verifica melhor (no build) | ArchUnit sobre o bytecode (ARCH-HEX-001) |
| `llm` com `engine: jev` | A decisão depende de contexto, mas a pergunta é de sim/não sobre uma linha | "este retry grava dinheiro sem chave de idempotência?" (RES-IDEMP-001) |
| `llm` generativo | A regra é semântica e aberta, e o revisor precisa apontar onde | regras de qualidade (QUAL-CODE-001) |

Uma regra pode combinar mecanismos. A LGPD-LOG-001 tem uma regex que bloqueia o caso
direto e o Jev que julga os casos indiretos. O que o LLM encontra **só acrescenta**
achados: ele nunca remove o que a camada determinística achou e nunca aprova nada
sozinho.

---

## Etapa 1. O ADR: o porquê

**O que é.** O Architecture Decision Record registra a decisão, o contexto que a
motivou, as alternativas descartadas e as consequências aceitas. É o documento que
alguém lê daqui a dois anos para entender por que o PR dele foi bloqueado.

**Onde.** `adrs/ADR-<ÁREA>-<NNN>-<tema-curto>.md`, a partir de
[templates/adr-template.md](../templates/adr-template.md). O ID segue o padrão
`ADR-[A-Z]+-\d{3}` (o schema da política verifica): `ADR-FIN-001`, `ADR-SEC-003`. A área
agrupa decisões afins (ARCH, FIN, LGPD, SEC, DATA, API, SUP, AI, GOV, QUAL). Um ADR pode
fundamentar várias políticas: o ADR-SEC-003 fundamenta SEC-CRYPTO-001 e SEC-PAN-001.

**Seções do template e o que colocar em cada uma** (exemplo:
[ADR-FIN-001](../adrs/ADR-FIN-001-aritmetica-monetaria.md)):

| Seção | O que escrever | No ADR-FIN-001 |
|---|---|---|
| Status | `Proposto`, `Aceito` ou `Substituído por ...`, com data | Aceito — 2026-09-29 |
| Contexto | O problema real e por que importa agora | erro de centavo vira diferença de conciliação; `new BigDecimal(0.1)` herda o erro binário; `divide` sem `RoundingMode` lança exceção em produção |
| Decisão | A regra em linguagem natural, sem regex | valor monetário usa `BigDecimal` ou um value object `Dinheiro`; toda divisão declara o `RoundingMode` |
| Verificação | Tabela: política, o que o motor verifica, outras camadas; e os **limites conhecidos** | tipo inferido (`var x = calcula()`) escapa; `divide` em `BigInteger` dá falso positivo |
| Exemplos | Onde estão os casos de eval | `eval/cases/fin-money-001-*.yaml` |
| Consequências | Custos, falsos positivos esperados, impacto nos times | entra em `warn`; nomes como `taxaDeAcerto` geram falso positivo |

**O que NÃO colocar no ADR:** regex, escopo, severidade ou modo. Isso vive só na
política; duas fontes divergem com o tempo (princípio "uma regra, uma fonte").

**Use `Proposto`** quando a decisão depende de alguém de fora do time de plataforma
(jurídico, segurança da informação, uma plataforma que ainda não existe). Exemplos:
ADR-DATA-002 (lista de regiões) e ADR-AI-001 (gateway corporativo de IA).

---

## Etapa 2. A política: o quê

**O que é.** Um arquivo YAML que é a **fonte única** da regra: o motor avalia a partir
dele, e os exports para o Claude Code e para o AWS Security Agent saem dele.

**Onde.** `policies/<ID>.yaml`, a partir de
[templates/policy-template.yaml](../templates/policy-template.yaml). **O nome do arquivo
é o ID** (o `validate` recusa se não for). O formato é validado por
[policies/schema/policy.schema.json](../policies/schema/policy.schema.json).

### Os campos, um a um

A política completa está em [policies/FIN-MONEY-001.yaml](../policies/FIN-MONEY-001.yaml).

```yaml
id: FIN-MONEY-001
title: Aritmética monetária com tipo binário ou sem arredondamento explícito
version: 1.0.0
owner: arquitetura
adr: ADR-FIN-001
severity: CRITICAL
mode: warn
scope:
  include: ["**/src/main/**/*.java", "**/src/main/**/*.kt"]
  exclude: ["**/src/test/**"]
description: >-
  Valor monetário (...) não pode usar double/float (...)
remediation: >-
  Use BigDecimal (ou um value object Dinheiro no domínio) (...)
targets: [pr-review, claude-code, aws-security-agent]
compliance:
  applicability: Código Java/Kotlin de produção que calcula ou armazena valores monetários.
  compliant: monetary values use BigDecimal (...)
  non_compliant: monetary values are declared as double/float (...)
enforcement:
  deterministic:
    - type: regex
      pattern: '\b(?:double|float|Double|Float)\s+\w*(?i:valor|saldo|...)\w*\s*[;=,)(]|...'
      strip: '"(?:[^"\\]|\\.)*"|//.*$'
      message: Valor monetário declarado como double/float. Use BigDecimal ou um value object de dinheiro.
    # (+ duas regras: BigDecimal de literal double; divide/setScale sem RoundingMode)
```

| Campo | O que é | Como escolher |
|---|---|---|
| `id` | Identificador estável: `ÁREA-TEMA-NNN` | Nunca reaproveite um ID; ele aparece em evidências antigas |
| `title` | Uma frase com a regra | Aparece no comentário do PR e no painel |
| `version` | Versão da **política** (semver) | Suba a cada mudança de comportamento; ela fica registrada em cada `result.json` |
| `owner` | Time dono da regra | Quem responde por falso positivo e por promoção |
| `adr` | O ADR da etapa 1 | O `validate` confere que o arquivo existe em `adrs/` |
| `severity` | `CRITICAL`, `MAJOR` ou `MINOR` | Só `CRITICAL` pode bloquear |
| `mode` | `audit` (só evidência), `warn` (aparece no PR) ou `enforce` (bloqueia) | **Toda regra nova entra em `warn`** (ADR-GOV-003) |
| `scope.include` / `exclude` | Globs dos arquivos que a regra olha | `**/` casa zero ou mais pastas; seja estreito: escopo largo = falso positivo |
| `description` | O que a regra exige e o que cada camada cobre | Escrito para o desenvolvedor que foi bloqueado |
| `remediation` | Como corrigir | Concreto, com o código certo; a primeira linha aparece no achado do Jev |
| `targets` | Onde a regra vale: `pr-review` (motor), `claude-code` (orienta o assistente), `aws-security-agent` (pack exportado) | `aws-security-agent` exige o bloco `compliance` |
| `compliance` | Critérios de conformidade em inglês, para o AWS Security Agent | Só quando `aws-security-agent` está em `targets` |
| `enforcement` | Como a regra é verificada | Abaixo |

**Quando um achado bloqueia o PR:** política em `enforce` **e** severidade `CRITICAL`
**e** (achado determinístico **ou** política com `llm.blocking: true`) **e** sem waiver
válido. Todo o resto aparece como alerta. Qualquer erro de execução bloqueia (fail-closed).

### `enforcement.deterministic`: os tipos de regra

Todos se aplicam só aos arquivos do escopo. A `message` é o texto do achado.

**`regex`**: roda em cada **linha adicionada** do PR.

| Chave | Para quê | Na FIN-MONEY-001 |
|---|---|---|
| `pattern` | O padrão que caracteriza a violação | declaração `double`/`float` com nome monetário |
| `strip` | Remove trechos **antes** de testar | literais de string e comentários `//`: `"double valor"` num texto não dispara |
| `exclude` | Descarta a linha inteira se casar | não usado aqui |
| `validator` | `cpf`, `cnpj` ou `pan`: o trecho casado só vira achado se passar no cálculo | não usado aqui; é o que separa CPF real de "11 dígitos quaisquer" na LGPD-DATA-001 |

Dicas de regex no YAML: use aspas simples; para uma aspa simples dentro do padrão,
escreva duas (`''`). `(?i:...)` liga "ignorar maiúsculas" só num trecho. O `validate`
compila cada regex e recusa uma inválida.

**`path_changed`**: um único achado listando os arquivos do escopo que mudaram.
`change_types` restringe a `added`, `modified`, `renamed` ou `deleted`. A DATA-MIG-001
usa `[modified, renamed, deleted]`: migração **nova** é o caminho certo e não dispara.

**`requires_companion`**: se um arquivo do escopo muda (ou tem linha adicionada que casa
com `trigger`), o PR precisa alterar algum arquivo que case com `companion`. Grupos
nomeados que começam com `key` no `trigger` fazem a regra contar só o que não existia na
base: na GOV-ADR-001, `<artifactId>(?P<key>[^<]+)</artifactId>` dispara para dependência
nova, mas não para troca de versão de uma existente.

**`contract`**: compara a versão da base com a do PR (`format: openapi` ou `avro`) e
aponta cada mudança incompatível (campo removido, obrigatório novo, tipo alterado). O
comparador está em `engine/governance/contracts.py`.

**`external`**: documenta uma verificação feita fora do motor (ArchUnit no build). O
motor não executa.

### `enforcement.llm`: quando a regra precisa de julgamento

**Com o Jev** (`engine: jev`), o modelo não escreve nada: responde a probabilidade de
"sim" para uma pergunta sobre cada linha marcada. Exemplo, a
[RES-IDEMP-001](../policies/RES-IDEMP-001.yaml):

```yaml
enforcement:
  llm:
    engine: jev
    blocking: false
    candidates: '@Retryable\b|@Retry\b|\bRetryTemplate\b|...'
    threshold: 0.5
    question: |
      A linha {line} de `codigo` é: {text}
      Essa linha configura retry automático de uma operação que grava ou movimenta dinheiro
      (...) sem uma chave de idempotência reenviada em cada tentativa (...)? Não conta:
      retry de leitura ou consulta (...)
```

| Chave | Para quê |
|---|---|
| `candidates` | Regex que marca as linhas adicionadas a julgar. **O recall da regra nunca passa do recall desta regex**: o que ela não marca, o Jev não vê. Faça-a ampla |
| `question` | Pergunta de sim/não sobre **uma** linha; `{line}` e `{text}` viram o número e o texto dela. O Jev recebe o arquivo inteiro e os arquivos do PR que ele cita como contexto. Diga o que conta e, principalmente, o que **não** conta |
| `threshold` | Probabilidade a partir da qual a linha vira achado; calibrada no eval |
| `blocking` | `false` até o eval justificar; `true` exige `eval_evidence` |

**Com o revisor generativo** (sem `engine`), o modelo lê os arquivos do escopo e aponta
achados. Exemplo, a [QUAL-CODE-001](../policies/QUAL-CODE-001.yaml):

```yaml
enforcement:
  llm:
    reviewer: quality          # engine/governance/prompts/quality.md
    blocking: false
    criteria: |
      Aponte, somente em linhas adicionadas:
      - `return null` em método público; (...)
```

O `reviewer` escolhe o prompt em `engine/governance/prompts/<reviewer>.md` (somado ao
`base.md`), e o `criteria` entra no prompt. Mudar um prompt é release do bundle (etapa 9).

Nos dois casos, o conteúdo enviado ao provedor passa antes pela remoção de segredos,
CPF, CNPJ, cartão e e-mail (`engine/governance/redact.py`), e a severidade do achado é
a da política, não a que o modelo acha.

---

## Etapa 3. Os casos de eval: a prova

**O que são.** Exemplos executáveis da regra: arquivos de código com a expectativa de
disparar ou não. Eles provam que a regra pega o que deve (recall) e não pega o que não
deve (precisão), e protegem contra regressão quando alguém mexer na regra, no motor ou
no modelo depois.

**Onde.** `eval/cases/<id-da-política-em-minúsculas>-<cenário>.yaml`.

Caso positivo, [fin-money-001-double-e-divide.yaml](../eval/cases/fin-money-001-double-e-divide.yaml):

```yaml
id: fin-money-001-double-e-divide
description: Valor em double, BigDecimal de literal double e divide sem RoundingMode.
tags: [financeiro]
files:
  app/src/main/java/com/empresa/conta/domain/Tarifa.java: |
    package com.empresa.conta.domain;

    import java.math.BigDecimal;

    public class Tarifa {
        private double valorTarifa;
        private final BigDecimal percentual = new BigDecimal(0.015);

        public BigDecimal rateio(BigDecimal total, BigDecimal parcelas) {
            return total.divide(parcelas);
        }
    }
expect:
  FIN-MONEY-001: true
```

Caso negativo, [fin-money-001-bigdecimal-ok.yaml](../eval/cases/fin-money-001-bigdecimal-ok.yaml):
o mesmo código escrito do jeito certo, mais um `double latenciaMs` (um `double` que não
é dinheiro), com `FIN-MONEY-001: false`.

| Campo | Para quê |
|---|---|
| `id` | Igual ao nome do arquivo |
| `description` | O cenário, em uma frase |
| `tags` | Agrupamento livre |
| `requires_llm` | `true` quando só a IA consegue acertar o caso (ex.: `toString()` implícito de objeto com CPF). Esses casos só rodam no eval com LLM |
| `files` | Caminho → conteúdo. **Todas as linhas contam como adicionadas.** O caminho precisa cair no `scope` da política |
| `base_files` | Opcional: conteúdo na base do PR. Um caminho que está nos dois vira "modificado". Obrigatório para `contract`, `path_changed` com `modified` e `requires_companion` com `key` |
| `expect` | Política → `true` (tem de disparar) ou `false` (não pode disparar). Um caso pode esperar várias políticas |

**Como escrever bons casos:**

- **Pelo menos um positivo e um negativo** por política. Para `enforce`, o `validate`
  exige; para `warn`, é o que dá segurança para promover depois.
- **O negativo mais valioso é o quase-positivo:** código parecido com a violação que
  não é violação (`double latenciaMs`; retry numa consulta; CPF com dígito inválido).
  É ele que mede o falso positivo.
- **Um positivo que exercite todas as regras da política.** Se a política tem três
  `regex`, o caso positivo deve ter as três violações; o teste da etapa 4 confere.
- **Caminhos realistas**, dentro do escopo (`src/main/.../domain/...`). Um caso fora do
  escopo "passa" pelo motivo errado.
- **Sem dado real:** CPF e cartão de exemplo têm de ser sintéticos ou números de teste
  das bandeiras.
- Caracteres invisíveis só com escapes em string YAML entre aspas duplas (regra 8 do
  CLAUDE.md).

---

## Etapa 4. Testes do motor (quando precisa)

Uma política nova que só usa tipos de regra existentes **não precisa** de teste em
`tests/`: o eval já é o teste dela. Escreva teste quando:

- **A política tem várias regras.** O eval confere a política como um todo; se só uma
  das três regras funcionar, ele passa mesmo assim. O teste
  `test_every_rule_of_the_policy_fires_on_its_positive_case`
  ([tests/test_financial_rules.py](../tests/test_financial_rules.py)) confere que cada
  `message` da política aparece no caso positivo. Acrescente a sua política à lista
  parametrizada dele.
- **Você mexeu no motor** (tipo de regra novo, validador novo, mudança no diff): teste
  unitário do comportamento novo em `tests/`, no estilo dos existentes (`test_*.py`,
  fixtures em `tests/conftest.py`).

---

## Etapa 5. Classificação (opcional)

Se a regra deve ser mais rígida em repositórios de maior risco, endureça-a na classe em
[classification/repositories.yaml](../classification/repositories.yaml)
([ADR-GOV-009](../adrs/ADR-GOV-009-classificacao-de-repositorios.md)):

```yaml
classes:
  restrito:
    llm: false
    raise_mode:
      SEC-PAN-001: enforce
```

A classe **só endurece** (`audit` < `warn` < `enforce`); tentar afrouxar invalida o
bundle. Subir para `enforce` numa classe exige os mesmos casos positivo e negativo. Assim
a regra bloqueia primeiro onde o risco é maior e continua em `warn` no resto.

---

## Etapa 6. Export: os arquivos gerados

```bash
PYTHONPATH=engine python -m governance export
```

| Arquivo gerado | Para quem | O que leva da política |
|---|---|---|
| `.claude/rules/governance-policies.md` | Claude Code dos desenvolvedores, **antes** do PR | políticas com `claude-code` em `targets`: título, severidade, modo, escopo, descrição e correção |
| `exports/aws-security-agent/governance-pack.json` | AWS Security Agent (revisão de design e pentest) | políticas com `aws-security-agent`: descrição e o bloco `compliance` |

**Nunca edite esses arquivos à mão** (regra 3 do CLAUDE.md): edite a política e rode o
export de novo. O CI roda `export --check` e reprova se estiverem desatualizados.

---

## Etapa 7. Validação local

Antes de abrir o PR, rode na raiz do repositório:

```bash
python -m pytest                                  # testes do motor
PYTHONPATH=engine python -m governance validate   # consistência do bundle
PYTHONPATH=engine python -m governance export --check
PYTHONPATH=engine python -m governance eval       # eval determinístico (etapa 8)
```

**O que o `validate` confere** (e por que cada item existe):

| Verificação | Evita |
|---|---|
| Cada política segue o schema | campo faltando, modo ou severidade inexistente |
| Nome do arquivo = `id`; `id` único | duas fontes para a mesma regra |
| O ADR citado existe em `adrs/` | regra sem porquê |
| Todas as regex compilam (`pattern`, `strip`, `exclude`, `trigger`, `candidates`) | erro de regex só em produção |
| `llm.blocking: true` tem `eval_evidence` | IA bloqueando sem medição |
| Waivers válidos (aprovador ≠ solicitante, até 90 dias, política existente) | exceção sem controle |
| Provedores do `bundle.yaml` conhecidos; prompt existe para cada `reviewer`; seção `jev` presente se alguma política usa o Jev | revisor quebrado |
| Política em `enforce` tem caso positivo e negativo; idem para o que uma classe sobe para `enforce` | bloqueio sem prova |
| Classificação consistente (classes, repositórios, a classe só endurece) | classe afrouxando regra |
| Nenhum submódulo versionado | o incidente das tags v1.4.0–v1.7.0 (ADR-GOV-007) |

Saída esperada: `Bundle 1.5.0 válido: 34 políticas`.

**Teste num repositório de verdade**, só com a camada determinística:

```bash
PYTHONPATH=engine python -m governance review --repo ../../java/virtualthreads \
  --base origin/main --no-llm --out /tmp/gov
```

O `result.json` e o `report.md` em `--out` mostram o que o PR daquele repositório
receberia.

---

## Etapa 8. O eval

O eval trata o revisor como um modelo em produção (ADR-GOV-000, princípio 4): nenhuma
mudança em regra, motor, prompt ou modelo entra se piorar o resultado nos casos.

### Eval determinístico (todo PR, no CI)

```bash
PYTHONPATH=engine python -m governance eval --out eval-offline.json
```

**O que acontece:** para cada caso **sem** `requires_llm`, o motor roda a camada
determinística sobre os `files` (todas as linhas como adicionadas, `base_files` como a
base) e compara o que disparou com o `expect`.

**Saída** (trecho real):

```
Eval (offline, 64 casos, repetições=1)
política            TP  FP  FN  TN  recall   prec.
FIN-MONEY-001        1   0   0   1    1.00    1.00
SEC-PAN-001          1   0   0   1    1.00    1.00
...
Eval: APROVADO
```

| Coluna | Significa |
|---|---|
| TP (verdadeiro positivo) | esperado `true` e disparou |
| FP (falso positivo) | esperado `false` e disparou |
| FN (falso negativo) | esperado `true` e não disparou |
| TN (verdadeiro negativo) | esperado `false` e não disparou |
| recall | TP ÷ (TP + FN): quanto do que deveria ser pego foi pego |
| prec. (precisão) | TP ÷ (TP + FP): quanto do que foi apontado estava certo |

**Critério:** no modo determinístico, **todo caso tem de bater 100%**. Um único erro
aparece como `caso: POLÍTICA esperado=True obtido=False` e o eval reprova (código de
saída 1). Regex não tem "quase": ou o caso passa, ou a regra está errada, ou o caso está.

### Eval com LLM (release do bundle)

```bash
OPENROUTER_API_KEY=... TYPESAFE_API_KEY=... \
  PYTHONPATH=engine python -m governance eval --llm --repeat 5 --out eval-llm-1.5.0.json
```

**Quando é obrigatório:** sempre que mudar algo que define o comportamento do revisor:
modelo, prompt, `bundle.yaml`, ou uma política com `enforcement.llm` (nova ou alterada).
Também antes de pedir `llm.blocking: true` para uma política.

**O que acontece:**

1. Roda **todos** os casos, inclusive os de `requires_llm`, com o revisor generativo e o
   Jev de verdade (modelos fixados no `bundle.yaml`).
2. Repete cada caso N vezes (`--repeat`), porque modelo não é determinístico.
3. Soma TP/FP/FN/TN de todas as repetições por política e calcula recall e precisão.
4. Mede a **estabilidade** de cada caso: a fração de repetições em que acertou tudo. Caso
   abaixo de 1,00 aparece em "Casos instáveis".
5. Qualquer erro de execução (provedor fora do ar, entrada grande demais) reprova.
6. Opcional: `--min-recall 0.9 --min-precision 0.9` viram critério de reprovação para as
   políticas com LLM.

Resultado do bundle 1.5.0: 79 casos × 5 repetições, recall e precisão 1,00 em todas as
políticas, nenhum caso instável.

**Com o Jev, olhe a folga, não só o acerto.** O log mostra a probabilidade de cada linha
julgada (`Jev RES-IDEMP-001 TransferenciaClient.java:12 p=0.95`). No bundle 1.5.0, os
positivos da RES-IDEMP-001 ficaram entre 0,94 e 0,95 e os negativos entre 0,08 e 0,19,
longe do limiar de 0,5. Um positivo em 0,55 acerta hoje e erra amanhã: melhore a
`question` (diga melhor o que conta e o que não conta) antes de publicar.

**Outros usos:**

- `--model <id>` avalia um modelo candidato sem alterar o bundle: é assim que se decide
  uma troca de modelo.
- O resultado (`eval-llm-*.json`) **não é versionado** neste repositório (`.gitignore`);
  os números vão na mensagem do commit da release. No CI, o job `eval-llm` (disparado à
  mão em Actions → ci → Run workflow, com `llm_repeat`) guarda o JSON como artefato.
- Para `llm.blocking: true`, o `eval_evidence` da política aponta esse resultado.

### Quando o eval reprova

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Caso positivo com FN no determinístico | regex não casa, `strip` removeu demais, caminho fora do `scope` | teste a regex na linha exata; confira o glob |
| Caso negativo com FP no determinístico | regex larga demais | estreite o padrão, use `exclude` ou `validator`; acrescente o quase-positivo como caso |
| Caso de outra política quebrou | sua mudança afetou outra regra (escopo compartilhado, motor) | corrija antes de seguir: regressão é o que o eval existe para pegar |
| Caso instável com LLM | pergunta ou critério ambíguo | reescreva o `question`/`criteria`; ajuste o `threshold` só com base nas probabilidades |
| Erro de execução com LLM | chave ausente, provedor fora do ar, arquivo acima de `max_input_chars` | resolva e rode de novo; nada é truncado |

---

## Etapa 9. Versões, PR e CI no repositório central

**Versões** (ADR-GOV-007):

| O que mudou | Suba |
|---|---|
| Qualquer coisa que vá para uma release | versão do motor em `engine/governance/__init__.py` e `pyproject.toml`, igual à tag |
| Política, prompt, modelo ou orçamento | também `bundle_version` em `engine/bundle.yaml` |
| Comportamento da política | o `version` da própria política |
| Formato do `result.json` | `schema_version` e o gate de deploy (`evidence.py`) |

**PR.** O `.github/CODEOWNERS` deste repositório exige a aprovação do dono de cada área
(`/policies/FIN-*`, `/classification/`, `/engine/`...). A política não entra sem quem
responde por ela.

**CI** ([.github/workflows/ci.yml](../.github/workflows/ci.yml)), em todo PR e push na
`main`:

1. `pytest`
2. `validate`
3. `export --check`
4. `eval` determinístico

O job `eval-llm` roda sob demanda (etapa 8). Nenhuma mudança entra com o CI vermelho.

---

## Etapa 10. Release e smoke test

1. **Merge na `main` e tag nova:** `git tag v1.10.0 && git push origin v1.10.0`. **Tag
   publicada nunca se move**: ela é o que os repositórios-alvo executam e o que está
   registrado nas evidências já assinadas. Defeito se corrige com uma versão nova.
2. **Smoke test no repositório piloto:** um PR trocando a tag no `governance.yml` e no
   `deploy.yml` (no `uses:` e em `governance_ref`). O próprio PR roda na versão nova e
   tem de ser avaliado sem erro; depois do merge, o gate de deploy tem de liberar.
3. Só então a versão é anunciada aos outros repositórios (com organização, é uma
   mudança no ruleset).

O smoke test existe porque um problema pode aparecer só quando o motor é baixado por
outro repositório: foi o caso das tags v1.4.0–v1.7.0, que passavam em todos os testes
locais.

---

## Etapa 11. A regra em produção: warn, medição e promoção

1. **Em `warn`, a regra aparece no PR sem bloquear.** O desenvolvedor vê o achado no
   comentário e na linha do código (Code Scanning), com a correção.
2. **Falso positivo é medido.** Se o achado estiver errado, o desenvolvedor dispensa o
   alerta em Security → Code scanning com o motivo **"False positive"**. Isso não
   desbloqueia nada; entra na medição.
3. **O painel de conformidade** (toda segunda-feira, ADR-GOV-006) mostra, por política,
   achados, PRs afetados, falsos positivos e a **prontidão para `enforce`**.
4. **Promoção `warn` → `enforce`**, quando o painel mostrar "pronta para enforce":
   - casos positivo e negativo no eval;
   - pelo menos 14 dias em `warn`;
   - pelo menos 10 achados (amostra mínima);
   - falso positivo abaixo de 5%.

   A promoção é um PR mudando `mode: enforce` (e o `version` da política), citando os
   números do painel, com aviso prévio aos times afetados.
5. **Falso positivo alto** volta para a etapa 2: estreite a regra, acrescente o caso que
   falhou como negativo no eval, e o ciclo recomeça.
6. **Exceção pontual** é waiver (`waivers/*.yaml`: política, repositório, caminhos,
   justificativa, solicitante, aprovador diferente, validade de até 90 dias), nunca
   comentário no PR.
7. **Aposentar uma regra:** marque o ADR como substituído, remova a política e os casos
   no mesmo PR; o ID não é reaproveitado.

---

## Checklist

- [ ] A decisão é importante e observável no PR (etapa 0)
- [ ] Escolhi o mecanismo mais simples: regex > validador > caminho/companheiro/contrato > Jev > LLM generativo
- [ ] `adrs/ADR-<ÁREA>-<NNN>-*.md` com contexto, decisão, verificação com limites, consequências
- [ ] `policies/<ID>.yaml` com `mode: warn`, escopo estreito, `adr` apontando o ADR, `remediation` concreta
- [ ] `compliance` preenchido se `aws-security-agent` estiver em `targets`
- [ ] Casos de eval: um positivo que exercita todas as regras, um negativo quase-positivo
- [ ] Teste em `tests/` se a política tem várias regras ou se o motor mudou
- [ ] `export` rodado; nenhum arquivo gerado editado à mão
- [ ] `pytest`, `validate`, `export --check` e `eval` verdes
- [ ] Se tem LLM ou mexeu no bundle: `eval --llm --repeat 5` aprovado, folga do Jev conferida
- [ ] Versões: motor (tag), `bundle_version` (se mudou o bundle), `version` da política
- [ ] PR aprovado pelos CODEOWNERS; CI verde
- [ ] Tag nova, smoke test no repositório piloto, merge liberado pelo gate de deploy
- [ ] Acompanhar no painel; promover para `enforce` só com os números

## Problemas comuns

| Mensagem ou sintoma | Causa | Correção |
|---|---|---|
| `nome do arquivo deve ser X.yaml` | arquivo e `id` diferentes | renomeie o arquivo |
| `ADR ADR-XXX-NNN não encontrado` | ADR ausente ou com outro ID | crie o ADR com o nome `ADR-XXX-NNN-tema.md` |
| `regex inválida em pattern` | escape errado no YAML | aspas simples; `''` para aspa simples; `\\` dentro de `"..."` |
| `enforce exige casos positivo e negativo` | faltam casos | escreva os dois na etapa 3 |
| `llm.blocking=true exige llm.eval_evidence` | IA bloqueando sem medição | rode o eval com LLM e aponte o resultado |
| `classe X: ... só pode endurecer` | `raise_mode` igual ou abaixo do modo da política | remova a entrada ou suba o modo |
| `submódulo versionado por engano` | pasta com `.git` adicionada (ex.: worktrees) | `git rm --cached` e `.gitignore` |
| `desatualizado: .claude/rules/...` no CI | faltou rodar o export | `python -m governance export` e commit |
| Regra dispara em teste | `scope.exclude` sem `**/src/test/**` | acrescente o exclude |
| Regra não dispara num arquivo que deveria | glob não casa o caminho | `**/` no começo; lembre que `*` não atravessa `/` |
