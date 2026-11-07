"""Pruebas de la busqueda por palabras clave (sin cargar embeddings)."""

from __future__ import annotations

from app.search.retriever import _fts_match


def test_descarta_palabras_vacias():
    assert _fts_match("Que es la mitosis?") == '"mitosis"*'


def test_conserva_terminos_tecnicos():
    match = _fts_match("Como se calcula la hipotenusa")
    assert '"hipotenusa"*' in match
    assert '"como"*' not in match


def test_sin_terminos_utiles():
    assert _fts_match("que es la de el") == ""


def test_evita_operadores_fts():
    # Los caracteres raros no deben llegar al motor FTS5.
    assert _fts_match('" OR * --') == ""
