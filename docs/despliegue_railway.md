# Preparación de Railway

Esta configuración despliega la rama `develop` usando el `Dockerfile`, Gunicorn y un volumen persistente. Railway debe tener un servicio web conectado al repositorio `LzMauLz/Proyecto-GestorT`.

## Servicio y volumen

1. Selecciona la rama `develop` como rama de despliegue.
2. Usa el Dockerfile de la raíz.
3. Añade un volumen con punto de montaje `/app/instance`.
4. Configura `RAILWAY_RUN_UID=0`. Railway monta el volumen con propietario root. El punto de entrada corrige el propietario de los directorios y archivos SQLite existentes y luego cambia el proceso de la aplicación a UID 10001.
5. Deja que Railway asigne `PORT`. Gunicorn escucha ese puerto en todas las interfaces del contenedor.
6. Configura la comprobación de salud en `/health`. La ruta devuelve 200 cuando SQLite acepta una consulta sencilla.
7. Genera un dominio público de Railway desde la configuración de red del servicio.

## Variables del servicio

- `GESTORTECH_SECRET_KEY`: genera un valor aleatorio largo y guárdalo como secreto en Railway.
- `GESTORTECH_DATABASE`: `/app/instance/gestortech.sqlite3`.
- `GESTORTECH_COOKIE_SECURE`: `1`.
- `GROQ_ENABLED`: `false` hasta decidir activar el proveedor desde Railway.
- `GROQ_API_KEY` y `GROQ_MODEL`: se pueden dejar sin definir con el proveedor apagado. No los copies desde archivos del proyecto.

## Inicialización y migraciones

El punto de entrada crea el esquema solo si la base todavía no existe en el volumen. En el primer despliegue, crea el administrador desde Railway Shell con `python -m flask --app wsgi:app auth create-admin`. La contraseña se pide de forma interactiva y debe guardarse en el gestor seguro del usuario.

No conectes una copia de la base local del taller durante la primera publicación. Para migrar una base con datos, detén el servicio, realiza un respaldo nuevo de SQLite y de `product-images`, valida el respaldo y aplica `python -m flask --app wsgi:app init-db` como operación explícita. Si el preflight detecta reparaciones sin técnico válido o productos duplicados, resuelve esos registros antes de migrar.

Activa respaldos automáticos del volumen y confirma la restauración antes de importar datos reales. Una restauración SQLite conserva la base, y la carpeta `product-images` debe incluirse en la misma estrategia de respaldo.

## Verificación local

El Dockerfile continúa escuchando en el puerto 8000 para Compose local. La prueba del entorno local debe revisar `GET /health`, login y CSRF, subida y visualización de imagen, persistencia de SQLite e imagen tras reiniciar, usuario 10001 y filesystem raíz de solo lectura.
