import io
import json
import pytest

from app.application.ai_assistant import resolve_proposal
from app.domain.models import DomainError
from app.infrastructure.database import get_db


def test_duplicate_import_rolls_back_all_approved_rows(integration_app, admin_client):
    client, headers = admin_client
    content = b'nombre,categoria,precio,stock\nCable USB,Accesorios,100,2\n cable   usb , accesorios ,200,3\n'
    response = client.post('/products/import/preview', headers=headers,
                           data={'file': (io.BytesIO(content), 'duplicate.csv')})
    assert response.status_code == 200
    with integration_app.app_context():
        batch = get_db().execute('SELECT id FROM import_batches').fetchone()[0]
    response = client.post(f'/products/import/{batch}/approve', headers=headers, data={'row': ['0', '1']})
    assert response.status_code == 302
    with integration_app.app_context():
        db = get_db()
        assert db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM inventory_movements').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM import_batches WHERE id=?', (batch,)).fetchone()[0] == 1


def test_duplicate_ai_batch_remains_pending_without_partial_products(integration_app):
    with integration_app.app_context():
        db = get_db()
        payload = {'products': [{'name': name, 'category': 'Repuestos', 'price': '10', 'stock': 2}
                                for name in ('Cable USB', ' cable   usb ')]}
        db.execute('INSERT INTO ai_proposals(id,user_id,operation,payload_json,status,created_at) VALUES(?,?,?,?,?,?)',
                   ('duplicate-batch', 1, 'product_create', json.dumps(payload), 'pending', '2026-01-01'))
        db.commit()
        with pytest.raises(DomainError):
            resolve_proposal(db, {'id': 1, 'role': 'admin'}, 'duplicate-batch', True)
        assert db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM inventory_movements').fetchone()[0] == 0
        assert db.execute('SELECT status FROM ai_proposals WHERE id=?', ('duplicate-batch',)).fetchone()[0] == 'pending'


def test_malformed_json_and_absent_required_fields_do_not_create_repair(integration_app, admin_client):
    client, headers = admin_client
    for payload in ([], None, {'id_tecnico': 2}, {'equipo': None, 'descripcion_problema': 'Falla', 'id_tecnico': 2}):
        response = client.post('/api/reparaciones', json=payload, headers=headers)
        assert response.status_code == 400
        assert 'error' in response.get_json()
    with integration_app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM repairs').fetchone()[0] == 0
