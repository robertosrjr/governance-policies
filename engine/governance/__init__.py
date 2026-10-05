"""Motor de governança: avalia políticas-as-código sobre as mudanças de um PR.

Camadas (ver adrs/ADR-GOV-000):
- T0 determinístico: regras regex/caminho declaradas nas políticas. É o piso e bloqueia.
- T1 LLM: só políticas semânticas; só ACRESCENTA achados e só bloqueia quando a
  política declara `llm.blocking: true` (exige resultado de eval).
"""

__version__ = "1.10.0"
