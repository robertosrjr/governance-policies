# ADR-QUAL-001: Regras objetivas de qualidade de código

## Status

Aceito — 2026-09-25.

## Contexto

O `code-quality-auditor` da PoC bloqueava por "violação de regra inviolável (critério
geral)", o que deixava a decisão de bloqueio inteira com o modelo.

## Decisão

Só quatro regras objetivas, em [QUAL-CODE-001](../policies/QUAL-CODE-001.yaml): sem
`return null` em método público, sem injeção por campo, sem `catch` genérico que engole a
exceção, sem retorno `Object` em API pública. Revisão por LLM em modo `warn`: aparece no
PR, não bloqueia. Julgamento de SOLID e Clean Code além disso fica com a revisão humana.

## Consequências

- Menos ruído e nenhum bloqueio de qualidade dependente de modelo.
- Se o eval mostrar precisão alta, as regras podem ganhar implementação determinística
  (PMD/Checkstyle) e passar a `enforce`.
