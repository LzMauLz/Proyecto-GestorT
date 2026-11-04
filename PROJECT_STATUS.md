# Estado de GestorTech

**Estado:** MVP local en modernización para revisión académica. Actualizado: 2026-11-03.

## Implementado

- Estructura Flask por capas con dominio, aplicación, adaptador SQLite y controladores de página/API.
- Autenticación de personal con roles administrador/técnico y creación inicial segura de administrador mediante CLI.
- Reparaciones: asignación, código de seguimiento aleatorio, flujo de estados acordado e historial.
- Consulta pública limitada a estado y avances marcados públicos; notas internas y problema no salen en la respuesta.
- Inventario: productos, edición de catálogo, baja lógica, precios en centavos y movimientos atómicos que impiden stock negativo.
- Importación CSV/XLSX local con límites, previsualización editable y selección humana antes de guardar. Groq está integrado mediante puerto/adaptador, con validación de campos permitidos y fallback manual.
- API alineada con Módulo 2, OpenAPI JSON, documentación README y trazabilidad.
- Rediseño visual Gaming Premium aplicado al panel, inventario, reparaciones, formularios, importación, login y consulta pública; conserva el logo/mascota oficial local y una paleta violeta con estados operativos diferenciados.
- Dashboard con estado activo de navegación, región de tabla accesible por teclado y estilos de estado semánticos.
- Rediseño integral frontend aplicado con metodología `frontend-design`: shell lateral para personal, shell público separado, jerarquía editorial, superficies oscuras de alto contraste, acentos violeta/cian, formularios, tablas, estados, seguimiento, login e inventario coherentes en móvil y escritorio. La mascota/logo local se conserva sin reemplazo.
- Adaptador Groq opt-in mediante `.env`. Las peticiones están limitadas a 50 filas y 128 KiB; las respuestas a 256 KiB; los prompts tratan campos importados como datos no confiables y existe fallback manual sin reintentos.
- Asistente administrativo IA implementado con chat, consultas factuales de inventario, propuestas de producto/movimiento, confirmación/cancelación y registro de aprobación en SQLite. Técnicos quedan limitados a consultas. Groq fue probado localmente con una credencial fuera del repositorio.
- El chat del asistente acepta propuestas de un producto o de hasta 20 productos por solicitud; la confirmación administrativa crea el lote de forma atómica.
- Suite `unittest`: 32 pruebas aprobadas en última ejecución; `compileall` aprobado.
- Dockerfile y Compose verificados: usuario `10001`, filesystem raíz read-only, volumen persistente SQLite y credenciales Groq solo como variables de ejecución. La imagen se construyó, el contenedor inició, `http://127.0.0.1:8000` respondió `HTTP 200` y una marca SQLite sobrevivió al reinicio del contenedor.
- Repositorio GitHub publicado en `LzMauLz/Proyecto-GestorT`, con ramas `main` y `develop`, commits descriptivos y Pull Request #1 fusionado.

## Pendiente

- La validación principal se ejecutó con `unittest`; Pytest está declarado en `requirements.txt`, pero no se utilizó para el resultado registrado.
- Dockerfile/Compose: build, arranque, puerto, creación del volumen y persistencia SQLite tras reinicio verificados. No queda pendiente operativo de Docker para el MVP.
- Groq está configurado y habilitado en el `.env` local (`GROQ_ENABLED=true`, modelo `openai/gpt-oss-20b`, timeout de 12 segundos). La API key está presente y fue validada con una solicitud real; permanece fuera de Git.
- Falta mitigación de intentos repetidos en login/seguimiento y revisión de seguridad antes de desplegar en Internet.
- Validación visual local realizada en navegador integrado sobre seguimiento público y login: sin overflow a 390, 660 y 1440 px; foco inicial y navegación por teclado comprobados. No se validó dashboard autenticado con navegador.
- La demostración académica en video y el PDF final de entrega aún deben prepararse.
- La auditoría actualizada está en `docs/auditoria_estado_actual.md`.

## Restricciones

- No publicar cambios adicionales ni crear remotos sin aprobación.
- No instalar paquetes, crear conexiones MCP ni enviar código/datos a proveedores externos sin aprobación.
- No usar datos reales de clientes en demostraciones.
