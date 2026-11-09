# Migración opcional desde PostgreSQL de Windows

**No ejecutar sin autorización explícita.** Este texto es un procedimiento, no un script automático.

La pila Docker de la fase 1 usa un volumen `pgdata` **vacío**. El servidor PostgreSQL instalado en Windows no se monta ni se publica el de Compose.

Si en el futuro se desea copiar datos:

1. En Windows, con el servicio local detenido para escrituras:  
   `pg_dump -Fc -d notificaciones_agua -f respaldo.dump`
2. Anotar conteos: `SELECT COUNT(*) FROM interrupciones;` y tablas de usuarios/notificaciones.
3. Restaurar **solo** en el contenedor `db` (red interna), por ejemplo con un `docker compose cp` + `pg_restore` hacia `notificaciones_agua`.
4. Volver a contar y comparar.
5. No usar `DROP DATABASE`, `TRUNCATE` ni `docker compose down -v` sobre el origen.

Hasta que ese procedimiento se ejecute y se validen conteos, Compose y Windows permanecen **aislados**.
