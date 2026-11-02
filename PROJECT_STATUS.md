# Estado de GestorTech

**Estado:** MVP local en modernización para revisión académica. Actualizado: 2026-11-02.

## Implementado

- Estructura Flask por capas con dominio, aplicación, adaptador SQLite y controladores de página/API.
- Autenticación de personal con roles administrador/técnico y creación inicial segura de administrador mediante CLI.
- Reparaciones: asignación, código de seguimiento aleatorio, flujo de estados acordado e historial.
- Consulta pública limitada a estado y avances marcados públicos; notas internas y problema no salen en la respuesta.
- Inventario: productos, edición de catálogo, baja lógica, precios en centavos y movimientos atómicos que impiden stock negativo.
- Importación CSV/XLSX local con límites, previsualización editable y selección humana antes de guardar. Groq está preparado con puerto/adaptador, desactivado por defecto, validación de campos permitidos y fallback manual.
- API alineada con Módulo 2, OpenAPI JSON, documentación README y trazabilidad.
- Rediseño visual Gaming Premium aplicado al panel, inventario, reparaciones, formularios, importación, login y consulta pública; conserva el logo/mascota oficial local y una paleta violeta con estados operativos diferenciados.
- Dashboard con estado activo de navegación, región de tabla accesible por teclado y estilos de estado semánticos.
- Rediseño integral frontend aplicado con metodología `frontend-design`: shell lateral para personal, shell público separado, jerarquía editorial, superficies oscuras de alto contraste, acentos violeta/cian, formularios, tablas, estados, seguimiento, login e inventario coherentes en móvil y escritorio. La mascota/logo local se conserva sin reemplazo.
- Adaptador Groq continúa opt-in. Petición limitada a 50 filas y 128 KiB; salida a 256 KiB; prompts tratan campos importados como datos no confiables. Fallback manual sin reintentos.
- Asistente administrativo IA implementado con chat, consultas factuales de inventario, propuestas de producto/movimiento, confirmación/cancelación y registro de aprobación en SQLite. Técnicos quedan limitados a consultas. Groq fue probado localmente con una credencial fuera del repositorio.
- Suite `unittest`: 32 pruebas aprobadas en última ejecución; `compileall` aprobado.
- Dockerfile y Compose revisados estáticamente: usuario `10001`, filesystem raíz read-only, volumen persistente SQLite y credenciales Groq solo como variables de ejecución. No construidos ni iniciados porque Docker/Compose no están disponibles.

## Pendiente

- Pytest no está instalado en el Python activo. No se instaló ninguna dependencia ni se creó un entorno virtual.
- El usuario debe aprobar el entorno virtual y la instalación antes de instalar `requirements.txt`.
- Dockerfile/Compose recibieron revisión estática; Docker no está disponible, por lo que construcción y ejecución están pendientes.
- Groq requiere configuración local en `.env`; la credencial no está en Git. La aplicación no realiza llamadas si falta la configuración válida.
- Falta mitigación de intentos repetidos en login/seguimiento y revisión de seguridad antes de desplegar en Internet.
- El repositorio GitHub es `LzMauLz/Proyecto-GestorT`, con ramas `main` y `develop`, dos commits publicados y un único integrante. No se atribuyen revisiones o contribuciones a personas que no hayan participado.
- Validación visual local realizada en navegador integrado sobre seguimiento público y login: sin overflow a 390, 660 y 1440 px; foco inicial y navegación por teclado comprobados. No se validó dashboard autenticado con navegador para no usar datos de la base local; sus vistas siguen cubiertas por pruebas Flask.
- La auditoría actualizada está en `docs/auditoria_estado_actual.md`; el estado del repositorio Git sigue por confirmar porque el directorio inspeccionado no muestra metadatos `.git`.

## Restricciones

- No publicar ni crear remoto sin aprobación.
- No instalar paquetes, crear conexiones MCP ni enviar código/datos a proveedores externos sin aprobación.
- No usar datos reales de clientes en demostraciones.
