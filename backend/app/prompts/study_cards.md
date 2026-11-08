TAREA: crea tarjetas de repaso a partir del CONTEXTO.

Devuelve SOLO un objeto JSON valido, sin texto adicional ni bloques de codigo:

{"cards":[{"front":"pregunta concreta","back":"respuesta breve","cite":1}]}

Reglas:
- Exactamente [[COUNT]] tarjetas.
- Una sola idea por tarjeta.
- El frontal es una pregunta que se pueda responder sin ver el reverso.
- El reverso responde en 40 palabras como maximo.
- "cite" es el numero del fragmento que respalda la respuesta, o null si no aplica.
- Sin duplicados ni preguntas triviales.
- Espanol.

TEMA: [[TOPIC]]

CONTEXTO:

[[CONTEXT]]
