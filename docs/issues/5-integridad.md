# Issue #5: integridad de reparaciones y productos

## Decisiones y comportamiento

- El administrador selecciona un técnico activo al crear una reparación. La ausencia, un usuario inexistente/inactivo, otro rol o un identificador inválido se rechazan antes de escribir.
- Un técnico crea la reparación asignada a su propio usuario; una asignación distinta enviada por el cliente no cambia ese responsable.
- El formulario exige selección y, cuando no hay técnicos activos, explica cómo crear uno y deshabilita el envío. Las verificaciones del backend y SQLite siguen aplicándose a solicitudes directas.
- La unicidad de productos es **por categoría**, según la decisión del usuario: nombre y categoría se comparan con `casefold()` y espacios exteriores/repetidos normalizados. El nombre visible se conserva. La categoría vacía se compara como una categoría común.
- La regla también abarca productos retirados, para conservar su identidad histórica. La misma denominación en otra categoría está permitida. Editar el propio producto sin colisionar está permitido; una colisión devuelve HTTP 409.

## Persistencia y actualización de una base existente

SQLite utiliza un índice UNIQUE sobre `normalize_inventory_key(name)` y `normalize_inventory_key(category)`. La función determinista se registra en cada conexión de `connect_db`; las herramientas que escriban directamente deben usar esa conexión. La validación del servicio proporciona el mensaje amigable y el índice resuelve carreras entre solicitudes.

Las bases nuevas tienen `repairs.assigned_to NOT NULL`. Los triggers de inserción y reasignación exigen que el usuario referenciado sea técnico activo.

`init_db()` realiza una comprobación previa dentro de una transacción antes de aplicar restricciones. Si hay órdenes sin asignación válida o productos que colisionan por nombre/categoría, informa cantidades y aborta. No reasigna órdenes, no renombra ni elimina productos.

Cuando los datos son válidos, reconstruye solamente la tabla antigua de reparaciones que admite NULL, conserva IDs, historial, índices y triggers, y comprueba las claves foráneas antes de confirmar. La reconstrucción suspende claves foráneas exclusivamente en su conexión y transacción para evitar que el DROP del padre borre el historial por cascada; se reactivan al finalizar. Un fallo revierte datos y esquema. El proceso es idempotente.

Antes de aplicar la migración a una base real, el responsable debe disponer de respaldo y resolver manualmente cualquier dato que el preflight rechace. Esta entrega no inspeccionó ni migró la base real.

## Evidencia automatizada

Se ejecutaron comprobaciones con SQLite temporal y datos ficticios:

| Cobertura | Resultado observado |
|---|---|
| Ausencia/rol/inactividad de técnico, autoasignación y restricciones SQL | PASS |
| Unicidad por nombre/categoría, edición, categorías distintas y productos retirados | PASS |
| Inserción SQL directa y altas concurrentes mediante conexiones separadas | PASS |
| API y formulario sin técnicos activos | PASS |
| Migración con preservación de IDs/historial/índices, idempotencia y rollback | PASS |
| Rechazo de datos legacy inválidos o duplicados sin modificar registros | PASS |
| Suite existente y 16 pruebas nuevas, incluyendo altas y ediciones concurrentes | 57 passed, 51 subtests passed en 33,99 s |

Revisión adicional: límites de IDs SQLite y rechazo de IDs booleanos/estructurados en reasignación. Suite final local: **58 passed, 56 subtests passed en 31,97 s**, incluyendo 17 pruebas de integridad.

Comando de verificación completa ejecutado: `python -B -m pytest tests/test_integrity.py tests/test_app.py -q -p no:cacheprovider`.

La verificación local utilizó Python 3.12.14 incluido con el entorno de herramientas y las dependencias existentes del proyecto: el intérprete original del entorno virtual Python 3.11 no estaba disponible. Python 3.11 sigue siendo el stack aprobado; su validación en CI queda pendiente. No se instalaron dependencias ni se hicieron llamadas a Groq.

Validación del stack aprobado completada posteriormente: GitHub Actions Python 3.11 pasó para el commit `df2a83d` ([run 43776061344](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43776061344)). El PR y la integración en `develop` continúan pendientes.
