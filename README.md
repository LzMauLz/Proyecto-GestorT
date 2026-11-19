# GestorTech

MVP académico para pequeños talleres de reparación. El personal registra órdenes, controla el inventario y decide qué repuestos se muestran en el catálogo. Los clientes pueden consultar el catálogo y el estado de su reparación por código.

[Demo en PythonAnywhere](https://gestortech.pythonanywhere.com/) · [Consulta de reparación](https://gestortech.pythonanywhere.com/track) · [Acceso del personal](https://gestortech.pythonanywhere.com/login)

[![CI](https://github.com/LzMauLz/Proyecto-GestorT/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/LzMauLz/Proyecto-GestorT/actions/workflows/ci.yml)

## Alcance

- **Implementado:** acceso por roles, reparaciones asignadas con historial, seguimiento público, inventario y movimientos, catálogo con imágenes y disponibilidad, importación CSV/XLSX con revisión y asistente de inventario con Groq opcional.
- **Alcance parcial:** el asistente interpreta consultas y propone cambios dentro de los flujos documentados. Los archivos se procesan por columnas reconocidas y filtros de la interfaz. Las sugerencias requieren revisión humana.
- **Fuera del MVP o pendiente:** WhatsApp, migración a otro motor de base de datos y validación de carga, usabilidad y operación para producción. La URL pública corresponde a la demo académica.

## Instalación local

Tecnologías principales: Python 3.11, Flask, Jinja2, SQLite, HTML, CSS y JavaScript. En PowerShell, desde la raíz del repositorio:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:GESTORTECH_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python -m flask --app wsgi:app init-db
python -m flask --app wsgi:app auth create-admin
python -m flask --app wsgi:app run
```

Abre [el sitio local](http://127.0.0.1:5000/). Crea al menos un técnico activo desde **Usuarios** para asignar reparaciones. Protege la clave de sesión y utiliza una base separada para las pruebas. Los nombres de las variables de entorno están en [`.env.example`](.env.example). Groq viene desactivado y se puede habilitar siguiendo la [guía de IA](docs/uso_ia.md).

### Docker local

Con Docker Compose, define `GESTORTECH_SECRET_KEY` como en el ejemplo anterior y ejecuta:

```powershell
docker compose up --build
docker compose exec gestortech python -m flask --app wsgi:app auth create-admin
```

Abre [la instancia de Docker](http://127.0.0.1:8000/). El volumen conserva SQLite y las imágenes. Para activar IA en Docker se usan `DOCKER_GROQ_ENABLED`, `DOCKER_GROQ_MODEL` y `DOCKER_GROQ_API_KEY` en el entorno de ejecución.

## Pruebas y despliegue

```powershell
python -m pytest -q
```

La suite usa datos ficticios y bases SQLite temporales. Las pruebas reales del proveedor se ejecutan por separado. Consulta [validación y operación de la demo](docs/entrega_funcional.md), [evidencias de CI](docs/evidencias.md) y [configuración en PythonAnywhere](docs/despliegue_pythonanywhere.md). El estado básico de la demo se comprueba en [`/health`](https://gestortech.pythonanywhere.com/health).

## Documentación

- [Requisitos y trazabilidad](docs/requisitos.md) y [decisiones del MVP](docs/decisiones_mvp.md).
- [Arquitectura, diagramas C4 y ADR](docs/arquitectura.md).
- [Manual de administrador, técnico y cliente](docs/manual-usuario.md).
- [Capacidades, privacidad y límites de IA](docs/uso_ia.md).
- [API](docs/api.md) y [OpenAPI JSON](https://gestortech.pythonanywhere.com/api/openapi.json).
- [Estado del proyecto](PROJECT_STATUS.md).

`develop` es la rama de integración y `main` la rama base. Los datos de instancia, el entorno virtual y las credenciales se mantienen fuera de Git.
