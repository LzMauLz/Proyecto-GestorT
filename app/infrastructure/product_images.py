"""Decode and re-encode commercial raster uploads outside public static files."""
import io
import re
import uuid
import warnings
from pathlib import Path

from flask import current_app

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 12_000_000
MAX_DIMENSION = 6000
MAX_STORED_BYTES = 8 * 1024 * 1024
IMAGE_KEY = re.compile(r'[0-9a-f]{32}\.png\Z')


def image_directory():
    return Path(current_app.config.get('PRODUCT_IMAGE_DIRECTORY', Path(current_app.instance_path) / 'product-images'))


def image_path(image_key):
    if not isinstance(image_key, str) or not IMAGE_KEY.fullmatch(image_key):
        raise ValueError('Identificador de imagen inválido.')
    root = image_directory().resolve()
    path = root / image_key
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError('Ruta de imagen inválida.')
    return path


def prepare_image(upload):
    if upload is None or not upload.filename:
        return None
    allowed = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP'}
    extension = Path(upload.filename).suffix.lower()
    if extension not in allowed:
        raise ValueError('Carga una imagen PNG, JPEG o WebP; no se aceptan SVG ni otros formatos.')
    raw = upload.stream.read(MAX_UPLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError('La imagen debe tener contenido y pesar como máximo 2 MB.')
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:
        raise ValueError('La carga de imágenes no está disponible en este entorno. Contacta a administración.') from exc
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as original:
                width, height = original.size
                if original.format != allowed[extension] or getattr(original, 'is_animated', False):
                    raise ValueError('El contenido debe coincidir con una imagen estática del formato indicado.')
                if width * height > MAX_PIXELS or max(width, height) > MAX_DIMENSION:
                    raise ValueError('La imagen supera los límites de dimensiones permitidos.')
                original.load()
                oriented = ImageOps.exif_transpose(original)
                oriented.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                mode = 'RGBA' if 'A' in oriented.getbands() or 'transparency' in oriented.info else 'RGB'
                pixels = oriented.convert(mode)
                clean = Image.new(mode, pixels.size)
                clean.paste(pixels)
                result = io.BytesIO()
                clean.save(result, format='PNG')
                content = result.getvalue()
                if len(content) > MAX_STORED_BYTES:
                    raise ValueError('La imagen procesada es demasiado grande; usa una imagen más pequeña.')
                return content
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError('No se pudo validar la imagen. Carga un archivo raster válido.') from exc


def store_image(content):
    image_directory().mkdir(mode=0o700, parents=True, exist_ok=True)
    key = uuid.uuid4().hex + '.png'
    path = image_path(key)
    target = path.open('xb')
    try:
        with target:
            target.write(content)
    except OSError:
        # UUID filenames are exclusively reserved before writing; partial files are not served.
        if path.exists():
            path.unlink()
        raise
    return key


def discard_image(key):
    if key:
        image_path(key).unlink(missing_ok=True)
