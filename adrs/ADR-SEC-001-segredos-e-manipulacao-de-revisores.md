# ADR-SEC-001: Segredos, ofuscação e manipulação de revisores

## Status

Aceito — 2026-09-25.

## Contexto

Com revisores automatizados (LLM) no pipeline, o código revisado vira entrada de um
modelo. Além dos riscos clássicos (credencial versionada), surgem ataques contra o
revisor: texto que tenta instruí-lo (OWASP LLM01, prompt injection indireta) e
ofuscação que faz o código parecer diferente do que é executado.

## Decisão

| Política | Tipo | Modo |
|---|---|---|
| [SEC-SECRET-001](../policies/SEC-SECRET-001.yaml) | Credencial literal: regex no motor + gitleaks no workflow | enforce |
| [SEC-UNICODE-001](../policies/SEC-UNICODE-001.yaml) | Caracteres bidi/invisíveis (Trojan Source, instrução oculta) | enforce |
| [SEC-OBFUSC-001](../policies/SEC-OBFUSC-001.yaml) | Escape `\uXXXX` fora de literal em Java | enforce |
| [LLM-INJ-001](../policies/LLM-INJ-001.yaml) | Texto dirigido a IA: regex + LLM, **sinal** | warn |

LLM-INJ-001 não bloqueia de propósito. A lista de palavras se contorna trocando de idioma
ou de codificação, e dispara em código legítimo de guardrail. O controle real contra
injeção é o desenho do ADR-GOV-000: o prompt vem do repo central, o conteúdo entra
delimitado por uma tag com nonce aleatório, o LLM não aprova nada e não remove achados
determinísticos. Já os caracteres invisíveis e os escapes Unicode são verificáveis sem
ambiguidade e não têm uso legítimo em código, por isso bloqueiam.

## Consequências

- Literais i18n com caracteres de largura zero exigem forma escapada ou waiver.
- A regex de segredos gera falso positivo em fixtures com valores fictícios; use valores
  claramente inválidos (`${VAR}`, menos de 8 caracteres) ou waiver com caminho restrito.
