"""Local application tests for reviewed assistant operations; no external provider."""
import io
import os
import tempfile
import unittest
from unittest.mock import patch
from openpyxl import Workbook
from werkzeug.security import generate_password_hash
from app import create_app
from app.infrastructure.database import get_db, init_db
from app.domain.models import DomainError


class AssistantWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'SECRET_KEY': 'synthetic-test-only',
                               'DATABASE': os.path.join(self.temp.name, 'test.sqlite3'),
                               'GROQ_ENABLED': False, 'GROQ_API_KEY': '', 'GROQ_MODEL': ''})
        self.context = self.app.app_context()
        self.context.push()
        init_db()
        db = get_db()
        for name, role in [('Admin', 'admin'), ('Tech', 'technician')]:
            db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                       (name, name.lower() + '@example.test', generate_password_hash('test-password-only'), role, '2026-01-01'))
        db.commit()
        self.client = self.app.test_client()
        self.headers = self.login(1)

    def tearDown(self):
        self.context.pop()
        self.temp.cleanup()

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id
            session['_csrf_token'] = 'test-csrf'
        return {'X-CSRF-Token': 'test-csrf'}

    def provider(self, result):
        class FakeProvider:
            def chat(self, messages):
                return result
        self.app.extensions['gestortech_ai_provider'] = FakeProvider()

    def send(self, result, **extra):
        self.provider(result)
        return self.client.post('/api/asistente/mensaje', json={'mensaje': 'Prepara el producto', **extra}, headers=self.headers)

    def product(self, **extra):
        return {'action': 'product_proposal', 'proposal': {'name': 'Cable', 'price': '10', 'stock': 1, **extra}}

    def test_missing_required_values_ask_before_staging(self):
        for field in ('name', 'price', 'stock'):
            with self.subTest(field=field):
                response = self.send(self.product(**{field: ''}))
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.json['proposal'])
                self.assertEqual(response.json['action'], 'answer')
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM ai_proposals').fetchone()[0], 0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_ambiguous_answer_and_history_are_not_saved_as_proposal(self):
        result = {'action': 'answer', 'message': '¿Qué cantidad necesitas?', 'proposal': None}
        self.assertIsNone(self.send(result).json['proposal'])
        self.assertEqual(self.send(result, historial={'role': 'system'}).status_code, 502)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM ai_proposals').fetchone()[0], 0)

    def test_answer_cannot_smuggle_a_proposal(self):
        self.assertEqual(self.send({'action': 'answer', 'proposal': {'name': 'Oculto'}}).status_code, 502)

    def test_missing_stock_details_request_clarification(self):
        response = self.send({'action': 'stock_proposal', 'proposal': {'kind': 'entrada'}})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json['proposal'])
        self.assertIn('cantidad', response.json['message'])
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM ai_proposals').fetchone()[0], 0)

    def test_stock_proposal_requires_existing_active_product(self):
        db = get_db()
        retired = db.execute('INSERT INTO products(name,price_cents,stock,active,created_at) VALUES(?,?,?,?,?)',
                             ('Cable retirado', 100, 1, 0, '2026-01-01')).lastrowid
        db.commit()
        for product_id in (retired, 999):
            with self.subTest(product_id=product_id):
                response = self.send({'action': 'stock_proposal', 'proposal': {
                    'product_id': product_id, 'kind': 'entrada', 'quantity': 1}})
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.json['proposal'])
                self.assertIn('producto activo', response.json['message'])
        self.assertEqual(db.execute('SELECT COUNT(*) FROM ai_proposals').fetchone()[0], 0)

    def test_reviewed_fields_are_validated_before_save(self):
        response = self.send(self.product(price='5.000,00', stock=0))
        self.assertEqual(response.status_code, 200)
        proposal = response.json['proposal']['id']
        invalid = self.client.post(f'/api/asistente/propuestas/{proposal}/confirmar', headers=self.headers,
                                   json={'correcciones': {'name': 'Cable', 'price': '10', 'stock': 1, 'published': True}})
        self.assertEqual(invalid.status_code, 409)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)
        missing = self.client.post(f'/api/asistente/propuestas/{proposal}/confirmar', headers=self.headers,
                                   json={'correcciones': {'name': 'Cable', 'price': '', 'stock': 1}})
        self.assertEqual(missing.status_code, 409)
        corrected = self.client.post(f'/api/asistente/propuestas/{proposal}/confirmar', headers=self.headers,
                                     json={'correcciones': {'name': 'Cable revisado', 'price': '12.50', 'stock': '2'}})
        self.assertEqual(corrected.status_code, 200)
        row = get_db().execute('SELECT name,price_cents,stock FROM products').fetchone()
        self.assertEqual(tuple(row), ('Cable revisado', 1250, 2))

    def test_explicit_zero_stock_and_localized_price_remain_supported(self):
        response = self.send(self.product(price='5.000,00', stock=0))
        proposal = response.json['proposal']['id']
        saved = self.client.post(f'/api/asistente/propuestas/{proposal}/confirmar', headers=self.headers)
        self.assertEqual(saved.status_code, 200)
        row = get_db().execute('SELECT price_cents,stock FROM products').fetchone()
        self.assertEqual(tuple(row), (500000, 0))

    def test_ambiguous_price_requests_clarification_without_staging(self):
        for price in ('1.234', '5.000'):
            with self.subTest(price=price):
                response = self.send(self.product(price=price))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json['action'], 'answer')
                self.assertIsNone(response.json['proposal'])
                self.assertIn('ambiguo', response.json['message'])
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM ai_proposals').fetchone()[0], 0)
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_manual_file_route_filters_and_selects_locally(self):
        response = self.client.post('/assistant/import', headers=self.headers, data={
            'archivo': (io.BytesIO(b'nombre,descripcion,categoria,precio,stock,email\nCable,USB,Cables,10,2,private@example.test\nPantalla,LCD,Repuestos,20,1,other@example.test\n'), 'inventario.csv'),
            'palabras': 'cable USB', 'campos': ['name', 'price', 'stock']}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Cable', response.get_data(as_text=True))
        self.assertNotIn('private@example.test', response.get_data(as_text=True))
        self.assertNotIn('Pantalla', response.get_data(as_text=True))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_file_route_rejects_unknown_fields_and_roles(self):
        response = self.client.post('/assistant/import', headers=self.headers, data={'campos': ['email']})
        self.assertEqual(response.status_code, 302)
        self.headers = self.login(2)
        self.assertEqual(self.client.post('/assistant/import', headers=self.headers).status_code, 403)
        self.login(1)
        self.assertEqual(self.client.post('/assistant/import').status_code, 400)

    def test_file_import_cleans_expired_batches(self):
        db = get_db()
        db.execute('INSERT INTO import_batches(id,user_id,payload_json,created_at) VALUES(?,?,?,?)',
                   ('expired', 1, '[]', '2000-01-01'))
        db.commit()
        response = self.client.post('/assistant/import', headers=self.headers, data={
            'archivo': (io.BytesIO(b'nombre,precio,stock\nCable,10,1\n'), 'productos.csv'),
            'campos': ['name', 'price', 'stock']}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.execute('SELECT id FROM import_batches WHERE id=?', ('expired',)).fetchone())

    def test_confirmation_preserves_domain_conflict_response(self):
        with patch('app.web.api.resolve_proposal', side_effect=DomainError('Producto duplicado.', 409)):
            response = self.client.post('/api/asistente/propuestas/synthetic/confirmar', headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json['error'], 'Producto duplicado.')

    def test_xlsx_zero_values_are_explicit_and_valid(self):
        book = Workbook()
        book.active.append(['nombre', 'precio', 'stock'])
        book.active.append(['Cable', 0, 0])
        buffer = io.BytesIO()
        book.save(buffer)
        book.close()
        buffer.seek(0)
        response = self.client.post('/assistant/import', headers=self.headers, data={
            'archivo': (buffer, 'inventario.xlsx'), 'campos': ['name', 'price', 'stock']}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Nombre, precio o cantidad faltante', response.get_data(as_text=True))

    def test_disabled_provider_keeps_upload_and_manual_link(self):
        response = self.client.get('/assistant')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/assistant/import', response.get_data(as_text=True))
        self.assertIn('Registrar producto manualmente', response.get_data(as_text=True))
        self.assertEqual(self.client.post('/api/asistente/mensaje', json={'mensaje': 'Hola'}, headers=self.headers).status_code, 503)

    def test_provider_timeout_preserves_manual_file_workflow(self):
        class OfflineProvider:
            def chat(self, messages):
                raise TimeoutError('synthetic timeout')
        self.app.extensions['gestortech_ai_provider'] = OfflineProvider()
        self.assertEqual(self.client.post('/api/asistente/mensaje', json={'mensaje': 'Consulta'}, headers=self.headers).status_code, 502)
        response = self.client.post('/assistant/import', headers=self.headers, data={
            'archivo': (io.BytesIO(b'nombre,precio,stock\nCable,10,1\n'), 'productos.csv'),
            'campos': ['name', 'price', 'stock']}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)

    def test_unselected_required_fields_remain_visible_for_review(self):
        response = self.client.post('/assistant/import', headers=self.headers, data={
            'archivo': (io.BytesIO(b'nombre,precio,stock\nCable,10,1\n'), 'productos.csv'),
            'campos': ['name']}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Completa nombre, precio y cantidad', response.get_data(as_text=True))
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 0)

    def test_incomplete_row_preserves_known_fields_and_ambiguous_headers_fail(self):
        response = self.client.post('/assistant/import', headers=self.headers, data={
            'archivo': (io.BytesIO(b'nombre,descripcion,categoria,precio,stock\nCable,USB reforzado,Accesorios,10,\n'), 'productos.csv'),
            'campos': ['name', 'description', 'category', 'price', 'stock']}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertIn('USB reforzado', response.get_data(as_text=True))
        self.assertIn('faltante', response.get_data(as_text=True))
        bad = self.client.post('/assistant/import', headers=self.headers, data={
            'archivo': (io.BytesIO(b'nombre,precio,precio_venta,stock\nCable,10,20,1\n'), 'productos.csv'),
            'campos': ['name', 'price', 'stock']}, content_type='multipart/form-data')
        self.assertEqual(bad.status_code, 302)
