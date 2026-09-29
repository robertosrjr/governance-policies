# Manual de configuração, passo a passo

Este manual liga a governança em um repositório de aplicação, do zero até o primeiro PR
bloqueado. É o roteiro que usamos para ligar a PoC `robertosrjr/virtualthreads` no modo
**conta pessoal** (sem organização no GitHub), com os erros que encontramos no caminho.

Para entender o que cada peça faz, veja o [guia](guia.md). Este manual só diz **o que
fazer e em que ordem**.

- [Antes de começar](#antes-de-começar)
- [Parte 1. Repositório central](#parte-1-repositório-central)
- [Parte 2. Repositório da aplicação](#parte-2-repositório-da-aplicação)
- [Parte 3. Proteção do branch principal (ruleset)](#parte-3-proteção-do-branch-principal-ruleset)
- [Parte 4. Testar](#parte-4-testar)
- [Parte 5. Publicar uma versão nova](#parte-5-publicar-uma-versão-nova)
- [Erros que encontramos](#erros-que-encontramos)
- [Checklist final](#checklist-final)

---

## Antes de começar

| O que | Por quê |
|---|---|
| Conta no GitHub com os dois repositórios: o central (`governance-policies`) e o da aplicação | O workflow da aplicação chama o do central |
| Repositório da aplicação **público**, ou privado com plano **Pro** | Rulesets em repositório privado de conta pessoal gratuita não funcionam |
| Uma chave da OpenRouter só da aplicação (https://openrouter.ai/keys, com limite mensal) | A camada de IA é obrigatória no pipeline; sem a chave, PRs com código Java ficam bloqueados |
| Python 3.12+ e git na máquina | Para rodar o motor localmente |

Os nomes usados neste manual:

| Nome | Valor na PoC |
|---|---|
| Repositório central | `robertosrjr/governance-policies` |
| Repositório da aplicação | `robertosrjr/virtualthreads` |
| Versão do central em uso | `v1.1.0` |
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

Os quatro precisam terminar sem erro. O último deve dizer `Eval: APROVADO`.

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
git tag -a v1.1.0 -m "Descrição da versão"
git push origin v1.1.0
```

Confira: `git ls-remote --tags origin` deve listar `refs/tags/v1.1.0`.

> O `git push` normal **não** envia tags. Sem o `git push origin v1.1.0`, a tag existe só
> na sua máquina e o PR da aplicação falha.

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
    uses: robertosrjr/governance-policies/.github/workflows/governance-required.yml@v1.3.0
    with:
      governance_ref: v1.3.0      # tem que ser igual à tag do 'uses:'
    secrets:                      # só a chave do projeto (nunca 'secrets: inherit')
      OPENROUTER_API_KEY: ${{ secrets.VIRTUALTHREADS_OR_API_KEY }}
      TYPESAFE_API_KEY: ${{ secrets.VIRTUALTHREADS_JEV_API_KEY }}
```

As duas tags (`@v1.3.0` e `governance_ref: v1.3.0`) **têm que ser iguais**.

À esquerda do `:` fica o nome que o workflow central espera (`OPENROUTER_API_KEY`); à
direita, o nome do segredo na aplicação, que pode ser qualquer um. Tags anteriores à
`v1.2.0` não declaram segredos: com elas, use `secrets: inherit` e `GEMINI_API_KEY`.

### 2.3 Adicionar o CODEOWNERS

Copie [templates/target-repo/CODEOWNERS](../templates/target-repo/CODEOWNERS) para
`.github/CODEOWNERS` e troque `@org/plataforma` pelo seu usuário (`@robertosrjr`).

### 2.4 Conferir o ArchUnit

As regras de arquitetura também são verificadas por testes ArchUnit no build. Confira se
a aplicação tem os dois testes com estes nomes:

- `ArchitectureTest#domain_should_not_depend_on_frameworks`
- `ArchitectureTest#application_should_not_depend_on_infrastructure`

> Na PoC os testes existem, mas nenhum workflow roda `mvn verify` no PR. Hoje só a regex
> do motor protege o PR.

### 2.5 Testar localmente antes do push

A partir do repositório central:

```powershell
cd C:\Developer\Workspace\Governance\governance-policies
$env:PYTHONPATH = "engine"
python -m governance review --repo ..\..\java\virtualthreads --base origin/main --no-llm
```

Esperado neste PR: `Veredito: APPROVED`, com o alerta `GOV-SELF-001` (o PR mexe em
`.github/`, o que é esperado).

### 2.6 Enviar e abrir o PR

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git add .github
git commit -m "Governança central"
git push -u origin chore/governanca-central
```

Abra o PR no GitHub. **Não faça o merge ainda**: primeiro configure o segredo e o ruleset.

### 2.7 Criar o segredo

Na aplicação: *Settings → Secrets and variables → Actions → New repository secret*:

- Name: `VIRTUALTHREADS_OR_API_KEY` (o mesmo nome usado no `secrets:` do `governance.yml`)
- Secret: a chave da OpenRouter criada **só para esta aplicação**

E, desde a v1.3.0, a chave da TypeSafe (Jev), usada pelas políticas com `llm.engine: jev`
([ADR-GOV-002](../adrs/ADR-GOV-002-julgamento-tipado-jev.md)):

- Name: `VIRTUALTHREADS_JEV_API_KEY`
- Secret: a chave criada em https://console.typesafe.ai **só para esta aplicação**

Uma chave por aplicação: cada uma tem o próprio limite e o próprio gasto no painel do
provedor, e pode ser revogada sem afetar as outras
([ADR-GOV-001](../adrs/ADR-GOV-001-provedor-llm-openrouter.md)).

Se existir uma **variável** `GEMINI_MODEL` do pipeline antigo, ela pode ser apagada: o
modelo agora fica no `engine/bundle.yaml` do central.

Depois de criar o segredo, rode o check de novo no PR (*Re-run all jobs*).

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
     - marque **Require branches to be up to date before merging**
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

Com o check verde, faça o merge. A partir daqui, todo PR na `main` da aplicação passa
pela governança.

---

## Parte 4. Testar

Dá para testar de dois jeitos: **localmente**, em segundos e sem abrir PR, e **no GitHub**,
com um PR de verdade. Comece pelo local.

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
- A saída termina em `Veredito: APPROVED` ou `Veredito: BLOCKED`.
- O comentário que iria para o PR fica em `governance-out\report.md`, e a evidência em
  `governance-out\result.json`.

Cenários para testar. As saídas abaixo são reais, só sem a data e a hora de cada linha.

**Domínio dependendo de Spring** (em uma classe de `domain/`):

```java
import org.springframework.stereotype.Component;

@Component
public class Cliente {}
```
```
INFO      CRITICAL ARCH-HEX-001     src/main/java/com/x/domain/Cliente.java:2 (deterministic, bloqueia)
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

**Segredo em configuração** (em um `.properties`; a chave abaixo é o exemplo público da
documentação da AWS, não uma credencial real):

```properties
aws.access_key = "AKIAIOSFODNN7EXAMPLE"
```
```
INFO      CRITICAL SEC-SECRET-001   app.properties:1 (deterministic, bloqueia)
INFO    Veredito: BLOCKED. Bloqueado: 1 violação(ões) bloqueante(s).
```

**Só alerta, não bloqueia** (qualquer arquivo em `.github/`):

```
INFO      MAJOR    GOV-SELF-001     .github/workflows/x.yml:None (deterministic)
INFO    Veredito: APPROVED. Aprovado com 1 achado(s) não bloqueante(s).
```

**Revisor de IA sem chave** (rode **sem** `--no-llm` e sem `OPENROUTER_API_KEY`, com uma
classe Java alterada):

```
ERROR     Revisor de IA não configurado (sem OPENROUTER_API_KEY): LGPD-LOG-001, LLM-INJ-001, QUAL-CODE-001 não foram avaliadas. -> Crie o segredo OPENROUTER_API_KEY em Settings → Secrets and variables → Actions do repositório e rode de novo.
INFO    Veredito: BLOCKED. Bloqueado: 1 erro(s) de execução impedem um veredito confiável.
```

**Revisor de IA com chave inválida** (`$env:OPENROUTER_API_KEY = "chave-invalida"` e sem
`--no-llm`):

```
WARNING Tentativa 1/3 falhou: HTTP 401
ERROR     Revisor de IA (lgpd): a chave do provedor de LLM foi recusada (HTTP 401). -> Verifique o segredo OPENROUTER_API_KEY em Settings → Secrets and variables → Actions do repositório.
```

**Com a IA ligada** (`OPENROUTER_API_KEY` válida e sem `--no-llm`): os achados do LLM aparecem
com origem `llm` e nunca bloqueiam. Ex.: `logger.info("Cliente criado: {}", cliente)`
quando `Cliente` tem CPF, que a regex não pega.

Ao terminar, volte para a `main` e apague o branch de teste:

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git checkout main
git branch -D teste/local
```

### 4.2 Testar no GitHub: um PR que deve ser bloqueado

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git checkout main
git pull
git checkout -b teste/violacao-dominio
```

Em uma classe de domínio (na PoC,
`application/pedidos/src/main/java/com/robertosrjr/pedidos/domain/model/OrderItem.java`),
adicione:

```java
import org.springframework.stereotype.Component;

@Component
public record OrderItem(...)
```

```powershell
git add -A
git commit -m "teste: Spring no domínio (deve ser bloqueado)"
git push -u origin teste/violacao-dominio
```

Abra o PR. Esperado:

| Onde | Resultado |
|---|---|
| Check `governance / governance` | ❌ |
| Comentário do motor | `⛔ CRITICAL · ARCH-HEX-001 · OrderItem.java:6 · Domínio referencia Spring ou JPA (ADR-ARCH-001)` |
| Botão de merge | bloqueado |

### 4.3 Onde ver as mensagens no GitHub

Cada execução do check deixa a mesma informação em vários lugares:

| Onde | Como chegar | O que mostra |
|---|---|---|
| **Comentário no PR** | Aba *Conversation* do PR | O veredito, os achados (política, arquivo, linha) e, se houver, os erros com **O que fazer**. Um só comentário, atualizado a cada execução. |
| **Check** | Final da aba *Conversation*, ou aba *Checks* | `governance / governance` ✅ ou ❌. É o que o ruleset exige. |
| **Anotações da execução** | *Checks* → *governance* → *Details* | Os erros em destaque no topo da página, com a causa e o que fazer. |
| **Resumo da execução** | Na mesma página, seção *Summary* | O mesmo texto do comentário do PR. |
| **Linha do código** | Aba *Files changed* | O achado ao lado da linha que o causou (via Code Scanning). |
| **Code Scanning** | *Security → Code scanning* | Todos os achados (`enterprise-governance`) e segredos (`gitleaks`). |
| **Evidência** | *Actions* → execução → *Artifacts* → `governance-<sha>` | `result.json`, `report.md` e os SARIF. |

### 4.4 As mensagens de erro e o que fazer

Quando a revisão **não consegue terminar**, o PR fica bloqueado (fail-closed) e o
comentário mostra uma destas seções:

| Título no comentário | Mensagem | Causa | O que fazer |
|---|---|---|---|
| ⚠️ Revisor de IA indisponível | `…respondeu HTTP 503 (sobrecarga ou falha do provedor)` | O provedor do modelo está sobrecarregado. Não é problema no código. | Esperar alguns minutos e *Re-run all jobs*. |
| ⚠️ Revisor de IA indisponível | `…sem cota no provedor de LLM (HTTP 429)` | A cota do plano da chave acabou. | Esperar a cota renovar e *Re-run all jobs*. |
| ⚠️ Revisor de IA indisponível | `…sem créditos no provedor de LLM (HTTP 402)` | A chave da aplicação atingiu o limite de gasto na OpenRouter. | Aumentar o limite da chave ou recarregar créditos e *Re-run all jobs*. |
| ⚠️ Revisor de IA indisponível | `…sem resposta do provedor de LLM (TimeoutError)` | Timeout ou rede. | *Re-run all jobs*. |
| ❗ Erros de execução | `…a chave do provedor de LLM foi recusada (HTTP 401/403)` | Chave da OpenRouter inválida ou revogada. | Corrigir o segredo no repositório. |
| ❗ Erros de execução | `Revisor de IA não configurado (sem OPENROUTER_API_KEY)` | O segredo não existe ou não foi repassado no `secrets:` do `governance.yml`. | Criar o segredo (Parte 2.7) e conferir o repasse (Parte 2.2). |
| ❗ Erros de execução | `…recusou a requisição (HTTP 404); modelo ou parâmetro inválido no bundle` | Configuração central errada. | Avisar o time de plataforma. |
| ❗ Erros de execução | `…passa do limite do revisor de IA` | Arquivo grande demais para o LLM. Nada é truncado. | Se for gerado, pedir para tirar do escopo; se for código, dividir. |
| ❗ Erros de execução | `O gitleaks encontrou possível segredo em um dos commits do PR` | Credencial em algum commit, mesmo que apagada depois. | Revogar a credencial e ver o alerta em *Code scanning*. |
| ❗ Erro de configuração | `git diff … falhou` | O motor nem conseguiu avaliar (ex.: base do diff inexistente). | *Re-run all jobs*; se repetir, avisar a plataforma. |

Toda seção de erro diz também se **as regras que rodaram** encontraram violação. Assim dá
para saber se, fora o erro, o PR passaria.

Exemplo real do comentário com o Gemini fora do ar:

> ## 🛡️ Governança — ❌ Bloqueado
>
> Bloqueado: revisor de IA indisponível.
>
> ### ⚠️ Revisor de IA indisponível
>
> O PR fica bloqueado porque a revisão não pôde ser concluída (fail-closed).
>
> As regras que rodaram não encontraram violação bloqueante.
>
> - Revisor de IA (lgpd) indisponível: o provedor de LLM respondeu HTTP 503 (sobrecarga ou falha do provedor).
> - Revisor de IA (quality) indisponível: o provedor de LLM respondeu HTTP 503 (sobrecarga ou falha do provedor).
> - Revisor de IA (security) indisponível: o provedor de LLM respondeu HTTP 503 (sobrecarga ou falha do provedor).
>
> **O que fazer:** Não é problema no seu código. Aguarde alguns minutos e rode de novo (Re-run all jobs no check governance).

Para simular estes erros com segurança, use o teste local da seção 4.1 (sem chave ou com
chave inválida). Não apague o segredo do repositório para testar: isso bloquearia todos os
PRs abertos.

### 4.5 Limpar

Feche o PR **sem merge** e apague o branch:

```powershell
git checkout main
git branch -D teste/violacao-dominio
git push origin --delete teste/violacao-dominio
```

### 4.6 Evidências

Para guardar a prova de que funcionou:

- o comentário do motor no PR;
- em *Actions*, na execução do check, o artefato `governance-<sha>` com o `result.json`.
  Ele traz o status por ADR (ex.: `"ADR-ARCH-001": "FAIL"`), o commit e a tag usada.

---

## Parte 5. Publicar uma versão nova

Quando algo mudar no central (regra, motor, mensagens):

**No central**

```powershell
cd C:\Developer\Workspace\Governance\governance-policies
$env:PYTHONPATH = "engine"
python -m pytest
python -m governance validate
python -m governance export --check
python -m governance eval
git add <arquivos>
git commit -m "..."
git push
git tag -a v1.2.1 -m "..."
git push origin v1.2.1
```

- Nunca mova nem apague uma tag publicada.
- Mudou modelo, prompt ou `engine/bundle.yaml`? Suba `bundle_version` e rode antes
  `python -m governance eval --llm --repeat 5`.
- Atualize também a tag em `templates/target-repo/governance.yml`.

**Na aplicação** (por PR, porque a `main` está protegida)

```powershell
cd C:\Developer\Workspace\java\virtualthreads
git checkout main
git pull
git checkout -b chore/governanca-v1.2.1
```

Troque a tag nos **dois** lugares do `.github/workflows/governance.yml` e envie:

```powershell
git add .github/workflows/governance.yml
git commit -m "Governança v1.2.1"
git push -u origin chore/governanca-v1.2.1
```

O rodapé do comentário no PR mostra a versão do motor em uso (ex.: `motor 1.1.0`).

---

## Erros que encontramos

Tudo isto aconteceu ao configurar a PoC.

| Sintoma | Causa | Solução |
|---|---|---|
| Pasta `.github/` sumiu depois de mover o projeto de diretório | A cópia não levou a pasta oculta | Conferir `git status` depois de mover. Recuperamos de uma cópia antiga. |
| A execução aparece com o nome do arquivo (`.github/workflows/governance.yml`) e falha na hora, sem comentário | A tag referenciada não existia no GitHub | `git push origin <tag>`; depois feche e reabra o PR. |
| Todo PR ficaria bloqueado para sempre | O ruleset antigo exigia o check `ai-review`, do pipeline removido | Trocar o check exigido no ruleset **no mesmo dia** em que se troca o pipeline. |
| O check `governance / governance` não aparecia para escolher no ruleset | O GitHub só lista checks que já rodaram | Abrir o PR primeiro, ou configurar pela API. |
| O PR não rodou de novo depois de publicar a tag | O workflow só dispara ao abrir, dar push ou reabrir | Fechar e reabrir o PR, ou *Re-run all jobs*. |
| `governance.yml` não aparece na pasta local | A pasta está em outro branch (ex.: `main` antes do merge) | `git branch --show-current`; o arquivo está no branch do PR. |
| `No module named governance` | `PYTHONPATH` não definido na janela do PowerShell | `$env:PYTHONPATH = "engine"`. |
| `--llm exige OPENROUTER_API_KEY` com a chave nas variáveis do Windows | A janela foi aberta antes de a variável ser criada | Feche e abra o PowerShell (ou o VS Code). |
| Muitos `503 Service Unavailable` no eval com LLM | Sobrecarga do modelo no Google (não é cota; cota é 429) | Tentar em outro horário, com `--repeat 3`. No PR, o motor bloqueia e mostra "⚠️ Revisor de IA indisponível". |
| Comentário "✅ Aprovado" com o check vermelho | Na v1.0.0, o gitleaks não entrava no comentário | Corrigido na v1.1.0: o gitleaks faz parte do veredito. |

---

## Checklist final

**Central**
- [ ] `pytest`, `validate`, `export --check` e `eval` passando
- [ ] Repositório no GitHub (e acesso liberado em *Actions → Access*, se privado)
- [ ] Tag publicada com `git push origin <tag>`

**Aplicação**
- [ ] Pipeline de IA antigo removido
- [ ] `.github/workflows/governance.yml` com a mesma tag no `uses:` e em `governance_ref`
- [ ] `.github/CODEOWNERS` com o seu usuário
- [ ] Segredo com a chave da OpenRouter da aplicação, repassado como `OPENROUTER_API_KEY`
- [ ] Ruleset na `main`: PR obrigatório, 0 aprovações, check `governance / governance`,
      sem bypass, sem check antigo
- [ ] PR de configuração verde e mergeado

**Teste**
- [ ] PR com Spring no domínio bloqueado por ARCH-HEX-001
- [ ] PR de teste fechado sem merge e branch apagado
- [ ] Comentário e `result.json` guardados como evidência

**Limites conhecidos (modo conta pessoal)**
- Um PR pode editar ou apagar o `governance.yml` da aplicação. O check obrigatório e o
  CODEOWNERS reduzem, mas não eliminam, esse risco. Com uma organização, o workflow passa
  a ser imposto por um ruleset da org (veja o [guia, seção 5.2](guia.md#52-modo-organização-o-destino)).
