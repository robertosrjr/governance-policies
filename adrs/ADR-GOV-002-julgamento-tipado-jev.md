# ADR-GOV-002: Julgamento tipado (Jev) para políticas que não precisam gerar texto

## Status

Aceito — 2026-09-29. Piloto: [LGPD-LOG-001](../policies/LGPD-LOG-001.yaml). Complementa o
[ADR-GOV-000](ADR-GOV-000-modelo-de-governanca.md) (camada T1) e o
[ADR-GOV-001](ADR-GOV-001-provedor-llm-openrouter.md) (revisor generativo).

## Contexto

O revisor T1 é um LLM generativo: recebe o arquivo e devolve achados (política, linha,
mensagem). Nas políticas semânticas atuais, porém, a decisão é de sim ou não ("esta linha
leva dado pessoal ao log?", "este texto é instrução dirigida a uma IA?"). A mensagem
pode vir da própria política. Gerar texto para isso tem três custos:

- a saída não traz probabilidade, então não há limiar para calibrar e o caminho para
  `llm.blocking: true` fica difícil de justificar;
- o texto livre é a superfície que o código hostil tenta manipular (LLM-INJ-001);
- o custo cresce com a saída.

O Jev (TypeSafe System One) recebe um estado e perguntas tipadas e devolve
probabilidades, sem gerar texto.

## Decisão

1. **Motor por política.** `llm.engine: generative` (padrão) mantém o revisor da
   OpenRouter. `llm.engine: jev` usa o julgamento tipado, com três campos:
   - `candidates`: regex que marca as linhas **adicionadas** a julgar;
   - `question`: pergunta de sim ou não sobre uma linha (`{line}`, `{text}`);
   - `threshold`: probabilidade a partir da qual a linha vira achado.
2. **O código localiza e o Jev julga.** Linha que não casa com `candidates` não é
   julgada. Isso segue o princípio "determinístico primeiro": a regex é ampla (qualquer
   escrita em log, MDC, span, métrica ou exceção) e o Jev decide o caso.
3. **Estado:** o arquivo revisado, com as linhas numeradas, e os arquivos do PR que ele
   cita pelo nome (ex.: o record `Cliente` com CPF). Tudo redigido, como no revisor
   generativo. As perguntas de um arquivo vão numa só requisição
   (`POST https://api.typesafe.ai/v1/systemone`, Noul).
4. **Modelo fixo no bundle** (`jev.model: jev-1.13.0`, não `jev-latest`), pela mesma razão
   do ADR-GOV-001: o alias muda de modelo sem aviso.
5. **Mesmas garantias da camada T1:** achado do Jev é `source: llm`, consultivo até
   `llm.blocking: true` com `eval_evidence`; estado acima de `jev.max_input_chars` é erro
   (nada é truncado); resposta sem probabilidade para alguma pergunta é erro; qualquer
   falha do provedor bloqueia.
6. **Uma chave por projeto**, repassada como `TYPESAFE_API_KEY`, igual ao ADR-GOV-001.
7. O `result.json` registra o modelo do Jev em `bundle.jev` (schema 1.2).

## Verificação

| O quê | Como |
|---|---|
| Contrato da API e garantias (limiar, candidatos, estado, orçamento, fail-closed) | `tests/test_jev.py`, sem rede |
| Qualidade e limiar da LGPD-LOG-001 | `python -m governance eval --llm --repeat 5`, com os casos `eval/cases/lgpd-log-001-*`, inclusive negativos em que a regex marca a linha sem haver dado pessoal |
| `engine: jev` sem `candidates`, `question` ou `threshold`, ou sem a seção `jev` no bundle | `python -m governance validate` falha |

Eval do bundle 1.2.0 em 2026-09-29 (`--repeat 5`, 36 casos, `jev-1.13.0`): LGPD-LOG-001
com recall e precisão 1,00 (40 TP, 20 TN, 0 FP, 0 FN), igual ao revisor generativo no
bundle 1.1.0, agora com 12 casos em vez de 7. Probabilidades por linha, estáveis entre
as repetições (variação de até 0,13):

| Linhas | p |
|---|---|
| Positivas: toString de objeto com CPF, span, tag de métrica, log em várias linhas, getter, concatenação | 0,95 a 0,98 |
| Positiva: CPF na mensagem de exceção | 0,66 a 0,72 (a de menor folga) |
| Negativas: `maskEmail(email)` | 0,18 a 0,31 (a de menor folga) |
| Negativas: objeto sem dado pessoal, ids técnicos, valores mascarados, segredo (não é dado pessoal) | 0,02 a 0,14 |

Com `threshold: 0.5` há folga dos dois lados. As linhas de menor folga são as primeiras a
observar se casos reais pedirem recalibrar.

A decisão de migrar outra política depende do eval dela com o Jev não ficar abaixo do
revisor generativo.

## Consequências

- **Recall limitado pela regex:** o recall de uma política `jev` nunca passa do da regex
  `candidates`. Por isso ela é ampla, e a precisão fica a cargo do Jev.
- **Contexto limitado ao PR:** um tipo citado que não está no PR (ex.: `Cliente` em outro
  módulo) não entra no estado. Esse limite já existia no revisor generativo.
- **Probabilidades auditáveis:** o log do motor registra `p` de cada linha julgada, o que
  permite recalibrar `threshold` com casos reais.
- **Mais um provedor recebe código (redigido):** a TypeSafe entra na pendência de contrato
  (LGPD Art. 33) do ADR-GOV-000.
- **Candidatas a migrar depois:** LLM-INJ-001 (comentários e strings adicionados) e a
  parte de QUAL-CODE-001 que não vira regex (`catch` que engole a exceção).
