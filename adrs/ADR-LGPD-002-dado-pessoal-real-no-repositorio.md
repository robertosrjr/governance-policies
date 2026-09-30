# ADR-LGPD-002: Repositório não é ambiente para dado pessoal real

## Status

Aceito — 2026-09-29.

## Contexto

LGPD-LOG-001 impede que o código envie dado pessoal a logs. Falta o caso anterior: o
dado pessoal dentro do próprio repositório, em massa de teste copiada de produção, em
arquivo de carga, em exemplo de documentação ou em configuração. O repositório é
clonado em estações, runners de CI e ferramentas de terceiros; nenhum desses ambientes
foi avaliado para tratar dado de titular (LGPD Art. 6º III, minimização; Art. 46,
segurança).

## Decisão

- CPF com dígito verificador válido não entra no repositório.
- Massa de teste usa CPF com dígito verificador inválido ou gerado em tempo de teste.
- Teste de validador de CPF que exige número válido usa waiver com caminho restrito.
- O motor detecta CPF com ou sem máscara e valida os dígitos. Sequências repetidas
  (111.111.111-11) são tratadas como sintéticas.

CNPJ fica fora da regra: CNPJ de empresa não é dado pessoal e a própria instituição
precisa versionar o seu (ex.: configuração de Pix). O validador `cnpj` existe no motor
para a remoção antes do envio ao LLM (ADR-GOV-003).

## Verificação

| Política | Motor (diff) | Outras camadas |
|---|---|---|
| [LGPD-DATA-001](../policies/LGPD-DATA-001.yaml) | regex + validador `cpf` | DLP corporativo; varredura de histórico sob demanda |

Limites: o motor vê só linhas adicionadas; dado já versionado exige varredura do
histórico. Qualquer sequência de 11 dígitos tem ~1% de chance de passar na validação
(ex.: telefone com DDD), o que gera falso positivo raro. CPF gerado por ferramenta
online é válido e dispara, como deve: não há como distinguir de um CPF real.

## Exemplos

`eval/cases/lgpd-data-001-*.yaml`.

## Consequências

- Entra em `warn` (ADR-GOV-003). Times com massa de teste grande precisam migrar para
  geração sintética antes do `enforce`.
