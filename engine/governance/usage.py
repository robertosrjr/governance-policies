"""Consumo de IA de uma execução (ADR-FINOPS-002).

Cada provedor guarda, numa `UsageLog`, o que a resposta informou: tokens e, quando o
provedor informa, o custo em dólar. O motor soma tudo no `stats.ai_usage` do resultado.
Nada aqui estima preço: o custo é o que o provedor devolveu, ou nulo.
"""

import threading


class UsageLog:
    """Acumula o consumo por (provedor, modelo). Seguro para chamadas em paralelo."""

    def __init__(self):
        self._lock = threading.Lock()
        self._rows = {}

    def record(self, provider, model, *, input_tokens=0, output_tokens=0, cost_usd=None):
        with self._lock:
            row = self._rows.setdefault((provider, model), {
                "provider": provider, "model": model, "calls": 0,
                "input_tokens": 0, "output_tokens": 0, "cost_usd": None})
            row["calls"] += 1
            row["input_tokens"] += _count(input_tokens)
            row["output_tokens"] += _count(output_tokens)
            if isinstance(cost_usd, (int, float)) and not isinstance(cost_usd, bool):
                row["cost_usd"] = (row["cost_usd"] or 0.0) + float(cost_usd)

    def rows(self):
        with self._lock:
            return [dict(row) for _, row in sorted(self._rows.items())]


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _round(cost):
    return None if cost is None else round(cost, 6)


def summarize(*providers):
    """`stats.ai_usage`: totais e uma linha por modelo, dos provedores que têm `usage`."""
    merged = {}
    for provider in providers:
        log = getattr(provider, "usage", None)
        if not isinstance(log, UsageLog):
            continue
        for row in log.rows():
            key = (row["provider"], row["model"])
            into = merged.setdefault(key, {**row, "calls": 0, "input_tokens": 0,
                                           "output_tokens": 0, "cost_usd": None})
            into["calls"] += row["calls"]
            into["input_tokens"] += row["input_tokens"]
            into["output_tokens"] += row["output_tokens"]
            if row["cost_usd"] is not None:
                into["cost_usd"] = (into["cost_usd"] or 0.0) + row["cost_usd"]
    rows = [{**row, "cost_usd": _round(row["cost_usd"])} for _, row in sorted(merged.items())]
    costs = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
    return {
        "calls": sum(row["calls"] for row in rows),
        "input_tokens": sum(row["input_tokens"] for row in rows),
        "output_tokens": sum(row["output_tokens"] for row in rows),
        "cost_usd": _round(sum(costs)) if costs else None,
        "providers": rows,
    }
