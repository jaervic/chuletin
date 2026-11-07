"""Servidor LLM falso para probar la interfaz sin gastar tokens.

Implementa lo minimo de la API de OpenAI: /v1/models y
/v1/chat/completions con streaming.

Uso: uvicorn scripts.mock_llm:app --port 8099
"""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="Chuletin mock LLM")

ANSWER = [
    "La **mitosis** es la división celular que produce dos células hijas "
    "con la misma información genética [1].\n\n",
    "Sus fases son profase, metafase, anafase y telofase [1].\n\n",
    "En un triángulo rectángulo se cumple $a^2 + b^2 = c^2$ [2].\n\n",
    "> Respuesta generada por el servidor de pruebas.\n",
]


@app.get("/v1/models")
def list_models() -> dict:
    return {"object": "list", "data": [{"id": "mock-model", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "mock-model")

    if not body.get("stream"):
        return {
            "id": "mock",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "".join(ANSWER)}}
            ],
        }

    async def generator():
        for piece in ANSWER:
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
            await asyncio.sleep(0.04)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
