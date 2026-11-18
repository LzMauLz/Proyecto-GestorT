# Auditoría consolidada del estado de GestorTech

**Fecha de consolidación:** 2026-11-15. Alcance: propuestas de los issues #5, #10, #12, #7, #14 y #15 integradas localmente. No implica merge, despliegue o aceptación de riesgos de producción.

## Estado verificable de las propuestas

- Integridad: técnico activo obligatorio, autoasignación y unicidad por nombre/categoría normalizados protegidas por SQLite. Migración con preflight, sin reasignaciones ni deduplicación automática: [#5](issues/5-integridad.md).
- Catálogo público aprobado: publicación explícita, altas/importaciones ocultas y datos comerciales minimizados: [#10](issues/10-catalogo.md).
- Seguridad: rate limiting SQLite local, CSRF/roles, propuestas atómicas y auditoría vinculada, rechazo de contenido activo de XLSX y errores externos sanitizados. Matriz de severidad, pruebas y límites: [#12](issues/12-seguridad.md).
- Asistente: aclaración de faltantes/ambigüedad, edición y revalidación, carga local CSV/XLSX con continuidad manual: [#7](issues/7-asistente.md).
- Interfaz: revisión real Edge headless en móvil/tablet/escritorio sobre datos ficticios, navegación por rol, foco/errores, contraste seleccionado y flujos integrados de asistente/reparación: [#14](issues/14-interfaz.md).
- La suite conjunta local pasó **131 pruebas y 77 subtests en 65,75 s**; [CI Python 3.11](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777915059) pasó para el commit **0b4f44a**. Evidencia y límites en [#15](issues/15-pruebas-ci.md). Los nuevos PR y el movimiento de Projects aún no se han completado; no se ha hecho merge.

Las ejecuciones actuales usan datos sintéticos, nunca la base del taller. Python 3.12.14 fue el runtime local complementario porque el ejecutable 3.11 del entorno virtual original no está disponible; el stack objetivo y CI continúan en Python 3.11. Los conteos observados por fase están en sus informes, sin sumarlos ni tratarlos como un conteo integrado.

## Límites que permanecen abiertos

No hubo nuevas llamadas a Groq ni lectura de credenciales. La activación, modelo y clave actuales no están auditados; los ensayos con dobles comprueban límites de confianza y contratos, no calidad semántica del proveedor real. No se verificaron lectores de pantalla/dispositivos físicos, todos los pares de contraste ni todos los formatos de archivos posibles.

La exposición a Internet sigue bloqueada: faltan decisión y validación de TLS/proxy, servidor WSGI de producción, política de backups/retención/cifrado/restauración y análisis de dependencias/secretos históricos. El snapshot/restauración SQLite se verificó sobre datos ficticios; no configura una política productiva. Estos pendientes no se registran como riesgos aceptados.

## Archivo histórico — informe de 2026-11-02

El texto siguiente se conserva como antecedente de Misiones 08–12. Sus afirmaciones sobre 33 pruebas, disponibilidad de Docker, configuración de Groq y pendientes de interfaz pertenecen a esa etapa; contiene contradicciones históricas y no sustituye el estado consolidado de arriba ni verifica secretos presentes. Se preserva para mantener trazabilidad, no como certificación vigente.

---

# Auditoría del estado actual de GestorTech

**Fecha:** 2026-11-02
**Alcance:** revisión de código, configuración de ejemplo, documentación, pruebas, interfaz, integración Groq, contenedor y estado Git. No se registran claves ni datos de la base local. Se realizó una prueba controlada de Groq con configuración local y datos ficticios.

## Resumen ejecutivo

GestorTech cuenta con un MVP web Flask/Jinja y SQLite para personal de taller y consulta pública de reparaciones. Tiene autenticación por roles, inventario con movimientos, flujo de reparaciones e historial, seguimiento público restringido e importación CSV/XLSX con revisión y aprobación humana. La identidad Gaming Premium violeta y la mascota local están integradas. Groq está integrado mediante un adaptador HTTP sin SDK y fue validado localmente.

La suite `unittest` y `compileall` pasaron en la última ejecución. Groq está integrado y validado localmente. El proyecto permanece como demo local: faltan validaciones visuales interactivas completas, Docker en ejecución y medidas contra intentos repetidos antes de cualquier despliegue público.

## Qué se auditó

- Instrucciones del proyecto (`AGENTS.md`), estado (`PROJECT_STATUS.md`) y README.
- Capas web, aplicación, dominio e infraestructura relacionadas con auth, reparaciones, inventario, importación y Groq.
- Plantillas y estilos de dashboard, login, reparaciones, inventario, importación y consulta pública.
- CSRF, roles, separación de notas internas/públicas, validación de importaciones y persistencia explícita.
- `.env.example`, Dockerfile/Compose de forma estática, tests y documentación de API/IA.
- Estado Git observable del directorio de trabajo.

## Cambios realizados en Misiones 08–12

- Se incorporó el logo/mascota original en `app/static/images/gestortech-mascot.png`, conservando transparencia, para encabezado, login y consulta pública.
- Se creó `app/static/css/gestortech-theme.css` con identidad violeta propia, ajustes de tarjetas, navegación, estado de foco y composición responsive. Se mejoró la vista pública con código destacado y progreso del flujo existente.
- Se creó la skill local independiente `.agents/skills/gestortech-design-review/` con `SKILL.md`, tres referencias y `NOTICE.md`; no incluye motor Impeccable.
- Misión 11 fue un diagnóstico solo lectura del dashboard; no cambió código.
- En Misión 12 el dashboard recibió navegación activa `aria-current`, una región de tabla navegable por teclado y estilos diferenciados para estados de reparación. Se añadieron límites defensivos al adaptador Groq: máximo 50 filas y 128 KiB de solicitud; el límite de respuesta sigue en 256 KiB. El prompt trata entradas importadas como datos no confiables.
- Se añadieron pruebas mock para timeout/límite, JSON inválido, exceso de filas y navegación/tabla del dashboard.
- Se sincronizaron README, PROJECT_STATUS y `docs/uso_ia.md`. `.env.example` conserva `GROQ_API_KEY=` y `GROQ_MODEL=` vacíos con `GROQ_ENABLED=false`.

## Estado por módulo

| Módulo | Estado | Pendiente principal |
|---|---|---|
| Autenticación | Login, sesión, roles, CSRF y creación inicial de administrador | Mitigar intentos repetidos; revisar recuperación/cambio y baja de cuentas. |
| Dashboard | Indicadores admin, órdenes recientes, vacío, acción principal y navegación activa | Comprobación visual en navegador; adaptación real en dispositivos pequeños. |
| Reparaciones | Registro, asignación, transiciones, historial, notas internas/públicas | Revisión interactiva de estados, errores, teclado y permisos con roles distintos. |
| Seguimiento público | Código, estado, progreso e historial público; salida limitada y no-cache | Confirmar visualmente layouts y accesibilidad; mantener minimización de información. |
| Inventario | Catálogo, edición, baja lógica y movimientos trazables | Búsqueda/filtros no están implementados; no inventar controles hasta aprobar funcionalidad/backend. |
| Importación CSV/XLSX | Límites, normalización, vista previa editable, selección y aprobación humana | Probar visualmente archivos largos/errores en navegador; la vía IA permanece apagada. |
| Groq | Adaptador HTTP estándar, validación, límites, chat y fallback manual; prueba local controlada realizada | Mantener la credencial fuera de Git y revisar el proveedor antes de producción. |
| Documentación | README, estado, API, uso IA y decisiones existentes | Mantener trazabilidad sincronizada con futuras pruebas y cambios. |

## Seguridad y privacidad

- La consulta pública debe continuar exponiendo únicamente estado y eventos publicados. No añadir datos privados a HTML/JavaScript para ocultarlos visualmente.
- Las rutas mantienen login/roles; ocultar acciones en la interfaz nunca sustituye autorización en backend.
- Los formularios mutables deben conservar CSRF y validación de servidor.
- Las propuestas de IA no escriben por sí mismas en SQLite; el flujo manual permanece disponible ante desactivación o error.
- No se instaló SDK adicional. La clave activa se mantiene fuera de Git y no se reproduce en este informe.

## Pruebas y verificaciones

- `python -B -m compileall -q app tests`: aprobado.
- `python -B -m unittest discover -s tests -v`: **33 pruebas aprobadas** en la última ejecución.
- Rediseño frontend verificado en navegador integrado para seguimiento público y login: render correcto, sin overflow horizontal en 390/660/1440 px y foco por teclado alcanzable. No se usaron datos reales ni se validó dashboard autenticado en navegador.
- Cobertura relevante: auth/CSRF, roles y acceso a órdenes, privacidad del seguimiento, stock transaccional, importación manual, mocks IA, fallos/timeouts y aprobación humana.
- Pytest está declarado en `requirements.txt`; la validación registrada se ejecutó principalmente con `unittest`.
- No se realizó comprobación visual interactiva ni pruebas con lector de pantalla/dispositivos reales. Las pruebas Flask verifican render y comportamiento HTTP, no el aspecto renderizado.

## Docker y Git

- Docker/Compose no están disponibles en el entorno; Dockerfile y Compose tienen revisión estática. Build, inicio, login y persistencia SQLite dentro del contenedor siguen sin comprobar.
- El repositorio GitHub `LzMauLz/Proyecto-GestorT` tiene `main` y `develop`; el Pull Request #1 fue fusionado.

## Pendientes priorizados

1. **Seguridad previa a Internet:** control de intentos en login y seguimiento, revisión de manejo de sesiones, HTTPS, backups, logging y servidor WSGI de producción.
2. **Pruebas visuales:** revisar los roles admin/técnico y el cliente en escritorio, tablet y anchos 320/375/768/1024; evaluar contraste, teclado, zoom y movimiento reducido.
3. **Docker:** validar build, usuario no-root, filesystem read-only, inicio, sesión y persistencia en un entorno que tenga Docker.
4. **Funciones no existentes:** búsqueda/filtros de inventario y recuperación/baja de cuentas requieren definición funcional y aprobación antes de programarlas.

## Conclusión

El MVP ofrece los flujos centrales de taller y una identidad visual consistente para evaluación local. Groq está integrado y fue probado localmente; la clave permanece fuera del repositorio. La evidencia automatizada disponible es positiva (33 pruebas y compilación), y Docker fue ejecutado con respuesta HTTP 200 y persistencia SQLite tras reinicio, aunque no equivale a aprobación de producción. No desplegar públicamente hasta completar los pendientes de seguridad y operación.
