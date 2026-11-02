# Decisiones de implementación del MVP

Estas decisiones traducen la arquitectura de Módulo 2 a un MVP ejecutable. No alteran el PDF original.

| Tema | Decisión | Motivo y alcance |
|---|---|---|
| Estados de reparación | Recibido → En diagnóstico → Esperando aprobación → En reparación → Listo para entregar → Entregado; Cancelado desde cualquier estado activo. Desde Listo para entregar se permite volver a En reparación. | Flujo confirmado por el usuario el 2026-10-31; Módulo 2 ilustraba estados, pero no definía la matriz de transiciones. Estados terminales: Entregado y Cancelado. |
| Roles | admin y technician. Administración crea usuarios, gestiona inventario y ve/reasigna todas las órdenes; técnico ve y modifica solo órdenes asignadas y puede registrar órdenes que quedan asignadas a sí mismo. | El PDF define administración y técnico, y consulta de órdenes asignadas; no enumera el nombre interno del rol. |
| Seguimiento | Código `GT-` más 128 bits aleatorios. Respuesta pública no muestra equipo, problema, cliente, nota interna o usuario. | La muestra GT-000123 del PDF es ilustrativa; código aleatorio reduce enumeración. |
| Historial público | Cada avance guarda notas internas y una nota pública separadas; solo una nota pública explícita se incluye en el seguimiento. | La consulta debe limitarse a información aprobada. Los campos internos no se serializan en el endpoint público. |
| Asignación | `repairs.assigned_to` referencia a usuario técnico. | Hace posible aplicar el requisito del actor técnico asignado, no representado en el esquema original. |
| Precio | Almacenamiento como entero en centavos (`price_cents`), validación con Decimal, máximo de almacenamiento SQLite y máximo de dos decimales. | Evita errores de precisión monetaria y overflow. |
| Cantidades | Existencias entre cero y 2.147.483.647; cada movimiento entre uno y 2.147.483.647; precios de importación sin separador de miles, punto decimal opcional. | Límites de entrada defensivos y formato de importación explícito; comunicar estos límites al taller. |
| Importación | Parser CSV/XLSX local, previsualización en base temporal, selección y edición humana; puerto/adaptador Groq preparado y apagado por defecto. | Solo tras habilitación aprobada se podrían enviar campos de catálogo limitados; existe continuidad manual y no hay llamadas ni credenciales incorporadas. |
| Seguridad CSRF | Token de sesión para métodos mutables en páginas y API. | Protege solicitudes autenticadas basadas en cookie. |
| API | Rutas en español alineadas con la especificación inicial, sesión web y documento OpenAPI 3.1 servido en `/api/openapi.json`. | La propuesta de importación devuelve modo manual o sugerencia validada; siempre requiere revisión humana y no persiste por sí sola. |
| Servidor | Flask integrado para demo local; no para despliegue público. | Docker no está disponible para validación local y no se añadió servidor de producción. |

## Pendientes de decisión/validación

- Confirmar política de acceso del técnico a los productos. El MVP permite consulta de inventario, pero solo administración escribe movimientos y catálogo.
- Revisar protección adicional contra intentos repetidos en login y consulta de seguimiento antes de exponer el sistema a Internet.
- La zona horaria se guarda como UTC ISO 8601; revisar presentación localizada si la evaluación la exige.
