# ADR-ARCH-001: Isolamento do domínio na Arquitetura Hexagonal

## Status

Aceito. Substitui o antigo "ADR-001" deste repositório (renumerado para evitar colisão
com o ADR-001 da PoC `virtualthreads`, que trata do pipeline de IA).

## Contexto

Na Arquitetura Hexagonal (Ports and Adapters), o núcleo da aplicação contém só regras de
negócio. Acoplar o domínio a frameworks (Spring) ou ORMs (JPA/Jakarta Persistence)
dificulta testes unitários, impede a troca de tecnologia e mistura detalhes de banco ou
de framework web às entidades de negócio.

## Decisão

1. Classes em `domain` são agnósticas de framework: não referenciam `org.springframework`,
   `jakarta.persistence` nem `javax.persistence`.
2. `domain` e `application` não referenciam classes de `infrastructure`. A dependência
   aponta para dentro: `infrastructure -> application -> domain`.

## Verificação

| Política | Motor (diff) | Build (bytecode) |
|---|---|---|
| [ARCH-HEX-001](../policies/ARCH-HEX-001.yaml) | regex sobre linhas adicionadas: import, import static e nome qualificado | ArchUnit `domain_should_not_depend_on_frameworks` |
| [ARCH-HEX-002](../policies/ARCH-HEX-002.yaml) | regex sobre linhas adicionadas | ArchUnit `application_should_not_depend_on_infrastructure` |

As duas camadas são complementares: a regex dá retorno no PR e cobre repositórios sem
ArchUnit; o ArchUnit analisa o bytecode e pega o que texto não pega (ex.: dependência
transitiva por tipo de retorno). Ofuscação por escape Unicode (`org.springframework`)
é coberta por [SEC-OBFUSC-001](../policies/SEC-OBFUSC-001.yaml).

O LLM **não** participa destas políticas: são 100% determinísticas (ver ADR-GOV-000,
princípio 2).

Severidade: `CRITICAL`, modo `enforce`. Uma versão anterior deste ADR dizia `HIGH`,
enquanto o README dos auditores e o orquestrador da PoC diziam `CRITICAL`. A severidade
agora é a da política e só existe nela.

## Exemplos

Não conforme:

```java
package com.empresa.produto.domain.model;

import jakarta.persistence.Entity;
import org.springframework.stereotype.Component;

@Entity
@Component
public class Cliente { /* ... */ }
```

Também não conforme (escapava da regra textual antiga, que só olhava `import X.`):

```java
@org.springframework.stereotype.Component
public class Cliente { /* ... */ }
```

Conforme:

```java
package com.empresa.produto.domain.model;

public class Cliente {
    private final Long id;
    private final String nome;

    public Cliente(Long id, String nome) {
        if (nome == null || nome.isBlank()) {
            throw new IllegalArgumentException("Nome do cliente é obrigatório.");
        }
        this.id = id;
        this.nome = nome;
    }
}
```

Os exemplos executáveis ficam em `eval/cases/arch-*.yaml`.

## Remediação

1. Remova as anotações Spring (`@Component`, `@Service`, `@Autowired`) e JPA (`@Entity`,
   `@Table`, `@Column`, `@Id`) das classes de `domain`.
2. Mova a persistência para `infrastructure/persistence` (ex.: `ClienteEntity`).
3. Converta entre `ClienteEntity` e `Cliente` com mappers na infraestrutura.
