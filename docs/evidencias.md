# Evidencias del proyecto GestorTech

Registro acumulativo de pruebas, integración continua y entregas académicas. Se actualizará cuando se incorporen nuevas evidencias verificadas.

## Módulo 6 · Sesión 3: pruebas e integración continua

### Suite local

El 14 de noviembre de 2026 se ejecutó `python -m pytest -q` desde el entorno virtual del proyecto. Resultado reportado en terminal: **40 pruebas aprobadas y 40 subtests aprobados**, en 50,92 segundos.

![Ejecución completa de la suite](evidencias/sesion-3-suite-completa.png)

La ejecución de CI en GitHub también muestra el job `tests` en verde y el resumen de Pytest:

![Resumen verde del workflow](evidencias/sesion-3-ci-resumen-success.png)

![Detalle del job de pruebas y resumen de Pytest](evidencias/sesion-3-ci-tests-pytest.png)

### Comprobación de mutación

El 15 de noviembre de 2026 se modificó temporalmente `_to_integer` para aceptar booleanos como enteros. La prueba `test_product_stock_and_movement_quantity_require_integers` detectó la regresión: fallaron los dos subtests con `True` (uno para existencias iniciales y otro para movimiento de inventario). Después se restauró la condición original y la misma prueba pasó: **1 prueba y 8 subtests aprobados**.

![La prueba detecta la mutación](evidencias/sesion-3-mutacion-detectada.png)

![La prueba pasa después de restaurar el código](evidencias/sesion-3-mutacion-restaurada.png)

### Revisión de una prueba sugerida por IA

En un ejercicio de revisión, el primer borrador de IA para el endpoint `POST /api/productos` esperaba HTTP 422 ante un precio inválido. La ejecución dirigida mostró HTTP 400 (`400 != 422`), que es el código que usa el controlador Flask al convertir el error de dominio. Se corrigió la prueba a `test_invalid_product_price_returns_400`; el usuario ejecutó la prueba corregida y obtuvo **1 passed en 1,19 s**.

Esta comprobación documenta el error real del borrador generado durante el ejercicio; no se cambió la regla del endpoint.

![Borrador de IA con expectativa incorrecta de HTTP 422](evidencias/sesion-3-test-ia-422-fallido.png)

![Prueba corregida para HTTP 400 aprobada](evidencias/sesion-3-test-corregido-400.png)

### Integración continua

- Workflow: `.github/workflows/ci.yml`.
- Python: 3.11; dependencias instaladas desde `requirements.txt`; ejecución `python -m pytest -q`.
- Eventos: `push` y `pull_request`.
- No requiere secretos ni realiza llamadas al proveedor de IA.
- Ejecución verificada en `push`: [GitHub Actions run 43757548979](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43757548979), resultado **success**.
- Pull Request [#24](https://github.com/LzMauLz/Proyecto-GestorT/pull/24), abierto hacia `develop` para revisión; no fusionado.
- Ejecución verificada en `pull_request`: [GitHub Actions run 43768715477](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43768715477), resultado **success**.

## Historial

Añadir aquí futuras pruebas, capturas, resultados de Actions y enlaces a Pull Requests, indicando fecha y resultado observado. No registrar secretos ni datos reales de clientes.
