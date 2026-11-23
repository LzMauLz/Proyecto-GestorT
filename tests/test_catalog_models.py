import io
import json
import re
from html import unescape

import pytest
from PIL import Image

from app.application.ports import AIProviderError
from app.infrastructure.ai.groq_adapter import GroqAdapter
from app.infrastructure.database import get_db, init_db


SEARCH_PATH = '/catalog/modelos'


@pytest.fixture
def add_part(integration_app):
    def create(name, brand='Samsung', model='Galaxy A15 5G', *, published=True, active=True, available=True):
        with integration_app.app_context():
            db = get_db()
            product = db.execute(
                'INSERT INTO products(name, description, category, price_cents, stock, '
                'published, active, available, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (name, 'Pantalla de demostración', 'Repuestos', 1250050, 987654, published, active, available, '2026-01-01'),
            ).lastrowid
            if brand and model:
                db.execute(
                    'INSERT INTO product_compatibility(product_id, brand, model) VALUES(?, ?, ?)',
                    (product, brand, model),
                )
            db.commit()
        return product
    return create


def public_detail(product_id):
    return f'/catalog/products/{product_id}'


def csrf(client):
    with client.session_transaction() as session:
        session['_csrf_token'] = 'compatibility-test-csrf'
    return {'X-CSRF-Token': 'compatibility-test-csrf'}


class RecordingProvider:
    def __init__(self, response=None, error=None):
        self.response = {'brand': 'Samsung', 'model': 'Galaxy A15 5G'} if response is None else response
        self.error = error
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.response


def test_detail_displays_declared_compatibility_without_private_inventory_data(integration_app, add_part):
    product_id = add_part('Pantalla de prueba', available=False)
    client = integration_app.test_client()

    response = client.get(public_detail(product_id))
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Samsung' in page and 'Galaxy A15 5G' in page and 'No disponible' in page
    assert 'Pantalla de prueba' in page and 'Consultar al taller' in page
    assert '987654' not in page and 'Admin ficticio' not in page
    assert public_detail(product_id) in client.get('/catalog').get_data(as_text=True)


@pytest.mark.parametrize(('published', 'active'), [(False, True), (True, False)])
def test_unpublished_or_inactive_detail_is_not_public(integration_app, add_part, published, active):
    product_id = add_part('Ficha privada', published=published, active=active)
    client = integration_app.test_client()
    assert client.get(public_detail(product_id)).status_code == 404
    assert public_detail(product_id) not in client.get('/catalog').get_data(as_text=True)


def test_detail_uses_catalog_image_and_hides_it_after_unpublishing(integration_app, admin_client, tmp_path):
    integration_app.config['PRODUCT_IMAGE_DIRECTORY'] = str(tmp_path / 'product-images')
    admin, headers = admin_client
    image = io.BytesIO()
    Image.new('RGB', (2, 2), 'purple').save(image, format='PNG')
    image.seek(0)
    response = admin.post('/products/new', data={
        'name': 'Pantalla ilustrada', 'price': '100', 'stock': '1', 'publish': '1',
        'image': (image, 'pantalla.png'),
    }, headers=headers)
    assert response.status_code == 302
    with integration_app.app_context():
        product_id = get_db().execute("SELECT id FROM products WHERE name='Pantalla ilustrada'").fetchone()[0]

    public = integration_app.test_client()
    detail = public.get(public_detail(product_id))
    markup = detail.get_data(as_text=True)
    image_match = re.search(r'href="(/catalog/images/[a-f0-9]+\.png)"', markup)
    assert detail.status_code == 200 and image_match is not None
    assert public.get(image_match[1]).mimetype == 'image/png'
    assert admin.post(f'/products/{product_id}/publication', data={'published': '0'}, headers=headers).status_code == 302
    assert public.get(public_detail(product_id)).status_code == 404
    assert public.get(image_match[1]).status_code == 404


def test_admin_can_replace_compatibilities_atomically_and_other_roles_cannot(integration_app, admin_client, add_part):
    product_id = add_part('Pantalla editable')
    path = f'/products/{product_id}/compatibility'
    anonymous = integration_app.test_client()
    technician = integration_app.test_client()
    tech_headers = csrf(technician)
    with technician.session_transaction() as session:
        session['user_id'] = 2
    client, admin_headers = admin_client
    valid = {'compatibilities': 'Samsung | Galaxy A15 5G\nMotorola | Moto G54'}

    assert anonymous.get(path).status_code == 302
    assert technician.get(path).status_code == 403
    assert technician.post(path, data=valid, headers=tech_headers).status_code == 403
    assert client.post(path, data=valid).status_code == 400
    assert client.get(path).status_code == 200
    assert client.post(path, data=valid, headers=admin_headers).status_code in (302, 303)

    invalid = {'compatibilities': 'Motorola | Otro\nSamsung | Galaxy A15 5G\n samsung | gálaxy  A15 5G'}
    assert client.post(path, data=invalid, headers=admin_headers).status_code == 400
    with integration_app.app_context():
        rows = get_db().execute('SELECT brand, model FROM product_compatibility WHERE product_id=?', (product_id,))
        assert {tuple(row) for row in rows} == {('Samsung', 'Galaxy A15 5G'), ('Motorola', 'Moto G54')}


def test_existing_catalog_remains_readable_before_additive_schema_upgrade(integration_app, add_part):
    product_id = add_part('Pantalla existente', brand='', model='')
    with integration_app.app_context():
        db = get_db()
        db.execute('DROP TABLE product_compatibility')
        db.commit()
        before = tuple(db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone())

    client = integration_app.test_client()
    assert client.get(public_detail(product_id)).status_code == 200
    assert client.get(SEARCH_PATH, query_string={'model': 'Galaxy A15 5G'}).status_code == 200
    with integration_app.app_context():
        init_db()
        init_db()
        db = get_db()
        assert tuple(db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()) == before
        assert db.execute('SELECT COUNT(*) FROM product_compatibility').fetchone()[0] == 0


def test_model_search_distinguishes_variants_and_only_shows_public_available_parts(integration_app, add_part):
    variant_5g = add_part('Pantalla Cinco')
    variant_4g = add_part('Pantalla Cuatro', model='Galaxy A15 4G')
    unavailable = add_part('Pantalla agotada', available=False)
    private = add_part('Pantalla privada', published=False)
    retired = add_part('Pantalla retirada', active=False)
    unverified = add_part('Supuesto compatible Galaxy A15 5G', brand='', model='')
    provider = RecordingProvider()
    integration_app.extensions['gestortech_ai_provider'] = provider
    client = integration_app.test_client()

    partial = client.get(SEARCH_PATH, query_string={'brand': 'Samsung', 'model': 'Galaxy A15'})
    partial_text = partial.get_data(as_text=True)
    assert partial.status_code == 200
    assert 'Galaxy A15 4G' in partial_text and 'Galaxy A15 5G' in partial_text
    assert public_detail(variant_4g) not in partial_text and public_detail(variant_5g) not in partial_text

    match = client.get(SEARCH_PATH, query_string={'brand': 'sámsung', 'model': '  GALAXY  A15 5G  '})
    html = match.get_data(as_text=True)
    assert match.status_code == 200
    assert public_detail(variant_5g) in html
    assert all(public_detail(product_id) not in html for product_id in (variant_4g, unavailable, private, retired, unverified))
    assert provider.calls == []


def test_groq_only_extracts_the_model_from_the_query_and_sqlite_matches_parts(integration_app, add_part):
    product_id = add_part('Ficha cuyo nombre no se transfiere')
    provider = RecordingProvider()
    integration_app.extensions['gestortech_ai_provider'] = provider
    client = integration_app.test_client()
    query = '¿Hay pantalla para Samsung Galaxy A15 5G?'

    response = client.post(SEARCH_PATH, data={'q': query}, headers=csrf(client))
    assert response.status_code == 200
    assert public_detail(product_id) in response.get_data(as_text=True)
    assert len(provider.calls) == 1
    messages = provider.calls[0]
    assert [item['role'] for item in messages] == ['system', 'user']
    assert messages[1] == {'role': 'user', 'content': query}
    system_prompt = messages[0]['content']
    assert 'Ficha cuyo nombre no se transfiere' not in system_prompt
    assert '987654' not in system_prompt and 'example.test' not in system_prompt


def test_model_search_uses_groq_http_chat_contract(integration_app, add_part):
    product_id = add_part('Pantalla de la prueba HTTP de Groq')
    requests = []
    query = 'Busco una pantalla para Samsung Galaxy A15 5G'

    def open_response(request, *, timeout):
        requests.append(request)
        reply = {'brand': 'Samsung', 'model': 'Galaxy A15 5G'}
        envelope = {'choices': [{'message': {'content': json.dumps(reply)}}]}
        return io.BytesIO(json.dumps(envelope).encode('utf-8'))

    integration_app.extensions['gestortech_ai_provider'] = GroqAdapter(
        'test-key', 'openai/gpt-oss-20b', enabled=True, opener=open_response,
    )
    client = integration_app.test_client()
    response = client.post(SEARCH_PATH, data={'q': query}, headers=csrf(client))
    assert response.status_code == 200
    assert public_detail(product_id) in response.get_data(as_text=True)
    assert len(requests) == 1
    request = requests[0]
    assert request.full_url == 'https://api.groq.com/openai/v1/chat/completions'
    assert request.method == 'POST'
    body = json.loads(request.data)
    assert body['model'] == 'openai/gpt-oss-20b'
    assert body['response_format'] == {'type': 'json_object'}
    assert body['messages'][-1] == {'role': 'user', 'content': query}
    assert 'Pantalla de la prueba HTTP de Groq' not in request.data.decode()


def test_ai_does_not_show_a_different_variant_from_the_one_requested(integration_app, add_part):
    wrong_part = add_part('Pantalla variante incorrecta', model='Galaxy A15 4G')
    provider = RecordingProvider({'brand': 'Samsung', 'model': 'Galaxy A15 4G'})
    integration_app.extensions['gestortech_ai_provider'] = provider
    client = integration_app.test_client()

    response = client.post(
        SEARCH_PATH, data={'q': '¿Hay pantalla para Samsung Galaxy A15 5G?'}, headers=csrf(client),
    )
    assert response.status_code == 200
    assert len(provider.calls) == 1
    assert public_detail(wrong_part) not in response.get_data(as_text=True)


def test_ai_requests_confirmation_when_the_query_does_not_name_a_brand(integration_app, add_part):
    product_id = add_part('Pantalla con marca confirmada')
    provider = RecordingProvider({'brand': '', 'model': 'Galaxy A15 5G'})
    integration_app.extensions['gestortech_ai_provider'] = provider
    client = integration_app.test_client()

    response = client.post(SEARCH_PATH, data={'q': 'Pantalla Galaxy A15 5G'}, headers=csrf(client))
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert public_detail(product_id) not in page
    choice_path = re.search(r'href="(/catalog/modelos\?[^"]*exact=1[^"]*)"', page)
    assert choice_path is not None
    confirmed = client.get(unescape(choice_path[1]))
    assert public_detail(product_id) in confirmed.get_data(as_text=True)
    assert len(provider.calls) == 1


def test_ai_response_cannot_supply_catalog_results(integration_app, add_part):
    product_id = add_part('Pantalla que solo debe acreditar el catálogo')
    provider = RecordingProvider({'brand': 'Samsung', 'model': 'Galaxy A15 5G', 'products': [product_id]})
    integration_app.extensions['gestortech_ai_provider'] = provider
    client = integration_app.test_client()

    response = client.post(SEARCH_PATH, data={'q': 'Pantalla Samsung Galaxy A15 5G'}, headers=csrf(client))
    assert response.status_code == 200
    assert public_detail(product_id) not in response.get_data(as_text=True)
    assert len(provider.calls) == 1


def test_manual_search_remains_available_when_groq_fails_or_is_unconfigured(integration_app, add_part):
    product_id = add_part('Pantalla tras error del proveedor')
    provider = RecordingProvider(error=AIProviderError('Marcador privado del proveedor'))
    integration_app.extensions['gestortech_ai_provider'] = provider
    client = integration_app.test_client()
    headers = csrf(client)
    data = {'q': 'Pantalla Samsung Galaxy A15 5G'}

    unavailable = client.post(SEARCH_PATH, headers=headers, data=data)
    assert unavailable.status_code == 200
    assert 'Marcador privado del proveedor' not in unavailable.get_data(as_text=True)
    assert len(provider.calls) == 1
    integration_app.extensions['gestortech_ai_provider'] = None
    response = client.get(SEARCH_PATH, query_string={'brand': 'Samsung', 'model': 'Galaxy A15 5G'})
    assert response.status_code == 200
    assert public_detail(product_id) in response.get_data(as_text=True)


@pytest.mark.parametrize('query', ['Soporte para Pixel 8, correo ejemplo@example.test', 'Pixel 8' + 'a' * 140])
def test_ai_does_not_send_personal_contact_or_an_overlong_query(integration_app, add_part, query):
    add_part('Pantalla con compatibilidad registrada', brand='Google', model='Pixel 8')
    provider = RecordingProvider()
    integration_app.extensions['gestortech_ai_provider'] = provider
    client = integration_app.test_client()
    response = client.post(SEARCH_PATH, headers=csrf(client), data={'q': query})
    assert response.status_code in (200, 400)
    assert provider.calls == []


@pytest.mark.parametrize(('limit', 'next_address'), [
    ('CATALOG_AI_IP_LIMIT', '192.0.2.1'),
    ('CATALOG_AI_GLOBAL_LIMIT', '192.0.2.2'),
    ('CATALOG_AI_DAILY_LIMIT', '192.0.2.2'),
])
def test_public_ai_requires_csrf_and_respects_budgets(integration_app, add_part, limit, next_address):
    product_id = add_part('Pantalla con cuota compartida')
    provider = RecordingProvider()
    integration_app.extensions['gestortech_ai_provider'] = provider
    integration_app.config[limit] = 1
    client = integration_app.test_client()
    data = {'q': 'Pantalla Samsung Galaxy A15 5G'}

    assert client.post(SEARCH_PATH, data=data).status_code == 400
    assert provider.calls == []
    headers = csrf(client)
    first = client.post(SEARCH_PATH, headers=headers, data=data, environ_overrides={'REMOTE_ADDR': '192.0.2.1'})
    limited = client.post(SEARCH_PATH, headers=headers, data=data, environ_overrides={'REMOTE_ADDR': next_address})
    assert first.status_code == 200
    assert limited.status_code == 200
    assert len(provider.calls) == 1
    manual = client.get(SEARCH_PATH, query_string={'model': 'Galaxy A15 5G'})
    assert public_detail(product_id) in manual.get_data(as_text=True)
