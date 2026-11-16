# Issue #15 — Pruebas y CI

La suite de la Sesión 3 es el punto de partida. Este issue comprueba los flujos ampliados y sus errores, sin reemplazar pruebas existentes para obtener un resultado verde.

## Matriz de aceptación

| Criterio | Evidencia de código a integrar | Estado |
|---|---|---|
| Asignación obligatoria y técnico válido | tests/test_integrity.py, issue #5 | PASS integrado |
| Nombre único dentro de categoría, edición y concurrencia | tests/test_integrity.py, issue #5 | PASS integrado |
| Catálogo público y privacidad | tests/test_catalog.py, issue #10 | PASS integrado |
| Propuestas editables, faltantes, CSV/XLSX y aprobación | tests/test_assistant_workflow.py, issue #7 | PASS integrado con proveedor de prueba explícito |
| Permisos, CSRF, límites, errores y transacciones | tests/test_security.py, issue #12 | PASS integrado |
| Reglas puras de dinero, cantidades y JSON | tests/test_unit_rules.py | Comprobado localmente |
| Concordancia de rutas/métodos y OpenAPI | tests/test_api_contract.py | PASS integrado |
| CI Python 3.11 con datos ficticios | .github/workflows/ci.yml | SUCCESS, run 43777915059 |

## Verificaciones observadas

Las pruebas nuevas de reglas puras y contrato pasaron: **26 passed en 0,93 s**, con Python 3.12.14 empaquetado y dependencias existentes. Las reglas puras no requieren fixture Flask/SQLite. La comprobación de contrato compara el mapa de rutas real con los métodos/path de OpenAPI.

El entorno virtual local apunta a un Python 3.11 ausente. La ejecución complementaria con Python 3.12 no sustituye la comprobación obligatoria de CI con Python 3.11.

Suite integrada final: **131 passed, 77 subtests passed en 65,75 s**, ejecutada con `python -B -m pytest -q -p no:cacheprovider`. No se modificaron los datos reales del taller. El mismo código (`0b4f44a`) pasó en GitHub Actions Python 3.11: [run 43777915059](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777915059).

Los flujos cruzados también están cubiertos por `tests/test_cross_flows.py`: duplicados en importación y lote IA no dejan productos/movimientos parciales; la propuesta IA queda pendiente tras rollback; JSON y campos obligatorios inválidos se rechazan sin crear reparaciones.

## Alcance de datos y proveedor

Los tests usan Flask y SQLite reales en bases temporales con datos ficticios. Las pruebas de concurrencia usan conexiones independientes. Los fallos de proveedor se inducen con dobles explícitos; no son llamadas reales a Groq ni evidencia de comprensión del modelo. El usuario aprobó pruebas locales únicamente.

## Evidencia pendiente

La validación automatizada está completada para los criterios locales. La creación de PRs y la actualización de Projects requieren que el conector GitHub disponible vuelva a aceptar operaciones; no se registran como realizadas. Los cambios permanecen en ramas temporales sin merge hasta aprobación humana.
