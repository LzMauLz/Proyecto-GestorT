import csv
import io
import json
import secrets
import zipfile
import sqlite3
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for, send_file
from openpyxl import load_workbook
from werkzeug.security import generate_password_hash

from app.application.services import create_product, create_repair, move_stock, now_iso, update_product, update_repair_status
from app.application.ai_import import prepare_product_proposal
from app.application.catalog import public_catalog, set_publication, set_availability
from app.infrastructure.product_images import prepare_image, store_image, discard_image, image_path
from app.domain.models import DomainError, REPAIR_STATUSES, TRANSITIONS
from app.infrastructure.database import get_db
from app.web.auth import current_user, login_required, roles_required

web_bp = Blueprint('web', __name__)
MAX_ROWS = 1000
MAX_COLUMNS = 30
MAX_UNCOMPRESSED_XLSX = 20 * 1024 * 1024


def _header_key(value):
    return ' '.join(str(value or '').strip().lower().replace('_',' ').split())


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
        try:
            item['price'] = str('' if item['price'] is None else item['price']).strip().replace('$','').replace(' ','')
            item['stock'] = str('' if item['stock'] is None else item['stock']).strip()
            if not item['price'] or not item['stock'] or not str(item['name'] or '').strip():
                raise ValueError
            if ',' in item['price']:
                raise ValueError
            price_value=Decimal(item['price'])
            stock_value=Decimal(item['stock'])
            if not price_value.is_finite() or price_value < 0 or price_value > Decimal('92233720368547758.07') or price_value != price_value.quantize(Decimal('0.01')):
                raise ValueError
            if not stock_value.is_finite() or stock_value < 0 or stock_value > 2_147_483_647 or stock_value != stock_value.to_integral_value():
                raise ValueError
            item['price']=str(price_value)
            item['stock']=str(int(stock_value))
            item['source_row'] = number
            item['name'] = str(item['name']).strip()
            item['description'] = str(item['description'] or '').strip()
            item['category'] = str(item['category'] or '').strip()
            if len(item['name']) > 160 or len(item['description']) > 2000 or len(item['category']) > 100:
                raise ValueError
            normalized.append(item)
        except (ValueError, InvalidOperation, TypeError):
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
        text = raw.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(text, newline=''))
        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError('El archivo está vacío.')
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
    return render_template('assistant.html', assistant_available=current_app.extensions.get('gestortech_ai_provider') is not None)

@web_bp.route('/repairs/new', methods=['GET','POST'])
@roles_required('admin','technician')
def repair_new():
    db = get_db(); user = current_user()
    technicians = db.execute("SELECT id,name FROM users WHERE role='technician' AND active=1 ORDER BY name").fetchall()
    if request.method == 'POST':
        try:
            assigned = request.form.get('assigned_to') or None
            repair_id, code = create_repair(db, {'device':request.form.get('device'),'issue':request.form.get('issue'),'assigned_to':int(assigned) if assigned else None},user['id'],user['role'])
            flash(f'Reparación registrada. Código de seguimiento: {code}','success')
            return redirect(url_for('web.repair_detail',repair_id=repair_id))
        except (DomainError,ValueError) as exc:
            flash(getattr(exc,'message',str(exc)),'error')
    return render_template('repair_form.html',technicians=technicians)

@web_bp.get('/repairs/<int:repair_id>')
@roles_required('admin','technician')
def repair_detail(repair_id):
    user=current_user(); db=get_db()
    query='SELECT r.*,u.name AS technician FROM repairs r LEFT JOIN users u ON u.id=r.assigned_to WHERE r.id=?'
    repair=db.execute(query,(repair_id,)).fetchone()
    if not repair: abort(404)
    if user['role']!='admin' and repair['assigned_to'] != user['id']: abort(403)
    history=db.execute('SELECT h.*,u.name AS author FROM repair_history h JOIN users u ON u.id=h.user_id WHERE repair_id=? ORDER BY h.id DESC',(repair_id,)).fetchall()
    technicians=db.execute("SELECT id,name FROM users WHERE role='technician' AND active=1 ORDER BY name").fetchall()
    return render_template('repair_detail.html',repair=repair,history=history,technicians=technicians,
                           statuses=REPAIR_STATUSES,allowed=TRANSITIONS.get(repair['status'],set()))

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

@web_bp.get('/products')
@roles_required('admin','technician')
def products():
    db=get_db()
    items=db.execute('SELECT p.*,u.name AS last_user FROM products p LEFT JOIN inventory_movements m ON m.product_id=p.id LEFT JOIN users u ON u.id=m.user_id WHERE p.active=1 GROUP BY p.id ORDER BY p.name').fetchall()
    return render_template('products.html',products=items)


@web_bp.get('/catalog')
def catalog():
    try:
        products = public_catalog(get_db())
    except sqlite3.Error:
        current_app.logger.warning('El catálogo no pudo consultar la base de datos.')
        response = current_app.make_response((render_template('catalog.html', products=[], catalog_error=True), 503))
    else:
        response = current_app.make_response(render_template('catalog.html', products=products))
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
    return redirect(url_for('web.products'))


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
    return redirect(url_for('web.products'))

@web_bp.route('/products/new',methods=['GET','POST'])
@roles_required('admin')
def product_new():
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
            data = {'name': request.form.get('name'), 'description': request.form.get('description'), 'category': request.form.get('category'), 'price': request.form.get('price'), 'stock': request.form.get('stock', '0'), 'user_id': current_user()['id']}
            db.execute('BEGIN IMMEDIATE')
            product_id = create_product(db, data, commit=False)
            db.execute('UPDATE products SET available=?,image_key=? WHERE id=?', (int(available), key, product_id))
            db.commit()
            flash('Producto guardado. Revisa su ficha antes de publicarlo.', 'success')
            return redirect(url_for('web.products'))
        except (DomainError, ValueError) as exc:
            db.rollback()
            _discard_failed_product_image(key)
            flash(getattr(exc, 'message', str(exc)), 'error')
        except (OSError, sqlite3.Error):
            db.rollback()
            _discard_failed_product_image(key)
            flash('No se pudo guardar el producto y su imagen. Revisa el archivo e inténtalo nuevamente.', 'error')
    return render_template('product_form.html')


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
            update_product(db, product_id, {'name': request.form.get('name'), 'description': request.form.get('description'), 'category': request.form.get('category'), 'price': request.form.get('price')}, commit=False)
            db.execute('UPDATE products SET available=?,image_key=? WHERE id=?', (int(available), key or product['image_key'], product_id))
            db.commit()
            flash('Producto actualizado.', 'success')
            return redirect(url_for('web.products'))
        except (DomainError, ValueError) as exc:
            db.rollback()
            _discard_failed_product_image(key)
            flash(getattr(exc, 'message', str(exc)), 'error')
        except (OSError, sqlite3.Error):
            db.rollback()
            _discard_failed_product_image(key)
            flash('No se pudo guardar la ficha y su imagen. Revisa el archivo e inténtalo nuevamente.', 'error')
    return render_template('product_edit.html', product=product)


@web_bp.post('/products/<int:product_id>/movement')
@roles_required('admin')
def product_movement(product_id):
    try:
        move_stock(get_db(),product_id,current_user()['id'],request.form.get('kind'),request.form.get('quantity'),request.form.get('note',''))
        flash('Movimiento de inventario guardado.','success')
    except DomainError as exc: flash(exc.message,'error')
    return redirect(url_for('web.products'))

@web_bp.post('/products/<int:product_id>/retire')
@roles_required('admin')
def product_retire(product_id):
    db=get_db(); cursor=db.execute('UPDATE products SET active=0 WHERE id=? AND active=1',(product_id,)); db.commit()
    if cursor.rowcount == 0: abort(404)
    flash('Producto dado de baja. El historial de movimientos se conserva.','success')
    return redirect(url_for('web.products'))

@web_bp.get('/products/import')
@roles_required('admin')
def import_form():
    return render_template('import.html')

@web_bp.post('/products/import/preview')
@roles_required('admin')
def import_preview():
    try:
        rows=parse_product_upload(request.files.get('file'))
        if not rows: raise ValueError('El archivo no contiene filas para importar.')
        rows, import_mode = prepare_product_proposal(rows, current_app.extensions.get('gestortech_ai_provider'))
        batch=secrets.token_urlsafe(18)
        get_db().execute("DELETE FROM import_batches WHERE datetime(created_at) < datetime('now','-1 day')")
        get_db().execute('INSERT INTO import_batches(id,user_id,payload_json,created_at) VALUES(?,?,?,?)',(batch,current_user()['id'],json.dumps(rows,ensure_ascii=False),now_iso()))
        get_db().commit()
        return render_template('import_preview.html',rows=rows,batch=batch,import_mode=import_mode)
    except (ValueError,UnicodeDecodeError) as exc:
        flash(str(exc),'error'); return redirect(url_for('web.import_form'))

@web_bp.post('/assistant/import')
@roles_required('admin')
def assistant_import():
    """Extract only selected product fields locally; files never go to the provider."""
    try:
        fields = set(request.form.getlist('campos'))
        allowed = {'name', 'description', 'category', 'price', 'stock'}
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
        batch = secrets.token_urlsafe(18)
        db = get_db()
        db.execute("DELETE FROM import_batches WHERE datetime(created_at) < datetime('now','-1 day')")
        db.execute('INSERT INTO import_batches(id,user_id,payload_json,created_at) VALUES(?,?,?,?)', (batch, current_user()['id'], json.dumps(rows, ensure_ascii=False), now_iso()))
        db.commit()
        return render_template('import_preview.html', rows=rows, batch=batch, import_mode='manual')
    except (ValueError, UnicodeDecodeError) as exc:
        flash(str(exc), 'error')
        return redirect(url_for('web.assistant'))

@web_bp.post('/products/import/<batch>/approve')
@roles_required('admin')
def import_approve(batch):
    db=get_db(); staged=db.execute('SELECT * FROM import_batches WHERE id=? AND user_id=?',(batch,current_user()['id'])).fetchone()
    if not staged: abort(404)
    rows=json.loads(staged['payload_json'])
    approved={int(v) for v in request.form.getlist('row') if v.isdigit()}
    if not approved:
        flash('Selecciona al menos una fila revisada.','error'); return redirect(url_for('web.import_form'))
    try:
        db.execute('BEGIN IMMEDIATE')
        saved=0
        for idx,row in enumerate(rows):
            if idx not in approved: continue
            create_product(db,{'name':request.form.get(f'name_{idx}',row['name']),'description':request.form.get(f'description_{idx}',row['description']),'category':request.form.get(f'category_{idx}',row['category']),'price':request.form.get(f'price_{idx}',row['price']),'stock':request.form.get(f'stock_{idx}',row['stock']),'user_id':current_user()['id']},commit=False)
            saved+=1
        db.execute('DELETE FROM import_batches WHERE id=?',(batch,)); db.commit()
        flash(f'Se guardaron {saved} productos aprobados.','success')
        return redirect(url_for('web.products'))
    except Exception:
        db.rollback(); current_app.logger.error('Falló el guardado de un lote de importación.')
        flash('No fue posible guardar el lote. Revisa precio y cantidad. No se guardó parcialmente.','error')
        return redirect(url_for('web.import_form'))

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
