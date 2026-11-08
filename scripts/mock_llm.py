"""Servidor LLM falso para probar la interfaz sin gastar tokens.

Implementa lo minimo de la API de OpenAI: /v1/models y
/v1/chat/completions con streaming. Detecta si la peticion es de chat,
resumen o generacion de JSON (tarjetas / test) y responde en consecuencia.

Uso: uvicorn scripts.mock_llm:app --port 8099
"""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="Chuletin mock LLM")

CHAT_ANSWER = [
    "La **mitosis** es la división celular que produce dos células hijas "
    "con la misma información genética [1].\n\n",
    "Sus fases son profase, metafase, anafase y telofase [1].\n\n",
    "En un triángulo rectángulo se cumple $a^2 + b^2 = c^2$ [2].\n\n",
    "> Respuesta generada por el servidor de pruebas.\n",
]

SUMMARY = (
    "## Ideas clave\n\n"
    "- La célula es la unidad básica de la vida [1].\n"
    "- La mitosis produce dos células hijas idénticas [1].\n"
    "- El teorema de Pitágoras relaciona catetos e hipotenusa [2].\n\n"
    "## Desarrollo\n\n"
    "La mitosis consta de profase, metafase, anafase y telofase [1]. "
    "En un triángulo rectángulo se cumple $a^2 + b^2 = c^2$ [2].\n\n"
    "## Para repasar\n\n"
    "1. ¿Qué es la mitosis?\n"
    "2. ¿Qué fases tiene?\n"
    "3. ¿Qué dice el teorema de Pitágoras?\n"
)

OUTLINE = (
    "## Esquema\n\n"
    "- **La célula** [1]\n"
    "  - Membrana plasmática [1]\n"
    "  - Material genético [1]\n"
    "- **Mitosis** [1]\n"
    "  - Profase [1]\n"
    "  - Metafase [1]\n"
    "  - Anafase [1]\n"
    "  - Telofase [1]\n"
    "- **Teorema de Pitágoras** [2]\n"
    "  - $a^2 + b^2 = c^2$ [2]\n"
)

CARDS = {
    "cards": [
        {
            "front": "¿Qué es la mitosis?",
            "back": "La división celular que produce dos células hijas con la misma información genética.",
            "cite": 1,
        },
        {
            "front": "¿Cuáles son las fases de la mitosis?",
            "back": "Profase, metafase, anafase y telofase.",
            "cite": 1,
        },
        {
            "front": "¿Qué relaciona el teorema de Pitágoras?",
            "back": "Los catetos y la hipotenusa de un triángulo rectángulo.",
            "cite": 2,
        },
        {
            "front": "¿Qué tienen en común todas las células?",
            "back": "Membrana plasmática y material genético.",
            "cite": 1,
        },
    ]
}

QUIZ = {
    "items": [
        {
            "question": "¿Qué produce la mitosis?",
            "options": [
                "Dos células hijas",
                "Una sola célula",
                "Cuatro células",
                "Ninguna célula",
            ],
            "correct": 0,
            "explanation": "Produce dos células hijas con la misma información.",
            "cite": 1,
        },
        {
            "question": "¿Qué fases tiene la mitosis?",
            "options": [
                "Profase, metafase, anafase y telofase",
                "Solo profase",
                "Anafase y telofase",
                "Interfase",
            ],
            "correct": 0,
            "explanation": "Son cuatro fases consecutivas.",
            "cite": 1,
        },
        {
            "question": "¿Qué relaciona el teorema de Pitágoras?",
            "options": [
                "Cateto, cateto e hipotenusa",
                "Área y volumen",
                "Perímetro y radio",
                "Ángulos opuestos",
            ],
            "correct": 0,
            "explanation": "a² + b² = c².",
            "cite": 2,
        },
        {
            "question": "¿Qué tienen en común todas las células?",
            "options": [
                "Membrana y material genético",
                "Núcleo definido",
                "Cloroplastos",
                "Pared celular",
            ],
            "correct": 0,
            "explanation": "Son comunes a todas las células.",
            "cite": 1,
        },
    ]
}


def _request_text(body: dict) -> str:
    return "\n".join(
        str(message.get("content", "")) for message in body.get("messages") or []
    )


def _pieces(body: dict) -> list[str]:
    text = _request_text(body)
    if '"cards"' in text:
        return [json.dumps(CARDS, ensure_ascii=False)]
    if '"items"' in text:
        return [json.dumps(QUIZ, ensure_ascii=False)]
    if "esquema jerarquico" in text.lower():
        return [OUTLINE]
    if "resumen de estudio" in text.lower():
        return [SUMMARY]
    return CHAT_ANSWER


@app.get("/v1/models")
def list_models() -> dict:
    return {"object": "list", "data": [{"id": "mock-model", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "mock-model")
    pieces = _pieces(body)

    if not body.get("stream"):
        return {
            "id": "mock",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "".join(pieces)}}
            ],
        }

    async def generator():
        for piece in pieces:
            payload = {
                "id": "mock",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": model,
                "choices": [
                    {"index": 0, "delta": {"content": piece}, "finish_reason": None}
                ],
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.03)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
