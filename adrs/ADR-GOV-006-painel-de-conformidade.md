# ADR-GOV-006: Painel de conformidade e medição de falso positivo

## Status

Aceito — 2026-09-30.

## Contexto

O ADR-GOV-003 definiu quando uma política sai de `warn` para `enforce`: casos no eval,
duas semanas em `warn` e falso positivo abaixo de 5%. Até aqui ninguém media nada disso,
então nenhuma das políticas em `warn` tinha como ser promovida, e a liderança não tinha
visão da postura de risco: quantos PRs bloqueados, por qual regra, quanto bloqueio foi
erro da própria esteira, quais exceções estão vencendo.

A parte difícil é o falso positivo: é preciso um sinal de "este achado estava errado"
que seja auditável, atribuído a uma pessoa e que não dependa de planilha paralela.

## Decisão

### Fonte dos dados

- **Achados, vereditos e erros:** o `result.json` da última avaliação de cada PR, lido
  dos artefatos `governance-<sha>` (janela de até 90 dias, a retenção do artefato). Para
  janelas maiores, a evidência do bucket imutável (ADR-GOV-005) é lida no modo offline
  (`--from-dir`).
- **Falso positivo:** alerta do Code Scanning da ferramenta `enterprise-governance`
  dispensado com o motivo nativo **"false positive"**. O GitHub registra quem dispensou,
  quando e o comentário. É feedback, não exceção: dispensar o alerta não muda o veredito
  nem desbloqueia nada (exceção continua sendo waiver).
- **Tempo no modo atual:** a data do primeiro commit do repositório central que
  introduziu a linha `mode:` atual da política.

### Métricas

Por política: achados, PRs afetados, bloqueios, falsos positivos, taxa de falso
positivo, tempo no modo atual e **prontidão para `enforce`**, que lista o que falta.
Critérios, com um acréscimo ao ADR-GOV-003: **amostra mínima de 10 achados**. Sem ela,
"0% de falso positivo" não quer dizer nada.

Geral: PRs avaliados, aprovados, bloqueados, **bloqueados só por erro de execução**
(provedor de IA indisponível, chave ausente), erros por tipo e waivers vencendo em 30
dias.

### Entrega

`python -m governance dashboard` gera `dashboard.json` (dados para outros painéis),
`dashboard.html` (autocontido) e `dashboard.md` (resumo). O workflow
`compliance-dashboard.yml` roda toda segunda-feira sobre `dashboard/repos.txt`, com um
token só de leitura (`DASHBOARD_TOKEN`), e publica o painel como artefato.

### Adendo — 2026-10-05: custo de IA

O painel passou a somar o consumo de IA registrado em `stats.ai_usage` de cada avaliação:
total na janela, média por PR e por modelo
([ADR-FINOPS-002](ADR-FINOPS-002-custo-da-esteira.md)).

## Alternativas rejeitadas

| Alternativa | Motivo |
|---|---|
| Comando no PR (`/governance falso-positivo`) | Comentário é editável e ruído no PR; o Code Scanning já tem o fluxo, com trilha |
| Contar waiver como falso positivo | Waiver também cobre violação real aceita como risco; misturaria as duas coisas |
| Banco de dados e serviço próprio de painel | Mais uma peça para operar; o JSON alimenta o painel corporativo que já existir |

## Consequências

- A promoção `warn` → `enforce` passa a ter número: o PR de promoção cita o painel.
- "Bloqueado só por erro" mede a confiabilidade da própria esteira, o custo do
  fail-closed para os times.
- O falso positivo depende de os times dispensarem o alerta com o motivo certo; a
  orientação vai no guia e no comentário do PR.
- **Pendência:** alimentar o painel corporativo (Power BI, Grafana) a partir do
  `dashboard.json` e ler o bucket de evidências quando a retenção estiver ligada.
