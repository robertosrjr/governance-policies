# ADR-LGPD-001: Dado pessoal fora de logs, traces, métricas e exceções

## Status

Aceito — 2026-09-25.

## Contexto

Logs, traces e métricas são copiados para vários sistemas (APM, SIEM, backups) com
retenção e acesso bem mais amplos que o banco de dados. Um CPF em log vira um dado
pessoal espalhado sem controle, contrariando a minimização e a segurança exigidas pela
LGPD (Art. 6º III e VII, Art. 46).

## Decisão

Nenhum dado pessoal chega a logs, traces, métricas ou mensagens de exceção sem
mascaramento (`PIISanitizer.mask`). Política: [LGPD-LOG-001](../policies/LGPD-LOG-001.yaml).

- **Determinístico (bloqueia):** identificador pessoal passado diretamente a uma chamada
  de log ou `System.out`, fora de mask/sanitize/redact, na mesma linha.
- **LLM (consultivo):** caminhos indiretos, como `toString()` de objeto com dado pessoal,
  corpo de request, atributo de span, tag de métrica ou mensagem de exceção. Passa a
  bloquear só com evidência de eval (ADR-GOV-000).

## Consequências

- Chamadas de log quebradas em várias linhas escapam da regex e dependem do LLM.
- Testes ficam fora do escopo; dado pessoal real em fixtures é tratado em revisão humana.
