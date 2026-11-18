import pytest

from app import create_app
from app.infrastructure.database import get_db, init_db


@pytest.fixture
def integration_app(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'integration-tests-only',
                      'DATABASE': str(tmp_path / 'integration.sqlite3'),
                      'GROQ_ENABLED': False, 'GROQ_API_KEY': '', 'GROQ_MODEL': ''})
    with app.app_context():
        init_db()
        db = get_db()
        db.executemany('INSERT INTO users(id,name,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',
                       [(1, 'Admin ficticio', 'admin@example.test', 'unused', 'admin', '2026-01-01'),
                        (2, 'Técnico ficticio', 'tech@example.test', 'unused', 'technician', '2026-01-01')])
        db.commit()
    return app


@pytest.fixture
def admin_client(integration_app):
    client = integration_app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = 1
        session['_csrf_token'] = 'integration-csrf'
    return client, {'X-CSRF-Token': 'integration-csrf'}
