# Issue #7 — Asistente y revisión de inventario

## Implementado

- Conversación libre conserva puerto/adaptador de IA. Las instrucciones piden aclaración ante ambigüedad; el backend comprueba nombre, precio y cantidad explícitos antes de guardar una propuesta de producto. Cero explícito es válido; un campo vacío no se convierte en cero.
- Propuestas visibles como fichas editables, con campos permitidos y confirmación/cancelación. El servidor revalida correcciones; no admite cambios de usuario, operación o publicación enviados por cliente.
- Adjuntar CSV/XLSX desde el asistente abre la previsualización existente. La extracción es local incluso con IA desactivada; el archivo y las columnas ajenas al producto no se envían al proveedor.
- El usuario selecciona campos y puede filtrar por todas las palabras clave sobre nombre, descripción o categoría. Se aceptan alias de encabezados existentes; encabezados que compiten por el mismo campo se rechazan con explicación. Un archivo de encabezados desconocidos necesita corrección manual.
- La vista previa conserva los valores conocidos, marca faltantes y requiere selección de filas antes de persistir. Se mantienen los límites de 5 MB, 1.000 filas, 30 columnas y 20 MB descomprimidos.
- Administración prepara/importa y confirma cambios. Técnicos solo consultan. La publicación en catálogo sigue siendo una decisión administrativa separada.

## Rutas y contratos

- `POST /assistant/import`: multipart administrativo con CSRF; `archivo`, `palabras` opcional (máximo 100 caracteres), lista `campos` dentro de `name`, `description`, `category`, `price`, `stock`. Devuelve la previsualización editable existente o un mensaje seguro y redirección.
- `POST /api/asistente/propuestas/<id>/confirmar`: conserva confirmación sin cuerpo para propuestas completas; admite JSON `correcciones` con el payload de producto, lote `products` o movimiento según la operación almacenada. No puede cambiar el tipo de operación.
- Si faltan datos en una propuesta del proveedor, `/api/asistente/mensaje` devuelve `action: answer`, `proposal: null` y una pregunta concreta; no crea propuesta ni producto.

## Diseño

Se aplicaron las guías `frontend-design` y `ui-ux-pro-max` (secciones web de accesibilidad, interacción, formularios y responsive), sin ejecutar sus scripts ni añadir dependencias. Se conservaron etiquetas visibles, controles nativos, estado ocupado, errores recuperables, foco existente y movimiento reducido sobre la identidad existente: superficies grafito, acento violeta, tipografía local, mascota preservada y fichas orientadas a revisar datos. Formularios con etiquetas, controles de al menos 44 px, mensajes de estado, protección frente a doble envío y recuperación de errores. En móvil la revisión usa una columna.

## Validación y límites

Pruebas locales con Flask/SQLite reales y datos ficticios. Los proveedores son dobles explícitos; no se realizaron llamadas externas. El Python 3.11 del entorno virtual original no se encuentra en su ruta. Se utilizó Python 3.12.14 bundled de Codex con las dependencias ya existentes del entorno virtual; esto es validación complementaria y no reemplaza CI con Python 3.11.

La comprensión de lenguaje natural de Groq real y una auditoría visual interactiva de navegador siguen sin verificarse en esta entrega. Los mensajes escritos al chat, historial permitido y contexto limitado de inventario se transmiten solo cuando el proveedor está habilitado; deben contener únicamente datos de catálogo y no datos personales. No se afirma detección perfecta de información sensible en texto libre.

Se cambió la prueba antigua que esperaba stock faltante convertido en cero para verificar aclaración y ausencia de persistencia. El caso válido de precio localizado y stock cero explícito permanece cubierto por una prueba separada.

Resultado observado en este worktree: **54 passed, 43 subtests passed** (42,44 s). JavaScript pasó `node --check app/static/js/app.js`; `git diff --check` no reportó errores. No se ejecutó un proveedor real ni una validación de navegador.

La preparación de movimientos exige un producto activo existente; IDs inexistentes o retirados devuelven una aclaración sin crear propuesta.
Validación posterior a la guardia de producto activo: **14 passed, 5 subtests passed** en `tests/test_assistant_workflow.py` (11,61 s), mismo runtime complementario. La integración final con #12/#10 y CI Python 3.11 corresponde a la revisión conjunta.

Revisión final: precios con separador ambiguo (`1.234`, `5.000`) solicitan aclaración sin persistir propuesta. Se admiten valores inequívocos como `5000`, `5000.00` y `5.000,00`, validados en centavos con Decimal. La confirmación conserva el código de error de dominio (por ejemplo 409 para duplicados), y la carga local limpia lotes vencidos igual que el importador original. Verificación dirigida final: **18 passed, 7 subtests passed** (15,19 s), sin red ni proveedor real.
