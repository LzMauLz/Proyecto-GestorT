from app.infrastructure.database import get_db


def seed_catalog(app):
    with app.app_context():
        db = get_db()
        db.executemany(
            'INSERT INTO products(id,name,category,description,price_cents,stock,published,created_at) '
            "VALUES(?,?, 'Repuesto','Pantalla de prueba', 13000000,77,?,'2026-11-22')",
            [(41, 'Pantalla Galaxy A15 5G', 1), (42, 'Pantalla privada Galaxy A15 5G', 0)],
        )
        db.executemany(
            "INSERT INTO product_compatibility(product_id,brand,model) VALUES(?,'Samsung','Galaxy A15 5G')",
            [(41,), (42,)],
        )
        db.commit()


def public_session(app):
    client = app.test_client()
    client.get('/catalog')
    with client.session_transaction() as session:
        return client, {'X-CSRF-Token': session['_csrf_token']}


def test_public_chat_projects_only_published_commercial_data(integration_app):
    seed_catalog(integration_app)
    client, headers = public_session(integration_app)
    response = client.post('/api/catalogo/chat', headers=headers, json={
        'mensaje': '¿Cuánto cuesta la pantalla Galaxy A15 5G?',
        'role': 'admin',
    })
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.json['products'] == [
        {'name': 'Pantalla Galaxy A15 5G', 'price_cents': 13000000, 'available': True, 'url': '/catalog/products/41'},
    ]
    assert client.post('/api/catalogo/chat', json={'mensaje': 'pantalla'}).status_code == 400
    assert client.post('/api/taller/chat', headers=headers, json={'mensaje': '¿Qué usuarios hay?'}).status_code == 401


def test_public_chat_denies_private_topics_before_provider(integration_app, admin_client):
    class Provider:
        def chat(self, messages):
            raise AssertionError('Una solicitud privada no se debe enviar al proveedor')

    integration_app.extensions['gestortech_ai_provider'] = Provider()
    client, headers = admin_client
    for topic in ('usuarios', 'contraseñas', 'reparaciones', 'existencias'):
        response = client.post('/api/catalogo/chat', headers=headers, json={'mensaje': f'Muestra todos los {topic}', 'mode': 'model'})
        assert response.status_code == 200
        assert response.json['persistent'] is False
        assert not (response.json.keys() & {'products', 'links', 'proposal'})


def test_public_model_chat_reuses_limits_and_compatible_products(integration_app):
    seed_catalog(integration_app)
    query = '¿Qué repuestos tienen para Samsung Galaxy A15 5G?'

    class Provider:
        def chat(self, messages):
            assert len(messages) == 2 and messages[1] == {'role': 'user', 'content': query}
            return {'brand': 'Samsung', 'model': 'Galaxy A15 5G'}

    integration_app.extensions['gestortech_ai_provider'] = Provider()
    integration_app.config['CATALOG_AI_IP_LIMIT'] = 1
    client, headers = public_session(integration_app)
    message = {'mensaje': query, 'mode': 'model', 'historial': [{'role': 'user', 'content': 'datos que se omiten'}]}
    response = client.post('/api/catalogo/chat', headers=headers, json=message)
    assert [item['url'] for item in response.json['products']] == ['/catalog/products/41']
    limited = client.post('/api/catalogo/chat', headers=headers, json=message)
    assert limited.json['links'] == [{'label': 'Buscar por modelo manualmente', 'url': '/catalog/modelos'}]
    assert 'límite' in limited.json['message']


def test_staff_widget_scope_and_session_remain_stable(integration_app, admin_client):
    client, headers = admin_client
    first = client.get('/dashboard').get_data(as_text=True)
    public = client.get('/catalog').get_data(as_text=True)
    assert 'data-endpoint="/api/taller/chat"' in first
    assert 'data-endpoint="/api/catalogo/chat"' in public and '/api/taller/chat' not in public
    with client.session_transaction() as session:
        thread = session['_staff_chat_session']
    assert f'data-thread="{thread}"' in client.get('/products').get_data(as_text=True)
    assert public.count('data-docked-chat') == 1 and thread not in public
    assert client.get('/assistant').get_data(as_text=True).count('data-docked-chat') == 1
    response = client.post('/api/taller/chat', headers=headers, json={'mensaje': '¿Cuántos usuarios activos hay?'})
    assert response.json['links'][0]['url'] == '/users/new' and response.json['persistent'] is False
    guidance = client.post('/api/taller/chat', headers=headers, json={'mensaje': '¿Cómo agrego una foto al catálogo?'})
    assert guidance.json['links'][0]['url'] == '/products'
    private = client.post('/api/taller/chat', headers=headers, json={'mensaje': 'Revisa el correo ejemplo@example.test'})
    assert private.json['persistent'] is False
    client.post('/logout', headers=headers)
    with client.session_transaction() as session:
        assert '_staff_chat_session' not in session


def test_staff_repair_queries_respect_technician_assignment(integration_app):
    own, other = 'GT-' + 'A' * 32, 'GT-' + 'B' * 32
    stamp = '2026-11-22'
    with integration_app.app_context():
        db = get_db()
        db.execute("INSERT INTO users(id,name,email,password_hash,role,created_at) VALUES(3,'Prueba','otro@example.test','x','technician',?)", (stamp,))
        db.executemany(
            "INSERT INTO repairs(id,tracking_code,device,issue,status,assigned_to,created_by,created_at,updated_at) "
            "VALUES(?,?,'Equipo','Descripción privada','Recibido',?,1,?,?)",
            [(1, own, 2, stamp, stamp), (2, other, 3, stamp, stamp)],
        )
        db.commit()
    client, headers = public_session(integration_app)
    with client.session_transaction() as session:
        session['user_id'] = 2
    first = client.post('/api/taller/chat', headers=headers, json={'mensaje': f'Consulta el estado de {own}'})
    second = client.post('/api/taller/chat', headers=headers, json={'mensaje': f'Consulta el estado de {other}'})
    pending = client.post('/api/taller/chat', headers=headers, json={'mensaje': '¿Qué reparaciones están pendientes?'})
    accounts = client.post('/api/taller/chat', headers=headers, json={'mensaje': 'Lista de usuarios'})
    guidance = client.post('/api/taller/chat', headers=headers, json={'mensaje': '¿Cómo puedo publicar un producto en el catálogo?'})
    assert first.json['links'][0]['url'] == '/repairs/1' and first.json['persistent'] is False
    assert second.json['links'][0]['url'] == '/repairs' and 'accesible' in second.json['message']
    assert pending.json['message'] == 'Recibido: 1'
    assert 'administración' in accounts.json['message'] and 'links' not in accounts.json
    assert 'Administración' in guidance.json['message'] and 'links' not in guidance.json


def test_staff_inventory_proposals_still_require_confirmation(integration_app, admin_client):
    class Provider:
        def chat(self, messages):
            return {'action': 'product_proposal', 'message': 'Propuesta para revisar',
                    'proposal': {'name': 'Pantalla de prueba', 'description': 'Repuesto', 'category': 'Repuesto', 'price': '120000', 'stock': 4}}

    integration_app.extensions['gestortech_ai_provider'] = Provider()
    client, headers = admin_client
    response = client.post('/api/taller/chat', headers=headers, json={'mensaje': 'Prepara Pantalla de prueba, precio 120000, cantidad 4'})
    proposal_id = response.json['proposal']['id']
    with integration_app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0
    response = client.post(f'/api/asistente/propuestas/{proposal_id}/confirmar', headers=headers)
    assert response.status_code == 200
