"""Verify the existing local-demo security boundary without provider calls."""
import pytest

from app import create_app
from app.infrastructure.database import get_db, init_db


@pytest.fixture
def demo_app(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'synthetic-local-demo',
                      'DATABASE': str(tmp_path / 'demo.sqlite3'),
                      'GROQ_ENABLED': False, 'GROQ_API_KEY': '', 'GROQ_MODEL': ''})
    with app.app_context():
        init_db()
        db = get_db()
        db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                   ('Técnico ficticio', 'tech@example.test', 'unused-hash', 'technician', '2026-01-01'))
        db.commit()
    return app


def test_local_catalog_and_manual_workflow_do_not_need_provider(demo_app):
    assert demo_app.extensions['gestortech_ai_provider'] is None
    client = demo_app.test_client()
    assert client.get('/catalog').status_code == 200
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['_csrf_token'] = 'demo-csrf'
    assert client.get('/assistant').status_code == 200
    response = client.post('/api/asistente/mensaje', json={'mensaje': 'Consulta de prueba'},
                           headers={'X-CSRF-Token': 'demo-csrf'})
    assert response.status_code == 503
    with demo_app.app_context():
        assert get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0


def test_personnel_and_catalog_writes_cannot_be_reached_anonymously(demo_app):
    client = demo_app.test_client()
    assert client.get('/dashboard').status_code == 302
    assert client.get('/products/new').status_code == 302
    assert client.get('/api/productos').status_code == 401
    response = client.get('/track')
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert "default-src 'self'" in response.headers['Content-Security-Policy']
