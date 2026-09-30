# ADR-GOV-009: Classificação de repositórios decide IA e rigor das regras

## Status

Aceito — 2026-09-30. As classes e a lista de repositórios são mantidas por segurança da
informação; a classificação de dados da empresa, quando existir, substitui esta lista.

## Contexto

Duas pendências do ADR-GOV-003 travavam o rollout numa instituição financeira:

1. **Provedor de IA sem contrato.** Até o contrato (retenção zero, sem treino, região
   definida, CMN 4.893, LGPD Art. 33), o código de repositórios com dado pessoal ou de
   cartão não deve sair para o provedor. Mas o gate era fail-closed: sem chave, todo PR
   com Java ficava bloqueado. A única saída era não ligar o gate nesses repositórios,
   justamente os de maior risco.
2. **Mesmo rigor para tudo.** Um repositório do ambiente de cartão (PCI DSS) e uma
   ferramenta interna tinham as mesmas regras e os mesmos modos. Promover SEC-PAN-001
   para `enforce` em todos, ao mesmo tempo, seria o bloqueio em massa que o
   ADR-GOV-003 quer evitar.

## Decisão

Cada repositório-alvo tem uma **classe**, definida em `classification/repositories.yaml`
no repositório central. O repositório-alvo não consegue se declarar numa classe mais
branda, pelo mesmo princípio de separar quem governa de quem é governado
(ADR-GOV-000).

| Classe | IA | Endurece | Uso |
|---|---|---|---|
| `interno` | Sim | — | Sem dado pessoal nem de cartão |
| `confidencial` | Não, até o contrato do provedor | — | Trata dado pessoal (LGPD) |
| `restrito` | Não | SEC-PAN-001, LGPD-DATA-001, SEC-CRYPTO-001 → `enforce` | Ambiente de cartão (PCI) ou dado sensível |
| `nao-classificado` | Não | — | Padrão para repositório fora da lista |

Regras:

- **IA desligada por classe é decisão, não falha.** As políticas semânticas não rodam, o
  PR não é bloqueado por isso, e o relatório e a evidência registram a classe e o que
  não foi avaliado. Falha do provedor numa classe com IA continua bloqueando
  (fail-closed).
- **A classe só endurece.** `raise_mode` sobe o modo (`audit` < `warn` < `enforce`) e
  nunca afrouxa; tentar afrouxar invalida o bundle. Subir para `enforce` exige casos
  positivo e negativo no eval, como qualquer política (`validate` verifica).
- **Na dúvida, sem IA.** Repositório que não está na lista recebe `nao-classificado`, e o
  relatório avisa. Código não sai para terceiros antes de alguém classificar o
  repositório.
- A evidência (`result.json`, formato 1.3) registra a classe, a origem (`listed` ou
  `default`), se a IA estava permitida e quais políticas a classe endureceu. O painel
  conta as avaliações por classe.

## Alternativas rejeitadas

| Alternativa | Motivo |
|---|---|
| O repositório-alvo declarar a própria classe (arquivo no repo ou variável) | O time escolheria a classe menos exigente; a classificação é de quem governa |
| Desligar o LLM quando a chave falta | Mistura decisão com falha: uma chave expirada viraria "sem IA" silenciosamente |
| Classe padrão `interno` para quem não está na lista | Mandaria código de repositório não avaliado para o provedor de IA |

## Consequências

- O gate pode entrar nos repositórios de cartão e de dado pessoal já, só com as regras
  determinísticas, sem esperar o contrato do provedor.
- As políticas de dado de cartão, dado pessoal e criptografia bloqueiam primeiro onde o
  risco é maior; nas outras classes continuam em `warn` até o painel justificar.
- Incluir um repositório na organização passa a exigir classificá-lo, senão ele roda sem IA.
- Quando o contrato do provedor sair, basta mudar `llm: true` em `confidencial`, por PR
  aprovado por segurança da informação.
