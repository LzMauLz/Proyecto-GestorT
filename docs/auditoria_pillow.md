# Revisión de dependencia para imágenes: Pillow 13.0.0

Revisado el 2026-11-16. El usuario aprobó explícitamente Pillow 13.0.0 para la validación y recodificación de imágenes en el entorno aislado de GestorTech y en CI.

## Fuente y alcance

- Original: https://github.com/python-pillow/Pillow, organización python-pillow.
- Versión fija propuesta: 13.0.0, publicada el 2026-10-16 según sus notas oficiales.
- Compatibilidad Python 3.11 confirmada en https://pillow.readthedocs.io/en/stable/installation/python-support.html.
- Instalación oficial: https://pillow.readthedocs.io/en/stable/installation/basic-installation.html.
- Licencia MIT-CMU y avisos de copyright: https://raw.githubusercontent.com/python-pillow/Pillow/13.0.0/LICENSE.

La revisión comprobó la procedencia, documentación, licencia y adecuación del decodificador para los formatos admitidos. No constituye una auditoría exhaustiva del código fuente ni acredita ausencia de vulnerabilidades. La popularidad no se usa como evidencia de seguridad.

## Instalación y permisos autorizados

Instalar exclusivamente un wheel publicado en PyPI, mediante `python -m pip install --only-binary=:all: --index-url https://pypi.org/simple Pillow==13.0.0`, dentro del entorno virtual del proyecto. No ejecutar un instalador de repositorio, compilar desde un script descargado ni instalar globalmente. Se añaden el paquete `PIL`, metadatos Pillow y bibliotecas de codecs incluidas en el wheel. No requiere administrador, cuentas, hooks, persistencia automática o servicios.

La descarga accede a PyPI y su infraestructura de archivos. El uso en la aplicación es local: no envía imágenes al proveedor IA. El proceso tiene únicamente el acceso a archivos de la app; el adaptador limita su uso a archivos recibidos y al directorio de imágenes del proyecto.

## Riesgos y controles del proyecto

Un decodificador procesa archivos no confiables. La aplicación debe limitar bytes y píxeles, admitir únicamente PNG/JPEG/WebP, verificar y decodificar el contenido, rechazar SVG/archivos corruptos/animaciones no admitidas y generar un archivo nuevo sin metadatos. Usar identificadores generados, no nombres o rutas del cliente. La imagen original no se publica ni se ejecuta. Una imagen de un producto no publicado no debe quedar accesible por una URL adivinada.

Los límites y tests reales del adaptador se registran en el informe de imágenes. Mantener esta dependencia actualizada y revisar avisos de seguridad antes de publicar en Internet.

## Reversión

Ejecutar `python -m pip uninstall Pillow` en el mismo entorno y retirar la dependencia al revertir esta función. No borrar imágenes del usuario ni reemplazar el entorno virtual anterior. `.venv-review/` se excluye de Git; se conserva el entorno preexistente.
