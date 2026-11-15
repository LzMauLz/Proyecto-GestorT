# Issue #15 — Pruebas y CI

La suite de la Sesión 3 es el punto de partida. Este issue comprueba los flujos ampliados y sus errores, sin reemplazar pruebas existentes para obtener un resultado verde.

## Matriz de aceptación

| Criterio | Evidencia de código a integrar | Estado |
|---|---|---|
| Asignación obligatoria y técnico válido | tests/test_integrity.py, issue #5 | Pendiente de ejecución integrada |
| Nombre único dentro de categoría, edición y concurrencia | tests/test_integrity.py, issue #5 | Pendiente de ejecución integrada |
| Catálogo público y privacidad | tests/test_catalog.py, issue #10 | Pendiente de ejecución integrada |
| Propuestas editables, faltantes, CSV/XLSX y aprobación | tests/test_assistant_workflow.py, issue #7 | Pendiente de ejecución integrada |
| Permisos, CSRF, límites, errores y transacciones | tests/test_security.py, issue #12 | Pendiente de ejecución integrada |
| Reglas puras de dinero, cantidades y JSON | tests/test_unit_rules.py | Comprobado localmente |
| Concordancia de rutas/métodos y OpenAPI | tests/test_api_contract.py | Comprobado antes de integración |
| CI Python 3.11 con datos ficticios | .github/workflows/ci.yml | Pendiente de publicación y consulta del run |

## Verificaciones observadas

Las pruebas nuevas de reglas puras y contrato pasaron: **26 passed en 0,93 s**, con Python 3.12.14 empaquetado y dependencias existentes. Las reglas puras no requieren fixture Flask/SQLite. La comprobación de contrato compara el mapa de rutas real con los métodos/path de OpenAPI.

El entorno virtual local apunta a un Python 3.11 ausente. La ejecución complementaria con Python 3.12 no sustituye la comprobación obligatoria de CI con Python 3.11.

## Alcance de datos y proveedor

Los tests usan Flask y SQLite reales en bases temporales con datos ficticios. Las pruebas de concurrencia usan conexiones independientes. Los fallos de proveedor se inducen con dobles explícitos; no son llamadas reales a Groq ni evidencia de comprensión del modelo. El usuario aprobó pruebas locales únicamente.

## Evidencia pendiente

Actualizar esta matriz con comandos, resultados integrados, commit validado y enlaces a Actions antes de marcar el issue como terminado. Los PR permanecen sin merge hasta aprobación humana.
