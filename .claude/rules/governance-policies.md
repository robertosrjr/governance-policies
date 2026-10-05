# Políticas de governança (Claude Code)

<!-- GERADO por `python -m governance export`. Edite policies/*.yaml. -->

Ao gerar ou editar código, respeite as políticas abaixo. As `enforce` + `CRITICAL`
bloqueiam o merge no pipeline central; as `warn` aparecem como alerta.

## AI-FAIR-001 — Dado pessoal sensível como entrada de modelo ou regra de decisão
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-AI-002`
- Escopo: `**/src/main/**/*.java`, `**/src/main/**/*.kt`, `**/*.py`, `**/*.sql`
- Verificação: LLM consultivo

Origem racial ou étnica, religião, opinião política, filiação sindical, saúde, vida sexual, dado genético ou biométrico (dado pessoal sensível, LGPD Art. 5º II) não entram em modelo, score, regra de aprovação, preço, limite ou segmentação de clientes. Além do tratamento restrito do Art. 11, usar esses dados para decidir é discriminação, e variáveis aparentemente neutras podem reproduzi-la. A regex marca linhas que citam esses atributos e o Jev julga se o dado vira entrada de decisão (ADR-GOV-002).

**Correção:** Remova o atributo das features e da regra. Se houver base legal e finalidade aprovada por privacidade (ex.: acessibilidade), registre em ADR e no inventário de IA, e mantenha teste de viés que compare resultados entre grupos antes de cada nova versão do modelo.

## AI-GW-001 — Chamada a LLM fora do gateway corporativo de IA
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-AI-001`
- Escopo: `**/*.java`, `**/*.kt`, `**/*.py`, `**/*.ts`, `**/*.js`, `**/*.yml`, `**/*.yaml`, `**/*.properties`, `**/*.json`, `**/.env*`
- Verificação: motor (regex), motor (regex)

Aplicação chama LLM só pelo gateway corporativo de IA, que concentra contrato com o provedor (retenção, região), remoção de dado pessoal, limite de custo, auditoria e troca de modelo. SDK de provedor (OpenAI, Anthropic, Gemini, Bedrock, adaptadores de Spring AI e LangChain4j) e endpoint público de provedor ficam restritos ao adaptador do gateway (`infrastructure/**/llm` ou `infrastructure/**/ai`).

**Correção:** Use o cliente do gateway corporativo de IA. Se o gateway é compatível com a API de um provedor, o SDK pode ser usado apenas no adaptador em `infrastructure/**/llm`, com a URL base do gateway vinda de configuração.

## AI-HUMAN-001 — Decisão sobre cliente tomada só pela IA, sem revisão humana nem contestação
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-AI-002`
- Escopo: `**/src/main/**/*.java`, `**/src/main/**/*.kt`, `**/*.py`
- Verificação: LLM consultivo

A saída de um modelo de IA não decide sozinha algo que afeta o cliente: aprovar ou negar crédito, definir limite ou preço, bloquear conta ou cartão, recusar sinistro. O titular tem direito a pedir revisão de decisão tomada unicamente por tratamento automatizado (LGPD Art. 20), e só uma pessoa responde pela decisão. A regex marca as linhas que chamam um modelo de IA e o Jev julga se o resultado vira a decisão sem passar por pessoa nem ser registrado para contestação (ADR-GOV-002).

**Correção:** Use a IA como recomendação: encaminhe a sugestão, com a justificativa, para um analista decidir; ou, se a decisão automática for aprovada pelo comitê, registre modelo, versão, entrada, saída e justificativa, e ofereça canal de revisão humana ao cliente.

## AI-INV-001 — Uso novo de IA sem registro no inventário de IA
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-AI-002`
- Escopo: `**/*.java`, `**/*.kt`, `**/*.py`, `**/*.ts`, `**/*.js`
- Verificação: motor (requires_companion)

Todo uso de IA na organização está no inventário de IA, com finalidade, dono, dados usados, modelo, avaliação de risco e se a decisão afeta clientes. Sem inventário não há como auditar, explicar uma decisão nem responder ao titular. O motor aponta o arquivo que passa a importar um cliente de modelo de IA (SDK de provedor, Spring AI, LangChain4j, LangChain) que não importava antes, quando o PR não altera o inventário (`ai-inventory.yaml`) nem um model card.

**Correção:** Adicione ou atualize a entrada do caso de uso em `ai-inventory.yaml` (ou o model card em `docs/ai/`) no mesmo PR: finalidade, dono, dados, modelo e versão, avaliação de risco, se há decisão sobre cliente e como é a revisão humana.

## AI-MODEL-001 — Modelo de IA não fixado (alias latest, auto ou roteador)
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-AI-001`
- Escopo: `**/*.java`, `**/*.kt`, `**/*.py`, `**/*.ts`, `**/*.js`, `**/*.yml`, `**/*.yaml`, `**/*.properties`, `**/*.json`
- Verificação: motor (regex)

Um modelo de IA em produção é versionado como qualquer dependência: alias `latest`, `auto` ou roteador trocam o modelo sem aviso, e a avaliação (eval) que aprovou o comportamento deixa de valer. É a mesma regra que o próprio gate segue no `engine/bundle.yaml`. O motor aponta atribuição de modelo terminada em -latest, :latest, auto ou router.

**Correção:** Fixe a versão do modelo (ex.: um id com data ou número de versão) e troque de modelo por PR, com o eval da aplicação rodando antes do merge.

## API-CONTRACT-001 — Mudança incompatível em contrato OpenAPI publicado
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-API-001`
- Escopo: `**/openapi*.yaml`, `**/openapi*.yml`, `**/openapi*.json`, `**/*.openapi.yaml`, `**/*.openapi.yml`, `**/swagger*.yaml`, `**/swagger*.yml`, `**/swagger*.json`
- Verificação: motor (contract)

Contrato de API publicado não quebra consumidores: nada é removido nem passa a ser obrigatório. O motor compara a versão da base com a do PR e aponta caminho ou operação removidos, parâmetro ou propriedade de corpo obrigatórios novos, resposta 2xx removida e propriedade removida ou com tipo alterado na resposta. Contrato novo não dispara; contrato removido dispara.

**Correção:** Mudança compatível: adicione campos opcionais e novas operações. Mudança que quebra: publique uma nova versão (/v2) ao lado da atual, com data de descontinuação da antiga combinada com os consumidores e registrada em ADR.

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

## ARCH-TIME-001 — Relógio e fuso implícitos no domínio ou nos casos de uso
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-ARCH-002`
- Escopo: `**/src/main/**/domain/**/*.java`, `**/src/main/**/domain/**/*.kt`, `**/src/main/**/application/**/*.java`, `**/src/main/**/application/**/*.kt`
- Verificação: motor (regex)

Regra de negócio que depende de data (corte, D+1, vencimento, horário de Pix, dia útil) não pode ler o relógio e o fuso da máquina. `LocalDate.now()`, `new Date()`, `System.currentTimeMillis()` e `ZoneId.systemDefault()` tornam o resultado dependente do servidor (UTC no contêiner, America/Sao_Paulo na estação), impossível de testar na virada do dia e impossível de reproduzir numa auditoria. O relógio entra como dependência (`Clock`) e o fuso é explícito.

**Correção:** Injete um `java.time.Clock` (ou uma porta `Relogio`) e use `LocalDate.now(clock)`; defina o fuso de negócio explicitamente (`ZoneId.of("America/Sao_Paulo")`) ou trabalhe em UTC e converta na borda. Nos testes, use `Clock.fixed(...)`.

## DATA-MIG-001 — Migração de banco já versionada foi editada, renomeada ou removida
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-DATA-001`
- Escopo: `**/db/migration/**/V*__*.sql`, `**/db/migration/V*__*.sql`
- Verificação: motor (path_changed)

Uma migração versionada (Flyway V<versão>__<descrição>.sql) que já existe na base pode ter rodado em homologação e produção. Editá-la faz o checksum divergir (a aplicação não sobe) ou, pior, faz ambientes diferentes terem schemas diferentes. O schema só evolui com uma migração nova. O motor aponta arquivo de migração modificado, renomeado ou removido; arquivo novo é o caminho correto e não dispara.

**Correção:** Desfaça a alteração na migração existente e crie uma nova (V<próxima versão>__...) com a correção. Se a migração ainda não saiu do seu branch, peça waiver com o commit.

## DATA-MIG-002 — Mudança destrutiva de schema sem expand/contract
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-DATA-001`
- Escopo: `**/db/migration/**/*.sql`, `**/db/changelog/**/*.sql`
- Verificação: motor (regex)

DROP de tabela, coluna, view ou schema, RENAME, troca de tipo, NOT NULL em coluna existente, TRUNCATE e DELETE sem WHERE numa migração quebram a versão da aplicação que ainda está rodando durante o deploy (rolling update, blue/green) e não têm volta sem restore. A mudança destrutiva segue expand/contract: primeiro adiciona e migra, e só remove numa release posterior, depois que nenhuma versão em produção usa o objeto.

**Correção:** Divida em etapas: (1) expand: crie a coluna/tabela nova e escreva nas duas; (2) migre os dados; (3) contract: remova o antigo em outra release, com ADR ou registro de mudança aprovado por dados. Mantenha backup verificado antes do contract.

## DATA-RES-001 — Infraestrutura em região fora da lista aprovada (residência de dados)
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-DATA-002`
- Escopo: `**/*.tf`, `**/*.tfvars`
- Verificação: motor (regex)

Dado de cliente fica em região aprovada (Brasil) salvo decisão registrada. Provisionar recurso em outra região é transferência internacional (LGPD Art. 33) e contratação de nuvem sujeita à Resolução CMN 4.893. O motor aponta `region`/`location` do Terraform fora de sa-east-1 (AWS), southamerica-east1/southamerica-west1 (GCP) e brazilsouth/brazilsoutheast (Azure). Serviços globais que exigem outra região (ex.: certificado do CloudFront em us-east-1) usam waiver com justificativa.

**Correção:** Use a região aprovada. Se o serviço não existir no Brasil ou for global, registre a decisão (ADR e avaliação de privacidade) e peça waiver restrito ao arquivo.

## EVT-SCHEMA-001 — Mudança incompatível em schema de evento (Avro)
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-API-001`
- Escopo: `**/*.avsc`
- Verificação: motor (contract)

Schema de evento publicado mantém compatibilidade nos dois sentidos (produtor novo com consumidor antigo e vice-versa), porque produtores e consumidores são implantados em momentos diferentes e eventos antigos ficam retidos no tópico. O motor compara a base com o PR e aponta campo novo sem default, campo removido sem default, tipo alterado sem promoção válida (int→long é aceito) e símbolo de enum removido.

**Correção:** Adicione campos sempre com default; remova só campos que têm default; não troque tipos. Mudança que quebra vira um novo tópico ou um novo schema versionado, com migração dos consumidores registrada em ADR. Mantenha também a checagem do Schema Registry no deploy.

## FIN-MONEY-001 — Aritmética monetária com tipo binário ou sem arredondamento explícito
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-FIN-001`
- Escopo: `**/src/main/**/*.java`, `**/src/main/**/*.kt`
- Verificação: motor (regex), motor (regex), motor (regex)

Valor monetário (valor, saldo, preço, juros, tarifa, taxa, montante) não pode usar double/float: o tipo binário não representa centavos e o erro se acumula em juros, rateio e conciliação. BigDecimal não pode nascer de literal double, e divide/setScale precisam de RoundingMode explícito (sem ele, dízima vira ArithmeticException em produção e a regra de arredondamento fica implícita). O motor cobre a declaração, o literal e a chamada numa mesma linha; tipo inferido fica com a revisão humana.

**Correção:** Use BigDecimal (ou um value object Dinheiro no domínio) criado com BigDecimal.valueOf(...) ou a partir de String, e informe o RoundingMode definido pelo produto (ex.: divide(b, 2, RoundingMode.HALF_EVEN), setScale(2, RoundingMode.HALF_EVEN)).

## FINOPS-K8S-001 — Contêiner Kubernetes sem requests e limits de recursos
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-FINOPS-001`
- Escopo: `**/*.yaml`, `**/*.yml`
- Verificação: motor (structured)

Contêiner de Deployment, StatefulSet, DaemonSet, ReplicaSet, Job, CronJob ou Pod sem `resources.requests` não é dimensionado pelo escalonador: o cluster não sabe quanto reservar e o time não sabe quanto paga, e sem `resources.limits.memory` um vazamento de memória derruba o nó dos vizinhos. As quantidades exigidas são os parâmetros da regra. CPU em `limits` não é exigido: o limite de CPU causa estrangulamento (throttling) mesmo com o nó ocioso, e o `requests.cpu` já garante a reserva. O motor lê o manifesto YAML (arquivos de outro tipo, sem `kind` de workload, são ignorados) e só aponta o contêiner que o PR criou ou alterou. Template Helm (`{{ }}`) não é YAML até ser renderizado e não é lido: renderize com `helm template` e versione o resultado, ou valide no cluster.

**Correção:** Acrescente ao contêiner `resources: { requests: { cpu: 250m, memory: 256Mi }, limits: { memory: 512Mi } }` com valores medidos (use o histórico do serviço, não um palpite). Se o serviço usa VPA ou um perfil padrão (LimitRange) do namespace, documente no ADR do serviço e peça waiver.

## FINOPS-SHUTDOWN-001 — Spring configurado para encerrar de imediato, sem desligamento gracioso
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-FINOPS-001`
- Escopo: `**/src/main/resources/application*.yml`, `**/src/main/resources/application*.yaml`, `**/src/main/resources/application*.properties`
- Verificação: motor (regex)

Carga barata (instância Spot, escala para zero, rolling update frequente) só funciona se o serviço termina o que está processando ao receber o SIGTERM. `server.shutdown: immediate` derruba as requisições em andamento: numa interrupção do Spot ou num deploy, vira pedido perdido ou duplicado. O motor aponta a configuração explícita de encerramento imediato. O que ele não vê: a ausência da configuração (depende do padrão da versão do Spring Boot) e o comportamento real, que é um teste de execução, não de diff (ADR-FINOPS-001).

**Correção:** Use `server.shutdown: graceful` e um `spring.lifecycle.timeout-per-shutdown-phase` menor que o `terminationGracePeriodSeconds` do pod (30s por padrão). Prove com um teste de encerramento no ambiente de staging: envie SIGTERM durante uma requisição longa e confira que ela termina e que a operação é idempotente.

## FINOPS-TAG-001 — Recurso de infraestrutura sem as tags de alocação de custo
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-FINOPS-001`
- Escopo: `**/*.tf`
- Verificação: motor (structured)

Todo recurso que gera custo traz as tags de alocação (CostCenter e Owner): sem elas, a fatura não se atribui a um centro de custo nem a um dono, e o FinOps não consegue cobrar, orçar ou desligar o que ninguém reclama. O motor lê o Terraform do PR e soma as tags do recurso com as `default_tags` do provider do mesmo diretório, resolvendo `locals` e `merge`. Só aponta o que dá para afirmar: tag vinda de variável, de módulo ou de `for_each` não é afirmada, e módulo filho (diretório sem provider) herda as tags do módulo raiz. Só entra o recurso que o PR criou ou alterou. A trava definitiva é a política de tags da conta de nuvem (ADR-FINOPS-001); esta regra avisa antes.

**Correção:** Defina as tags no provider, uma vez, e todo recurso as herda: `provider "aws" { default_tags { tags = { CostCenter = "...", Owner = "..." } } }`. Ou declare `tags = { CostCenter = "...", Owner = "..." }` no recurso (ou em `locals` e `merge`). O valor de CostCenter vem do cadastro de centros de custo da empresa.

## GOV-ADR-001 — Decisão estrutural sem ADR no mesmo PR
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-GOV-004`
- Escopo: `**/pom.xml`, `**/build.gradle`, `**/build.gradle.kts`, `**/settings.gradle`, `**/settings.gradle.kts`, `**/docker-compose*.yml`, `**/docker-compose*.yaml`, `**/compose*.yml`, `**/compose*.yaml`
- Verificação: motor (requires_companion), motor (requires_companion), motor (requires_companion)

Uma decisão estrutural vem acompanhada do seu registro: o PR que adiciona uma dependência nova, um módulo novo ou um datastore/broker novo traz um ADR (novo ou atualizado) no mesmo PR. O motor só conta o que não existia na base: trocar a versão de uma dependência existente não dispara.

**Correção:** Adicione ou atualize um ADR em `adrs/`, `docs/adr/` ou `docs/architecture/decisions/` explicando o porquê, as alternativas e as consequências da decisão.

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

## RES-IDEMP-001 — Retry automático em escrita financeira sem chave de idempotência
- Severidade: `CRITICAL` · modo: `warn` · ADR: `ADR-FIN-002`
- Escopo: `**/src/main/**/*.java`, `**/src/main/**/*.kt`
- Verificação: LLM consultivo

Retry numa operação que movimenta dinheiro (pagamento, transferência, débito, lançamento) só é seguro se o destino deduplicar pela mesma chave de idempotência. Sem ela, um timeout depois do processamento vira cobrança ou transferência em dobro. A regex marca as linhas com retry (@Retryable, RetryTemplate, Resilience4j, retry() do Reactor) e o Jev julga se a operação é uma escrita financeira sem chave (ADR-GOV-002). Consultivo até o eval justificar bloqueio.

**Correção:** Gere a chave de idempotência antes da primeira tentativa e reenvie a mesma chave em cada retry (header Idempotency-Key ou campo do comando); no destino, deduplique pela chave. Sem isso, não faça retry automático: devolva o erro e reconcilie.

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

## SUP-DEP-001 — Dependência SNAPSHOT ou com versão flutuante
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-SUP-001`
- Escopo: `**/pom.xml`, `**/build.gradle`, `**/build.gradle.kts`, `**/gradle/libs.versions.toml`
- Verificação: motor (regex)

Dependência SNAPSHOT, faixa de versão ([1.0,2.0), 1.+), LATEST, RELEASE ou latest.release faz o mesmo commit gerar artefatos diferentes em dias diferentes: o build deixa de ser reproduzível, o SBOM deixa de corresponder ao que roda e uma versão comprometida entra sem revisão. A versão própria do projeto (`<version>` do pom) não é verificada.

**Correção:** Fixe a versão exata (1.4.2), de preferência num BOM ou catálogo de versões, e deixe a atualização para um bot de dependências (Renovate/Dependabot) com PR revisado.

## SUP-IMG-001 — Imagem de contêiner sem digest, rodando como root ou baixando código sem verificação
- Severidade: `MAJOR` · modo: `warn` · ADR: `ADR-SUP-001`
- Escopo: `**/Dockerfile`, `**/Dockerfile.*`, `**/*.Dockerfile`, `**/Containerfile`
- Verificação: motor (regex), motor (regex), motor (regex)

Imagem base referenciada só por tag (`eclipse-temurin:21-jre`) muda sem aviso quando a tag é republicada: o mesmo Dockerfile gera imagens diferentes e uma imagem comprometida entra sem revisão. Contêiner com `USER root` amplia o impacto de qualquer falha. `ADD` de URL e `curl | sh` executam código baixado sem verificação de integridade. O registry aprovado depende da organização e fica para quando ela for definida (ADR-SUP-001).

**Correção:** Fixe a imagem por digest (`imagem:tag@sha256:...`), rode com usuário sem privilégio (`USER 10001`), baixe artefatos com checksum verificado (`curl -o x && sha256sum -c`) e prefira imagens do registry corporativo.
