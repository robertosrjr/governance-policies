# ADR-GOV-003: Operação do gate em instituição financeira

## Status

Proposto — 2026-09-29. Os itens marcados como pendência dependem de jurídico,
compliance e segurança da informação.

## Contexto

O gate nasceu numa PoC de conta pessoal. Em um banco ou corretora ele passa a ser um
controle de mudança auditável, sob LGPD, PCI DSS e a regulação do Banco Central (em
especial a Resolução CMN 4.893/2021, sobre segurança cibernética e contratação de
processamento e armazenamento de dados em nuvem). Quatro pontos mudam:

1. **Terceiros processando código.** O revisor LLM (OpenRouter) e o Jev (TypeSafe)
   recebem trechos do código do PR. Código de banco pode conter dado pessoal, dado de
   cartão e segredo de negócio. Ambos são serviços de processamento em nuvem e, fora
   do Brasil, também transferência internacional (LGPD Art. 33).
2. **Rollout sem parar a empresa.** Uma regra nova em `enforce` bloqueia centenas de
   repositórios no primeiro dia. Com falso positivo, o time contorna em vez de corrigir.
3. **Segregação de funções.** Quem escreve o código não aprova o próprio merge, e quem
   pede uma exceção não a aprova.
4. **Evidência com prazo regulatório.** O artefato do Actions expira em 90 dias; a
   evidência de controle de mudança precisa durar o prazo que auditoria e regulador
   exigirem.

## Decisão

### 1. Dados enviados a provedores de IA

- Antes de qualquer envio, o motor remove segredos e também CPF, CNPJ, número de cartão
  (validados por dígito verificador/Luhn) e e-mail literais (`engine/governance/redact.py`).
  O marcador indica o tipo do dado (`[CPF REMOVIDO]`) para que o revisor semântico ainda
  saiba que ali havia um dado pessoal.
- Só vão os arquivos no escopo de políticas semânticas (ADR-GOV-000).
- **Pendência bloqueante para produção:** contratar o LLM e o Jev como serviços de
  nuvem avaliados pela instituição: contrato com retenção zero e sem uso para
  treinamento, região definida (preferência por processamento no Brasil, ex.: Bedrock
  em sa-east-1 ou Vertex AI em southamerica-east1), avaliação do fornecedor e as
  comunicações exigidas pela Resolução CMN 4.893. Até lá, o gate roda com LLM só em
  repositórios piloto sem dado sensível. Os demais usam só a camada determinística, pela
  classificação de repositórios
  ([ADR-GOV-009](ADR-GOV-009-classificacao-de-repositorios.md)): classes `confidencial`,
  `restrito` e `nao-classificado` rodam sem IA, sem bloquear por isso.

### 2. Rollout das políticas

Toda política nova entra em `warn` (ADR-GOV-000). Ela sobe para `enforce` quando:

- tem casos positivo e negativo no eval (verificado por `validate`);
- rodou em `warn` por ao menos duas semanas nos repositórios piloto;
- a taxa de falso positivo medida (alertas dispensados como "false positive" no Code
  Scanning ÷ achados) ficou abaixo de 5%, com amostra de ao menos 10 achados; os números
  vêm do painel de conformidade
  ([ADR-GOV-006](ADR-GOV-006-painel-de-conformidade.md));
- os times afetados receberam aviso com data e guia de correção.

A promoção é um PR neste repositório, com os números no corpo do PR.

### 3. Segregação de funções

- Ruleset da organização (`templates/org-ruleset.json`): 1 aprovação, revisão de
  CODEOWNER, aprovação do último push e sem bypass. A PoC de conta pessoal usa 0
  aprovações e não vale como referência.
- Waivers: aprovador diferente do solicitante (validado pelo motor), validade máxima de
  90 dias, e `/waivers/` protegido por CODEOWNERS de AppSec.
- Alteração de política, prompt, modelo ou motor: CODEOWNER do time de plataforma e,
  para `enforce`, do dono da política.

### 4. Evidência

- `result.json` atestado (Sigstore) por commit, com versão do motor, do bundle, digest
  das políticas e modelos usados.
- Gate de deploy verificando a atestação e retenção em S3 com Object Lock:
  [ADR-GOV-005](ADR-GOV-005-gate-de-deploy-e-retencao-de-evidencia.md). **Pendência:**
  criar o bucket (templates/evidence-store) com o prazo de retenção definido por
  compliance e preencher `EVIDENCE_BUCKET` e `EVIDENCE_ROLE_ARN` no workflow central.

### 5. Pré-requisitos de plataforma das políticas

Algumas políticas só podem subir para `enforce` quando a plataforma oferecer a
correção que elas pedem: gateway corporativo de IA (AI-GW-001, ADR-AI-001), registry de
imagens aprovado (ADR-SUP-001) e lista de regiões aprovada por segurança da informação e
jurídico (DATA-RES-001, ADR-DATA-002). Bloquear sem oferecer o caminho correto só gera
waiver.

## Alternativas rejeitadas

| Alternativa | Motivo |
|---|---|
| Ligar todas as regras novas em `enforce` | Bloqueio em massa no primeiro dia e pressão por waiver genérico |
| Desligar o LLM quando o provedor falha | Contradiz o fail-closed (ADR-GOV-000). O modo sem LLM tem de ser decisão por classificação do repositório, não reação à falha |
| Enviar o código sem remover dado pessoal, confiando no contrato | Minimização (LGPD Art. 6º III) vale também para o processador |

## Consequências

- A remoção de dado pessoal muda a entrada do LLM e do Jev: o eval com LLM deve rodar de
  novo antes da release (bundle 1.3.0).
- Enquanto a pendência do provedor não fechar, o gate não deve ir para repositórios com
  dado de produção com o LLM ligado.
