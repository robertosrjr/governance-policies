# ADR-GOV-004: Decisão estrutural chega com o seu ADR

## Status

Aceito — 2026-09-30.

## Contexto

As regras deste repositório verificam decisões que já foram tomadas. Falta o momento
em que uma decisão nova entra: uma dependência, um módulo, um banco ou um broker novo
aparecem num PR sem que ninguém registre por quê, quais alternativas foram descartadas
e quais consequências foram aceitas. Meses depois, a decisão existe só no código, e o
ADR, quando é escrito, é reconstrução.

## Decisão

O PR que introduz uma decisão estrutural traz o ADR no mesmo PR (novo ou atualizado),
em `adrs/`, `docs/adr/` ou `docs/architecture/decisions/`. São decisões estruturais
reconhecidas pelo motor:

- dependência nova (artefato Maven ou Gradle que não existia na base);
- módulo novo (`<module>` no Maven, `include` no Gradle);
- datastore ou broker novo no compose (Postgres, Oracle, Redis, Kafka, RabbitMQ...).

Trocar a versão de uma dependência existente não é decisão nova e não dispara.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [GOV-ADR-001](../policies/GOV-ADR-001.yaml) | `requires_companion`: gatilho novo (ausente na base) sem arquivo de ADR alterado no PR | revisão de arquitetura |

Limites: o motor verifica que um ADR mudou, não que ele trata daquela decisão. Datastore
provisionado só em Terraform ou Helm não está no gatilho.

## Exemplos

`eval/cases/gov-adr-001-*.yaml`.

## Consequências

- Entra em `warn`: o objetivo é criar o hábito antes de bloquear.
- O motor ganhou o tipo de regra `requires_companion`, reutilizável para outros pares
  (ex.: migração exige teste de repositório).
