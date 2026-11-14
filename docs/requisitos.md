# Requisitos – GestorTech

**Proyecto integrador – Módulo 6**  
**Sesión 1: Diagnóstico y definición de requisitos**  
**Repositorio:** [LzMauLz/Proyecto-GestorT](https://github.com/LzMauLz/Proyecto-GestorT)  
**Rama de trabajo:** `develop`

## 1. Descripción del proyecto

GestorTech es una aplicación web para apoyar la operación de pequeños talleres de servicio técnico. Centraliza la gestión de reparaciones, el inventario de productos y repuestos, y la consulta del avance de las reparaciones mediante un código de seguimiento.

El sistema está construido con Python, Flask, Jinja2, SQLite, HTML, CSS y JavaScript. Su estructura separa la presentación web, los servicios de aplicación, las reglas de dominio y la infraestructura de persistencia. La integración de IA se realiza mediante un adaptador opcional de Groq.

El proyecto ya dispone de un MVP con autenticación para administradores y técnicos, registro y seguimiento de reparaciones, inventario y movimientos de stock, importación CSV/XLSX con previsualización, y un asistente conversacional que puede preparar propuestas sujetas a aprobación. El Módulo 6 se enfocará en corregir errores encontrados, completar la experiencia del catálogo para clientes, ampliar la interacción con IA, fortalecer la seguridad y preparar la entrega integradora. No se plantea reconstruir las funciones que ya existen.

## 2. Alcance de esta entrega

### Incluido

- Corregir la creación de reparaciones que pueden quedar sin técnico asignado.
- Evitar productos duplicados en el inventario.
- Incorporar un catálogo comercial de productos y repuestos para clientes, con control administrativo de publicación.
- Ampliar el asistente para comprender instrucciones naturales y preparar productos a partir de mensajes o archivos.
- Integrar la carga de archivos CSV/XLSX en el flujo conversacional del asistente, conservando la revisión humana.
- Auditar, reforzar y probar controles de seguridad.
- Ampliar pruebas automatizadas, verificar integración continua y completar documentación y despliegue.
- Revisar la experiencia de uso de los paneles de administración, técnicos y clientes.

### Fuera del alcance obligatorio de esta semana

La integración de WhatsApp para responder consultas y recibir pedidos queda registrada como evolución futura, pero no se implementará en esta entrega. Requiere evaluar una integración oficial, credenciales, costos, privacidad y el proceso de atención de pedidos.

El carrusel automático de productos destacados se registra como mejora opcional. Solo se realizará si están terminadas las tareas Must y Should y queda tiempo disponible.

### Mejora Should: evolución de la base de datos

La aplicación utiliza SQLite actualmente. Se registra como mejora importante evaluar y preparar la migración a PostgreSQL o MySQL, comparando ambas alternativas según las necesidades reales de GestorTech y el entorno de despliegue. Esta tarea no implica cambiar el motor durante la entrega obligatoria: SQLite se mantendrá hasta que exista una decisión justificada, un plan de migración y pruebas de integridad y funcionamiento.

## 3. Historias de usuario

Cada historia incluye criterios verificables. El estado refleja el estado documentado del proyecto y el trabajo pendiente para alcanzar el alcance de esta entrega.

### HU-01: Asignar un técnico responsable a cada reparación

Como administrador del taller, quiero que cada reparación nueva quede asociada a un técnico activo, para asegurar que todas las solicitudes tengan una persona responsable.

- Dado que un administrador registra una reparación, cuando confirma el formulario, entonces debe seleccionar un técnico activo y la orden queda asignada a esa persona.
- Dado que un técnico registra una reparación, cuando la guarda, entonces queda asignada a su propio usuario; el backend no acepta una asignación distinta.
- Dado que falta la asignación o el usuario indicado no es un técnico activo, cuando se intenta guardar la reparación, entonces el sistema rechaza la operación y muestra un mensaje claro.

**Estado:** Pendiente.  
**Issue relacionada:** [#5 – Corregir bugs de reparaciones e inventario](https://github.com/LzMauLz/Proyecto-GestorT/issues/5).

### HU-02: Mantener un inventario sin productos duplicados

Como administrador del taller, quiero que GestorTech detecte productos con el mismo nombre normalizado, para evitar registros duplicados y conservar la integridad del inventario.

- Dado que existe un producto registrado, cuando se intenta crear otro con el mismo nombre ignorando mayúsculas/minúsculas y espacios innecesarios, entonces el sistema impide el duplicado.
- Dado que el administrador edita un producto, cuando conserva su propio nombre o utiliza uno que no pertenece a otro producto, entonces la actualización se permite; si coincide con otro registro, se rechaza.
- Dado que llegan dos solicitudes simultáneas para crear el mismo producto, cuando se persisten, entonces la validación de backend y base de datos evita que ambas generen duplicados.

**Estado:** Pendiente.  
**Issue relacionada:** [#5 – Corregir bugs de reparaciones e inventario](https://github.com/LzMauLz/Proyecto-GestorT/issues/5).

**Decisión por confirmar:** la propuesta inicial es que el nombre normalizado sea único globalmente. Antes de implementar debe confirmarse si se permitirá repetir el nombre cuando cambien la marca o la categoría.

### HU-03: Administrar la publicación de productos en el catálogo

Como administrador del taller, quiero decidir qué productos del inventario se publican o se retiran del catálogo, para controlar la información comercial que pueden consultar los clientes.

- Dado que un producto está registrado y tiene la información comercial requerida, cuando el administrador lo publica, entonces queda visible en el catálogo de clientes.
- Dado que un producto se despublica o se da de baja, cuando el cliente consulta el catálogo, entonces ese producto deja de mostrarse sin eliminar el historial interno del inventario.
- Dado que un producto se importa o se crea mediante IA, cuando termina el registro, entonces no se publica automáticamente; requiere una decisión explícita del administrador.

**Estado:** Pendiente.  
**Issue relacionada:** [#10 – Implementar catálogo de productos y repuestos para clientes](https://github.com/LzMauLz/Proyecto-GestorT/issues/10).

### HU-04: Consultar el catálogo de productos y repuestos

Como cliente, quiero consultar los productos y repuestos que ofrece el taller, para conocer su información comercial y disponibilidad general.

- Dado que existen productos activos y publicados, cuando el cliente abre el catálogo, entonces visualiza su nombre, descripción, categoría y precio cuando esté definido.
- Dado que un producto no está publicado, está inactivo o fue retirado, cuando el cliente consulta el catálogo, entonces no recibe información de ese producto.
- Dado que el cliente consulta el catálogo, cuando se presenta la información, entonces no se exponen cantidades exactas de inventario, costos, movimientos, proveedores ni datos administrativos.

**Estado:** Pendiente.  
**Issue relacionada:** [#10 – Implementar catálogo de productos y repuestos para clientes](https://github.com/LzMauLz/Proyecto-GestorT/issues/10).

**Decisión por confirmar:** el repositorio actual dispone de roles de administrador y técnico y de una consulta pública de seguimiento, pero no documenta cuentas autenticadas de clientes. Se debe decidir si el catálogo será una página pública sin inicio de sesión o si formará parte de un futuro panel autenticado. No se crearán cuentas de cliente sin aprobar primero ese alcance.

### HU-05: Preparar operaciones de inventario mediante instrucciones naturales

Como administrador del taller, quiero conversar con el asistente de GestorTech utilizando lenguaje natural, para preparar productos u operaciones de inventario sin completar una plantilla rígida.

- Dado que el administrador describe una necesidad con sus propias palabras, cuando el asistente procesa el mensaje, entonces identifica la intención y extrae únicamente los campos permitidos por la aplicación.
- Dado que el mensaje no contiene datos suficientes o presenta ambigüedades, cuando el asistente prepara la operación, entonces pregunta o marca los campos pendientes en lugar de inventarlos.
- Dado que el asistente prepara una propuesta, cuando la presenta, entonces el administrador puede revisarla, editarla, confirmarla o cancelarla; no se guarda ningún cambio sin confirmación.

**Estado:** Pendiente. La conversación y las propuestas básicas ya existen; falta completar y validar la comprensión flexible y los flujos requeridos para esta entrega.  
**Issue relacionada:** [#7 – Mejorar el asistente IA para trabajar con lenguaje natural y archivos de inventario](https://github.com/LzMauLz/Proyecto-GestorT/issues/7).

### HU-06: Importar inventario desde CSV/XLSX usando el asistente

Como encargado del inventario, quiero adjuntar un archivo CSV o XLSX y explicar en lenguaje natural qué datos necesito extraer, para preparar el inventario sin adaptar manualmente el archivo a una plantilla rígida.

- Dado que el usuario adjunta un CSV o XLSX válido, cuando solicita extraer campos como nombre, referencia, descripción, categoría, precio o stock, entonces el asistente identifica y organiza los valores disponibles dentro de los campos permitidos.
- Dado que el archivo contiene valores ausentes, ambiguos o inválidos, cuando se genera la previsualización, entonces esos datos quedan señalados para revisión y no se completan con valores inventados.
- Dado que el usuario revisa la previsualización, cuando confirma la importación, entonces el backend vuelve a validar los datos y persiste únicamente las filas aprobadas; si la IA falla, se conserva la alternativa manual.

**Estado:** Pendiente. El importador CSV/XLSX existe como flujo separado; falta integrarlo en la conversación del asistente.  
**Issue relacionada:** [#7 – Mejorar el asistente IA para trabajar con lenguaje natural y archivos de inventario](https://github.com/LzMauLz/Proyecto-GestorT/issues/7).

### HU-07: Consultar el avance de una reparación

Como cliente, quiero consultar el estado y los avances públicos de mi reparación mediante un código de seguimiento, para conocer el progreso del servicio sin acceder al panel interno del taller.

- Dado que el cliente tiene un código de seguimiento válido, cuando consulta la reparación, entonces el sistema muestra su estado, fechas y los avances marcados expresamente como públicos.
- Dado que el código no existe o no es válido, cuando se realiza la consulta, entonces el sistema informa que no encontró la reparación sin revelar información de otros registros.
- Dado que la reparación contiene notas internas o datos del cliente, cuando se genera la respuesta pública, entonces esos datos no se incluyen.

**Estado:** Hecha según el estado documentado del MVP.  
**Relación de verificación:** [#12 – Seguridad](https://github.com/LzMauLz/Proyecto-GestorT/issues/12) y [#15 – Pruebas automatizadas e integración continua](https://github.com/LzMauLz/Proyecto-GestorT/issues/15).

### HU-08: Restringir las operaciones según el rol del usuario

Como administrador o técnico del taller, quiero que GestorTech habilite únicamente las operaciones permitidas para mi rol, para proteger la información y evitar modificaciones no autorizadas.

- Dado que un usuario inicia sesión, cuando accede a una función protegida, entonces el backend verifica su sesión, rol y autorización sobre el recurso solicitado.
- Dado que un técnico consulta o modifica reparaciones, cuando realiza la operación, entonces solo puede acceder a las órdenes que tiene asignadas y a las funciones permitidas para su rol.
- Dado que un usuario intenta ejecutar una operación sin autorización o sin la protección CSRF requerida, cuando envía la solicitud, entonces el backend la rechaza sin modificar los datos.

**Estado:** Hecha en su base funcional según la documentación y pruebas existentes; el endurecimiento adicional y las pruebas de seguridad siguen pendientes.  
**Issues relacionadas:** [#12 – Auditar, reforzar y probar la seguridad](https://github.com/LzMauLz/Proyecto-GestorT/issues/12) y [#15 – Pruebas automatizadas e integración continua](https://github.com/LzMauLz/Proyecto-GestorT/issues/15).

## 4. Requisitos no funcionales

Los siguientes valores son objetivos propuestos para validar durante el módulo. No representan resultados de medición ya obtenidos.

| Código | Atributo | Requisito medible | Verificación prevista |
|---|---|---|---|
| RNF-01 | Rendimiento | El 95 % de las consultas de catálogo, seguimiento y operaciones habituales deberá responder en menos de 500 ms bajo una carga de prueba definida de hasta 20 solicitudes concurrentes. | Prueba de rendimiento en un entorno documentado, registrando percentiles y condiciones. |
| RNF-02 | Seguridad | El 100 % de las operaciones que modifican información deberá validar autenticación, autorización por rol y protección CSRF cuando use sesión; el repositorio no deberá contener secretos. | Pruebas de acceso, CSRF, roles y revisión del repositorio. |
| RNF-03 | Disponibilidad | La URL pública deberá responder correctamente durante toda la sustentación de 8 a 10 minutos y el endpoint de salud deberá devolver HTTP 200. | Prueba de disponibilidad antes y durante el ensayo de sustentación. |
| RNF-04 | Usabilidad | Al menos 4 de 5 usuarios de prueba deberán completar sin ayuda una tarea de consulta del catálogo o registro de producto en menos de 2 minutos. | Prueba moderada con datos ficticios y registro de tiempo y resultado. |

## 5. Cambios frente a las propuestas de IA

Se revisaron las propuestas generadas durante el análisis y se aplicaron las siguientes correcciones para mantener el alcance y la seguridad del proyecto:

1. **No completar precios ni existencias mediante suposiciones de IA.** Aunque el modelo pueda sugerir datos descriptivos, el precio y la cantidad deben proceder del archivo o de una indicación explícita del usuario. Los campos faltantes quedan pendientes de revisión.
2. **No guardar ni publicar productos automáticamente.** La IA puede preparar y organizar una propuesta, pero solo un administrador puede revisarla y confirmarla. La publicación en el catálogo es una decisión separada.
3. **No incorporar WhatsApp como requisito obligatorio del Módulo 6.** La atención conversacional y recepción de pedidos por WhatsApp se registra como evolución futura, fuera del alcance de esta semana.
4. **No incorporar un carrusel automático como requisito obligatorio.** La presentación de productos destacados queda como mejora opcional que solo se considera después de los Must y Should.

## 6. Backlog y trazabilidad con GitHub Issues

Los issues se organizaron por bloques de trabajo. Cuando varias tareas correspondían al mismo flujo, se consolidaron para evitar duplicados.

| Issue | Trabajo consolidado | Historias relacionadas | MoSCoW |
|---|---|---|---|
| [#5](https://github.com/LzMauLz/Proyecto-GestorT/issues/5) | Corregir asignación de reparaciones y evitar productos duplicados | HU-01, HU-02 | Must |
| [#7](https://github.com/LzMauLz/Proyecto-GestorT/issues/7) | Mejorar lenguaje natural, integrar CSV/XLSX al asistente y preparar propuestas de inventario | HU-05, HU-06 | Must |
| [#10](https://github.com/LzMauLz/Proyecto-GestorT/issues/10) | Crear catálogo comercial y administrar publicación de productos | HU-03, HU-04 | Must |
| [#12](https://github.com/LzMauLz/Proyecto-GestorT/issues/12) | Auditar, reforzar y probar la seguridad | HU-07, HU-08 y transversal | Must |
| [#14](https://github.com/LzMauLz/Proyecto-GestorT/issues/14) | Mejorar y validar experiencia de los paneles | HU-03, HU-04 y transversal | Should |
| [#20](https://github.com/LzMauLz/Proyecto-GestorT/issues/20) | Evaluar y migrar la persistencia desde SQLite a PostgreSQL o MySQL; comparar motores, documentar la decisión y probar la migración | HU-01 a HU-08, transversal de persistencia | Should |
| [#21](https://github.com/LzMauLz/Proyecto-GestorT/issues/21) | Crear y versionar el documento de requisitos de la Sesión 1 en `docs/requisitos.md` | HU-01 a HU-08, trazabilidad documental | Must |
| [#15](https://github.com/LzMauLz/Proyecto-GestorT/issues/15) | Ampliar pruebas automatizadas y verificar CI | HU-01 a HU-08 | Must |
| [#16](https://github.com/LzMauLz/Proyecto-GestorT/issues/16) | Completar documentación funcional, manual y entrega/despliegue | HU-01 a HU-08 | Must |
| [#17](https://github.com/LzMauLz/Proyecto-GestorT/issues/17) | Elaborar/actualizar diagramas C4 y documentar decisiones mediante ADR | HU-01 a HU-08, transversal | Must |
| [#18](https://github.com/LzMauLz/Proyecto-GestorT/issues/18) | Registrar integración futura de WhatsApp para atención y pedidos | Evolución futura; no forma parte de las HU obligatorias | Won't |
| [#19](https://github.com/LzMauLz/Proyecto-GestorT/issues/19) | Agregar sección de productos destacados con carrusel automático | Mejora opcional relacionada con HU-04 | Could |

### Criterio de priorización MoSCoW

- **Must:** indispensable para completar los entregables y la sustentación.
- **Should:** importante, pero puede presentarse el proyecto sin completarlo.
- **Could:** mejora deseable si queda tiempo después de terminar Must y Should.
- **Won't:** se registra, pero queda fuera del alcance de esta entrega.

## 7. Decisiones funcionales pendientes de confirmación

Antes de implementar los cambios relacionados, deben quedar acordadas estas decisiones:

- **Catálogo del cliente:** determinar si será público sin inicio de sesión o si se integrará en un panel autenticado. El repositorio actual no contiene un rol de cliente.
- **Unicidad de productos:** confirmar si el nombre normalizado será único globalmente o si se permitirá repetirlo al cambiar marca/categoría.
- **Disponibilidad en catálogo:** definir si se mostrará una indicación general de disponibilidad. No se recomienda exponer existencias exactas.
- **Campos obligatorios de inventario:** confirmar qué datos deben ser obligatorios para registrar un producto y cómo se manejarán valores ausentes.
- **Integración IA:** mantener Groq opcional, la alternativa manual y la aprobación explícita antes de persistir cambios.
- **Motor de base de datos:** comparar PostgreSQL y MySQL considerando compatibilidad, concurrencia, transacciones, despliegue, mantenimiento, respaldos y costos. Registrar la opción seleccionada en un ADR. La migración deberá conservar los datos y restricciones, contar con respaldo y reversión, y superar pruebas antes de retirar SQLite.

## 8. Referencias internas del proyecto

- [Estado actual del proyecto](../PROJECT_STATUS.md).
- [README](../README.md).
- [Decisiones de implementación del MVP](decisiones_mvp.md).
- [Auditoría del estado actual](auditoria_estado_actual.md).
- [Documentación de API](api.md).
- [Uso responsable de IA](uso_ia.md).
- [Backlog de GitHub](https://github.com/LzMauLz/Proyecto-GestorT/issues).
