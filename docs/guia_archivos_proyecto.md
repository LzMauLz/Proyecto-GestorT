# Guía sencilla de GestorTech

## ¿Qué es GestorTech?

GestorTech es una aplicación web para administrar reparaciones e inventario
de un taller. Está construida con Flask, Jinja2, SQLite, HTML, CSS y
JavaScript.

El sistema tiene cuatro partes principales:

1. **Web:** recibe solicitudes del navegador y muestra las páginas.
2. **Aplicación:** coordina las operaciones del negocio.
3. **Dominio:** contiene reglas como estados y validaciones.
4. **Infraestructura:** conecta con SQLite y Groq.

## Cómo iniciar el proyecto

Desde PowerShell:

```powershell
cd D:\Escritorio\GestorTech
.\.venv\Scripts\python.exe -m flask --app wsgi:app run --host 127.0.0.1 --port 5055
```

Después se abre `http://127.0.0.1:5055`.

La configuración local se encuentra en `.env`. Ese archivo no debe subirse a
Git porque puede contener la clave de Groq y la clave secreta de Flask.

## Archivos principales

| Archivo | Explicación corta |
|---|---|
| `.env` | Configuración local y secretos. No compartir ni subir a Git. |
| `.env.example` | Plantilla sin secretos para saber qué variables existen. |
| `.gitignore` | Indica qué archivos privados o temporales no deben controlarse con Git. |
| `README.md` | Manual general de instalación, ejecución y seguridad. |
| `PROJECT_STATUS.md` | Estado actual, funcionalidades, pendientes y limitaciones. |
| `AGENTS.md` | Instrucciones de trabajo y criterios del proyecto. |
| `requirements.txt` | Dependencias Python del proyecto. |
| `docker-compose.yml` | Configuración para ejecutar la aplicación con Docker. |
| `.dockerignore` | Archivos que Docker no debe copiar a la imagen. |

## Configuración

| Archivo | Explicación corta |
|---|---|
| `config/settings.py` | Lee `.env` y las variables de entorno. Define la clave Flask, Groq, timeout y base de datos. |
| `config/__init__.py` | Marca `config` como paquete Python. |

## Entrada de la aplicación

| Archivo | Explicación corta |
|---|---|
| `wsgi.py` | Crea la instancia Flask que usa el comando `flask --app wsgi:app`. |
| `app/__init__.py` | Construye la aplicación, registra rutas, conecta SQLite, configura Groq y errores HTTP. |

## Dominio: reglas del negocio

| Archivo | Explicación corta |
|---|---|
| `app/domain/models.py` | Define estados, errores y reglas básicas de reparaciones e inventario. |
| `app/domain/__init__.py` | Marca el dominio como paquete Python. |

## Aplicación: operaciones y casos de uso

| Archivo | Explicación corta |
|---|---|
| `app/application/services.py` | Crea reparaciones y productos, cambia estados y registra movimientos de stock. |
| `app/application/ports.py` | Define errores y contratos que pueden usar los adaptadores externos. |
| `app/application/ai_import.py` | Prepara sugerencias de IA para importar productos y valida las respuestas. |
| `app/application/ai_assistant.py` | Coordina el chat IA, las consultas de inventario, las propuestas y la confirmación humana. |
| `app/application/__init__.py` | Marca la capa de aplicación como paquete Python. |

## Web: autenticación, páginas y API

| Archivo | Explicación corta |
|---|---|
| `app/web/auth.py` | Inicio y cierre de sesión, usuarios, roles y protección CSRF. |
| `app/web/pages.py` | Rutas que muestran dashboard, reparaciones, inventario, importación y asistente. |
| `app/web/api.py` | Endpoints JSON para productos, reparaciones, movimientos, seguimiento y asistente IA. |
| `app/web/__init__.py` | Marca la capa web como paquete Python. |

## Infraestructura: datos y proveedores

| Archivo | Explicación corta |
|---|---|
| `app/infrastructure/database.py` | Abre conexiones SQLite, activa claves foráneas y administra transacciones. |
| `app/infrastructure/schema.sql` | Crea tablas de usuarios, reparaciones, productos, movimientos, importaciones y auditoría IA. |
| `app/infrastructure/ai/groq_adapter.py` | Envía solicitudes JSON a Groq, aplica timeout, límites, User-Agent y maneja errores. |
| `app/infrastructure/ai/__init__.py` | Marca los adaptadores de IA como paquete Python. |
| `app/infrastructure/__init__.py` | Marca infraestructura como paquete Python. |

## Plantillas HTML

Todas están en `app/templates` y usan Jinja2.

| Archivo | Explicación corta |
|---|---|
| `base.html` | Plantilla común: logo, menú, navegación, mensajes y pie de página. |
| `login.html` | Formulario de acceso del personal. |
| `dashboard.html` | Panel principal con resumen operativo. |
| `assistant.html` | Chat administrativo con Groq y revisión de propuestas. |
| `products.html` | Lista de productos e inventario. |
| `product_form.html` | Alta de producto. |
| `product_edit.html` | Edición de datos de un producto. |
| `import.html` | Carga de archivos CSV/XLSX. |
| `import_preview.html` | Previsualización y aprobación manual de importaciones. |
| `repair_form.html` | Creación de una reparación. |
| `repair_detail.html` | Detalle, estado, técnico e historial de una reparación. |
| `user_form.html` | Creación de usuarios administrativos o técnicos. |
| `track.html` | Consulta pública de seguimiento por código. |

## Archivos visuales y del navegador

| Archivo | Explicación corta |
|---|---|
| `app/static/css/app.css` | Sistema visual principal: layout, tarjetas, tablas, formularios, responsive y accesibilidad. |
| `app/static/css/gestortech-theme.css` | Ajustes específicos de identidad GestorTech. |
| `app/static/js/app.js` | Interacciones del chat, envío con Enter, confirmaciones y renderizado seguro. |
| `app/static/images/gestortech-mascot.png` | Logo y mascota oficial. No reemplazar ni deformar. |

## Base de datos local

| Ruta | Explicación corta |
|---|---|
| `instance/gestortech.sqlite3` | Base SQLite local con usuarios, reparaciones, productos y movimientos. |
| `instance/` | Carpeta privada de datos locales; no se sube a Git. |

No se debe eliminar `gestortech.sqlite3` si se desean conservar los datos.
`init-db` se utiliza para preparar la estructura, no para iniciar la aplicación
cada vez.

## Pruebas

| Archivo | Explicación corta |
|---|---|
| `tests/test_app.py` | Pruebas de autenticación, permisos, reparaciones, inventario, importaciones y asistente IA. |

Ejecutar:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La última ejecución registrada pasó **30 pruebas**.

## Documentación adicional

| Archivo | Explicación corta |
|---|---|
| `docs/api.md` | Rutas API, permisos, solicitudes y respuestas. |
| `docs/uso_ia.md` | Uso responsable, límites y aprobación humana de IA. |
| `docs/auditoria_estado_actual.md` | Auditoría técnica y riesgos conocidos. |
| `docs/decisiones_mvp.md` | Decisiones confirmadas del MVP. |
| `docs/trazabilidad_m3.md` | Relación entre requisitos, implementación y pruebas. |
| `docs/Modulo 2  Arquitectura y Diseño de Aplicaciones con IA.pdf` | Documento académico de referencia. |

## Diagramas

Los archivos de `diagrams/` explican el sistema visualmente:

- `Diagrama de contexto.drawio`: actores y sistema.
- `Diagrama de componentes.drawio`: módulos principales.
- `Diagrama de flujo.drawio`: procesos.
- `Modelo de datos.drawio`: tablas y relaciones.

## Flujo sencillo de una pregunta al asistente

1. El usuario escribe en `assistant.html`.
2. `app.js` envía el mensaje a `/api/asistente/mensaje`.
3. `api.py` verifica sesión, rol y CSRF.
4. `ai_assistant.py` consulta datos reales de SQLite y prepara el contexto.
5. `groq_adapter.py` consulta Groq cuando está activado.
6. La respuesta se valida localmente.
7. Las modificaciones quedan como propuesta pendiente.
8. Solo un administrador puede confirmar y ejecutar la operación.

La IA nunca modifica SQLite directamente ni puede aprobar una operación por sí
sola.
