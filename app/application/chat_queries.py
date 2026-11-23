"""Read-only chat queries over the data allowed in each interface."""
import re

from app.application.catalog import catalog_text, public_catalog
from app.domain.models import REPAIR_STATUSES


PUBLIC_BLOCKED = re.compile(
    r'\b(?:usuarios?|contrasenas?|credenciales?|clientes?|tecnicos?|administradores?|'
    r'reparaciones?|ordenes?|movimientos?|privad[oa]s?|intern[oa]s?|stock|existencias)\b'
)
CATALOG_WORDS = set((
    'a al alguno algo buscar con cual cuales cuanto cuesta cuestan de del disponible disponibles '
    'el en es esta estan hay la las lo los me mi modelo modelos mostrar muestra muestrame opciones para '
    'por precio precios producto productos que quiero repuesto repuestos se sirve su tienen tiene un una ver y '
    'busco necesito puede puedes pueden quisiera saber ofrecen oferta hola porfa favor gracias '
    'sus venden vendes costo costos queda quedan comprar consulta consultar catalogo alguna '
    'algunas recomiendame recomienda recomendar'
).split())
CATALOG_INTENT = re.compile(r'\b(?:productos?|repuestos?|opciones|catalogo|disponibles)\b')
REPAIR_CODE = re.compile(r'(?<!\w)GT-[0-9A-F]{32}(?!\w)', re.IGNORECASE)
REPAIR_TOPIC = re.compile(r'\b(?:reparacion(?:es)?|orden(?:es)?|servicios?)\b')
ACCOUNT_TOPIC = re.compile(r'\b(?:usuarios?|tecnicos?|administradores?|permisos|contrasenas?|credenciales?)\b')


def public_chat_blocked(message):
    """Avoid forwarding private operational requests to the model."""
    return bool(PUBLIC_BLOCKED.search(catalog_text(message)))


def public_product_search(db, message):
    text = catalog_text(message)
    terms = set(re.findall(r'\w+', text)) - CATALOG_WORDS
    if not terms and not CATALOG_INTENT.search(text):
        return []
    products = public_catalog(db)
    return [
        product for product in products
        if all(term in catalog_text(f"{product['name']} {product['category']} {product['description']}") for term in terms)
        and (terms or product['available'])
    ][:6]


def staff_repair_summary(db, user, text):
    """Apply the same assignment boundary as the repairs screen."""
    scope = ' AND assigned_to=?' if user['role'] == 'technician' else ''
    params = (user['id'],) if scope else ()
    code = REPAIR_CODE.search(text)
    if code:
        row = db.execute(
            f'SELECT id, status FROM repairs WHERE tracking_code=?{scope}',
            (code.group().upper(), *params),
        ).fetchone()
        if not row:
            return 'No encontré una reparación accesible con ese código.', None, None
        return f"Estado de la reparación: {row['status']}.", row['id'], None

    normalized = catalog_text(text)
    status = next((status for status in REPAIR_STATUSES if catalog_text(status) in normalized), None)
    if not status and 'listas' in normalized and 'entregar' in normalized:
        status = 'Listo para entregar'
    filters = [status] if status else []
    view = None
    if not status and re.search(r'\bpendientes?\b', normalized):
        filters = [item for item in REPAIR_STATUSES if item not in {'Listo para entregar', 'Entregado', 'Cancelado'}]
        view = 'pending'
    states = f" AND status IN ({','.join('?' for _ in filters)})" if filters else ''
    rows = db.execute(
        f'SELECT status, COUNT(*) AS total FROM repairs WHERE 1=1{scope}{states} GROUP BY status',
        (*params, *filters),
    ).fetchall()
    counts = {row['status']: row['total'] for row in rows}
    summary = '\n'.join(f'{status}: {counts[status]}' for status in REPAIR_STATUSES if status in counts)
    return summary or 'No hay reparaciones para esa consulta.', None, {'status': status, 'view': view}
