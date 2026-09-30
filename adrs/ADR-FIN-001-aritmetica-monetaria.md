# ADR-FIN-001: Aritmética monetária exata e arredondamento explícito

## Status

Aceito — 2026-09-29.

## Contexto

Em instituição financeira, o erro de centavo não é cosmético: vira diferença de
conciliação, cobrança indevida de juros e tarifa, divergência com a contabilidade e
questionamento de cliente e regulador. As causas recorrentes em Java/Kotlin são:

- `double`/`float` para valor: 0,1 não tem representação binária exata, e o erro se
  acumula em somatórios, juros compostos e rateios;
- `new BigDecimal(0.1)`: o BigDecimal herda o valor binário (0.1000000000000000055...);
- `divide(b)` sem escala e `RoundingMode`: com dízima lança `ArithmeticException` em
  produção; `setScale(n)` sem `RoundingMode` falha quando precisa arredondar. A regra de
  arredondamento (HALF_EVEN, HALF_UP, truncamento) é decisão de produto e contábil, não
  default de biblioteca.

## Decisão

Valor monetário usa `BigDecimal` (ou um value object `Dinheiro` no domínio, que também
carrega a moeda), criado a partir de `String` ou `BigDecimal.valueOf`. Toda divisão e
toda mudança de escala declaram o `RoundingMode`.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [FIN-MONEY-001](../policies/FIN-MONEY-001.yaml) | regex: declaração double/float com nome monetário, BigDecimal de literal double, divide/setScale sem RoundingMode | revisão humana; ArchUnit pode proibir `double` em `domain` por tipo de campo |

Limites: o motor reconhece valor monetário pelo nome (valor, saldo, preço, juros...).
`var x = calcula()` com tipo inferido, ou um campo chamado `v`, escapa. `divide` com um
argumento em `BigInteger` gera falso positivo. `BigDecimal.equals` (compara escala) fica
para revisão humana.

## Exemplos

`eval/cases/fin-money-001-*.yaml`.

## Consequências

- Entra em `warn` (ADR-GOV-003): o legado costuma ter `double` em DTO e relatório.
- Nomes como `taxaDeAcerto` geram falso positivo; o time renomeia ou pede waiver.
