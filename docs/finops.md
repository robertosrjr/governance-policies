# FinOps na plataforma de governança

Este documento explica o que a esteira faz hoje por FinOps (gestão financeira de nuvem),
o que ela não faz e por quê, como ajustar as regras e como ler o custo da própria
esteira. Versão descrita: **v1.10.0**. As decisões estão no
[ADR-FINOPS-001](../adrs/ADR-FINOPS-001-finops-no-pull-request.md) (as regras de custo de
infraestrutura) e no [ADR-FINOPS-002](../adrs/ADR-FINOPS-002-custo-da-esteira.md) (o custo
de IA da esteira).

- [1. A ideia: shift-left](#1-a-ideia-shift-left)
- [2. O que existe hoje e o que não existe](#2-o-que-existe-hoje-e-o-que-não-existe)
- [3. As três regras de FinOps](#3-as-três-regras-de-finops)
- [4. Como ajustar uma regra](#4-como-ajustar-uma-regra)
- [5. Como testar](#5-como-testar)
- [6. O custo da própria esteira](#6-o-custo-da-própria-esteira)
- [7. Fora do gate, e a evolução](#7-fora-do-gate-e-a-evolução)
- [8. Problemas comuns](#8-problemas-comuns)

---

## 1. A ideia: shift-left

Custo de nuvem costuma ser descoberto na fatura do mês seguinte, quando o recurso mal
dimensionado ou sem dono já gastou. Shift-left é mover a conferência para o Pull Request,
**antes** de o recurso existir: o desenvolvedor vê o alerta no PR, com o arquivo, a linha
e a correção, e não um e-mail do FinOps semanas depois.

A plataforma já tinha o que sustenta isso: regras como código com um único dono por regra,
entrada gradual (`audit` → `warn` → `enforce`) medida pelo painel, exceção com prazo e
aprovador, evidência assinada e gate de deploy. O FinOps entra como mais um conjunto de
regras e como a medição do custo da própria esteira.

---

## 2. O que existe hoje e o que não existe

| Camada de FinOps | Situação | Onde |
|---|---|---|
| Tags de alocação de custo em recursos Terraform | **Implementada** (`warn`) | FINOPS-TAG-001 |
| `requests` e `limits` de CPU e memória em contêineres Kubernetes | **Implementada** (`warn`) | FINOPS-K8S-001 |
| Encerramento gracioso (pré-requisito de carga barata/Spot) | **Implementada** (`warn`), só a configuração explícita | FINOPS-SHUTDOWN-001 |
| Gateway de IA obrigatório e modelo fixado (controle de gasto com IA) | **Implementada** (`warn`) | AI-GW-001, AI-MODEL-001 |
| Custo da própria esteira | **Implementada** | `stats.ai_usage`, painel, eval |
| Estimativa de custo da mudança (Infracost) | **Só desenhada** | ADR-FINOPS-001 |
| Proibir On-Demand e forçar Spot | **Não vira regra geral** | ver [7](#7-fora-do-gate-e-a-evolução) |
| Teste de encerramento (SIGTERM) em staging | **Do pipeline do time**, não do gate | idem |
| Canary com rollback por custo | **Da ferramenta de deploy**, não do gate | idem |

O critério de corte é o mesmo de qualquer regra da plataforma: o gate de PR só verifica o
que dá para afirmar olhando os arquivos do PR. O que depende de uma ferramenta de preços,
de um serviço rodando ou de dados de produção fica de fora e está dito acima, em vez de
prometido.

---

## 3. As três regras de FinOps

Todas têm severidade `MAJOR` e modo `warn`: aparecem como alerta no comentário do PR e no
Code Scanning e **nunca bloqueiam**, mesmo se um dia forem para `enforce` (só `CRITICAL`
bloqueia). Errar uma tag não deve parar um deploy de emergência; a trava definitiva de tag
é a política de tags e as políticas de serviço da conta de nuvem.

Duas garantias valem para as regras estruturais, para o falso positivo não ensinar o time a
ignorá-las:

- **só se afirma o que dá para afirmar:** valor que vem de variável, de módulo ou de
  `for_each` não é afirmado;
- **só entra o que o PR alterou:** um recurso ou contêiner só é apontado se alguma linha dele
  foi adicionada.

### 3.1 FINOPS-TAG-001: tags de custo no Terraform

**O que exige:** todo recurso de um dos tipos configurados (instâncias, bancos, buckets,
filas, funções, clusters...) traz as tags `CostCenter` e `Owner`.

**Como o motor decide.** Lê o `.tf`, soma as tags do recurso com as `default_tags` do
`provider` do **mesmo diretório** e resolve `locals` e `merge`. Os outros `.tf` do diretório
que o PR tocou entram como contexto, porque o `provider` quase sempre está em outro arquivo.
Se faltar alguma tag depois dessa soma, há um achado.

Ruim (alerta nos dois recursos, que o PR criou):

```hcl
provider "aws" {
  region = "sa-east-1"
}

resource "aws_instance" "pedidos_api" {          # sem CostCenter, Owner
  ami           = "ami-0abcdef1234567890"
  instance_type = "m6i.large"
}

resource "aws_s3_bucket" "extratos" {            # sem Owner
  bucket = "extratos"
  tags = { CostCenter = "4410", Name = "extratos" }
}
```

Bom, com as tags herdadas do provider (uma vez, para todos os recursos):

```hcl
provider "aws" {
  region = "sa-east-1"

  default_tags {
    tags = {
      CostCenter = "4410"
      Owner      = "pagamentos"
    }
  }
}
```

Também vale `tags = { CostCenter = "...", Owner = "..." }` no recurso, ou
`tags = merge(local.common_tags, { Name = "x" })` com as tags em um `locals`.

**Quando o motor não afirma (e por quê):**

| Situação | Comportamento |
|---|---|
| `tags = var.tags`, `module.x.tags`, `for` | Não afirma: o valor vem de fora |
| Diretório sem `provider` (módulo filho) | Não afirma: o módulo raiz define as `default_tags` |
| Tipo de recurso fora da lista | Ignora |
| Recurso que o PR não alterou | Ignora |
| `provider` com alias (`provider = aws.west`) | Usa as `default_tags` do provider daquele alias |

**Limite:** o nome da tag é exato (`CostCenter` não casa com `costcenter`).

### 3.2 FINOPS-K8S-001: `requests` e `limits` no Kubernetes

**O que exige:** todo contêiner de Deployment, StatefulSet, DaemonSet, ReplicaSet, Job,
CronJob e Pod declara `resources.requests.cpu`, `resources.requests.memory` e
`resources.limits.memory`.

**Por quê:** sem `requests`, o escalonador não sabe quanto reservar e o time não sabe quanto
paga; sem `limits.memory`, um vazamento de memória derruba o nó dos vizinhos. O limite de
**CPU não é exigido**: ele estrangula o contêiner mesmo com o nó ocioso, e o `requests.cpu`
já garante a reserva.

Ruim:

```yaml
containers:
  - name: api
    image: registry.interno/pedidos:1.4.2
```

Bom:

```yaml
containers:
  - name: api
    image: registry.interno/pedidos:1.4.2
    resources:
      requests: { cpu: 250m, memory: 256Mi }
      limits:   { memory: 512Mi }
```

Use valores **medidos** (o histórico do serviço), não um palpite.

| Situação | Comportamento |
|---|---|
| Template Helm (`{{ }}`) | Não lido: não é YAML até ser renderizado. Renderize com `helm template` e versione o resultado, ou valide no cluster |
| Patch de Kustomize que acrescenta `resources` | Gera alerta (o motor não aplica patches): peça waiver ou versione o manifesto renderizado |
| LimitRange ou VPA no namespace | Cobre a ausência, mas o motor não vê: peça waiver |
| Init containers | Ignorados |
| YAML inválido que parece manifesto | Apontado como "manifesto ilegível" |

### 3.3 FINOPS-SHUTDOWN-001: encerramento gracioso

**O que exige:** que `server.shutdown` não seja `immediate` na configuração de produção do
Spring. Carga barata (Spot, escala para zero, deploys frequentes) só funciona se o serviço
termina o que está processando ao receber o SIGTERM.

**O que a regra não vê:** a ausência da configuração (depende do padrão da versão do Spring
Boot) e o comportamento real. Prová-lo é um teste de execução: enviar SIGTERM durante uma
requisição longa no staging e conferir que ela termina e que a operação é idempotente. Esse
teste é do pipeline do time, não do gate.

---

## 4. Como ajustar uma regra

Os parâmetros ficam no YAML da própria política, em `params`: quem responde pelo orçamento
muda a regra por PR, sem tocar em código. O `validate` recusa parâmetros inválidos (lista de
tags vazia, quantidade desconhecida).

| Quero… | Edito |
|---|---|
| Exigir outra tag (ex.: `Environment`) | `params.required_tags` em [FINOPS-TAG-001](../policies/FINOPS-TAG-001.yaml) |
| Cobrir outro tipo de recurso | `params.resource_types` (precisa ser um tipo que aceita tag) |
| Exigir limite de CPU | `params.limits: [cpu, memory]` em [FINOPS-K8S-001](../policies/FINOPS-K8S-001.yaml) |
| Cobrir outro provedor (labels do Google) | Outra regra `structured` com `params.attribute: labels` e os tipos do provedor |
| Mudar a severidade | `severity` na política; só `CRITICAL` bloqueia |

Cada mudança é um PR neste repositório: política (suba o `version`), casos de eval e, se
mudar o comportamento, o `bundle_version`. O passo a passo está no
[manual do ciclo de vida de uma regra](manual-ciclo-de-vida-de-uma-regra.md).

**Promover para `enforce`:** só vale a pena para uma regra que o painel mostrar como "pronta
para enforce" (14 dias em `warn`, ao menos 10 achados e falso positivo abaixo de 5%), e só
bloqueia se a severidade também for `CRITICAL` (decisão do dono do FinOps).

---

## 5. Como testar

**Localmente, em segundos** (a camada determinística, sem chave de IA), com o repositório
de aplicação ao lado:

```bash
PYTHONPATH=engine python -m governance review --repo ../../java/virtualthreads --base origin/main --no-llm
```

**Os casos de eval** de cada regra mostram o que dispara e o que não dispara:
`eval/cases/finops-tag-001-*.yaml`, `finops-k8s-001-*.yaml` e `finops-shutdown-001-*.yaml`.
O caso de tags usa `context_files` para o `providers.tf` que o PR não alterou.

**No GitHub** (como foi validado na PoC): um PR com um `infra/main.tf` com recursos sem tags,
um `infra/k8s/pedidos.yaml` com Deployment sem `resources` e um
`application-prod.yml` com `server.shutdown: immediate`. O resultado esperado é **aprovado
com 4 alertas** (nenhum bloqueia):

| Política | Achado |
|---|---|
| FINOPS-TAG-001 | `aws_instance.pedidos_api sem CostCenter, Owner` |
| FINOPS-TAG-001 | `aws_s3_bucket.extratos sem Owner` |
| FINOPS-K8S-001 | `Deployment 'pedidos', container 'api' sem resources.requests.cpu, resources.requests.memory, resources.limits.memory` |
| FINOPS-SHUTDOWN-001 | `Encerramento imediato (server.shutdown=immediate); use graceful.` |

Se o alerta estiver errado, dispense-o em **Security → Code scanning** com o motivo
**"False positive"**: entra na medição da regra e ajuda a decidir a promoção.

---

## 6. O custo da própria esteira

A esteira usa IA paga em dois lugares: o revisor generativo (OpenRouter) e o julgamento
tipado (Jev, TypeSafe). Uma plataforma que cobra disciplina de custo dos outros precisa saber
o que gasta ([ADR-FINOPS-002](../adrs/ADR-FINOPS-002-custo-da-esteira.md)).

### 6.1 Onde ver

| Onde | O que mostra |
|---|---|
| `result.json` de cada PR, em `stats.ai_usage` | Chamadas, tokens de entrada e saída, custo em US$ e uma linha por modelo |
| Painel de conformidade | Custo total na janela, média por PR e consumo por modelo |
| `eval --llm` | O consumo da própria execução, ao final da tabela |

Exemplo do `stats.ai_usage` de um PR real da PoC:

```json
{"calls": 1, "input_tokens": 1086, "output_tokens": 30, "cost_usd": 0.000401,
 "providers": [{"provider": "openrouter", "model": "google/gemini-3.5-flash-lite",
                "calls": 1, "input_tokens": 1086, "output_tokens": 30, "cost_usd": 0.000401}]}
```

### 6.2 Quanto custa

Valores medidos na v1.10.0:

| Medida | Valor |
|---|---|
| PR típico da PoC (uma chamada do revisor generativo) | cerca de US$ 0,0004 |
| Eval completo com IA (85 casos × 5 repetições) | US$ 0,216 na OpenRouter, mais 100 chamadas do Jev (75 mil tokens de entrada) |

O custo cresce com o número de arquivos no escopo das regras semânticas e com o tamanho
deles, não com o tamanho total do PR: as regras determinísticas (todas as de FinOps) não
custam nada.

### 6.3 O que controla o gasto

| Controle | Onde |
|---|---|
| Uma chave por projeto, com limite mensal | ADR-GOV-001; ao acabar, o provedor devolve HTTP 402 e o PR é bloqueado com a causa explicada |
| Teto de saída por chamada (`max_output_tokens`) | `engine/bundle.yaml` |
| IA só nas políticas semânticas e só nos arquivos do escopo | ADR-GOV-000 |
| Classes de repositório sem IA | ADR-GOV-009 |
| Modelo fixado por versão (sem troca silenciosa) | `engine/bundle.yaml` |

### 6.4 Limites da medição

- O **Jev não informa preço**: o painel mostra os tokens dele, não dólares. O valor vem da
  fatura da TypeSafe.
- Não há limite por PR que bloqueie ao ser excedido; o teto de hoje é o limite mensal da chave.
- Só entra o que o motor viu: o custo do runner do GitHub Actions não está incluído.

---

## 7. Fora do gate, e a evolução

| Item | Por que não é do gate | O que fazer |
|---|---|---|
| **Estimativa de custo da mudança** (Infracost) | O cálculo é de uma ferramenta de preços, não do motor | Desenho no ADR-FINOPS-001: um passo no workflow central e uma política com o limite (`FINOPS-COST-001`). Antes: o dono do orçamento definir os limites por componente e aprovar o envio de metadados dos recursos à API de preços |
| **Proibir On-Demand e forçar Spot** | Carga stateful crítica (conta, pagamentos) não roda em Spot, e saber se a carga é stateless é dado do cadastro, não do manifesto | Quando `WorkloadType` (Stateless ou Stateful) for tag obrigatória, uma regra poderá cruzá-la com o tipo de capacidade, em `warn` |
| **Teste de SIGTERM** | É teste de execução: precisa do serviço rodando em staging | Job no pipeline do time: SIGTERM durante uma requisição longa; ela termina e a operação é idempotente |
| **Canary com rollback por custo** | É feedback de produção | Ferramenta de deploy com observabilidade, comparando custo por transação entre a versão nova e a anterior |
| **Superdimensionamento frente ao histórico** | Depende de dado de produção | Recomendação de rightsizing do FinOps, não regra de PR |

A fronteira segue o ADR-GOV-008: fitness functions de execução ficam com a observabilidade
e com o deploy; o gate cobre o que aparece no PR.

---

## 8. Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| FINOPS-TAG-001 aponta recurso que herda as tags | O `provider` com `default_tags` está em outro diretório que o PR não tocou | Mantenha provider e recursos no mesmo diretório, ou peça waiver para o caminho |
| FINOPS-TAG-001 não aponta nada num módulo filho | Esperado: sem `provider` no diretório o motor não afirma | Garanta `default_tags` no módulo raiz e a política de tags na conta de nuvem |
| FINOPS-K8S-001 aponta contêiner que tem `resources` por Kustomize ou LimitRange | O motor lê só o manifesto, não os patches nem o namespace | Versione o manifesto renderizado ou peça waiver |
| FINOPS-K8S-001 não aponta um chart Helm | Template Helm não é lido | `helm template` e versione o resultado |
| "manifesto ilegível" | YAML inválido num arquivo que tem `kind:` | Corrija o YAML |
| O painel mostra "sem preço informado" no custo de IA | Só o Jev rodou, ou o provedor não informou custo | Esperado para o Jev: consulte a fatura da TypeSafe |
| Alerta correto, mas o time contesta | Falta o contexto de por que a regra existe | O ADR-FINOPS-001 explica o porquê e as alternativas descartadas |
