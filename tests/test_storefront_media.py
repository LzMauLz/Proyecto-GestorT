import io
import re
from types import SimpleNamespace

import pytest
from PIL import Image, PngImagePlugin

from app.application.catalog import public_catalog
from app.application.services import create_product
from app.infrastructure.database import get_db, init_db
from app.infrastructure.product_images import MAX_UPLOAD_BYTES, image_path, store_image


@pytest.fixture
def media_app(integration_app, tmp_path):
    integration_app.config['PRODUCT_IMAGE_DIRECTORY'] = str(tmp_path / 'product-images')
    return integration_app


def raster(fmt='PNG', size=(40, 30), metadata=False):
    out = io.BytesIO()
    image = Image.new('RGBA' if fmt == 'PNG' else 'RGB', size, (80, 20, 150, 100) if fmt == 'PNG' else (80, 20, 150))
    kwargs = {}
    if metadata and fmt == 'PNG':
        info = PngImagePlugin.PngInfo(); info.add_text('Author', 'SYNTHETIC-PRIVATE-METADATA'); kwargs['pnginfo'] = info
    image.save(out, format=fmt, **kwargs)
    return out.getvalue()


def add_product(app, name='Cable', stock=7):
    with app.app_context():
        return create_product(get_db(), {'name': name, 'category': 'Accesorios', 'price': 100, 'stock': stock, 'user_id': 1})


def product_row(app, product_id):
    with app.app_context():
        return dict(get_db().execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone())


def upload(client, headers, product_id, content, filename='product.png'):
    return client.post(f'/products/{product_id}/image', headers=headers, data={'image': (io.BytesIO(content), filename)})


@pytest.mark.parametrize(('fmt', 'filename'), [('PNG', 'photo.png'), ('JPEG', 'photo.jpg'), ('WEBP', 'photo.webp')])
def test_real_image_decoders_reencode_as_png_without_metadata(media_app, admin_client, fmt, filename):
    client, headers = admin_client
    product_id = add_product(media_app)
    response = upload(client, headers, product_id, raster(fmt, metadata=True), filename)
    assert response.status_code == 302
    row = product_row(media_app, product_id)
    assert row['published'] == 0
    assert re.fullmatch('[0-9a-f]{32}\\.png', row['image_key'])
    private = client.get(f'/products/{product_id}/image')
    assert private.status_code == 200
    assert private.headers['Content-Type'].startswith('image/png')
    assert private.headers['Cache-Control'] == 'no-store'
    with Image.open(io.BytesIO(private.data)) as result:
        assert result.format == 'PNG'
        assert 'Author' not in result.info
        assert not result.getexif()
        assert result.size == (40, 30)
        if fmt == 'PNG':
            assert result.mode == 'RGBA'
    assert b'SYNTHETIC-PRIVATE-METADATA' not in private.data


def test_public_image_requires_active_published_product(media_app, admin_client):
    client, headers = admin_client
    product_id = add_product(media_app)
    assert upload(client, headers, product_id, raster()).status_code == 302
    key = product_row(media_app, product_id)['image_key']
    public = media_app.test_client()
    url = '/catalog/images/' + key
    assert public.get(url).status_code == 404
    assert client.post(f'/products/{product_id}/publication', headers=headers, data={'published': '1'}).status_code == 302
    response = public.get(url)
    assert response.status_code == 200
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Cache-Control'] == 'no-store'
    assert client.post(f'/products/{product_id}/publication', headers=headers, data={'published': '0'}).status_code == 302
    assert public.get(url).status_code == 404
    client.post(f'/products/{product_id}/publication', headers=headers, data={'published': '1'})
    client.post(f'/products/{product_id}/retire', headers=headers)
    assert public.get(url).status_code == 404
    assert public.get('/catalog/images/..%2f..%2f.env').status_code == 404


def test_media_routes_require_admin_and_csrf(media_app, admin_client):
    client, headers = admin_client
    product_id = add_product(media_app)
    anonymous = media_app.test_client()
    assert anonymous.get(f'/products/{product_id}/image').status_code == 302
    assert upload(client, {}, product_id, raster()).status_code == 400
    with client.session_transaction() as session:
        session['user_id'] = 2
    assert upload(client, headers, product_id, raster()).status_code == 403
    assert client.get(f'/products/{product_id}/image').status_code == 403
    assert client.post(f'/products/{product_id}/availability', headers=headers, data={'available': '0'}).status_code == 403
    assert product_row(media_app, product_id)['image_key'] is None


@pytest.mark.parametrize(('content', 'name'), [(b'<svg><script>alert(1)</script></svg>', 'bad.svg'), (b'not an image', 'bad.png'), (b'GIF89a', 'bad.jpg'), (b'', 'empty.png')])
def test_invalid_upload_never_changes_product(media_app, admin_client, content, name):
    client, headers = admin_client
    product_id = add_product(media_app)
    assert upload(client, headers, product_id, content, name).status_code == 400
    assert product_row(media_app, product_id)['image_key'] is None
    assert product_row(media_app, product_id)['stock'] == 7


def test_byte_dimension_and_actual_content_limits(media_app, admin_client):
    client, headers = admin_client
    product_id = add_product(media_app)
    for content, filename in ((b'x' * (MAX_UPLOAD_BYTES + 1), 'large.png'), (raster(size=(6001, 1)), 'wide.png'), (raster(size=(4000, 3100)), 'pixels.png'), (raster(), 'disguised.jpg')):
        assert upload(client, headers, product_id, content, filename).status_code == 400
    assert product_row(media_app, product_id)['image_key'] is None


def test_commercial_availability_is_separate_from_stock(media_app, admin_client):
    client, headers = admin_client
    product_id = add_product(media_app)
    client.post(f'/products/{product_id}/publication', headers=headers, data={'published': '1'})
    assert client.post(f'/products/{product_id}/availability', headers=headers, data={'available': '0'}).status_code == 302
    row = product_row(media_app, product_id)
    assert row['available'] == 0
    assert row['stock'] == 7
    assert client.post(f'/products/{product_id}/availability', headers=headers, data={'available': 'true'}).status_code == 400
    with media_app.app_context():
        item = public_catalog(get_db())[0]
        assert item['available'] == 0
        assert set(item) == {'id', 'name', 'description', 'category', 'price_cents', 'available', 'image_key'}


def test_new_and_edit_forms_save_image_and_commercial_fields_atomically(media_app, admin_client):
    client, headers = admin_client
    form = {'name': 'Nuevo', 'description': 'Sintético', 'category': 'Accesorios', 'price': '10', 'stock': '2', 'available': '0', 'image': (io.BytesIO(raster()), 'new.png')}
    assert client.post('/products/new', headers=headers, data=form).status_code == 302
    with media_app.app_context():
        db = get_db()
        product_id = db.execute("SELECT id FROM products WHERE name='Nuevo'").fetchone()[0]
    row = product_row(media_app, product_id)
    assert row['available'] == 0 and row['published'] == 0 and row['image_key']
    old_key = row['image_key']
    assert client.post(f'/products/{product_id}/edit', headers=headers, data={'name': 'Editado', 'description': 'Editado', 'category': 'Accesorios', 'price': '11', 'available': '1', 'image': (io.BytesIO(raster('JPEG')), 'edited.jpg')}).status_code == 302
    row = product_row(media_app, product_id)
    assert row['name'] == 'Editado' and row['available'] == 1 and row['image_key'] != old_key
    assert row['stock'] == 2 and row['published'] == 0


def test_duplicate_forms_roll_back_and_discard_new_image(media_app, admin_client, tmp_path):
    client, headers = admin_client
    first = add_product(media_app, 'Cable')
    second = add_product(media_app, 'Adaptador')
    before = product_row(media_app, second)
    fields = {'name': 'Cable', 'description': 'No guardar', 'category': 'Accesorios', 'price': '10', 'stock': '1', 'available': '0'}
    for path in ('/products/new', f'/products/{second}/edit'):
        response = client.post(path, headers=headers, data={**fields, 'image': (io.BytesIO(raster()), 'collision.png')})
        assert response.status_code == 200
        assert b'Ya existe' in response.data
        if path == '/products/new':
            assert f'/products/{first}/edit'.encode() in response.data
    assert product_row(media_app, second) == before
    assert list((tmp_path / 'product-images').glob('*.png')) == []
    with media_app.app_context():
        assert get_db().execute('SELECT count(*) FROM products').fetchone()[0] == 2


def test_publish_with_image_from_product_form_updates_catalog_and_featured(media_app, admin_client):
    client, headers = admin_client
    for index in range(9):
        product_id = add_product(media_app, f'Anterior {index}')
        assert client.post(f'/products/{product_id}/publication', headers=headers, data={'published': '1'}).status_code == 302
    response = client.post('/products/new', headers=headers, data={
        'name': 'Ficha nueva', 'price': '120.000,50', 'stock': '2', 'publish': '1',
        'image': (io.BytesIO(raster('JPEG')), 'producto.jpg'),
    })
    assert response.status_code == 302
    public = media_app.test_client()
    html = public.get('/catalog').get_data(as_text=True)
    shelf = html.split('id="store-carousel"', 1)[1].split('</section>', 1)[0]
    assert 'Ficha nueva' in shelf and '120.000,50' in shelf
    key = re.search(r'/catalog/images/([a-f0-9]+\.png)', shelf)[1]
    assert public.get('/catalog/images/' + key).mimetype == 'image/png'


def test_generated_filename_collision_never_overwrites(media_app, monkeypatch):
    # Deterministic collision injection verifies exclusive filesystem creation.
    monkeypatch.setattr('app.infrastructure.product_images.uuid.uuid4', lambda: SimpleNamespace(hex='1' * 32))
    with media_app.app_context():
        key = store_image(raster())
        before = image_path(key).read_bytes()
        with pytest.raises(FileExistsError):
            store_image(b'replacement')
        assert image_path(key).read_bytes() == before


def test_media_migration_preserves_existing_publication(media_app):
    with media_app.app_context():
        db = get_db()
        db.execute('DROP TABLE products')
        db.execute("CREATE TABLE products (id INTEGER PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',category TEXT NOT NULL DEFAULT '',price_cents INTEGER NOT NULL,stock INTEGER NOT NULL DEFAULT 0,published INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL)")
        db.execute("INSERT INTO products(id,name,category,price_cents,stock,published,created_at) VALUES(1,'Legacy','Partes',100,3,1,'2026-01-01')")
        db.commit()
        init_db(); init_db()
        row = db.execute('SELECT * FROM products').fetchone()
        assert row['name'] == 'Legacy' and row['stock'] == 3 and row['published'] == 1
        assert row['available'] == 1 and row['image_key'] is None
