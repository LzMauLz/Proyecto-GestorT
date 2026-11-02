from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import secrets

from app.domain.models import DomainError, REPAIR_STATUSES, TRANSITIONS


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def to_cents(value):
    try:
        amount = Decimal(str(value).strip())
        if not amount.is_finite() or amount < 0 or amount > Decimal('92233720368547758.07'):
            raise ValueError
        if amount != amount.quantize(Decimal('0.01')):
            raise ValueError
        return int(amount * 100)
    except (InvalidOperation, ValueError, AttributeError):
        raise DomainError('El precio debe ser un número igual o mayor que cero.')


def create_product(db, data, commit=True):
    name = str(data.get('name', '')).strip()
    if not name or len(name) > 160:
        raise DomainError('El nombre del producto es obligatorio y admite hasta 160 caracteres.')
    try:
        stock = int(data.get('stock', 0))
        if stock < 0 or stock > 2_147_483_647:
            raise ValueError
    except (TypeError, ValueError):
        raise DomainError('La cantidad inicial debe ser un entero igual o mayor que cero.')
    cur = db.execute('INSERT INTO products(name,description,category,price_cents,stock,created_at) VALUES(?,?,?,?,?,?)',
                     (name, str(data.get('description','')).strip()[:2000], str(data.get('category','')).strip()[:100], to_cents(data.get('price',0)), stock, now_iso()))
    if stock:
        db.execute('INSERT INTO inventory_movements(product_id,user_id,kind,quantity,note,created_at) VALUES(?,?,?,?,?,?)',
                   (cur.lastrowid, data['user_id'], 'entrada', stock, 'Stock inicial', now_iso()))
    if commit:
        db.commit()
    return cur.lastrowid


def update_product(db, product_id, data):
    name = str(data.get('name', '')).strip()
    if not name or len(name) > 160:
        raise DomainError('El nombre del producto es obligatorio y admite hasta 160 caracteres.')
    exists = db.execute('SELECT id FROM products WHERE id=? AND active=1', (product_id,)).fetchone()
    if not exists:
        raise DomainError('Producto no disponible.', 404)
    with db:
        db.execute('UPDATE products SET name=?,description=?,category=?,price_cents=? WHERE id=?',
                   (name, str(data.get('description','')).strip()[:2000], str(data.get('category','')).strip()[:100],
                    to_cents(data.get('price')), product_id))


def move_stock(db, product_id, user_id, kind, quantity, note=''):
    if kind not in ('entrada','salida'):
        raise DomainError('Tipo de movimiento no válido.')
    try:
        quantity = int(quantity)
        if quantity <= 0 or quantity > 2_147_483_647:
            raise ValueError
    except (TypeError, ValueError):
        raise DomainError('La cantidad debe ser un entero positivo.')
    try:
        db.execute('BEGIN IMMEDIATE')
        product = db.execute('SELECT stock,active FROM products WHERE id=?', (product_id,)).fetchone()
        if not product or not product['active']:
            raise DomainError('Producto no disponible.', 404)
        new_stock = product['stock'] + quantity if kind == 'entrada' else product['stock'] - quantity
        if new_stock > 2_147_483_647:
            raise DomainError('La cantidad supera el límite admitido.')
        if new_stock < 0:
            raise DomainError('La salida supera las existencias disponibles.', 409)
        db.execute('UPDATE products SET stock=? WHERE id=?', (new_stock, product_id))
        db.execute('INSERT INTO inventory_movements(product_id,user_id,kind,quantity,note,created_at) VALUES(?,?,?,?,?,?)',
                   (product_id,user_id,kind,quantity,str(note).strip()[:500],now_iso()))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return new_stock


def create_repair(db, data, user_id, role):
    device = str(data.get('device','')).strip()
    issue = str(data.get('issue','')).strip()
    if not device or len(device) > 160 or not issue or len(issue) > 2000:
        raise DomainError('Indica el equipo y una descripción del problema (máximo 2000 caracteres).')
    assigned = data.get('assigned_to') if role == 'admin' else user_id
    if assigned is not None:
        person = db.execute('SELECT id FROM users WHERE id=? AND active=1 AND role=\'technician\'', (assigned,)).fetchone()
        if not person:
            raise DomainError('Técnico asignado no válido.')
    code = 'GT-' + secrets.token_hex(16).upper()
    stamp = now_iso()
    cur = db.execute('INSERT INTO repairs(tracking_code,device,issue,status,assigned_to,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                     (code,device,issue,'Recibido',assigned,user_id,stamp,stamp))
    db.execute('INSERT INTO repair_history(repair_id,user_id,status,public_note,public_visible,created_at) VALUES(?,?,?,?,?,?)',
               (cur.lastrowid,user_id,'Recibido','Reparación recibida.',1,stamp))
    db.commit()
    return cur.lastrowid, code


def update_repair_status(db, repair_id, actor_id, role, status, internal_note='', public_note='', assigned_to=None):
    if status not in REPAIR_STATUSES:
        raise DomainError('Estado no reconocido.')
    repair = db.execute('SELECT * FROM repairs WHERE id=?', (repair_id,)).fetchone()
    if not repair:
        raise DomainError('Reparación no encontrada.',404)
    if role != 'admin' and repair['assigned_to'] != actor_id:
        raise DomainError('No tienes permiso para modificar esta reparación.',403)
    if status not in TRANSITIONS.get(repair['status'], set()):
        raise DomainError(f'Transición no permitida desde “{repair["status"]}” a “{status}”.',409)
    if assigned_to is not None:
        if role != 'admin':
            raise DomainError('Solo administración puede reasignar reparaciones.',403)
        if not db.execute('SELECT 1 FROM users WHERE id=? AND role=\'technician\' AND active=1',(assigned_to,)).fetchone():
            raise DomainError('Técnico asignado no válido.')
    stamp = now_iso()
    with db:
        if assigned_to is None:
            db.execute('UPDATE repairs SET status=?,updated_at=? WHERE id=?',(status,stamp,repair_id))
        else:
            db.execute('UPDATE repairs SET status=?,assigned_to=?,updated_at=? WHERE id=?',(status,assigned_to,stamp,repair_id))
        db.execute('INSERT INTO repair_history(repair_id,user_id,status,internal_note,public_note,public_visible,created_at) VALUES(?,?,?,?,?,?,?)',
                   (repair_id,actor_id,status,str(internal_note).strip()[:2000],str(public_note).strip()[:500],1 if str(public_note).strip() else 0,stamp))


def public_repair(db, code):
    code=str(code).strip().upper()
    if not code or len(code)>40:
        return None
    repair = db.execute('SELECT tracking_code,status,created_at,updated_at FROM repairs WHERE tracking_code=?',(code,)).fetchone()
    if not repair:
        return None
    history = db.execute('SELECT status,public_note,created_at FROM repair_history WHERE repair_id=(SELECT id FROM repairs WHERE tracking_code=?) AND public_visible=1 ORDER BY id',(code,)).fetchall()
    return {'tracking_code':repair['tracking_code'],'status':repair['status'],'created_at':repair['created_at'],'updated_at':repair['updated_at'],'history':[dict(item) for item in history]}
