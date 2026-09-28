# Plataforma de Governança e SecLLMOps

Políticas-como-código avaliadas em todo Pull Request da organização, com regras
determinísticas como base, revisão semântica por LLM apenas como camada aditiva, e
evidência atestada por commit.

Decisão de arquitetura: [ADR-GOV-000](adrs/ADR-GOV-000-modelo-de-governanca.md).
Origem: a PoC `virtualthreads` (pipeline Gemini no PR) e o roteiro em
`docs/Governança SecLLMOps Enterprise.docx`.

## Como funciona

1. O ruleset da organização exige o workflow
   [governance-required.yml](.github/workflows/governance-required.yml) em todo PR, numa
   ref fixada deste repositório. O repo-alvo não consegue alterá-lo.
2. O workflow faz checkout do PR (como dado) e do motor (desta revisão), roda o gitleaks
   nos commits do PR e o motor sobre o diff.
3. O motor escolhe as políticas cujo `scope` casa com os arquivos alterados e aplica:
   - **T0 determinístico** (regex, path): bloqueia em `enforce` + `CRITICAL`;
   - **T1 LLM** (só políticas com `enforcement.llm`): recebe o conteúdo sem segredos,
     delimitado por uma tag com nonce; só acrescenta achados; só bloqueia com
     `llm.blocking: true`, que exige evidência de eval.
4. Waivers válidos (aprovador ≠ solicitante, até 90 dias) são descontados.
5. Saídas: comentário no PR, SARIF no Code Scanning, `result.json` atestado (Sigstore) e
   guardado como artefato. Qualquer erro bloqueia.

## Políticas

| Id | Modo | Camadas |
|---|---|---|
| ARCH-HEX-001 domínio sem Spring/JPA | enforce | regex + ArchUnit no build |
| ARCH-HEX-002 camadas internas sem infrastructure | enforce | regex + ArchUnit no build |
| LGPD-LOG-001 dado pessoal em log/trace/métrica | enforce | regex (bloqueia) + LLM (consultivo) |
| SEC-SECRET-001 credencial versionada | enforce | regex + gitleaks |
| SEC-UNICODE-001 caracteres invisíveis/bidi | enforce | regex |
| SEC-OBFUSC-001 escape Unicode fora de literal (Java) | enforce | regex |
| LLM-INJ-001 texto dirigido a IA | warn | regex + LLM (sinal) |
| GOV-SELF-001 mudança em CI/instruções de IA | warn | path |
| QUAL-CODE-001 regras objetivas de qualidade | warn | LLM |
| OWASP-A01/A02/A03/A04/A10 | audit | só exportadas para o AWS Security Agent |

## Adoção em um repositório-alvo

1. Copie [templates/target-repo/CODEOWNERS](templates/target-repo/CODEOWNERS) para
   `.github/CODEOWNERS` do repo-alvo.
2. Remova o workflow de IA local (na PoC: `.github/workflows/ai-governance.yml` e
   `.github/scripts/orchestrator.py`), que lia prompts do próprio PR.
3. Mantenha o ArchUnit no build: é a verificação de arquitetura sobre o bytecode.

## Configuração da organização (uma vez)

1. Publique uma tag deste repositório (ex.: `v1.0.0`) e aplique
   [templates/org-ruleset.json](templates/org-ruleset.json) com o `repository_id` dele.
2. Secrets da organização: `GEMINI_API_KEY` e, se este repositório for privado,
   `GOVERNANCE_READ_TOKEN` (somente leitura neste repositório).
3. Ajuste `GOVERNANCE_REPOSITORY` no workflow se o nome do repositório mudar.
4. Confirme no primeiro PR que `github.workflow_sha` aponta para a revisão deste
   repositório: se não apontar, o checkout do motor falha e o PR é bloqueado
   (fail-closed), sem aprovar nada indevidamente.

## Modo conta pessoal (sem organização, provisório)

Sem organização não há required workflow. O repo-alvo chama o workflow central:

1. Copie [templates/target-repo/governance.yml](templates/target-repo/governance.yml) para
   `.github/workflows/governance.yml` do repo-alvo, com a mesma tag no `uses:` e em
   `governance_ref`.
2. Secret `GEMINI_API_KEY` no repo-alvo. Se este repositório for privado, libere-o em
   *Settings → Actions → General → Access* para os repositórios da sua conta.
3. Ruleset do repo-alvo no branch principal: exigir PR e o status check
   `governance / governance`. Rulesets em repositório privado exigem plano Pro.

Limite conhecido: o PR pode editar ou remover a chamada (ADR-GOV-000, alternativas
rejeitadas). O CODEOWNERS e o check obrigatório só reduzem esse risco. Migre para o
ruleset da organização antes de tratar o resultado como controle.

## Gate de deploy

O deploy de um commit só prossegue com um `result.json` atestado e aprovado para ele:

```bash
gh run download <run-id> -R org/app -n "governance-${SHA}" -D evidence
gh attestation verify evidence/result.json -R org/app \
  --predicate-type https://github.com/robertosrjr/governance-policies/governance-result/v1 \
  --signer-workflow robertosrjr/governance-policies/.github/workflows/governance-required.yml
jq -e --arg sha "$SHA" '.status == "APPROVED" and .subject.commit == $sha' evidence/result.json
```

O `--signer-workflow` é essencial: sem ele, um workflow qualquer do repo-alvo poderia
atestar um `result.json` forjado.

Isso fecha o caso do merge feito por cima do check: sem evidência, não há deploy.

## Desenvolvimento

```bash
pip install --no-deps --require-hashes -r engine/requirements-dev.lock
python -m pytest
PYTHONPATH=engine python -m governance validate
PYTHONPATH=engine python -m governance export --check
PYTHONPATH=engine python -m governance eval
```

Regras para editar este repositório: [CLAUDE.md](CLAUDE.md).
