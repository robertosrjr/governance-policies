# ADR-DATA-002: Residência de dados em região aprovada

## Status

Proposto — 2026-09-30. A lista de regiões aprovadas é de segurança da informação e
jurídico.

## Contexto

Provisionar recurso de nuvem fora do Brasil com dado de cliente é transferência
internacional (LGPD Art. 33) e contratação de processamento sujeita à Resolução CMN
4.893. Em Terraform, isso é uma linha (`region = "us-east-1"`), fácil de copiar de um
exemplo da internet e difícil de perceber na revisão.

## Decisão

Recursos são provisionados em região aprovada: sa-east-1 (AWS), southamerica-east1 e
southamerica-west1 (GCP), brazilsouth e brazilsoutheast (Azure). Outra região exige
decisão registrada (ADR e avaliação de privacidade) e waiver restrito ao arquivo.

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [DATA-RES-001](../policies/DATA-RES-001.yaml) | regex em `region`/`location` do Terraform | SCP/Organization Policy restringindo regiões na conta; AWS Config |

Limites: região vinda de variável (`region = var.region`) só é vista onde o valor é
definido (`.tfvars`). Serviços globais que exigem us-east-1 (certificado do CloudFront,
WAF global) disparam e usam waiver. O controle definitivo é a restrição de região na
própria conta de nuvem; a regra no PR avisa antes.

## Exemplos

`eval/cases/data-res-001-*.yaml`.

## Consequências

- Entra em `warn` (ADR-GOV-003) até a lista de regiões ser aprovada.
