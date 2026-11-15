import io
import json
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
    assert 'Pantalla ficticia' in html and '12,500.50' in html
    assert '987654' not in html and 'Admin ficticio' not in html
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    with catalog_app.app_context():
        assert set(public_catalog(get_db())[0]) == {'name', 'description', 'category', 'price_cents'}


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
