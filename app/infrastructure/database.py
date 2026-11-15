import sqlite3
import re
from flask import current_app, g


class DatabaseMigrationError(RuntimeError):
    """Existing data needs explicit repair before constraints can be installed."""


def normalize_inventory_key(value):
    return ' '.join(str(value or '').split()).casefold()


def connect_db(path=None):
    db = sqlite3.connect(path or current_app.config['DATABASE'], timeout=10)
    db.row_factory = sqlite3.Row
    db.create_function('normalize_inventory_key', 1, normalize_inventory_key, deterministic=True)
    db.execute('PRAGMA foreign_keys = ON')
    db.execute('PRAGMA busy_timeout = 10000')
    return db


def get_db():
    if 'db' not in g:
        g.db = connect_db()
    return g.db


def close_db(_error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def _check_legacy_integrity(db):
    tables = {row['name'] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'repairs' in tables:
        invalid = db.execute(
            "SELECT COUNT(*) FROM repairs r LEFT JOIN users u ON u.id=r.assigned_to "
            "WHERE r.assigned_to IS NULL OR u.id IS NULL OR u.role!='technician' OR u.active!=1"
        ).fetchone()[0]
        if invalid:
            raise DatabaseMigrationError(
                f'Hay {invalid} reparaciones sin técnico activo válido. Revisa sus asignaciones antes de migrar; no se cambió ningún registro.'
            )
    if 'products' in tables:
        duplicates = db.execute(
            'SELECT COUNT(*) FROM (SELECT 1 FROM products '
            'GROUP BY normalize_inventory_key(name), normalize_inventory_key(category) HAVING COUNT(*)>1)'
        ).fetchone()[0]
        if duplicates:
            raise DatabaseMigrationError(
                f'Hay {duplicates} grupos de productos duplicados por nombre y categoría. Revisa los registros antes de migrar; no se renombró ni eliminó ninguno.'
            )


def _migrate_repair_assignment(db, schema):
    columns = list(db.execute('PRAGMA table_info(repairs)'))
    if not columns or next(row['notnull'] for row in columns if row['name'] == 'assigned_to'):
        return
    names = 'id,tracking_code,device,issue,status,assigned_to,created_by,created_at,updated_at'
    if {row['name'] for row in columns} != set(names.split(',')):
        raise DatabaseMigrationError('El esquema existente de reparaciones requiere revisión manual antes de migrar.')
    dependent_sql = [row['sql'] for row in db.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name='repairs' AND type IN ('index','trigger') AND sql IS NOT NULL"
    )]
    definition = re.search(r'CREATE TABLE IF NOT EXISTS repairs\s*\(.*?\);', schema, re.S).group(0)
    db.execute(definition.replace('IF NOT EXISTS repairs', 'repairs_required_assignment', 1))
    db.execute(f'INSERT INTO repairs_required_assignment({names}) SELECT {names} FROM repairs')
    db.execute('DROP TABLE repairs')
    db.execute('ALTER TABLE repairs_required_assignment RENAME TO repairs')
    for statement in dependent_sql:
        db.execute(statement)


def init_db():
    db = connect_db()
    try:
        with current_app.open_resource('infrastructure/schema.sql') as schema_file:
            schema = schema_file.read().decode('utf-8-sig')
        # Rebuild the parent table without cascading deletion into repair_history.
        db.execute('PRAGMA foreign_keys = OFF')
        db.execute('BEGIN IMMEDIATE')
        _check_legacy_integrity(db)
        _migrate_repair_assignment(db, schema)
        statement = ''
        for line in schema.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                db.execute(statement)
                statement = ''
        columns = {row['name'] for row in db.execute('PRAGMA table_info(products)')}
        if 'published' not in columns:
            db.execute('ALTER TABLE products ADD COLUMN published INTEGER NOT NULL DEFAULT 0 CHECK(published IN (0,1))')
        if 'proposal_id' not in {row['name'] for row in db.execute('PRAGMA table_info(ai_operations)')}:
            db.execute('ALTER TABLE ai_operations ADD COLUMN proposal_id TEXT REFERENCES ai_proposals(id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_ai_operations_proposal ON ai_operations(proposal_id)')
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise DatabaseMigrationError('Hay referencias inválidas en la base. No se aplicó la migración.')
        db.commit()
        db.execute('PRAGMA journal_mode = WAL')
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute('PRAGMA foreign_keys = ON')
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
