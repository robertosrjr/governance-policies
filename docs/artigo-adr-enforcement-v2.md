# Da ADR ao PR bloqueado: o que muda quando a decisão de arquitetura vira regra

A ADR é aprovada. Meses depois, um PR coloca `@Entity` numa classe de domínio, o revisor
não percebe, e a ADR continua lá, correta e sem efeito.

Não é má vontade. A ADR não está presente quando o código é escrito nem quando ele é
revisado. Este texto relata o que aconteceu quando ligamos as ADRs de um projeto Java a
regras executadas em todo Pull Request: o que funcionou, o que quebrou e o que continua
aberto.

**Escopo:** prova de conceito. São 9 regras no PR (6 bloqueiam, 3 só alertam), cobrindo
arquitetura hexagonal, dado pessoal em log, segredos e manipulação de revisores de IA. O
objetivo é o mecanismo: com ele pronto, cada guardrail novo é uma política, uma ADR e
seus casos de teste.

## Como funciona

- Cada decisão **verificável** de uma ADR vira uma política em YAML que aponta para a ADR.
- Um workflow roda as políticas no diff de todo PR.
- O branch principal só aceita merge com o check verde.

A ADR continua sendo o *porquê*. A política é o *quê*, num formato que a máquina checa.

## Exemplo de ponta a ponta

**A decisão** (ADR-ARCH-001):

> Classes em `domain` são agnósticas de framework: não referenciam `org.springframework`,
> `jakarta.persistence` nem `javax.persistence`.

**A política:**

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

**O resultado:** um PR de teste adicionou `@Component` a um `record` do domínio. O merge
ficou bloqueado com este comentário:

> **Governança — Bloqueado**
>
> | Severidade | Política | Local | Descrição |
> |---|---|---|---|
> | CRITICAL | ARCH-HEX-001 | `.../domain/model/OrderItem.java:6` | Domínio referencia Spring ou JPA (ADR-ARCH-001). |

Dois detalhes:

- A regex só olha as **linhas adicionadas**. Código antigo que já viola a regra não trava
  quem não mexeu nele.
- A regex dá retorno rápido no PR. O ArchUnit analisa o bytecode e pega o que texto não
  pega (ex.: dependência que chega por tipo de retorno). No nosso caso, o ArchUnit ainda
  não roda no CI da aplicação.

## O que a ligação ADR ↔ regra resolveu

| Antes | Agora |
|---|---|
| A mesma regra existia em 5 lugares (ADR, pacote JSON de uma ferramenta de segurança, README, prompt do revisor de IA, ArchUnit). A ADR dizia `HIGH`; o README e o revisor, `CRITICAL`. | A severidade existe só na política. Os outros formatos são gerados dela. |
| Regra sem justificativa escrita era possível. | Toda política tem `adr:`, e a validação falha se a ADR não existir. |
| O motivo chegava em comentário vago de revisão, dias depois. | O motivo chega no PR, com arquivo, linha e ADR. |
| O assistente de código não conhecia as decisões. | As políticas são exportadas como regras do Claude Code: a decisão aparece antes do código ser gerado. |
| "O PR passou?" era a única pergunta. | O motor grava um `result.json` assinado com o status **de cada ADR** no commit. |

O `result.json` do PR de teste:

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

Ele responde "este commit cumpre a ADR-ARCH-001, com qual versão das regras?". Por
enquanto só guardamos o arquivo; ainda não há painel nem bloqueio de deploy em cima dele.

## Nem toda decisão vira regra

| Tipo de decisão | Exemplo | Como verificar | Modo |
|---|---|---|---|
| Proibição objetiva, visível no texto | Domínio sem Spring/JPA; segredo no código | Regex ou path | Bloqueia |
| Proibição estrutural | Camada interna dependendo de `infrastructure` | Regex no PR + ArchUnit no build | Bloqueia |
| Proibição com caso direto e indireto | CPF em log | Regex bloqueia o direto; LLM alerta o indireto | Bloqueia só o direto |
| Boa prática com exceções legítimas | Injeção por construtor, não retornar `null` | LLM | Só alerta |
| Decisão que depende de contexto | Autorização com Cedar, TLS em trânsito | Revisão humana | Auditoria, fora do PR |

O CPF mostra o limite:

```java
logger.info("CPF do cliente: " + cpf);    // regex bloqueia
logger.info("Cliente criado: {}", novo);  // passa: o CPF está no toString() de Cliente
```

O segundo caso só um revisor que entende o código enxerga. Fica com o LLM, que comenta
mas não bloqueia: para bloquear, ele precisaria provar que acerta de forma consistente, e
essa evidência ainda não existe.

## O que deu errado no primeiro dia

| O que aconteceu | Causa | Lição |
|---|---|---|
| Todo PR ficaria bloqueado para sempre | A proteção do branch exigia o check `ai-review`, do pipeline removido | Trocou o pipeline, troque a proteção do branch no mesmo dia. |
| O workflow falhou antes de começar, sem mensagem útil (só o nome do arquivo no lugar do job) | A aplicação apontava para a tag `v1.0.0`, que não tinha sido publicada | Falhar fechado estava certo, mas custou tempo. Publique a tag antes do PR. |
| O check novo não aparecia para ser exigido | O GitHub só lista checks que já rodaram | Rode o check num PR antes, ou configure pela API. |
| Sequência de erros 503 ao medir o revisor de IA | Sobrecarga do provedor | Como qualquer erro bloqueia, o provedor fora do ar **trava PRs**. Decidimos manter o bloqueio, mas com um alerta explícito: "Revisor de IA indisponível. Não é problema no seu código." |
| O PR que instalou a governança gerou um alerta sobre ele mesmo | A política de mudança em CI viu 5 arquivos em `.github/` | Esperado, mas alerta demais vira ruído rápido. |

## O que o eval prova e o que não prova

Cada política tem casos de teste: código que deve violar e código parecido que não deve.
Os 27 casos da camada determinística:

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

- **Zero erros é esperado por construção:** quem escreveu os casos escreveu as regras, e a
  validação exige que passem. É um **teste de regressão**, não uma medida de falso
  positivo em código real.
- **A precisão real vem dos PRs.** Até agora, um PR real: bloqueio correto. É pouco. Todo
  erro encontrado em PR vira caso de teste antes da correção.
- **Os casos de LLM** (`toString()`, atributos de trace, manipulação do revisor, qualidade)
  ficam fora desse eval. Só serão medidos com o eval com LLM, repetindo cada caso, porque
  a resposta do modelo varia.

## Limites em aberto

- **O repositório avaliado pode desligar a avaliação.** Sem organização no GitHub, a
  aplicação chama o workflow central por um arquivo dela, que um PR pode editar. Check
  obrigatório e aprovação reduzem o risco, não eliminam. Com organização, a regra é
  imposta de fora.
- **O ArchUnit não roda no CI da aplicação.** Hoje só a regex protege o PR.
- **O diff sai do país.** O código vai para um LLM no exterior. Com dado pessoal real, isso
  exige base legal (LGPD, Art. 33). É decisão de compliance, não de engenharia.
- **O LLM não aprova nada.** Ele só acrescenta achados; um "aprove este PR" escrito no
  código não muda o veredito. Em contrapartida, a camada de IA hoje informa, não protege.

## Para começar amanhã

1. Escolha **uma** ADR com uma proibição objetiva (arquitetura hexagonal, "nenhum segredo
   no código").
2. Escreva a regra mais simples: path ou regex nas linhas adicionadas. Sem LLM.
3. Escreva casos que violam e casos parecidos que não violam. Os negativos evitam falso
   positivo.
4. Ligue em modo **alerta** e observe algumas semanas de PRs.
5. Só então bloqueie. Regra que bloqueia errado ensina o time a contorná-la.
6. Exceção é registro com dono, justificativa e validade. Nunca "bypass" por comentário.
7. Ao trocar o pipeline, revise no mesmo dia a proteção do branch e a versão publicada.

## Teste você mesmo

O repositório é público. Sem abrir PR:

1. Clone e instale: `pip install --no-deps --require-hashes -r engine/requirements-dev.lock`.
2. Num projeto Java seu, crie um branch, adicione
   `import org.springframework.stereotype.Component;` a uma classe de `domain/` e faça commit.
3. Rode `python -m governance review --repo <seu-projeto> --base main --no-llm`
   (com `PYTHONPATH=engine`).
4. Resultado: `ARCH-HEX-001 … (deterministic, bloqueia)` e `Veredito: BLOCKED`.

O [manual de configuração](manual-configuracao.md) traz os outros cenários com a saída
real de cada um, como ligar no GitHub e o que fazer com cada mensagem de erro.

## Conclusão

A ADR não ficou mais importante. As partes verificáveis dela passaram a ter consequência
no merge, e a divergência entre "o que a ADR diz" e "o que o pipeline cobra" deixou de
ser possível.

O custo é real: regras e casos para manter, e um pipeline que falha fechado e, por isso,
também trava por problema de infraestrutura. Para decisões objetivas e caras de desfazer
(segredo vazado, dado pessoal em log, domínio acoplado), a troca tem valido a pena. Para o
resto, a ADR continua sendo um bom registro do porquê.
