# Instalación y demostración en Windows

## 1. Python y PostgreSQL

1. Instale Python 3.12 y marque “Add python.exe to PATH”.
2. Instale PostgreSQL y recuerde la contraseña del usuario `postgres`.
3. En pgAdmin o `psql`:

```sql
CREATE DATABASE notificaciones_agua;
```

## 2. Proyecto

```powershell
cd C:\ruta\Sistema-Notificacion-Agua
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Valores mínimos:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=notificaciones_agua
DB_USER=postgres
DB_PASSWORD=su_password
SMTP_ENABLED=false
MODO_ENVIO=simulacion
```

```powershell
python -m scripts.init_db
```

## 3. Demostración

Terminal 1:

```powershell
python -m src.pipeline
python -m src.pipeline
```

La segunda ejecución debe reportar `sin_cambios` si la fuente no varió.

Terminal 2:

```powershell
python -m src.web
```

Abra http://127.0.0.1:8000

1. Panel: totales de la base real (no cifras inventadas).
2. Interrupciones: filtro por distrito y detalle con historial.
3. Suscripciones: registre un correo propio de prueba, confirme el enlace mostrado y **no** active SMTP real.
4. Vuelva a ejecutar el pipeline: si hay coincidencia, verá notificaciones `SIMULADA`.
5. Los archivos de simulación quedan en `data\simulaciones\`.

## 4. Programador de tareas

1. Abra el Programador de tareas.
2. Crear tarea básica → desencadenador diario o cada hora.
3. Acción: Iniciar un programa.

Programa:

```
powershell.exe
```

Argumentos:

```
-ExecutionPolicy Bypass -File C:\ruta\Sistema-Notificacion-Agua\scripts\ejecutar_pipeline.ps1
```

Inicie en: `C:\ruta\Sistema-Notificacion-Agua`

La tarea usa el modo simulación a menos que cambie `.env`.

## 5. Correo real (opt-in)

Solo con autorización explícita:

```
SMTP_ENABLED=true
MODO_ENVIO=real
SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...
```

```powershell
python -m src.pipeline --envio-real
```

El estado `ACEPTADA_SMTP` significa que el servidor aceptó el mensaje, no que el buzón lo recibió.

## 6. Si la API no responde

El pipeline registra `ERROR`, conserva las interrupciones previas y no interpreta ausencias como cancelación.

Puede demostrar el flujo con el fixture:

```powershell
python -m src.pipeline --desde-archivo tests\fixtures\captura_minima.json
```
