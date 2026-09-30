# ADR-AI-001: Aplicações usam IA pelo gateway corporativo e com modelo fixado

## Status

Proposto — 2026-09-30. Depende da existência do gateway corporativo de IA.

## Contexto

O ADR-GOV-000 separou dois produtos: IA governando código (este gate) e segurança de
aplicações de IA em produção. O segundo chega pelos PRs: um time adiciona o SDK de um
provedor e passa a enviar dado de cliente a um terceiro sem contrato avaliado (LGPD
Art. 33, Resolução CMN 4.893), sem remoção de dado pessoal, sem limite de custo e sem
trilha de auditoria. E um alias `latest` troca o modelo sem aviso, invalidando o eval
que aprovou o comportamento. É o mesmo problema que o gate resolveu para si no
`engine/bundle.yaml` (ADR-GOV-000, princípio 4).

## Decisão

1. Chamadas a LLM passam pelo gateway corporativo de IA. SDK de provedor e endpoint
   público ficam restritos ao adaptador do gateway (`infrastructure/**/llm` ou
   `infrastructure/**/ai`), o único lugar autorizado a falar com o provedor.
2. O modelo é fixado por versão. Troca de modelo é PR, com o eval da aplicação.
3. Configuração de agentes (servidores MCP, ferramentas, permissões) passa pela
   GOV-SELF-001 e exige aprovação de plataforma.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [AI-GW-001](../policies/AI-GW-001.yaml) | regex de import de SDK e de endpoint público fora do adaptador | egress da rede bloqueando provedores fora do gateway |
| [AI-MODEL-001](../policies/AI-MODEL-001.yaml) | regex de modelo `latest`/`auto`/roteador | eval da aplicação |
| [GOV-SELF-001](../policies/GOV-SELF-001.yaml) | `path_changed` em `.mcp.json`, `.claude/`, `.cursor/`... | CODEOWNERS de plataforma |

Limites: chamada HTTP montada à mão para um host em variável não é vista; o controle
definitivo é o bloqueio de egress. Aliases sem sufixo (`gpt-4o`) também flutuam e não
são reconhecidos pela regex.

## Exemplos

`eval/cases/ai-gw-001-*.yaml` e `eval/cases/ai-model-001-*.yaml`.

## Consequências

- Entram em `warn` até o gateway existir; sem ele, a correção sugerida não é possível.
