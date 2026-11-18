"""Operator-invoked coherent SQLite snapshots; never overwrite a destination."""
import sqlite3
from pathlib import Path
from app.infrastructure.database import normalize_inventory_key


def backup_database(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    if source == destination or not source.is_file():
        raise ValueError('El destino debe ser distinto de la base de datos de origen.')
    original = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
    try:
        with destination.open('xb'):
            identity = destination.stat()
        try:
            copy = sqlite3.connect(destination)
            copy.create_function('normalize_inventory_key', 1, normalize_inventory_key, deterministic=True)
            try:
                original.backup(copy)
                if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise sqlite3.DatabaseError('La copia no supera la comprobación de integridad.')
            finally:
                copy.close()
        except Exception:
            if destination.exists() and destination.stat().st_ino == identity.st_ino:
                destination.unlink()
            raise
    finally:
        original.close()
    return destination
