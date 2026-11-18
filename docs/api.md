# API de GestorTech

Actualizado: 2026-11-15 para las propuestas de cambio. Las verificaciones por issue se documentan en `docs/issues/`; la suite integrada local pasó 131 pruebas y 77 subtests y [CI Python 3.11](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777915059) terminó en success para el commit 0b4f44a. Las cifras históricas no certifican la versión actual.

Base local: `/api`. Autenticación mediante sesión Flask; las operaciones privadas requieren iniciar sesión. Solicitudes mutables requieren `X-CSRF-Token`, obtenido de `GET /api/csrf` en la misma sesión. Content-Type JSON salvo donde se indica. Los errores se devuelven como `{ "error": "…" }`, sin trazas internas.

## Endpoints

| Método y ruta | Acceso | Parámetros y solicitud | Respuesta y códigos |
|---|---|---|---|
| GET `/api/csrf` | Público, crea sesión | Sin parámetros | 200: `{ "token_csrf": "…" }` |
| GET `/api/productos` | Admin/técnico | Sin parámetros | 200: lista de productos activos (`id_producto`, `nombre`, `descripcion`, `categoria`, `precio_centavos`, `cantidad_stock`, `activo`, `fecha_creacion`); 401 sin autenticación; 403 rol no permitido |
| POST `/api/productos` | Admin | JSON requerido `nombre` (texto), `precio` (número ≥ 0); opcionales `descripcion`, `categoria`, `cantidad_stock` (entero ≥ 0) | 201: `{ "id_producto": 1 }`; 400 validación/CSRF; 401 no autenticado; 403 permiso; 409 nombre/categoría duplicados |
| PUT `/api/productos/{id}` | Admin | `id` entero de ruta; JSON `nombre`, `precio`; opcionales `descripcion`, `categoria`. El stock no se edita aquí. | 200: `{ "id_producto": 1 }`; 400, 401, 403, 404, 409 por duplicado |
| GET `/api/productos/{id}/movimientos` | Admin/técnico | `id` entero | 200: lista con `id_movimiento`, `tipo`, `cantidad`, `observacion`, `fecha`, `usuario`; 401, 403, 404 |
| POST `/api/productos/{id}/movimientos` | Admin | `id` de ruta; JSON `tipo` (`entrada`/`salida`), `cantidad` entero positivo, `observacion` opcional | 201: `id_producto`, `cantidad_stock`; 400, 401, 403, 404, 409 si la salida excede existencias |
| GET `/api/reparaciones` | Admin/técnico | Ninguno | 200: lista; admin ve todas, técnico solo asignadas. Incluye `id_reparacion`, `codigo_seguimiento`, `equipo`, `descripcion_problema`, `estado`, `id_tecnico`, fechas. 401, 403 |
| POST `/api/reparaciones` | Admin/técnico | JSON `equipo`, `descripcion_problema`; `id_tecnico` obligatorio y activo para admin; el técnico se autoasigna | 201: `{ "id_reparacion": 1, "codigo_seguimiento": "GT-…", "estado": "Recibido" }`; 400, 401, 403 |
| PATCH `/api/reparaciones/{id}/estado` | Admin/técnico asignado | `id` de ruta; JSON `estado`; opcionales `nota_interna`, `comentario_publico`, `id_tecnico` (solo admin) | 200: `id_reparacion`, `estado`; 400, 401, 403, 404, 409 transición no permitida |
| GET `/api/seguimiento/{codigo}` | Público | Código en ruta | 200: `codigo_seguimiento`, `estado`, fechas e `historial_publico` (estado, comentario publicado, fecha); 404 código no encontrado; 429 límite de intentos |
| POST `/api/ia/importacion/propuesta` | Admin | Multipart `archivo`, CSV o XLSX | 200: filas normalizadas, `requiere_revision_humana: true`, `modo` (`manual` o `groq`). Sugerencias solo para nombre/descripción/categoría; precio y stock siguen siendo los del archivo. No persiste. 400 archivo inválido, 401, 403, 413 |
| POST `/api/asistente/mensaje` | Admin; técnico solo consulta | JSON `mensaje` (máximo 2.000 caracteres) y `historial` opcional | 200: respuesta o propuesta pendiente de uno o varios productos (máximo 20) o movimiento. 502 proveedor no disponible; 503 asistente desactivado |
| POST `/api/asistente/propuestas/{id}/confirmar` | Admin propietario | Sin cuerpo o JSON con `correcciones`; requiere CSRF | 200: operación validada y ejecutada atómicamente; 409 propuesta inexistente/resuelta, duplicado o revisión inválida |
| POST `/api/asistente/propuestas/{id}/cancelar` | Admin | Sin cuerpo; requiere CSRF | 200: propuesta cancelada; 409 propuesta inexistente o ya resuelta |
| GET `/api/openapi.json` | Público | Ninguno | 200: especificación OpenAPI 3.1 de las rutas API implementadas |

Los métodos mutables también requieren la cabecera `X-CSRF-Token`. El GET `/api/seguimiento/{codigo}` se configura `Cache-Control: no-store`.

## Ejemplos de solicitud y respuesta

Crear una reparación como administrador (el ID del ejemplo debe corresponder a un técnico activo en la base sintética):

```json
{
  "equipo": "Computador portátil",
  "descripcion_problema": "El equipo no inicia",
  "id_tecnico": 2
}
```

Respuesta 201:

```json
{
  "id_reparacion": 1,
  "codigo_seguimiento": "GT-ALEATORIO",
  "estado": "Recibido"
}
```

Registrar movimiento de inventario:

```json
{
  "tipo": "salida",
  "cantidad": 1,
  "observacion": "Uso en reparación"
}
```

El seguimiento público nunca devuelve el equipo, descripción del problema, datos de cliente, usuario, ni notas internas. Solo se exponen los comentarios que el personal introdujo explícitamente como públicos. La interfaz HTML también ofrece un flujo de importación con preview y aprobación humana antes de guardar.

## Asistente IA

La pantalla `/assistant` usa el endpoint `/api/asistente/mensaje`. Un administrador puede pedir por chat un producto individual o varios productos en una misma solicitud; el backend devuelve una única propuesta pendiente y la confirmación los crea en una transacción. Groq solo se consulta cuando `GROQ_ENABLED=true`, `GROQ_API_KEY` y `GROQ_MODEL` están configurados. No se fija un modelo como validado actualmente ni se inspeccionan credenciales. Esta fase autoriza únicamente pruebas locales; cualquier llamada real necesita aprobación separada.

La importación de inventario acepta `nombre`, `descripcion`, `categoria`, `precio` o `precio_venta`, y `stock`. En plantillas con `precio_compra` y `precio_venta`, usa `precio_venta` como precio del catálogo. Columnas adicionales como código, marca, precio de compra y stock mínimo se ignoran durante la normalización y no se persisten porque no forman parte del modelo actual.

Las consultas de inventario se acompañan de datos obtenidos por SQLite; el modelo no puede consultar SQL, herramientas ni servicios arbitrarios. Las propuestas de producto y movimientos se guardan como pendientes en `ai_proposals` y requieren confirmación administrativa. El servicio vuelve a validar rol, producto, tipo, cantidad y stock antes de ejecutar. Técnicos solo reciben respuestas de consulta. No se almacenan claves, prompts completos ni respuestas del proveedor en el historial de auditoría.

Las transiciones de reparación están documentadas en [decisiones_mvp.md](decisiones_mvp.md). La muestra `GT-000123` del documento académico es ilustrativa; GestorTech genera códigos aleatorios con 128 bits de entropía.

## Revisión de propuestas del asistente (issue #7)

`POST /api/asistente/propuestas/<id>/confirmar` admite opcionalmente un objeto JSON `correcciones` con los campos del producto o movimiento permitido por la propuesta. Las propuestas incompletas no se guardan: el chat solicita los datos faltantes. Solo administración confirma y la propiedad de la propuesta se valida en backend.

`POST /assistant/import` recibe un CSV/XLSX en `archivo`, una lista de `campos` permitidos y `palabras` opcional. Requiere sesión administrativa y CSRF. Extrae localmente y reutiliza la previsualización editable; no envía el archivo a Groq. Véase [issue #7](issues/7-asistente.md).


## Catálogo y controles web

Estas rutas devuelven HTML y no usan el prefijo `/api`:

| Método y ruta | Acceso | Contrato |
|---|---|---|
| GET `/catalog` | Público | Solo productos activos/publicados; nombre, descripción, categoría y precio. 200 normal/vacío; 503 ante fallo controlado de consulta. Sin stock, movimientos ni usuarios. |
| POST `/products/{id}/publication` | Admin, CSRF | Campo `published` igual a `0` o `1`; publicar/despublicar explícitamente. No elimina historial. |
| POST `/assistant/import` | Admin, CSRF | Archivo CSV/XLSX, `campos` allowlist y `palabras` opcional; extracción local, previsualización editable y aprobación posterior. |

Los límites locales son 5 solicitudes de login y 30 consultas de seguimiento por IP en una ventana de 60 segundos. UI `/track` y API de seguimiento comparten presupuesto. Al excederlo se devuelve 429 con `Retry-After`; no se confía en `X-Forwarded-For` sin un diseño de proxy aprobado. La confirmación de IA no puede cambiar de propietario ni ejecutarse dos veces y la auditoría se vincula a la propuesta concreta.
