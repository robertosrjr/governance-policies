# ADR-GOV-007: Release e versionamento do repositório central

## Status

Aceito — 2026-09-30.

## Contexto

Os repositórios-alvo executam o workflow central numa **tag** deste repositório. Uma
tag é, na prática, uma versão de produção do controle de mudança de todos os times.
Em 2026-09-30, o primeiro teste ponta a ponta na PoC mostrou o custo de uma release
sem verificação no destino: as pastas `.claude/worktrees/agent-*` (worktrees temporárias
de agentes do Claude Code) entraram no commit da v1.4.0 como submódulos sem
`.gitmodules`. O `actions/checkout` falha ao limpar credenciais de submódulos, então as
tags **v1.4.0 a v1.7.0** bloqueavam todo PR (fail-closed). Nenhum teste local pegou:
o problema só aparece quando o motor é baixado por outro repositório.

## Decisão

### Três versões, uma tag

| Versão | Onde | Sobe quando |
|---|---|---|
| Tag `vX.Y.Z` | git | Toda release; é o que o repositório-alvo fixa no `uses:` |
| `__version__` do motor | `engine/governance/__init__.py`, `pyproject.toml` | Junto com a tag (mesmo número), para o `result.json` dizer qual release avaliou |
| `bundle_version` | `engine/bundle.yaml` | Só quando muda o que define o comportamento do revisor: modelo, prompt, orçamento ou políticas |
| `schema_version` | `result.json` | Só quando muda o formato da evidência; o gate de deploy tem de conhecer a versão |

### Antes de publicar uma tag

1. `pytest`, `validate`, `export --check` e `eval` determinístico verdes (o CI faz).
2. Mudou o bundle: `eval --llm --repeat 5` aprovado. O resultado (`eval-llm-*.json`) não
   é versionado aqui (é artefato do CI e, com a retenção ligada, evidência no bucket);
   os números vão na mensagem do commit da release.
3. `validate` recusa submódulo versionado (`git ls-files` com modo 160000), e
   `.claude/worktrees/` está no `.gitignore`.
4. **Smoke test no destino:** um PR num repositório piloto apontando para a tag nova
   antes de anunciá-la aos times.

### Tag publicada não se move

Mover uma tag muda o código que já foi atestado com ela e invalida a evidência dos PRs
avaliados. Release com defeito é corrigida com uma nova versão (v1.7.1) e a anterior é
marcada como defeituosa nas releases do GitHub.

## Alternativas rejeitadas

| Alternativa | Motivo |
|---|---|
| Repositórios-alvo apontarem para `main` | Toda mudança aqui entraria sem release; a atestação não diria qual versão avaliou |
| Mover a tag para o commit corrigido | Quebra a rastreabilidade da evidência já atestada |
| Versionar os `eval-llm-*.json` no repositório | Arquivos grandes e gerados; a evidência de eval vive no CI e no bucket |

## Consequências

- Correção de uma release é sempre uma versão nova, e os repositórios-alvo atualizam o
  `uses:`. Com organização, é uma mudança só no ruleset.
- O smoke test no repositório piloto passa a fazer parte da release.
