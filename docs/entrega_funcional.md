# Entrega funcional y operativa

## Verificación de la demo

| Flujo | Evidencia observada |
|---|---|
| Disponibilidad | La URL pública abrió por HTTPS. `/health` devolvió `{"status":"ok"}`. |
| Personal y reparación | Se abrió el panel con una cuenta administradora. Se registró una orden ficticia asignada a un técnico activo. La consulta pública por código mostró «Recibido» y el avance autorizado. La nota interna quedó fuera. |
| Catálogo e imágenes | Se publicó una ficha ficticia con imagen. La imagen cargó en el catálogo y en destacados, y la ficha mostró «No disponible». |
| IA desde el panel | Groq respondió al chat, generó una ficha ficticia y esta se canceló sin modificar existencias. Tras corregir el adaptador, el formulario volvió a generar una descripción editable. |
| Importación y aprobación | Con Groq real y una base temporal, se probaron dos descripciones y dos filas CSV sin descripción. Ambas filas recibieron sugerencias sin guardarse automáticamente. La aprobación de una propuesta ficticia se comprobó por separado en una base temporal. |
| Regresión | En una copia aislada del código desplegado con el parche pasaron 161 pruebas Pytest y 77 subpruebas. Cubren roles, inventario, imágenes, catálogo, reparaciones y seguimiento. |

La corrección de redacción quedó registrada en [`3b76032`](https://github.com/LzMauLz/Proyecto-GestorT/commit/3b76032e14c9b047764920c818538839c2a2063e). El [historial de CI](https://github.com/LzMauLz/Proyecto-GestorT/actions/workflows/ci.yml) y las [evidencias de la sesión 3](evidencias.md) documentan verificaciones adicionales.

## Operación y seguridad

- El sitio usa [PythonAnywhere](despliegue_pythonanywhere.md) con WSGI, HTTPS y persistencia SQLite. Docker es una opción local.
- Antes de la sustentación, revisa la fecha de vencimiento en **Web**, confirma la renovación y comprueba el sitio y `/health`. Verifica el acceso al panel y los flujos con datos ficticios.
- Respalda SQLite y las imágenes conjuntamente mediante el procedimiento del despliegue. Conserva el material fuera del repositorio y verifica la restauración en un entorno separado antes de depender del respaldo.
- Sesión, roles, CSRF, transiciones y límites de intentos protegen las operaciones descritas en [la revisión de seguridad](issues/12-seguridad.md). Las cuentas y claves se configuran fuera del repositorio. No se incluyen datos reales, claves ni códigos de seguimiento en este documento.
- Este despliegue cubre la demo académica. La verificación pública no sustituye pruebas de carga, un ensayo de recuperación de respaldos ni la validación formal de seguridad de producción. Los objetivos de duración y usabilidad de los [requisitos](requisitos.md) siguen pendientes de medición.

## Guion breve de sustentación

1. Abre el catálogo público y muestra una ficha ficticia con imagen y disponibilidad.
2. Entra como administrador, registra una orden ficticia asignada a un técnico y consulta el código en la vista pública.
3. Pide una propuesta ficticia a Groq y muestra la revisión antes de cancelarla. Si el proveedor falla, muestra la carga manual con previsualización.
4. Muestra la [arquitectura](arquitectura.md), [pruebas y evidencias](evidencias.md), [manual](manual-usuario.md) y [límites de IA](uso_ia.md).
