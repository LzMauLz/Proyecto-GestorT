from flask import Blueprint, abort, current_app, jsonify, request, url_for
from werkzeug.exceptions import TooManyRequests

from app.application.ai_import import prepare_product_proposal
from app.application.ai_assistant import request_assistant, resolve_proposal
from app.application.catalog import catalog_text
from app.application.chat_queries import (
    ACCOUNT_TOPIC, REPAIR_CODE, REPAIR_TOPIC, public_chat_blocked, public_product_search, staff_repair_summary,
)
from app.application.compatibility_search import find_compatible_parts, interpret_device_query, prepare_ai_query
from app.application.ports import AIProviderError
from app.application.services import create_product, create_repair, move_stock, public_repair, update_product, update_repair_status
from app.domain.models import DomainError
from app.infrastructure.database import get_db
from app.web.auth import current_user
from app.web.request_limits import enforce_catalog_ai_limits

api_bp = Blueprint('api', __name__)


def actor(roles=None):
    user=current_user()
    if not user: abort(401,description='Autenticación requerida.')
    if roles and user['role'] not in roles: abort(403)
    return user


def body():
    value=request.get_json(silent=True)
    if not isinstance(value,dict): abort(400,description='El cuerpo debe ser un objeto JSON.')
    return value


def api_error(error):
    abort(error.status_code,description=error.message)


def _chat_json(message, **data):
    response = jsonify(message=message, **data)
    response.headers['Cache-Control'] = 'no-store'
    return response


def _public_cards(products):
    return [
        {
            'name': entry['name'],
            'price_cents': entry['price_cents'],
            'available': bool(entry['available']),
            'url': url_for('web.catalog_product', product_id=entry['id']),
        }
        for entry in products[:6]
    ]


@api_bp.post('/catalogo/chat')
def catalog_chat():
    data = body()
    raw = data.get('mensaje')
    if not isinstance(raw, str):
        abort(400, description='Escribe una consulta de productos.')
    if public_chat_blocked(raw):
        return _chat_json('Puedo ayudarte a encontrar productos, precios y repuestos compatibles.', persistent=False)
    try:
        text = prepare_ai_query(raw)
    except ValueError as exc:
        return _chat_json(str(exc), persistent=False)

    db = get_db()
    if data.get('mode') == 'model':
        manual = [{'label': 'Buscar por modelo manualmente', 'url': url_for('catalog_search.find')}]
        provider = current_app.extensions.get('gestortech_ai_provider')
        if provider is None:
            return _chat_json('Por ahora puedes consultar la compatibilidad en la búsqueda manual.', links=manual)
        try:
            enforce_catalog_ai_limits()
            brand, model = interpret_device_query(provider, text)
        except TooManyRequests:
            return _chat_json('Se alcanzó el límite de consultas con IA. Usa la búsqueda manual.', links=manual)
        except (AIProviderError, TimeoutError, OSError, ValueError, KeyError, TypeError, RuntimeError):
            return _chat_json('Escribe la marca y la variante del equipo en la búsqueda manual.', links=manual)
        products, choices = find_compatible_parts(db, brand, model, require_confirmation=not brand) if model else ([], [])
        if choices:
            links = [
                {'label': f"{choice['brand']} {choice['model']}",
                 'url': url_for('catalog_search.find', brand=choice['brand'], model=choice['model'], exact='1')}
                for choice in choices[:6]
            ]
            return _chat_json('Elige el modelo exacto de tu equipo para continuar.', links=links)
        if products:
            return _chat_json('Estos repuestos están disponibles y tienen compatibilidad confirmada.', products=_public_cards(products))
        return _chat_json('No encontré repuestos disponibles con compatibilidad confirmada. Verifica el modelo y su variante.', links=manual)

    products = public_product_search(db, text)
    if products:
        return _chat_json('Estas fichas coinciden con tu búsqueda.', products=_public_cards(products))
    return _chat_json('No encontré coincidencias. Prueba el nombre del producto o usa el modo Por modelo para consultar compatibilidad.')


@api_bp.post('/taller/chat')
def staff_chat():
    user = actor(('admin', 'technician'))
    data = body()
    message = data.get('mensaje')
    if not isinstance(message, str) or not message.strip() or len(message) > 2000:
        abort(400, description='Escribe una solicitud de hasta 2.000 caracteres.')
    text = catalog_text(message)
    db = get_db()

    if ACCOUNT_TOPIC.search(text) and (not REPAIR_TOPIC.search(text) or any(term in text for term in ('contrasena', 'credencial'))):
        if user['role'] != 'admin':
            return _chat_json('La gestión de usuarios está disponible para administración.', persistent=False)
        if any(word in text for word in ('contrasena', 'credencial')):
            return _chat_json('Usa el proceso de acceso correspondiente para gestionar credenciales.', persistent=False)
        count = db.execute('SELECT COUNT(*) FROM users WHERE active=1').fetchone()[0]
        return _chat_json(f'Usuarios activos en el taller: {count}.', persistent=False,
                          links=[{'label': 'Crear usuario', 'url': url_for('web.user_new')}])

    if REPAIR_CODE.search(message) or REPAIR_TOPIC.search(text):
        if not REPAIR_CODE.search(message) and any(term in text for term in ('crear', 'registrar', 'nueva')):
            return _chat_json('Abre el formulario para registrar una reparación.', links=[
                {'label': 'Nueva reparación', 'url': url_for('web.repair_new')},
            ])
        reply, repair_id, filters = staff_repair_summary(db, user, message)
        link = (
            {'label': 'Abrir reparación', 'url': url_for('web.repair_detail', repair_id=repair_id)}
            if repair_id else {'label': 'Abrir bandeja', 'url': url_for('web.repairs', **(filters or {}))}
        )
        return _chat_json(reply, persistent=False, links=[link])

    if 'importar' in text or 'xlsx' in text or 'csv' in text:
        if user['role'] != 'admin':
            return _chat_json('La importación está disponible para administración.')
        return _chat_json('Abre el formulario de importación para cargar y revisar el archivo.', links=[
            {'label': 'Importar productos', 'url': url_for('web.import_form')},
        ])

    if ('stock' in text or 'existencias' in text or 'unidades' in text) and ('pocas' in text or 'bajo' in text):
        count = db.execute('SELECT COUNT(*) FROM products WHERE active=1 AND stock<=2').fetchone()[0]
        return _chat_json(f'Productos activos con dos unidades o menos: {count}.', links=[
            {'label': 'Revisar existencias', 'url': url_for('web.products', stock='low')},
        ])

    if 'que puedes hacer' in text or text.strip(' ¿?!') == 'ayuda':
        return _chat_json('Puedo consultar reparaciones y existencias, y guiarte en las tareas del taller según tu rol.', links=[
            {'label': 'Reparaciones', 'url': url_for('web.repairs')},
            {'label': 'Inventario', 'url': url_for('web.products')},
        ])

    if 'catalogo' in text and any(term in text for term in ('publicar', 'retirar', 'compatib', 'foto', 'imagen')):
        if user['role'] != 'admin':
            return _chat_json('Administración gestiona la publicación, las fotos y la compatibilidad del catálogo.')
        return _chat_json('En Inventario, localiza el producto. Desde ahí puedes publicarlo o retirarlo. Abre su edición para gestionar la foto y los modelos compatibles.', links=[
            {'label': 'Gestionar productos en Inventario', 'url': url_for('web.products')},
            {'label': 'Abrir el catálogo público', 'url': url_for('web.catalog')},
        ])

    if '@' in message or any(term in text for term in ('telefono', 'correo', 'del cliente', 'datos personales', 'nota interna')):
        return _chat_json('Escribe la consulta con datos de inventario y omite los datos personales.', persistent=False)
    provider = current_app.extensions.get('gestortech_ai_provider')
    if provider is None:
        return _chat_json('Puedes consultar los productos desde Inventario mientras la IA está desactivada.', links=[
            {'label': 'Abrir inventario', 'url': url_for('web.products')},
        ])
    try:
        result = request_assistant(db, provider, user, message, data.get('historial', []))
    except AIProviderError:
        current_app.logger.warning('El chat del taller no pudo completar la solicitud de inventario.')
        return _chat_json('La IA no pudo procesar la consulta. Puedes seguir trabajando en Inventario.', links=[
            {'label': 'Abrir inventario', 'url': url_for('web.products')},
        ], persistent=False)
    return _chat_json(**result, inventory_history=True)


@api_bp.get('/csrf')
def csrf():
    from app.web.auth import csrf_token
    return jsonify({'token_csrf':csrf_token()})

@api_bp.get('/openapi.json')
def openapi():
    return jsonify({
      'openapi':'3.1.0','info':{'title':'API de GestorTech','version':'0.1.0'},'servers':[{'url':'/api'}],
      'components':{'securitySchemes':{'sessionCookie':{'type':'apiKey','in':'cookie','name':'session'},'csrfHeader':{'type':'apiKey','in':'header','name':'X-CSRF-Token'}},'schemas':{'Error':{'type':'object','properties':{'error':{'type':'string'}}}}},
      'paths':{
        '/catalogo/chat': {
          'post': {
            'summary': 'Consultar productos y compatibilidad del catálogo público',
            'parameters': [{'in': 'header', 'name': 'X-CSRF-Token', 'required': True, 'schema': {'type': 'string'}}],
            'requestBody': {'required': True, 'content': {'application/json': {'schema': {
              'type': 'object', 'required': ['mensaje'], 'properties': {
                'mensaje': {'type': 'string', 'maxLength': 140},
                'mode': {'type': 'string', 'enum': ['product', 'model']},
              },
            }}}},
            'responses': {'200': {'description': 'Respuesta comercial, fichas públicas o enlaces para precisar el modelo'},
                          '400': {'description': 'Solicitud o CSRF inválido'}},
          },
        },
        '/taller/chat': {
          'post': {
            'summary': 'Consultar el taller y preparar propuestas de inventario según los permisos del usuario',
            'security': [{'sessionCookie': []}],
            'parameters': [{'in': 'header', 'name': 'X-CSRF-Token', 'required': True, 'schema': {'type': 'string'}}],
            'requestBody': {'required': True, 'content': {'application/json': {'schema': {
              'type': 'object', 'required': ['mensaje'], 'properties': {
                'mensaje': {'type': 'string', 'maxLength': 2000},
                'historial': {'type': 'array', 'items': {'type': 'object'}},
              },
            }}}},
            'responses': {'200': {'description': 'Respuesta operativa o propuesta pendiente'},
                          '400': {'description': 'Solicitud o CSRF inválido'},
                          '401': {'description': 'Autenticación requerida'},
                          '403': {'description': 'Permiso insuficiente'}},
          },
        },
        '/productos':{
          'get':{'summary':'Listar productos activos (administrador o técnico)','responses':{'200':{'description':'Lista de productos'},'401':{'description':'Autenticación requerida'}}},
          'post':{'summary':'Registrar producto (administrador)','parameters':[{'in':'header','name':'X-CSRF-Token','required':True,'schema':{'type':'string'}}],'requestBody':{'required':True,'content':{'application/json':{'schema':{'type':'object','required':['nombre','precio'],'properties':{'nombre':{'type':'string'},'descripcion':{'type':'string'},'categoria':{'type':'string'},'precio':{'type':'number','minimum':0},'cantidad_stock':{'type':'integer','minimum':0}}}}}},'responses':{'201':{'description':'Producto registrado'},'400':{'description':'Datos inválidos'},'401':{'description':'No autenticado'},'403':{'description':'Permiso insuficiente'}}}},
        '/productos/{id}':{'put':{'summary':'Actualizar producto (administrador)','parameters':[{'in':'path','name':'id','required':True,'schema':{'type':'integer'}},{'in':'header','name':'X-CSRF-Token','required':True,'schema':{'type':'string'}}],'requestBody':{'required':True,'content':{'application/json':{'schema':{'type':'object','required':['nombre','precio'],'properties':{'nombre':{'type':'string'},'descripcion':{'type':'string'},'categoria':{'type':'string'},'precio':{'type':'number','minimum':0}}}}}},'responses':{'200':{'description':'Producto actualizado'},'404':{'description':'No encontrado'}}}},
        '/productos/{id}/movimientos':{
          'get':{'summary':'Consultar movimientos (administrador o técnico)','parameters':[{'in':'path','name':'id','required':True,'schema':{'type':'integer'}}],'responses':{'200':{'description':'Movimientos'}}},
          'post':{'summary':'Registrar entrada o salida (administrador)','parameters':[{'in':'path','name':'id','required':True,'schema':{'type':'integer'}},{'in':'header','name':'X-CSRF-Token','required':True,'schema':{'type':'string'}}],'requestBody':{'required':True,'content':{'application/json':{'schema':{'type':'object','required':['tipo','cantidad'],'properties':{'tipo':{'type':'string','enum':['entrada','salida']},'cantidad':{'type':'integer','minimum':1},'observacion':{'type':'string'}}}}}},'responses':{'201':{'description':'Movimiento registrado'},'409':{'description':'Existencias insuficientes'}}}},
        '/reparaciones':{
          'get':{'summary':'Listar reparaciones visibles según el rol','responses':{'200':{'description':'Reparaciones'}}},
          'post': {
            'summary': 'Crear reparación (personal autorizado)',
            'description': 'Los datos opcionales de contacto solo se consultan en el detalle interno.',
            'parameters': [{'in': 'header', 'name': 'X-CSRF-Token', 'required': True, 'schema': {'type': 'string'}}],
            'requestBody': {'required': True, 'content': {'application/json': {'schema': {
              'type': 'object', 'required': ['equipo', 'descripcion_problema'], 'properties': {
                'equipo': {'type': 'string'}, 'descripcion_problema': {'type': 'string'},
                'id_tecnico': {'type': 'integer'}, 'nombre_cliente': {'type': 'string', 'maxLength': 120},
                'telefono_cliente': {'type': 'string', 'maxLength': 32}, 'correo_cliente': {'type': 'string', 'maxLength': 254},
              },
            }}}},
            'responses': {'201': {'description': 'Reparación, código de seguimiento y estado inicial'},
                          '400': {'description': 'Datos no válidos'}},
          },
        },
        '/reparaciones/{id}/estado':{'patch':{'summary':'Cambiar estado permitido y guardar historial','parameters':[{'in':'path','name':'id','required':True,'schema':{'type':'integer'}},{'in':'header','name':'X-CSRF-Token','required':True,'schema':{'type':'string'}}],'requestBody':{'required':True,'content':{'application/json':{'schema':{'type':'object','required':['estado'],'properties':{'estado':{'type':'string'},'nota_interna':{'type':'string'},'comentario_publico':{'type':'string'},'id_tecnico':{'type':'integer'}}}}}},'responses':{'200':{'description':'Estado actualizado'},'403':{'description':'Permiso insuficiente'},'409':{'description':'Transición inválida'}}}},
        '/seguimiento/{codigo}':{'get':{'summary':'Consultar estado e historial expresamente publicado','parameters':[{'in':'path','name':'codigo','required':True,'schema':{'type':'string'}}],'responses':{'200':{'description':'Seguimiento público, sin notas internas'},'404':{'description':'Código no encontrado'}}}},
        '/ia/importacion/propuesta':{'post':{'summary':'Validar CSV/XLSX y proponer campos opcionales para revisión humana (administrador); sin proveedor disponible, mantiene modo manual','parameters':[{'in':'header','name':'X-CSRF-Token','required':True,'schema':{'type':'string'}}],'requestBody':{'required':True,'content':{'multipart/form-data':{'schema':{'type':'object','required':['archivo'],'properties':{'archivo':{'type':'string','format':'binary'}}}}}},'responses':{'200':{'description':'Filas normalizadas en modo manual o sugerencias validadas, siempre para revisión humana'},'400':{'description':'Archivo o formato inválido'},'401':{'description':'Autenticación requerida'}}}},
        '/asistente/mensaje':{'post':{'summary':'Enviar una solicitud al asistente IA (admin; técnico solo consulta)','description':'Puede devolver una propuesta de un producto o de hasta 20 productos. La confirmación administrativa es obligatoria.','parameters':[{'in':'header','name':'X-CSRF-Token','required':True,'schema':{'type':'string'}}],'requestBody':{'required':True,'content':{'application/json':{'schema':{'type':'object','required':['mensaje'],'properties':{'mensaje':{'type':'string','maxLength':2000},'historial':{'type':'array'}}}}}},'responses':{'200':{'description':'Respuesta o propuesta pendiente'},'502':{'description':'Proveedor no disponible'},'503':{'description':'Asistente desactivado'}}}},
        '/asistente/propuestas/{id}/confirmar':{'post':{'summary':'Confirmar propuesta IA (solo administrador)','parameters':[{'in':'path','name':'id','required':True,'schema':{'type':'string'}},{'in':'header','name':'X-CSRF-Token','required':True,'schema':{'type':'string'}}],'responses':{'200':{'description':'Operación validada y ejecutada'},'409':{'description':'Propuesta inexistente o ya resuelta'}}}},
        '/asistente/propuestas/{id}/cancelar':{'post':{'summary':'Cancelar propuesta IA (solo administrador)','parameters':[{'in':'path','name':'id','required':True,'schema':{'type':'string'}},{'in':'header','name':'X-CSRF-Token','required':True,'schema':{'type':'string'}}],'responses':{'200':{'description':'Propuesta cancelada'},'409':{'description':'Propuesta inexistente o ya resuelta'}}}},
        '/csrf':{'get':{'summary':'Obtener token CSRF asociado a la sesión','responses':{'200':{'description':'Token CSRF'}}}},
        '/openapi.json':{'get':{'summary':'Especificación OpenAPI de las rutas implementadas','responses':{'200':{'description':'OpenAPI 3.1 JSON'}}}},
      }
    })

@api_bp.get('/productos')
def products_list():
    actor(('admin','technician'))
    rows=get_db().execute('SELECT id AS id_producto,name AS nombre,description AS descripcion,category AS categoria,price_cents AS precio_centavos,stock AS cantidad_stock,active AS activo,created_at AS fecha_creacion FROM products WHERE active=1 ORDER BY name').fetchall()
    return jsonify([dict(row) for row in rows])

@api_bp.post('/productos')
def product_create():
    user=actor(('admin',)); data=body()
    try:
        product_id=create_product(get_db(),{'name':data.get('nombre'),'description':data.get('descripcion',''),'category':data.get('categoria',''),'price':data.get('precio'),'stock':data.get('cantidad_stock',0),'user_id':user['id']})
        return jsonify({'id_producto':product_id}),201
    except DomainError as exc: api_error(exc)

@api_bp.put('/productos/<int:product_id>')
def product_update(product_id):
    actor(('admin',)); data=body()
    try:
        update_product(get_db(),product_id,{'name':data.get('nombre'),'description':data.get('descripcion',''),'category':data.get('categoria',''),'price':data.get('precio')})
        return jsonify({'id_producto':product_id})
    except DomainError as exc: api_error(exc)

@api_bp.get('/productos/<int:product_id>/movimientos')
def movements_list(product_id):
    actor(('admin','technician'))
    if not get_db().execute('SELECT 1 FROM products WHERE id=?',(product_id,)).fetchone(): abort(404)
    rows=get_db().execute('SELECT m.id AS id_movimiento,m.kind AS tipo,m.quantity AS cantidad,m.note AS observacion,m.created_at AS fecha,u.name AS usuario FROM inventory_movements m JOIN users u ON u.id=m.user_id WHERE m.product_id=? ORDER BY m.id DESC',(product_id,)).fetchall()
    return jsonify([dict(row) for row in rows])

@api_bp.post('/productos/<int:product_id>/movimientos')
def movement_create(product_id):
    user=actor(('admin',)); data=body()
    try:
        stock=move_stock(get_db(),product_id,user['id'],data.get('tipo'),data.get('cantidad'),data.get('observacion',''))
        return jsonify({'id_producto':product_id,'cantidad_stock':stock}),201
    except DomainError as exc: api_error(exc)

@api_bp.get('/reparaciones')
def repairs_list():
    user=actor(('admin','technician')); db=get_db()
    columns='id AS id_reparacion,tracking_code AS codigo_seguimiento,device AS equipo,issue AS descripcion_problema,status AS estado,assigned_to AS id_tecnico,created_at AS fecha_creacion,updated_at AS ultima_actualizacion'
    if user['role']=='admin': rows=db.execute(f'SELECT {columns} FROM repairs ORDER BY updated_at DESC').fetchall()
    else: rows=db.execute(f'SELECT {columns} FROM repairs WHERE assigned_to=? ORDER BY updated_at DESC',(user['id'],)).fetchall()
    return jsonify([dict(row) for row in rows])

@api_bp.post('/reparaciones')
def repair_create():
    user=actor(('admin','technician')); data=body()
    try:
        repair_id, code = create_repair(get_db(), {
            'device': data.get('equipo'),
            'issue': data.get('descripcion_problema'),
            'assigned_to': data.get('id_tecnico'),
            'customer_name': data.get('nombre_cliente', ''),
            'customer_phone': data.get('telefono_cliente', ''),
            'customer_email': data.get('correo_cliente', ''),
        }, user['id'], user['role'])
        return jsonify({'id_reparacion':repair_id,'codigo_seguimiento':code,'estado':'Recibido'}),201
    except DomainError as exc: api_error(exc)

@api_bp.patch('/reparaciones/<int:repair_id>/estado')
def repair_update(repair_id):
    user=actor(('admin','technician')); data=body()
    try:
        update_repair_status(get_db(),repair_id,user['id'],user['role'],data.get('estado',''),data.get('nota_interna',''),data.get('comentario_publico',''),data.get('id_tecnico'))
        return jsonify({'id_reparacion':repair_id,'estado':data.get('estado')})
    except DomainError as exc: api_error(exc)

@api_bp.get('/seguimiento/<code>')
def tracking(code):
    result=public_repair(get_db(),code)
    if not result: abort(404)
    return jsonify({'codigo_seguimiento':result['tracking_code'],'estado':result['status'],'fecha_creacion':result['created_at'],'ultima_actualizacion':result['updated_at'],
                    'historial_publico':[{'estado':h['status'],'comentario':h['public_note'],'fecha':h['created_at']} for h in result['history']]})

@api_bp.post('/ia/importacion/propuesta')
def import_proposal():
    actor(('admin',))
    from app.web.pages import parse_product_upload
    try:
        parsed=parse_product_upload(request.files.get('archivo'))
        parsed, mode=prepare_product_proposal(parsed, current_app.extensions.get('gestortech_ai_provider'))
        rows=[]
        for row in parsed:
            item={'fila_origen':row['source_row'],'nombre':row.get('name',''),'descripcion':row.get('description',''),'categoria':row.get('category',''),'precio':row.get('price',''),'cantidad_stock':row.get('stock','')}
            if row.get('ai_suggested'):
                item['sugerencia_ia']=True
                item['valores_originales']=row['original_values']
            if row.get('error'): item['error']=row['error']
            rows.append(item)
        return jsonify({'propuesta':rows,'requiere_revision_humana':True,'modo':mode}),200
    except (ValueError,UnicodeDecodeError) as exc:
        abort(400,description=str(exc))

@api_bp.post('/asistente/mensaje')
def assistant_message():
    user = actor(('admin', 'technician'))
    data = body()
    provider = current_app.extensions.get('gestortech_ai_provider')
    if provider is None:
        abort(503, description='El asistente IA está desactivado o no tiene configuración válida.')
    try:
        result = request_assistant(get_db(), provider, user, data.get('mensaje'), data.get('historial', []))
        return jsonify(result)
    except AIProviderError as exc:
        current_app.logger.warning('El asistente IA no pudo completar la solicitud.')
        abort(502, description='No fue posible procesar la solicitud del asistente. Revisa los datos o usa el flujo manual.')

@api_bp.post('/asistente/propuestas/<proposal_id>/confirmar')
def assistant_confirm(proposal_id):
    user = actor(('admin',))
    try:
        edits = body().get('correcciones') if request.is_json else None
        return jsonify(resolve_proposal(get_db(), user, proposal_id, True, edited_payload=edits))
    except AIProviderError as exc:
        abort(409, description=str(exc))
    except DomainError as exc:
        get_db().rollback()
        api_error(exc)
    except Exception as exc:
        get_db().rollback()
        current_app.logger.warning('No se pudo confirmar propuesta IA (%s).', type(exc).__name__)
        abort(400, description='La propuesta no pudo ejecutarse; revisa sus datos.')

@api_bp.post('/asistente/propuestas/<proposal_id>/cancelar')
def assistant_cancel(proposal_id):
    user = actor(('admin',))
    try:
        return jsonify(resolve_proposal(get_db(), user, proposal_id, False))
    except AIProviderError as exc:
        abort(409, description=str(exc))
