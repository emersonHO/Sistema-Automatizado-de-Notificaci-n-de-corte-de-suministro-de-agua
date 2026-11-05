# Resultados de pruebas (evidencia de esta ejecución)

Zona horaria de reporte: **America/Lima**.

## Pruebas automatizadas

Comando: `python -m pytest -q`

Resultado observado el 2 de noviembre de 2026, 21:24 America/Lima:

```
20 passed in 0.96s
```

Ninguna prueba habilitó SMTP real.

## Pipeline contra la fuente pública (esta máquina)

Primera ejecución (21:23 America/Lima, 2 nov 2026):

- Estado: `COMPLETADO`
- Captura completa: sí
- Registros: 185
- Nuevos: 185
- Actualizados: 0
- Sin cambios: 0
- Tiempo de descarga: 178 ms
- Normalización: 26 ms
- Persistencia: 74 ms
- Captura: `data/raw/cortes_20261102_212322_977796.json`

Segunda ejecución idéntica en contenido (21:24 America/Lima):

- Nuevos: 0
- Actualizados: 0
- Sin cambios: 185
- Notificaciones creadas: 0

Estos números corresponden a esa consulta. No son permanentes: la fuente cambia.

## Suscripción de demostración (correo de ejemplo)

Se registró y confirmó `demo.tesis@example.com` (dominio de ejemplo, no un destinatario real). Tras una ejecución posterior:

- Coincidencias: 2
- Notificaciones creadas: 2
- Envío: 2 simuladas, 0 aceptadas SMTP, 0 fallidas

Los mensajes quedaron en `data/simulaciones/`.

## Indicadores de casos etiquetados

`python -m src.evaluacion` (2 nov 2026, 21:23 America/Lima):

| Indicador | Valor |
|-----------|--------|
| Precisión correspondencia | 1.0 (VP 3, FP 0, 7 casos) |
| Recall correspondencia | 1.0 (FN 0) |
| Exactitud hash origen | 1.0 (5/5) |
| Exactitud hash relevante | 1.0 (5/5) |

Estos valores miden únicamente los casos de `src/casos_evaluacion.py`, no el universo de Lima.

## Limitaciones de latencia de detección

La fuente no documenta una fecha de publicación contractual. `fec_deteccion` no se usa como publicación. La latencia publicación→observación no se calcula sobre la API real; solo podría medirse en pruebas controladas con marcas de tiempo inyectadas.
