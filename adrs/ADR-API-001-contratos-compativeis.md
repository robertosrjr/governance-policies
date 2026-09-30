# ADR-API-001: Contratos de API e de eventos evoluem sem quebrar consumidores

## Status

Aceito — 2026-09-30.

## Contexto

Num banco, uma API ou um evento tem consumidores que o time dono não controla: canais,
parceiros, Open Finance, outros domínios. Remover um campo ou torná-lo obrigatório
quebra quem ainda não atualizou, e o erro aparece em produção, em outro time. Em
eventos é pior: produtor e consumidor sobem em momentos diferentes e mensagens antigas
continuam retidas no tópico.

## Decisão

- Contrato publicado só evolui de forma compatível: adicionar operação e campo opcional.
- Mudança que quebra é uma nova versão publicada ao lado da atual (`/v2`, novo tópico ou
  novo schema), com data de descontinuação combinada e registrada em ADR.
- A comparação é feita pelo próprio motor (`engine/governance/contracts.py`) entre a
  base e o PR, sem ferramenta externa, para ser reproduzível e testável no eval.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [API-CONTRACT-001](../policies/API-CONTRACT-001.yaml) | `contract` (openapi) | testes de contrato do consumidor (Pact) |
| [EVT-SCHEMA-001](../policies/EVT-SCHEMA-001.yaml) | `contract` (avro, compatibilidade FULL) | compatibilidade do Schema Registry no deploy |

O que é comparado: caminho/operação removidos, parâmetro e propriedade de corpo
obrigatórios novos, resposta 2xx removida, propriedade de resposta removida ou com tipo
alterado; no Avro, campo sem default adicionado ou removido, tipo sem promoção e símbolo
de enum removido. Fora disso (oneOf/allOf, headers, JSON Schema de eventos, Protobuf),
nada é comparado; se esses formatos forem adotados, o motor ganha comparadores ou a
regra passa a chamar uma ferramenta dedicada (oasdiff, buf).

## Exemplos

`eval/cases/api-contract-001-*.yaml` e `eval/cases/evt-schema-001-*.yaml`.

## Consequências

- Entram em `warn` (ADR-GOV-003). Contrato removido dispara sempre: remover é quebrar.
