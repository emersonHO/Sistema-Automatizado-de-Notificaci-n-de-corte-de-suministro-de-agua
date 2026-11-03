# Sistema de notificación de interrupciones de agua (Lima Metropolitana)

Proyecto de tesis de Ingeniería de Software:

**Desarrollo de un sistema automatizado de notificación proactiva de interrupciones del servicio de agua potable para usuarios de Lima Metropolitana.**

El sistema consulta periódicamente una **fuente pública de un tercero** (`https://cortedeagua.net.pe/api.php`), normaliza las incidencias, las persiste en PostgreSQL, detecta novedades y cambios relevantes, las relaciona con zonas de interés registradas de forma voluntaria y genera avisos por correo (desactivado por defecto).

No reemplaza los canales oficiales de la empresa prestadora. Una coincidencia territorial **no confirma** que una vivienda esté afectada.

## Requisitos

- Python 3.12 o compatible
- PostgreSQL 16 o compatible
- Windows 10/11 para la demostración local prevista (también funciona en Linux)

## Instalación

```powershell
cd Sistema-Notificacion-Agua
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` con la contraseña de PostgreSQL. No confirme envío real de correo hasta tener autorización.

## PostgreSQL

```sql
CREATE DATABASE notificaciones_agua;
```

```powershell
python -m scripts.init_db
```

## Pipeline completo

```powershell
python -m src.pipeline
```

Opciones útiles:

```powershell
python -m src.pipeline --desde-archivo tests\fixtures\captura_minima.json
python -m src.pipeline --sin-outbox
```

El envío SMTP real exige `SMTP_ENABLED=true`, `MODO_ENVIO=real` y `--envio-real`. Por defecto el modo es **simulación**: los mensajes se guardan en `data/simulaciones/` y no se contacta a destinatarios reales.

## Aplicación web

```powershell
python -m src.web
```

Abra `http://127.0.0.1:8000`.

Pantallas: panel, interrupciones (con historial), suscripciones (registro, confirmación y baja), notificaciones (correos enmascarados) y ejecuciones.

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas de integración usan la base `notificaciones_agua_test` (no la base de demostración).

```powershell
python -m src.evaluacion
```

Los reportes se escriben en `data/evaluacion/`. Precisión y recall se calculan solo sobre casos etiquetados.

## Automatización en Windows

Vea `docs/INSTALACION_WINDOWS.md` y el script `scripts/ejecutar_pipeline.ps1`.

## Documentación

- `docs/ARQUITECTURA.md`
- `docs/PLAN_IMPLEMENTACION.md`
- `docs/PRUEBAS.md`
- `docs/RESULTADOS_PRUEBAS.md`
- `docs/INSTALACION_WINDOWS.md`

## Limitaciones

- La API consultada no es oficial de SEDAPAL y puede cambiar o fallar.
- `fec_deteccion` y `fec_estimada` se tratan como fechas reportadas, no como inicio o restauración confirmados.
- Si la captura es incompleta, no se interpreta la ausencia de un identificador como cancelación.
- Callao se conserva en los datos originales y se excluye de la correspondencia territorial del MVP.
- `ACEPTADA_SMTP` no implica entrega al buzón.
