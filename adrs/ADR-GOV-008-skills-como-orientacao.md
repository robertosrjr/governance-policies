# ADR-GOV-008: Skills orientam, políticas decidem

## Status

Aceito — 2026-09-30.

## Contexto

Havia 17 skills do Claude Code (`C:\Developer\Workspace\java\skills`) com boas práticas
de arquitetura, qualidade, LGPD, observabilidade, resiliência, segurança de IA e
documentação, mais a `global-ai-principles`. A tentação é usá-las como prompt do
revisor. Isso repete o problema nº 3 do ADR-GOV-000: a mesma regra escrita em vários
lugares, com severidades diferentes. Algumas skills também contradiziam decisões já
tomadas; a `prompt-injection-guard`, por exemplo, mandava bloquear PR por lista de
palavras, o que o ADR-GOV-000 rejeitou.

## Decisão

- **Regra verificável vive só em `policies/*.yaml`**, com o ADR que explica o porquê.
  Skill não bloqueia nada.
- **Skill é orientação consultiva** para quem desenha ou escreve código, antes do PR. As
  regras que o assistente precisa respeitar chegam pelo arquivo gerado
  `.claude/rules/governance-policies.md`, e não por texto copiado das skills.
- O motor nunca lê skills, prompts ou configuração do repositório-alvo (ADR-GOV-000).

### Triagem das skills

| Skill | Destino |
|---|---|
| lgpd-sre-compliance | Políticas LGPD-DATA-001 e SEC-CONFIG-001 (ADR-LGPD-002, ADR-SEC-002) |
| resilience-checker | RES-IDEMP-001 (ADR-FIN-002) |
| platform-practices | SEC-CONFIG-001 |
| api-design-guidance | API-CONTRACT-001 e EVT-SCHEMA-001 (ADR-API-001) |
| architecture-guidance | Já coberta por ARCH-HEX-001/002; orientação |
| spring-logging, spring-tracing, spring-metrics | Orientação; o que é verificável já está na LGPD-LOG-001 |
| docker-compose-spec | SUP-IMG-001 (ADR-SUP-001), apontando para o Dockerfile |
| saif-skill | Base do ADR-AI-001 (gateway, modelo fixado) |
| global-ai-principles | AI-HUMAN-001, AI-FAIR-001 e AI-INV-001 (ADR-AI-002); fica em `.claude/skills` como consultora |
| security-code-review | Descartada: duplica SEC-SECRET, ARCH-HEX e QUAL-CODE |
| prompt-injection-guard | Descartada: contradiz o ADR-GOV-000 (LLM-INJ-001 fica em `warn`) |
| code-quality, testing-strategy, quality-assurance | Build (Spotless, JaCoCo) e QA, não o gate |
| service-modeling (TOGAF), tech-documentation, sre-observability | Fora do escopo ou cobertas por outras |

Além das skills, entraram regras que nenhuma delas cobria e que pesam numa instituição
financeira: FIN-MONEY-001 (ADR-FIN-001), SEC-CRYPTO-001 e SEC-PAN-001 (ADR-SEC-003),
DATA-MIG-001/002 (ADR-DATA-001), DATA-RES-001 (ADR-DATA-002), ARCH-TIME-001
(ADR-ARCH-002), SUP-DEP-001 (ADR-SUP-001) e GOV-ADR-001 (ADR-GOV-004).

### Relação com fitness functions

Cada política é uma fitness function no sentido de *Building Evolutionary
Architectures*: uma verificação objetiva e automatizada de uma característica da
arquitetura, disparada a cada PR. A plataforma soma a governança em volta: fonte única
ligada ao ADR, ciclo `audit` → `warn` → `enforce`, exceção com aprovador e prazo, e
evidência assinada. As fitness functions de runtime (latência, resiliência, custo)
ficam com observabilidade e com o gate de deploy.

## Consequências

- Uma skill nova passa pela mesma triagem: o que for verificável vira política com ADR e
  casos de eval; o resto continua como orientação.
- As skills podem evoluir livremente sem mexer no comportamento do gate.
