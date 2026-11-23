import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app import create_app
from app.application.services import create_product, create_repair, update_product, update_repair_status
from app.domain.models import DomainError
from app.infrastructure.database import DatabaseMigrationError, connect_db, get_db, init_db


def make_test_app(path):
    return create_app({'TESTING': True, 'SECRET_KEY': 'synthetic-integrity-test',
                       'DATABASE': path, 'GROQ_ENABLED': False, 'GROQ_API_KEY': '', 'GROQ_MODEL': ''})


def seed_users(db):
    db.executemany(
        'INSERT INTO users(id,name,email,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?,?)',
        [(1, 'Admin', 'admin@example.test', 'unused-test-hash', 'admin', 1, '2026-01-01'),
         (2, 'Tech', 'tech@example.test', 'unused-test-hash', 'technician', 1, '2026-01-01'),
         (3, 'Inactive', 'inactive@example.test', 'unused-test-hash', 'technician', 0, '2026-01-01')],
    )
    db.commit()


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, 'integrity.sqlite3')
        self.app = make_test_app(self.path)
        self.context = self.app.app_context()
        self.context.push()
        init_db()
        seed_users(get_db())

    def tearDown(self):
        self.context.pop()
        self.temp.cleanup()

    def product(self, name='Cable USB', category='Accesorios'):
        return create_product(get_db(), {'name': name, 'category': category, 'price': '100', 'stock': 0, 'user_id': 1})

    def test_administrador_necesita_tecnico_activo_valido(self):
        for assigned in (None, '', 0, True, 1, 3, 999, 2**64):
            with self.subTest(assigned=assigned), self.assertRaises(DomainError):
                create_repair(get_db(), {'device': 'Equipo', 'issue': 'Falla', 'assigned_to': assigned}, 1, 'admin')
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM repairs').fetchone()[0], 0)
        repair_id, _ = create_repair(get_db(), {'device': 'Equipo', 'issue': 'Falla', 'assigned_to': 2}, 1, 'admin')
        self.assertEqual(get_db().execute('SELECT assigned_to FROM repairs WHERE id=?', (repair_id,)).fetchone()[0], 2)

    def test_reasignacion_rechaza_ids_malformados_sin_cambiar_estado(self):
        db = get_db()
        repair_id, _ = create_repair(db, {'device': 'Equipo', 'issue': 'Falla', 'assigned_to': 2}, 1, 'admin')
        for assigned in (True, [], {}, 2**64):
            with self.subTest(assigned=assigned), self.assertRaises(DomainError):
                update_repair_status(db, repair_id, 1, 'admin', 'En diagnóstico', assigned_to=assigned)
        self.assertEqual(db.execute('SELECT status FROM repairs WHERE id=?', (repair_id,)).fetchone()[0], 'Recibido')

    def test_tecnico_se_autoasigna_ignorando_asignacion_ajena(self):
        repair_id, _ = create_repair(get_db(), {'device': 'Equipo', 'issue': 'Falla', 'assigned_to': 1}, 2, 'technician')
        self.assertEqual(get_db().execute('SELECT assigned_to FROM repairs WHERE id=?', (repair_id,)).fetchone()[0], 2)

    def test_persistencia_rechaza_asignaciones_invalidas(self):
        db = get_db()
        self.assertEqual(next(r['notnull'] for r in db.execute('PRAGMA table_info(repairs)') if r['name'] == 'assigned_to'), 1)
        for assigned in (None, 1, 3, 999):
            with self.subTest(assigned=assigned), self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO repairs(tracking_code,device,issue,status,assigned_to,created_by,created_at,updated_at) VALUES('GT-DIRECT','Equipo','Falla','Recibido',?,1,'2026-01-01','2026-01-01')", (assigned,))
            db.rollback()
        repair_id, _ = create_repair(db, {'device': 'Equipo', 'issue': 'Falla', 'assigned_to': 2}, 1, 'admin')
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute('UPDATE repairs SET assigned_to=NULL WHERE id=?', (repair_id,))
        db.rollback()
        self.assertEqual(db.execute('SELECT assigned_to FROM repairs WHERE id=?', (repair_id,)).fetchone()[0], 2)

    def test_nombre_y_categoria_se_normalizan_para_unicidad(self):
        self.product('  Cable   USB ', '  ACCESORIOS  USB ')
        with self.assertRaises(DomainError) as error:
            self.product('cable usb', 'accesorios usb')
        self.assertEqual(error.exception.status_code, 409)
        self.product('cable usb', 'Otra categoría')
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 2)

    def test_edicion_propia_permitida_y_colision_rechazada(self):
        cable = self.product()
        hub = self.product('Hub')
        update_product(get_db(), cable, {'name': ' CABLE   usb ', 'category': 'accesorios', 'price': '150'})
        with self.assertRaises(DomainError):
            update_product(get_db(), hub, {'name': 'cable usb', 'category': 'ACCESORIOS', 'price': '150'})
        self.assertEqual(get_db().execute('SELECT name FROM products WHERE id=?', (hub,)).fetchone()[0], 'Hub')

    def test_categoria_vacia_y_productos_retirados_siguen_siendo_unicos(self):
        product_id = self.product('Cable', '')
        get_db().execute('UPDATE products SET active=0 WHERE id=?', (product_id,))
        get_db().commit()
        with self.assertRaises(DomainError):
            self.product(' CABLE ', '   ')

    def test_indice_impide_duplicados_desde_sql_directo(self):
        self.product()
        with self.assertRaises(sqlite3.IntegrityError):
            get_db().execute("INSERT INTO products(name,category,price_cents,stock,created_at) VALUES(' CABLE  USB ',' accesorios ',100,0,'2026-01-01')")
        get_db().rollback()
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)

    def test_solicitudes_concurrentes_crean_un_solo_producto(self):
        start = Barrier(2)

        def insert(name):
            db = connect_db(self.path)
            try:
                start.wait(timeout=5)
                try:
                    create_product(db, {'name': name, 'category': 'Cables', 'price': '1', 'stock': 0, 'user_id': 1})
                    return 'created'
                except DomainError as error:
                    return error.status_code
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(insert, ['Cable USB', ' cable  usb ']))
        self.assertCountEqual(results, ['created', 409])
        self.assertEqual(get_db().execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)

    def test_api_rechaza_asignacion_ausente_y_duplicado(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = 1
            session['_csrf_token'] = 'synthetic-csrf'
        headers = {'X-CSRF-Token': 'synthetic-csrf'}
        response = client.post('/api/reparaciones', json={'equipo': 'Equipo', 'descripcion_problema': 'Falla'}, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.get_json())
        response = client.post('/api/reparaciones', json={'equipo': 'Equipo', 'descripcion_problema': 'Falla', 'id_tecnico': 2}, headers=headers)
        self.assertEqual(response.status_code, 201)
        self.product()
        response = client.post('/api/productos', json={'nombre': ' cable USB ', 'categoria': 'ACCESORIOS', 'precio': '100'}, headers=headers)
        self.assertEqual(response.status_code, 409)
        self.assertIn('misma categoría', response.get_json()['error'])

    def test_ediciones_concurrentes_no_producen_duplicados(self):
        ids = [self.product('Cable A'), self.product('Cable B')]
        start = Barrier(2)

        def edit(product_id):
            db = connect_db(self.path)
            try:
                start.wait(timeout=5)
                try:
                    update_product(db, product_id, {'name': 'Cable final', 'category': 'Accesorios', 'price': '100'})
                    return 'updated'
                except DomainError as error:
                    return error.status_code
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(edit, ids))
        self.assertCountEqual(results, ['updated', 409])
        self.assertEqual(get_db().execute("SELECT COUNT(*) FROM products WHERE name='Cable final'").fetchone()[0], 1)

    def test_formulario_exige_tecnico_y_explicacion_si_no_hay_activos(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['user_id'] = 1
        html = client.get('/repairs/new').get_data(as_text=True)
        self.assertIn('name="assigned_to" required', html)
        self.assertNotIn('Sin asignar', html)
        get_db().execute('UPDATE users SET active=0 WHERE id=2')
        get_db().commit()
        html = client.get('/repairs/new').get_data(as_text=True)
        self.assertIn('Necesitas un técnico activo', html)
        self.assertIn('type="submit" disabled', html)


LEGACY_SCHEMA = """
CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',category TEXT NOT NULL DEFAULT '',price_cents INTEGER NOT NULL,stock INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE repairs(id INTEGER PRIMARY KEY,tracking_code TEXT NOT NULL UNIQUE,device TEXT NOT NULL,issue TEXT NOT NULL,status TEXT NOT NULL,assigned_to INTEGER REFERENCES users(id),created_by INTEGER NOT NULL REFERENCES users(id),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE repair_history(id INTEGER PRIMARY KEY,repair_id INTEGER NOT NULL REFERENCES repairs(id) ON DELETE CASCADE,user_id INTEGER NOT NULL REFERENCES users(id),status TEXT NOT NULL,internal_note TEXT NOT NULL DEFAULT '',public_note TEXT NOT NULL DEFAULT '',public_visible INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
CREATE INDEX legacy_device_idx ON repairs(device);
"""


class LegacyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = make_test_app(os.path.join(self.temp.name, 'legacy.sqlite3'))
        self.context = self.app.app_context()
        self.context.push()
        self.db = get_db()
        self.db.executescript(LEGACY_SCHEMA)
        seed_users(self.db)

    def tearDown(self):
        self.context.pop()
        self.temp.cleanup()

    def legacy_repair(self, assigned=2):
        self.db.execute("INSERT INTO repairs VALUES(7,'GT-LEGACY','Equipo ficticio','Falla ficticia','Recibido',?,1,'2026-01-01','2026-01-01')", (assigned,))
        self.db.execute("INSERT INTO repair_history VALUES(8,7,1,'Recibido','Nota sintética','Recibida',1,'2026-01-01')")
        self.db.commit()

    def test_migracion_preserva_ids_historial_indices_y_es_idempotente(self):
        self.legacy_repair()
        before = [tuple(row) for row in self.db.execute('SELECT * FROM repair_history')]
        init_db()
        init_db()
        self.assertEqual([tuple(row) for row in self.db.execute('SELECT * FROM repair_history')], before)
        self.assertEqual(self.db.execute('SELECT id FROM repairs').fetchone()[0], 7)
        contact = self.db.execute('SELECT customer_name, customer_phone, customer_email FROM repairs WHERE id=7').fetchone()
        self.assertEqual(tuple(contact), ('', '', ''))
        self.assertEqual(next(r['notnull'] for r in self.db.execute('PRAGMA table_info(repairs)') if r['name'] == 'assigned_to'), 1)
        self.assertIsNotNone(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='legacy_device_idx'").fetchone())
        self.assertIsNone(self.db.execute('PRAGMA foreign_key_check').fetchone())
        self.assertEqual(self.db.execute('PRAGMA foreign_keys').fetchone()[0], 1)

    def test_migracion_aborta_sin_reasignar_ordenes_nulas(self):
        self.legacy_repair(None)
        before = list(self.db.iterdump())
        with self.assertRaises(DatabaseMigrationError):
            init_db()
        self.assertEqual(list(self.db.iterdump()), before)

    def test_migracion_aborta_sin_tocar_tecnico_inactivo(self):
        self.legacy_repair(3)
        before = list(self.db.iterdump())
        with self.assertRaises(DatabaseMigrationError):
            init_db()
        self.assertEqual(list(self.db.iterdump()), before)

    def test_migracion_aborta_sin_renombrar_duplicados(self):
        self.db.executemany("INSERT INTO products(name,category,price_cents,created_at) VALUES(?,?,100,'2026-01-01')", [('Cable USB', 'Accesorios'), (' cable  usb ', ' ACCESORIOS ')])
        self.db.commit()
        before = list(self.db.iterdump())
        with self.assertRaises(DatabaseMigrationError):
            init_db()
        self.assertEqual(list(self.db.iterdump()), before)

    def test_fallo_despues_de_reconstruir_revierte_esquema_y_datos(self):
        self.legacy_repair()
        self.db.execute('PRAGMA foreign_keys = OFF')
        self.db.execute('UPDATE repair_history SET user_id=999')
        self.db.commit()
        self.db.execute('PRAGMA foreign_keys = ON')
        before = list(self.db.iterdump())
        with self.assertRaises(DatabaseMigrationError):
            init_db()
        self.assertEqual(list(self.db.iterdump()), before)
