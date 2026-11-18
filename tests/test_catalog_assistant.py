"""Real Flask/SQLite checks of catalog handoff; provider responses are synthetic."""
import os
import tempfile
import unittest

from app import create_app
from app.infrastructure.database import get_db, init_db


class CatalogAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'synthetic-test-only',
                               'DATABASE': os.path.join(self.temp.name, 'catalog.sqlite3'),
                               'GROQ_ENABLED': False, 'GROQ_API_KEY': '', 'GROQ_MODEL': ''})
        self.context = self.app.app_context()
        self.context.push()
        init_db()
        db = get_db()
        db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                   ('Admin ficticio', 'admin@example.test', 'synthetic-unused', 'admin', '2026-01-01'))
        db.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['_csrf_token'] = 'test-csrf'
        self.headers = {'X-CSRF-Token': 'test-csrf'}

    def tearDown(self):
        self.context.pop()
        self.temp.cleanup()

    def propose(self, product, message='Prepara una ficha de catálogo'):
        class FakeProvider:
            def chat(self, messages):
                return {'action': 'product_proposal', 'proposal': product}
        self.app.extensions['gestortech_ai_provider'] = FakeProvider()
        return self.client.post('/api/asistente/mensaje', json={'mensaje': message}, headers=self.headers)

    def test_catalog_text_without_quantity_asks_before_staging(self):
        response = self.propose({'name': 'Cable', 'description': 'USB-C reforzado', 'price': '18000'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json['proposal'])
        self.assertIn('cantidad inicial 0', response.json['message'])
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM ai_proposals').fetchone()[0], 0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_explicit_zero_acceptance_returns_product_for_image_handoff(self):
        response = self.propose({'name': 'Cable', 'description': 'USB-C reforzado', 'price': '18000', 'stock': 0},
                                'Confirmo cantidad inicial 0 para la ficha del cable')
        proposal_id = response.json['proposal']['id']
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)
        confirmed = self.client.post(f'/api/asistente/propuestas/{proposal_id}/confirmar', headers=self.headers)
        self.assertEqual(confirmed.status_code, 200)
        product_id = confirmed.json['product_id']
        self.assertEqual(confirmed.json['product_ids'], [product_id])
        row = get_db().execute('SELECT name,description,price_cents,stock,published FROM products WHERE id=?', (product_id,)).fetchone()
        self.assertEqual(tuple(row), ('Cable', 'USB-C reforzado', 1800000, 0, 0))

    def test_cancelled_catalog_proposal_creates_no_product_or_image_handoff(self):
        response = self.propose({'name': 'Cable', 'description': 'USB-C', 'price': '10', 'stock': 1})
        proposal_id = response.json['proposal']['id']
        cancelled = self.client.post(f'/api/asistente/propuestas/{proposal_id}/cancelar', headers=self.headers)
        self.assertEqual(cancelled.status_code, 200)
        self.assertNotIn('product_id', cancelled.json)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_batch_confirmation_returns_each_unpublished_product(self):
        response = self.propose({'products': [
            {'name': 'Cable', 'description': 'USB-C', 'price': '10', 'stock': 1},
            {'name': 'Base', 'description': 'Base portátil', 'price': '20', 'stock': 0},
        ]})
        proposal_id = response.json['proposal']['id']
        confirmed = self.client.post(f'/api/asistente/propuestas/{proposal_id}/confirmar', headers=self.headers)
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(len(set(confirmed.json['product_ids'])), 2)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products WHERE published=1').fetchone()[0], 0)

    def test_provider_cannot_add_media_or_publication_fields(self):
        response = self.propose({'name': 'Cable', 'price': '10', 'stock': 1, 'image_url': 'https://example.test/image.png', 'published': True})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_provider_cannot_use_inventory_cent_field_as_product_price(self):
        response = self.propose({'name': 'Cable', 'price_cents': 2500000, 'stock': 2})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM ai_proposals').fetchone()[0], 0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)
