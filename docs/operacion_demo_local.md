# Operación de la demostración local

El 2026-11-16 el usuario confirmó que esta entrega es para demostración local. La auditoría #12 se evalúa sobre ese alcance. No se presenta la demo como un despliegue público validado.

## Inicio y datos

- Abrir `D:\Escritorio\GestorTech` en Visual Studio Code. Los cambios actuales están en `feat/tienda-catalogo-imagenes`.
- Usar Python 3.11 y las dependencias aprobadas de `requirements.txt` en el entorno virtual del proyecto.
- Servir exclusivamente en loopback: `python -m flask --app wsgi:app run --host=127.0.0.1 --port=8000`. Compose también publica únicamente `127.0.0.1:8000`.
- La página pública de entrada es la tienda; el acceso del personal conserva autenticación y roles. No existen cuentas o contraseñas por defecto.
- La imagen del producto se adjunta en el formulario local. No se transmite a Groq. Las propuestas textuales continúan sujetas a confirmación humana.

## Actualización de una base existente

Antes de ejecutar `init-db`, detener el servidor y crear un respaldo nuevo con `backup-db --output RUTA_NUEVA.sqlite3`. Esta utilidad no sobrescribe destinos. Revisar los errores del preflight: las reparaciones sin técnico válido o productos duplicados deben resolverse mediante una decisión humana, sin reasignaciones o borrado automático.

Las migraciones de esta entrega se prueban con bases ficticias. No se ejecutan sobre la base del taller durante el desarrollo ni como efecto de una visita al catálogo.

## Respaldo de la ficha completa

El respaldo SQLite contiene las referencias a las imágenes, pero no sus archivos. Con el servidor detenido, el operador debe copiar también `instance/product-images/` al mismo respaldo protegido. No publicar archivos de `instance/` ni subirlos a Git. Para restaurar, conservar el estado anterior, comprobar integridad y claves foráneas de la base copiada, recuperar su directorio de imágenes y verificar la ficha con datos ficticios antes de sustituir el entorno de demostración.

## Límite del cierre local

Los controles de autenticación, roles, objetos, CSRF, límites de intentos, importación, aprobación transaccional y carga de imágenes requieren pruebas observadas registradas en el informe de esta entrega. Las pruebas del proveedor mediante dobles explícitos no verifican comprensión semántica de Groq.

Publicar en Internet requiere otra aprobación: servidor WSGI, terminación TLS/proxy, cookie Secure, dominio, restricciones de red, política de retención/cifrado/restauración y operación supervisada. No se instalan ni conectan esos componentes al cerrar la demo local.
