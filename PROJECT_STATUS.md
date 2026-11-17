# Estado de GestorTech

Verificación adicional del 2026-11-16: **155 pruebas y 77 subtests aprobados en 66,98 s**, Python 3.12.14 local y datos temporales. Se corrigieron el aislamiento de temporales y el contexto del asistente para preguntas por nombre, con aprobación del usuario para el contexto comercial. [Informe y límites](docs/verificacion_integral_2026-11-16.md). Groq real y Docker operativo siguen sin verificar en esta ejecución.

## Ampliación del 2026-11-16

La carpeta `D:\Escritorio\GestorTech` contiene la nueva tienda, shell del personal y dashboard, junto con imágenes locales validadas mediante Pillow 13.0.0, disponibilidad comercial y pasos de revisión/publicación tras aceptar propuestas IA. El usuario confirmó demostración local y aprobó la dependencia; no se activó Groq ni se modificó la base del taller. La operación y evidencia nueva están en [docs/tienda_y_catalogo.md](docs/tienda_y_catalogo.md). Los datos y runs anteriores se conservan como históricos; la validación de esta ampliación se registrará al terminar la suite y CI.

Verificación local de la ampliación: **154 pruebas y 77 subtests aprobados en 85,85 s**, con Python 3.12.14 en `.venv-review`. `pip check` aprobado. Pillow 13.0.0 instalado desde wheel oficial y declarado en requirements. La ejecución Python 3.11 de CI se registrará tras publicar el commit; las pruebas locales y sus capturas no se presentan como llamadas reales a Groq.

CI Python 3.11 aprobado para `bb49c11`: [run 44007586942](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/44007586942). El [PR #31](https://github.com/LzMauLz/Proyecto-GestorT/pull/31) está abierto sobre `test/issue-15` y depende del #30 y anteriores; no se hizo merge. El usuario indicó expresamente dejar sus datos intactos: no se respaldó, inspeccionó ni migró la base existente del taller. Para ejecutar la nueva función con esa base hay que autorizar la actualización previamente; la demo de pruebas usa datos temporales.

**Actualizado:** 2026-11-15. **Estado:** MVP local con propuestas de cambio para los issues #5, #10, #12, #7, #14 y #15. La implementación en estas propuestas no implica que se haya fusionado en `develop` o desplegado.

## Capacidades implementadas en las propuestas

| Issue | Capacidad | Evidencia y límites |
|---|---|---|
| #5 | Técnico activo obligatorio al crear/reasignar; autoasignación del técnico; unicidad por nombre/categoría normalizados con protección SQLite y preflight de migración | [Integridad](docs/issues/5-integridad.md) |
| #10 | Catálogo público sin cuentas de cliente; publicación administrativa explícita; nuevos productos e importaciones ocultos; solo campos comerciales públicos | [Catálogo](docs/issues/10-catalogo.md) |
| #12 | Límites persistentes de intentos, resolución/auditoría atómica de propuestas IA, errores sanitizados, importación endurecida y utilidad de backup/restauración controlada | [Matriz de seguridad](docs/issues/12-seguridad.md) |
| #7 | Aclaración de faltantes y precios ambiguos, fichas editables, archivos CSV/XLSX desde el asistente y revisión manual disponible sin proveedor | [Asistente](docs/issues/7-asistente.md) |
| #14 | Navegación móvil por rol, foco de errores, conservación de campos no secretos, tablas accesibles, contraste y revisión visual local integrada | [Interfaz](docs/issues/14-interfaz.md) |
| #15 | Ampliación y trazabilidad de pruebas de los flujos integrados e integración continua | [Pruebas integradas](docs/issues/15-pruebas-ci.md) |

Se conservan Python 3.11 como stack objetivo, Flask/Jinja2, SQLite, HTML/CSS/JavaScript y la arquitectura por capas. La mascota local y la identidad violeta siguen en uso. Los roles son administrador/técnico; el cliente consulta catálogo y seguimiento públicos sin cuenta.

## Validación actual

Las verificaciones actuales se realizan localmente con Flask y SQLite reales, bases temporales y datos ficticios. Los dobles del proveedor se identifican explícitamente; no se conecta Groq ni se consulta `.env` o la base del taller. Los conteos y condiciones observados se conservan en los informes de cada issue. La suite integrada del #15 pasó **131 pruebas y 77 subtests en 65,75 s** en Python 3.12.14. GitHub Actions con Python 3.11 terminó en **success** para el commit `0b4f44a`: [run 43777915059](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777915059). Estos son resultados observados y distintos de las pruebas parciales.

El ejecutable de Python 3.11 del entorno virtual original no está disponible. Las pruebas locales complementarias usan Python 3.12.14 empaquetado con las dependencias ya presentes; CI con Python 3.11 es la comprobación del stack acordado y pasó en el run enlazado.

La validación de navegador documentada en #14 utiliza Edge/Chromium headless a 375, 768 y 1440 px, servidor loopback y datos sintéticos; no equivale a pruebas con dispositivos físicos o lectores de pantalla.

## Límites y pendientes

- La comprensión semántica de Groq real no se ha probado en esta fase. Su activación y cualquier transmisión externa requieren aprobación explícita.
- No se afirma que una credencial exista ni que el proveedor esté habilitado actualmente en el entorno local; no se han leído esas configuraciones.
- Producción permanece bloqueada hasta elegir y validar TLS/proxy, servidor WSGI, política operativa de respaldos/restauración y revisión de dependencias/secretos históricos. Estos riesgos no se consideran aceptados automáticamente.
- Las migraciones no se han aplicado a datos reales. El preflight bloquea inconsistencias; el operador debe respaldar y resolverlas sin reasignaciones ni fusiones automáticas.
- Los PR #25–#31 fueron creados y están abiertos en la consulta del 2026-11-16. #31 amplía tienda, imágenes y asistente; depende de #30 y sus predecesores. Projects no se ha movido a Done en esta revisión. El PR #24 permanece abierto. Revisión y merge siguen pendientes.
- El video, el PDF final académico y tareas de evolución fuera de estos issues siguen su propio alcance.

## Evidencia histórica

[docs/evidencias.md](docs/evidencias.md) conserva las capturas de la Sesión 3: 40 pruebas y 40 subtests locales, detección/restauración de mutación y corrección de una expectativa HTTP 422 a 400. Los runs [43757548979](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43757548979) y [43768715477](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43768715477) corresponden al trabajo del PR #24 y no certifican cambios posteriores.

Los informes previos registraron 33 pruebas unittest, una validación Docker local con persistencia SQLite y una prueba controlada de Groq. Son antecedentes fechados; no representan una nueva ejecución ni verifican credenciales actuales. El informe histórico se conserva en [docs/auditoria_estado_actual.md](docs/auditoria_estado_actual.md).

## CI observado por propuesta

| Issue | Ejecución Python 3.11 | Resultado |
|---|---|---|
| #5 | [43776061344](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43776061344) | success |
| #10 | [43777324396](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777324396) | success |
| #12 | [43777324592](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777324592) | success |
| #7 | [43777324295](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777324295) | success |
| #14 | [43777914192](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777914192), commit 6d09e0a | success |
| #15 integrado | [43777915059](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777915059), commit 0b4f44a | success |
