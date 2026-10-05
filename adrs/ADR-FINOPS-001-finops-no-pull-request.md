# ADR-FINOPS-001: FinOps no Pull Request: o que o gate verifica e o que fica de fora

## Status

Aceito — 2026-10-05. A integração com uma ferramenta de estimativa de custo (seção
"Estimativa de custo") está desenhada e **não implementada**: depende do dono do
orçamento e da aprovação do serviço de preços.

## Contexto

Custo de nuvem costuma ser descoberto na fatura do mês seguinte, quando o recurso mal
dimensionado ou sem dono já gastou. O princípio de shift-left do FinOps é mover a trava
para o Pull Request, antes de o recurso existir. Anotações de estudo de FinOps em CI/CD
organizam isso em quatro camadas: estimativa de custo de infraestrutura, policy-as-code de
custo (tags, tipo de capacidade, `requests` e `limits`), contratos de resiliência para
rodar em capacidade barata (encerramento controlado) e canary com rollback por anomalia
de custo.

A plataforma já tem a base: fonte única de regras, rollout `audit` → `warn` → `enforce`
medido pelo painel, exceção com prazo e aprovador, gateway e modelo fixado para IA
(AI-GW-001, AI-MODEL-001), evidência assinada e gate de deploy. Faltava dizer, para cada
camada, **o que o gate de PR consegue verificar de forma confiável** e o que depende de
outra coisa, para não prometer o que o diff não mostra.

## Decisão

### Onde cada camada fica

| Camada | Onde | Por quê |
|---|---|---|
| 1. Estimativa de custo da mudança | Passo externo no workflow central, com o limite aplicado pelo motor (desenho abaixo, não implementado) | O cálculo é de uma ferramenta de preços, não do motor; o motor só aplica o limite |
| 2. Tags de custo, `requests`/`limits` | **Motor**, regras estruturais (este ADR) | Estão no arquivo e são verificáveis no diff |
| 2. Proibir capacidade On-Demand e forçar Spot | **Não vira regra geral** | Carga stateful e crítica (conta, pagamentos) não roda em Spot. Saber se a carga é stateless é um dado do cadastro do serviço, não do manifesto (ver "Evolução") |
| 2. Superdimensionamento frente ao histórico | Fora do gate | Depende de dado de produção; é recomendação de rightsizing, não de PR |
| 3. Teste de encerramento (SIGTERM) | Pré-requisito no PR (FINOPS-SHUTDOWN-001); o teste em si é do pipeline do time | É fitness function de execução: precisa do serviço rodando em staging (ADR-GOV-008) |
| 4. Canary com rollback por custo | Ferramenta de deploy e observabilidade, fora do gate | É feedback de produção (ADR-GOV-008) |

### As três regras (todas em `warn`)

- **FINOPS-TAG-001:** recurso Terraform de um dos tipos configurados sem as tags
  `CostCenter` e `Owner`.
- **FINOPS-K8S-001:** contêiner de Deployment, StatefulSet, DaemonSet, ReplicaSet, Job,
  CronJob ou Pod sem `resources.requests.cpu`, `requests.memory` e `limits.memory`.
- **FINOPS-SHUTDOWN-001:** `server.shutdown: immediate` em configuração Spring de produção.

### Decisões de desenho

1. **Severidade `MAJOR`.** Só `CRITICAL` bloqueia, então estas regras alertam mesmo em
   `enforce`. Custo é importante, mas errar uma tag não deve parar um deploy de
   emergência. A trava definitiva de tag é a política de tags e as políticas de controle
   de serviço da conta de nuvem, que valem para quem não usa a esteira; esta regra avisa
   antes. Quem responde pelo FinOps pode subir a severidade por PR, com os números do
   painel (ADR-FINOPS-002 e ADR-GOV-006).
2. **Parâmetros na política, não no motor.** As tags exigidas, os tipos de recurso e as
   quantidades de `requests`/`limits` são `params` da regra (`type: structured`). Quem é
   dono do orçamento muda a regra por PR, sem tocar em código. O mesmo vale para qualquer
   limite de custo: o "+15% ou +US$ 200 por mês" de um exemplo é parâmetro, não constante.
3. **Só se afirma o que dá para afirmar.** Tag vinda de variável, módulo ou `for_each`
   não é afirmada; módulo filho (diretório sem `provider`) herda do módulo raiz e não é
   apontado; só entra o recurso ou contêiner que o PR criou ou alterou. Falso positivo
   ensina o time a ignorar a regra, e o painel mede isso.
4. **O módulo inteiro como contexto.** O `default_tags` do provider quase sempre está em
   outro arquivo do mesmo diretório. Para tags herdadas não virarem alerta falso, o motor
   lê os demais `.tf` do diretório que o PR tocou (status `context`): não são achado, não
   selecionam política e não contam como arquivo alterado.
5. **Limite de CPU não é exigido.** `limits.cpu` estrangula o contêiner mesmo com o nó
   ocioso; o `requests.cpu` já garante a reserva. É decisão técnica explícita e ajustável:
   basta acrescentar `cpu` em `params.limits`.
6. **Leitor de HCL próprio.** Uma biblioteca nova entraria no lock com hash por causa de
   uma regra. O leitor (`engine/governance/hcl.py`) cobre blocos, atributos, comentários,
   strings com interpolação e heredoc, e declara onde não sabe (variáveis, módulos,
   funções além de `merge` e `tomap`).

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [FINOPS-TAG-001](../policies/FINOPS-TAG-001.yaml) | `structured` / `terraform_tags`: tags do recurso + `default_tags` do provider do mesmo diretório, com `locals` e `merge` resolvidos | Política de tags e SCP na conta de nuvem; relatório de custo por tag |
| [FINOPS-K8S-001](../policies/FINOPS-K8S-001.yaml) | `structured` / `kubernetes_resources`: lê o manifesto YAML | LimitRange e ResourceQuota no namespace; admission controller no cluster |
| [FINOPS-SHUTDOWN-001](../policies/FINOPS-SHUTDOWN-001.yaml) | regex na configuração Spring | Teste de SIGTERM no staging |

### Limites conhecidos

- **Tags:** nome exato (`CostCenter` não casa com `costcenter`). `default_tags` só do mesmo
  diretório. A lista de tipos de recurso é um parâmetro e cobre AWS; outros provedores
  usam `params.attribute` (por exemplo `labels`), sem herança de tags de provider.
- **Kubernetes:** manifesto Helm (`{{ }}`) não é lido; renderize com `helm template`.
  Patches do Kustomize não são aplicados: uma base sem `resources` e um patch que as
  acrescenta geram alerta (peça waiver ou versione o manifesto renderizado). Perfil
  padrão por LimitRange ou VPA cobre a ausência e também pede waiver.
- **Desligamento:** só a configuração explícita de encerramento imediato. A ausência da
  configuração depende do padrão da versão do Spring Boot e não aparece no diff; o
  comportamento real é um teste de execução.

### Estimativa de custo (desenho, não implementado)

Uma ferramenta como o Infracost lê o Terraform e calcula a diferença mensal entre a base
e o PR, sem credencial da nuvem. O desenho: um passo no workflow central, com versão e
hash fixados como o gitleaks, produz o resultado em `out/`; uma política (`FINOPS-COST-001`)
define o limite (`max_monthly_increase_usd`, `max_percent`) e o motor gera o achado.
Antes de implementar é preciso: (a) o dono do orçamento definir os limites por
componente; (b) aprovar o envio dos metadados dos recursos à API de preços, com a mesma
análise do ADR-GOV-003 (ou usar uma API de preços própria); (c) aceitar que o cálculo é a
preço de tabela, sem desconto de compromisso, e que custo por uso exige um arquivo de
uso. Sem isso, o número seria um alerta sem dono.

### Evolução

Quando `WorkloadType` (Stateless ou Stateful) for tag obrigatória, uma regra poderá
cruzar a tag com o tipo de capacidade e pedir Spot só para cargas stateless, em `warn`.

## Alternativas rejeitadas

| Alternativa | Motivo |
|---|---|
| Resolver tags com o JSON de `terraform plan` | Exige credencial da nuvem e acesso ao state no CI de todo repositório; o motor lê só o diff, como dado |
| Biblioteca de HCL | Dependência nova no lock com hash; o leitor mínimo atende e declara onde não sabe |
| Exigir as tags em qualquer recurso | Tipos que não aceitam tag gerariam alerta falso; os tipos são parâmetro |
| Bloquear (`enforce` com `CRITICAL`) desde o início | Uma tag errada não justifica parar o deploy; a trava definitiva está na conta de nuvem |
| Regra geral "On-Demand proibido" | Quebraria carga stateful crítica; depende de dado que o manifesto não traz |

## Exemplos

`eval/cases/finops-tag-001-*.yaml`, `eval/cases/finops-k8s-001-*.yaml` e
`eval/cases/finops-shutdown-001-*.yaml`. Os casos de tag usam `context_files` para o
provider que o PR não alterou.

## Consequências

- Entram em `warn` (ADR-GOV-003), com falso positivo medido pelo painel.
- O motor ganha o tipo de regra `structured`, reutilizável para outras verificações que
  dependem do bloco inteiro.
- A PoC não tem Terraform nem Kubernetes: a validação de ponta a ponta exige um diretório
  `infra/` no repositório piloto; até lá, os casos de eval e os testes são a prova.
