# Uso responsable de IA en el MVP

**Actualizado: 2026-11-15.** Implementación en propuestas pendientes de revisión/merge. La validación actual es local con datos sintéticos y dobles explícitos del proveedor; no se realizan llamadas a Groq ni se inspecciona `.env`.

## Uso realizado

- Codex asistió en la implementación, organización de archivos y redacción de documentación y pruebas.
- El historial previo registra una prueba controlada de Groq con datos ficticios. No se repitió en esta fase y no permite afirmar que hoy exista una credencial configurada o que el proveedor esté habilitado.
- No se generaron productos, precios, cantidades ni compatibilidades mediante IA.

## Decisiones y revisión humana

- El flujo de estados que no estaba definido en Módulo 2 lo confirmó el usuario antes de implementarlo.
- El flujo manual CSV/XLSX permanece disponible cuando Groq está desactivado, no tiene configuración suficiente o falla.
- El parser produce una previsualización. La persona puede editar y seleccionar filas antes de guardar; las filas incompletas no reciben valores inventados.
- Comentarios del historial requieren un campo explícito para publicarse; el texto interno no se copia a la vista pública.

## Correcciones y verificaciones históricas

- Las pruebas descubrieron un formato incorrecto en un archivo simulado de carga; se corrigió el fixture.
- La inspección del CLI mostró que Flask registra `create-admin` bajo el grupo `auth`; se corrigieron README y pasos de Docker para usar `auth create-admin`.
- Se corrigió el cierre del archivo de esquema SQLite tras observar un `ResourceWarning`.
- La revisión de privacidad retiró equipo y descripción del problema de la respuesta pública.
- En la fase histórica se registraron `compileall` y 33 pruebas unittest; después la Sesión 3 incorporó Pytest y CI. Esos conteos son antecedentes, no el resultado actual de las propuestas. La validación vigente se registra en `docs/issues/` y `docs/evidencias.md`.
- El proyecto se entrega como trabajo individual; no se atribuye revisión independiente a un segundo integrante.

## Integración de Groq

Se implementaron `ProductProposalProvider` (puerto), `prepare_product_proposal` (orquestación y validación) y `GroqAdapter` (adaptador HTTP con biblioteca estándar). No se instaló el SDK ni se incorporaron credenciales durante esta fase. No se realizó una auditoría de secretos de todo el historial Git. La configuración central está en `config/settings.py`; `.env.example` enumera `GROQ_API_KEY`, `GROQ_MODEL` y `GROQ_ENABLED=false` sin secretos. Las nuevas propuestas se verifican con proveedor simulado y aplicación/SQLite reales; el comportamiento semántico de un modelo real queda pendiente.

Al activar el proveedor posteriormente, la solicitud contendrá solo `source_row`, `name`, `description` y `category` de filas válidas, hasta 50 filas y 128 KiB. Precio, stock, datos de clientes y filas inválidas quedan fuera. El adaptador solicita JSON, no habilita herramientas, limita la espera a 12 segundos y la respuesta a 256 KiB. La aplicación valida forma, filas y campos. No hace reintentos; timeout, error de conexión, límite del proveedor o respuesta inválida vuelven al modo manual sin registrar el cuerpo ni persistir automáticamente. La propuesta queda editable; marcar filas y confirmar es obligatorio.

**Implementado en las propuestas:** puerto/adaptador, límites, validación, fallback y revisión humana. Las pruebas locales del contrato no demuestran que Groq siempre interprete correctamente el lenguaje ni resista toda prompt injection. No se inspeccionó la configuración secreta actual.

Referencias oficiales: [API reference](https://console.groq.com/docs/api-reference), [Structured Outputs](https://console.groq.com/docs/structured-outputs), [Models](https://console.groq.com/docs/models). Se usa JSON Object con validación adicional local.

El endpoint `/api/ia/importacion/propuesta` requiere administrador, informa `modo` como `manual` o `groq` y siempre incluye `requiere_revision_humana: true`.

## Asistente conversacional de inventario

El panel `/assistant` y los endpoints `/api/asistente/mensaje` permiten a administradores consultar el inventario, redactar o mejorar descripciones y preparar propuestas de uno o varios productos (hasta 20 por solicitud) o movimientos. Si falta nombre, precio o stock, se pide aclaración antes de preparar la propuesta. Los precios con separador de miles local, como `5.000,00`, se normalizan; el stock cero debe estar indicado explícitamente. Los técnicos solo pueden realizar consultas; no pueden preparar ni confirmar cambios.

El asistente recibe un contexto factual limitado generado por servicios de consulta SQLite. No recibe permiso para ejecutar SQL, código, herramientas ni solicitudes arbitrarias. El modelo devuelve JSON validado localmente; cualquier propuesta se guarda temporalmente en `ai_proposals` y requiere confirmación explícita de un administrador. La confirmación vuelve a validar el usuario, producto, tipo, cantidad y stock y ejecuta `create_product` o `move_stock`; cancelar no modifica inventario.

La auditoría mínima se almacena en `ai_operations` ligada por `proposal_id` a la propuesta concreta, con usuario, operación, producto cuando aplica y estado de aprobación. La resolución reserva la propuesta pendiente dentro de una transacción, valida propietario/rol y evita confirmación doble. La confirmación de una propuesta múltiple crea todos los productos en una sola transacción: si un elemento falla, no se guarda ninguno. No se almacenan claves, tokens ni el contenido completo del proveedor. Groq no se consulta mientras `GROQ_ENABLED=false` o falte clave, modelo o configuración válida.

## Revisión explícita del asistente — issue #7

Las propuestas de productos requieren nombre, precio y cantidad explícitos. Si falta un dato, el asistente pregunta antes de crear una propuesta; no se aplican ceros por omisión. Las fichas permiten corregir esos campos antes de confirmar y el servidor los revalida.

Los archivos adjuntos desde `/assistant` se extraen localmente mediante el parser existente, con selección de campos y filtro por palabras clave. No se envían archivos ni columnas desconocidas al proveedor. La previsualización, aprobación y cancelación manual siguen disponibles cuando la IA está desactivada.

Precios como `1.234` o `5.000` se consideran ambiguos y generan aclaración; `5000`, `5000.00` y `5.000,00` son formatos inequívocos admitidos. Los valores ausentes no se convierten en cero. Publicar el producto sigue siendo una operación administrativa independiente.
