"""Prepare Railway's persistent volume, then run Flask as the app user."""
import os
from pathlib import Path
import pwd
import subprocess
import sys


APP_USER = 'gestortech'
DEFAULT_VOLUME = Path('/app/instance')


def prepare_volume():
    volume = Path(os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', DEFAULT_VOLUME))
    volume.mkdir(parents=True, exist_ok=True)
    database = Path(os.environ.get('GESTORTECH_DATABASE', volume / 'gestortech.sqlite3'))
    database.parent.mkdir(parents=True, exist_ok=True)
    image_directory = Path(os.environ.get('PRODUCT_IMAGE_DIRECTORY', database.parent / 'product-images'))
    image_directory.mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        account = pwd.getpwnam(APP_USER)
        for directory in {volume, database.parent, image_directory}:
            os.chown(directory, account.pw_uid, account.pw_gid)
        for path in (database, Path(str(database) + '-wal'), Path(str(database) + '-shm')):
            if path.exists():
                os.chown(path, account.pw_uid, account.pw_gid)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)


def main():
    prepare_volume()
    volume = Path(os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', DEFAULT_VOLUME))
    database = Path(os.environ.get('GESTORTECH_DATABASE', volume / 'gestortech.sqlite3'))
    if not database.exists():
        subprocess.run(
            [sys.executable, '-B', '-m', 'flask', '--app', 'wsgi:app', 'init-db'],
            check=True,
        )
    port = os.environ.get('PORT', '8000')
    os.execvp('gunicorn', [
        'gunicorn', '--bind', f'0.0.0.0:{port}', '--workers', '1',
        '--threads', '4', '--timeout', '60', '--access-logfile', '-',
        '--error-logfile', '-', 'wsgi:app',
    ])


if __name__ == '__main__':
    main()
