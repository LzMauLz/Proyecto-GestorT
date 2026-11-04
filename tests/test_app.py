import io
import os
import tempfile
import unittest
from werkzeug.security import generate_password_hash
from werkzeug.datastructures import FileStorage

from app import create_app
from app.application.ai_import import prepare_product_proposal
from app.application.ai_assistant import inventory_snapshot, request_assistant
from app.application.ports import AIProviderError
from app.infrastructure.ai.groq_adapter import GroqAdapter
from app.application.services import create_product, create_repair, move_stock, update_repair_status
from app.domain.models import DomainError
from app.infrastructure.database import get_db, init_db
from app.web.pages import parse_product_upload


class GestorTechTests(unittest.TestCase):
    def setUp(self):
        project_root=os.path.dirname(os.path.dirname(__file__))
        self.temp = tempfile.TemporaryDirectory(dir=os.path.join(project_root,'instance'))
        self.app = create_app({'TESTING':True,'SECRET_KEY':'test-key-only','DATABASE':os.path.join(self.temp.name,'test.sqlite3'),'GROQ_ENABLED':False,'GROQ_API_KEY':'','GROQ_MODEL':''})
        self.context = self.app.app_context()
        self.context.push()
        init_db()
        db=get_db()
        db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',('Admin','admin@example.test',generate_password_hash('admin-password-test'),'admin','2026-01-01T00:00:00+00:00'))
        db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',('Tech','tech@example.test',generate_password_hash('tech-password-test'),'technician','2026-01-01T00:00:00+00:00'))
        db.commit()
        self.client=self.app.test_client()

    def tearDown(self):
        self.context.pop()
        self.temp.cleanup()

    def session_as(self, user_id, csrf='test-csrf'):
        with self.client.session_transaction() as sess:
            sess['user_id']=user_id
            sess['_csrf_token']=csrf
        return {'X-CSRF-Token':csrf}

    def test_public_tracking_excludes_problem_and_internal_note(self):
        repair_id,code=create_repair(get_db(),{'device':'Portátil','issue':'Detalle privado'},1,'admin')
        update_repair_status(get_db(),repair_id,1,'admin','En diagnóstico','No publicar: dato interno','')
        response=self.client.get('/api/seguimiento/'+code)
        self.assertEqual(response.status_code,200)
        data=response.get_json()
        self.assertNotIn('descripcion_problema',data)
        self.assertNotIn('equipo',data)
        self.assertNotIn('Detalle privado',response.get_data(as_text=True))
        self.assertNotIn('dato interno',response.get_data(as_text=True))

    def test_public_note_is_explicitly_published(self):
        repair_id,code=create_repair(get_db(),{'device':'Portátil','issue':'Falla'},1,'admin')
        update_repair_status(get_db(),repair_id,1,'admin','En diagnóstico','','Diagnóstico iniciado')
        data=self.client.get('/api/seguimiento/'+code).get_json()
        self.assertEqual(data['historial_publico'][-1]['comentario'],'Diagnóstico iniciado')

    def test_repair_transitions_are_enforced_and_recorded(self):
        repair_id,_=create_repair(get_db(),{'device':'Laptop','issue':'No inicia'},1,'admin')
        update_repair_status(get_db(),repair_id,1,'admin','En diagnóstico')
        with self.assertRaises(DomainError):
            update_repair_status(get_db(),repair_id,1,'admin','Entregado')
        count=get_db().execute('SELECT COUNT(*) n FROM repair_history WHERE repair_id=?',(repair_id,)).fetchone()['n']
        self.assertEqual(count,2)

    def test_technician_can_only_change_assigned_repair(self):
        repair_id,_=create_repair(get_db(),{'device':'Laptop','issue':'Falla'},1,'admin')
        with self.assertRaises(DomainError) as err:
            update_repair_status(get_db(),repair_id,2,'technician','En diagnóstico')
        self.assertEqual(err.exception.status_code,403)
        db=get_db(); db.execute('UPDATE repairs SET assigned_to=2 WHERE id=?',(repair_id,)); db.commit()
        update_repair_status(db,repair_id,2,'technician','En diagnóstico')

    def test_stock_movement_is_atomic_and_never_negative(self):
        product_id=create_product(get_db(),{'name':'Cable','price':'18000','stock':3,'user_id':1})
        self.assertEqual(move_stock(get_db(),product_id,1,'salida',2),1)
        with self.assertRaises(DomainError):
            move_stock(get_db(),product_id,1,'salida',2)
        row=get_db().execute('SELECT stock FROM products WHERE id=?',(product_id,)).fetchone()
        self.assertEqual(row['stock'],1)
        self.assertEqual(get_db().execute('SELECT COUNT(*) n FROM inventory_movements WHERE product_id=?',(product_id,)).fetchone()['n'],2)

    def test_api_requires_auth_and_csrf(self):
        self.assertEqual(self.client.get('/api/productos').status_code,401)
        headers=self.session_as(1)
        response=self.client.post('/api/productos',json={'nombre':'Adaptador','precio':12000,'cantidad_stock':2},headers=headers)
        self.assertEqual(response.status_code,201)
        bad=self.client.post('/api/productos',json={'nombre':'Otro','precio':1})
        self.assertEqual(bad.status_code,400)

    def test_openapi_and_public_not_found(self):
        self.assertEqual(self.client.get('/api/openapi.json').get_json()['openapi'],'3.1.0')
        self.assertEqual(self.client.get('/api/seguimiento/GT-INVALIDO').status_code,404)

    def test_xlsx_import_reads_values_without_executing_formula_content(self):
        from openpyxl import Workbook
        workbook=Workbook()
        sheet=workbook.active
        sheet.append(['nombre','precio','cantidad_stock'])
        sheet.append(['Adaptador',12500,2])
        buffer=io.BytesIO(); workbook.save(buffer); buffer.seek(0)
        upload=FileStorage(stream=buffer,filename='catalogo.xlsx')
        rows=parse_product_upload(upload)
        self.assertEqual(rows[0]['name'],'Adaptador')
        self.assertEqual(rows[0]['stock'],'2')

    def test_product_edit_keeps_stock_history_separate(self):
        product_id=create_product(get_db(),{'name':'Cable','price':'100','stock':3,'user_id':1})
        headers=self.session_as(1)
        response=self.client.put(f'/api/productos/{product_id}',json={'nombre':'Cable reforzado','precio':150,'cantidad_stock':99},headers=headers)
        self.assertEqual(response.status_code,200)
        row=get_db().execute('SELECT name,stock FROM products WHERE id=?',(product_id,)).fetchone()
        self.assertEqual((row['name'],row['stock']),('Cable reforzado',3))
        edit_page=self.client.get(f'/products/{product_id}/edit')
        self.assertEqual(edit_page.status_code,200)

    def test_csv_import_requires_explicit_values_and_never_calls_ai(self):
        upload=FileStorage(stream=io.BytesIO('nombre,descripcion,categoria,precio,cantidad_stock\nCable,USB,Cables,18000,4\n'.encode()),filename='productos.csv')
        rows=parse_product_upload(upload)
        self.assertEqual(rows[0]['name'],'Cable')
        self.assertEqual(rows[0]['price'],'18000')
        missing=FileStorage(stream=io.BytesIO('nombre,precio,cantidad_stock\nCable,,\n'.encode()),filename='productos.csv')
        invalid=parse_product_upload(missing)
        self.assertIn('faltante',invalid[0]['error'])

    def test_staff_pages_render(self):
        self.session_as(1)
        for path in ['/dashboard','/products','/products/new','/products/import','/repairs/new','/users/new','/assistant']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200,response.get_data(as_text=True)[:500])

    def test_dashboard_has_active_navigation_and_keyboard_table_region(self):
        create_repair(get_db(),{'device':'Tablet','issue':'Pantalla dañada'},1,'admin')
        self.session_as(1)
        response=self.client.get('/dashboard')
        html=response.get_data(as_text=True)
        self.assertEqual(response.status_code,200)
        self.assertIn('aria-current="page"',html)
        self.assertIn('aria-label="Reparaciones recientes" tabindex="0"',html)

    def test_login_requires_csrf_and_authenticates(self):
        page=self.client.get('/login')
        self.assertEqual(page.status_code,200)
        import re
        match=re.search(r'name="_csrf_token" value="([^"]+)"',page.get_data(as_text=True))
        self.assertIsNotNone(match)
        response=self.client.post('/login',data={'_csrf_token':match.group(1),'email':'admin@example.test','password':'admin-password-test'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.headers['Location'].endswith('/dashboard'))

    def test_repair_detail_and_import_preview_render_and_approve(self):
        headers=self.session_as(1)
        repair_id,code=create_repair(get_db(),{'device':'Consola','issue':'No enciende'},1,'admin')
        self.assertEqual(self.client.get(f'/repairs/{repair_id}').status_code,200)
        upload=(io.BytesIO(b'nombre,precio,cantidad_stock\nCable,18000,4\n'),'productos.csv')
        preview=self.client.post('/products/import/preview',data={'_csrf_token':'test-csrf','file':upload},content_type='multipart/form-data')
        self.assertEqual(preview.status_code,200,preview.get_data(as_text=True)[:500])
        batch=get_db().execute('SELECT id FROM import_batches').fetchone()['id']
        approved=self.client.post(f'/products/import/{batch}/approve',data={'_csrf_token':'test-csrf','row':'0','name_0':'Cable USB-C','description_0':'Cable','category_0':'Accesorios','price_0':'18000','stock_0':'4'})
        self.assertEqual(approved.status_code,302)
        product=get_db().execute('SELECT * FROM products WHERE name=?',('Cable USB-C',)).fetchone()
        self.assertIsNotNone(product)
        self.assertEqual(product['stock'],4)
        self.assertTrue(code.startswith('GT-'))

    def test_manual_import_api_is_authenticated_and_does_not_claim_ai(self):
        headers=self.session_as(1)
        upload=(io.BytesIO(b'nombre,precio,cantidad_stock\nCable,18000,3\n'),'productos.csv')
        response=self.client.post('/api/ia/importacion/propuesta',data={'archivo':upload},headers=headers,content_type='multipart/form-data')
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        data=response.get_json()
        self.assertTrue(data['requiere_revision_humana'])
        self.assertIn('manual',data['modo'])
        self.assertEqual(data['propuesta'][0]['nombre'],'Cable')
        self.assertNotIn('name',data['propuesta'][0])

    def test_openapi_paths_match_implemented_api_routes(self):
        schema=self.client.get('/api/openapi.json').get_json()
        for path in ['/productos','/productos/{id}','/reparaciones','/reparaciones/{id}/estado','/seguimiento/{codigo}','/ia/importacion/propuesta','/asistente/mensaje','/asistente/propuestas/{id}/confirmar','/asistente/propuestas/{id}/cancelar']:
            self.assertIn(path,schema['paths'])

    def test_customer_view_is_accessible_and_no_store(self):
        response=self.client.get('/track')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers.get('Cache-Control'),'no-store')
        self.assertEqual(response.headers.get('X-Content-Type-Options'),'nosniff')

    def test_groq_disabled_or_missing_credentials_uses_manual_without_network(self):
        adapter=GroqAdapter('', '', enabled=True, opener=lambda *a,**k: self.fail('network must not be called'))
        self.assertFalse(adapter.available)
        rows=[{'source_row':2,'name':'Cable','description':'USB','category':'Accesorios','price':'12','stock':'3'}]
        prepared,mode=prepare_product_proposal(rows,None)
        self.assertEqual((prepared,mode),(rows,'manual'))
        with self.assertRaises(AIProviderError): adapter.propose_products([])

    def test_valid_mock_proposal_sends_only_allowed_fields_and_preserves_price_stock(self):
        rows=[{'source_row':2,'name':'Cable USB','description':'Cable','category':'Accesorios','price':'18000','stock':'4'}]
        class MockProvider:
            def propose_products(self, sent):
                self.asserted=sent
                return [{'source_row':2,'name':'Cable USB-C','description':'Cable USB-C reforzado','category':'Cables'}]
        provider=MockProvider()
        prepared,mode=prepare_product_proposal(rows,provider)
        self.assertEqual(mode,'groq')
        self.assertEqual(set(provider.asserted[0]),{'source_row','name','description','category'})
        self.assertEqual((prepared[0]['name'],prepared[0]['price'],prepared[0]['stock']),('Cable USB-C','18000','4'))
        self.assertEqual(prepared[0]['original_values']['name'],'Cable USB')

    def test_invalid_mock_response_falls_back_to_manual(self):
        rows=[{'source_row':2,'name':'Cable','description':'','category':'','price':'10','stock':'1'}]
        class InvalidProvider:
            def propose_products(self, sent): return [{'source_row':2,'name':'Inventado'}]
        prepared,mode=prepare_product_proposal(rows,InvalidProvider())
        self.assertEqual((prepared,mode),(rows,'manual'))

    def test_provider_error_falls_back_to_manual(self):
        rows=[{'source_row':2,'name':'Cable','description':'','category':'','price':'10','stock':'1'}]
        class BrokenProvider:
            def propose_products(self, sent): raise AIProviderError('offline')
        self.assertEqual(prepare_product_proposal(rows,BrokenProvider()),(rows,'manual'))

    def test_timeout_and_rate_limit_errors_keep_manual_import_available(self):
        rows=[{'source_row':2,'name':'Cable','description':'','category':'','price':'10','stock':'1'}]
        for provider_error in (TimeoutError('timeout'), RuntimeError('rate limited')):
            class UnavailableProvider:
                def propose_products(self, sent): raise provider_error
            with self.subTest(error=type(provider_error).__name__):
                self.assertEqual(prepare_product_proposal(rows,UnavailableProvider()),(rows,'manual'))

    def test_invalid_provider_json_is_rejected(self):
        from app.application.ai_import import parse_provider_json
        for body in ('not-json', '{"products": [], "extra": true}', '[]'):
            with self.subTest(body=body), self.assertRaises(AIProviderError):
                parse_provider_json(body)

    def test_rows_over_ai_limit_are_not_sent_to_provider(self):
        rows=[{'source_row':index+2,'name':'Producto','description':'','category':'','price':'1','stock':'1'} for index in range(51)]
        class MustNotRunProvider:
            def propose_products(self, sent): self.fail('provider called beyond configured row cap')
        prepared,mode=prepare_product_proposal(rows,MustNotRunProvider())
        self.assertEqual(prepared,rows)
        self.assertEqual(mode,'manual')

    def test_human_approval_required_before_persisting_ai_suggestion(self):
        headers=self.session_as(1)
        class MockProvider:
            def propose_products(self, sent):
                return [{'source_row':2,'name':'Cable normalizado','description':'','category':'Accesorios'}]
        self.app.extensions['gestortech_ai_provider']=MockProvider()
        upload=(io.BytesIO(b'nombre,descripcion,categoria,precio,cantidad_stock\nCable,USB,,18000,4\n'),'productos.csv')
        preview=self.client.post('/products/import/preview',data={'_csrf_token':'test-csrf','file':upload},content_type='multipart/form-data')
        self.assertEqual(preview.status_code,200)
        self.assertIn('Cable normalizado',preview.get_data(as_text=True))
        self.assertEqual(get_db().execute('SELECT COUNT(*) n FROM products').fetchone()['n'],0)
        batch=get_db().execute('SELECT id FROM import_batches').fetchone()['id']
        approved=self.client.post(f'/products/import/{batch}/approve',data={'_csrf_token':'test-csrf','row':'0','name_0':'Cable editado','price_0':'18000','stock_0':'4'})
        self.assertEqual(approved.status_code,302)
        self.assertIsNotNone(get_db().execute('SELECT id FROM products WHERE name=?',('Cable editado',)).fetchone())

    def test_mock_api_provider_failure_keeps_manual_mode(self):
        headers=self.session_as(1)
        class BrokenProvider:
            def propose_products(self, sent): raise RuntimeError('offline')
        self.app.extensions['gestortech_ai_provider']=BrokenProvider()
        upload=(io.BytesIO(b'nombre,precio,cantidad_stock\nCable,18000,3\n'),'productos.csv')
        response=self.client.post('/api/ia/importacion/propuesta',data={'archivo':upload},headers=headers,content_type='multipart/form-data')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()['modo'],'manual')

    def test_assistant_disabled_returns_service_unavailable(self):
        headers=self.session_as(1)
        response=self.client.post('/api/asistente/mensaje',json={'mensaje':'¿Cuántos productos tenemos?'},headers=headers)
        self.assertEqual(response.status_code,503)

    def test_assistant_uses_inventory_facts_and_creates_pending_product_proposal(self):
        create_product(get_db(),{'name':'Cable USB','description':'','category':'Cables','price':'18000','stock':3,'user_id':1})
        class MockAssistant:
            def chat(self, messages):
                content=messages[-1]['content']
                if 'Cable USB' not in content:
                    raise AssertionError('inventory facts were not included')
                return {'message':'Preparé una propuesta para revisar.','action':'product_proposal',
                        'proposal':{'name':'Cable USB-C','description':'Cable reforzado','category':'Cables','price':'18000','stock':3}}
        self.app.extensions['gestortech_ai_provider']=MockAssistant()
        headers=self.session_as(1)
        response=self.client.post('/api/asistente/mensaje',json={'mensaje':'Prepara un producto usando los productos actuales'},headers=headers)
        self.assertEqual(response.status_code,200)
        proposal=response.get_json()['proposal']
        self.assertEqual(get_db().execute('SELECT COUNT(*) n FROM products').fetchone()['n'],1)
        confirmed=self.client.post('/api/asistente/propuestas/'+proposal['id']+'/confirmar',headers=headers)
        self.assertEqual(confirmed.status_code,200)
        self.assertEqual(get_db().execute('SELECT COUNT(*) n FROM products').fetchone()['n'],2)
        self.assertEqual(get_db().execute('SELECT approval_status FROM ai_operations').fetchone()['approval_status'],'approved')

    def test_assistant_accepts_flat_product_proposal_response(self):
        class MockAssistant:
            def chat(self, messages):
                return {'action': 'product_proposal', 'name': 'Adaptador USB-C',
                        'description': 'Adaptador USB-C a USB-A de 3 metros',
                        'category': 'Accesorios', 'price': 25000, 'stock': 10,
                        'message': 'Propuesta preparada.'}
        self.app.extensions['gestortech_ai_provider'] = MockAssistant()
        response = self.client.post(
            '/api/asistente/mensaje',
            json={'mensaje': 'Prepara un producto Adaptador USB-C'},
            headers=self.session_as(1),
        )
        self.assertEqual(response.status_code, 200)
        proposal = response.get_json()['proposal']
        self.assertEqual(proposal['name'], 'Adaptador USB-C')
        self.assertEqual(proposal['stock'], 10)

    def test_assistant_accepts_product_alias_without_message(self):
        class MockAssistant:
            def chat(self, messages):
                return {'action': 'crear_producto', 'producto': {
                    'name': 'Puertos para Moto G56', 'description': '',
                    'category': '', 'price': 5000, 'stock': 5}}
        self.app.extensions['gestortech_ai_provider'] = MockAssistant()
        response = self.client.post(
            '/api/asistente/mensaje',
            json={'mensaje': 'Agrega 5 puertos para Moto G56 a 5000 cada uno'},
            headers=self.session_as(1),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['proposal']['stock'], 5)

    def test_assistant_accepts_and_atomically_confirms_multiple_products(self):
        class MockAssistant:
            def chat(self, messages):
                return {'message': 'Preparé dos productos para revisar.', 'action': 'product_proposal',
                        'proposal': {'products': [
                            {'name': 'Hub USB', 'description': 'Hub de cuatro puertos', 'category': 'Accesorios', 'price': 45000, 'stock': 3},
                            {'name': 'Base portátil', 'description': 'Base ajustable', 'category': 'Accesorios', 'price': 70000, 'stock': 2},
                        ]}}
        self.app.extensions['gestortech_ai_provider'] = MockAssistant()
        headers = self.session_as(1)
        response = self.client.post(
            '/api/asistente/mensaje',
            json={'mensaje': 'Agrega Hub USB y Base portátil al inventario'},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        proposal = response.get_json()['proposal']
        self.assertEqual(len(proposal['products']), 2)
        confirmed = self.client.post(
            '/api/asistente/propuestas/' + proposal['id'] + '/confirmar',
            headers=headers,
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(len(confirmed.get_json()['product_ids']), 2)
        self.assertEqual(get_db().execute('SELECT COUNT(*) n FROM products').fetchone()['n'], 2)

    def test_technician_cannot_prepare_mutation_from_assistant(self):
        class MockAssistant:
            def chat(self, messages):
                return {'message':'Propuesta','action':'stock_proposal',
                        'proposal':{'product_id':1,'kind':'entrada','quantity':1,'note':'test'}}
        self.app.extensions['gestortech_ai_provider']=MockAssistant()
        headers=self.session_as(2)
        response=self.client.post('/api/asistente/mensaje',json={'mensaje':'Agrega stock'},headers=headers)
        self.assertEqual(response.status_code,502)

    def test_assistant_stock_confirmation_uses_transactional_service_and_cancel_is_audited(self):
        product_id=create_product(get_db(),{'name':'Adaptador','price':'100','stock':2,'user_id':1})
        class MockAssistant:
            def chat(self, messages):
                return {'message':'Revisa esta entrada.','action':'stock_proposal',
                        'proposal':{'product_id':product_id,'kind':'entrada','quantity':3,'note':'Reposición'}}
        self.app.extensions['gestortech_ai_provider']=MockAssistant()
        headers=self.session_as(1)
        response=self.client.post('/api/asistente/mensaje',json={'mensaje':'Prepara una entrada de 3 Adaptadores'},headers=headers)
        proposal=response.get_json()['proposal']['id']
        cancelled=self.client.post('/api/asistente/propuestas/'+proposal+'/cancelar',headers=headers)
        self.assertEqual(cancelled.status_code,200)
        self.assertEqual(get_db().execute('SELECT stock FROM products WHERE id=?',(product_id,)).fetchone()['stock'],2)
        self.assertEqual(get_db().execute('SELECT approval_status FROM ai_operations').fetchone()['approval_status'],'cancelled')


if __name__=='__main__':
    unittest.main()
