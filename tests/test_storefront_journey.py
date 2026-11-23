"""Full local approval-to-catalog journey; provider response is an explicit test double."""
import io
from PIL import Image

from app.infrastructure.database import get_db


def test_featured_precedes_results_and_catalog_filters_keep_other_selections(integration_app):
    with integration_app.app_context():
        db = get_db()
        db.executemany(
            'INSERT INTO products(name,category,price_cents,available,published,created_at) VALUES (?,?,1000,?,1,?)',
            [('Cable flexible disponible', 'Repuesto', 1, '2026-11-22'),
             ('Cable flexible agotado', 'Repuesto', 0, '2026-11-22'),
             ('Cable auxiliar', 'Accesorio', 1, '2026-11-22')],
        )
        db.commit()
    client = integration_app.test_client()
    home = client.get('/catalog').get_data(as_text=True)
    assert home.index('id="productos-destacados"') < home.index('id="catalog-results"')
    assert 'aria-current="true">Todos los estados' in home

    filtered = client.get('/catalog?q=cable&category=repuesto&available=1').get_data(as_text=True)
    assert 'id="productos-destacados"' not in filtered
    assert 'aria-current="true">Repuesto' in filtered and 'aria-current="true">Solo disponibles' in filtered
    assert 'Cable flexible disponible' in filtered
    assert 'Cable flexible agotado' not in filtered and 'Cable auxiliar' not in filtered
    assert 'q=cable&amp;category=Repuesto#catalog-results' in filtered
    assert 'q=cable&amp;category=Accesorio&amp;available=1#catalog-results' in filtered


def test_accept_image_publish_availability_and_revoke(integration_app, admin_client, tmp_path):
    integration_app.config['PRODUCT_IMAGE_DIRECTORY'] = str(tmp_path / 'images')

    class ProposalProvider:
        def chat(self, messages):
            return {'action': 'product_proposal', 'message': 'Propuesta para revisar',
                    'proposal': {'name': 'Repuesto ficticio', 'description': 'Ficha suministrada por el usuario',
                                 'category': 'Repuestos', 'price': '12500.50', 'stock': 3}}

    integration_app.extensions['gestortech_ai_provider'] = ProposalProvider()
    client, headers = admin_client
    response = client.post('/api/asistente/mensaje', headers=headers,
                           json={'mensaje': 'Prepara la ficha del repuesto con los datos suministrados'})
    assert response.status_code == 200
    proposal_id = response.json['proposal']['id']
    with integration_app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0
    response = client.post(f'/api/asistente/propuestas/{proposal_id}/confirmar', headers=headers)
    assert response.status_code == 200
    product_id = response.json['product_id']
    public = integration_app.test_client()
    assert 'Repuesto ficticio' not in public.get('/catalog').get_data(as_text=True)

    original = io.BytesIO()
    Image.new('RGB', (30, 30), '#6b32ad').save(original, format='JPEG')
    original.seek(0)
    assert client.post(f'/products/{product_id}/image', headers=headers,
                       data={'image': (original, 'repuesto.jpg')}).status_code == 302
    with integration_app.app_context():
        db = get_db()
        row = db.execute('SELECT image_key,published,stock FROM products WHERE id=?', (product_id,)).fetchone()
        image_key = row['image_key']
        assert row['published'] == 0 and row['stock'] == 3
    assert public.get(f'/catalog/images/{image_key}').status_code == 404
    assert client.post(f'/products/{product_id}/publication', headers=headers, data={'published': '1'}).status_code == 302
    assert client.post(f'/products/{product_id}/availability', headers=headers, data={'available': '0'}).status_code == 302
    html = public.get('/catalog').get_data(as_text=True)
    assert 'Repuesto ficticio' in html and 'No disponible' in html and '12.500,50' in html
    assert public.get(f'/catalog/images/{image_key}').mimetype == 'image/png'
    assert client.post(f'/products/{product_id}/availability', headers=headers, data={'available': '1'}).status_code == 302
    with integration_app.app_context():
        assert get_db().execute('SELECT stock FROM products WHERE id=?', (product_id,)).fetchone()[0] == 3
    assert client.post(f'/products/{product_id}/publication', headers=headers, data={'published': '0'}).status_code == 302
    assert public.get(f'/catalog/images/{image_key}').status_code == 404
    assert 'Repuesto ficticio' not in public.get('/catalog').get_data(as_text=True)
