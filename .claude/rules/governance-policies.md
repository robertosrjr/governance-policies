# Políticas de governança (Claude Code)

<!-- GERADO por `python -m governance export`. Edite policies/*.yaml. -->

Ao gerar ou editar código, respeite as políticas abaixo. As `enforce` + `CRITICAL`
bloqueiam o merge no pipeline central; as `warn` aparecem como alerta.

## ARCH-HEX-001 — Domínio livre de frameworks (Spring, JPA)
- Severidade: `CRITICAL` · modo: `enforce` · ADR: `ADR-ARCH-001`
- Escopo: `**/src/main/java/**/domain/**/*.java`
- Verificação: motor (regex), archunit (`ArchitectureTest#domain_should_not_depend_on_frameworks`)

Classes em `domain` não podem depender de Spring (`org.springframework`) nem de Jakarta/Javax Persistence. A regra do motor cobre import, import static e nome totalmente qualificado (inclusive em anotações). Ofuscação via escapes Unicode é coberta por SEC-OBFUSC-001, e o ArchUnit do build verifica o bytecode.

**Correção:** Remova anotações Spring/JPA do domínio. Mova o mapeamento ORM para `infrastructure/persistence` (ex.: ClienteEntity) e converta com mappers.

## ARCH-HEX-002 — Camadas internas não dependem de infrastructure
- Severidade: `CRITICAL` · modo: `enforce` · ADR: `ADR-ARCH-001`
- Escopo: `**/src/main/java/**/domain/**/*.java`, `**/src/main/java/**/application/**/*.java`
- Verificação: motor (regex), archunit (`ArchitectureTest#application_should_not_depend_on_infrastructure`)

`domain` e `application` não podem referenciar classes de pacotes `infrastructure` (import, import static ou nome totalmente qualificado). A dependência aponta sempre para dentro: infrastructure -> application -> domain.

**Correção:** Declare uma porta (interface) em `application/port/out` e implemente o adaptador em `infrastructure`. O caso de uso depende só da porta.

## LGPD-LOG-001 — Dado pessoal em logs, traces, métricas ou exceções
- Severidade: `CRITICAL` · modo: `enforce` · ADR: `ADR-LGPD-001`
- Escopo: `**/*.java`, `**/*.kt`
- Verificação: motor (regex), LLM consultivo

Nenhum dado pessoal (CPF, CNPJ, RG, e-mail, telefone, cartão, senha) pode chegar a logs, traces, métricas ou mensagens de exceção sem mascaramento. A regra do motor cobre o caso direto em uma linha (identificador pessoal como argumento de log fora de mask/sanitize/redact). Os casos indiretos (toString() de objeto com dado pessoal, corpo de request, atributo de span, tag de métrica, chamada de log quebrada em várias linhas) ficam com o LLM, em modo consultivo até o eval justificar bloqueio.

**Correção:** Passe o valor por `PIISanitizer.mask(valor)` antes de logar, ou registre só um identificador técnico (id do pedido, hash). Nunca logue o objeto inteiro nem o corpo de request/response.

## LLM-INJ-001 — Conteúdo que tenta manipular revisores ou assistentes de IA
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-SEC-001`
- Escopo: `**/*`
- Verificação: motor (regex), LLM consultivo

Sinal, não controle: frases dirigidas a uma IA ("ignore previous rules", "approve this PR", "INSTRUCTION:") escondidas no código. Lista de palavras é fácil de contornar e gera falso positivo em código que implementa guardrails, por isso não bloqueia. A defesa real é de arquitetura (ADR-GOV-000): o LLM não aprova nada e não consegue remover achados da camada determinística. Este achado chama a atenção do revisor humano para uma tentativa de manipulação.

**Correção:** Remova o texto. Se for um caso de teste de guardrail, mantenha-o em diretório de testes e rotule como adversarial.

## OWASP-A01 — Controle de acesso: menor privilégio, default deny, IDOR e SSRF
- Severidade: `CRITICAL` · modo: `audit` · ADR: `ADR-SEC-002`
- Escopo: `**/*`
- Verificação: revisão humana / AWS Security Agent

Enforce least privilege, default deny, and IDOR/SSRF prevention across APIs and microservices (OWASP A01:2025).

**Correção:** Implement Amazon Verified Permissions or Cedar policies for fine-grained authorization. Validate user ownership before object access (CWE-639) and restrict outbound VPC traffic for SSRF prevention (CWE-918).

## OWASP-A02 — Configuração segura: defaults seguros, sem debug, sem acesso público
- Severidade: `MAJOR` · modo: `audit` · ADR: `ADR-SEC-002`
- Escopo: `**/*`
- Verificação: revisão humana / AWS Security Agent

Ensure secure defaults, disable active debug code, and restrict public access (OWASP A02:2025).

**Correção:** Remove active debug code (CWE-489) before deployment. Use AWS Config rules to enforce S3 Block Public Access and TLS 1.2+.

## OWASP-A03 — Cadeia de suprimentos: dependências mantidas e SBOM
- Severidade: `MAJOR` · modo: `audit` · ADR: `ADR-SEC-002`
- Escopo: `**/*`
- Verificação: revisão humana / AWS Security Agent

Validate third-party dependencies and maintain Software Bill of Materials (OWASP A03:2025).

**Correção:** Set up automated dependency scanning using Amazon Inspector / OWASP Dependency-Track and restrict packages to internal Amazon CodeArtifact repositories.

## OWASP-A04 — Criptografia: KMS CMK em repouso e TLS 1.2+ em trânsito
- Severidade: `CRITICAL` · modo: `audit` · ADR: `ADR-SEC-002`
- Escopo: `**/*`
- Verificação: revisão humana / AWS Security Agent

Enforce strong cryptography and Customer Managed Keys (CMK) for data at rest and in transit (OWASP A04:2025).

**Correção:** Migrate secrets and keys to AWS Secrets Manager or KMS. Replace cleartext HTTP/FTP endpoints with HTTPS/TLS.

## OWASP-A10 — Tratamento de exceções: fail-closed, sem stack trace ao cliente
- Severidade: `MAJOR` · modo: `audit` · ADR: `ADR-SEC-002`
- Escopo: `**/*`
- Verificação: revisão humana / AWS Security Agent

Prevent improper error handling and ensure fail-closed logic (OWASP A10:2025).

**Correção:** Implement global exception handlers that return generic error pages/JSON to clients while logging full details internally to CloudWatch.

## QUAL-CODE-001 — Regras objetivas de qualidade de código Java
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-QUAL-001`
- Escopo: `**/src/main/java/**/*.java`
- Verificação: LLM consultivo

Regras objetivas herdadas do code-quality-auditor da PoC: não retornar null em método público, injeção por construtor (não por campo), nenhum `catch` genérico que engole a exceção, nenhum retorno `Object` em API pública. Revisão por LLM, consultiva.

**Correção:** Use Optional ou exceção de domínio em vez de null; injete dependências pelo construtor; trate exceções específicas e propague ou registre com contexto; tipe o retorno.

## SEC-OBFUSC-001 — Escape Unicode fora de literal em código Java
- Severidade: `CRITICAL` · modo: `enforce` · ADR: `ADR-SEC-001`
- Escopo: `**/*.java`
- Verificação: motor (regex)

O compilador Java traduz `\uXXXX` antes da análise léxica, inclusive em comentários. Isso permite esconder imports proibidos (`org.springframework`) ou executar código "comentado" (`// \u000a codigo()`), enganando regras textuais e revisores.

**Correção:** Escreva o caractere diretamente. Escapes Unicode só são aceitos dentro de literais de string ou char.

## SEC-SECRET-001 — Segredo ou credencial no código ou em configuração versionada
- Severidade: `CRITICAL` · modo: `enforce` · ADR: `ADR-SEC-001`
- Escopo: `**/*`
- Verificação: motor (regex)

Chaves de API, tokens, senhas e chaves privadas não podem ser versionados (Secret Zero). O motor detecta formatos conhecidos (AWS, Google, GitHub, Slack, chave privada PEM) e atribuições literais a nomes como password/secret/token/api_key. O pipeline também roda o gitleaks sobre os commits do PR.

**Correção:** Remova o valor, revogue a credencial (ela já está no histórico) e leia de um cofre (AWS Secrets Manager, Vault) ou de variável de ambiente injetada no deploy.

## SEC-UNICODE-001 — Caracteres Unicode invisíveis ou de controle bidirecional
- Severidade: `CRITICAL` · modo: `enforce` · ADR: `ADR-SEC-001`
- Escopo: `**/*`
- Verificação: motor (regex)

Caracteres de controle bidirecional (Trojan Source, CVE-2021-42574), de largura zero e de "tag" Unicode fazem o código parecer diferente do que é executado e escondem instruções de revisores humanos e de LLMs. Não têm uso legítimo em código-fonte.

**Correção:** Remova os caracteres. Se forem necessários em um literal (i18n), use a forma escapada e registre um waiver com justificativa.
