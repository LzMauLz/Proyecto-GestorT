import os
from pathlib import Path


def _load_local_env():
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        name, value = line.split('=', 1)
        name = name.strip()
        value = value.strip()
        if not name or name.startswith('#'):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if value:
            os.environ[name] = value


class Config:
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600
    GROQ_API_KEY = ''
    GROQ_MODEL = ''
    GROQ_ENABLED = False
    GROQ_TIMEOUT = 12

    @classmethod
    def from_environment(cls):
        _load_local_env()
        try:
            timeout = int(os.environ.get('GROQ_TIMEOUT', '12'))
        except ValueError:
            timeout = 12
        values = {
            'SECRET_KEY': os.environ.get('GESTORTECH_SECRET_KEY', ''),
            'SESSION_COOKIE_SECURE': os.environ.get('GESTORTECH_COOKIE_SECURE', '0') == '1',
            'GROQ_API_KEY': os.environ.get('GROQ_API_KEY', ''),
            'GROQ_MODEL': os.environ.get('GROQ_MODEL', ''),
            'GROQ_ENABLED': os.environ.get('GROQ_ENABLED', 'false').strip().lower() == 'true',
            'GROQ_TIMEOUT': max(1, min(timeout, 60)),
        }
        return values
