import pytest

from app.infrastructure.database import get_db, init_db


PRIVATE_CONTACT = {
    'customer_name': 'Cliente ficticio <Demostración>',
    'customer_phone': '+1 202-555-0142',
    'customer_email': 'contacto@example.test',
}
REPAIR_FORM = {'device': 'Portátil ficticio', 'issue': 'Revisión de pantalla', 'assigned_to': '2'}
REPAIR_API = {'equipo': 'Portátil ficticio', 'descripcion_problema': 'Revisión de pantalla', 'id_tecnico': 2}


def test_repair_contact_visible_only_in_private_detail(integration_app, admin_client):
    client, headers = admin_client
    registered = client.post('/repairs/new', data={**REPAIR_FORM, **PRIVATE_CONTACT}, headers=headers)
    assert registered.status_code == 302
    detail = client.get(registered.location)
    assert detail.status_code == 200
    assert detail.headers['Cache-Control'] == 'no-store'
    assert 'Cliente ficticio &lt;Demostración&gt;' in detail.get_data(as_text=True)
    for field in ('customer_phone', 'customer_email'):
        assert PRIVATE_CONTACT[field] in detail.get_data(as_text=True)

    with integration_app.app_context():
        code = get_db().execute('SELECT tracking_code FROM repairs').fetchone()[0]
    public = integration_app.test_client()
    csrf_token = public.get('/api/csrf').json['token_csrf']
    for response in (
        public.get(f'/api/seguimiento/{code}'),
        public.post('/track', data={'code': code, '_csrf_token': csrf_token}),
        client.get('/api/reparaciones'),
        client.get('/repairs'),
        client.post('/api/taller/chat', json={'mensaje': f'Ver la reparación {code}'}, headers=headers),
    ):
        assert response.status_code == 200
        assert all(value not in response.get_data(as_text=True) for value in PRIVATE_CONTACT.values())
        assert 'Cliente ficticio' not in response.get_data(as_text=True)
    assert public.get(registered.location).status_code == 302


@pytest.mark.parametrize('fields', [
    {'telefono_cliente': 'uno dos tres'},
    {'telefono_cliente': '123456'},
    {'correo_cliente': 'sin-dominio'},
    {'nombre_cliente': 'A' * 121},
    {'nombre_cliente': 'Nombre\nOtras líneas'},
    {'nombre_cliente': False},
])
def test_create_api_rejects_invalid_contact_atomically(integration_app, admin_client, fields):
    client, headers = admin_client
    response = client.post('/api/reparaciones', json={**REPAIR_API, **fields}, headers=headers)
    assert response.status_code == 400
    with integration_app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM repairs').fetchone()[0] == 0
        assert get_db().execute('SELECT COUNT(*) FROM repair_history').fetchone()[0] == 0


def test_repair_contact_edit_honors_assignment_csrf_and_timeline(integration_app, admin_client):
    client, headers = admin_client
    response = client.post('/api/reparaciones', json={
        **REPAIR_API, 'nombre_cliente': 'Cliente inicial', 'correo_cliente': 'inicial@example.test',
    }, headers=headers)
    assert response.status_code == 201
    route = f"/repairs/{response.json['id_reparacion']}"
    public_api = f"/api/seguimiento/{response.json['codigo_seguimiento']}"
    original_public_timeline = client.get(public_api).json
    assert client.post(route, data=PRIVATE_CONTACT).status_code == 400

    with integration_app.app_context():
        db = get_db()
        db.execute("INSERT INTO users(id,name,email,password_hash,role,created_at) "
                   "VALUES(3,'Otro técnico','otro@example.test','unused','technician','2026-01-01')")
        db.commit()
    with client.session_transaction() as session:
        session['user_id'] = 3
    assert client.get(route).status_code == 403
    assert client.post(route, data=PRIVATE_CONTACT, headers=headers).status_code == 403
    with client.session_transaction() as session:
        session['user_id'] = 2
    invalid = client.post(route, data={**PRIVATE_CONTACT, 'customer_phone': '123'}, headers=headers)
    assert invalid.status_code == 400
    assert 'Cliente inicial' in invalid.get_data(as_text=True)
    assert 'Escribe un teléfono válido' in invalid.get_data(as_text=True)
    corrected = client.post(route, data=PRIVATE_CONTACT, headers=headers, follow_redirects=True)
    assert corrected.status_code == 200
    assert PRIVATE_CONTACT['customer_email'] in corrected.get_data(as_text=True)
    assert client.get(public_api).json == original_public_timeline


def test_migration_adds_contact_to_an_existing_order(integration_app, admin_client):
    client, headers = admin_client
    registered = client.post('/api/reparaciones', json=REPAIR_API, headers=headers)
    assert registered.status_code == 201
    repair_id = registered.json['id_reparacion']
    code = registered.json['codigo_seguimiento']
    with integration_app.app_context():
        db = get_db()
        for column in PRIVATE_CONTACT:
            db.execute(f'ALTER TABLE repairs DROP COLUMN {column}')
        db.commit()
        init_db()
        init_db()
        order = db.execute('SELECT * FROM repairs WHERE id=?', (repair_id,)).fetchone()
        assert order['tracking_code'] == code and order['assigned_to'] == 2
        assert all(order[key] == '' for key in PRIVATE_CONTACT)
        assert db.execute('SELECT COUNT(*) FROM repair_history WHERE repair_id=?', (repair_id,)).fetchone()[0] == 1
    assert 'Añadir datos del cliente' in client.get(f'/repairs/{repair_id}').get_data(as_text=True)
