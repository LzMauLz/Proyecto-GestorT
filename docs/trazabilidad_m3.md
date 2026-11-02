# Trazabilidad Módulo 2 / actividad Módulo 3

| Requisito | Evidencia del MVP | Pruebas |
|---|---|---|
| Separar interfaz, controlador, servicio y adaptador de persistencia | `app/web`, `app/application`, `app/domain`, `app/infrastructure` | importación de app y pruebas de servicios/rutas |
| Usuarios autorizados y roles | Login, administración de usuarios, restricción por rol | login/roles y CSRF |
| Productos y movimientos de inventario | Catálogo, baja lógica, entradas/salidas transaccionales sin stock negativo | productos, atomicidad y permisos |
| Crear reparación y código único | Alta con código aleatorio de 128 bits | creación y consulta |
| Cambios de estado e historial | Matriz de transición acordada; historial interno y público separado | probado: transiciones válidas e inválidas |
| Consulta pública limitada | Código requerido; salida excluye problema, notas privadas e identidad | probado: contenido público y `no-store` |
| Importar CSV/XLSX con aprobación | Previsualización, campos editables, selección explícita por persona | probado: CSV/XLSX y aprobación de fila |
| IA desacoplada y opcional; continuidad manual | Puerto/adaptador Groq disponible pero apagado; manual como fallback; documentación en `docs/uso_ia.md` | pruebas simuladas, modo manual y aprobación humana |
| API documentada | OpenAPI 3.1 en `/api/openapi.json`, guía en `docs/api.md` | probado: especificación y rutas principales |
| Configuración segura | secret env, `.env.example`, `.gitignore`, CSRF, cookies y headers | tests de configuración/sesión |
| Docker y demo reproducible | Dockerfile, Compose y pasos README | No ejecutado: Docker no disponible |
| Colaboración Git/PR | Repositorio GitHub con `main` y `develop`; trabajo individual | No atribuir una revisión o contribución de otra persona |

Verificación registrada: `python -B -m compileall -q app tests` y `python -B -m unittest discover -s tests -v` (32 pruebas aprobadas, ejecución del 2026-11-01). La revisión visual del rediseño se realizó en navegador integrado sobre seguimiento público y login, con comprobación de overflow en 390/660/1440 px y foco inicial por teclado. Docker/Compose no fueron ejecutados en este entorno.
