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

## Consequências

- Alterar um requisito é editar o YAML e rodar `python -m governance export`; o CI
  bloqueia exports desatualizados.
- O texto dos requisitos OWASP permanece em inglês, como no pack original.
