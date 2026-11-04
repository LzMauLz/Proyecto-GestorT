# Uso responsable de IA en el MVP

## Uso realizado

- Codex asistió en la implementación, organización de archivos y redacción de documentación y pruebas.
- La integración Groq se probó con una credencial configurada únicamente en el entorno local. No se enviaron código, documentos, credenciales ni datos reales de clientes.
- No se generaron productos, precios, cantidades ni compatibilidades mediante IA.

## Decisiones y revisión humana

- El flujo de estados que no estaba definido en Módulo 2 lo confirmó el usuario antes de implementarlo.
- El flujo manual CSV/XLSX permanece disponible cuando Groq está desactivado, no tiene configuración suficiente o falla.
- El parser produce una previsualización. La persona puede editar y seleccionar filas antes de guardar; las filas incompletas no reciben valores inventados.
- Comentarios del historial requieren un campo explícito para publicarse; el texto interno no se copia a la vista pública.

## Correcciones y verificaciones

- Las pruebas descubrieron un formato incorrecto en un archivo simulado de carga; se corrigió el fixture.
- La inspección del CLI mostró que Flask registra `create-admin` bajo el grupo `auth`; se corrigieron README y pasos de Docker para usar `auth create-admin`.
- Se corrigió el cierre del archivo de esquema SQLite tras observar un `ResourceWarning`.
- La revisión de privacidad retiró equipo y descripción del problema de la respuesta pública.
- Se ejecutaron `python -B -m compileall -q app config tests` y 33 pruebas con `python -B -m unittest discover -s tests -v`; Pytest no se ejecutó porque la validación principal usa `unittest`.
- El proyecto se entrega como trabajo individual; no se atribuye revisión independiente a un segundo integrante.

## Integración de Groq

Se implementaron `ProductProposalProvider` (puerto), `prepare_product_proposal` (orquestación y validación) y `GroqAdapter` (adaptador HTTP con biblioteca estándar). No se instaló el SDK ni se guardó ninguna API Key en el repositorio. La configuración central está en `config/settings.py`; `.env.example` enumera `GROQ_API_KEY`, `GROQ_MODEL` y `GROQ_ENABLED=false` sin secretos. La integración se probó localmente con el modelo configurado en `.env`.

Al activar el proveedor posteriormente, la solicitud contendrá solo `source_row`, `name`, `description` y `category` de filas válidas, hasta 50 filas y 128 KiB. Precio, stock, datos de clientes y filas inválidas quedan fuera. El adaptador solicita JSON, no habilita herramientas, limita la espera a 12 segundos y la respuesta a 256 KiB. La aplicación valida forma, filas y campos. No hace reintentos; timeout, error de conexión, límite del proveedor o respuesta inválida vuelven al modo manual sin registrar el cuerpo ni persistir automáticamente. La propuesta queda editable; marcar filas y confirmar es obligatorio.

**Implementado y verificado:** puerto, adaptador, configuración, límites, validación, fallback, operación manual, chat y pruebas automatizadas. La clave permanece fuera del repositorio. No se incluyen credenciales en este documento.

Referencias oficiales: [API reference](https://console.groq.com/docs/api-reference), [Structured Outputs](https://console.groq.com/docs/structured-outputs), [Models](https://console.groq.com/docs/models). Se usa JSON Object con validación adicional local.

El endpoint `/api/ia/importacion/propuesta` requiere administrador, informa `modo` como `manual` o `groq` y siempre incluye `requiere_revision_humana: true`.

## Asistente conversacional de inventario

El panel `/assistant` y los endpoints `/api/asistente/mensaje` permiten a administradores consultar el inventario, redactar o mejorar descripciones y preparar propuestas de uno o varios productos (hasta 20 por solicitud) o movimientos. Los técnicos solo pueden realizar consultas; no pueden preparar ni confirmar cambios.

El asistente recibe un contexto factual limitado generado por servicios de consulta SQLite. No recibe permiso para ejecutar SQL, código, herramientas ni solicitudes arbitrarias. El modelo devuelve JSON validado localmente; cualquier propuesta se guarda temporalmente en `ai_proposals` y requiere confirmación explícita de un administrador. La confirmación vuelve a validar el usuario, producto, tipo, cantidad y stock y ejecuta `create_product` o `move_stock`; cancelar no modifica inventario.

La auditoría mínima se almacena en `ai_operations` con usuario, tipo de operación, producto cuando aplica, resultado y estado de aprobación. La confirmación de una propuesta múltiple crea todos los productos en una sola transacción: si un elemento falla, no se guarda ninguno. No se almacenan claves, tokens ni el contenido completo del proveedor. Groq no se consulta mientras `GROQ_ENABLED=false` o falte clave, modelo o configuración válida.
