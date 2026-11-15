# Issue #10 — Catálogo público

Verificación integrada con #5: **65 passed, 56 subtests passed en 33,17 s** (Python 3.12 local). CI Python 3.11 aprobado en el commit `3cc4b18`: [run 43777324396](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777324396). Comprobación real Edge headless a 375 px sin desbordamiento horizontal; la ampliación de accesibilidad se realiza en el #14.

Decisión confirmada por el usuario el 2026-11-15: catálogo público sin cuentas de cliente. Se conserva Flask/Jinja2 y la identidad local.

## Implementación

- GET `/catalog` muestra exclusivamente nombre, descripción, categoría y precio de productos activos y publicados. La consulta no selecciona stock, movimientos ni datos de personal.
- POST `/products/<id>/publication` permite a administración publicar/despublicar, exige CSRF y valida `published` como `0` o `1`.
- `products.published` tiene valor inicial 0, también para altas desde importación/IA. La migración aditiva deja todos los registros existentes sin publicar y es repetible.
- Dar de baja oculta el producto sin borrar su historial. La respuesta pública usa `no-store`.
- Vista vacía y error 503 con reintento; texto escapado por Jinja. Tarjetas adaptables reutilizan paleta y logo existentes.

## Verificación local

`tests/test_catalog.py`: 5 pruebas aprobadas con Flask real y SQLite temporal, sin llamadas externas. Se verifican roles/CSRF, campos públicos permitidos, XSS escapado, despublicación/baja, migración y un fallo real al consultar una tabla ausente.

Suite completa en este worktree: **46 passed, 40 subtests passed**, 33,39 s.

Después se añadieron dos pruebas reales de aprobación de importación y propuesta IA almacenada: ambas dejan `published=0`. La suite dirigida actual del catálogo pasó **7 pruebas en 1,72 s**. La propuesta IA de esta prueba se crea en SQLite sintético, sin contactar al proveedor.

Entorno: Python 3.12.14 empaquetado, usando dependencias ya instaladas del proyecto. El ejecutable del entorno virtual apunta a un Python 3.11 ausente; GitHub Actions con Python 3.11 y la revisión visual real quedan pendientes al integrar.

No se consultó ni migró la base del usuario. Para una base existente, respaldar y ejecutar la migración solo después de revisar los cambios.
