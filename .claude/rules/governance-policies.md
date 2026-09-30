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

## FIN-MONEY-001 — Aritmética monetária com tipo binário ou sem arredondamento explícito
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-FIN-001`
- Escopo: `**/src/main/**/*.java`, `**/src/main/**/*.kt`
- Verificação: motor (regex), motor (regex), motor (regex)

Valor monetário (valor, saldo, preço, juros, tarifa, taxa, montante) não pode usar double/float: o tipo binário não representa centavos e o erro se acumula em juros, rateio e conciliação. BigDecimal não pode nascer de literal double, e divide/setScale precisam de RoundingMode explícito (sem ele, dízima vira ArithmeticException em produção e a regra de arredondamento fica implícita). O motor cobre a declaração, o literal e a chamada numa mesma linha; tipo inferido fica com a revisão humana.

**Correção:** Use BigDecimal (ou um value object Dinheiro no domínio) criado com BigDecimal.valueOf(...) ou a partir de String, e informe o RoundingMode definido pelo produto (ex.: divide(b, 2, RoundingMode.HALF_EVEN), setScale(2, RoundingMode.HALF_EVEN)).

## LGPD-DATA-001 — CPF válido versionado em código, configuração ou massa de teste
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-LGPD-002`
- Escopo: `**/*`
- Verificação: motor (regex)

CPF com dígito verificador válido no repositório pode ser de um titular real (massa copiada de produção, print de chamado, planilha). Repositório não é ambiente autorizado para dado pessoal (LGPD Art. 6º III e Art. 46). O motor procura CPF com ou sem máscara e valida os dígitos verificadores; CPF com dígito inválido e sequências repetidas (111.111.111-11) passam.

**Correção:** Em massa de teste, use CPF com dígito verificador inválido ou um gerador sintético em tempo de teste. Se for dado real, remova e acione privacidade (ele continua no histórico). Teste de validador de CPF que precise de número válido: waiver.

## LGPD-LOG-001 — Dado pessoal em logs, traces, métricas ou exceções
- Severidade: `CRITICAL` · modo: `enforce` · ADR: `ADR-LGPD-001`
- Escopo: `**/*.java`, `**/*.kt`
- Verificação: motor (regex), LLM consultivo

Nenhum dado pessoal (CPF, CNPJ, RG, e-mail, telefone, cartão, senha) pode chegar a logs, traces, métricas ou mensagens de exceção sem mascaramento. A regra do motor cobre o caso direto em uma linha (identificador pessoal como argumento de log fora de mask/sanitize/redact). Os casos indiretos (toString() de objeto com dado pessoal, corpo de request, atributo de span, tag de métrica, chamada de log quebrada em várias linhas) ficam com o Jev: uma regex ampla marca as linhas que escrevem em log, span, métrica ou exceção, e o Jev julga cada uma (ADR-GOV-002). Consultivo até o eval justificar bloqueio.

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

## SEC-CONFIG-001 — Configuração Spring insegura para produção
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-SEC-002`
- Escopo: `**/src/main/resources/application*.yml`, `**/src/main/resources/application*.yaml`, `**/src/main/resources/application*.properties`
- Verificação: motor (regex), motor (regex), motor (regex), motor (regex), motor (regex)

Torna verificável parte da OWASP-A02 (configuração segura) e da A10 (erro sem detalhe ao cliente) nos arquivos de configuração que vão para produção: Hibernate alterando o schema (ddl-auto create/update), SQL e parâmetros de bind em log (dado pessoal), stack trace na resposta HTTP, Actuator com todos os endpoints expostos ou mostrando valores de ambiente, console do H2 e modo debug. Perfis dev, local e test ficam fora.

**Correção:** ddl-auto: validate (ou none) com migração versionada (Flyway/Liquibase); show-sql false e bind fora de TRACE; server.error.include-stacktrace: never; Actuator só com health e info expostos e show-values: never; H2 e debug apenas em perfil local.

## SEC-CRYPTO-001 — Criptografia fraca, TLS inseguro ou aleatoriedade previsível em segredo
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-SEC-003`
- Escopo: `**/*.java`, `**/*.kt`
- Verificação: motor (regex), motor (regex), motor (regex), motor (regex), motor (regex)

Torna verificável a OWASP-A04 no código: hash fraco (MD5, SHA-1), cifra fraca ou sem modo seguro (DES, 3DES, RC4, Blowfish, ECB, "AES" sem modo, que no JCE vira ECB), protocolo TLS antigo (SSL, TLSv1, TLSv1.1), verificação de certificado ou hostname desligada, e Random/Math.random gerando token, OTP, senha, nonce ou salt.

**Correção:** Hash: SHA-256+ (senha: Argon2/bcrypt/PBKDF2). Cifra: AES/GCM/NoPadding com IV aleatório, chave no KMS/HSM. TLS: 1.2+ sem desligar verificação (use truststore próprio em vez de trust-all). Segredo aleatório: SecureRandom.

## SEC-OBFUSC-001 — Escape Unicode fora de literal em código Java
- Severidade: `CRITICAL` · modo: `enforce` · ADR: `ADR-SEC-001`
- Escopo: `**/*.java`
- Verificação: motor (regex)

O compilador Java traduz `\uXXXX` antes da análise léxica, inclusive em comentários. Isso permite esconder imports proibidos (`org.springframework`) ou executar código "comentado" (`// \u000a codigo()`), enganando regras textuais e revisores.

**Correção:** Escreva o caractere diretamente. Escapes Unicode só são aceitos dentro de literais de string ou char.

## SEC-PAN-001 — Número de cartão (PAN) versionado
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-SEC-003`
- Escopo: `**/*`
- Verificação: motor (regex)

Nenhum número de cartão pode estar no repositório: código, configuração, fixture de teste, massa de dados ou documentação (PCI DSS: PAN só no ambiente de dados de cartão). O motor procura sequências de 13 a 19 dígitos com prefixo de bandeira e dígito de Luhn válido; os números de teste publicados pelas bandeiras (ex.: 4111 1111 1111 1111) são aceitos.

**Correção:** Remova o número e trate como incidente se for de titular real (ele continua no histórico do git). Em testes, use os números de teste das bandeiras ou um token do cofre de cartões.

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
