# ADR-ARCH-002: Relógio injetável e fuso explícito na regra de negócio

## Status

Aceito — 2026-09-30.

## Contexto

Regra financeira depende de data: corte de TED, D+1, vencimento de boleto, janela do
Pix noturno, dia útil, apuração de juros. Quando o domínio lê o relógio e o fuso da
máquina (`LocalDate.now()`, `new Date()`, `ZoneId.systemDefault()`):

- o resultado muda com o servidor (contêiner em UTC, estação em America/Sao_Paulo) e
  falha entre 21h e 0h de Brasília, quando as datas em UTC e em Brasília são diferentes;
- não dá para testar a virada do dia, fim de mês ou horário de corte;
- não dá para reproduzir numa auditoria o que o sistema decidiu em uma data passada.

## Decisão

Domínio e casos de uso recebem o tempo por dependência (`java.time.Clock` ou uma porta
`Relogio`) e usam fuso de negócio explícito, ou trabalham em UTC e convertem na borda.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [ARCH-TIME-001](../policies/ARCH-TIME-001.yaml) | regex de relógio/fuso implícito em `domain` e `application` | ArchUnit (proibir `now()` sem argumento); testes com `Clock.fixed` |

Limites: `infrastructure` fica fora (é onde o `Clock` real é criado). Bibliotecas que
leem o relógio internamente não aparecem no diff.

## Exemplos

`eval/cases/arch-time-001-*.yaml`.

## Consequências

- Entra em `warn`. O ajuste costuma ser mecânico: um `Clock` no construtor.
