"""Fusion de rankings por Reciprocal Rank Fusion."""

from __future__ import annotations

from collections import defaultdict


def reciprocal_rank_fusion(
    rankings: list[list[int]], *, k: int = 60
) -> dict[int, float]:
    """Combina varias listas ordenadas de ids en una puntuacion unica.

    RRF evita tener que normalizar puntuaciones de busqueda que no son
    comparables entre si (BM25 y distancia vectorial).
    """
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item_id in enumerate(ranking):
            scores[item_id] += 1.0 / (k + rank + 1)
    return dict(scores)
