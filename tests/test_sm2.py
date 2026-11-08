"""Pruebas del repaso espaciado."""

from __future__ import annotations

import pytest
from app.study.sm2 import review


def test_primer_repaso_bien_un_dia():
    schedule = review(ease=2.5, interval_days=0, repetitions=0, lapses=0, rating=3)
    assert schedule.repetitions == 1
    assert schedule.interval_days == 1
    assert schedule.ease == 2.5


def test_secuencia_normal():
    first = review(ease=2.5, interval_days=0, repetitions=0, lapses=0, rating=3)
    second = review(
        ease=first.ease,
        interval_days=first.interval_days,
        repetitions=first.repetitions,
        lapses=first.lapses,
        rating=3,
    )
    assert second.repetitions == 2
    assert second.interval_days == 6

    third = review(
        ease=second.ease,
        interval_days=second.interval_days,
        repetitions=second.repetitions,
        lapses=second.lapses,
        rating=3,
    )
    assert third.interval_days >= 14
    assert third.interval_days <= 365


def test_otra_vez_reinicia():
    schedule = review(ease=2.5, interval_days=30, repetitions=5, lapses=0, rating=1)
    assert schedule.repetitions == 0
    assert schedule.interval_days == 0
    assert schedule.lapses == 1
    assert schedule.ease < 2.5


def test_facil_suben_intervalos():
    hard = review(ease=2.5, interval_days=10, repetitions=3, lapses=0, rating=2)
    easy = review(ease=2.5, interval_days=10, repetitions=3, lapses=0, rating=4)
    assert easy.ease > hard.ease
    assert easy.interval_days > hard.interval_days


def test_limites_de_facilidad():
    low = review(ease=1.3, interval_days=1, repetitions=1, lapses=0, rating=1)
    assert low.ease >= 1.3
    high = review(ease=2.95, interval_days=10, repetitions=3, lapses=0, rating=4)
    assert high.ease <= 3.0


def test_calificacion_invalida():
    with pytest.raises(ValueError):
        review(ease=2.5, interval_days=1, repetitions=1, lapses=0, rating=9)
