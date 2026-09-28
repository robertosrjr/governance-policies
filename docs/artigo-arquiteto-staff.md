# O que acontece com a sua decisão de arquitetura depois que ela é aprovada?

Arquitetura é um conjunto de decisões ao longo do tempo. Registramos essas decisões em
ADRs, e ficamos bons nisso. O que continua raro é saber, seis meses depois, se elas ainda
valem no código.

Não é descuido de ninguém. A ADR registra a intenção, mas não tem ciclo de retorno. Ela
não está presente quando o código é escrito, nem quando é revisado, nem quando alguém
pergunta "estamos em conformidade?". A decisão vai se degradando em silêncio, um PR por
vez.

Esse problema sempre existiu. O que mudou é a escala: agentes de IA passaram a escrever
uma parte crescente do código, e o volume de mudanças cresce mais rápido que a
capacidade de revisão humana. Uma decisão que só existe num documento que ninguém abre
não orienta um agente.

Fiz uma prova de conceito para testar uma resposta: tornar executáveis as partes
verificáveis das ADRs, com cada regra apontando para a decisão que a justifica. Os
detalhes técnicos estão no GitHub (link no fim). Aqui quero falar das perguntas que isso
ajuda a responder, e das que não responde.

## As perguntas que um arquiteto precisa conseguir responder

**"Nossas decisões estão sendo seguidas?"**
Hoje a resposta costuma ser uma impressão. Quando a parte verificável de uma ADR roda em
todo Pull Request, a resposta passa a ser um registro: para cada commit, o status de cada
decisão (cumpre, alerta, viola), com a versão das regras usada. É uma evidência, não uma
opinião de revisor.

**"Qual versão da regra vale?"**
Na PoC, a mesma regra de arquitetura existia em cinco lugares: a ADR, o README, uma
ferramenta de segurança, o prompt de um revisor de IA e um teste. A ADR dizia uma
severidade; o pipeline cobrava outra. Ninguém sabia qual valia. Com uma fonte única, da
qual os outros formatos são gerados, essa divergência deixa de ser possível. Esse foi o
ganho que eu menos esperava e o que mais me convenceu.

**"Como escalo as decisões sem virar o gargalo da revisão?"**
Se toda verificação depende do arquiteto no PR, a arquitetura para de escalar junto com o
time. Quando as verificações objetivas acontecem sozinhas, com o motivo explicado no PR,
a revisão humana fica livre para o que só humanos fazem bem: discutir trade-offs.

**"Como oriento os agentes de IA que escrevem código?"**
A mesma fonte que bloqueia o PR é exportada como instrução para o assistente de código.
A decisão chega **antes** do código ser gerado, não só depois. Para mim, esse é o ponto
mais relevante para os próximos anos: decisões de arquitetura precisam ser legíveis por
máquina.

**"Como provo conformidade para auditoria?"**
Cada avaliação gera um resultado assinado e ligado ao commit. Para temas como LGPD (dado
pessoal em log) e segredos no código, isso muda a conversa com compliance: de "temos uma
política" para "temos a prova de que ela foi aplicada neste commit".

**"Como lido com exceções sem virar bagunça?"**
Toda regra encontra um caso legítimo em que não se aplica. Exceção por comentário no PR
("pode passar") não tem dono, não expira e não deixa rastro. Na PoC, exceção é um
registro versionado, com justificativa, aprovador diferente de quem pediu e validade
máxima de 90 dias. Quando vence, a regra volta a valer.

## O que isso não resolve

Aqui é onde um arquiteto experiente deve desconfiar, e eu também desconfio.

**Só a fatia verificável de uma ADR vira regra, e costuma ser a menor.** "O domínio não
depende de framework" vira verificação automática. "Este contexto usa consistência
eventual porque o custo de coordenação não se paga" não vira. As decisões mais
importantes continuam exigindo julgamento. O risco real é reduzir arquitetura a lint e o
time passar a otimizar para o check verde, não para a intenção.

**Não é uma ideia nova.** Fitness functions, testes de arquitetura e policy-as-code
existem há anos. O que esta abordagem acrescenta é a rastreabilidade até a decisão, a
evidência por commit e o uso da mesma fonte para orientar agentes de IA. É uma
combinação, não uma invenção.

**Governança centralizada vira polícia.** Na PoC, um único dono aprova todas as regras.
Isso não escala. O modelo sustentável é federado: cada domínio é dono das próprias
políticas, e a plataforma é dona do mecanismo, do versionamento e da evidência.

**A IA no caminho crítico tem um custo.** Usei um revisor de IA como camada consultiva:
ele aponta o que regex não enxerga (como um CPF escondido no `toString()` de um objeto),
mas não bloqueia nada. Mesmo assim, quando o provedor ficou instável, os PRs travaram,
porque o pipeline falha fechado: sem revisão completa, sem merge. É uma escolha defensável,
mas é uma inconsistência que precisa ser assumida. Um componente que não decide nada
passou a determinar a disponibilidade do fluxo de entrega. Para quem desenha isso em
escala, essa é uma decisão de arquitetura por si só.

**A evidência ainda é pequena.** Um PR de teste foi bloqueado corretamente. Os testes das
regras passam todos, mas foram escritos por quem escreveu as regras: provam que nada
regrediu, não que a regra acerta em código real. Não há ainda números de adoção nem de
falso positivo.

**Sem a camada de plataforma, é contornável.** Na PoC, o próprio repositório avaliado
chama a verificação, então um PR pode removê-la. Para virar controle de verdade, a regra
precisa ser imposta de fora do repositório, pela organização.

## Princípios que eu levaria para qualquer implementação

1. **Determinístico primeiro.** Se a decisão pode ser verificada por uma regra exata, não
   use IA para isso.
2. **IA como sinal, não como juiz.** Ela amplia o que é visto; não aprova nem remove
   achados. Para bloquear, precisa provar que acerta de forma consistente.
3. **Quem governa fica separado de quem é governado.** Nada no repositório avaliado pode
   mudar como ele é avaliado.
4. **Falhar fechado, e saber quanto isso custa.** Um erro nunca vira aprovação, mas
   qualquer dependência no caminho do merge passa a ser uma dependência de disponibilidade.
5. **Exceção com dono e prazo.** Nunca por comentário.
6. **A decisão tem ciclo de vida.** Quando a ADR é substituída, a regra dela precisa ser
   aposentada junto.

## Se eu fosse começar numa organização

- Escolheria **uma** decisão objetiva e cara de desfazer: segredo no código, dado pessoal
  em log ou acoplamento do domínio.
- Ligaria em modo de **alerta** por algumas semanas antes de bloquear. Regra que bloqueia
  errado ensina o time a contorná-la.
- Mediria desde o primeiro dia: taxa de falso positivo, tempo até a correção, quantidade
  de exceções ativas e tentativas de contorno. Sem isso, não há como defender a expansão.
- Daria a propriedade das regras aos domínios, não à arquitetura central.
- Trataria a exportação para os agentes de IA como requisito, não como bônus.

## Para fechar

A ADR não precisa ficar mais bonita. Precisa ter consequência. Tornar executável a parte
verificável de uma decisão não substitui o julgamento do arquiteto. Ele fica livre para as
decisões que só ele pode tomar, e as que já foram tomadas deixam de se degradar em
silêncio.

Esta é uma prova de conceito, com poucas regras por enquanto. O objetivo é ampliar os
guardrails a partir de um mecanismo que já funciona. O código, o manual passo a passo e o
relato técnico completo (o que funcionou, o que quebrou e os números) estão no GitHub:

https://github.com/robertosrjr/governance-policies

Se você já tentou algo parecido, quero saber: onde a regra executável ajudou, e onde ela
atrapalhou?
