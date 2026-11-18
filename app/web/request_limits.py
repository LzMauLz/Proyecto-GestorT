"""Shared SQLite request budgets; client identifiers are keyed hashes."""
import hashlib
import hmac
import time

from flask import current_app, request
from werkzeug.exceptions import TooManyRequests

from app.infrastructure.database import connect_db


def enforce_request_limits():
    if request.endpoint == 'auth.login' and request.method == 'POST':
        scope, maximum = 'login', current_app.config['LOGIN_RATE_LIMIT']
    elif (request.endpoint == 'web.track' and request.method == 'POST') or request.endpoint == 'api.tracking':
        scope, maximum = 'tracking', current_app.config['TRACKING_RATE_LIMIT']
    else:
        return
    now = int(time.time())
    window = current_app.config['RATE_LIMIT_WINDOW']
    identity = (scope + ':' + (request.remote_addr or 'unknown')).encode('utf-8')
    secret = current_app.secret_key
    if isinstance(secret, str):
        secret = secret.encode('utf-8')
    bucket = hmac.new(secret, identity, hashlib.sha256).hexdigest()
    db = connect_db()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('CREATE TABLE IF NOT EXISTS request_limits (bucket TEXT PRIMARY KEY, hits INTEGER NOT NULL, reset_at INTEGER NOT NULL)')
            db.execute('DELETE FROM request_limits WHERE reset_at <= ?', (now,))
            row = db.execute('SELECT hits,reset_at FROM request_limits WHERE bucket=?', (bucket,)).fetchone()
            if row and row['hits'] >= maximum:
                raise TooManyRequests(description='Demasiados intentos. Espera antes de volver a intentarlo.', retry_after=max(1, row['reset_at'] - now))
            db.execute('INSERT INTO request_limits(bucket,hits,reset_at) VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET hits=hits+1', (bucket, now + window))
    finally:
        db.close()
