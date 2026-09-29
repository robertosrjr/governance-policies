# ADR-GOV-001: Provedor de LLM via OpenRouter, com modelo fixo e chave por projeto

## Status

Aceito — 2026-09-29. Complementa o [ADR-GOV-000](ADR-GOV-000-modelo-de-governanca.md)
(princípio 4 e "Dados enviados ao provedor de LLM").

## Contexto

Até o bundle 1.0.0 o revisor T1 chamava a API do Gemini direto (SDK `google-genai`,
segredo `GEMINI_API_KEY`). Trocar de modelo ou de fornecedor exigia código novo, e cada
repositório-alvo precisava de uma chave do Google.

A OpenRouter expõe muitos modelos pela mesma API (Chat Completions), com structured
outputs e controle de roteamento por requisição. Ela também oferece roteadores
(`openrouter/auto`, `typesafe/jev-router`) que escolhem o modelo a cada chamada: em teste,
o Jev Router mandou uma revisão de código para `deepseek/deepseek-v4.1-flash` na Together.

## Decisão

1. **Provedor `openrouter` no motor** (`OpenRouterProvider` em `engine/governance/llm.py`),
   selecionado por `llm.provider` no `bundle.yaml`. O `GeminiProvider` continua disponível
   para retorno rápido (`provider: gemini`).
2. **Modelo fixo.** O bundle 1.1.0 usa `google/gemini-3.5-flash-lite`, o mesmo modelo do
   1.0.0, agora pela OpenRouter. Roteadores não são aceitos no bundle: o eval valida um
   modelo e o PR seria revisado por outro. É a mesma razão pela qual o ADR-GOV-000 rejeitou
   roteamento de modelo por pacote.
3. **Toda requisição leva** `response_format` `json_schema` com `strict: true`,
   `provider.require_parameters: true` (só endpoints que honram o schema),
   `provider.data_collection: "deny"` (nenhum provedor que guarda ou treina com o prompt) e
   `max_tokens` (`llm.max_output_tokens`). Sem `max_tokens` a OpenRouter reserva a saída
   máxima do modelo e recusa chaves com limite de gasto (HTTP 402).
4. **Fail-closed preservado.** Erro HTTP, erro no corpo de uma resposta 200,
   `finish_reason` `error` ou `length` (resposta cortada) e JSON inválido viram erro de
   execução e bloqueiam. HTTP 402 (sem créditos) é "revisor indisponível", não culpa do PR.
5. **Uma chave por repositório-alvo, repassada explicitamente.** Cada projeto cria a sua
   chave na OpenRouter, com limite mensal próprio, e a entrega ao workflow central com
   `secrets: OPENROUTER_API_KEY: ${{ secrets.<NOME_NO_PROJETO> }}`. O
   `governance-required.yml` declara os segredos que aceita; `secrets: inherit` deixa de
   ser usado porque entregava todos os segredos do repo-alvo ao workflow central.

## Verificação

| O quê | Como |
|---|---|
| Contrato da API (URL, headers, corpo, erros) | `tests/test_openrouter.py`, sem rede |
| Qualidade do revisor com o modelo do bundle | `python -m governance eval --llm --repeat 5` (CI: `ci.yml`, entrada manual) |
| Provedor desconhecido no bundle | `python -m governance validate` falha |

Eval do bundle 1.1.0 em 2026-09-29 (`--repeat 5`, 31 casos): recall e precisão 1,00 em
todas as políticas, sem erro de execução, por cerca de US$ 0,14.

## Consequências

- Trocar de modelo passa a ser uma linha do `bundle.yaml` (e um eval completo, como antes).
- O conteúdo revisado (redigido) passa pela OpenRouter além do provedor do modelo. A
  pendência de contrato do ADR-GOV-000 (LGPD Art. 33) continua aberta e agora inclui a
  OpenRouter. `data_collection: "deny"` reduz, mas não substitui, um contrato com retenção
  zero.
- Cada projeto vê e limita o próprio gasto e pode revogar a sua chave sem afetar os
  outros. Em conta pessoal a chave fica copiada em cada repo-alvo; quem administra o repo
  pode usá-la em outro workflow. Com organização, preferir segredo de org restrito aos
  repositórios selecionados.
- Migração: o repo-alvo troca `secrets: inherit` pelo repasse explícito ao mudar o
  `uses:` para a tag que contém este ADR. Tags anteriores não declaram os segredos e
  recusam o repasse explícito.
- `GEMINI_API_KEY` pode ser removido dos repositórios depois que o bundle 1.1.0 estiver
  estável; `google-genai` sai do lock quando o `GeminiProvider` for removido.
