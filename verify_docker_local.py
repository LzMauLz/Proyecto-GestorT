"""Manual Docker/Compose acceptance check using a new disposable project.

Run only after approval: python -B verify_docker_local.py
Copies a whitelist build context; does not mount host data or load .env.
"""
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request


def main():
    source = Path(__file__).resolve().parent
    project = 'gestortech-qa-' + secrets.token_hex(6)
    with tempfile.TemporaryDirectory(prefix=project + '-') as directory:
        root = Path(directory)
        context = root / 'context'
        context.mkdir()
        for name in ('Dockerfile', 'requirements.txt', 'wsgi.py', 'README.md'):
            shutil.copyfile(source / name, context / name)
        for name in ('app', 'config'):
            shutil.copytree(source / name, context / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.env', '.env.*'))
        empty = root / 'empty.env'
        empty.write_text('', encoding='utf-8')
        override = root / 'compose.qa.json'
        override.write_text(json.dumps({'services': {'gestortech': {
            'build': {'context': context.as_posix()},
            'image': project + ':local',
            'ports': ['127.0.0.1:5068:8000'],
            'restart': 'no',
        }}}), encoding='utf-8')
        # Override ports explicitly to avoid also publishing the demo's usual port.
        override_yaml = root / 'compose.qa.yml'
        override_yaml.write_text('services:\n  gestortech:\n    ports: !override\n      - "127.0.0.1:5068:8000"\n', encoding='utf-8')
        env = dict(os.environ)
        env.update(GESTORTECH_SECRET_KEY=secrets.token_hex(32),
                   DOCKER_GROQ_ENABLED='false', DOCKER_GROQ_API_KEY='', DOCKER_GROQ_MODEL='')
        docker = ['docker', '--config', str(root / 'docker-config'),
                  '--host', 'npipe:////./pipe/docker_engine']
        compose = docker + ['compose', '--env-file', str(empty), '-p', project,
                            '-f', str(source / 'docker-compose.yml'),
                            '-f', str(override), '-f', str(override_yaml)]

        def run(args, **kwargs):
            return subprocess.run(args, env=env, check=True, text=True, **kwargs)

        def execute(code):
            return run(compose + ['exec', '-T', 'gestortech', 'python', '-B', '-'],
                       input=code, capture_output=True).stdout.strip()

        def wait_http():
            for attempt in range(40):
                try:
                    with urllib.request.urlopen('http://127.0.0.1:5068/catalog', timeout=2) as response:
                        assert response.status == 200
                        return
                except OSError:
                    time.sleep(1)
            raise RuntimeError('El contenedor no respondió en el puerto QA.')

        try:
            print('QA_PROJECT=' + project, flush=True)
            run(compose + ['build', 'gestortech'])
            run(compose + ['up', '-d', '--no-build'])
            wait_http()
            print('PASS build, inicio y catalogo HTTP 200', flush=True)
            result = execute("""
import os, io
from PIL import Image
from werkzeug.security import generate_password_hash
from werkzeug.datastructures import FileStorage
from app import create_app
from app.infrastructure.database import get_db
from app.application.services import create_product
from app.infrastructure.product_images import prepare_image,store_image
assert os.getuid()==10001
try:
    with open('/app/qa-write-denied','w') as stream: stream.write('qa')
except OSError:
    pass
else:
    raise AssertionError('La raiz permite escritura')
app=create_app()
assert app.extensions['gestortech_ai_provider'] is None
with app.app_context():
    db=get_db()
    assert db.execute('PRAGMA foreign_keys').fetchone()[0]==1
    db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',('Admin QA','admin@example.test',generate_password_hash('Solo-QA-Temporal-2026!'),'admin','2026-01-01')); db.commit()
    pid=create_product(db,{'name':'Producto Docker QA','description':'Ficticio','price':'12345','stock':3,'user_id':1})
    image=io.BytesIO(); Image.new('RGB',(20,20),'purple').save(image,format='PNG'); image.seek(0)
    key=store_image(prepare_image(FileStorage(stream=image,filename='qa.png')))
    db.execute('UPDATE products SET published=1,image_key=? WHERE id=?',(key,pid)); db.commit()
    print('PASS usuario 10001, raiz protegida, SQLite y PNG persistentes, Groq desactivado')
""")
            print(result, flush=True)
            client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            page = client.open('http://127.0.0.1:5068/login').read().decode()
            token = re.search(r'name="_csrf_token" value="([^"]+)"', page).group(1)
            data = urllib.parse.urlencode({'_csrf_token': token, 'email': 'admin@example.test',
                                          'password': 'Solo-QA-Temporal-2026!'}).encode()
            response = client.open('http://127.0.0.1:5068/login', data=data)
            assert response.url.endswith('/dashboard') and 'Panel del taller' in response.read().decode()
            print('PASS login real por HTTP con CSRF y dashboard', flush=True)
            run(compose + ['restart', 'gestortech'])
            wait_http()
            html = client.open('http://127.0.0.1:5068/catalog').read().decode()
            assert 'Producto Docker QA' in html
            image_path = re.search(r'src="(/catalog/images/[^"]+)"', html).group(1)
            with client.open('http://127.0.0.1:5068' + image_path) as response:
                assert response.headers['Content-Type'].startswith('image/png')
                assert response.read().startswith(b'\x89PNG')
            print('PASS SQLite e imagen sobreviven al reinicio', flush=True)
            container = run(compose + ['ps', '-q', 'gestortech'], capture_output=True).stdout.strip()
            config = run(docker + ['inspect', '--format', '{{.HostConfig.ReadonlyRootfs}} {{.Config.User}}', container], capture_output=True).stdout.strip()
            assert config == 'true 10001:10001'
            print('PASS configuracion efectiva read-only y sin root', flush=True)
        finally:
            # Only this random QA project's resources are removed, never other volumes.
            run(compose + ['down', '-v', '--remove-orphans'])
            print('QA_CLEANUP=' + project, flush=True)


if __name__ == '__main__':
    main()
