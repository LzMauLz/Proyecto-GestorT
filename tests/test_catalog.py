import io
import json
from urllib.parse import parse_qs, urlsplit

import pytest

from app import create_app
from app.application.catalog import public_catalog
from app.application.services import create_product
from app.application.ai_assistant import resolve_proposal
from app.infrastructure.database import get_db, init_db


@pytest.fixture
def catalog_app(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'catalog-test-only',
                      'DATABASE': str(tmp_path / 'catalog.sqlite3'),
                      'GROQ_ENABLED': False, 'GROQ_API_KEY': '', 'GROQ_MODEL': ''})
    with app.app_context():
        init_db()
        db = get_db()
        for role, name in [('admin', 'Admin ficticio'), ('technician', 'Técnico ficticio')]:
            db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                       (name, role + '@example.test', 'unused-test-hash', role, '2026-01-01'))
        db.commit()
    return app


def staff(client, user_id):
    with client.session_transaction() as session:
        session['user_id'] = user_id
        session['_csrf_token'] = 'catalog-csrf'
    return {'X-CSRF-Token': 'catalog-csrf'}


def product(app):
    with app.app_context():
        return create_product(get_db(), {'name': 'Pantalla ficticia', 'description': '<script>alert(1)</script>',
                                        'category': 'Repuestos', 'price': '12500.50', 'stock': 987654, 'user_id': 1})


def test_publication_requires_admin_and_csrf(catalog_app):
    client = catalog_app.test_client()
    product_id = product(catalog_app)
    url = f'/products/{product_id}/publication'
    assert client.post(url, data={'published': '1'}).status_code == 400
    headers = staff(client, 2)
    assert client.post(url, data={'published': '1'}, headers=headers).status_code == 403
    headers = staff(client, 1)
    assert client.post(url, data={'published': '1'}).status_code == 400
    assert client.post(url, data={'published': 'garbage'}, headers=headers).status_code == 400
    assert client.post('/products/9999/publication', data={'published': '1'}, headers=headers).status_code == 404
    with catalog_app.app_context():
        assert get_db().execute('SELECT published FROM products').fetchone()['published'] == 0


def test_catalog_exposes_only_approved_commercial_fields(catalog_app):
    product_id = product(catalog_app)
    public = catalog_app.test_client()
    assert 'Pantalla ficticia' not in public.get('/catalog').get_data(as_text=True)
    admin = catalog_app.test_client()
    headers = staff(admin, 1)
    assert admin.post(f'/products/{product_id}/publication', data={'published': '1'}, headers=headers).status_code == 302
    response = public.get('/catalog')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'Pantalla ficticia' in html and '12.500,50' in html
    assert '987654' not in html and 'Admin ficticio' not in html
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    with catalog_app.app_context():
        assert set(public_catalog(get_db())[0]) == {'id', 'name', 'description', 'category', 'price_cents', 'available', 'image_key'}


def test_unpublish_and_retirement_hide_without_deleting_history(catalog_app):
    product_id = product(catalog_app)
    admin = catalog_app.test_client()
    headers = staff(admin, 1)
    url = f'/products/{product_id}/publication'
    admin.post(url, data={'published': '1'}, headers=headers)
    admin.post(url, data={'published': '0'}, headers=headers)
    with catalog_app.app_context():
        assert public_catalog(get_db()) == []
    admin.post(url, data={'published': '1'}, headers=headers)
    assert admin.post(f'/products/{product_id}/retire', headers=headers).status_code == 302
    with catalog_app.app_context():
        db = get_db()
        assert public_catalog(db) == []
        assert db.execute('SELECT COUNT(*) FROM inventory_movements').fetchone()[0] == 1
    assert admin.post(url, data={'published': '1'}, headers=headers).status_code == 404


def test_catalog_migration_leaves_legacy_products_unpublished(catalog_app):
    with catalog_app.app_context():
        db = get_db()
        db.execute('ALTER TABLE products DROP COLUMN published')
        db.commit()
        product_id = create_product(db, {'name': 'Migrado', 'price': '0', 'stock': 0, 'user_id': 1})
        init_db()
        init_db()
        assert db.execute('SELECT published FROM products WHERE id=?', (product_id,)).fetchone()[0] == 0


def test_catalog_database_failure_has_safe_retry_view(catalog_app):
    with catalog_app.app_context():
        get_db().execute('DROP TABLE products')
        get_db().commit()
    response = catalog_app.test_client().get('/catalog')
    assert response.status_code == 503
    html = response.get_data(as_text=True)
    assert 'Volver a intentar' in html
    assert 'no such table' not in html
    assert response.headers['Cache-Control'] == 'no-store'


def test_import_approved_product_is_not_automatically_public(catalog_app):
    client = catalog_app.test_client()
    headers = staff(client, 1)
    response = client.post('/products/import/preview', headers=headers,
                           data={'file': (io.BytesIO(b'nombre,precio,stock\nImportado,100,2\n'), 'productos.csv')})
    assert response.status_code == 200
    with catalog_app.app_context():
        batch = get_db().execute('SELECT id FROM import_batches').fetchone()[0]
    assert client.post(f'/products/import/{batch}/approve', headers=headers, data={'row': '0'}).status_code == 302
    with catalog_app.app_context():
        assert get_db().execute('SELECT published FROM products').fetchone()[0] == 0
        assert public_catalog(get_db()) == []


def test_ai_approved_product_is_not_automatically_public(catalog_app):
    with catalog_app.app_context():
        db = get_db()
        payload = json.dumps({'name': 'Propuesta ficticia', 'price': '100', 'stock': 2})
        db.execute('INSERT INTO ai_proposals(id,user_id,operation,payload_json,status,created_at) VALUES(?,?,?,?,?,?)',
                   ('catalog-proposal', 1, 'product_create', payload, 'pending', '2026-01-01'))
        db.commit()
        result = resolve_proposal(db, {'id': 1, 'role': 'admin'}, 'catalog-proposal', True)
        assert result['status'] == 'approved'
        assert db.execute('SELECT published FROM products').fetchone()[0] == 0
        assert public_catalog(db) == []


def test_public_catalog_combines_filters_without_exposing_private_products(catalog_app):
    cases = [
        ('Cable USB trenzado', 'Accesorio', 1, 1, 1),
        ('Cable USB agotado', 'Accesorio', 0, 1, 1),
        ('Placa USB', 'Repuesto', 1, 1, 1),
        ('Funda rígida', 'Accesorio', 1, 1, 1),
        ('Pieza interna', 'Categoría privada', 1, 0, 1),
        ('Pieza retirada', 'Categoría retirada', 1, 1, 0),
    ]
    with catalog_app.app_context():
        db = get_db()
        for name, category, available, published, active in cases:
            product_id = create_product(db, {'name': name, 'category': category, 'price': 1, 'stock': 0})
            db.execute('UPDATE products SET available=?, published=?, active=? WHERE id=?',
                       (available, published, active, product_id))
        db.commit()

    client = catalog_app.test_client()
    response = client.get('/catalog', query_string={'q': 'Usb', 'category': 'Accesorio', 'available': '1'})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Cable USB trenzado' in html
    for text in ('Cable USB agotado', 'Placa USB', 'Funda rígida', 'Categoría privada', 'Categoría retirada',
                 'Pieza interna', 'Pieza retirada', 'Productos destacados'):
        assert text not in html
    empty = client.get('/catalog', query_string={'q': 'sin resultados'}).get_data(as_text=True)
    assert 'No encontramos coincidencias' in empty and 'Limpiar filtros' in empty


def test_low_stock_filter_keeps_inventory_context_after_retirement(integration_app, admin_client):
    client, headers = admin_client
    with integration_app.app_context():
        db = get_db()
        for index in range(9):
            last_id = create_product(db, {'name': f'Cable modelo {index}', 'category': 'Accesorio',
                                         'price': 10, 'stock': 2, 'user_id': 1})
        for name, category, stock in [('Cable con stock alto', 'Accesorio', 3),
                                      ('Cable de repuesto', 'Repuesto', 1),
                                      ('Teclado', 'Accesorio', 0)]:
            create_product(db, {'name': name, 'category': category, 'stock': stock, 'user_id': 1})

    assert '/products?stock=low' in client.get('/dashboard').get_data(as_text=True)
    filters = {'q': 'cable', 'category': 'Accesorio', 'stock': 'low', 'page': '2'}
    html = client.get('/products', query_string=filters).get_data(as_text=True)
    assert 'Cable modelo 8' in html and 'Cable modelo 7' not in html
    for excluded in ('Cable con stock alto', 'Cable de repuesto', 'Teclado'):
        assert excluded not in html

    response = client.post(f'/products/{last_id}/retire', headers=headers,
                           query_string={**filters, 'next': 'https://example.test/'})
    assert response.status_code == 302
    target = urlsplit(response.location)
    assert target.netloc == '' and target.path == '/products'
    assert parse_qs(target.query) == {key: [value] for key, value in filters.items()}
    html = client.get(response.location).get_data(as_text=True)
    assert 'Cable modelo 7' in html and 'Cable modelo 8' not in html
