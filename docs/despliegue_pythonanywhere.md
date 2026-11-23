# Despliegue gratuito en PythonAnywhere

Esta guía prepara la demo pública gratuita en una cuenta PythonAnywhere Beginner. Ese plan ofrece una app en `gestortech.pythonanywhere.com`, un trabajador web y 512 MiB de almacenamiento. La aplicación gratuita vence al mes y requiere renovación periódica desde el panel.

## 1. Obtener el código de `develop`

En el panel de PythonAnywhere, abre **Consoles** y una consola Bash. Ejecuta:

```bash
cd /home/gestortech
git clone --branch develop --single-branch https://github.com/LzMauLz/Proyecto-GestorT.git GestorTech
cd /home/gestortech/GestorTech
```

Si ya existe `/home/gestortech/GestorTech`, entra en esa carpeta y actualízala desde `develop` antes de instalar. No clones la base de datos local del taller.

## 2. Preparar Python y dependencias

En el selector de la pestaña **Web**, elige Python 3.13. En Bash crea un entorno con la misma versión e instala las dependencias:

```bash
mkvirtualenv --python=python3.13 gestortech
cd /home/gestortech/GestorTech
pip install -r requirements.txt
```

En **Web → Virtualenv**, escribe `/home/gestortech/.virtualenvs/gestortech`.

## 3. Clave local y base vacía

En Bash crea una clave aleatoria para esta instalación:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

Guarda el resultado en `/home/gestortech/GestorTech/.env` usando el editor de archivos de PythonAnywhere. Incluye:

```ini
GESTORTECH_SECRET_KEY=PEGA_AQUI_LA_CLAVE_GENERADA
GESTORTECH_COOKIE_SECURE=1
GROQ_ENABLED=false
GROQ_MODEL=
GROQ_API_KEY=
```

No publiques el contenido de `.env`. La app crea la base en `instance/gestortech.sqlite3`; la carpeta `instance/product-images/` conserva las imágenes cargadas. Inicializa el esquema y crea la cuenta administrativa mediante prompts:

```bash
cd /home/gestortech/GestorTech
python -m flask --app wsgi:app init-db
python -m flask --app wsgi:app auth create-admin
```

Introduce el correo y la contraseña en la consola de PythonAnywhere. No uses credenciales de ejemplo.

## 4. Configurar la app web

En **Web**, selecciona **Add a new web app**, la URL gratuita `gestortech.pythonanywhere.com`, Python 3.13 y **Manual configuration**. Abre el archivo WSGI indicado en esa pestaña y reemplaza su contenido por:

```python
import sys

project = '/home/gestortech/GestorTech'
if project not in sys.path:
    sys.path.insert(0, project)

from wsgi import app as application
```

Configura el archivo WSGI para usar el entorno virtual anterior. En **Static files**, añade `/static/` con la ruta `/home/gestortech/GestorTech/app/static/`. Activa **Force HTTPS** en **Web**, guarda y pulsa **Reload**.

Comprueba la URL, `/health`, inicio de sesión, catálogo, seguimiento ficticio y carga de una imagen de prueba. Mantén los datos reales de clientes fuera de la demostración inicial.

Después de subir el código de una versión nueva, recarga la aplicación. En el catálogo, comprueba que la URL de `/static/js/storefront.js` incluya el parámetro `v` y responda con HTTP 200. Flask calcula esa versión al arrancar a partir del contenido del archivo. Mantén el mapeo de `/static/` apuntando a la misma copia de código que usa WSGI.

## 5. Groq y operación gratuita

La cuenta gratuita limita el tráfico saliente a una lista permitida. `api.groq.com` aparece actualmente en la lista de PythonAnywhere. Si activas el asistente, añade `GROQ_ENABLED=true`, `GROQ_MODEL` y `GROQ_API_KEY` al `.env` privado y recarga la app. Envía únicamente datos ficticios de productos en la prueba.

El plan gratis tiene un trabajador y una cuota de almacenamiento total de 512 MiB, incluidos código, entorno y datos. En una ventana sin escrituras, usa la operación de respaldo de SQLite y conserva una copia privada de `instance/gestortech.sqlite3` y `instance/product-images/`. La cuenta requiere renovar la app gratuita cuando venza al mes.

Fuentes oficiales consultadas: [Planes PythonAnywhere](https://www.pythonanywhere.com/pricing/), [límites de cuentas gratuitas](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [configuración Flask](https://help.pythonanywhere.com/pages/Flask/), [variables de entorno en WSGI](https://help.pythonanywhere.com/pages/EnvironmentVariables/) y [lista de sitios permitidos](https://www.pythonanywhere.com/whitelist/).

## Actualizar una base existente para usar compatibilidades

Antes de desplegar esta función, sigue el [procedimiento de respaldo y actualización](operacion_demo_local.md#actualización-de-una-base-existente) con el entorno virtual de GestorTech y la ruta de la base del sitio. La inicialización crea la tabla de compatibilidades y deja los productos existentes con su lista de modelos vacía hasta que el taller la complete. Puedes repetir la inicialización sin perder las compatibilidades ya registradas.

La búsqueda por modelo funciona en modo manual. Si Groq está configurado, la consulta pública de texto cuenta con un máximo de 6 solicitudes por IP y 12 para toda la aplicación en una ventana de 60 segundos, además de 120 solicitudes para toda la aplicación en una ventana de 24 horas. Al llegar a un límite, la búsqueda manual sigue disponible.

## Evidencia de entrega

Consulta [los flujos verificados y los límites de la demo](entrega_funcional.md).
