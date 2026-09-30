# ADR-GOV-005: Gate de deploy e retenção imutável da evidência

## Status

Aceito — 2026-09-30. A retenção fica desligada até o bucket existir (templates/evidence-store).

## Contexto

Desde o ADR-GOV-000 o `result.json` de cada PR é atestado (Sigstore), mas nada usava a
atestação: o check no PR impede o merge, e só. Para auditoria interna e regulador,
controle de mudança significa provar que **o que está em produção** passou pelo
controle, e guardar essa prova pelo prazo exigido. Dois problemas:

1. **Ninguém verifica a evidência no deploy.** Um push direto (bypass, conta de serviço)
   ou um deploy de branch chega à produção sem avaliação.
2. **A evidência expira.** O artefato do GitHub Actions dura 90 dias; o prazo de
   retenção de controle de mudança é de anos.

Um detalhe de desenho: a governança avalia o **último commit do PR**, mas o deploy é do
**commit de merge** no main, que tem outro SHA.

## Decisão

### Gate de deploy (`governance-deploy-gate.yml`)

O pipeline de deploy do repositório-alvo chama o workflow central antes de implantar
(`templates/target-repo/deploy.yml`). Ele:

1. acha o PR do commit implantado: o PR mergeado cujo `merge_commit_sha` é o commit, ou
   o PR cujo último commit é o próprio commit. Sem PR, bloqueia;
2. baixa o `result.json` da avaliação desse PR;
3. verifica a assinatura com `gh attestation verify --signer-workflow`: só vale evidência
   assinada pelo **workflow central**, e não por um job do repositório-alvo com o mesmo
   nome;
4. verifica o conteúdo (`python -m governance verify-evidence`): veredito APPROVED, sem
   erro nem violação bloqueante, mesmo repositório, mesmo commit e `governance_ref`
   presente. Qualquer dúvida bloqueia.

Para que o merge não traga código que não foi avaliado, o ruleset exige PR atualizado
com o main antes do merge (`strict_required_status_checks_policy`).

### Retenção imutável

Depois de atestar, o workflow do PR grava `result.json`, `report.md`, SARIF e o bundle
da atestação num bucket S3 com Object Lock em modo COMPLIANCE, criptografado com CMK,
em sa-east-1 (`templates/evidence-store`). O acesso é por OIDC, sem chave estática; o
papel só aceita o workflow central (claim `job_workflow_ref`) e só pode gravar. Cada
execução usa um prefixo próprio, então reexecuções não sobrescrevem nada.

Bucket e papel ficam fixos no workflow central, como o `GOVERNANCE_REPOSITORY`: o
repositório-alvo não pode redirecionar a própria evidência. Com a retenção configurada,
falha ao gravar bloqueia o PR (fail-closed); sem configuração, o passo avisa.

## Alternativas rejeitadas

| Alternativa | Motivo |
|---|---|
| Reavaliar o commit de merge no push para o main | Dobra o custo (LLM) e a avaliação chega depois do merge, quando não dá mais para bloquear |
| Confiar no check verde do PR no momento do deploy | O status de check não é assinado nem diz quem o produziu |
| Guardar a evidência só como artefato ou release do GitHub | Expira ou pode ser apagada por um admin do repositório |
| Chave de acesso da AWS como segredo do repositório | Credencial estática que o repositório-alvo poderia usar para outra coisa |

## Consequências

- O deploy passa a depender da evidência. Commit sem PR (hotfix por push direto) não
  implanta: hotfix também vai por PR.
- O gate usa o artefato do PR, que expira em 90 dias. Implantar um commit mais antigo
  exige reavaliar o PR ou buscar a evidência no bucket (não automatizado ainda).
- **Pendência:** anexar o veredito e o link da evidência à requisição de mudança
  (ServiceNow/Jira) e ter um painel de conformidade que leia o bucket.
