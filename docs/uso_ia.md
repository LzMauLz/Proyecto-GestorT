# Uso responsable de IA en el MVP

## Uso realizado

- Codex asistió en la implementación, organización de archivos y redacción de documentación y pruebas.
- No se conectó proveedor externo de inferencia y no se enviaron código, documentos, credenciales, datos reales de clientes ni inventario a servicios de IA externos durante esta misión.
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
- Se ejecutaron `python -B -m compileall -q app tests` y 26 pruebas con `python -B -m unittest discover -s tests -v`; Pytest no se ejecutó porque no está instalado.
- La aprobación final del MVP y la revisión independiente por un segundo integrante siguen pendientes.

## Preparación de Groq

Se implementaron `ProductProposalProvider` (puerto), `prepare_product_proposal` (orquestación y validación) y `GroqAdapter` (adaptador HTTP con biblioteca estándar). No se instaló el SDK, no se utilizó ni guardó ninguna API Key, y no se hizo ninguna solicitud externa. La configuración central está en `config/settings.py`; `.env.example` enumera `GROQ_API_KEY`, `GROQ_MODEL` y `GROQ_ENABLED=false` sin secretos.

Al activar el proveedor posteriormente, la solicitud contendrá solo `source_row`, `name`, `description` y `category` de filas válidas, hasta 50 filas y 128 KiB. Precio, stock, datos de clientes y filas inválidas quedan fuera. El adaptador solicita JSON, no habilita herramientas, limita la espera a 12 segundos y la respuesta a 256 KiB. La aplicación valida forma, filas y campos. No hace reintentos; timeout, error de conexión, límite del proveedor o respuesta inválida vuelven al modo manual sin registrar el cuerpo ni persistir automáticamente. La propuesta queda editable; marcar filas y confirmar es obligatorio.

**Preparado:** puerto, adaptador, configuración, límites, validación, fallback, operación manual y pruebas simuladas. **Pendiente:** revocar toda credencial compartida accidentalmente en chats, aprobación explícita para transmitir los campos, configurar una credencial nueva directamente en el entorno local, verificar y elegir un modelo oficial, activar y evaluar funcionamiento. No guardar credenciales en este repositorio. Este documento no autoriza esas acciones.

Referencias oficiales: [API reference](https://console.groq.com/docs/api-reference), [Structured Outputs](https://console.groq.com/docs/structured-outputs), [Models](https://console.groq.com/docs/models). Se usa JSON Object con validación adicional local.

El endpoint `/api/ia/importacion/propuesta` requiere administrador, informa `modo` como `manual` o `groq` y siempre incluye `requiere_revision_humana: true`.

## Asistente conversacional de inventario

El panel `/assistant` y los endpoints `/api/asistente/mensaje` permiten a administradores consultar el inventario, redactar o mejorar descripciones y preparar propuestas de productos o movimientos. Los técnicos solo pueden realizar consultas; no pueden preparar ni confirmar cambios.

El asistente recibe un contexto factual limitado generado por servicios de consulta SQLite. No recibe permiso para ejecutar SQL, código, herramientas ni solicitudes arbitrarias. El modelo devuelve JSON validado localmente; cualquier propuesta se guarda temporalmente en `ai_proposals` y requiere confirmación explícita de un administrador. La confirmación vuelve a validar el usuario, producto, tipo, cantidad y stock y ejecuta `create_product` o `move_stock`; cancelar no modifica inventario.

La auditoría mínima se almacena en `ai_operations` con usuario, tipo de operación, producto cuando aplica, resultado y estado de aprobación. No se almacenan claves, tokens ni el contenido completo del proveedor. Groq no se consulta mientras `GROQ_ENABLED=false` o falte clave, modelo o configuración válida.
