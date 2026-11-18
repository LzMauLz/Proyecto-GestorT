"""Manual live check: five Groq requests, synthetic data, disposable SQLite.

Execute only after approval: python -B verify_live_groq.py
Never collected by pytest; never prints credentials or provider content.
"""
import os
import secrets
import tempfile

from app import create_app
from app.application.ai_import import prepare_product_proposal
from app.application.services import create_product
from app.infrastructure.ai.groq_adapter import GroqAdapter
from app.infrastructure.database import get_db, init_db
from config.settings import Config


def main():
    config = Config.from_environment()
    if not config['GROQ_API_KEY'] or not config['GROQ_MODEL']:
        raise RuntimeError('Configuración Groq incompleta.')
    with tempfile.TemporaryDirectory(prefix='gestortech-groq-live-') as temp:
        app = create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32),
                          'DATABASE': os.path.join(temp, 'live.sqlite3'),
                          'PRODUCT_IMAGE_DIRECTORY': os.path.join(temp, 'images'),
                          'GROQ_ENABLED': False, 'GROQ_API_KEY': '', 'GROQ_MODEL': ''})
        provider = GroqAdapter(config['GROQ_API_KEY'], config['GROQ_MODEL'], True, timeout=30)
        app.extensions['gestortech_ai_provider'] = provider
        with app.app_context():
            init_db()
            db = get_db()
            db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                       ('Admin ficticio', 'admin@example.test', 'unused', 'admin', '2026-01-01'))
            db.commit()
            create_product(db, {'name': 'Cable QA', 'category': 'Accesorios', 'price': '18000', 'stock': 4, 'user_id': 1})
        client = app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = 1
            session['_csrf_token'] = 'live-test-csrf'
        headers = {'X-CSRF-Token': 'live-test-csrf'}

        def ask(message):
            response = client.post('/api/asistente/mensaje', json={'mensaje': message}, headers=headers)
            assert response.status_code == 200, f'Groq real HTTP {response.status_code}; contenido omitido.'
            return response.json

        def count():
            with app.app_context():
                return get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0]

        answer = ask('Cuanto vale el Cable QA? Responde el precio que consta en inventario, sin hacer cambios.')
        assert answer['action'] == 'answer' and answer['proposal'] is None
        assert any(value in answer['message'] for value in ('18000', '18.000', '18,000'))
        print('PASS consulta natural por nombre y precio ficticio', flush=True)
        incomplete = ask('Prepara un producto llamado Base QA, descripcion soporte para pruebas. Todavia no he decidido su precio ni su cantidad.')
        assert incomplete['proposal'] is None
        print('PASS aclaracion de faltantes sin propuesta', flush=True)
        message = ('Prepara un producto nuevo: nombre Base QA, descripcion soporte ficticio, '
                   'categoria Accesorios, precio COP 25000.00, cantidad inicial 2. Solo propuesta para revisar.')
        draft = ask(message)
        assert draft['proposal'] and draft['proposal']['operation'] == 'product_create' and count() == 1
        cancelled = client.post('/api/asistente/propuestas/' + draft['proposal']['id'] + '/cancelar', headers=headers)
        assert cancelled.status_code == 200 and cancelled.json['status'] == 'cancelled' and count() == 1
        print('PASS propuesta real y cancelacion sin crear producto', flush=True)
        draft = ask(message)
        assert draft['proposal'] and draft['proposal']['operation'] == 'product_create' and count() == 1
        approved = client.post('/api/asistente/propuestas/' + draft['proposal']['id'] + '/confirmar', headers=headers)
        assert approved.status_code == 200
        with app.app_context():
            row = get_db().execute('SELECT name,price_cents,stock,published FROM products WHERE id=?',
                                   (approved.json['product_id'],)).fetchone()
            assert tuple(row) == ('Base QA', 2500000, 2, 0)
        print('PASS aprobacion explicita: datos exactos y producto sin publicar', flush=True)
        rows = [{'source_row': 1, 'name': 'cable usb qa', 'description': 'cable ficticio para pruebas',
                 'category': 'accesorios', 'price': '18000', 'stock': '4'}]
        prepared, mode = prepare_product_proposal(rows, provider)
        assert mode == 'groq' and prepared[0]['price'] == '18000' and prepared[0]['stock'] == '4'
        print('PASS importacion real conserva precio y cantidad', flush=True)
    print('PASS base ficticia eliminada; base del taller no utilizada', flush=True)


if __name__ == '__main__':
    main()
