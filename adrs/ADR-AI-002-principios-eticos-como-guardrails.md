# ADR-AI-002: Princípios éticos de IA como guardrails verificáveis

## Status

Aceito — 2026-09-30.

## Contexto

A skill `.claude/skills/global-ai-principles` reúne princípios globais de governança de
IA: bem-estar, autonomia, não discriminação, privacidade, auditabilidade, agência
humana e sustentabilidade. Como texto, eles têm o destino dos PDFs de arquitetura: todos
concordam, ninguém verifica. Numa instituição financeira, três deles têm consequência
legal direta quando a IA entra num produto:

- **Agência humana:** o titular pode pedir revisão de decisão tomada unicamente por
  tratamento automatizado (LGPD Art. 20), e alguém precisa responder pela decisão.
- **Não discriminação:** dado pessoal sensível (LGPD Art. 5º II) tem tratamento restrito
  (Art. 11), e usá-lo para decidir crédito, preço ou limite é discriminação.
- **Auditabilidade:** sem saber onde a IA é usada, não há como explicar uma decisão,
  responder ao titular ou avaliar risco.

## Decisão

Cada princípio vai para a camada que consegue verificá-lo:

| Princípio | Onde é verificado | Como |
|---|---|---|
| Agência humana | PR | [AI-HUMAN-001](../policies/AI-HUMAN-001.yaml): o Jev julga se a saída de IA decide sobre o cliente sem revisão humana |
| Não discriminação | PR | [AI-FAIR-001](../policies/AI-FAIR-001.yaml): o Jev julga se dado sensível entra em modelo, score ou regra de decisão |
| Auditabilidade e justificativa | PR | [AI-INV-001](../policies/AI-INV-001.yaml): uso novo de IA exige entrada no inventário de IA ou model card |
| Controle de dados, intimidade | PR + runtime | Gateway corporativo (AI-GW-001), remoção de dado pessoal, modelo fixado (AI-MODEL-001) |
| Não discriminação (efeito) | Antes do deploy do modelo | Teste de viés comparando resultados entre grupos; variável neutra pode ser proxy (ex.: CEP) |
| Bem-estar, autonomia, inclusão, due diligence | Processo | Comitê de IA e avaliação de impacto antes do caso de uso entrar no inventário |
| Eficiência ecológica | Métrica | Tokens e custo por requisição no gateway; escolha do menor modelo que passa no eval |

A skill continua como consultora para quem desenha um sistema de IA, antes do PR. As
políticas verificam a parte que aparece no código.

## Verificação

As três políticas entram em `warn`. AI-HUMAN-001 e AI-FAIR-001 usam o Jev: "decide sem
revisão humana" e "vira entrada de decisão" dependem do contexto do método, não de uma
palavra na linha. A regex de candidatos limita o recall (chamada de IA ou atributo
sensível que não casa não é julgado). AI-INV-001 é determinística (`requires_companion`).

Limites: AI-FAIR-001 não vê variáveis que servem de proxy (CEP, escola, nome); isso fica
com o teste de viés. AI-HUMAN-001 julga o arquivo; se a decisão acontece em outro
serviço que consome a saída, ela não aparece. AI-INV-001 verifica que o inventário mudou,
não que a entrada está correta.

## Exemplos

`eval/cases/ai-human-001-*.yaml`, `eval/cases/ai-fair-001-*.yaml` (exigem `--llm`) e
`eval/cases/ai-inv-001-*.yaml`.

## Consequências

- Casos de uso de IA passam a nascer registrados, e o inventário vira a base do
  comitê de IA e da resposta ao titular.
- Cada PR com chamada de IA ou atributo sensível gera chamadas ao Jev para as linhas
  marcadas.
