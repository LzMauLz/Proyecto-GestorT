import csv
import io
import json
import secrets
import zipfile
from decimal import Decimal, InvalidOperation
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from openpyxl import load_workbook
from werkzeug.security import generate_password_hash

from app.application.services import create_product, create_repair, move_stock, now_iso, update_product, update_repair_status
from app.application.ai_import import prepare_product_proposal
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
        'price': {'precio','price','valor'},
        'stock': {'cantidad stock','stock','existencias','cantidad'},
    }
    indexes = {}
    for idx, header in enumerate(headers):
        key = _header_key(header)
        for field, names in aliases.items():
            if key in names and field not in indexes:
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
            item['price'] = str(item['price'] or '').strip().replace('$','').replace(' ','')
            item['stock'] = str(item['stock'] or '').strip()
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
            normalized.append({'source_row':number,'name':str(row[indexes['name']] if indexes['name'] < len(row) else '')[:160],
                               'description':'','category':'','price':'','stock':'','error':'Nombre, precio o cantidad faltante o inválida. Corrige la fuente antes de aprobar.'})
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
                if sum(entry.file_size for entry in archive.infolist()) > MAX_UNCOMPRESSED_XLSX or any(entry.file_size / max(entry.compress_size,1) > 100 for entry in archive.infolist()):
                    raise ValueError('El contenido descomprimido supera el límite permitido.')
            upload_buffer.seek(0)
            workbook = load_workbook(upload_buffer, read_only=True, data_only=True, keep_links=False)
            sheet = workbook.active
            if sheet.max_column > MAX_COLUMNS or sheet.max_row > MAX_ROWS + 1:
                workbook.close()
                raise ValueError('El archivo supera los límites de filas o columnas.')
            iterator = sheet.iter_rows(values_only=True)
            headers = list(next(iterator, ()))
            rows = list(iterator)
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
    return redirect(url_for('web.dashboard') if current_user() else url_for('web.track'))

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

@web_bp.route('/products/new',methods=['GET','POST'])
@roles_required('admin')
def product_new():
    if request.method=='POST':
        try:
            data={'name':request.form.get('name'),'description':request.form.get('description'),'category':request.form.get('category'),'price':request.form.get('price'),'stock':request.form.get('stock','0'),'user_id':current_user()['id']}
            create_product(get_db(),data)
            flash('Producto guardado.','success'); return redirect(url_for('web.products'))
        except DomainError as exc: flash(exc.message,'error')
    return render_template('product_form.html')

@web_bp.route('/products/<int:product_id>/edit',methods=['GET','POST'])
@roles_required('admin')
def product_edit(product_id):
    db=get_db(); product=db.execute('SELECT * FROM products WHERE id=? AND active=1',(product_id,)).fetchone()
    if not product: abort(404)
    if request.method=='POST':
        try:
            update_product(db,product_id,{'name':request.form.get('name'),'description':request.form.get('description'),
                          'category':request.form.get('category'),'price':request.form.get('price')})
            flash('Producto actualizado.','success'); return redirect(url_for('web.products'))
        except DomainError as exc: flash(exc.message,'error')
    return render_template('product_edit.html',product=product)

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
        db.rollback(); current_app.logger.exception('Falló el guardado de un lote de importación.')
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
