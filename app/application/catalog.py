"""Commercial catalog queries expose only explicitly published fields."""
import unicodedata

from app.domain.models import DomainError


MAX_COMPATIBILITIES = 40
MAX_COMPATIBILITY_TEXT = 8200
MAX_BRAND_LENGTH = 80
MAX_MODEL_LENGTH = 120
PRODUCT_FIELDS = 'id,name,description,category,price_cents,available,image_key'


def public_catalog(db):
    return [dict(row) for row in db.execute(
        f'SELECT {PRODUCT_FIELDS} FROM products '
        'WHERE active=1 AND published=1 ORDER BY category,name,id'
    ).fetchall()]


def public_product(db, product_id):
    if not 0 < product_id < 2**63:
        return None
    product = db.execute(
        f'SELECT {PRODUCT_FIELDS} FROM products WHERE id=? AND active=1 AND published=1',
        (product_id,),
    ).fetchone()
    return dict(product) if product else None


def compatibility_ready(db):
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='product_compatibility'"
    ).fetchone() is not None


def product_compatibilities(db, product_id):
    if not compatibility_ready(db):
        return []
    return [dict(row) for row in db.execute(
        'SELECT brand,model FROM product_compatibility WHERE product_id=? ORDER BY brand,model',
        (product_id,),
    )]


def public_compatibilities(db):
    if not compatibility_ready(db):
        return []
    return [dict(row) for row in db.execute(
        'SELECT c.product_id,c.brand,c.model FROM product_compatibility c '
        'JOIN products p ON p.id=c.product_id WHERE p.active=1 AND p.published=1 AND p.available=1 '
        'ORDER BY c.brand,c.model,c.product_id'
    )]


def catalog_text(value):
    folded = unicodedata.normalize('NFD', value.casefold())
    return ''.join(character for character in folded if not unicodedata.combining(character))


def compatibility_key(value):
    return ' '.join(catalog_text(unicodedata.normalize('NFKC', value)).split())


def save_product_compatibilities(db, product_id, raw_text):
    if not compatibility_ready(db):
        raise DomainError('La edición de compatibilidades estará disponible tras actualizar la base de datos.', 503)
    if len(raw_text) > MAX_COMPATIBILITY_TEXT:
        raise DomainError('La lista de modelos compatibles es demasiado larga.', 400)
    entries = []
    seen = set()
    for number, line in enumerate(raw_text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = [' '.join(part.split()) for part in line.split('|')]
        if len(parts) != 2 or not all(parts):
            raise DomainError(f'Escribe una marca y un modelo separados por | en la línea {number}.', 400)
        brand, model = parts
        if len(brand) > MAX_BRAND_LENGTH or len(model) > MAX_MODEL_LENGTH:
            raise DomainError(f'La marca o el modelo de la línea {number} supera la longitud permitida.', 400)
        if any(unicodedata.category(character).startswith('C') for character in brand + model):
            raise DomainError(f'Revisa los caracteres de la marca y el modelo en la línea {number}.', 400)
        key = (compatibility_key(brand), compatibility_key(model))
        if not all(key):
            raise DomainError(f'Revisa la marca y el modelo en la línea {number}.', 400)
        if key in seen:
            raise DomainError(f'El modelo de la línea {number} ya figura en la lista.', 400)
        seen.add(key)
        entries.append((product_id, brand, model))
        if len(entries) > MAX_COMPATIBILITIES:
            raise DomainError(f'Puedes indicar hasta {MAX_COMPATIBILITIES} modelos por producto.', 400)

    with db:
        db.execute('DELETE FROM product_compatibility WHERE product_id=?', (product_id,))
        if not db.execute('SELECT 1 FROM products WHERE id=? AND active=1', (product_id,)).fetchone():
            raise DomainError('Producto no disponible.', 404)
        db.executemany('INSERT INTO product_compatibility(product_id,brand,model) VALUES(?,?,?)', entries)


def filter_catalog(products, query, category, available_only):
    terms = catalog_text(query).split()
    category_key = catalog_text(category)
    matches = []
    for product in products:
        label = product['category'] or 'General'
        if category_key and catalog_text(label) != category_key:
            continue
        if available_only and not product['available']:
            continue
        if terms:
            text = catalog_text(' '.join((product['name'], label, product['description'] or '')))
            if not all(term in text for term in terms):
                continue
        matches.append(product)
    return matches


def set_publication(db, product_id, published):
    if not isinstance(published, bool):
        raise DomainError('Indica si deseas publicar o retirar el producto del catálogo.')
    with db:
        result = db.execute(
            'UPDATE products SET published=? WHERE id=? AND active=1',
            (int(published), product_id),
        )
        if result.rowcount != 1:
            raise DomainError('Producto no disponible.', 404)


def set_availability(db, product_id, available):
    if not isinstance(available, bool):
        raise DomainError('Indica si el producto está disponible para venta.')
    with db:
        result = db.execute('UPDATE products SET available=? WHERE id=? AND active=1', (int(available), product_id))
        if result.rowcount != 1:
            raise DomainError('Producto no disponible.', 404)
