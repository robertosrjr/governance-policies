# ADR-SEC-002: Requisitos OWASP Top 10:2025 para revisão de design e pentest

## Status

Aceito — 2026-09-25.

## Contexto

O pacote `custom_security_pack_owasp2025.json` era mantido à mão para o AWS Security
Agent. Esses requisitos (A01, A02, A03, A04, A10) tratam de desenho, configuração de
nuvem e comportamento em execução, e não são verificáveis olhando só o diff de um PR.

## Decisão

- Cada requisito vira uma política (`policies/OWASP-*.yaml`) em modo `audit`, sem
  `enforcement`: o motor de PR não os avalia.
- O pack do AWS Security Agent é **gerado** em
  `exports/aws-security-agent/governance-pack.json` junto com as políticas de PR que
  também se aplicam a ele (ARCH-HEX-001, LGPD-LOG-001, SEC-SECRET-001).
- As mesmas políticas vão para o Claude Code (`.claude/rules/governance-policies.md`) como
  orientação no desenvolvimento.

### Adendo — 2026-09-29: parte verificável de A02 e A10

A configuração Spring que vai para produção é texto no diff e pode ser verificada sem
LLM. [SEC-CONFIG-001](../policies/SEC-CONFIG-001.yaml) cobre `ddl-auto` que altera o
schema, SQL e bind em log, stack trace na resposta, Actuator exposto e H2/debug ligados.
Os perfis `dev`, `local` e `test` ficam fora do escopo. Limite: propriedade aninhada em
YAML só é vista quando a chave final é inequívoca (ex.: `ddl-auto`, `include: "*"`);
valores vindos de variável de ambiente ou de config server não aparecem no diff. As
políticas OWASP-A02/A10 continuam em `audit` para o que não é texto do PR.

## Consequências

- Alterar um requisito é editar o YAML e rodar `python -m governance export`; o CI
  bloqueia exports desatualizados.
- O texto dos requisitos OWASP permanece em inglês, como no pack original.
