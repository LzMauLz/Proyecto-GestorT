import csv
import io
import json
import secrets
import re
import zipfile
import sqlite3
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, current_app, flash, jsonify, make_response, redirect, render_template, request, url_for, send_file
from openpyxl import load_workbook
from werkzeug.security import generate_password_hash

from app.application.services import (
    create_product, create_repair, move_stock, now_iso, to_cents, update_product, update_repair_contact, update_repair_status,
)
from app.application.ai_import import prepare_product_proposal
from app.application.catalog import (
    MAX_COMPATIBILITY_TEXT, catalog_text, compatibility_ready, filter_catalog, product_compatibilities, public_catalog,
    public_product, save_product_compatibilities, set_publication, set_availability,
)
from app.infrastructure.product_images import prepare_image, store_image, discard_image, image_path
from app.domain.models import DomainError, PRODUCT_CATEGORIES, REPAIR_STATUSES, TRANSITIONS
from app.infrastructure.database import get_db, normalize_inventory_key
from app.web.auth import current_user, login_required, roles_required

web_bp = Blueprint('web', __name__)
MAX_ROWS = 1000
MAX_COLUMNS = 30
MAX_UNCOMPRESSED_XLSX = 20 * 1024 * 1024
PRODUCTS_PER_PAGE = 8
REPAIRS_PER_PAGE = 20
READY_REPAIR_STATUS = 'Listo para entregar'
PENDING_REPAIR_STATUSES = tuple(
    status for status in REPAIR_STATUSES if TRANSITIONS[status] and status != READY_REPAIR_STATUS
)


def _header_key(value):
    return ' '.join(str(value or '').strip().lower().replace('_',' ').split())


def _form_price(value):
    price = str(value if value is not None else '').strip().removeprefix('$').strip()
    if re.fullmatch(r'[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?', price):
        return price.replace(',', '')
    if re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+),[0-9]{1,2}', price):
        return price.replace('.', '').replace(',', '.')
    if re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{3})+', price):
        return price.replace('.', '')
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,2})?', price):
        raise DomainError('Escribe el precio en pesos, por ejemplo 120000 o 120.000,50.')
    return price


def _normalize_rows(headers, rows):
    aliases = {
        'name': {'nombre','name','producto','product'},
        'description': {'descripcion','descripción','description','detalle'},
        'category': {'categoria','categoría','category'},
        'price': {'precio','precio venta','precio de venta','price','valor'},
        'stock': {'cantidad stock','stock','existencias','cantidad'},
    }
    indexes = {}
    for idx, header in enumerate(headers):
        key = _header_key(header)
        for field, names in aliases.items():
            if key in names and field in indexes:
                raise ValueError(f'Hay varias columnas para {field}. Conserva una columna por campo antes de importar.')
            if key in names:
                indexes[field] = idx
    if 'name' not in indexes:
        raise ValueError('No se encontró una columna de nombre/producto.')
    normalized = []
    for number, row in enumerate(rows, start=2):
        if not row or not any(v not in (None, '') for v in row):
            continue
        if len(row) > MAX_COLUMNS:
            raise ValueError(f'La fila {number} supera el límite de {MAX_COLUMNS} columnas.')
        item = {field: (row[indexes[field]] if indexes.get(field) is not None and indexes[field] < len(row) else '') for field in aliases}
        if len(row) > len(headers):
            raise ValueError(f'La fila {number} tiene más columnas que el encabezado. Si usas coma como separador, pon entre comillas los valores que contienen comas.')
        try:
            item['price'] = _form_price(item['price'])
            item['stock'] = str('' if item['stock'] is None else item['stock']).strip()
            if not item['price'] or not item['stock'] or not str(item['name'] or '').strip():
                raise ValueError
            to_cents(item['price'])
            stock_value=Decimal(item['stock'])
            if not stock_value.is_finite() or stock_value < 0 or stock_value > 2_147_483_647 or stock_value != stock_value.to_integral_value():
                raise ValueError
            item['stock']=str(int(stock_value))
            item['source_row'] = number
            item['name'] = str(item['name']).strip()
            item['description'] = str(item['description'] or '').strip()
            item['category'] = str(item['category'] or '').strip()
            if len(item['name']) > 160 or len(item['description']) > 2000 or len(item['category']) > 100:
                raise ValueError
            normalized.append(item)
        except (DomainError, ValueError, InvalidOperation, TypeError):
            limits = {'name': 160, 'description': 2000, 'category': 100, 'price': 64, 'stock': 64}
            normalized.append({'source_row': number, **{key: str('' if item.get(key) is None else item.get(key, ''))[:limit] for key, limit in limits.items()},
                               'error':'Nombre, precio o cantidad faltante o inválida. Corrige los campos antes de aprobar.'})
        if len(normalized) > MAX_ROWS:
            raise ValueError(f'El archivo supera el límite de {MAX_ROWS} filas.')
    return normalized


def parse_product_upload(upload):
    if not upload or not upload.filename:
        raise ValueError('Selecciona un archivo CSV o XLSX.')
    name = upload.filename.rsplit('/',1)[-1].rsplit('\\',1)[-1]
    extension = name.rsplit('.',1)[-1].lower() if '.' in name else ''
    raw = upload.stream.read(current_app.config['MAX_CONTENT_LENGTH'] + 1)
    if len(raw) > current_app.config['MAX_CONTENT_LENGTH']:
        raise ValueError('El archivo supera el límite de 5 MB.')
    if extension == 'csv':
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('cp1252')
        try:
            delimiter = max((',', ';'), key=lambda sep: len(next(csv.reader(io.StringIO(text, newline=''), delimiter=sep), [])))
            reader = csv.reader(io.StringIO(text, newline=''), delimiter=delimiter, strict=True)
            headers = next(reader)
        except StopIteration:
            raise ValueError('El archivo está vacío.')
        except csv.Error as exc:
            raise ValueError('No se pudo leer el encabezado del CSV.') from exc
        if len(headers) > MAX_COLUMNS:
            raise ValueError(f'El archivo supera el límite de {MAX_COLUMNS} columnas.')
        rows = []
        try:
            for i, row in enumerate(reader):
                if i >= MAX_ROWS + 1:
                    raise ValueError(f'El archivo supera el límite de {MAX_ROWS} filas.')
                rows.append(row)
        except csv.Error:
            raise ValueError('El CSV contiene filas con formato o tamaño inválido.')
    elif extension == 'xlsx':
        upload_buffer = io.BytesIO(raw)
        try:
            with zipfile.ZipFile(upload_buffer) as archive:
                if any('vbaproject' in entry.filename.lower() or entry.filename.lower().startswith('xl/externallinks/') for entry in archive.infolist()):
                    raise ValueError('No se aceptan macros ni vínculos externos en el libro.')
                if sum(entry.file_size for entry in archive.infolist()) > MAX_UNCOMPRESSED_XLSX or any(entry.file_size / max(entry.compress_size,1) > 100 for entry in archive.infolist()):
                    raise ValueError('El contenido descomprimido supera el límite permitido.')
            upload_buffer.seek(0)
            workbook = load_workbook(upload_buffer, read_only=True, data_only=False, keep_links=False)
            try:
                sheet = workbook.active
                if (sheet.max_column or 0) > MAX_COLUMNS or (sheet.max_row or 0) > MAX_ROWS + 1:
                    raise ValueError('El archivo supera los límites de filas o columnas.')
                values = []
                for index, cells in enumerate(sheet.iter_rows()):
                    if index > MAX_ROWS or len(cells) > MAX_COLUMNS:
                        raise ValueError('El archivo supera los límites de filas o columnas.')
                    if any(cell.data_type == 'f' for cell in cells):
                        raise ValueError('No se aceptan fórmulas en el libro; carga valores.')
                    values.append([cell.value for cell in cells])
                headers = values[0] if values else []
                rows = values[1:]
            finally:
                workbook.close()
        except ValueError:
            raise
        except Exception:
            raise ValueError('El archivo XLSX no se pudo leer. Verifica que sea un libro válido.')
    else:
        raise ValueError('Solo se aceptan archivos CSV y XLSX sin macros.')
    return _normalize_rows(headers, rows)

@web_bp.get('/')
def index():
    return redirect(url_for('web.dashboard') if current_user() else url_for('web.catalog'))

@web_bp.get('/dashboard')
@login_required
def dashboard():
    user = current_user()
    db = get_db()
    if user['role'] == 'admin':
        repairs = db.execute('SELECT r.*,u.name AS technician FROM repairs r LEFT JOIN users u ON u.id=r.assigned_to ORDER BY r.updated_at DESC LIMIT 50').fetchall()
        counts = {'repairs':db.execute('SELECT COUNT(*) n FROM repairs').fetchone()['n'],
                  'products':db.execute('SELECT COUNT(*) n FROM products WHERE active=1').fetchone()['n'],
                  'low_stock':db.execute('SELECT COUNT(*) n FROM products WHERE active=1 AND stock<=2').fetchone()['n']}
    else:
        repairs = db.execute('SELECT r.*,u.name AS technician FROM repairs r LEFT JOIN users u ON u.id=r.assigned_to WHERE r.assigned_to=? ORDER BY r.updated_at DESC LIMIT 50',(user['id'],)).fetchall()
        counts = {'repairs':len(repairs),'products':db.execute('SELECT COUNT(*) n FROM products WHERE active=1').fetchone()['n'],'low_stock':0}
    return render_template('dashboard.html', repairs=repairs, counts=counts)

@web_bp.get('/assistant')
@roles_required('admin', 'technician')
def assistant():
    return redirect(url_for('web.dashboard', chat='open'))


@web_bp.get('/repairs')
@roles_required('admin', 'technician')
def repairs():
    user = current_user()
    db = get_db()
    query = request.args.get('q', '').strip()[:160]
    status = request.args.get('status', '')
    if not status:
        status = {'pending': 'pending', 'ready': READY_REPAIR_STATUS}.get(request.args.get('view'), '')
    conditions = []
    parameters = []
    technicians = []
    technician_id = None

    if user['role'] == 'admin':
        technicians = db.execute("SELECT id,name,active FROM users WHERE role='technician' ORDER BY name,id").fetchall()
        requested_technician = request.args.get('technician', type=int)
        if any(technician['id'] == requested_technician for technician in technicians):
            technician_id = requested_technician
    else:
        technician_id = user['id']
    if technician_id is not None:
        conditions.append('r.assigned_to=?')
        parameters.append(technician_id)

    if query:
        normalized_query = normalize_inventory_key(query)
        conditions.append('(instr(normalize_inventory_key(r.device), ?) > 0 OR instr(lower(r.tracking_code), ?) > 0)')
        parameters.extend((normalized_query, normalized_query))
    if status == 'pending':
        placeholders = ','.join('?' for _ in PENDING_REPAIR_STATUSES)
        conditions.append(f'r.status IN ({placeholders})')
        parameters.extend(PENDING_REPAIR_STATUSES)
    elif status in REPAIR_STATUSES:
        conditions.append('r.status=?')
        parameters.append(status)
    else:
        status = ''

    where = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''
    total = db.execute(f'SELECT COUNT(*) FROM repairs r{where}', parameters).fetchone()[0]
    last_page = max(1, (total + REPAIRS_PER_PAGE - 1) // REPAIRS_PER_PAGE)
    page = min(last_page, max(1, request.args.get('page', 1, type=int)))
    offset = (page - 1) * REPAIRS_PER_PAGE
    orders = db.execute(
        'SELECT r.id,r.device,r.status,r.tracking_code,r.updated_at,u.name AS technician '
        f'FROM repairs r LEFT JOIN users u ON u.id=r.assigned_to{where} '
        'ORDER BY r.updated_at DESC,r.id DESC LIMIT ? OFFSET ?',
        (*parameters, REPAIRS_PER_PAGE, offset),
    ).fetchall()
    filters = {
        'q': query or None,
        'status': status or None,
        'technician': technician_id if user['role'] == 'admin' else None,
    }
    response = make_response(render_template(
        'repairs.html', repairs=orders, statuses=REPAIR_STATUSES, ready_status=READY_REPAIR_STATUS,
        technicians=technicians, filters=filters, page=page, last_page=last_page, total=total, offset=offset,
    ))
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@web_bp.route('/repairs/new', methods=['GET','POST'])
@roles_required('admin','technician')
def repair_new():
    db = get_db(); user = current_user()
    technicians = db.execute("SELECT id,name FROM users WHERE role='technician' AND active=1 ORDER BY name").fetchall()
    if request.method == 'POST':
        try:
            assigned = request.form.get('assigned_to') or None
            repair_id, code = create_repair(db, {
                'device': request.form.get('device'),
                'issue': request.form.get('issue'),
                'assigned_to': int(assigned) if assigned else None,
                'customer_name': request.form.get('customer_name', ''),
                'customer_phone': request.form.get('customer_phone', ''),
                'customer_email': request.form.get('customer_email', ''),
            }, user['id'], user['role'])
            flash(f'Reparación registrada. Código de seguimiento: {code}','success')
            return redirect(url_for('web.repair_detail',repair_id=repair_id))
        except (DomainError,ValueError) as exc:
            flash(getattr(exc,'message',str(exc)),'error')
    response = make_response(render_template('repair_form.html', technicians=technicians))
    response.headers['Cache-Control'] = 'no-store'
    return response

@web_bp.route('/repairs/<int:repair_id>', methods=['GET', 'POST'])
@roles_required('admin','technician')
def repair_detail(repair_id):
    user=current_user(); db=get_db()
    query='SELECT r.*,u.name AS technician FROM repairs r LEFT JOIN users u ON u.id=r.assigned_to WHERE r.id=?'
    repair=db.execute(query,(repair_id,)).fetchone()
    if not repair: abort(404)
    if user['role']!='admin' and repair['assigned_to'] != user['id']: abort(403)
    contact_error = None
    if request.method == 'POST':
        try:
            update_repair_contact(db, repair_id, user['id'], user['role'], request.form)
        except DomainError as exc:
            if exc.status_code != 400:
                abort(exc.status_code)
            contact_error = exc.message
        else:
            flash('Datos del cliente actualizados.', 'success')
            return redirect(url_for('web.repair_detail', repair_id=repair_id, _anchor='repair-client'))
    history=db.execute('SELECT h.*,u.name AS author FROM repair_history h JOIN users u ON u.id=h.user_id WHERE repair_id=? ORDER BY h.id DESC',(repair_id,)).fetchall()
    technicians=db.execute("SELECT id,name FROM users WHERE role='technician' AND active=1 ORDER BY name").fetchall()
    response = make_response(render_template(
        'repair_detail.html', repair=repair, history=history, technicians=technicians,
        statuses=REPAIR_STATUSES, allowed=TRANSITIONS.get(repair['status'], set()), contact_error=contact_error,
    ), 400 if contact_error else 200)
    response.headers['Cache-Control'] = 'no-store'
    return response

@web_bp.post('/repairs/<int:repair_id>/status')
@roles_required('admin','technician')
def repair_status(repair_id):
    user=current_user()
    try:
        assigned=request.form.get('assigned_to') or None
        update_repair_status(get_db(),repair_id,user['id'],user['role'],request.form.get('status',''),
                             request.form.get('internal_note',''),request.form.get('public_note',''),int(assigned) if assigned else None)
        flash('Estado actualizado y guardado en el historial.','success')
    except (DomainError,ValueError) as exc:
        flash(getattr(exc,'message',str(exc)),'error')
    return redirect(url_for('web.repair_detail',repair_id=repair_id))

def _inventory_view():
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)
    return {
        'q': request.args.get('q', '').strip()[:160] or None,
        'category': category if category in PRODUCT_CATEGORIES else None,
        'stock': 'low' if request.args.get('stock') == 'low' else None,
        'page': page if page > 1 else None,
    }


@web_bp.get('/products')
@roles_required('admin','technician')
def products():
    view = _inventory_view()
    query = view['q'] or ''
    category = view['category'] or ''
    conditions = ['active=1']
    parameters = []
    if query:
        conditions.append('instr(normalize_inventory_key(name), ?) > 0')
        parameters.append(normalize_inventory_key(query))
    if category:
        key = normalize_inventory_key(category)
        conditions.append('normalize_inventory_key(category) IN (?, ?)')
        parameters.extend((key, key + 's'))
    if view['stock']:
        conditions.append('stock <= 2')
    where = ' AND '.join(conditions)
    db = get_db()
    total = db.execute(f'SELECT COUNT(*) FROM products WHERE {where}', parameters).fetchone()[0]
    last_page = max(1, (total + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
    page = min(last_page, view['page'] or 1)
    view['page'] = page if page > 1 else None
    offset = (page - 1) * PRODUCTS_PER_PAGE
    items = db.execute(
        f'SELECT * FROM products WHERE {where} ORDER BY normalize_inventory_key(name), id LIMIT ? OFFSET ?',
        (*parameters, PRODUCTS_PER_PAGE, offset),
    ).fetchall()
    page_numbers = sorted({1, last_page, *range(max(1, page - 2), min(last_page, page + 2) + 1)})
    return render_template('products.html', products=items, product_categories=PRODUCT_CATEGORIES,
                           query=query, category=category, view=view, page=page, last_page=last_page,
                           page_numbers=page_numbers, total=total, offset=offset)


@web_bp.get('/catalog')
def catalog():
    try:
        products = public_catalog(get_db())
    except sqlite3.Error:
        current_app.logger.warning('El catálogo no pudo consultar la base de datos.')
        response = current_app.make_response((render_template('catalog.html', products=[], catalog_error=True), 503))
    else:
        query = request.args.get('q', '').strip()[:160]
        category = request.args.get('category', '').strip()[:100]
        available_only = request.args.get('available') == '1'
        filtered = bool(query or category or available_only)
        featured = [] if filtered else sorted(products, key=lambda product: product['id'], reverse=True)[:8]
        categories = sorted({p['category'] or 'General' for p in products}, key=str.casefold)
        category = next((item for item in categories if catalog_text(item) == catalog_text(category)), category)
        response = current_app.make_response(render_template(
            'catalog.html', products=filter_catalog(products, query, category, available_only),
            featured=featured, categories=categories, catalog_query=query, catalog_category=category,
            available_only=available_only, filtered=filtered,
        ))
    response.headers['Cache-Control'] = 'no-store'
    return response


@web_bp.get('/catalog/products/<int:product_id>')
def catalog_product(product_id):
    db = get_db()
    product = public_product(db, product_id)
    if not product:
        abort(404)
    response = make_response(render_template(
        'catalog_product.html', product=product, models=product_compatibilities(db, product_id),
    ))
    response.headers['Cache-Control'] = 'no-store'
    return response


def _image_response(image_key):
    try:
        path = image_path(image_key)
    except ValueError:
        abort(404)
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype='image/png', conditional=False, max_age=0)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@web_bp.get('/catalog/images/<image_key>')
def catalog_image(image_key):
    if not get_db().execute('SELECT 1 FROM products WHERE image_key=? AND active=1 AND published=1', (image_key,)).fetchone():
        abort(404)
    return _image_response(image_key)


def _discard_failed_product_image(key):
    try:
        discard_image(key)
    except (OSError, ValueError):
        current_app.logger.error('No se pudo retirar una imagen no vinculada a un producto.')


@web_bp.route('/products/<int:product_id>/image', methods=['GET', 'POST'])
@roles_required('admin')
def product_image(product_id):
    db = get_db()
    product = db.execute('SELECT image_key FROM products WHERE id=? AND active=1', (product_id,)).fetchone()
    if not product:
        abort(404)
    if request.method == 'GET':
        return _image_response(product['image_key'])
    key = None
    try:
        content = prepare_image(request.files.get('image'))
        if content is None:
            raise ValueError('Selecciona una imagen para el producto.')
        key = store_image(content)
        with db:
            cursor = db.execute('UPDATE products SET image_key=? WHERE id=? AND active=1', (key, product_id))
            if cursor.rowcount != 1:
                raise DomainError('Producto no disponible.', 404)
    except (DomainError, ValueError) as exc:
        _discard_failed_product_image(key)
        abort(getattr(exc, 'status_code', 400), description=getattr(exc, 'message', str(exc)))
    except (OSError, sqlite3.Error):
        _discard_failed_product_image(key)
        abort(500)
    flash('Imagen actualizada. Publicar el producto sigue siendo una decisión independiente.', 'success')
    return redirect(url_for('web.product_edit', product_id=product_id))


@web_bp.post('/products/<int:product_id>/availability')
@roles_required('admin')
def product_availability(product_id):
    value = request.form.get('available')
    if value not in ('0', '1'):
        abort(400, description='Selecciona disponible o no disponible.')
    try:
        set_availability(get_db(), product_id, value == '1')
    except DomainError as exc:
        abort(exc.status_code, description=exc.message)
    flash('Disponibilidad comercial actualizada.', 'success')
    return redirect(url_for('web.products', **_inventory_view()))


@web_bp.post('/products/<int:product_id>/publication')
@roles_required('admin')
def product_publication(product_id):
    value = request.form.get('published')
    if value not in ('0', '1'):
        abort(400, description='Selecciona publicar o retirar del catálogo.')
    try:
        set_publication(get_db(), product_id, value == '1')
    except DomainError as exc:
        abort(exc.status_code, description=exc.message)
    flash('Producto publicado en el catálogo.' if value == '1' else 'Producto retirado del catálogo.', 'success')
    return redirect(url_for('web.products', **_inventory_view()))


@web_bp.post('/products/suggest-description')
@roles_required('admin')
def suggest_description():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) - {'name', 'category', 'description'}:
        return jsonify(error='Revisa los datos del producto.'), 400
    limits = {'name': 160, 'category': 100, 'description': 2000}
    if any(not isinstance(data.get(key, ''), str) or len(data.get(key, '')) > size for key, size in limits.items()) or not data.get('name', '').strip():
        return jsonify(error='Escribe un nombre válido para el producto.'), 400
    row = {key: data.get(key, '').strip() for key in limits}
    suggestions, mode = prepare_product_proposal([{'source_row': 1, **row}], current_app.extensions.get('gestortech_ai_provider'))
    if mode != 'groq' or not suggestions[0]['description']:
        return jsonify(error='La IA no pudo preparar una descripción. Puedes escribirla o reintentar.'), 503
    return jsonify(description=suggestions[0]['description'])

@web_bp.route('/products/new',methods=['GET','POST'])
@roles_required('admin')
def product_new():
    existing_product = None
    if request.method == 'POST':
        db = get_db()
        key = None
        try:
            available = request.form.get('available', '1')
            if available not in ('0', '1'):
                raise ValueError('Selecciona disponible o no disponible.')
            content = prepare_image(request.files.get('image'))
            if content is not None:
                key = store_image(content)
            publish = request.form.get('publish') == '1'
            data = {'name': request.form.get('name'), 'description': request.form.get('description'), 'category': request.form.get('category'), 'price': _form_price(request.form.get('price')), 'stock': request.form.get('stock', '0'), 'user_id': current_user()['id']}
            db.execute('BEGIN IMMEDIATE')
            product_id = create_product(db, data, commit=False)
            db.execute('UPDATE products SET available=?,image_key=?,published=? WHERE id=?', (int(available), key, int(publish), product_id))
            db.commit()
            flash('Producto publicado en el catálogo.' if publish else 'Producto guardado en inventario. Aún no está publicado.', 'success')
            return redirect(url_for('web.products'))
        except (DomainError, ValueError) as exc:
            db.rollback()
            _discard_failed_product_image(key)
            flash(getattr(exc, 'message', str(exc)), 'error')
            if isinstance(exc, DomainError) and exc.status_code == 409:
                existing_product = db.execute(
                    'SELECT id FROM products WHERE active=1 AND normalize_inventory_key(name)=normalize_inventory_key(?) '
                    'AND normalize_inventory_key(category)=normalize_inventory_key(?)',
                    (request.form.get('name', ''), request.form.get('category', '')),
                ).fetchone()
        except (OSError, sqlite3.Error):
            db.rollback()
            _discard_failed_product_image(key)
            flash('No se pudo guardar el producto y su imagen. Revisa el archivo e inténtalo nuevamente.', 'error')
    return render_template('product_form.html', existing_product=existing_product, product_categories=PRODUCT_CATEGORIES)


@web_bp.route('/products/<int:product_id>/edit',methods=['GET','POST'])
@roles_required('admin')
def product_edit(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id=? AND active=1', (product_id,)).fetchone()
    if not product:
        abort(404)
    if request.method == 'POST':
        key = None
        try:
            available = request.form.get('available', str(product['available']))
            if available not in ('0', '1'):
                raise ValueError('Selecciona disponible o no disponible.')
            content = prepare_image(request.files.get('image'))
            if content is not None:
                key = store_image(content)
            db.execute('BEGIN IMMEDIATE')
            publish = request.form.get('publish') == '1'
            update_product(db, product_id, {'name': request.form.get('name'), 'description': request.form.get('description'), 'category': request.form.get('category'), 'price': _form_price(request.form.get('price'))}, commit=False)
            db.execute('UPDATE products SET available=?,image_key=COALESCE(?,image_key),published=CASE WHEN ? THEN 1 ELSE published END WHERE id=?', (int(available), key, publish, product_id))
            db.commit()
            flash('Producto publicado en el catálogo.' if publish else 'Producto actualizado.', 'success')
            return redirect(url_for('web.products', **_inventory_view()))
        except (DomainError, ValueError) as exc:
            db.rollback()
            _discard_failed_product_image(key)
            flash(getattr(exc, 'message', str(exc)), 'error')
        except (OSError, sqlite3.Error):
            db.rollback()
            _discard_failed_product_image(key)
            flash('No se pudo guardar la ficha y su imagen. Revisa el archivo e inténtalo nuevamente.', 'error')
    return render_template('product_edit.html', product=product, product_categories=PRODUCT_CATEGORIES, view=_inventory_view())


@web_bp.route('/products/<int:product_id>/compatibility', methods=['GET', 'POST'])
@roles_required('admin')
def product_compatibility(product_id):
    if not 0 < product_id < 2**63:
        abort(404)
    db = get_db()
    product = db.execute('SELECT id,name FROM products WHERE id=? AND active=1', (product_id,)).fetchone()
    if not product:
        abort(404)
    ready = compatibility_ready(db)
    error = ''
    status = 200
    fields = request.form.getlist('compatibilities') if request.method == 'POST' else []
    if len(fields) == 1:
        value = fields[0]
        try:
            save_product_compatibilities(db, product_id, value)
        except DomainError as exc:
            if exc.status_code == 404:
                abort(404)
            error, status = exc.message, exc.status_code
        else:
            flash('Modelos compatibles actualizados.', 'success')
            return redirect(url_for('web.product_edit', product_id=product_id, **_inventory_view()), code=303)
    else:
        value = '\n'.join(f"{entry['brand']} | {entry['model']}" for entry in product_compatibilities(db, product_id))
        if request.method == 'POST':
            error, status = 'Envía la lista de modelos compatibles para guardar los cambios.', 400
    return render_template(
        'product_compatibility.html', product=product, value=value[:MAX_COMPATIBILITY_TEXT], ready=ready,
        error=error, max_length=MAX_COMPATIBILITY_TEXT, view=_inventory_view(),
    ), status


@web_bp.post('/products/<int:product_id>/movement')
@roles_required('admin')
def product_movement(product_id):
    try:
        move_stock(get_db(),product_id,current_user()['id'],request.form.get('kind'),request.form.get('quantity'),request.form.get('note',''))
        flash('Movimiento de inventario guardado.','success')
    except DomainError as exc: flash(exc.message,'error')
    return redirect(url_for('web.products', **_inventory_view()))

@web_bp.post('/products/<int:product_id>/retire')
@roles_required('admin')
def product_retire(product_id):
    db=get_db(); cursor=db.execute('UPDATE products SET active=0 WHERE id=? AND active=1',(product_id,)); db.commit()
    if cursor.rowcount == 0: abort(404)
    flash('Producto dado de baja. El historial de movimientos se conserva.','success')
    return redirect(url_for('web.products', **_inventory_view()))

@web_bp.get('/products/import')
@roles_required('admin')
def import_form():
    return render_template('import.html', assistant_available=current_app.extensions.get('gestortech_ai_provider') is not None)


def _stage_import(rows):
    use_ai = request.form.get('use_ai') == '1'
    provider = current_app.extensions.get('gestortech_ai_provider') if use_ai else None
    rows, mode = prepare_product_proposal(rows, provider)
    batch = secrets.token_urlsafe(18)
    db = get_db()
    with db:
        db.execute("DELETE FROM import_batches WHERE datetime(created_at) < datetime('now','-1 day')")
        db.execute('INSERT INTO import_batches(id,user_id,payload_json,created_at) VALUES(?,?,?,?)',
                   (batch, current_user()['id'], json.dumps(rows, ensure_ascii=False), now_iso()))
    return render_template('import_preview.html', rows=rows, batch=batch, import_mode=mode,
                           ai_unavailable=use_ai and mode == 'manual')

@web_bp.post('/products/import/preview')
@roles_required('admin')
def import_preview():
    try:
        rows=parse_product_upload(request.files.get('file'))
        if not rows: raise ValueError('El archivo no contiene filas para importar.')
        return _stage_import(rows)
    except (ValueError,UnicodeDecodeError) as exc:
        flash(str(exc),'error'); return redirect(url_for('web.import_form'))

@web_bp.post('/assistant/import')
@roles_required('admin')
def assistant_import():
    """Read the file locally and offer optional suggestions for product fields."""
    try:
        allowed = {'name', 'description', 'category', 'price', 'stock'}
        fields = set(request.form.getlist('campos')) or allowed
        if not fields or not fields <= allowed:
            raise ValueError('Selecciona únicamente los campos de producto disponibles.')
        keyword = request.form.get('palabras', '').strip()
        if len(keyword) > 100:
            raise ValueError('La búsqueda admite hasta 100 caracteres.')
        rows = parse_product_upload(request.files.get('archivo'))
        if keyword:
            words = keyword.casefold().split()
            rows = [row for row in rows if all(word in ' '.join(str(row.get(key, '')) for key in ('name', 'description', 'category')).casefold() for word in words)]
        for row in rows:
            for field in allowed - fields:
                row[field] = ''
            if not {'name', 'price', 'stock'} <= fields:
                row['error'] = 'Completa nombre, precio y cantidad antes de aprobar.'
        if not rows:
            raise ValueError('No hay productos que coincidan; revisa el archivo o las palabras clave.')
        return _stage_import(rows)
    except (ValueError, UnicodeDecodeError) as exc:
        flash(str(exc), 'chat-import-error')
        return redirect(url_for('web.dashboard', chat='import'))

@web_bp.post('/products/import/<batch>/approve')
@roles_required('admin')
def import_approve(batch):
    db = get_db()
    user_id = current_user()['id']
    approved = {int(value) for value in request.form.getlist('row') if re.fullmatch(r'[0-9]{1,4}', value)}
    publish = request.form.get('publish') == '1'
    failed_row = None
    try:
        db.execute('BEGIN IMMEDIATE')
        staged = db.execute('SELECT payload_json FROM import_batches WHERE id=? AND user_id=?', (batch, user_id)).fetchone()
        if not staged:
            abort(404)
        rows = json.loads(staged['payload_json'])
        for index, row in enumerate(rows):
            for key in ('name', 'description', 'category', 'price', 'stock'):
                row[key] = request.form.get(f'{key}_{index}', row[key])
        if not approved or max(approved) >= len(rows):
            raise DomainError('Marca al menos una fila válida antes de guardar.')
        for index in sorted(approved):
            failed_row = rows[index]
            product_id = create_product(db, {**failed_row, 'price': _form_price(failed_row['price']),
                                              'stock': str(failed_row['stock']).strip(), 'user_id': user_id}, commit=False)
            if publish:
                db.execute('UPDATE products SET published=1 WHERE id=?', (product_id,))
        db.execute('DELETE FROM import_batches WHERE id=?', (batch,))
        db.commit()
    except DomainError as exc:
        db.rollback()
        if failed_row is not None:
            failed_row['error'] = exc.message
        flash((f"Fila {failed_row['source_row']}: " if failed_row is not None else '') + exc.message + ' No se guardó ninguna fila.', 'error')
        mode = 'groq' if any(row.get('ai_suggested') for row in rows) else 'manual'
        return render_template('import_preview.html', rows=rows, batch=batch, import_mode=mode,
                               selected_rows=approved, publish=publish), exc.status_code
    except sqlite3.Error:
        db.rollback()
        current_app.logger.error('Falló el guardado de un lote de importación.')
        abort(503, description='El inventario no pudo guardar el lote. Verifica que la base esté actualizada e inténtalo de nuevo.')
    flash(f'{len(approved)} productos publicados en el catálogo.' if publish else f'Se guardaron {len(approved)} productos en inventario. Aún no están publicados.', 'success')
    return redirect(url_for('web.products'))

@web_bp.route('/users/new',methods=['GET','POST'])
@roles_required('admin')
def user_new():
    if request.method=='POST':
        name=request.form.get('name','').strip()[:100]; email=request.form.get('email','').strip().lower()[:254]; password=request.form.get('password',''); role=request.form.get('role','')
        if not name or email.count('@') != 1 or any(ch.isspace() for ch in email) or len(email)>254 or len(password)<12 or role not in {'admin','technician'}:
            flash('Revisa el nombre, el correo, el rol y la contraseña (mínimo 12 caracteres).','error')
        else:
            try:
                get_db().execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',(name,email,generate_password_hash(password),role,now_iso())); get_db().commit()
                flash('Usuario creado.','success'); return redirect(url_for('web.dashboard'))
            except Exception:
                get_db().rollback(); flash('No fue posible crear el usuario. El correo debe ser único.','error')
    return render_template('user_form.html')

@web_bp.route('/track',methods=['GET','POST'])
def track():
    result=None; error=None
    if request.method=='POST':
        code=request.form.get('code','').strip()
        from app.application.services import public_repair
        result=public_repair(get_db(),code)
        if not result: error='No encontramos una reparación con ese código. Verifica los caracteres e inténtalo de nuevo.'
    return render_template('track.html',result=result,error=error)
