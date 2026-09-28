# ADR-[ÁREA]-[NNN]: [Título da decisão]

<!--
O ADR explica o PORQUÊ. A regra verificável (escopo, padrões, severidade, modo) vive
somente em policies/<ID>.yaml (templates/policy-template.yaml). Não repita padrões nem
severidade aqui: duas fontes divergem com o tempo.
-->

## Status

Proposto | Aceito | Substituído por ADR-... — AAAA-MM-DD

## Contexto

[Problema técnico ou de negócio e a motivação.]

## Decisão

[A regra em linguagem natural.]

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [ÁREA-TEMA-001](../policies/ÁREA-TEMA-001.yaml) | [regex / path / LLM consultivo] | [ArchUnit, gitleaks, revisão humana] |

[Limites conhecidos de cada camada: o que escapa e quem cobre.]

## Exemplos

Casos executáveis em `eval/cases/<id>-*.yaml` (ao menos um positivo e um negativo para
políticas em `enforce`).

## Consequências

[Custos, falsos positivos esperados, impacto em times.]
