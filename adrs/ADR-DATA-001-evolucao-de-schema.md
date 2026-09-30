# ADR-DATA-001: Schema evolui por migrações imutáveis e expand/contract

## Status

Aceito — 2026-09-30.

## Contexto

Incidente de banco de dados em produção é dos mais caros numa instituição financeira:
indisponibilidade de conta, lançamento perdido, restore demorado. Duas causas se
repetem:

1. **Migração editada depois de aplicada.** O Flyway detecta o checksum diferente e a
   aplicação não sobe; ou o ambiente que ainda não rodou recebe um schema diferente do
   que já rodou.
2. **Mudança destrutiva no mesmo deploy da aplicação.** Em rolling update ou blue/green,
   a versão antiga continua rodando enquanto a migração remove a coluna que ela usa.
   DROP, RENAME, troca de tipo e TRUNCATE não têm volta sem restore.

## Decisão

- Migração versionada é imutável: correção é uma migração nova.
- Mudança destrutiva segue expand/contract em releases separadas: adicionar e escrever
  nos dois, migrar os dados e, só depois que nenhuma versão em produção usa o objeto,
  remover o antigo, com backup verificado.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [DATA-MIG-001](../policies/DATA-MIG-001.yaml) | `path_changed` só para migração modificada, renomeada ou removida | `flyway validate` no build |
| [DATA-MIG-002](../policies/DATA-MIG-002.yaml) | regex de DDL/DML destrutivo em migração | revisão do DBA; ambiente de homologação com dados |

Limites: Liquibase com changesets no mesmo arquivo não é coberto pela DATA-MIG-001 (o
arquivo muda a cada changeset novo). A DATA-MIG-002 aponta também o *contract*
legítimo; nesse caso o PR referencia o expand anterior e usa waiver ou segue em `warn`.

## Exemplos

`eval/cases/data-mig-001-*.yaml` e `eval/cases/data-mig-002-*.yaml`.

## Consequências

- Entram em `warn` (ADR-GOV-003). O contract vira um passo planejado, com registro.
