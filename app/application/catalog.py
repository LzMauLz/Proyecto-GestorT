"""Commercial catalog queries expose only explicitly published fields."""
from app.domain.models import DomainError


def public_catalog(db):
    return [dict(row) for row in db.execute(
        'SELECT id,name,description,category,price_cents,available,image_key FROM products '
        'WHERE active=1 AND published=1 ORDER BY category,name,id'
    ).fetchall()]


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
