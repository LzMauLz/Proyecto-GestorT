"""Safe orchestration for the administrative inventory assistant."""
import json
import secrets

from app.application.ports import AIProviderError
from app.application.services import now_iso, move_stock, create_product

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY = 10
MAX_PRODUCT_PROPOSALS = 20
ALLOWED_ACTIONS = {'answer', 'product_description', 'product_proposal', 'stock_proposal'}


def _validate_product_proposal(proposal):
    product_fields = {'name', 'description', 'category', 'price', 'stock'}
    if not isinstance(proposal, dict) or set(proposal) - product_fields:
        raise AIProviderError('La propuesta de producto no tiene un formato válido.')
    if any(not isinstance(proposal.get(key, ''), (str, int, float)) for key in product_fields):
        raise AIProviderError('La propuesta de producto no tiene un formato válido.')
    if len(str(proposal.get('name', ''))) > 160 or len(str(proposal.get('description', ''))) > 2000 or len(str(proposal.get('category', ''))) > 100:
        raise AIProviderError('La propuesta de producto supera los límites permitidos.')
    return proposal


def _validate_response(value):
    if not isinstance(value, dict):
        raise AIProviderError('La respuesta de IA no tiene un formato válido.')
    allowed_envelope = {'message', 'action', 'proposal'}
    product_fields = {'name', 'description', 'category', 'price', 'stock'}
    aliases = {'producto', 'product'}
    unexpected = set(value) - allowed_envelope - product_fields - aliases - {'products'}
    if unexpected:
        raise AIProviderError('La respuesta de IA no tiene un formato válido.')
    message = value.get('message', '')
    action = value.get('action', 'answer')
    if action in ('crear_producto', 'crear producto', 'product_create'):
        action = 'product_proposal'
    if not isinstance(message, str) or len(message) > 4000 or action not in ALLOWED_ACTIONS:
        raise AIProviderError('La respuesta de IA no tiene un formato válido.')
    proposal = value.get('proposal')
    if action == 'product_proposal' and proposal is None:
        for alias in aliases:
            if isinstance(value.get(alias), dict):
                proposal = value[alias]
                break
    if action == 'product_proposal' and proposal is None and set(value) & product_fields:
        proposal = {key: value[key] for key in product_fields if key in value}
    if action == 'product_proposal' and proposal is None and isinstance(value.get('products'), list):
        proposal = {'products': value['products']}
    if action == 'product_proposal' and proposal is not None and not message:
        message = 'Propuesta de producto preparada para revisión.'
    if proposal is not None and not isinstance(proposal, dict):
        raise AIProviderError('La propuesta de IA no tiene un formato válido.')
    if action == 'product_proposal' and proposal is not None:
        if isinstance(proposal.get('products'), list):
            if set(proposal) != {'products'} or not 1 <= len(proposal['products']) <= MAX_PRODUCT_PROPOSALS:
                raise AIProviderError('La propuesta debe contener entre 1 y 20 productos.')
            proposal = {'products': [_validate_product_proposal(item) for item in proposal['products']]}
        else:
            proposal = _validate_product_proposal(proposal)
    if action == 'stock_proposal' and proposal is not None:
        if set(proposal) - {'product_id', 'kind', 'quantity', 'note'}:
            raise AIProviderError('La propuesta de inventario no tiene un formato válido.')
        if proposal.get('kind') not in ('entrada', 'salida') or not isinstance(proposal.get('product_id'), int):
            raise AIProviderError('La propuesta de inventario no tiene un formato válido.')
        if not isinstance(proposal.get('quantity'), int) or proposal['quantity'] <= 0 or proposal['quantity'] > 2147483647:
            raise AIProviderError('La cantidad propuesta no es válida.')
        if not isinstance(proposal.get('note', ''), str) or len(proposal.get('note', '')) > 500:
            raise AIProviderError('La nota propuesta no es válida.')
    return {'message': message.strip(), 'action': action, 'proposal': proposal}


def inventory_snapshot(db, question):
    """Return factual, bounded inventory context for the model."""
    lowered = question.lower()
    products = []
    if any(term in lowered for term in ('bajo', 'agotado', 'stock', 'existencias', 'productos')):
        rows = db.execute(
            'SELECT id,name,category,stock,price_cents FROM products WHERE active=1 ORDER BY name LIMIT 100'
        ).fetchall()
        products = [dict(row) for row in rows]
    movements = []
    if any(term in lowered for term in ('movimiento', 'entrada', 'salida', 'últimos')):
        rows = db.execute(
            'SELECT m.product_id,p.name,m.kind,m.quantity,m.note,m.created_at '
            'FROM inventory_movements m JOIN products p ON p.id=m.product_id '
            'ORDER BY m.id DESC LIMIT 20'
        ).fetchall()
        movements = [dict(row) for row in rows]
    return {'product_count': db.execute('SELECT COUNT(*) AS n FROM products WHERE active=1').fetchone()['n'],
            'low_stock': [item for item in products if item['stock'] <= 2],
            'out_of_stock': [item for item in products if item['stock'] == 0],
            'products': products, 'movements': movements}


def request_assistant(db, provider, user, message, history=None):
    if user['role'] not in ('admin', 'technician'):
        raise AIProviderError('No tienes permiso para usar el asistente.')
    message = str(message or '').strip()
    if not message or len(message) > MAX_MESSAGE_LENGTH:
        raise AIProviderError('Escribe una solicitud de hasta 2.000 caracteres.')
    facts = inventory_snapshot(db, message)
    system = (
        'Eres el asistente interno de GestorTech. Responde en español y solo con JSON válido. '
        'No inventes precios, stock, SKU, compatibilidades ni características. '
        'Nunca confirmes una operación: solo prepara propuestas. '
        'Usa action answer, product_description, product_proposal o stock_proposal. '
        'Para inventario usa únicamente los datos FACTUALES suministrados. '
        'Una propuesta de producto usa name, description, category, price y stock; deja faltantes vacíos. '
        'Para varios productos devuelve proposal con products como lista de hasta 20 objetos. '
        'Una propuesta de stock usa product_id, kind, quantity y note. '
        'El campo message debe explicar lo realizado de forma breve.'
    )
    context = json.dumps({'inventory_facts': facts, 'user_request': message}, ensure_ascii=False)
    messages = [{'role': 'system', 'content': system}]
    for item in (history or [])[-MAX_HISTORY:]:
        if isinstance(item, dict) and item.get('role') in ('user', 'assistant') and isinstance(item.get('content'), str):
            messages.append({'role': item['role'], 'content': item['content'][:2000]})
    messages.append({'role': 'user', 'content': context})
    try:
        result = _validate_response(provider.chat(messages))
    except AIProviderError:
        raise
    except (TimeoutError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        raise AIProviderError('El proveedor IA no está disponible o devolvió una respuesta inválida.') from exc
    if user['role'] == 'technician' and result['action'] != 'answer':
        raise AIProviderError('Los técnicos solo pueden consultar información del inventario.')
    proposal = result['proposal']
    if proposal is not None:
        proposal_id = secrets.token_urlsafe(18)
        operation = 'stock_move' if result['action'] == 'stock_proposal' else 'product_create' if result['action'] == 'product_proposal' else 'description'
        db.execute(
            'INSERT INTO ai_proposals(id,user_id,operation,payload_json,status,created_at) VALUES(?,?,?,?,?,?)',
            (proposal_id, user['id'], operation, json.dumps(proposal, ensure_ascii=False), 'pending', now_iso())
        )
        db.execute(
            'INSERT INTO ai_operations(user_id,operation,result,approval_status,created_at) VALUES(?,?,?,?,?)',
            (user['id'], operation, 'Propuesta creada', 'proposed', now_iso())
        )
        db.commit()
        result['proposal'] = {'id': proposal_id, 'operation': operation, **proposal}
    return result


def resolve_proposal(db, user, proposal_id, approve):
    row = db.execute(
        'SELECT * FROM ai_proposals WHERE id=? AND user_id=? AND status=?', (proposal_id, user['id'], 'pending')
    ).fetchone()
    if not row:
        raise AIProviderError('La propuesta no existe o ya fue resuelta.')
    if not approve:
        db.execute('UPDATE ai_proposals SET status=?,resolved_at=? WHERE id=?', ('cancelled', now_iso(), proposal_id))
        db.execute(
            'UPDATE ai_operations SET approval_status=? WHERE user_id=? AND operation=? AND approval_status=? '
            'AND id=(SELECT MAX(id) FROM ai_operations WHERE user_id=? AND operation=?)',
            ('cancelled', user['id'], row['operation'], 'proposed', user['id'], row['operation'])
        )
        db.commit()
        return {'status': 'cancelled'}
    payload = json.loads(row['payload_json'])
    if row['operation'] == 'stock_move':
        product_id = int(payload.get('product_id', 0))
        quantity = payload.get('quantity')
        kind = payload.get('kind')
        new_stock = move_stock(db, product_id, user['id'], kind, quantity, payload.get('note', 'Asistente IA'))
        result = {'status': 'approved', 'product_id': product_id, 'stock': new_stock}
    elif row['operation'] == 'product_create':
        products = payload.get('products') if isinstance(payload.get('products'), list) else [payload]
        product_ids = []
        for product in products:
            product_ids.append(create_product(db, {
                'name': product.get('name', ''), 'description': product.get('description', ''),
                'category': product.get('category', ''), 'price': product.get('price', ''),
                'stock': product.get('stock', 0), 'user_id': user['id']
            }, commit=False))
        result = {'status': 'approved', 'product_id': product_ids[0], 'product_ids': product_ids}
    else:
        result = {'status': 'approved', 'proposal': payload}
    db.execute('UPDATE ai_proposals SET status=?,resolved_at=? WHERE id=?', ('approved', now_iso(), proposal_id))
    db.execute(
        'UPDATE ai_operations SET approval_status=?,product_id=? WHERE user_id=? AND operation=? '
        'AND approval_status=? AND id=(SELECT MAX(id) FROM ai_operations WHERE user_id=? AND operation=?)',
        ('approved', result.get('product_id'), user['id'], row['operation'], 'proposed', user['id'], row['operation'])
    )
    db.commit()
    return result
