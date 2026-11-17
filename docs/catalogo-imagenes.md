# Catálogo: imágenes y disponibilidad comercial

## Alcance

Cada producto puede tener una imagen raster local y una etiqueta comercial Disponible/No disponible. La etiqueta es independiente del stock interno: nunca expone ni modifica sus cantidades. Los productos nuevos e importados siguen sin publicarse automáticamente. La entrada anónima del sitio dirige al catálogo; el personal autenticado continúa al dashboard.

Administración puede cargar una imagen en el alta o edición del producto, cambiar su disponibilidad y publicar/despublicar mediante controles separados. El técnico no puede administrar imágenes ni disponibilidad. El asistente de IA no recibe archivos de imagen, no usa visión y no genera imágenes.

## Validación y almacenamiento

- Dependencia aprobada: Pillow 13.0.0, incorporada a requirements.txt.
- Se admiten PNG, JPEG y WebP estáticos, con extensión coherente con el formato que identifica el decodificador real.
- El archivo original debe pesar como máximo 2 MB. Se limita a 12 megapíxeles y 6.000 píxeles por lado antes de decodificar sus datos. Se rechazan SVG, animaciones, contenido corrupto o formatos disfrazados.
- Se aplica orientación EXIF, se reduce conservando proporción a un máximo de 1.920 píxeles por lado y se vuelve a codificar a PNG nuevo, sin texto, EXIF ni metadatos originales. Se conserva transparencia cuando corresponde. La salida no puede superar 8 MB.
- El archivo se guarda con un UUID nuevo en instance/product-images, fuera de static y de Git. La creación es exclusiva: jamás se reemplaza un archivo existente.
- La base de datos guarda solo image_key y available. Los formularios coordinan los datos comerciales y la referencia a imagen en una sola transacción; si falla la persistencia, se retira el archivo nuevo no vinculado.
- Al reemplazar una imagen, el archivo anterior permanece privado y sin referencia pública para preservar respaldo/reversión. No se hace limpieza automática destructiva de archivos históricos.

## Rutas y privacidad

| Ruta | Acceso | Resultado |
|---|---|---|
| GET /catalog/images/<image_key> | Público | Sirve solo la imagen de un producto publicado y activo; responde 404 si se retira o despublica |
| GET /products/<id>/image | Administrador | Vista privada de la imagen para editar productos aún no publicados |
| POST /products/<id>/image | Administrador + CSRF | Carga raster validada; no publica el producto |
| POST /products/<id>/availability | Administrador + CSRF | Cambia únicamente la disponibilidad comercial |

Las claves solo admiten 32 caracteres hexadecimales y sufijo .png. No se usan nombres de archivo del cliente para construir rutas. Se rechazan rutas manipuladas y enlaces simbólicos del archivo; las respuestas usan image/png, nosniff y Cache-Control: no-store. La consulta pública contiene id, nombre, descripción, categoría, precio, disponibilidad y clave opaca de imagen, sin existencias, costos ni movimientos.

## Migración y operación

La migración aditiva crea available con valor inicial 1 e image_key vacío. Conserva la publicación, las existencias y los demás datos existentes. Es necesario respaldar la base y la carpeta de imágenes antes de aplicar init-db sobre datos reales. No se inició ni migró la base local del taller durante este desarrollo.

Un respaldo completo debe conservar SQLite y instance/product-images juntos. La utilidad backup-db cubre SQLite; la política operativa debe incluir la carpeta de imágenes y verificar que sus claves referenciadas existen al restaurar. No publicar directamente la carpeta mediante el servidor web: la ruta Flask realiza la comprobación de publicación en cada petición.

## Pruebas

tests/test_storefront_media.py usa imágenes generadas con Pillow, SQLite temporal y cliente Flask real. Comprueba decodificación, metadatos, privacidad, permisos, CSRF, límites, unicidad de archivos, atomicidad ante duplicados y migración aditiva. No utiliza fotografías ni datos reales. Los resultados se registrarán al terminar la ejecución sobre la integración.
