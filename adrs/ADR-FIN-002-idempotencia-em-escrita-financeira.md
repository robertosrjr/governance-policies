# ADR-FIN-002: Escrita financeira é idempotente; nada de retry cego

## Status

Aceito — 2026-09-30.

## Contexto

Retry é o padrão de resiliência mais usado e o mais perigoso em movimentação de
dinheiro. Um timeout não diz se a outra ponta processou: se processou e o cliente
repete a chamada, o pagamento, a transferência ou o débito acontece duas vezes. O
problema não aparece em teste (o timeout é raro) e aparece em produção como reclamação
de cliente e ajuste manual.

## Decisão

Operação que grava ou movimenta dinheiro só tem retry automático se a mesma chave de
idempotência, gerada antes da primeira tentativa, for reenviada em cada tentativa e o
destino deduplicar por ela. Sem chave, não há retry: o erro é devolvido e a operação vai
para reconciliação.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [RES-IDEMP-001](../policies/RES-IDEMP-001.yaml) | regex marca linhas com retry; o Jev julga se é escrita financeira sem chave (ADR-GOV-002) | testes de replay e de concorrência; reconciliação |

Por que o Jev e não regex: "é escrita financeira" e "a chave é reenviada" dependem do
contexto do método e dos tipos citados, e não de uma palavra na linha. A regex de
candidatos limita o recall: retry que não usa as APIs reconhecidas não é julgado.

## Exemplos

`eval/cases/res-idemp-001-*.yaml` (exigem `--llm`).

## Consequências

- Consultivo (`blocking: false`) até o eval com LLM justificar bloqueio.
- Cada PR com retry em código de produção gera uma chamada ao Jev para as linhas marcadas.
