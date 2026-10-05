# Manual de configuração, passo a passo

Este manual liga a governança em um repositório de aplicação, do zero até o primeiro PR
bloqueado e o primeiro deploy liberado pelo gate. É o roteiro que usamos para ligar a PoC
`robertosrjr/virtualthreads` no modo **conta pessoal** (sem organização no GitHub), com os
erros que encontramos no caminho. Versão descrita: **v1.10.0**.

Para entender o que cada peça faz, veja o [guia](guia.md). Para criar ou mudar regras, o
[manual do ciclo de vida de uma regra](manual-ciclo-de-vida-de-uma-regra.md). Este manual
só diz **o que fazer e em que ordem**.

- [Antes de começar](#antes-de-começar)
- [Parte 1. Repositório central](#parte-1-repositório-central)
- [Parte 2. Repositório da aplicação](#parte-2-repositório-da-aplicação)
- [Parte 3. Proteção do branch principal (ruleset)](#parte-3-proteção-do-branch-principal-ruleset)
- [Parte 4. Testar](#parte-4-testar)
- [Parte 5. Painel de conformidade](#parte-5-painel-de-conformidade)
- [Parte 6. Publicar uma versão nova](#parte-6-publicar-uma-versão-nova)
- [Erros que encontramos](#erros-que-encontramos)
- [Checklist final](#checklist-final)

---

## Antes de começar

| O que | Por quê |
|---|---|
| Conta no GitHub com os dois repositórios: o central (`governance-policies`) e o da aplicação | O workflow da aplicação chama o do central |
| Repositório da aplicação **público**, ou privado com plano **Pro** | Rulesets em repositório privado de conta pessoal gratuita não funcionam |
| Uma chave da OpenRouter só da aplicação (https://openrouter.ai/keys, com limite mensal) | Revisor de IA generativo |
| Uma chave da TypeSafe só da aplicação (https://console.typesafe.ai) | Jev, usado pelas políticas com `llm.engine: jev` ([ADR-GOV-002](../adrs/ADR-GOV-002-julgamento-tipado-jev.md)) |
| Python 3.12+ e git na máquina | Para rodar o motor localmente |

Sem as duas chaves, num repositório classificado com IA, todo PR que mexe em Java fica
bloqueado por "revisor de IA não configurado" (fail-closed).

Os nomes usados neste manual:

| Nome | Valor na PoC |
|---|---|
| Repositório central | `robertosrjr/governance-policies` |
| Repositório da aplicação | `robertosrjr/virtualthreads` |
| Classe da aplicação | `interno` (IA permitida) |
| Versão do central em uso | `v1.10.0` |
| Check exigido no PR | `governance / governance` |

> Os comandos são para PowerShell no Windows. Em bash, troque `$env:PYTHONPATH = "engine"`
> por `export PYTHONPATH=engine`.

---

## Parte 1. Repositório central

### 1.1 Conferir que está tudo verde

```powershell
cd C:\Developer\Workspace\Governance\governance-policies
pip install --no-deps --require-hashes -r engine/requirements-dev.lock
$env:PYTHONPATH = "engine"
python -m pytest
python -m governance validate
python -m governance export --check
python -m governance eval
```

Os quatro precisam terminar sem erro. O `validate` diz `Bundle 1.6.0 válido: 37
políticas` e o último, `Eval: APROVADO`.

> **`No module named governance`**: o `PYTHONPATH` não está definido nesta janela do
> PowerShell. Defina com `$env:PYTHONPATH = "engine"`. Não coloque nas variáveis de ambiente
> do Windows: vale só para este repositório.

### 1.2 Publicar no GitHub

Crie o repositório **vazio** no GitHub (sem README, sem .gitignore) e envie:

```powershell
git push -u origin main
```

Se o repositório central for **privado**: em *Settings → Actions → General → Access*,
escolha "Accessible from repositories owned by the user". Sem isso, a aplicação não
consegue chamar o workflow.

### 1.3 Criar a tag

A aplicação não usa a `main` do central. Ela usa uma **tag**, que é uma versão fixa.

```powershell
git tag v1.10.0
git push origin v1.10.0
```

Confira: `git ls-remote --tags origin` deve listar `refs/tags/v1.10.0`.

> O `git push` normal **não** envia tags. Sem o `git push origin v1.10.0`, a tag existe só
> na sua máquina e o PR da aplicação falha.
>
> **Não use as tags v1.4.0 a v1.7.0**: estão defeituosas (Erros que encontramos).

### 1.4 Classificar a aplicação e incluí-la no painel

Ainda no central, por PR (o `.github/CODEOWNERS` protege esses arquivos):

1. Em [classification/repositories.yaml](../classification/repositories.yaml), acrescente a
   aplicação em `repositories` com a classe certa
   ([ADR-GOV-009](../adrs/ADR-GOV-009-classificacao-de-repositorios.md)):

   ```yaml
   repositories:
     robertosrjr/virtualthreads: interno
   ```

   | Classe | Quando usar | IA |
   |---|---|---|
   | `interno` | Sem dado pessoal nem de cartão | Sim |
   | `confidencial` | Trata dado pessoal | Não, até o contrato do provedor |
   | `restrito` | Ambiente de cartão (PCI) ou dado sensível; regras de cartão, dado pessoal e criptografia passam a bloquear | Não |

   Fora da lista, a aplicação roda como `nao-classificado`: só as regras determinísticas,
   com um aviso no comentário.
2. Em [dashboard/repos.txt](../dashboard/repos.txt), acrescente `robertosrjr/virtualthreads`.
3. Rode o `validate` e publique uma tag nova (Parte 6) para a classificação valer: a
   aplicação lê a classe da tag que ela usa.

---

## Parte 2. Repositório da aplicação

Faça tudo desta parte em **um branch e um PR**. O próprio PR já roda a governança nova.

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git checkout main
git pull
git checkout -b chore/governanca-central
```

### 2.1 Remover o pipeline de IA antigo

Se a aplicação tiver um workflow que roda IA com prompts ou scripts **do próprio
repositório**, remova. Na PoC eram:

```powershell
git rm .github/workflows/ai-governance.yml
git rm -r .github/scripts
```

Motivo: quem abre o PR podia alterar o script ou o prompt e fazer o revisor aprovar
qualquer coisa. O workflow central não lê nada do repositório avaliado.

### 2.2 Adicionar o workflow que chama o central

Copie [templates/target-repo/governance.yml](../templates/target-repo/governance.yml) para
`.github/workflows/governance.yml` da aplicação. A parte que importa:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  governance:
    uses: robertosrjr/governance-policies/.github/workflows/governance-required.yml@v1.10.0
    with:
      governance_ref: v1.10.0      # tem que ser igual à tag do 'uses:'
    secrets:                      # só as chaves do projeto (nunca 'secrets: inherit')
      OPENROUTER_API_KEY: ${{ secrets.VIRTUALTHREADS_OR_API_KEY }}
      TYPESAFE_API_KEY: ${{ secrets.VIRTUALTHREADS_JEV_API_KEY }}
```

As duas tags (`@v1.10.0` e `governance_ref: v1.10.0`) **têm que ser iguais**.

À esquerda do `:` fica o nome que o workflow central espera (`OPENROUTER_API_KEY`,
`TYPESAFE_API_KEY`); à direita, o nome do segredo na aplicação, que pode ser qualquer um.

### 2.3 Adicionar o pipeline de deploy com o gate

Copie [templates/target-repo/deploy.yml](../templates/target-repo/deploy.yml) para
`.github/workflows/deploy.yml` (ou acrescente o job `governance-gate` ao seu pipeline de
deploy e faça o deploy depender dele com `needs:`):

```yaml
jobs:
  governance-gate:
    uses: robertosrjr/governance-policies/.github/workflows/governance-deploy-gate.yml@v1.10.0
    with:
      governance_ref: v1.10.0

  deploy:
    needs: governance-gate
    # ... o seu deploy
```

Use a **mesma tag** do `governance.yml`. O gate só libera commit que veio de PR com
avaliação aprovada e assinada pelo workflow central
([ADR-GOV-005](../adrs/ADR-GOV-005-gate-de-deploy-e-retencao-de-evidencia.md)).

### 2.4 Adicionar o CODEOWNERS

Copie [templates/target-repo/CODEOWNERS](../templates/target-repo/CODEOWNERS) para
`.github/CODEOWNERS` e troque `@org/plataforma` pelo seu usuário (`@robertosrjr`).

### 2.5 Conferir o ArchUnit

As regras de arquitetura também são verificadas por testes ArchUnit no build. Confira se
a aplicação tem os dois testes com estes nomes:

- `ArchitectureTest#domain_should_not_depend_on_frameworks`
- `ArchitectureTest#application_should_not_depend_on_infrastructure`

> Na PoC os testes existem, mas nenhum workflow roda `mvn verify` no PR. Hoje só a regex
> do motor protege o PR.

### 2.6 Testar localmente antes do push

A partir do repositório central:

```powershell
cd C:\Developer\Workspace\Governance\governance-policies
$env:PYTHONPATH = "engine"
python -m governance review --repo ..\..\java\virtualthreads --base origin/main --no-llm
```

Esperado neste PR: `Veredito: APPROVED`, com o alerta `GOV-SELF-001` (o PR mexe em
`.github/`, o que é esperado).

### 2.7 Enviar e abrir o PR

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git add .github
git commit -m "Governança central e gate de deploy"
git push -u origin chore/governanca-central
```

Abra o PR no GitHub. **Não faça o merge ainda**: primeiro configure os segredos e o
ruleset.

### 2.8 Criar os segredos

Na aplicação: *Settings → Secrets and variables → Actions → New repository secret*, um
para cada chave, com os nomes usados no `secrets:` do `governance.yml`:

| Name | Secret |
|---|---|
| `VIRTUALTHREADS_OR_API_KEY` | a chave da OpenRouter criada **só para esta aplicação** |
| `VIRTUALTHREADS_JEV_API_KEY` | a chave da TypeSafe criada **só para esta aplicação** |

Uma chave por aplicação: cada uma tem o próprio limite e o próprio gasto no painel do
provedor, e pode ser revogada sem afetar as outras
([ADR-GOV-001](../adrs/ADR-GOV-001-provedor-llm-openrouter.md)).

O `GEMINI_API_KEY` e a variável `GEMINI_MODEL` do pipeline antigo podem ser apagados: o
modelo fica no `engine/bundle.yaml` do central.

Depois de criar os segredos, rode o check de novo no PR (*Re-run all jobs*).

---

## Parte 3. Proteção do branch principal (ruleset)

O ruleset é o que faz o check valer: sem ele, o PR pode ser mergeado mesmo com o check
vermelho.

> **Antes**: o GitHub só lista um check para escolher depois que ele rodou uma vez. Por
> isso o PR da Parte 2 precisa estar aberto e o check `governance / governance` já ter
> aparecido nele.

### 3.1 Pela interface do GitHub

Na aplicação: *Settings → Rules → Rulesets*.

Se já existir um ruleset na `main`, **edite-o** em vez de criar outro. Na PoC havia o
`protecao-main`, que exigia o check `ai-review` do pipeline antigo (veja
[Erros que encontramos](#erros-que-encontramos)).

1. **New ruleset → New branch ruleset** (ou abra o existente).
2. **Ruleset name**: `protecao-main`.
3. **Enforcement status**: `Active`.
4. **Bypass list**: vazia. Assim a regra vale até para o dono do repositório.
5. **Target branches → Add target → Include default branch**.
6. **Rules**:
   - **Restrict deletions**
   - **Block force pushes**
   - **Require a pull request before merging**
     - *Required approvals*: `0`
     - *Require review from Code Owners*: **desmarcado** (com um único dono, você não
       conseguiria aprovar os próprios PRs)
   - **Require status checks to pass**
     - **Add checks** → digite `governance` → escolha **`governance / governance`**
     - marque **Require branches to be up to date before merging**: sem isso, o commit
       de merge pode trazer código que o gate não avaliou, e o gate de deploy perde a
       garantia
     - remova qualquer check antigo que não exista mais (ex.: `ai-review`)
7. **Create** (ou **Save changes**).

### 3.2 Pela API (alternativa)

Útil quando o check ainda não aparece na interface, ou para repetir a configuração em
outro repositório. O `integration_id` 15368 é o GitHub Actions.

```json
{
  "name": "protecao-main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"},
    {"type": "pull_request", "parameters": {
      "required_approving_review_count": 0,
      "require_code_owner_review": false,
      "dismiss_stale_reviews_on_push": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false}},
    {"type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": true,
      "do_not_enforce_on_create": false,
      "required_status_checks": [{"context": "governance / governance", "integration_id": 15368}]}}
  ]
}
```

Com o [GitHub CLI](https://cli.github.com/), salvo como `ruleset.json`:

```bash
# criar
gh api -X POST repos/robertosrjr/virtualthreads/rulesets --input ruleset.json
# ou atualizar um existente (o id aparece em: gh api repos/robertosrjr/virtualthreads/rulesets)
gh api -X PUT repos/robertosrjr/virtualthreads/rulesets/<id> --input ruleset.json
```

### 3.3 Fazer o merge do PR da Parte 2

Com o check verde, faça o merge. O merge dispara o `deploy.yml`: o job
`governance-gate / verify` tem de terminar verde e o deploy, rodar. A partir daqui, todo
PR na `main` da aplicação passa pela governança, e todo deploy, pelo gate.

---

## Parte 4. Testar

Dá para testar de dois jeitos: **localmente**, em segundos e sem abrir PR, e **no GitHub**,
com PRs de verdade. Comece pelo local.

### 4.1 Testar localmente

O motor avalia o que um branch adicionou em relação a outro. Crie um branch de teste na
aplicação, faça a alteração, faça commit (não precisa de push) e rode o motor a partir do
repositório central:

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git checkout main
git checkout -b teste/local
# ... altere um arquivo (exemplos abaixo) ...
git add -A
git commit -m "teste local"

cd C:\Developer\Workspace\Governance\governance-policies
$env:PYTHONPATH = "engine"
python -m governance review --repo ..\..\java\virtualthreads --base main --no-llm
```

- `--base main` compara com a sua `main` local. Use `--base origin/main` para comparar com
  o GitHub.
- `--no-llm` roda só as regras determinísticas (as que bloqueiam), sem chave e sem custo.
- **A classe localmente:** o motor procura a classe pelo nome completo do repositório.
  No GitHub esse nome vem de `GITHUB_REPOSITORY`; na sua máquina ele não existe, e a
  aplicação roda como `nao-classificado` (sem IA). Para simular o PR de verdade, defina
  `$env:GITHUB_REPOSITORY = "robertosrjr/virtualthreads"` e as duas chaves.
- A saída termina em `Veredito: APPROVED` ou `Veredito: BLOCKED`.
- O comentário que iria para o PR fica em `governance-out\report.md`, e a evidência em
  `governance-out\result.json`.

Cenários para testar. As saídas abaixo são reais (v1.9.0), só sem a data e a hora de cada
linha.

**Domínio dependendo de Spring** (numa classe de `domain/`):

```java
import org.springframework.stereotype.Component;

@Component
public class Cliente {}
```
```
INFO    Classe do repositório: nao-classificado (default), revisão por IA desligada
INFO      CRITICAL ARCH-HEX-001     application/pedidos/src/main/java/com/robertosrjr/pedidos/domain/model/Cliente.java:3 (deterministic, bloqueia)
INFO    Veredito: BLOCKED. Bloqueado: 1 violação(ões) bloqueante(s).
```

**CPF em log** (em qualquer classe Java):

```java
logger.info("CPF do cliente: " + cpf);
```
```
INFO      CRITICAL LGPD-LOG-001     src/main/java/com/x/application/Criar.java:4 (deterministic, bloqueia)
INFO    Veredito: BLOCKED. Bloqueado: 1 violação(ões) bloqueante(s).
```

**Segredo em configuração** (a chave abaixo é o exemplo público da documentação da AWS,
não uma credencial real):

```properties
aws.access_key = "AKIAIOSFODNN7EXAMPLE"
```
```
INFO      CRITICAL SEC-SECRET-001   app.properties:1 (deterministic, bloqueia)
INFO    Veredito: BLOCKED. Bloqueado: 1 violação(ões) bloqueante(s).
```

**Só alerta, não bloqueia** (`double` para dinheiro e relógio da máquina no domínio, ou
qualquer arquivo em `.github/`): o veredito é `APPROVED` com achados não bloqueantes
(FIN-MONEY-001 e ARCH-TIME-001; GOV-SELF-001).

**Revisor de IA sem chave**, na classe da aplicação (sem `--no-llm`, com
`$env:GITHUB_REPOSITORY = "robertosrjr/virtualthreads"` e sem as chaves no ambiente):

```
INFO    Classe do repositório: interno (listed)
WARNING OPENROUTER_API_KEY ausente: camada LLM indisponível
WARNING TYPESAFE_API_KEY ausente: julgamento pelo Jev indisponível
ERROR     Revisor de IA não configurado (sem OPENROUTER_API_KEY): LLM-INJ-001, QUAL-CODE-001 não foram avaliadas. -> Crie o segredo OPENROUTER_API_KEY em Settings → Secrets and variables → Actions do repositório e rode de novo.
ERROR     Revisor de IA não configurado (sem TYPESAFE_API_KEY): AI-FAIR-001, AI-HUMAN-001, LGPD-LOG-001, RES-IDEMP-001 não foram avaliadas. -> Crie o segredo TYPESAFE_API_KEY em Settings → Secrets and variables → Actions do repositório e rode de novo.
INFO    Veredito: BLOCKED. Bloqueado: 1 violação(ões) bloqueante(s) e 2 erro(s) de execução impedem um veredito confiável.
```

É o fail-closed: numa classe com IA, sem a chave, o PR não passa. Numa classe sem IA
(como `nao-classificado`, no primeiro cenário), a falta de chave não é erro.

**Revisor de IA com chave inválida** (`$env:OPENROUTER_API_KEY = "chave-invalida"`):

```
WARNING Tentativa 1/3 falhou: HTTP 401
ERROR     Revisor de IA (lgpd): a chave do provedor de LLM foi recusada (HTTP 401). -> Verifique o segredo OPENROUTER_API_KEY em Settings → Secrets and variables → Actions do repositório.
```

**Com a IA ligada** (chaves válidas): os achados da IA aparecem com origem `llm` e nunca
bloqueiam. Ex.: `logger.info("Cliente criado: {}", cliente)` quando `Cliente` tem CPF, que
a regex não pega e o Jev pega.

Ao terminar, volte para a `main` e apague o branch de teste:

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git checkout main
git branch -D teste/local
```

### 4.2 Testar no GitHub: os três vereditos

Os três PRs que validaram a v1.9.0 na PoC, cada um com um único arquivo novo em
`application/pedidos/src/main/java/com/robertosrjr/pedidos/domain/model/`:

| Branch | Conteúdo | Resultado esperado |
|---|---|---|
| `teste/pr-limpo` | Um value object Java puro (`OrderNumber`) | ✅ Aprovado, sem achados |
| `teste/pr-com-alertas` | `private double valorDesconto` e `LocalDate.now()` (`DiscountPolicy`) | ✅ Aprovado com 2 alertas: FIN-MONEY-001 e ARCH-TIME-001 |
| `teste/pr-bloqueado` | `import org.springframework.stereotype.Component;` e `@Component` | ❌ Bloqueado pela ARCH-HEX-001; o botão de merge é recusado com "Required status check is failing" |

Para cada um:

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git checkout main
git pull
git checkout -b teste/pr-bloqueado
# ... crie o arquivo ...
git add -A
git commit -m "teste: Spring no domínio (deve ser bloqueado)"
git push -u origin teste/pr-bloqueado
```

Abra o PR e confira o comentário. Faça o merge só do limpo; feche os outros sem merge.

### 4.3 Testar o gate de deploy

| Cenário | Como | Resultado esperado |
|---|---|---|
| Deploy de PR aprovado | Merge do PR limpo | `governance-gate / verify` verde; o log mostra `Commit <merge> -> PR #N, avaliado em <sha>` e `Gate de deploy: LIBERADO`; o `deploy` roda |
| Push direto no `main` | `git push origin HEAD:main` a partir de um commit local | Recusado pelo ruleset: `GH013: Repository rule violations found` |
| Deploy de commit sem PR | Publique um branch com um commit (sem abrir PR) e rode *Actions → deploy → Run workflow* nesse branch | `governance-gate / verify` vermelho com "O commit ... não veio de um PR"; o `deploy` fica `skipped` |

### 4.4 Onde ver as mensagens no GitHub

| Onde | Como chegar | O que mostra |
|---|---|---|
| **Comentário no PR** | Aba *Conversation* do PR | O veredito, os achados (política, arquivo, linha) e, se houver, os erros com **O que fazer**. O rodapé traz a versão do motor, os modelos e a classe. Um só comentário, atualizado a cada execução. |
| **Check** | Final da aba *Conversation*, ou aba *Checks* | `governance / governance` ✅ ou ❌. É o que o ruleset exige. |
| **Anotações da execução** | *Checks* → *governance* → *Details* | Os erros em destaque no topo da página, com a causa e o que fazer. |
| **Resumo da execução** | Na mesma página, seção *Summary* | O mesmo texto do comentário do PR. |
| **Linha do código** | Aba *Files changed* | O achado ao lado da linha que o causou (via Code Scanning). |
| **Code Scanning** | *Security → Code scanning* | Todos os achados (`enterprise-governance`) e segredos (`gitleaks`). É onde se marca falso positivo. |
| **Evidência** | *Actions* → execução → *Artifacts* → `governance-<sha>` | `result.json`, `report.md` e os SARIF (90 dias). |
| **Assinatura** | *Actions* → *Attestations* | A atestação Sigstore de cada `result.json`. |
| **Gate de deploy** | *Actions* → execução do `deploy` → job `governance-gate / verify` | O PR encontrado, a verificação da assinatura e o veredito. |

### 4.5 As mensagens de erro e o que fazer

Quando a revisão **não consegue terminar**, o PR fica bloqueado (fail-closed) e o
comentário mostra uma destas seções:

| Título no comentário | Mensagem | Causa | O que fazer |
|---|---|---|---|
| ⚠️ Revisor de IA indisponível | `…respondeu HTTP 503 (sobrecarga ou falha do provedor)` | O provedor do modelo está sobrecarregado. Não é problema no código. | Esperar alguns minutos e *Re-run all jobs*. |
| ⚠️ Revisor de IA indisponível | `…sem cota no provedor de LLM (HTTP 429)` | A cota do plano da chave acabou. | Esperar a cota renovar e *Re-run all jobs*. |
| ⚠️ Revisor de IA indisponível | `…sem créditos no provedor de LLM (HTTP 402)` | A chave atingiu o limite de gasto. | Aumentar o limite ou recarregar créditos e *Re-run all jobs*. |
| ⚠️ Revisor de IA indisponível | `…sem resposta do provedor de LLM (TimeoutError)` | Timeout ou rede. | *Re-run all jobs*. |
| ❗ Erros de execução | `…a chave do provedor de LLM foi recusada (HTTP 401/403)` | Chave inválida ou revogada. | Corrigir o segredo no repositório. |
| ❗ Erros de execução | `Revisor de IA não configurado (sem OPENROUTER_API_KEY)` ou `(sem TYPESAFE_API_KEY)` | O segredo não existe ou não foi repassado no `secrets:` do `governance.yml`. | Criar o segredo (2.8) e conferir o repasse (2.2). |
| ❗ Erros de execução | `…recusou a requisição (HTTP 404); modelo ou parâmetro inválido no bundle` | Configuração central errada. | Avisar o time de plataforma. |
| ❗ Erros de execução | `…passa do limite do revisor de IA` | Arquivo grande demais para a IA. Nada é truncado. | Se for gerado, pedir para tirar do escopo; se for código, dividir. |
| ❗ Erros de execução | `O gitleaks encontrou possível segredo em um dos commits do PR` | Credencial em algum commit, mesmo que apagada depois. | Revogar a credencial e ver o alerta em *Code scanning*. |
| ❗ Erro de configuração | `git diff … falhou` | O motor nem conseguiu avaliar (ex.: base do diff inexistente). | *Re-run all jobs*; se repetir, avisar a plataforma. |

Toda seção de erro diz também se **as regras que rodaram** encontraram violação. Assim dá
para saber se, fora o erro, o PR passaria.

Aviso que **não** é erro: `Classe nao-classificado: revisão por IA desligada; a parte
semântica de ... não foi avaliada`. O repositório não está em
`classification/repositories.yaml` (1.4); o PR segue só com as regras determinísticas.

Para simular erros com segurança, use o teste local da seção 4.1. Não apague o segredo
do repositório para testar: isso bloquearia todos os PRs abertos.

### 4.6 Evidências

Para guardar a prova de que funcionou:

- o comentário do motor no PR;
- em *Actions*, na execução do check, o artefato `governance-<sha>` com o `result.json`.
  Ele traz o status por ADR (ex.: `"ADR-ARCH-001": "FAIL"`), o commit, a tag, a classe do
  repositório e os modelos usados;
- a atestação em *Actions → Attestations*;
- o log do `governance-gate / verify` no deploy.

A retenção é de 90 dias. Para guardar por anos, crie o bucket de evidências
([templates/evidence-store](../templates/evidence-store/main.tf)) e preencha
`EVIDENCE_BUCKET` e `EVIDENCE_ROLE_ARN` no workflow central.

---

## Parte 5. Painel de conformidade

O painel ([ADR-GOV-006](../adrs/ADR-GOV-006-painel-de-conformidade.md)) roda toda
segunda-feira no central e mostra, por política, achados, bloqueios, falsos positivos e
a prontidão para `enforce`.

### 5.1 Criar o token

1. *github.com → sua foto → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token*.
2. **Token name:** `governance-dashboard`; **Expiration:** 90 dias (ou o prazo que
   preferir).
3. **Repository access:** *Only select repositories* → os repositórios de
   `dashboard/repos.txt`.
4. **Repository permissions** (só leitura): **Actions**, **Code scanning alerts** e
   **Metadata** (automático).
5. **Generate token** e copie o valor (ele só aparece uma vez).

### 5.2 Cadastrar no central

*governance-policies → Settings → Secrets and variables → Actions → New repository
secret*: Name `DASHBOARD_TOKEN`, Secret = o token.

### 5.3 Rodar e ver

*governance-policies → Actions → compliance-dashboard → Run workflow*. Ao terminar, o
resumo aparece na página da execução, e o painel completo fica no artefato
`compliance-dashboard-<número>` (`dashboard.html`, `.json` e `.md`, por 90 dias).

Localmente: `python -m governance dashboard --repo robertosrjr/virtualthreads`, com um
`GITHUB_TOKEN` com as mesmas permissões no ambiente.

O token vence: quando isso acontecer, a execução semanal falha com HTTP 401 ou 403. Gere
outro e atualize o segredo.

---

## Parte 6. Publicar uma versão nova

Quando algo mudar no central (regra, motor, classificação, mensagens). O processo é o
do [ADR-GOV-007](../adrs/ADR-GOV-007-release-e-versionamento.md).

**No central**

```powershell
cd C:\Developer\Workspace\Governance\governance-policies
$env:PYTHONPATH = "engine"
# 1. suba a versão do motor em engine/governance/__init__.py e pyproject.toml (= tag nova)
python -m pytest
python -m governance validate
python -m governance export --check
python -m governance eval
git add <arquivos>
git commit -m "..."
git push
git tag v1.10.0
git push origin v1.10.0
```

- Nunca mova nem apague uma tag publicada: defeito se corrige com uma versão nova.
- Mudou modelo, prompt, `engine/bundle.yaml` ou uma política com IA? Suba `bundle_version`
  e rode antes `python -m governance eval --llm --repeat 5`.
- Atualize também a tag em `templates/target-repo/governance.yml` e
  `templates/target-repo/deploy.yml`.

**Na aplicação: o smoke test** (por PR, porque a `main` está protegida)

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git checkout main
git pull
git checkout -b chore/governance-v1.10.0
```

Troque a tag nos **dois** lugares do `.github/workflows/governance.yml` e do
`.github/workflows/deploy.yml` e envie:

```powershell
git add .github/workflows/governance.yml .github/workflows/deploy.yml
git commit -m "Governança v1.10.0"
git push -u origin chore/governance-v1.10.0
```

O próprio PR roda na versão nova: o rodapé do comentário mostra `motor 1.10.0`. Depois do
merge, o gate de deploy tem de liberar. Só então a versão está entregue.

---

## Erros que encontramos

Tudo isto aconteceu ao configurar e evoluir a PoC.

| Sintoma | Causa | Solução |
|---|---|---|
| Pasta `.github/` sumiu depois de mover o projeto de diretório | A cópia não levou a pasta oculta | Conferir `git status` depois de mover. Recuperamos de uma cópia antiga. |
| A execução aparece com o nome do arquivo (`.github/workflows/governance.yml`) e falha na hora, sem comentário | A tag referenciada não existia no GitHub | `git push origin <tag>`; depois feche e reabra o PR. |
| Falha em "Checkout do motor" com `No url found for submodule path '.claude/worktrees/...'`, sem comentário | As tags v1.4.0 a v1.7.0 versionaram worktrees de agentes como submódulos | Use a v1.7.1 ou posterior. O `validate` recusa submódulos desde então. |
| Todo PR com Java bloqueado com "Revisor de IA não configurado (sem TYPESAFE_API_KEY)" | O `governance.yml` repassava `VIRTUALTHREADS_JEV_API_KEY`, mas o segredo nunca tinha sido criado | Criar o segredo (2.8). |
| O `governance.yml` voltou para uma versão antiga depois de trocar de branch | O branch local foi criado de um ponto anterior ao PR que atualizou o arquivo | Criar os branches a partir de `origin/main` atualizado (`git pull` antes). |
| Todo PR ficaria bloqueado para sempre | O ruleset antigo exigia o check `ai-review`, do pipeline removido | Trocar o check exigido no ruleset **no mesmo dia** em que se troca o pipeline. |
| O check `governance / governance` não aparecia para escolher no ruleset | O GitHub só lista checks que já rodaram | Abrir o PR primeiro, ou configurar pela API. |
| O PR não rodou de novo depois de publicar a tag | O workflow só dispara ao abrir, dar push ou reabrir | Fechar e reabrir o PR, ou *Re-run all jobs*. |
| `governance.yml` não aparece na pasta local | A pasta está em outro branch (ex.: `main` antes do merge) | `git branch --show-current`; o arquivo está no branch do PR. |
| `No module named governance` | `PYTHONPATH` não definido na janela do PowerShell | `$env:PYTHONPATH = "engine"`. |
| `--llm exige OPENROUTER_API_KEY` com a chave nas variáveis do Windows | A janela foi aberta antes de a variável ser criada | Feche e abra o PowerShell (ou o VS Code). |
| Muitos `503 Service Unavailable` no eval com LLM | Sobrecarga do modelo no provedor (não é cota; cota é 429) | Tentar em outro horário. No PR, o motor bloqueia e mostra "⚠️ Revisor de IA indisponível". |
| Localmente a IA "não roda", mas no PR roda | Sem `GITHUB_REPOSITORY`, o repositório é `nao-classificado` | Defina `$env:GITHUB_REPOSITORY` (4.1). |

---

## Checklist final

**Central**
- [ ] `pytest`, `validate`, `export --check` e `eval` passando
- [ ] Repositório no GitHub (e acesso liberado em *Actions → Access*, se privado)
- [ ] Aplicação em `classification/repositories.yaml` e em `dashboard/repos.txt`
- [ ] Tag publicada com `git push origin <tag>` (v1.7.1 ou posterior)
- [ ] Segredo `DASHBOARD_TOKEN` e painel rodando

**Aplicação**
- [ ] Pipeline de IA antigo removido
- [ ] `.github/workflows/governance.yml` com a mesma tag no `uses:` e em `governance_ref`
- [ ] `.github/workflows/deploy.yml` com o gate de deploy, na mesma tag
- [ ] `.github/CODEOWNERS` com o seu usuário
- [ ] Segredos da OpenRouter e da TypeSafe da aplicação, repassados no `secrets:`
- [ ] Ruleset na `main`: PR obrigatório, 0 aprovações, check `governance / governance` com
      branch atualizado, sem bypass, sem check antigo
- [ ] PR de configuração verde e mergeado; gate de deploy verde no merge

**Teste**
- [ ] PR limpo aprovado; PR com alertas aprovado com os alertas; PR com Spring no domínio
      bloqueado e com merge recusado
- [ ] Push direto no `main` recusado; deploy de commit sem PR barrado
- [ ] PRs de teste fechados sem merge (exceto o limpo) e branches apagados
- [ ] Comentário, `result.json` e log do gate guardados como evidência

**Limites conhecidos (modo conta pessoal)**
- Um PR pode editar ou apagar o `governance.yml` da aplicação. O check obrigatório e o
  CODEOWNERS reduzem, mas não eliminam, esse risco. Com uma organização, o workflow passa
  a ser imposto por um ruleset da org (veja o [guia, seção 5.4](guia.md#54-modo-organização-o-destino)).
- A evidência dura 90 dias até o bucket imutável existir.
