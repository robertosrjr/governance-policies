# ADR-SEC-003: Criptografia verificável no código e nenhum dado de cartão no repositório

## Status

Aceito — 2026-09-29.

## Contexto

A OWASP-A04 (criptografia) está em `audit`: descreve KMS e TLS, mas nada no PR a
verifica. Ao mesmo tempo, os erros mais comuns de criptografia em Java são chamadas de
API reconhecíveis numa linha: `MessageDigest.getInstance("MD5")`,
`Cipher.getInstance("AES")` (que no JCE significa AES/ECB), `SSLContext.getInstance("TLSv1")`,
`NoopHostnameVerifier` e `new Random()` gerando token.

Dados de cartão (PAN) seguem o PCI DSS: só podem existir no ambiente de dados de cartão
(CDE), protegidos. Um PAN em fixture, massa de teste ou print colado em documentação
coloca o repositório, o CI e todos os clones no escopo do PCI e é incidente se o número
for de titular real.

## Decisão

1. Os padrões inseguros de criptografia, TLS e geração de segredo acima não entram em
   código de produção.
2. Nenhum PAN entra no repositório. Testes usam os números de teste publicados pelas
   bandeiras ou tokens do cofre de cartões.
3. Detecção de PAN é determinística com validação: prefixo de bandeira (3, 4, 5, 6),
   13 a 19 dígitos e dígito de Luhn. A lista de números de teste aceitos fica no motor
   (`engine/governance/validators.py`), versionada com o bundle.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [SEC-CRYPTO-001](../policies/SEC-CRYPTO-001.yaml) | regex por API insegura | SAST do build; OWASP-A04 (`audit`) para KMS/CMK |
| [SEC-PAN-001](../policies/SEC-PAN-001.yaml) | regex + validador `pan` (Luhn) | gitleaks nos commits; DLP no destino dos logs |

Limites: criptografia montada por variável (`Cipher.getInstance(algoritmo)`) escapa.
MD5 usado como checksum não criptográfico (ETag) gera alerta legítimo de revisar.
Números de 13 a 19 dígitos que passam em Luhn por acaso (1 em 10) geram falso positivo;
o prefixo de bandeira reduz, mas não elimina.

## Exemplos

`eval/cases/sec-crypto-001-*.yaml` e `eval/cases/sec-pan-001-*.yaml`.

## Consequências

- Os dois entram em `warn` (ADR-GOV-003) e sobem para `enforce` com dados de falso
  positivo dos repositórios piloto.
- Achado de SEC-PAN-001 não mostra o número (a mensagem é fixa) e o motor o remove antes
  de qualquer envio ao LLM.
