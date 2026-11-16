# Issue 12 · Controles de seguridad del MVP

Estado final de verificación del código integrado: **131 pruebas y 77 subtests aprobados** localmente; CI Python 3.11 [43777915059](https://github.com/LzMauLz/Proyecto-GestorT/actions/runs/43777915059) aprobado en `0b4f44a`. `tests/test_security.py` contiene 20 tests. Los recuentos inferiores registrados más abajo corresponden a fases anteriores. La auditoría cubre el MVP local y no aprueba su exposición a Internet.

Fecha: 2026-11-15. Alcance: código y pruebas locales con Flask y SQLite reales sobre datos ficticios. La configuración y las bases de datos del taller no se leen ni migran durante estas verificaciones.

## Controles incorporados

| Hallazgo | Severidad | Evidencia y mitigación | Prueba |
|---|---|---|---|
| Login y seguimiento sin límites de solicitudes | Alta para exposición pública | Contador SQLite compartido entre procesos; 5 intentos de login y 30 consultas de seguimiento por dirección IP en 60 segundos. UI y API comparten presupuesto de seguimiento; el cliente no puede sustituir la identidad mediante X-Forwarded-For. | Persistencia entre apps, 429/Retry-After, vencimiento e independencia de clientes |
| Confirmación simultánea de una propuesta | Alta | BEGIN IMMEDIATE antes de leer pending; escritura de inventario, estado y auditoría en la misma transacción | Dos conexiones simultáneas: una aprobación y un rechazo |
| Commit de stock anterior al registro de aprobación | Alta | move_stock permite operación bajo transacción del llamador; rollback integral si falla la auditoría | Trigger SQLite que fuerza fallo de auditoría; inventario y propuesta sin cambios |
| Auditoría vinculada a la última operación | Media | ai_operations.proposal_id identifica la propuesta exacta. Migración aditiva; no se inventan asociaciones históricas | Resolución fuera de orden y migración idempotente |
| Error externo expuesto en logs/respuesta | Media | Mensajes genéricos en el límite del proveedor y API; sin cuerpo externo ni trazas en logs propios | Fallo de proveedor inyectado con marcador ficticio |
| CSRF Unicode y historial de tipo incorrecto | Media | Rechazo controlado antes de compare_digest o del procesamiento del historial | Respuestas 400/errores de aplicación; ninguna escritura |
| Libro con macros renombrado, fórmulas o vínculos externos | Media | Inspección del contenedor, rechazo de contenido activo y lectura acotada; cierre garantizado del workbook | Libro XLSX con fórmula real, paquete VBA sintético, ZIP corrupto y límites |
| Salida de texto controlado por usuario | Media | Jinja conserva escape; errores web se sirven como text/plain | Payload HTML sintético no aparece como etiqueta ejecutable |

El limitador almacena una clave HMAC, no direcciones IP ni correos en claro. Usa el secreto de sesión configurado por el operador. Las cuotas son límites de solicitudes, incluidos intentos inválidos; una red compartida consume un presupuesto compartido. Las constantes están en Config. Cambiar el secreto reinicia de hecho las identidades de presupuesto. Los registros vencidos se eliminan al procesar nuevas solicitudes.

La aplicación no confía en cabeceras de proxy. Antes de instalar un proxy inverso debe definirse explícitamente qué saltos son de confianza: de lo contrario los clientes compartirán la IP del proxy. No se configura ProxyFix automáticamente.

## Sesiones y permisos

Se conservan contraseña hasheada, rotación de sesión y CSRF al login, borrado de sesión al logout, roles y validación del propietario de una propuesta. Los técnicos no pueden confirmar ni cancelar propuestas en el servicio, aunque invoquen la función sin pasar por la ruta.

Flask 3.1.3 verifica la edad de la firma de sesión usando PERMANENT_SESSION_LIFETIME también al leer cookies no permanentes. No se cambió esta política. Se prueba su rechazo con una ventana artificialmente vencida en una app sintética, junto con HttpOnly, SameSite y Secure bajo configuración HTTPS.

## Verificación

Archivo: tests/test_security.py. Las pruebas de rutas usan el cliente real de Flask y una base SQLite temporal. La prueba concurrente usa dos conexiones y dos hilos reales. Las pruebas de rollback inducen un error SQLite con un trigger dentro de una base ficticia.

Los ensayos de respuesta maliciosa y error de proveedor usan dobles explícitos como verificación complementaria del límite de confianza. No son pruebas de Groq real ni demuestran que un modelo siempre resista prompt injection. No se realizan solicitudes externas.

Resultado observado: **57 passed, 44 subtests passed en 48,39 s** para la suite completa, incluidos los primeros 16 tests nuevos de seguridad. Tras añadir el rechazo de una respuesta `answer` con propuesta oculta, su prueba adversaria y la confirmación legítima existente pasaron: **2 passed en 2,74 s**. El archivo de seguridad contiene ahora 17 tests. Se ejecutó sin caché de pytest y con escritura de bytecode desactivada.

La validación local se ejecutó complementariamente con Python 3.12.14 empaquetado y los paquetes ya instalados del proyecto. El Python 3.11 base del entorno virtual local no está disponible. CI con Python 3.11 sigue siendo obligatorio antes de considerar concluida la validación del stack acordado.

Verificación posterior de entrada de reparaciones y respaldo/restauración: **20 passed, 14 subtests passed en 22,73 s** para `tests/test_security.py`. Incluye rechazo de valores JSON no textuales en equipo/problema y snapshot/restauración SQLite reales sobre datos ficticios. La utilidad de backup y el CLI no se ejecutaron sobre la base del taller.

## Pendientes antes de exposición a Internet

- HTTPS: elegir terminación TLS y proxy; comprobar renovación, redirección HTTPS y cookie Secure. Compose actual sirve únicamente HTTP local y no es evidencia de TLS.
- Servidor WSGI: el contenedor sigue usando el servidor de desarrollo Flask. Seleccionar, auditar y aprobar un servidor de producción antes de instalarlo.
- Backups operativos: definir destino, acceso, retención y cifrado antes de operar con datos del taller. La utilidad y restauración sobre una base ficticia se prueban localmente; esto no configura una política de respaldos de producción.
- Dependencias: no se realizó consulta remota de vulnerabilidades ni escaneo del historial de secretos. La ausencia de archivos sensibles rastreados no demuestra ausencia de secretos históricos.
- Datos existentes: aplicar la migración aditiva únicamente con respaldo y aprobación del operador. Los registros históricos sin proposal_id se conservan; su resolución posterior genera una nueva fila explícitamente ligada, sin alterar el registro antiguo.

Estos pendientes no están aceptados como riesgos ni autorizan un despliegue público. El cierre de la auditoría de producción requiere decisión humana y evidencia de esas verificaciones.

## Respaldo y restauración controlados

La utilidad `backup_database` utiliza la API de snapshot de SQLite para conservar consistencia incluso con WAL. Abre el origen en modo lectura, reserva el destino mediante creación exclusiva, verifica integridad y nunca reemplaza un destino existente ni la base de origen. Ante un fallo retira únicamente la copia recién creada.

El operador puede ejecutar `python -m flask --app wsgi:app backup-db --output RUTA_NUEVA.sqlite3`. El destino es explícito; su carpeta debe existir y tener permisos restringidos. No enviar el respaldo a Git. Para restaurar, detener primero los procesos de la aplicación, conservar la base vigente, validar la copia con `PRAGMA integrity_check` y `PRAGMA foreign_key_check`, y arrancar con `GESTORTECH_DATABASE` apuntando a la copia validada. La reversión consiste en volver a la ruta anterior conservada; no sobrescribir ni borrar el origen.

Las pruebas de respaldo/restauración crean un producto sintético, obtienen snapshot, arrancan otra aplicación Flask sobre esa copia y comprueban integridad, relaciones y aislamiento respecto a escrituras posteriores del origen. El CLI también se prueba con destino nuevo y rechazo de destino existente.
