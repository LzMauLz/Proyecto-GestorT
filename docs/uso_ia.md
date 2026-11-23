# Uso responsable de IA

GestorTech conecta su asistente de inventario con Groq mediante un adaptador HTTP opcional. No se requiere un SDK. La demo de PythonAnywhere se verificó con Groq habilitado y datos ficticios. En una instalación nueva, la IA empieza desactivada.

| Operación | Rol | Qué hace |
|---|---|---|
| Consulta en Asistente IA | Administrador y técnico | Responde preguntas sobre inventario a partir de un contexto factual limitado. |
| Propuesta de producto o movimiento | Administrador | Prepara fichas editables de hasta 20 productos o un movimiento permitido. Solicita datos faltantes o ambiguos. |
| Redacción de descripción | Administrador | Sugiere un texto editable en el formulario de producto, antes de guardar. |
| Previsualización CSV/XLSX | Administrador | Procesa el archivo localmente. Con IA optativa sugiere campos descriptivos. El administrador selecciona las filas que quiere guardar. |

Las propuestas requieren confirmación. El backend aplica roles, propiedad de la propuesta y validaciones de dominio. Una propuesta múltiple se guarda en una transacción. Cancelar no cambia las existencias. Confirmar una ficha no la publica. Añadir la imagen y publicar son decisiones posteriores.

## Datos y límites

- Envía únicamente datos de producto. Nunca incluyas nombres de clientes, teléfonos, notas internas, credenciales o archivos con datos personales.
- El chat envía la solicitud, un historial limitado y contexto comercial de inventario según la consulta. No habilita herramientas, SQL ni acceso directo del modelo a SQLite. Las imágenes se cargan a GestorTech y no se envían a Groq.
- En importación se transmiten solo el identificador de fila, nombre, descripción y categoría de hasta 50 filas válidas. El archivo, sus columnas desconocidas, los precios y las cantidades no se envían. Precio y cantidad deben venir del archivo o de una indicación explícita.
- Las solicitudes están limitadas a 128 KiB y las respuestas a 256 KiB. El adaptador aplica un timeout configurable. El backend valida la estructura JSON y los valores. Ante error, conserva la opción manual.
- El modelo puede malinterpretar el texto o sugerir detalles que no constan en la fuente. Revisa siempre la descripción y los campos antes de confirmar. La prueba con Groq acredita los casos ejercitados.

## Configuración y verificación

El catálogo ofrece **Buscar por modelo**. La modalidad con IA usa una pregunta breve para extraer la marca y el modelo que escribió el cliente. Solo se envía a Groq esa pregunta, hasta 140 caracteres. El formulario pide excluir datos personales y la aplicación bloquea patrones comunes de correos, teléfonos y enlaces.

GestorTech compara la marca y el modelo con la compatibilidad registrada por el taller. Si hace falta una variante o falta confirmar la marca, presenta las opciones para que el cliente elija. La búsqueda manual sigue disponible ante límites, respuestas inválidas o fallos de Groq.

El chat público usa la misma búsqueda por modelo cuando el cliente activa la opción con IA. Las consultas por producto consultan directamente el catálogo público. Las respuestas del chat público se construyen con fichas, precios y disponibilidad pública. El chat del taller exige iniciar sesión y consulta estados de reparación, existencias bajas o información administrativa según el rol. GestorTech resuelve esas consultas operativas en SQLite. Las propuestas de inventario siguen el flujo de confirmación administrativa.

`GROQ_ENABLED=false` mantiene el flujo manual. Para habilitar IA en un entorno autorizado, configura `GROQ_ENABLED=true`, `GROQ_MODEL` y `GROQ_API_KEY` de forma privada. `GROQ_TIMEOUT` admite de 1 a 60 segundos y por defecto usa 12. Evita compartir claves en Git, capturas, mensajes o prácticas de sustentación.

Rutas: `/assistant`, `POST /api/asistente/mensaje`, `POST /api/asistente/propuestas/<id>/confirmar`, `POST /api/asistente/propuestas/<id>/cancelar`, `POST /products/suggest-description` y `POST /api/ia/importacion/propuesta`. Consulta [la API](api.md) y [la evidencia real](entrega_funcional.md).

Codex apoyó la implementación, las pruebas y la redacción. Se revisaron las propuestas y los resultados antes de aplicarlos. La entrega es individual.
