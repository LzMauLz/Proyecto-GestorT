# GestorTech

MVP académico para organizar reparaciones e inventario de un taller de servicio técnico. El sistema separa el área del personal de la consulta pública por código de seguimiento.

## Estado

Revisa [PROJECT_STATUS.md](PROJECT_STATUS.md). La arquitectura y el modelo parten de `docs/Modulo 2  Arquitectura y Diseño de Aplicaciones con IA.pdf`; los documentos académicos originales no se modifican.

## Tecnologías

- Python 3.11, Flask y Jinja2.
- SQLite con claves foráneas habilitadas por conexión, restricciones y transacciones.
- HTML, CSS y JavaScript nativos.
- CSV con biblioteca estándar y XLSX con openpyxl.
- Pytest para la suite (tests compatibles también con `unittest`).

## Arquitectura

`app/domain` conserva estados y errores de dominio; `app/application` implementa reglas y servicios; `app/infrastructure` encapsula SQLite y adaptadores externos; `app/web` contiene controladores Flask para páginas y API. El asistente usa `app/application/ai_assistant.py` para coordinar consultas y propuestas, y el adaptador Groq para respuestas JSON. Está desactivado por defecto en el código; en desarrollo local se habilita mediante `.env` con `GROQ_ENABLED=true`, `GROQ_API_KEY`, `GROQ_MODEL` y opcionalmente `GROQ_TIMEOUT` (1–60 segundos). El modelo validado en este entorno es `openai/gpt-oss-20b`.

## Identidad visual

La interfaz usa una paleta violeta propia, navegación y tarjetas organizadas para el trabajo de taller, y conserva la mascota/logo oficial en `app/static/images/gestortech-mascot.png`. El cliente ve el código, el estado, el progreso y únicamente avances publicados. La inspiración visual se limita a patrones generales de navegación y jerarquía; no se usan recursos ni marca de terceros.

## Requisitos y preparación local

El entorno virtual local dispone de Flask, openpyxl y Pytest según
`requirements.txt`. Las versiones quedan fijadas en ese archivo; usa un
entorno virtual para instalar y ejecutar el proyecto.

```powershell
cd D:\Escritorio\GestorTech
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:GESTORTECH_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python -m flask --app wsgi:app init-db
python -m flask --app wsgi:app auth create-admin
python -m flask --app wsgi:app run
```

El archivo local `.env` es opcional, está excluido de Git y se carga automáticamente al iniciar la aplicación. Copia `.env.example` como `.env` y completa sus valores; los valores no vacíos del archivo local tienen prioridad en este entorno de desarrollo. En despliegue HTTPS configura `GESTORTECH_COOKIE_SECURE=1` y una clave aleatoria privada.

## Ejecución con Docker

El contenedor publica únicamente en `127.0.0.1:8000`, usa un volumen para la base SQLite, ejecuta como usuario sin privilegios y mantiene el filesystem raíz en solo lectura. Es una configuración reproducible para demostración local; `flask run` es el servidor de desarrollo de Flask y no se presenta como servidor de producción.

```powershell
$env:GESTORTECH_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
docker compose up --build
```

Luego crea el administrador dentro del contenedor (`docker compose exec gestortech python -m flask --app wsgi:app auth create-admin`). Docker no estaba disponible para validar la construcción en este entorno.

Docker mantiene Groq desactivado aunque exista un `.env` local. Para habilitarlo
de forma explícita en el contenedor, define `DOCKER_GROQ_ENABLED=true`,
`DOCKER_GROQ_MODEL` y `DOCKER_GROQ_API_KEY` en el entorno de ejecución. No
guardes esas variables en archivos versionados.

## Funcionalidades

- **Implementadas:** acceso con roles administrador/técnico; creación de usuarios administrativos; registro y seguimiento de reparaciones; asignación a técnicos; transiciones validadas e historial; separación de notas internas y avances públicos; consulta pública de código de alta entropía; productos, movimientos de stock atómicos y bajas lógicas; revisión y aprobación manual de CSV/XLSX; API OpenAPI JSON.
- **Parciales:** la autorización del técnico se basa en la reparación asignada. Los estados son el flujo acordado para el MVP. La publicación de cada nota es decisión explícita del personal.
- **Futuras:** integración automatizada de canales; despliegue externo; endurecimiento y pruebas de carga para producción.
- **Asistente IA:** disponible en `/assistant` para admin y consulta limitada para técnicos cuando Groq está habilitado. Puede redactar descripciones, preparar productos y movimientos y contestar consultas basadas en inventario. Toda modificación requiere preview y confirmación de un administrador.

## Seguridad conocida y límites

- Sin cuenta de administrador ni contraseña por defecto: inicializa SQLite y crea la primera cuenta mediante prompt interactivo.
- Claves guardadas con `werkzeug.security`; cookie HttpOnly y SameSite Lax; CSRF en métodos mutables.
- La consulta pública no revela dispositivo, descripción del problema, notas internas, identidad del usuario ni código incremental.
- Cambios de estado usan allowlist y transición; código de seguimiento usa 128 bits aleatorios.
- Importación limitada a 5 MB, 1.000 filas, 30 columnas y 20 MB descomprimidos; no se ejecutan fórmulas ni contenido importado. Toda fila requiere revisión humana.
- Groq usa un adaptador HTTP de biblioteca estándar, sin SDK. En la configuración local validada se realizó una prueba controlada con datos ficticios. Solo se envían nombre, descripción y categoría de filas válidas (máximo 50); precio y stock se conservan del archivo. Errores regresan al modo manual. La previsualización no persiste productos y las filas requieren selección y aprobación humana explícitas.
- El asistente IA usa solicitudes JSON limitadas a 128 KiB y respuestas a 256 KiB, timeout configurable, sin herramientas ni SQL. Un administrador puede preparar por chat un producto individual o hasta 20 productos en una sola propuesta; la confirmación los crea en una transacción. Las consultas reciben contexto factual del inventario; la IA no inventa existencias. Las propuestas pendientes se pueden confirmar o cancelar desde el panel y quedan registradas sin claves ni contenido sensible.
- La clave local se configura únicamente en `.env` o en el gestor de secretos del entorno. `.env.example` solo muestra nombres sin credenciales; no pongas secretos en README, Git o archivos compartidos. Mantén `GROQ_ENABLED=false` si no deseas transmitir datos al proveedor.
- El servidor integrado de Flask es solo para demo local. No desplegar este MVP en Internet sin completar revisión de seguridad, límites de intentos, HTTPS, logging protegido, copias de seguridad y un servidor WSGI apropiado.
- Datos ficticios únicamente. No enviar datos de clientes a servicios externos.

## API

Especificación OpenAPI disponible en `GET /api/openapi.json`. Las rutas, permisos, solicitudes, respuestas y códigos se describen en [docs/api.md](docs/api.md). El uso de IA queda registrado en [docs/uso_ia.md](docs/uso_ia.md). El API usa la sesión de Flask: consulta `GET /api/csrf` y envía el valor como `X-CSRF-Token` en solicitudes mutables.

## Pruebas

```powershell
python -m unittest discover -s tests -v
# Con Pytest instalado en el entorno virtual:
python -m pytest
```

No ejecutes pruebas con datos reales. La suite usa una base SQLite temporal y cuentas ficticias.

## Configuración local de Groq

No se deben compartir claves por chat ni guardarlas en Git. Puedes configurar Groq en el archivo local `.env`:

```text
GESTORTECH_SECRET_KEY=crea-una-clave-privada-larga
GROQ_ENABLED=true
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TIMEOUT=12
GROQ_API_KEY=tu-clave-de-groq
```

Para volver al modo manual usa `GROQ_ENABLED=false`. La aplicación permanece sin llamadas externas cuando falta cualquier valor requerido.

## Trabajo colaborativo

El repositorio remoto es [Proyecto-GestorT](https://github.com/LzMauLz/Proyecto-GestorT).
El flujo de entrega usa `develop` para desarrollo y `main` como rama base. Los
secretos, la base SQLite local y el entorno virtual están excluidos por
`.gitignore`. La entrega actual corresponde a un único integrante; no se
atribuyen revisiones ni contribuciones a personas que no hayan participado.
