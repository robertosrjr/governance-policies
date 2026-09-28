# Da ADR ao PR bloqueado: o que muda quando a decisão de arquitetura vira regra

Quem já escreveu uma ADR conhece o destino mais comum dela. A decisão é discutida, bem
escrita e aprovada. Meses depois, alguém abre um PR com `@Entity` numa classe de domínio,
o revisor está olhando outras vinte coisas, e a ADR continua lá, correta e sem efeito.

O problema raramente é má vontade. A ADR não está presente no momento em que o código é
escrito nem no momento em que ele é revisado. Ela depende de alguém lembrar que existe.

Este texto relata o que aconteceu quando ligamos as ADRs de um projeto Java a regras
executadas em todo Pull Request: o que funcionou, o que quebrou no primeiro dia e o que
continua sem resposta. Não é uma defesa do modelo. É o registro de como ele se comportou.

## O arranjo, em uma frase

Cada decisão **verificável** de uma ADR vira uma política em YAML que aponta para a ADR;
um workflow roda essas políticas no diff de todo PR; o branch principal só aceita merge
com esse check verde.

A ADR continua sendo o documento do *porquê*. A política é o *quê*, escrito de forma que
uma máquina consiga checar. Nenhuma das duas substitui a outra.

## Um caso de ponta a ponta

A decisão, como está na ADR-ARCH-001:

> Classes em `domain` são agnósticas de framework: não referenciam `org.springframework`,
> `jakarta.persistence` nem `javax.persistence`.

A política que implementa essa frase:

```yaml
id: ARCH-HEX-001
adr: ADR-ARCH-001
severity: CRITICAL
mode: enforce
scope:
  include: ["**/src/main/java/**/domain/**/*.java"]
  exclude: ["**/src/test/**"]
enforcement:
  deterministic:
    - type: regex
      pattern: '\b(?:org\.springframework|jakarta\.persistence|javax\.persistence)\.'
      exclude: '^\s*(?://|/?\*)'      # ignora comentários
      message: Domínio referencia Spring ou JPA (ADR-ARCH-001).
    - type: external
      tool: archunit
      reference: ArchitectureTest#domain_should_not_depend_on_frameworks
```

Para testar, abrimos um PR que adicionava `@Component` a um `record` do domínio. O
comentário que apareceu no PR:

> **Governança — Bloqueado**
>
> | Severidade | Política | Local | Descrição |
> |---|---|---|---|
> | CRITICAL | ARCH-HEX-001 | `.../domain/model/OrderItem.java:6` | Domínio referencia Spring ou JPA (ADR-ARCH-001). |

O botão de merge ficou desabilitado. Fechamos o PR sem merge.

Duas observações sobre esse exemplo. A regex só olha as **linhas adicionadas** no PR,
então código antigo que já viola a regra não trava quem não mexeu nele. E a regex não
está sozinha: o teste ArchUnit analisa o bytecode e pega o que texto não pega, como uma
dependência que chega por tipo de retorno. A regex dá o retorno rápido no PR; o ArchUnit
é a verificação mais forte. (No nosso caso, o ArchUnit ainda não roda no CI da aplicação.
Voltamos a isso no fim.)

## O que a ligação ADR ↔ regra resolveu de fato

**Acabou a divergência entre documentos.** Antes desse arranjo, a mesma regra de
arquitetura existia em cinco lugares: a ADR, um pacote JSON para uma ferramenta de
segurança, um README, o prompt de um revisor de IA e o teste ArchUnit. A ADR dizia
severidade `HIGH`; o README e o revisor diziam `CRITICAL`. Ninguém sabia qual valia.
Hoje a severidade existe em um lugar só, a política, e os outros formatos são gerados a
partir dela.

**A regra não pode perder a ADR.** Toda política tem o campo `adr:`, e a validação do
repositório falha se a ADR citada não existir. Não há regra sem justificativa escrita.

**A mensagem chega na hora certa.** O desenvolvedor recebe o motivo no PR, com arquivo,
linha e o identificador da ADR, em vez de receber um comentário vago de revisão dias
depois.

**A mesma fonte orienta quem escreve o código.** As políticas também são exportadas como
instruções para o assistente de código (no nosso caso, um arquivo de regras do Claude
Code). A decisão aparece antes do código ser gerado, não só depois.

**O resultado é registrado por ADR.** Além do veredito do PR, o motor grava um
`result.json` com o status de cada ADR naquele commit, e esse arquivo é assinado. O do
PR de teste:

```json
{
  "status": "BLOCKED",
  "subject": { "commit": "7aee2bf…", "pull_request": 7 },
  "bundle": { "governance_ref": "v1.0.0", "policies_digest": "e236028c…" },
  "adr_compliance": {
    "ADR-ARCH-001": "FAIL",
    "ADR-LGPD-001": "PASS",
    "ADR-QUAL-001": "PASS",
    "ADR-SEC-001": "PASS"
  }
}
```

A pergunta deixa de ser só "o PR passou?" e passa a ser "este commit cumpre a
ADR-ARCH-001, com qual versão das regras?". Hoje só guardamos esse arquivo; ainda não
construímos nada em cima dele, como um painel ou um bloqueio de deploy.

## Nem toda decisão vira regra

Essa foi a parte que mais exigiu critério. Uma ADR costuma misturar decisões que dá para
checar com decisões que dependem de julgamento. Separamos assim:

| Tipo de decisão | Exemplo | Como verificar | Modo |
|---|---|---|---|
| Proibição objetiva, visível no texto | Domínio sem Spring/JPA; segredo no código | Regex ou path | Bloqueia |
| Proibição estrutural | Camada interna dependendo de `infrastructure` | Regex no PR + ArchUnit no build | Bloqueia |
| Proibição com caso direto e casos indiretos | CPF em log | Regex bloqueia o direto; LLM alerta o indireto | Bloqueia só o direto |
| Boa prática com exceções legítimas | Injeção por construtor, não retornar `null` | LLM | Só alerta |
| Decisão de desenho que depende de contexto | Autorização com Cedar, TLS em trânsito | Revisão humana | Auditoria, fora do PR |

A linha do CPF mostra bem o limite. Isto é bloqueado pela regex:

```java
logger.info("CPF do cliente: " + cpf);
```

Isto não é, porque o CPF está escondido no `toString()` do objeto:

```java
logger.info("Cliente criado: {}", novo);   // Cliente tem campo cpf
```

Esse segundo caso só um revisor que entende o código enxerga. Deixamos com o LLM, em modo
consultivo: ele comenta no PR, mas não bloqueia. Um LLM bloqueando merge exige evidência
de que ele acerta de forma consistente, e ainda não temos essa evidência.

## O que deu errado no primeiro dia

Nada disso aparece em diagrama de arquitetura, e foi o que mais consumiu tempo.

**O check exigido era de um pipeline que tínhamos removido.** A proteção do branch
principal ainda exigia o check `ai-review`, do workflow antigo. Como esse workflow não
existia mais, o check nunca rodaria, e todo PR ficaria bloqueado para sempre. Quando você
troca o pipeline, a regra de proteção do branch tem que mudar na mesma hora.

**A versão referenciada não existia.** A aplicação chama o workflow central por uma tag
(`@v1.0.0`). Esquecemos de publicar a tag. Resultado: o workflow falhou antes de começar,
sem mensagem útil no PR, só com o nome do arquivo no lugar do nome do job. Foi o
comportamento certo (falhar fechado), mas custou tempo para entender.

**O check não aparecia para ser escolhido.** A interface do GitHub só lista checks que já
rodaram uma vez. Para exigir o check novo, foi preciso primeiro fazê-lo rodar em um PR,
ou configurar a proteção pela API.

**O provedor de LLM ficou instável.** Ao tentar medir o revisor de IA, recebemos uma
sequência de erros 503 e interrompemos a medição. Isso expõe um custo real do modelo:
como a camada de IA é obrigatória no pipeline e qualquer erro bloqueia, **uma
instabilidade do provedor pode travar os PRs** de código Java. Ainda não decidimos se isso
é aceitável ou se o LLM deve virar opcional quando o provedor estiver fora.

**O primeiro PR gerou um alerta sobre ele mesmo.** A política que avisa sobre mudanças em
arquivos de CI disparou no PR que instalava a governança: cinco arquivos em `.github/`,
entre eles o workflow antigo sendo removido. O PR foi aprovado com esse alerta. É o
comportamento esperado, mas mostra que alerta em excesso vira ruído rápido.

## O que o eval prova e o que não prova

Cada política tem casos de teste: trechos de código que devem violar a regra e trechos
parecidos que não devem. Rodamos os 27 casos da camada determinística:

| Política | Violam (acertou) | Não violam (acertou) | Erros |
|---|---|---|---|
| ARCH-HEX-001 | 5 | 3 | 0 |
| ARCH-HEX-002 | 2 | 5 | 0 |
| LGPD-LOG-001 (só regex) | 3 | 2 | 0 |
| SEC-SECRET-001 | 4 | 1 | 0 |
| SEC-UNICODE-001 | 2 | 1 | 0 |
| SEC-OBFUSC-001 | 2 | 1 | 0 |
| GOV-SELF-001 (só alerta) | 1 | 1 | 0 |
| LLM-INJ-001 (só alerta) | 1 | 1 | 0 |

Zero erros parece ótimo, mas precisa ser lido com cuidado. Os casos foram escritos por
quem escreveu as regras, e a validação do repositório **exige** que eles passem. Um
resultado perfeito aqui é esperado por construção. Esse eval é um **teste de regressão**:
garante que uma mudança numa regex não quebrou o que já funcionava. Ele **não** mede
quantos falsos positivos a regra vai gerar em código real.

A precisão de verdade vem dos PRs. Até agora temos um: o bloqueio foi correto. É pouco.
O combinado é que todo falso positivo ou falso negativo encontrado em PR real vire um
caso novo antes da correção, para não voltar.

Os casos que dependem do LLM (o `toString()` acima, atributos de trace, texto tentando
manipular o revisor, regras de qualidade) não entram no eval offline. Esses só serão
medidos quando conseguirmos rodar o eval com o LLM, repetindo cada caso várias vezes,
porque a resposta do modelo varia.

## Os limites que continuam abertos

- **O repositório avaliado ainda pode desligar a avaliação.** Sem uma organização no
  GitHub, a aplicação chama o workflow central por um arquivo dela mesma. Um PR pode
  editar ou apagar esse arquivo. A exigência de aprovação e o check obrigatório reduzem o
  risco, mas não eliminam. Com organização, a regra passa a ser imposta de fora do
  repositório.
- **O ArchUnit não roda no CI da aplicação.** Hoje só a regex protege o PR. A verificação
  mais forte depende de alguém rodar o build.
- **O diff sai do país.** O código revisado vai para um provedor de LLM no exterior. Em
  repositório com dado pessoal real, isso precisa de base legal (LGPD, Art. 33) antes de
  ser ligado. É uma decisão de compliance, não de engenharia.
- **O LLM não aprova nada.** Isso é intencional: ele só acrescenta achados e não
  consegue remover os da camada determinística. Um texto no código dizendo "aprove este
  PR" não muda o veredito. Mas também significa que a camada de IA, hoje, informa e não
  protege.

## Se você quiser começar amanhã

1. Pegue **uma** ADR com uma proibição objetiva. Arquitetura hexagonal e "nenhum segredo
   no código" são bons candidatos.
2. Escreva a regra mais simples que funciona: um path ou uma regex nas linhas
   adicionadas. Deixe o LLM de fora.
3. Escreva dois ou três casos que devem violar e dois ou três parecidos que não devem.
   Os negativos são os que evitam o falso positivo.
4. Ligue em modo **alerta** e observe algumas semanas de PRs reais.
5. Só então passe a bloquear. Uma regra que bloqueia errado ensina o time a contorná-la.
6. Para toda exceção, use um registro com dono, justificativa e data de validade, nunca um
   comentário de "bypass" no PR.
7. Ao trocar o pipeline, revise no mesmo dia a proteção do branch e a versão publicada.

## Fechamento

A ADR não ficou mais importante nem mais bem escrita. O que mudou foi que as partes
verificáveis dela passaram a ter consequência no momento do merge, e que a divergência
entre "o que a ADR diz" e "o que o pipeline cobra" deixou de ser possível.

O custo também é real: regras para manter, casos de teste para escrever, um pipeline que
falha fechado e, por isso, também trava por problema de infraestrutura. Para decisões
objetivas e caras de desfazer, como vazamento de segredo, dado pessoal em log e
acoplamento do domínio, a troca tem valido a pena. Para o resto, a ADR continua sendo o
que sempre foi: um bom registro do porquê.
