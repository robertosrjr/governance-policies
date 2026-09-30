# ADR-SUP-001: Build e imagem reproduzíveis

## Status

Aceito — 2026-09-30. O registry de imagens aprovado fica pendente até a organização
defini-lo.

## Contexto

A OWASP-A03 (cadeia de suprimentos) está em `audit`. Duas práticas quebram a
rastreabilidade entre o commit revisado e o que roda em produção:

- dependência SNAPSHOT, faixa de versão ou LATEST: o mesmo commit gera artefatos
  diferentes, o SBOM não corresponde ao que roda e uma versão comprometida entra sem
  revisão;
- imagem base só por tag, contêiner como root, e `ADD` de URL ou `curl | sh`: a imagem
  muda sem PR, o impacto de uma falha aumenta e código de fora entra sem checagem de
  integridade.

## Decisão

- Dependências com versão exata, atualizadas por bot (Renovate/Dependabot) com PR.
- Imagem base fixada por digest, contêiner sem root, download com checksum verificado.
- **Pendência:** imagens só do registry corporativo. A regra entra quando o nome do
  registry estiver definido; antes disso ela dispararia em todo Dockerfile.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [SUP-DEP-001](../policies/SUP-DEP-001.yaml) | regex em pom/Gradle/catálogo | SCA (osv-scanner/Trivy) e SBOM no build |
| [SUP-IMG-001](../policies/SUP-IMG-001.yaml) | regex em Dockerfile | admission controller no cluster (assinatura, digest, runAsNonRoot) |

Limites: no Maven, SNAPSHOT direto em `<version>` de dependência não é distinguível da
versão do próprio projeto numa linha; a regra cobre propriedades `*.version`. Dockerfile
sem nenhum `USER` também roda como root e não é visto pela regra de linha. `FROM` de
imagem sem tag nem registry (`FROM ubuntu`) não é visto.

## Exemplos

`eval/cases/sup-dep-001-*.yaml` e `eval/cases/sup-img-001-*.yaml`.

## Consequências

- Entram em `warn`. Fixar digest exige bot de atualização, senão a imagem envelhece.
