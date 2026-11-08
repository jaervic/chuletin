"""Repaso espaciado (variante de SM-2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MIN_EASE = 1.3
MAX_EASE = 3.0
MAX_INTERVAL = 365


@dataclass(slots=True)
class Schedule:
    ease: float
    interval_days: int
    repetitions: int
    lapses: int
    due_at: str


def review(
    *,
    ease: float,
    interval_days: int,
    repetitions: int,
    lapses: int,
    rating: int,
) -> Schedule:
    """Calcula el siguiente repaso.

    rating: 1 = otra vez, 2 = dificil, 3 = bien, 4 = facil.
    """
    if rating not in {1, 2, 3, 4}:
        raise ValueError("Calificacion no valida")

    ease = float(ease or 2.5)
    interval_days = int(interval_days or 0)
    repetitions = int(repetitions or 0)
    lapses = int(lapses or 0)
    now = datetime.now(timezone.utc)

    if rating == 1:
        repetitions = 0
        interval_days = 0
        lapses += 1
        ease = max(MIN_EASE, round(ease - 0.2, 2))
        due = now + timedelta(minutes=10)
    else:
        if rating == 2:
            ease = max(MIN_EASE, round(ease - 0.15, 2))
        elif rating == 4:
            ease = min(MAX_EASE, round(ease + 0.15, 2))

        repetitions += 1
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 6 if rating >= 3 else 3
        else:
            factor = 1.2 if rating == 2 else (1.3 if rating == 4 else ease)
            interval_days = max(1, round(interval_days * factor))
        interval_days = min(interval_days, MAX_INTERVAL)
        due = now + timedelta(days=interval_days)

    return Schedule(
        ease=ease,
        interval_days=interval_days,
        repetitions=repetitions,
        lapses=lapses,
        due_at=due.replace(microsecond=0).isoformat(),
    )
