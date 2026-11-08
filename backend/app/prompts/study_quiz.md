TAREA: crea un test de opcion multiple a partir del CONTEXTO.

Devuelve SOLO un objeto JSON valido, sin texto adicional ni bloques de codigo:

{"items":[{"question":"enunciado","options":["a","b","c","d"],"correct":0,"explanation":"por que","cite":1}]}

Reglas:
- Exactamente [[COUNT]] preguntas.
- Cuatro opciones por pregunta y una sola correcta.
- Los distractores deben ser plausibles pero claramente incorrectos segun el contexto.
- "correct" es el indice (0 a 3) de la opcion correcta.
- "explanation" explica la respuesta en 30 palabras como maximo.
- "cite" es el numero del fragmento que respalda la respuesta, o null si no aplica.
- Sin duplicados. Espanol.

TEMA: [[TOPIC]]

CONTEXTO:

[[CONTEXT]]
