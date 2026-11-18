# Manual de uso de GestorTech

Usa la [demo en PythonAnywhere](https://gestortech.pythonanywhere.com/). Para la sustentación, emplea productos y órdenes ficticias.

## Administrador

1. Abre [Acceso del personal](https://gestortech.pythonanywhere.com/login) e inicia sesión. En **Usuarios** crea un técnico activo si todavía no existe uno.
2. En **Nueva reparación**, escribe el equipo y el problema, selecciona el técnico responsable y pulsa **Crear reparación**. Entrega al cliente el código que aparece en el detalle.
3. En la orden, selecciona una transición permitida. Usa el campo de avance público para mensajes que deba ver el cliente y el campo de nota interna para información del taller.
4. En **Inventario**, busca por nombre o categoría. Al añadir un producto puedes adjuntar una imagen PNG, JPEG o WebP de hasta 2 MB y 12 megapíxeles. **Guardar en inventario** deja la ficha interna. **Guardar y publicar** la hace visible en tienda. Puedes cambiar su disponibilidad o retirarla del catálogo sin borrar el historial.
5. Registra entradas y salidas desde la fila del producto. El sistema no permite una salida que deje las existencias en negativo.
6. En **Asistente IA**, pide una ficha indicando nombre, precio y cantidad. Revisa los campos antes de confirmar o cancelar. Adjunta la imagen al completar la ficha y decide si la publicas.
7. Para importar CSV/XLSX, carga el archivo desde Inventario o Asistente IA, revisa las columnas y las filas de la previsualización, y guarda solo las que hayas seleccionado. La asistencia de IA es opcional.

## Técnico

1. Inicia sesión y abre el **Panel**. Allí aparecen las reparaciones asignadas a tu cuenta.
2. Abre una reparación asignada y guarda un cambio de estado permitido. Escribe en el campo público únicamente el avance que debe ver el cliente.
3. Si registras una nueva orden, el sistema la asigna a tu cuenta. Puedes consultar el inventario y el asistente. La publicación, la gestión de stock y la aprobación de propuestas son tareas de administración.

## Cliente

1. Abre el [catálogo público](https://gestortech.pythonanywhere.com/catalog) para buscar repuestos y consultar su disponibilidad general.
2. Abre [Consultar reparación](https://gestortech.pythonanywhere.com/track). Introduce el código que empieza por `GT-` y pulsa **Ver estado**. Verás el estado y los avances publicados, sin crear una cuenta.
3. Si el código no se encuentra, comprueba que lo copiaste completo y solicita al taller que confirme el código.

Consulta [uso responsable de IA](uso_ia.md) y [operación de la demo](entrega_funcional.md).
