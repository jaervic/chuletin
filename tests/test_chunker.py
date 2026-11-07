"""Pruebas del troceado de texto."""

from __future__ import annotations

from app.ingest.chunker import chunk_blocks
from app.ingest.types import Block


def test_respeta_el_limite_de_caracteres():
    blocks = [Block(text=("Una frase de prueba. " * 120).strip(), page=1)]
    chunks = chunk_blocks(blocks, max_chars=600, overlap_chars=80)
    assert len(chunks) > 1
    assert all(chunk.n_chars <= 620 for chunk in chunks)


def test_conserva_las_paginas():
    blocks = [
        Block(text=("Contenido de la pagina uno. " * 30).strip(), page=1),
        Block(text=("Contenido de la pagina dos. " * 30).strip(), page=2),
    ]
    chunks = chunk_blocks(blocks, max_chars=500, overlap_chars=60)
    assert any(chunk.page_from == 1 for chunk in chunks)
    assert any(chunk.page_from == 2 for chunk in chunks)


def test_arrastra_el_titulo_de_seccion():
    blocks = [
        Block(text="Tema 1: La celula", is_heading=True),
        Block(text=("La celula es la unidad basica. " * 30).strip(), page=1),
    ]
    chunks = chunk_blocks(blocks, max_chars=600)
    assert chunks
    assert chunks[0].heading == "Tema 1: La celula"


def test_no_genera_fragmentos_vacios():
    chunks = chunk_blocks([Block(text="   \n\n  "), Block(text="")])
    assert chunks == []


def test_texto_muy_largo_se_parte_por_palabras():
    blocks = [Block(text=("palabra " * 2000).strip(), page=3)]
    chunks = chunk_blocks(blocks, max_chars=500, overlap_chars=50)
    assert len(chunks) > 5
    assert all(chunk.page_from == 3 for chunk in chunks)
