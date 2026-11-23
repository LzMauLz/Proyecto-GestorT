"""Public, optionally assisted search for registered compatible parts."""
from flask import Blueprint, current_app, make_response, render_template, request
from werkzeug.exceptions import TooManyRequests

from app.application.catalog import MAX_BRAND_LENGTH, MAX_MODEL_LENGTH
from app.application.compatibility_search import (
    MAX_QUERY_LENGTH,
    find_compatible_parts,
    interpret_device_query,
    prepare_ai_query,
)
from app.application.ports import AIProviderError
from app.infrastructure.database import get_db
from app.web.request_limits import enforce_catalog_ai_limits


catalog_search_bp = Blueprint('catalog_search', __name__)


@catalog_search_bp.route('/catalog/modelos', methods=['GET', 'POST'])
def find():
    provider = current_app.extensions.get('gestortech_ai_provider')
    brand = request.args.get('brand', '').strip()
    model = request.args.get('model', '').strip()
    confirmed = request.args.get('exact') == '1'
    query = ''
    message = ''
    if request.method == 'POST':
        brand, model, confirmed = '', '', False
        try:
            query = prepare_ai_query(request.form.get('q', ''))
        except ValueError as exc:
            message = str(exc)
        else:
            if provider is None:
                message = 'La IA no está disponible. Puedes buscar por modelo de forma manual.'
            else:
                try:
                    enforce_catalog_ai_limits()
                    brand, model = interpret_device_query(provider, query)
                except TooManyRequests:
                    message = 'Por ahora se alcanzó el límite de consultas con IA. Usa la búsqueda manual.'
                except (AIProviderError, TimeoutError, OSError, ValueError, KeyError, TypeError, RuntimeError):
                    message = 'No pudimos interpretar la solicitud con IA. Escribe la marca y el modelo en la búsqueda manual.'
                else:
                    if not model:
                        message = 'Indica un modelo concreto para continuar con la búsqueda.'

    products, choices = [], []
    searched = False
    if len(brand) > MAX_BRAND_LENGTH or len(model) > MAX_MODEL_LENGTH:
        message = 'Acorta la marca o el modelo y vuelve a buscar.'
        brand, model = brand[:MAX_BRAND_LENGTH], model[:MAX_MODEL_LENGTH]
    elif model:
        searched = True
        products, choices = find_compatible_parts(
            get_db(), brand, model, confirmed=confirmed,
            require_confirmation=request.method == 'POST' and not brand,
        )
    elif request.method == 'GET' and (brand or 'model' in request.args):
        message = 'Escribe el modelo del equipo para buscar repuestos.'

    response = make_response(render_template(
        'catalog_search.html', products=products, choices=choices, brand=brand, model=model,
        query=query, message=message, searched=searched, ai_available=provider is not None,
        max_query_length=MAX_QUERY_LENGTH, max_brand_length=MAX_BRAND_LENGTH, max_model_length=MAX_MODEL_LENGTH,
    ))
    response.headers['Cache-Control'] = 'no-store'
    return response
