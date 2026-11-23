from app.application.services import create_repair
from app.infrastructure.database import get_db


def add_repair(db, device, technician=2, status='Recibido'):
    repair_id, code = create_repair(db, {
        'device': device, 'issue': 'Falla ficticia', 'assigned_to': technician,
    }, 1, 'admin')
    db.execute('UPDATE repairs SET status=?, updated_at=? WHERE id=?', (status, '2026-11-22T12:00:00Z', repair_id))
    db.commit()
    return code


def add_second_technician(db):
    db.execute('INSERT INTO users(id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',
               (3, 'Técnico alterno', 'alterno@example.test', 'unused', 'technician', '2026-11-22'))
    db.commit()


def test_queue_is_private_and_technician_scope_cannot_be_overridden(integration_app):
    with integration_app.app_context():
        db = get_db()
        add_second_technician(db)
        add_repair(db, 'Equipo propio')
        other_code = add_repair(db, 'Equipo de otro técnico', technician=3)

    client = integration_app.test_client()
    response = client.get('/repairs')
    assert response.status_code == 302
    assert '/login' in response.location

    with client.session_transaction() as session:
        session['user_id'] = 2
    response = client.get('/repairs', query_string={'technician': 3})
    content = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['Referrer-Policy'] == 'no-referrer'
    assert 'Equipo propio' in content
    assert 'Equipo de otro técnico' not in content
    assert other_code not in content
    assert 'name="technician"' not in content
    response = client.get('/repairs', query_string={'q': other_code})
    assert 'No hay reparaciones que coincidan' in response.get_data(as_text=True)


def test_admin_can_combine_search_status_and_technician(integration_app, admin_client):
    with integration_app.app_context():
        db = get_db()
        add_second_technician(db)
        code = add_repair(db, 'Portátil objetivo', technician=3, status='En diagnóstico')
        add_repair(db, 'Portátil ajeno', status='En diagnóstico')
        add_repair(db, 'Portátil entregado', technician=3, status='Entregado')

    client, _ = admin_client
    response = client.get('/repairs', query_string={'q': 'PORTÁTIL', 'status': 'En diagnóstico', 'technician': 3})
    content = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Portátil objetivo' in content
    assert 'Portátil ajeno' not in content
    assert 'Portátil entregado' not in content
    response = client.get('/repairs', query_string={'q': code.lower()})
    assert 'Portátil objetivo' in response.get_data(as_text=True)


def test_pending_and_ready_shortcuts_and_stable_pagination(integration_app, admin_client):
    with integration_app.app_context():
        db = get_db()
        for index in range(22):
            add_repair(db, f'Orden ficticia {index:02d}', status='Esperando aprobación')
        add_repair(db, 'Equipo listo', status='Listo para entregar')
        add_repair(db, 'Equipo cancelado', status='Cancelado')

    client, _ = admin_client
    page_1 = client.get('/repairs', query_string={'view': 'pending', 'q': 'Orden ficticia'}).get_data(as_text=True)
    assert 'Página 1 de 2' in page_1
    assert 'Orden ficticia 21' in page_1 and 'Orden ficticia 00' not in page_1
    assert 'page=2' in page_1 and 'status=pending' in page_1 and 'q=Orden+ficticia' in page_1
    page_2 = client.get('/repairs', query_string={'status': 'pending', 'q': 'Orden ficticia', 'page': 2}).get_data(as_text=True)
    assert 'Página 2 de 2' in page_2
    assert 'Orden ficticia 00' in page_2 and 'Orden ficticia 21' not in page_2
    pending = client.get('/repairs?view=pending').get_data(as_text=True)
    assert 'Equipo listo' not in pending and 'Equipo cancelado' not in pending
    ready = client.get('/repairs?view=ready').get_data(as_text=True)
    assert 'Equipo listo' in ready and 'Equipo cancelado' not in ready and 'Orden ficticia' not in ready
