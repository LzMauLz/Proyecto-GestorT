import os
from flask import Flask, abort, jsonify, request
from config.settings import Config
from app.infrastructure import database
from app.web.auth import auth_bp, enforce_csrf
from app.web.pages import web_bp
from app.web.api import api_bp


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config is None:
        app.config.update(Config.from_environment())
    app.config['DATABASE'] = os.environ.get('GESTORTECH_DATABASE', os.path.join(app.instance_path,'gestortech.sqlite3'))
    if test_config:
        app.config.update(test_config)
    if not app.config['SECRET_KEY']:
        if app.testing:
            app.config['SECRET_KEY'] = 'test-only-not-for-deployment'
        else:
            raise RuntimeError('Define GESTORTECH_SECRET_KEY antes de iniciar GestorTech.')
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.dirname(app.config['DATABASE']) or '.', exist_ok=True)
    database.init_app(app)
    from app.infrastructure.ai.groq_adapter import GroqAdapter
    provider = GroqAdapter(app.config['GROQ_API_KEY'], app.config['GROQ_MODEL'], app.config['GROQ_ENABLED'], timeout=app.config['GROQ_TIMEOUT'])
    app.extensions['gestortech_ai_provider'] = provider if provider.available else None
    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.cli.command('init-db')
    def init_db_command():
        database.init_db()
        print('Base de datos inicializada.')

    @app.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Content-Security-Policy', "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        if request.path == '/track' or request.path.startswith('/api/seguimiento/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.before_request
    def csrf_protection():
        enforce_csrf()

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    @app.errorhandler(502)
    def http_error(error):
        code = error.code
        message = error.description if code in (400,409,413,502) else {
            401:'Autenticación requerida.',
            403:'No tienes permiso para realizar esta acción.',
            404:'No se encontró el recurso solicitado.',
            409:'La operación entra en conflicto con el estado actual.'
        }.get(code, 'Solicitud no válida.')
        if request.path.startswith('/api/'):
            return jsonify({'error': message}), code
        return message, code

    @app.errorhandler(500)
    def internal_error(error):
        if request.path.startswith('/api/'):
            app.logger.exception('Error interno en la API.')
            return jsonify({'error': 'Error interno del servidor. Revisa la terminal de GestorTech.'}), 500
        raise error

    return app
