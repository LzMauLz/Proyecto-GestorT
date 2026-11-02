import hmac
import secrets
from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.domain.models import DomainError
from app.infrastructure.database import get_db
from app.application.services import now_iso

auth_bp = Blueprint('auth', __name__)


def current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    row = get_db().execute('SELECT id,name,email,role FROM users WHERE id=? AND active=1',(user_id,)).fetchone()
    return dict(row) if row else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for('auth.login', next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            user = current_user()
            if user['role'] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def enforce_csrf():
    if request.method in {'POST','PUT','PATCH','DELETE'}:
        expected = session.get('_csrf_token','')
        provided = request.headers.get('X-CSRF-Token') or request.form.get('_csrf_token','')
        if not expected or not provided or not hmac.compare_digest(expected, provided):
            abort(400, description='Token de seguridad inválido. Recarga la página e inténtalo de nuevo.')


auth_bp.add_app_template_global(current_user, 'current_user')
auth_bp.add_app_template_global(csrf_token, 'csrf_token')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()[:254]
        password = request.form.get('password','')
        row = get_db().execute('SELECT * FROM users WHERE email=? AND active=1',(email,)).fetchone()
        if not row or not check_password_hash(row['password_hash'], password):
            flash('Correo o contraseña no válidos.','error')
        else:
            session.clear()
            session['user_id'] = row['id']
            csrf_token()
            return redirect(url_for('web.dashboard'))
    return render_template('login.html')

@auth_bp.post('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.cli.command('create-admin')
def create_admin():
    """Create the first administrator interactively; never uses a default password."""
    import click
    from flask import current_app
    from app.infrastructure.database import init_db
    init_db()
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE role='admin' AND active=1").fetchone():
        raise click.ClickException('Ya existe una cuenta administradora activa.')
    name = click.prompt('Nombre')
    email = click.prompt('Correo').strip().lower()
    password = click.prompt('Contraseña (mínimo 12 caracteres)', hide_input=True, confirmation_prompt=True)
    if len(password) < 12:
        raise click.ClickException('La contraseña debe tener al menos 12 caracteres.')
    try:
        db.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                   (name.strip(),email,generate_password_hash(password), 'admin', now_iso()))
        db.commit()
    except Exception as exc:
        db.rollback()
        current_app.logger.warning('No fue posible crear la cuenta administrativa (%s).', type(exc).__name__)
        raise click.ClickException('No se pudo crear la cuenta; verifica que el correo sea válido y único.')
    click.echo('Cuenta administradora creada.')
