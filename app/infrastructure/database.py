import sqlite3
from flask import current_app, g


def connect_db(path=None):
    db = sqlite3.connect(path or current_app.config['DATABASE'], timeout=10)
    db.row_factory = sqlite3.Row
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


def init_db():
    db = connect_db()
    try:
        with current_app.open_resource('infrastructure/schema.sql') as schema_file:
            schema = schema_file.read().decode('utf-8-sig')
        db.executescript(schema)
        db.commit()
    finally:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)
