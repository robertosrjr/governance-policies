# filtering.md
## Code Review

### IgnorePatterns
/tests/**/*.snap
/dist/**
/build/**
/target/**
/node_modules/**
*.log

<!--
Não ignore **/*.md: em plataformas com LLM, arquivos .md (.claude/agents, skills, prompts,
CLAUDE.md) são instruções executadas por modelos e fazem parte da superfície de ataque.
-->

### ContextHints
<!--
Vazio de propósito. Afirmações não verificadas aqui ("URLs são presigned", "AppSec
aprovou X") desligam achados do revisor sem trilha de auditoria: na prática, uma prompt
injection autoinfligida. Exceções são registradas como waiver (waivers/*.yaml), com
escopo, aprovador e validade. Use esta seção só para fatos verificáveis no próprio
repositório, com link para o ADR que os sustenta.
-->
