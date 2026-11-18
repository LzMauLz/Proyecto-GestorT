# Verificación integral local — 2026-11-16

Checkout: `D:\Escritorio\GestorTech`, rama `feat/tienda-catalogo-imagenes`. Se usaron SQLite e imágenes temporales, cuentas y productos ficticios. No se leyó `.env`, no se inspeccionó ni migró la base del taller y no se llamó a Groq.

## Resultados observados

- Suite completa final: **155 passed, 77 subtests passed en 66,98 s**, Python 3.12.14, `.venv-review/Scripts/python.exe -B -m pytest -q -p no:cacheprovider`.
- Cubre autenticación/CSRF, roles y objetos, reparaciones y privacidad, movimientos, duplicados por categoría, CSV/XLSX, migraciones y backup con fixtures, imágenes, publicación/disponibilidad y aprobación/cancelación del asistente. Los proveedores son dobles explícitos; no validan Groq real.
- `pip check`: sin dependencias rotas. `node --check` aprobado para `app.js` y `storefront.js`.
- Flask real en loopback, puerto 5067 y base temporal: navegador integrado comprobó búsqueda sin resultados y restablecimiento, categoría (8 a 4 productos), seguimiento por código sin nota interna, login administrativo, dashboard, alta manual, publicación y cambio a no disponible reflejado en tienda.
- Asistente deshabilitado: modo manual y enlace de registro disponibles. La aceptación → imagen → publicación → disponibilidad → retirada pasó en la suite con proveedor de prueba identificado.

## Correcciones

1. `tests/test_app.py` creaba temporales bajo `instance`; los permisos locales causaron reintentos en `tempfile.mkdtemp`. Ahora usa el directorio temporal del sistema.
2. «¿Cuánto vale el Cable USB?» no recibía productos al no contener palabras disparadoras. Una regresión reprodujo el fallo. Se proporciona ahora el contexto comercial limitado existente (hasta 100 productos activos) independientemente de esas palabras. El usuario autorizó expresamente nombre, categoría, precio y existencias, sin datos de clientes. La regresión y suite completa pasaron. Las notas libres de movimientos siguen excluidas.

## Docker, PR y límites

Docker CLI/Compose instalados, motor detenido: no se construyó ni ejecutó el contenedor. Revisión estática: imagen copia app/config/requirements, incluye Pillow, usuario 10001, puerto loopback, raíz read-only y volumen `/app/instance`. Las imágenes por defecto quedan en ese volumen junto a SQLite. El arranque ejecuta `init-db`: una base existente requiere respaldo y autorización previos; no se usó el volumen del usuario.

PR #25–#31 abiertos en la consulta observada. #31 contiene la ampliación de tienda y depende de #30 y sus predecesores. Las correcciones se entregan en #31 para evitar duplicarlas en la cadena. No se hizo merge.

Groq real, Python 3.11 local, dispositivos físicos, lectores de pantalla y Docker operativo no se verificaron en esta ejecución. El contexto conserva un límite de 100 productos; no representa todo el inventario cuando se supera. No se afirma ausencia absoluta de defectos ni comprensión perfecta del lenguaje natural.

## Ampliación autorizada: Groq real y Docker

Posteriormente el usuario autorizó expresamente probar Groq real y Docker con datos ficticios. Se cargó la configuración mediante el mecanismo normal de la aplicación, sin imprimir credenciales ni inspeccionar la base del taller. La red restringida bloqueó el primer intento; con acceso de ejecución autorizado se completó la conexión.

La prueba real detectó un fallo de contrato: Groq copiaba `price_cents` del contexto en una propuesta, que el backend rechaza. Se corrigió el prompt: envoltura explícita `message/action/proposal`, `price` decimal en COP y `price_cents` solo para consultas en centavos. Se conservó la validación estricta y se agregó una regresión que rechaza centavos como campo de precio de propuesta sin persistir nada.

La secuencia final de **cinco solicitudes reales** pasó: consulta por nombre y precio conocido, aclaración de precio/cantidad faltantes, propuesta con cancelación sin alta, nueva propuesta con aprobación explícita y valores exactos (25000 COP, 2 unidades, sin publicar), e importación normalizada conservando precio/stock. Hubo solicitudes de diagnóstico adicionales antes de esta secuencia; no se presenta el fallo inicial como éxito. `verify_live_groq.py` conserva la comprobación manual, no se ejecuta en CI ni automáticamente y requiere aprobación para llamadas/consumo de cuota. El test usa Flask/SQLite reales mediante el cliente de pruebas y HTTP real a Groq; no equivale a recorrer el chat en navegador con el proveedor activado.

Docker Desktop se inició sin instalar software. Docker Engine 29.9.2 y Compose v5.6.1 construyeron el Dockerfile existente con Python 3.11-slim y Pillow 13.0.0. El contexto fue una copia temporal por lista permitida (app, config, Dockerfile, requirements, wsgi y README), sin `.env`, datos ni entornos virtuales. `.dockerignore` también excluye ahora `.venv*` para futuras construcciones normales.

Compose se probó con proyecto `gestortech-qa-3081616a1a8f`, volumen nuevo propio, puerto exclusivo `127.0.0.1:5068` y Groq deshabilitado dentro del contenedor. Se observaron: catálogo HTTP 200; base inicializada; login real HTTP con CSRF y dashboard; UID 10001; raíz read-only con intento de escritura rechazado; creación de PNG ficticio en el volumen; SQLite e imagen disponibles tras reinicio. `verify_docker_local.py` conserva la comprobación con overrides temporales y limpieza limitada al proyecto aleatorio que crea.

Se retiraron contenedor, red, volumen e imagen QA; la consulta por etiqueta de ese proyecto no devolvió contenedores ni volúmenes. No se montaron carpetas ni volúmenes del taller. No se modificaron credenciales o datos existentes, ni se migró su base. Dockerfile/Compose no necesitaron cambios funcionales. El servidor Flask sigue siendo de demostración local; estas pruebas no autorizan producción ni garantizan que todas las respuestas futuras de IA sean correctas.

Documentación oficial consultada para el formato de mensajes/respuestas: [Groq API reference](https://console.groq.com/docs/api-reference). La validación del backend sigue siendo obligatoria aunque el proveedor solicite JSON.

Suite posterior a la corrección: **156 passed, 77 subtests passed en 67,34 s**, mismo comando y Python 3.12.14 local. No hubo fallos en esta ejecución final. Los verificadores manuales pasaron revisión sintáctica y quedan fuera de la colección automática de Pytest.
