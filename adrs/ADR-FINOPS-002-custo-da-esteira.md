# ADR-FINOPS-002: O custo da própria esteira é medido

## Status

Aceito — 2026-10-05.

## Contexto

A esteira usa IA paga em dois lugares: o revisor generativo (OpenRouter) e o julgamento
tipado (Jev, TypeSafe). Uma plataforma que cobra disciplina de custo dos outros precisa
saber quanto gasta. Os controles de gasto já existiam: uma chave por projeto com limite
mensal (ADR-GOV-001), teto de saída por chamada (`max_output_tokens`), IA só nas políticas
semânticas e nos arquivos do escopo (ADR-GOV-000), e classes de repositório sem IA
(ADR-GOV-009). Faltava **medir**: ninguém sabia quanto custava um PR.

## Decisão

1. **Cada chamada de IA registra o consumo que o provedor informa.** A OpenRouter devolve
   os tokens e o custo em dólar (`usage.cost`); o Jev devolve tokens de entrada e de
   saída, sem preço. Toda tentativa que gerou resposta conta, inclusive as repetidas por
   falha transitória: elas também custaram.
2. **O consumo vai para a evidência.** O `result.json` ganha `stats.ai_usage`:

   ```json
   {"calls": 6, "input_tokens": 9120, "output_tokens": 410, "cost_usd": 0.00213,
    "providers": [{"provider": "openrouter", "model": "google/gemini-3.5-flash-lite",
                   "calls": 3, "input_tokens": 5100, "output_tokens": 310,
                   "cost_usd": 0.00213},
                  {"provider": "typesafe", "model": "jev-1.13.0", "calls": 3,
                   "input_tokens": 4020, "output_tokens": 100, "cost_usd": null}]}
   ```

   É um campo novo dentro de `stats`, que o schema já define como objeto aberto: o
   formato do resultado não muda, `schema_version` continua 1.3 e o gate de deploy ignora o
   campo. `cost_usd` é nulo quando nenhum provedor informou preço.
3. **O painel mostra o custo.** Total na janela, média por PR avaliado e tokens por
   modelo ([ADR-GOV-006](ADR-GOV-006-painel-de-conformidade.md)).
4. **O eval também.** `eval --llm` imprime o consumo da própria execução, para a troca de
   um modelo ser decidida com o custo na mão.

## Limites

- O **Jev não informa preço**: o painel mostra os tokens dele, não dólares. O valor vem da
  fatura da TypeSafe. Se a API passar a informar o custo, o campo `cost_usd` já existe.
- Não há **limite por PR** que bloqueie ao ser excedido. O teto de hoje é o limite mensal
  da chave do projeto, que, ao acabar, devolve HTTP 402 e o PR é bloqueado com a causa
  explicada (fail-closed). Um limite por PR é uma evolução possível, depois de o painel
  mostrar a distribuição real.
- Só entra o que o motor viu. Não inclui o custo do runner do GitHub Actions nem o do
  gitleaks.

## Alternativas rejeitadas

| Alternativa | Motivo |
|---|---|
| Estimar o custo por tokens × tabela de preços do motor | O preço muda sem aviso e a tabela divergiria da fatura; usa-se o custo que o provedor informa |
| Ler a fatura pela API do provedor | Exige chave administrativa por provedor, fora do que o motor recebe |
| Medir só no eval | O custo que importa é o de produção, por PR |

## Consequências

- O custo da governança passa a ser conhecido por PR, por repositório e por modelo.
- Há uma base para decidir, com número, se vale ligar a IA numa classe de repositório ou
  trocar de modelo.
- O `result.json` assinado passa a registrar o consumo de cada avaliação.
