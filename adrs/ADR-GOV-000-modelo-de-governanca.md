# ADR-GOV-000: Modelo da plataforma de governança e SecLLMOps

## Status

Aceito — 2026-09-25. Substitui o roteiro de `docs/Governança SecLLMOps Enterprise.docx`
como referência de arquitetura (o documento continua como histórico).

## Contexto

A PoC (`virtualthreads`, ADR-001 de lá) roda auditores LLM (Gemini) sobre o diff do PR e
bloqueia o merge em achados `CRITICAL`. A revisão da PoC e do roteiro mostrou:

1. **O PR controla o próprio revisor.** O prompt de sistema vem de `.claude/agents` e
   `.claude/skills` do checkout do PR, o orquestrador e o workflow também. Arquivos
   `.md` e `.py` ficam fora do filtro do diff, então essa mudança nem é revisada. O check
   `ai-review` exigido pode ser satisfeito por qualquer job com esse nome.
2. **Truncamento que deixa passar**: diff acima de 200 mil caracteres era cortado e
   revisado mesmo assim.
3. **A mesma regra existia em cinco lugares** (ADR, pack JSON, README, prompt, ArchUnit),
   com severidades e escopos diferentes.
4. **O revisor nunca foi avaliado**: validação com um PR e troca de modelo por variável
   de repositório, sem teste.
5. **Afirmações que desligavam achados** (`filtering.md` ContextHints) e lista de
   palavras proibidas tratada como controle `CRITICAL`.
6. O roteiro misturava dois produtos: IA governando código (esta plataforma) e
   segurança de aplicações de IA em produção (Macie, PrivateLink, guardrails de runtime).

## Decisão

Três planos, mais o ciclo de vida do próprio revisor.

```
 REPO CENTRAL (este repositório, protegido por CODEOWNERS)
 ├─ policies/*.yaml   1 arquivo = 1 regra (fonte única)
 ├─ waivers/*.yaml    exceções aprovadas
 └─ engine/           motor + prompts + bundle.yaml (modelo fixado)
          │  required workflow (ruleset da organização), ref fixada
          ▼
 EXECUÇÃO (a cada PR do repo-alvo)
 1. escolhe políticas: scope × arquivos alterados (sem RAG)
 2. T0 determinístico: regras do motor + gitleaks          → base, bloqueia
 3. remove segredos → T1 LLM (só políticas semânticas)     → só ACRESCENTA
 4. veredito = T0 ∪ T1 − waivers válidos
    entrada acima do orçamento, erro ou timeout            ⇒ bloqueia
          │
          ▼
 EVIDÊNCIA
 ├─ SARIF → Code Scanning (anotação na linha)
 ├─ result.json atestado (Sigstore) {commit, bundle, políticas, modelo, veredito}
 └─ gate de deploy verifica a atestação
```

### Princípios

1. **Quem governa fica separado de quem é governado.** Nada que o repo-alvo versiona é
   lido pelo motor como instrução: prompts, políticas, modelo e orquestrador vêm deste
   repositório, numa ref fixada pelo time de plataforma.
2. **Determinístico primeiro; LLM por último e só aditivo.** Se a regra pode ser escrita
   como regex/ArchUnit/gitleaks, o LLM não decide o bloqueio dela. O LLM só acrescenta
   achados. A severidade é a da política, não a do modelo. Achado de LLM só bloqueia com
   `llm.blocking: true`, que exige evidência de eval. Consequência: uma prompt injection
   bem-sucedida só consegue suprimir achados do LLM, nunca os da base determinística.
3. **Uma regra, uma fonte.** O ADR explica o porquê; o YAML define o quê. Do YAML saem o
   critério do prompt, o pack do AWS Security Agent e as regras do Claude Code
   (`python -m governance export`). Arquivos gerados não são editados à mão.
4. **O revisor é um modelo em produção.** `engine/bundle.yaml` (modelo, temperatura,
   orçamento) + prompts + políticas formam o bundle. Mudar qualquer um deles exige o eval
   (`eval/cases`) sem regressão.
5. **A decisão é evidência, não comentário.** O `result.json` é atestado por commit. Um
   comentário no PR é só a interface.
6. **Fail-closed.** Erro de API, cota, modelo inexistente, entrada acima do orçamento,
   waiver inválido no CI central: bloqueia. Nada é truncado.

### Modos de rollout

`audit` (só evidência) → `warn` (aparece no PR) → `enforce` (CRITICAL bloqueia). Toda
política nova entra em `audit` ou `warn`; `enforce` exige casos positivo e negativo no
eval (verificado por `python -m governance validate`).

### Exceções

Waivers em `waivers/*.yaml`: política, repositório, caminhos, justificativa, solicitante,
aprovador (diferente do solicitante), validade de até 90 dias e, opcionalmente, o commit.
O comando `/governance-bypass` por comentário foi rejeitado: comentário é editável, não
separa autor de aprovador e não se amarra ao SHA.

### Dados enviados ao provedor de LLM

- Segredos são removidos antes do envio (`engine/governance/redact.py`).
- Só vão os arquivos alterados que estão no escopo de políticas semânticas.
- Enviar código a um provedor fora do Brasil é transferência internacional (LGPD
  Art. 33). **Pendência de decisão:** contrato com retenção zero e sem uso para treino
  (ex.: Vertex AI com região definida, ou Bedrock), em vez da API pública com chave.

## Alternativas rejeitadas

| Alternativa | Motivo |
|---|---|
| RAG vetorial de ADRs para escolher regras | Falha silenciosa (ADR não recuperado = falso negativo não auditável). Seleção por `scope` é reproduzível. RAG só como contexto consultivo, se o corpus não couber no prompt |
| Reusable workflow chamado pelo repo-alvo | O PR pode remover ou editar a chamada. É preciso *required workflow* no ruleset da organização |
| Roteamento de modelo por pacote (`domain/` = modelo forte) | Vira forma de escapar: basta pôr a violação fora do pacote. Economia vem da seleção por escopo e de o LLM só rodar em políticas semânticas |
| Lista de palavras (`APPROVE PR`) como bloqueio CRITICAL | Contornável (idioma, Unicode, base64) e com falso positivo. Mantida como sinal `warn` (LLM-INJ-001) |
| As 5 camadas do roteiro (Macie, PrivateLink, guardrails de runtime) neste produto | Protegem aplicações de IA em produção, não um revisor de PR. Ficam para um produto separado, se houver apps LLM em produção |

## Consequências

- O repo-alvo perde a autonomia de ajustar os auditores; ajuste passa por PR aqui.
- Pipeline mais lento que a PoC na primeira execução (duas checkouts, gitleaks), mas o
  LLM roda menos: só nos arquivos no escopo de políticas semânticas.
- A troca de modelo passa a custar um eval completo.
- `enforce` com LLM só depois de métricas publicadas; até lá, casos semânticos de LGPD
  são consultivos. Os casos diretos continuam bloqueando pela regex.

## Pendências

- Contrato do provedor de LLM (LGPD Art. 33) e decisão entre Gemini, Bedrock e Vertex.
- Configurar o ruleset da organização (templates/org-ruleset.json) e o gate de deploy.
- Rodar `python -m governance eval --llm --repeat 5` e publicar as métricas antes de
  qualquer `llm.blocking: true`.
